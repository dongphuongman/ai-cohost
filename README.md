# AI Co-host

Trợ lý AI cho livestream bán hàng tại Việt Nam. Đọc comment, gợi ý trả lời trong dưới 3 giây, sinh kịch bản live chuyên nghiệp.

> **Tài liệu thiết kế đầy đủ:** [`docs/AI-Cohost-System-Design.md`](docs/AI-Cohost-System-Design.md)

## Architecture

```
Browser Extension ──WSS──► FastAPI (REST + WebSocket)
                                │
Dashboard (Next.js) ──HTTPS──►  ├──► Celery Workers
                                │        │
                                ▼        ▼
                           PostgreSQL  Redis
                           + pgvector  (broker/cache)
```

## Tech Stack

| Layer | Stack |
|---|---|
| Dashboard | Next.js 15, TypeScript, Tailwind, shadcn/ui, Zustand, TanStack Query |
| Extension | Chrome MV3, Vite + CRXJS, Preact, Tailwind |
| API | FastAPI, SQLAlchemy 2.0 async, Pydantic v2, WebSocket |
| Workers | Celery + Redis, 5 queues (llm, script, embed, media, usage) |
| Database | PostgreSQL 15 + pgvector, Alembic migrations |
| AI | Gemini Flash (primary), Claude Haiku (quality), DeepSeek V3 (fallback) |

## Setup

### Prerequisites

- Node.js 20+, pnpm 9+
- Python 3.11+, [uv](https://docs.astral.sh/uv/)
- Docker & Docker Compose

### First time setup

```bash
# 1. Clone and install
cd ai-cohost
pnpm install

# 2. Start infrastructure
docker compose -f infra/compose/docker-compose.dev.yml up -d

# 3. Setup backend
cd apps/api
cp ../../.env.example ../../.env
uv sync
uv run alembic upgrade head
uv run python seed.py

# 4. Setup workers
cd ../workers
uv sync
```

### Run locally

```bash
# Terminal 1: API server
cd apps/api
uv run uvicorn app.main:app --reload --port 8000

# Terminal 2: Dashboard
pnpm dev          # http://localhost:3000

# Terminal 3: Extension dev
pnpm dev:ext      # Load dist/ in chrome://extensions

# Terminal 4: Celery workers (requires Redis)
cd apps/workers
uv run celery -A celery_app worker -l info -Q llm_queue,script_queue,embed_queue,media_queue,usage_queue
```

## Commands

| Command | Description |
|---|---|
| `pnpm dev` | Start dashboard dev server |
| `pnpm dev:ext` | Start extension dev server |
| `pnpm build` | Build all frontend packages |
| `pnpm lint` | Lint all frontend packages |
| `pnpm type-check` | Type-check all frontend packages |
| `docker compose -f infra/compose/docker-compose.dev.yml up -d` | Start Postgres, Redis, Adminer, Mailhog |
| `uv run alembic upgrade head` | Run database migrations |
| `uv run python seed.py` | Seed demo data |

## Demo credentials

- Email: `demo@cohost.vn`
- Password: `demo1234`

## Infrastructure ports

| Service | Port |
|---|---|
| Dashboard | 3000 |
| API | 8000 |
| PostgreSQL | 5432 |
| Redis | 6379 |
| Adminer (DB UI) | 8080 |
| Mailhog (Email) | 8025 |
