# AI Co-host — Setup Guide

Hướng dẫn cài đặt và chạy hệ thống AI Co-host từ đầu trên máy local.

---

## Mục lục

1. [Yêu cầu hệ thống](#1-yêu-cầu-hệ-thống)
2. [Cài đặt công cụ](#2-cài-đặt-công-cụ)
3. [Clone & cài dependencies](#3-clone--cài-dependencies)
4. [Khởi động Infrastructure](#4-khởi-động-infrastructure-docker)
5. [Cấu hình Environment](#5-cấu-hình-environment)
6. [Khởi tạo Database](#6-khởi-tạo-database)
7. [Chạy Backend API](#7-chạy-backend-api)
8. [Chạy Celery Workers](#8-chạy-celery-workers)
9. [Chạy Dashboard (Frontend)](#9-chạy-dashboard-frontend)
10. [Build Chrome Extension](#10-build-chrome-extension)
11. [Seed dữ liệu mẫu](#11-seed-dữ-liệu-mẫu)
12. [(Tùy chọn) Chạy Lite-Avatar Worker (self-hosted Digital Human)](#12-tùy-chọn-chạy-lite-avatar-worker-self-hosted-digital-human)
13. [Kiểm tra hệ thống](#13-kiểm-tra-hệ-thống)
14. [Bảng tổng hợp ports & URLs](#14-bảng-tổng-hợp-ports--urls)
15. [Xử lý lỗi thường gặp](#15-xử-lý-lỗi-thường-gặp)

---

## 1. Yêu cầu hệ thống

| Yêu cầu       | Phiên bản tối thiểu |
|----------------|---------------------|
| Node.js        | >= 20.0.0           |
| pnpm           | >= 9.15.4           |
| Python         | >= 3.11             |
| uv             | >= 0.4.0            |
| Docker         | >= 24.0             |
| Docker Compose | >= 2.20             |
| Git            | >= 2.30             |

**Hệ điều hành:** macOS, Linux, hoặc WSL2 trên Windows.

---

## 2. Cài đặt công cụ

### Node.js & pnpm

```bash
# Cài Node.js (khuyến nghị dùng nvm)
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.7/install.sh | bash
nvm install 20
nvm use 20

# Cài pnpm
corepack enable
corepack prepare pnpm@9.15.4 --activate

# Kiểm tra
node -v    # >= v20.x
pnpm -v    # >= 9.15.4
```

### Python & uv

```bash
# Cài uv (Python package manager)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Kiểm tra
uv --version   # >= 0.4.x
python3 --version  # >= 3.11
```

### Docker

```bash
# macOS: Cài Docker Desktop từ https://docker.com/products/docker-desktop
# Linux:
curl -fsSL https://get.docker.com | sh

# Kiểm tra
docker --version
docker compose version
```

---

## 3. Clone & cài dependencies

```bash
# Clone repo
git clone <repo-url> ai-cohost
cd ai-cohost

# Cài Node.js dependencies (Dashboard + Extension + shared packages)
pnpm install

# Cài Python dependencies cho API
cd apps/api
uv sync
cd ../..

# Cài Python dependencies cho Workers
cd apps/workers
uv sync
cd ../..
```

**Cấu trúc thư mục:**

```
ai-cohost/
├── apps/
│   ├── api/            # FastAPI backend (Python)
│   ├── workers/        # Celery task workers (Python)
│   ├── dashboard/      # Next.js 16 frontend
│   └── extension/      # Chrome extension (Preact + Vite)
├── packages/           # Shared packages
├── services/
│   └── lite-avatar-worker/  # Self-hosted Digital Human worker (opt-in)
├── infra/
│   ├── compose/        # Docker Compose files
│   └── docker/         # Docker init scripts
├── docs/               # Documentation
├── .env.example        # Environment template
└── pnpm-workspace.yaml
```

---

## 4. Khởi động Infrastructure (Docker)

Hệ thống cần PostgreSQL (với pgvector), Redis, và các service phụ trợ.

```bash
# Khởi động tất cả services
docker compose -f infra/compose/docker-compose.dev.yml up -d

# Kiểm tra services đã healthy
docker compose -f infra/compose/docker-compose.dev.yml ps
```

**Services sẽ chạy:**

| Service    | Mô tả                          | Port  |
|------------|--------------------------------|-------|
| PostgreSQL | Database chính (pgvector/pg15) | 5434  |
| Redis      | Cache + Message broker         | 6379  |
| Adminer    | Database UI (web)              | 8080  |
| MailHog    | Email testing (SMTP + UI)      | 1025, 8025 |

**Kiểm tra kết nối:**

```bash
# PostgreSQL
docker exec -it $(docker ps -qf "ancestor=pgvector/pgvector:pg15") \
  psql -U postgres -d cohost_dev -c "SELECT 1;"

# Redis
docker exec -it $(docker ps -qf "ancestor=redis:7-alpine") \
  redis-cli ping
# => PONG
```

**PostgreSQL extensions** được tự động cài khi khởi tạo:
- `uuid-ossp` — UUID generation
- `pgcrypto` — Cryptography
- `vector` — pgvector (embeddings)
- `pg_trgm` — Trigram text search

---

## 5. Cấu hình Environment

```bash
# Copy template
cp .env.example .env
```

Mở file `.env` và cấu hình các biến sau:

### Bắt buộc cho development

```env
# Database (giữ nguyên nếu dùng Docker mặc định)
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5434/cohost_dev
REDIS_URL=redis://localhost:6379/0

# Auth (giữ nguyên cho dev, ĐỔI cho production!)
JWT_SECRET=change-me-in-production
JWT_ALGORITHM=HS256
JWT_ACCESS_EXPIRE_MINUTES=60
JWT_REFRESH_EXPIRE_DAYS=30

# LLM — BẮT BUỘC ít nhất 1 provider
GEMINI_API_KEY=<lấy từ https://aistudio.google.com/apikey>

# Embeddings
EMBEDDING_MODEL=gemini-text-embedding-004
EMBEDDING_DIMENSION=768

# App
APP_ENV=development
FRONTEND_URL=http://localhost:3000
API_URL=http://localhost:8000
```

### Tuỳ chọn (bật thêm tính năng)

```env
# Thêm LLM providers
ANTHROPIC_API_KEY=<optional>
DEEPSEEK_API_KEY=<optional>

# Supabase (optional cho local, BẮT BUỘC cho production)
SUPABASE_URL=<optional>
SUPABASE_ANON_KEY=<optional>
SUPABASE_SERVICE_KEY=<optional>

# Text-to-Speech
GOOGLE_CLOUD_TTS_KEY=<optional>
ELEVENLABS_API_KEY=<optional, dùng cho voice clone>

# Digital Human (chọn 1 trong 2)
HEYGEN_API_KEY=<optional, cloud provider>
# Hoặc dùng self-hosted Lite-Avatar worker — xem mục 12

# Object Storage (cần cho upload ảnh/video)
R2_ACCOUNT_ID=<Cloudflare R2>
R2_ACCESS_KEY_ID=
R2_SECRET_ACCESS_KEY=
R2_BUCKET=cohost-dev
R2_PUBLIC_URL=

# Billing
LEMONSQUEEZY_API_KEY=<optional>
LEMONSQUEEZY_WEBHOOK_SECRET=<optional>

# Email
RESEND_API_KEY=<optional, dùng MailHog cho dev>

# Monitoring
SENTRY_DSN=<optional>
```

### Extension environment

```bash
# Tạo file .env cho extension
cat > apps/extension/.env << 'EOF'
VITE_API_URL=http://localhost:8000/api/v1
VITE_WS_URL=ws://localhost:8000/ws
VITE_DASHBOARD_URL=http://localhost:3000
EOF
```

---

## 6. Khởi tạo Database

```bash
cd apps/api

# Chạy Alembic migrations
uv run alembic upgrade head

cd ../..
```

**Kiểm tra migration thành công:**

```bash
# Vào Adminer tại http://localhost:8080
# Server: postgres:5432
# Username: postgres
# Password: postgres
# Database: cohost_dev
```

Hoặc dùng command line:

```bash
docker exec -it $(docker ps -qf "ancestor=pgvector/pgvector:pg15") \
  psql -U postgres -d cohost_dev -c "\dt"
```

---

## 7. Chạy Backend API

```bash
cd apps/api

# Chạy FastAPI dev server
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

**Kiểm tra:**
- Health check: http://localhost:8000/health
- API Docs (Swagger): http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

Khi thấy output:

```
INFO:     Uvicorn running on http://0.0.0.0:8000
INFO:     Started reloader process
```

API đã sẵn sàng. **Giữ terminal này mở.**

---

## 8. Chạy Celery Workers

Mở **terminal mới**:

```bash
cd apps/workers

# Chạy Celery worker
uv run celery -A celery_app worker --loglevel=info --pool=solo
```

**Task queues:**

| Queue          | Xử lý                  |
|----------------|------------------------|
| `llm_queue`    | LLM inference          |
| `script_queue` | Sinh kịch bản          |
| `embed_queue`  | Tạo embeddings         |
| `media_queue`  | Xử lý media            |
| `usage_queue`  | Tracking sử dụng       |

Khi thấy output:

```
[config]
- ** ---------- celery@<hostname> v5.4.x
- ** ---------- [queues]
  ...
[tasks]
  . tasks.embed.*
  . tasks.llm.*
  . tasks.script.*
```

Workers đã sẵn sàng. **Giữ terminal này mở.**

---

## 9. Chạy Dashboard (Frontend)

Mở **terminal mới**:

```bash
# Từ thư mục gốc
pnpm dev
```

Hoặc chạy trực tiếp:

```bash
cd apps/dashboard
pnpm dev
```

Dashboard sẽ chạy tại: **http://localhost:3000**

---

## 10. Build Chrome Extension

Mở **terminal mới**:

```bash
# Dev mode (hot reload)
pnpm dev:ext
```

Hoặc:

```bash
cd apps/extension
pnpm dev
```

**Load extension vào Chrome:**

1. Mở Chrome, vào `chrome://extensions/`
2. Bật **Developer mode** (góc trên phải)
3. Click **Load unpacked**
4. Chọn thư mục `apps/extension/dist`
5. Extension "AI Co-host — Trợ lý Livestream" sẽ xuất hiện

**Lưu ý:** Mỗi khi build lại, cần click reload icon trên extension tại `chrome://extensions/`.

---

## 11. Seed dữ liệu mẫu

```bash
cd apps/api

# Tạo user demo + shop + dữ liệu mẫu
uv run python seed.py

cd ../..
```

**Tài khoản demo** (kiểm tra file `seed.py` để biết credentials chính xác):
- Truy cập http://localhost:3000/login
- Đăng nhập bằng email/password từ seed data

---

## 12. (Tùy chọn) Chạy Lite-Avatar Worker (self-hosted Digital Human)

Nếu không dùng HeyGen cloud, bạn có thể tự host service sinh video Digital Human bằng Lite-Avatar.

> **Cảnh báo:** Service này cần tải ~5–8 GB model weights lần đầu và yêu cầu tối thiểu 8 GB RAM / 4 CPU. Vì vậy nó được gắn **profile `lite-avatar`** và KHÔNG tự chạy khi `docker compose up` mặc định.

```bash
# Chạy self-hosted worker (opt-in profile)
docker compose -f infra/compose/docker-compose.dev.yml \
  --profile lite-avatar up -d lite-avatar-worker

# Theo dõi quá trình tải models (lần đầu có thể mất 10–20 phút)
docker logs -f cohost-lite-avatar

# Kiểm tra health
curl http://localhost:8088/health
```

**Cấu hình:**

| Biến môi trường       | Mặc định                      | Mô tả                              |
|------------------------|-------------------------------|------------------------------------|
| `LOG_LEVEL`            | `INFO`                        | Log verbosity                       |
| `VIDEO_CACHE_DIR`      | `/tmp/lite-avatar-videos`     | Thư mục cache video đầu ra         |
| `SKIP_MODEL_DOWNLOAD`  | `false`                       | Bỏ qua download weights cho dev/CI |

**Dev escape hatch:** Đặt `SKIP_MODEL_DOWNLOAD=true` khi cần khởi động container nhanh (không sinh video thật) cho unit test hoặc CI.

**Cấu hình API sử dụng Lite-Avatar thay vì HeyGen:** Xem `services/lite-avatar-worker/DEPLOYMENT.md` và `docs/AI-Cohost-System-Design.md` mục Digital Human.

---

## 13. Kiểm tra hệ thống

### Checklist

| #  | Kiểm tra                          | Cách kiểm tra                                      | Kỳ vọng          |
|----|-----------------------------------|-----------------------------------------------------|-------------------|
| 1  | Docker services                   | `docker compose ... ps`                             | Tất cả healthy    |
| 2  | PostgreSQL + pgvector             | `SELECT * FROM pg_extension;`                       | vector có mặt     |
| 3  | Redis                             | `redis-cli ping`                                    | PONG              |
| 4  | API health                        | `curl http://localhost:8000/health`                 | `{"status":"ok"}` |
| 5  | API docs                          | Mở http://localhost:8000/docs                       | Swagger UI        |
| 6  | Dashboard                         | Mở http://localhost:3000                            | Landing page      |
| 7  | Login                             | Đăng nhập tại /login                                | Redirect /dashboard |
| 8  | Celery worker                     | Tạo sản phẩm, kiểm tra embedding                   | Status: ready     |
| 9  | Extension                         | Icon hiện trên Chrome toolbar                       | Popup hiển thị    |
| 10 | WebSocket                         | Bắt đầu phiên live qua extension                    | Overlay hiện      |

### Chạy tests

```bash
# Tất cả tests
pnpm test

# Chỉ Python tests
pnpm test:py

# Chỉ Dashboard tests
cd apps/dashboard && pnpm test

# E2E tests (cần Playwright)
cd apps/dashboard && npx playwright install && pnpm e2e

# Type check
pnpm type-check
```

---

## 14. Bảng tổng hợp Ports & URLs

| Service                          | URL                                | Port |
|-----------------------------------|------------------------------------|------|
| Dashboard                         | http://localhost:3000               | 3000 |
| API                               | http://localhost:8000               | 8000 |
| API Docs (Swagger)                | http://localhost:8000/docs          | 8000 |
| WebSocket                         | ws://localhost:8000/ws              | 8000 |
| PostgreSQL                        | localhost:5434                      | 5434 |
| Redis                             | localhost:6379                      | 6379 |
| Adminer (DB UI)                   | http://localhost:8080               | 8080 |
| MailHog (Email UI)                | http://localhost:8025               | 8025 |
| MailHog (SMTP)                    | localhost:1025                      | 1025 |
| Lite-Avatar Worker (opt-in)       | http://localhost:8088               | 8088 |

---

## 15. Xử lý lỗi thường gặp

### Port 5434 đã bị chiếm

```bash
# Kiểm tra process đang dùng port
lsof -i :5434
# Kill nếu cần
kill -9 <PID>
```

### pgvector extension không tồn tại

```bash
# Chạy thủ công trong PostgreSQL
docker exec -it $(docker ps -qf "ancestor=pgvector/pgvector:pg15") \
  psql -U postgres -d cohost_dev -c "CREATE EXTENSION IF NOT EXISTS vector;"
```

### Alembic migration lỗi "relation already exists"

```bash
cd apps/api
# Đánh dấu migration hiện tại là đã chạy
uv run alembic stamp head
```

### Module not found khi chạy API/Workers

```bash
# Đảm bảo đã sync dependencies
cd apps/api && uv sync
cd ../workers && uv sync
```

### Extension không load được

1. Kiểm tra đã build: `ls apps/extension/dist/`
2. Nếu trống: `cd apps/extension && pnpm build`
3. Reload extension tại `chrome://extensions/`

### CORS error từ Dashboard đến API

Kiểm tra `FRONTEND_URL` trong `.env` khớp với URL dashboard (mặc định `http://localhost:3000`).

### Redis connection refused

```bash
# Kiểm tra Redis đang chạy
docker compose -f infra/compose/docker-compose.dev.yml ps redis
# Restart nếu cần
docker compose -f infra/compose/docker-compose.dev.yml restart redis
```

### Lỗi escape sequence khi tạo file Python từ AI

Python triple-quoted strings có thể corrupt `!!` thành `\!\!`. Dùng string concatenation thay vì triple-quote cho nội dung chứa `!!`.

---

## Quick Start (TL;DR)

```bash
# 1. Cài tools
corepack enable && corepack prepare pnpm@9.15.4 --activate
curl -LsSf https://astral.sh/uv/install.sh | sh

# 2. Dependencies
pnpm install
cd apps/api && uv sync && cd ../..
cd apps/workers && uv sync && cd ../..

# 3. Infrastructure
docker compose -f infra/compose/docker-compose.dev.yml up -d

# 4. Environment
cp .env.example .env
# => Mở .env, thêm GEMINI_API_KEY

# 5. Database
cd apps/api && uv run alembic upgrade head && cd ../..

# 6. Chạy (mỗi lệnh trong 1 terminal riêng)
cd apps/api && uv run uvicorn app.main:app --reload --port 8000
cd apps/workers && uv run celery -A celery_app worker --loglevel=info --pool=solo
pnpm dev          # Dashboard
pnpm dev:ext      # Extension

# 7. Mở http://localhost:3000
```
