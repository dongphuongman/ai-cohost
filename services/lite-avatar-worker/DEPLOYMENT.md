# LiteAvatar Worker — Deployment Guide

This doc covers local testing, production provisioning, API integration,
canary rollout, and day-2 operations for the LiteAvatar worker service.

---

## 1. Local development test

### 1.1 Build the image

```bash
cd services/lite-avatar-worker
docker build -t lite-avatar-worker:latest .
```

Model weights (~5–8 GB) are **not** pulled during build — they are fetched
on first container start via `entrypoint.sh`, so this step finishes fast.

### 1.2 Download avatars

Grab avatar data folders from the
[LiteAvatarGallery](https://modelscope.cn/models/HumanAIGC-Engineering/LiteAvatarGallery)
and place them under `services/lite-avatar-worker/avatars/`:

```
avatars/
├── linh_female/
├── nam_male/
├── huong_female/
├── tuan_male/
└── mai_female/
```

Folder names **must** match `LiteAvatarProvider.AVAILABLE_AVATARS` in
`apps/workers/dh_providers/liteavatar.py`. Avatar binaries are not
committed to git — only the folder structure is.

### 1.3 Start the service (two options)

**A) Standalone compose (service-local, host port 8080):**

```bash
cd services/lite-avatar-worker
docker compose up -d
```

**B) Main infra compose with profile (host port 8088 to avoid adminer):**

```bash
docker compose -f infra/compose/docker-compose.dev.yml \
  --profile lite-avatar up -d lite-avatar-worker
```

The profile guard keeps the service out of the default
`docker compose up` — adding ~5–8 GB of model download to every dev boot
would be unfriendly.

### 1.4 Wait for model download

```bash
docker logs -f lite-avatar-worker
```

Watch for: `[entrypoint] Model download complete`. On first run this
takes 5–10 minutes depending on your connection. The healthcheck is
configured with `start_period: 180s` so the container won't be marked
unhealthy while the model is downloading.

### 1.5 Run the smoke test

```bash
# Standalone compose
LITE_AVATAR_URL=http://localhost:8080 bash tests/test_smoke.sh

# Main infra compose
bash tests/test_smoke.sh   # defaults to http://localhost:8088
```

The test runs 5 steps (health → list → generate → poll → download) and
exits non-zero on any failure. The generated MP4 lands at
`/tmp/test-output.mp4` for manual visual review.

---

## 2. Production deployment — Hetzner CCX33

### 2.1 Specs

| Component     | Value                                            |
| ------------- | ------------------------------------------------ |
| Instance      | Hetzner CCX33 (dedicated AMD)                    |
| vCPU          | 8 dedicated                                      |
| RAM           | 32 GB                                            |
| Disk          | 240 GB NVMe SSD                                  |
| Cost          | ~€52/month                                       |
| OS            | Ubuntu 22.04 LTS                                 |
| GPU           | None — LiteAvatar runs CPU-only at 30 FPS       |

CCX33 gives enough headroom for 4–6 concurrent generations (~4–6 GB
RAM each). If you expect heavier load, scale vertically to CCX43 or run
multiple instances behind a load balancer.

### 2.2 Provision

```bash
# SSH into the box, then:
sudo apt update && sudo apt upgrade -y
sudo apt install -y docker.io docker-compose-plugin git curl
sudo usermod -aG docker $USER && newgrp docker
```

### 2.3 Clone repo and set up avatars

```bash
sudo mkdir -p /opt/cohost && sudo chown $USER /opt/cohost
git clone <your-repo> /opt/cohost
cd /opt/cohost/services/lite-avatar-worker

# Copy avatar data (scp/rsync from your workstation or fetch from object storage)
mkdir -p avatars
rsync -av ~/avatars-gallery/ avatars/
```

### 2.4 Build & start

```bash
cd /opt/cohost/services/lite-avatar-worker
docker compose up -d

# First boot downloads the model — watch progress:
docker logs -f lite-avatar-worker
# Look for "[entrypoint] Model download complete" (5–15 min depending on bandwidth)
```

### 2.5 Verify

```bash
curl http://localhost:8080/health
curl http://localhost:8080/avatars
bash tests/test_smoke.sh
```

---

## 3. Connect API workers to LiteAvatar

The API workers pick up LiteAvatar through the `LITE_AVATAR_URL` env
variable. If it is empty, `LiteAvatarProvider.is_available()` returns
False immediately and the router keeps using HeyGen.

### 3.1 Same Docker network (API + worker on one host)

```bash
# apps/workers .env (or API container env)
LITE_AVATAR_URL=http://lite-avatar-worker:8080
```

The hostname `lite-avatar-worker` resolves via the compose network. No
host ports required.

### 3.2 Separate VPS (API on one host, worker on another)

```bash
LITE_AVATAR_URL=http://<worker-vps-ip>:8080
```

Lock down the worker port at the firewall so only the API hosts can
reach it — the worker has no auth layer of its own.

### 3.3 Verify connection

From the API container:

```bash
docker exec -it cohost-api curl -sf $LITE_AVATAR_URL/health
```

Expect a JSON body like:

```json
{"status": "ok", "service": "lite-avatar-worker", ...}
```

If that succeeds, the next digital-human job will flow through
LiteAvatar automatically (unless `prefer_quality=True`, in which case
the router sticks with HeyGen).

---

## 4. A/B test before full migration

**Do not cut 100% of traffic to LiteAvatar on day one.** Run both
providers in parallel for 1–2 weeks and compare output quality and
stability before retiring HeyGen.

### 4.1 Canary snippet (temporary)

Add a random gate at the top of `DHProviderRouter.select_provider`:

```python
import random

def select_provider(self, request, prefer_quality=False):
    # CANARY: 50% traffic to LiteAvatar during A/B window.
    # Remove this block after 2026-05-01 once confidence is established.
    if (
        not prefer_quality
        and random.random() < 0.5
        and self.liteavatar.is_available()
        and self.liteavatar.supports_avatar(request.avatar_id)
    ):
        return self.liteavatar
    # Fall through to normal routing...
```

Keep the regular routing logic untouched below — this only biases the
coin flip; failures still auto-fall-back to HeyGen.

### 4.2 Metrics to track

| Metric               | Target                                     |
| -------------------- | ------------------------------------------ |
| Success rate         | ≥ 99% per provider                         |
| Avg generation time  | LiteAvatar ≤ 1.5× HeyGen                   |
| Cost per video       | LiteAvatar $0 vs HeyGen $0.40/min baseline |
| P95 latency          | No regression over 2-week window           |

### 4.3 Quality review

Pull 20 random LiteAvatar outputs + 20 HeyGen outputs from the same A/B
window. Manually review side-by-side for:

- Lip-sync accuracy
- Facial naturalness
- Audio quality (gTTS vs ElevenLabs)
- Watermark visibility (must be identical — same ffmpeg filter)

### 4.4 Cut over

Once success rate, latency, and quality all look acceptable for 2 weeks:

1. Remove the canary block.
2. Normal router selection (LiteAvatar preferred, HeyGen fallback)
   takes over and LiteAvatar starts receiving ~100% of eligible traffic.
3. Keep HeyGen API keys valid for at least one more month as an
   emergency fallback.

---

## 5. Monitoring & Troubleshooting

### 5.1 Health endpoint

```bash
curl http://localhost:8080/health
```

Returns `active_jobs` — alert if it stays above **10** for more than a
couple minutes: that indicates the background task queue is backing up
and generations are being serialized behind slow ones.

### 5.2 Disk cleanup

Generated MP4s accumulate in `/tmp/lite-avatar-videos`. Add a cron to
prune files older than 7 days:

```cron
0 3 * * * find /tmp/lite-avatar-videos -name "*.mp4" -mtime +7 -delete
```

(Inside the container; or on the host if you've bind-mounted the cache.)

### 5.3 Logs

```bash
docker logs --tail 100 -f lite-avatar-worker
```

Look for these tags in order during a generation:
- `[generate] Job <id> queued`
- `[run_generation] Job <id> processing started`
- `[generate] Running LiteAvatar inference...`
- `[generate] Inference complete: ...`
- `[run_generation] Job <id> completed`

### 5.4 Common issues

**Model download keeps failing**
- Check free disk: model needs ~10 GB free during download
- Check outbound network: the entrypoint hits ModelScope endpoints
- Manually retry: `docker exec -it lite-avatar-worker bash
  /app/lite-avatar/download_model.sh`

**Generation timeout (>10 min)**
- LiteAvatar takes roughly 1–2× video duration on CPU. A 60s video
  can legitimately take 60–120s of wall time.
- Bump the subprocess `timeout=` in `worker.py::generate_avatar_video`
  if your videos exceed 5 minutes.
- If you're calling from a Celery task, raise its `soft_time_limit`
  as well so Celery doesn't kill the job before the worker finishes.

**"Avatar not found" (HTTP 404 from /generate)**
- Verify the folder exists inside the container:
  `docker exec lite-avatar-worker ls /app/avatars`
- Folder name must match the `avatar_id` sent by the provider AND
  be listed in `LiteAvatarProvider.AVAILABLE_AVATARS`.
- Remember: the `avatars/` mount is read-only — rebuild or restart
  after adding a new avatar folder on the host.

**Out-of-memory kills**
- One generation uses ~4–6 GB RAM.
- On a 16 GB box, max safe concurrency is 2–3 simultaneous jobs.
- Symptoms: container restarts, `dmesg` shows OOM killer, jobs flip
  from `processing` to `failed` at random.
- Fix: scale vertically (32 GB box = CCX33/CCX43) or horizontally
  (multiple worker containers behind nginx/haproxy).

**Health check 503 for longer than 3 minutes**
- The `start_period: 180s` grace window has elapsed but the worker
  still isn't responding — check the container logs for a stack trace
  during startup. Usually it's a missing Python dep from the upstream
  LiteAvatar repo that failed silently during build.
