# LiteAvatar Worker Service

Self-hosted digital human video generation using
[LiteAvatar](https://github.com/HumanAIGC/lite-avatar) (CPU-only).

This service sits behind the `LiteAvatarProvider` in `apps/workers/dh_providers`.
When `LITE_AVATAR_URL` is set in the API workers' env, the provider router
prefers this free, self-hosted path over HeyGen (~$0.40/min).

## Architecture

```
API workers → HTTP → LiteAvatar Worker → LiteAvatar inference → ffmpeg → artifact
```

## Hardware

- 8 vCPU with AVX2, 16 GB RAM, 20 GB disk
- No GPU required — LiteAvatar runs on CPU at ~30 FPS

## Quick start

### 1. Build image

```bash
cd services/lite-avatar-worker
docker build -t lite-avatar-worker:latest .
```

Model weights (~5–8 GB) are **not** downloaded during build — they are
fetched on first container start inside `entrypoint.sh`, so the image
stays small.

### 2. Place avatars

Download avatars from
[LiteAvatarGallery](https://modelscope.cn/models/HumanAIGC-Engineering/LiteAvatarGallery)
and drop them into `avatars/`:

```
avatars/
├── linh_female/
├── nam_male/
├── huong_female/
├── tuan_male/
└── mai_female/
```

Folder names must match `LiteAvatarProvider.AVAILABLE_AVATARS` in
`apps/workers/dh_providers/liteavatar.py`. Avatar binaries are **not**
committed to git — only the folder structure.

### 3. Run service

```bash
docker compose up -d
docker logs -f lite-avatar-worker   # wait for "Model download complete"
```

### 4. Verify

```bash
curl http://localhost:8080/health
curl http://localhost:8080/avatars
bash tests/test_smoke.sh
```

## API

| Method | Path                     | Purpose                          |
| ------ | ------------------------ | -------------------------------- |
| GET    | /health                  | Health + active job count        |
| GET    | /avatars                 | List pre-loaded avatars          |
| POST   | /generate                | Start a job, returns `job_id`    |
| GET    | /status/{job_id}         | Poll job status                  |
| GET    | /artifacts/{filename}    | Download finished MP4            |
| DELETE | /jobs/{job_id}           | Cleanup finished job from memory |

### POST /generate body

```json
{
  "text": "Xin chào!",
  "avatar_id": "linh_female",
  "voice_audio_url": null,
  "background": "white",
  "language": "vi"
}
```

If `voice_audio_url` is provided, the worker downloads and uses it as the
input audio. Otherwise it falls back to gTTS in the given language.

## Integration with API workers

```bash
# apps/api or apps/workers .env
LITE_AVATAR_URL=http://lite-avatar-worker:8080
```

When set and `/health` returns 200, the provider router prefers LiteAvatar.
Leave it empty to force-fallback to HeyGen (the default in dev).

## Cost comparison

| Provider    | Cost              | Quality   | Custom avatars |
| ----------- | ----------------- | --------- | -------------- |
| LiteAvatar  | $0/min (hosted)   | Good      | Gallery only   |
| HeyGen      | $0.40/min         | Excellent | Yes            |

See `DEPLOYMENT.md` for VPS deployment + canary rollout guidance.
