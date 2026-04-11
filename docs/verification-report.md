# AI CO-HOST MVP — VERIFICATION REPORT

**Date:** 2026-04-10
**Auditor:** QA Lead / Technical Architect
**Codebase version:** `c8d09a9` (main branch)

---

## BƯỚC 1: Inventory

### 1A. Backend Endpoints

| # | Method | Path | Router File | Auth? | Shop Scope? | Has Test? |
|---|--------|------|-------------|-------|-------------|-----------|
| 1 | POST | `/api/v1/auth/signup` | routers/auth.py | No | No | No (schema only) |
| 2 | POST | `/api/v1/auth/verify-email` | routers/auth.py | No | No | No (schema only) |
| 3 | POST | `/api/v1/auth/resend-otp` | routers/auth.py | No | No | No |
| 4 | POST | `/api/v1/auth/login` | routers/auth.py | No | No | No |
| 5 | POST | `/api/v1/auth/refresh` | routers/auth.py | No | No | No |
| 6 | POST | `/api/v1/auth/forgot-password` | routers/auth.py | No | No | No |
| 7 | POST | `/api/v1/auth/reset-password` | routers/auth.py | No | No | No |
| 8 | POST | `/api/v1/auth/google` | routers/auth.py | No | No | No |
| 9 | POST | `/api/v1/auth/logout` | routers/auth.py | Yes | No | No |
| 10 | GET | `/api/v1/auth/me` | routers/auth.py | Yes | No | No |
| 11 | PATCH | `/api/v1/auth/me` | routers/auth.py | Yes | No | No |
| 12 | POST | `/api/v1/auth/change-password` | routers/auth.py | Yes | No | No |
| 13 | GET | `/api/v1/shops/` | routers/shops.py | Yes | No | No |
| 14 | POST | `/api/v1/shops/` | routers/shops.py | Yes | No | No |
| 15 | GET | `/api/v1/shops/current` | routers/shops.py | Yes | Yes | No |
| 16 | PATCH | `/api/v1/shops/current` | routers/shops.py | Yes | Yes (owner/admin) | No |
| 17 | GET | `/api/v1/shops/current/members` | routers/shops.py | Yes | Yes | No |
| 18 | POST | `/api/v1/shops/current/members` | routers/shops.py | Yes | Yes (owner/admin) | No |
| 19 | PATCH | `/api/v1/shops/current/members/{mid}` | routers/shops.py | Yes | Yes (owner) | No |
| 20 | DELETE | `/api/v1/shops/current/members/{mid}` | routers/shops.py | Yes | Yes (owner/admin) | No |
| 21 | GET | `/api/v1/products/` | routers/products.py | Yes | Yes | No |
| 22 | POST | `/api/v1/products/` | routers/products.py | Yes | Yes | No |
| 23 | POST | `/api/v1/products/extract-url` | routers/products.py | Yes | Yes | No |
| 24 | GET | `/api/v1/products/{id}` | routers/products.py | Yes | Yes | No |
| 25 | PATCH | `/api/v1/products/{id}` | routers/products.py | Yes | Yes | No |
| 26 | DELETE | `/api/v1/products/{id}` | routers/products.py | Yes | Yes | No |
| 27 | POST | `/api/v1/products/{id}/reindex` | routers/products.py | Yes | Yes | No |
| 28 | POST | `/api/v1/products/{id}/ai/highlights` | routers/products.py | Yes | Yes | No |
| 29 | POST | `/api/v1/products/{id}/ai/faqs` | routers/products.py | Yes | Yes | No |
| 30 | GET | `/api/v1/products/{id}/faqs/` | routers/faqs.py | Yes | Yes | No |
| 31 | POST | `/api/v1/products/{id}/faqs/` | routers/faqs.py | Yes | Yes | No |
| 32 | POST | `/api/v1/products/{id}/faqs/bulk` | routers/faqs.py | Yes | Yes | No |
| 33 | PATCH | `/api/v1/products/{id}/faqs/{faq_id}` | routers/faqs.py | Yes | Yes | No |
| 34 | DELETE | `/api/v1/products/{id}/faqs/{faq_id}` | routers/faqs.py | Yes | Yes | No |
| 35 | GET | `/api/v1/personas/` | routers/personas.py | Yes | Yes | No |
| 36 | POST | `/api/v1/personas/` | routers/personas.py | Yes | Yes | No |
| 37 | GET | `/api/v1/personas/{id}` | routers/personas.py | Yes | Yes | No |
| 38 | PATCH | `/api/v1/personas/{id}` | routers/personas.py | Yes | Yes | No |
| 39 | DELETE | `/api/v1/personas/{id}` | routers/personas.py | Yes | Yes | No |
| 40 | PATCH | `/api/v1/personas/{id}/default` | routers/personas.py | Yes | Yes | No |
| 41 | GET | `/api/v1/sessions/` | routers/sessions.py | Yes | Yes | No |
| 42 | GET | `/api/v1/sessions/{uuid}` | routers/sessions.py | Yes | Yes | No |
| 43 | GET | `/api/v1/sessions/{uuid}/comments` | routers/sessions.py | Yes | Yes | No |
| 44 | GET | `/api/v1/sessions/{uuid}/suggestions` | routers/sessions.py | Yes | Yes | No |
| 45 | GET | `/api/v1/scripts/` | routers/scripts.py | **No** | **No** | No |
| 46 | POST | `/api/v1/scripts/generate` | routers/scripts.py | **No** | **No** | No |
| 47 | GET | `/api/v1/scripts/{id}` | routers/scripts.py | **No** | **No** | No |
| 48 | PATCH | `/api/v1/scripts/{id}` | routers/scripts.py | **No** | **No** | No |
| 49 | DELETE | `/api/v1/scripts/{id}` | routers/scripts.py | **No** | **No** | No |
| 50 | GET | `/api/v1/billing/subscription` | routers/billing.py | Yes | Yes | No |
| 51 | GET | `/api/v1/billing/invoices` | routers/billing.py | Yes | Yes | No |
| 52 | GET | `/api/v1/billing/usage` | routers/billing.py | Yes | Yes | No |
| 53 | GET | `/api/v1/billing/plans` | routers/billing.py | No | No | No |
| 54 | POST | `/api/v1/billing/cancel` | routers/billing.py | Yes | Yes (owner) | No |
| 55 | POST | `/api/v1/billing/checkout` | routers/billing.py | Yes | Yes (owner) | No |
| 56 | POST | `/api/v1/billing/portal` | routers/billing.py | Yes | Yes (owner) | No |
| 57 | POST | `/api/v1/tts/generate` | routers/tts.py | Yes | Yes | No |
| 58 | GET | `/api/v1/analytics/overview` | routers/analytics.py | Yes | Yes | No |
| 59 | GET | `/api/v1/analytics/sessions` | routers/analytics.py | Yes | Yes | No |
| 60 | GET | `/api/v1/analytics/sessions/{id}` | routers/analytics.py | Yes | Yes | No |
| 61 | GET | `/api/v1/analytics/sessions/{id}/chart` | routers/analytics.py | Yes | Yes | No |
| 62 | GET | `/api/v1/analytics/sessions/{id}/products` | routers/analytics.py | Yes | Yes | No |
| 63 | GET | `/api/v1/analytics/sessions/{id}/questions` | routers/analytics.py | Yes | Yes | No |
| 64 | GET | `/api/v1/analytics/sessions/{id}/comments` | routers/analytics.py | Yes | Yes | No |
| 65 | GET | `/api/v1/analytics/sessions/{id}/export` | routers/analytics.py | Yes | Yes | No |
| 66 | GET | `/api/v1/analytics/usage` | routers/analytics.py | Yes | Yes | No |
| 67 | POST | `/api/v1/webhooks/lemonsqueezy` | routers/webhooks.py | HMAC | No | No |
| 68 | WS | `/ws?token=<jwt>` | ws/handler.py | JWT | Yes | No |
| 69 | GET | `/health` | main.py | No | No | No |

**Total: 69 endpoints (67 REST + 1 WS + 1 health)**

**Critical finding:** Scripts router (#45-49) has NO auth, NO validation, NO DB access — all 5 endpoints are stubs returning hardcoded data.

---

### 1B. Database Tables

Schema source: `apps/api/alembic/versions/0001_initial_schema.py` + ORM models in `apps/api/app/models/`

| Table | In Migration? | Has ORM Model? | Has RLS? | Actual Cols | Spec Cols | Delta |
|-------|:---:|:---:|:---:|:---:|:---:|---|
| shops | Yes | Yes | No (intentional) | 14 | 14 | Match |
| users | Yes | Yes | No (intentional) | 14 | 14 | Match |
| shop_members | Yes | Yes | No (intentional) | 8 | 8 | Match |
| products | Yes | Yes | **Yes** | 16 | 16 | Match |
| product_faqs | Yes | Yes | **Yes** | 12 | 12 | Match |
| personas | Yes | Yes | No (intentional) | 13 | 13 | Match |
| live_sessions | Yes | Yes | **Yes** | 20 | 20 | Match |
| comments | Yes | Yes | **Yes** | 14 | 14 | Match |
| suggestions | Yes | Yes | **Yes** | 18 | 18 | Match |
| scripts | Yes | Yes | **Yes** | 20 | 20 | Match |
| script_samples | Yes | Yes | No (global data) | 10 | 10 | Match |
| dh_videos | Yes | Yes | **Yes** | 18 | 18 | Match |
| voice_clones | Yes | Yes | **Yes** | 15 | 15 | Match |
| subscriptions | Yes | Yes | No (intentional) | 16 | 16 | Match |
| invoices | Yes | Yes | No (intentional) | 12 | 12 | Match |
| usage_logs | Yes | Yes | No (intentional) | 10 | 10 | Match |

**Total: 16 tables, all match spec. 8 tables have RLS policies.**

pgvector HNSW indexes exist on: `products.embedding`, `product_faqs.embedding`, `script_samples.embedding` — all with `m=16, ef_construction=64`.

Trigram GIN index on `products.name` for Vietnamese fuzzy search — present.

---

### 1C. Frontend Pages

| Route | File | Real UI? | API Calls? | Empty State? | Error Handling? | Vietnamese? |
|-------|------|:---:|:---:|:---:|:---:|:---:|
| `/` | app/page.tsx | Yes (static) | No | N/A | N/A | Yes |
| `/login` | app/(auth)/login/page.tsx | Yes | Yes | N/A | Yes | Yes |
| `/signup` | app/(auth)/signup/page.tsx | Yes | Yes | N/A | Yes | Yes |
| `/verify` | app/(auth)/verify/page.tsx | Yes (polished) | Yes | N/A | Yes | Yes |
| `/forgot-password` | app/(auth)/forgot-password/page.tsx | Yes | Yes | N/A | **BUG: errors swallowed** | Yes |
| `/onboarding` | app/(auth)/onboarding/page.tsx | Partial | Partial | N/A | **Step 1 error swallowed** | Yes |
| `/dashboard` | app/(dashboard)/dashboard/page.tsx | **PLACEHOLDER** | **No** | **No** | **No** | Partial |
| `/products` | app/(dashboard)/products/page.tsx | Yes (full) | Yes | Yes | Yes | **Partial** (accented issues) |
| `/products/[id]` | app/(dashboard)/products/[id]/page.tsx | Yes (full) | Yes | Yes (not-found) | Yes | Yes |
| `/scripts` | app/(dashboard)/scripts/page.tsx | **PLACEHOLDER** | **No** | Static only | **No** | Yes |
| `/sessions` | app/(dashboard)/sessions/page.tsx | **PLACEHOLDER** | **No** | Static only | **No** | Yes |
| `/settings` | app/(dashboard)/settings/page.tsx | Yes | Yes | N/A | Yes | Yes |
| `/settings/billing` | app/(dashboard)/settings/billing/page.tsx | Yes | Yes | N/A | Partial (alert only) | Yes |
| `/settings/team` | app/(dashboard)/settings/team/page.tsx | Yes | Yes | N/A | Yes | Yes |

**Missing pages per spec:**
- `/reset-password` — store action exists, route declared in middleware, **NO page file**
- `/sessions/[id]` — session detail page — **NOT created**
- `/scripts/new` or `/scripts/[id]` — script generator/editor — **NOT created**

---

### 1D. Extension Components

| Component | File | Implemented? | Notes |
|-----------|------|:---:|---|
| Manifest V3 | manifest.json | Yes | Valid MV3, bundler-dependent .ts paths |
| Background service worker | src/background/index.ts | **Yes (full)** | 8 message handlers, WS relay |
| Facebook adapter | src/adapters/facebook.ts | **Yes (full)** | Fragile CSS class selectors |
| YouTube adapter | src/adapters/youtube.ts | **Yes (full)** | Stable custom element selectors |
| TikTok adapter | src/adapters/tiktok.ts | **Yes (full)** | data-e2e selectors, reasonable |
| Shopee adapter | src/adapters/shopee.ts | **Yes (full)** | Most fragile (generic class names) |
| Smart Paste | src/content/smart-paste.ts | **Yes (full)** | 3 methods, NO Enter key, tooltip |
| Comment Reader | src/content/comment-reader.ts | **Yes** | Thin wrapper over adapter |
| Content Script | src/content/index.ts | **Yes (full)** | Platform detect, session lifecycle |
| Overlay main | src/content/overlay/Overlay.tsx | **Yes (full)** | Drag, collapse, keyboard shortcuts, streaming |
| SuggestionCard | src/content/overlay/SuggestionCard.tsx | **Yes (full)** | 4 buttons, edit mode, FAQ checkbox |
| HistoryList | src/content/overlay/HistoryList.tsx | **Yes** | Status badges, scrollable |
| Overlay mount | src/content/overlay/mount.ts | **Yes** | Shadow DOM injection |
| Popup | src/popup/popup.tsx | **Yes** | 3 states, but hardcoded shopId/personaId |
| WS client | src/lib/ws-client.ts | **Yes (full)** | Exponential backoff, ping/pong, max 10 retries |
| Auth lib | src/lib/auth.ts | **Partial** | refreshAuthToken() exists but NEVER called |
| Storage lib | src/lib/storage.ts | **Yes** | chrome.storage wrappers |
| Constants | src/lib/constants.ts | **Yes** | **Hardcoded localhost URLs** |

---

### 1E. Celery Tasks

| Task | Queue | File | Implemented? | Retry? | Timeout? |
|------|-------|------|:---:|:---:|:---:|
| `tasks.llm.generate_suggestion` | llm_queue | tasks/llm.py | **Yes (full 17-step pipeline)** | max 2 | 30s soft |
| `tasks.llm.classify_intent` | llm_queue | tasks/llm.py | **Yes** | No | No |
| `tasks.embed.embed_product` | embed_queue | tasks/embed.py | **Yes** | max 3, 10s delay | No |
| `tasks.embed.embed_faq` | embed_queue | tasks/embed.py | **Yes** | max 3, 10s delay | No |
| `tasks.script.generate_script` | script_queue | tasks/script.py | **STUB** | No | No |
| `tasks.media.generate_tts` | media_queue | tasks/media.py | **STUB** | No | No |
| `tasks.media.generate_dh_video` | media_queue | tasks/media.py | **STUB** | No | No |
| `tasks.media.clone_voice` | media_queue | tasks/media.py | **STUB** | No | No |
| `tasks.usage.log_usage` | usage_queue | tasks/usage.py | **STUB** | No | No |

**Missing tasks per spec:**
- `reindex_all_products` — mentioned in spec, not implemented

---

### 1F. Tests

**Backend (`apps/api`):**
```
47 passed, 2 skipped in 0.38s
```

| Test File | Tests | Coverage |
|-----------|:-----:|----------|
| test_auth_utils.py | 6 (2 skipped) | Password hash/verify, JWT roundtrips |
| test_otp.py | 3 | OTP length, digits, uniqueness |
| test_schemas.py | 7 | Pydantic validation for auth schemas |
| test_slugify.py | 5 | Vietnamese slug generation |
| test_usage.py | 4 | QuotaStatus calculations |
| test_analytics.py | 28 | Used rate, live hours, schema validation, CSV format |

**Frontend (`apps/dashboard`):** **0 tests. No test files exist.**

**Extension (`apps/extension`):** **0 tests. No test files exist.**

---

## BƯỚC 2: Feature-by-Feature Checklist

### F1 — Shop Onboarding & Product Catalog

**Backend:**
- [x] CRUD products endpoints (GET list, POST, GET detail, PATCH, DELETE) — `routers/products.py`
- [x] CRUD product FAQs endpoints — `routers/faqs.py`
- [x] POST /products/:id/reindex endpoint — `routers/products.py`
- [x] POST /products/extract-url endpoint (Shopee/TikTok URL extraction) — `services/url_extract.py`
- [x] POST /products/:id/ai/highlights endpoint — `services/ai_generate.py` (Gemini Flash)
- [x] POST /products/:id/ai/faqs endpoint — `services/ai_generate.py` (Gemini Flash)
- [x] CRUD personas endpoints — `routers/personas.py`
- [x] Embedding Celery task (embed_product) — `workers/tasks/embed.py`
- [x] Embedding Celery task (embed_faq) — `workers/tasks/embed.py`
- [x] Re-embed when name/description/highlights change — `services/products.py` checks field changes, re-enqueues
- [x] Product search (ILIKE on name) — `routers/products.py` search param
- [x] Quota check before create — `services/usage.py` check_quota()
- [x] pgvector HNSW index on products.embedding and product_faqs.embedding — in migration
- [x] Gemini text-embedding-004 with correct task_type — `workers/tasks/embed.py` uses RETRIEVAL_DOCUMENT; `workers/tasks/llm.py` uses RETRIEVAL_QUERY

**Frontend:**
- [x] Products List page (C2) — table with sort, filter, search, pagination
- [x] Product status badge — shows "Sẵn sàng" / "Đang index" / "Lỗi" (but see Vietnamese diacritics issue below)
- [x] Product Detail page (C3) — form edit, highlights list, FAQ accordion
- [x] Nút "AI gợi ý highlights" → modal chọn — implemented
- [x] Nút "AI tạo FAQ" → modal chọn — implemented
- [ ] **Onboarding B5: paste URL auto-extract** — UI input exists but **API call NOT wired** (advances to next step without saving)
- [x] Empty state for Products List
- [ ] **WebSocket listen event "product.indexed"** — NOT implemented in dashboard (no WS client in dashboard app)
- [x] Confirm dialog when deleting product (uses browser `confirm()`)
- [x] Unsaved changes warning via `beforeunload`

**Vietnamese diacritics issue:** `products/page.tsx` shows status badges as "San sang", "Dang index", "Loi" (unaccented) instead of proper "Sẵn sàng", "Đang index", "Lỗi".

**Tests:**
- [ ] Unit: Product CRUD — **No tests**
- [ ] Unit: AI highlight generation — **No tests**
- [ ] Unit: AI FAQ generation — **No tests**
- [ ] Integration: create product → embedding → search — **No tests**
- [ ] Integration: shop A cannot see shop B products — **No tests**

**F1 Score: 14/18 backend items, 7/10 frontend items = 21/28 (75%)**

---

### F2 — AI Comment Responder

**Backend:**
- [x] WebSocket handler: comment.new → save DB → enqueue LLM task — `ws/handler.py`
- [x] Intent classifier (keyword-based, no LLM) — `services/intent.py` + inline in `tasks/llm.py`
- [x] Only generate for: question, pricing, shipping, complaint — SKIP_INTENTS in `tasks/llm.py`
- [x] NOT generate for: greeting, thanks, praise, spam — confirmed in SKIP_INTENTS
- [x] RAG retrieval: embed comment → pgvector → top 2 products + top 3 FAQs — `tasks/llm.py` + `services/rag.py`
- [x] LLM streaming (Gemini Flash primary) — `tasks/llm.py` uses gemini-2.0-flash
- [ ] **LLM fallback (DeepSeek V3 when Gemini fails)** — NOT implemented. `deepseek_api_key` declared in config but **never used** in any task. No try/except around Gemini call with fallback.
- [x] Redis pub/sub: stream chunks from Celery → WS → extension — confirmed in tasks/llm.py and ws/handler.py
- [x] Response cache: same comment text in 5 min → cached response — Redis cache in ws/handler.py + tasks/llm.py
- [x] Conversation history: last 5 Q&A in Redis per session — confirmed in tasks/llm.py
- [x] Suggestion status update endpoint — ws/handler.py `suggestion.action` message
- [ ] **"Lưu làm FAQ"** — Extension has checkbox + handler that calls SAVE_AS_FAQ → background POST /faqs. **But backend expects shop_id via X-Shop-Id header which background/index.ts does NOT send.** Likely fails with 422.
- [x] TTS endpoint — `routers/tts.py` uses edge-tts, streaming response
- [ ] **Rate limit: max 30 suggestions/min/shop** — NOT implemented on WS suggestion flow. Rate limiting only on auth endpoints.
- [x] Session metrics update: increment counts on suggestion/action — confirmed in `services/sessions.py`

**Prompt:**
- [x] Persona context (name, tone, quirks, phrases) — confirmed in `tasks/llm.py` prompt builder
- [x] RAG product context — confirmed
- [x] RAG FAQ context — confirmed
- [x] Conversation history — confirmed
- [x] Rule: under 40 words — in system prompt
- [x] Rule: KHÔNG bịa thông tin — in system prompt
- [x] Rule: KHÔNG đề cập giá nếu không có data — in system prompt
- [x] Rule: "Để em check rồi báo lại" fallback — hardcoded fallback in tasks/llm.py

**Extension:**
- [x] Overlay shows comment + suggested reply (streaming) — Overlay.tsx + SuggestionCard.tsx
- [x] 4 action buttons: Gửi, Đọc, Sửa, Bỏ — SuggestionCard.tsx
- [x] Gửi = Quick Paste (NOT auto submit) — smart-paste.ts, NO Enter key
- [x] Keyboard shortcuts: Ctrl+Enter, Ctrl+Space, Esc — Overlay.tsx
- [ ] **Ctrl+E shortcut** — documented but NOT wired in Overlay.tsx (edit toggle only via button click)
- [x] Tooltip after paste: "Nhấn Enter để gửi" — smart-paste.ts
- [ ] **MutationObserver detect comment sent → mark 'sent'** — NOT implemented. Smart paste returns success/failure, but there's no observer watching if the user actually presses Enter and the comment appears.
- [ ] **30s timeout detect → mark 'pasted_not_sent'** — `SMART_PASTE_SEND_TIMEOUT` constant defined (30000ms) but **NEVER used**. No timeout logic exists.
- [x] Edit mode: textarea editable + checkbox "Lưu làm FAQ" — SuggestionCard.tsx
- [x] History list with status badges — HistoryList.tsx
- [ ] **First-time onboarding tooltip** — `onboardingSeen` storage key defined but **nothing reads or writes it**

**Tests:**
- [ ] Unit: Intent classifier — **No tests** (despite spec requiring 20+ Vietnamese test cases)
- [ ] Unit: Prompt builder — **No tests**
- [ ] Integration: full flow — **No tests**
- [ ] Integration: cache hit — **No tests**
- [ ] Manual: Facebook Live test — **Not verified**

**F2 Score: 12/15 backend, 8/8 prompt, 7/11 extension = 27/34 (79%)**

---

### F3 — Script Generator

**Backend:**
- [ ] **POST /scripts/generate → enqueue Celery** — STUB. Returns hardcoded message, no enqueue.
- [ ] **Celery task: query script_samples → build prompt → LLM → stream → save** — STUB. Returns `{"status": "not_implemented"}`.
- [ ] **Model routing: Claude Haiku for ≥20 min, Gemini Flash for shorter** — NOT implemented.
- [ ] **Post-processing: word count, duration estimate, CTA count** — NOT implemented.
- [ ] **Script CRUD endpoints** — ALL 5 endpoints are stubs with NO auth, NO validation, NO DB access.
- [ ] **POST /scripts/:id/regenerate** — NOT implemented.
- [ ] **GET /scripts/:id/export/pdf** — NOT implemented.
- [ ] **GET /scripts/:id/export/md** — NOT implemented.
- [ ] **Quota check** — NOT implemented (no real logic to check).
- [ ] **Script version tracking** — NOT implemented.
- [ ] **Streaming via Redis pub/sub → WS** — NOT implemented.

**Prompt:** All items NOT implemented (no prompt exists).

**Frontend:**
- [ ] **Scripts Library page (C4)** — PLACEHOLDER. Static empty state, non-functional button.
- [ ] **Script Generator page (C5)** — NOT created. No `/scripts/new` or `/scripts/[id]` route.
- [ ] **Config panel** — NOT created.
- [ ] **Content panel with streaming** — NOT created.
- [ ] **Stats card** — NOT created.
- [ ] **Action buttons** — NOT created.

**Seed data:**
- [x] 20 script_samples seeded (4 per category × 5 categories) — confirmed in `seed.py`
- [ ] **Samples have embedding** — NOT embedded. `seed.py` inserts raw text without calling embed task. `embedding` column is NULL for all samples.
- [x] Samples in Vietnamese — confirmed natural Vietnamese text in seed.py

**Tests:** ALL items NOT tested.

**F3 Score: 1/11 backend, 0/6 prompt, 0/6 frontend, 1/3 seed = 2/26 (8%)**

---

### F4 — Multi-Platform Browser Extension

**Core infrastructure:**
- [x] Manifest V3 valid — structurally correct MV3
- [x] Background service worker — fully implemented, 8 message handlers
- [x] Content script inject on 4 domains — manifest.json host_permissions correct
- [x] Popup UI 2 states — popup.tsx shows no-live / live-detected / active-session

**Platform adapters:**
- [x] PlatformAdapter interface — types.ts with 8 methods
- [x] Facebook adapter — implemented (fragile selectors)
- [x] YouTube adapter — implemented (stable selectors)
- [x] TikTok adapter — implemented (data-e2e selectors)
- [x] Shopee adapter — implemented (fragile class selectors)
- [ ] **Selector config fetch from server** — NOT implemented. All selectors hardcoded in adapter files. No server endpoint exists for selector config.
- [x] Fallback selectors hardcoded — effectively all selectors are hardcoded (this is the only option)

**Smart Paste:**
- [x] `execCommand('insertText')` primary — confirmed
- [x] `ClipboardEvent` fallback — confirmed
- [x] Native value setter last resort — confirmed
- [x] NEVER dispatch Enter key — confirmed, explicitly documented
- [x] NEVER click Send button — confirmed
- [x] Error handling — returns structured SmartPasteResult
- [x] Tooltip after paste — "Nhấn Enter để gửi", auto-removes after 4s

**Overlay:**
- [x] Mounted via Shadow DOM — mount.ts
- [x] Draggable (saves position to chrome.storage) — Overlay.tsx
- [x] Collapsible — Overlay.tsx
- [x] Z-index high — CSS z-index: 2147483647
- [x] Stats strip: duration, comments, suggestions — Overlay.tsx
- [x] Suggestion card: comment + reply + 4 buttons — SuggestionCard.tsx
- [x] History list scrollable — HistoryList.tsx with max-height: 200px
- [x] Session controls: Tạm dừng, Kết thúc — Overlay.tsx
- [ ] **Session end summary (D4)** — NOT implemented. Session end just unmounts overlay.

**WebSocket:**
- [x] Connect with JWT token — ws-client.ts
- [x] Auto-reconnect exponential backoff (max 10 attempts) — confirmed
- [x] Ping/pong every 30 seconds — confirmed
- [x] Handle session.start, comment.new, suggestion.action, session.end — background/index.ts
- [x] Handle suggestion.stream, suggestion.complete — content/index.ts → overlay events

**Tests:** ALL items NOT tested. No test files exist in extension.

**F4 Score: 4/4 core, 5/6 adapters, 7/7 paste, 9/10 overlay, 5/5 WS = 30/32 (94%)**

---

### F5 — Dashboard Analytics

**Backend:**
- [x] GET /analytics/overview — monthly stats + recent sessions
- [x] GET /analytics/sessions — paginated sessions list with filters
- [x] GET /analytics/sessions/:id — session detail
- [x] GET /analytics/sessions/:id/chart — comments per minute
- [x] GET /analytics/sessions/:id/products — product mentions
- [x] GET /analytics/sessions/:id/top-questions — top FAQ
- [x] GET /analytics/sessions/:id/export — CSV download (Vietnamese headers)
- [x] GET /analytics/usage — monthly usage summary

**Frontend:**
- [ ] **Dashboard Home (C1)** — PLACEHOLDER. Hardcoded "Demo User", no real data, no API calls.
- [ ] **Sessions List (C6a)** — PLACEHOLDER. Static "Chưa có phiên live nào", no API calls.
- [ ] **Session Detail (C6b)** — NOT created. No `/sessions/[id]` route exists.
- [ ] **Charts: Recharts AreaChart, PieChart** — recharts installed but NOT used anywhere.
- [ ] **Real-time: banner when session running** — NOT implemented.
- [ ] **CSV export button** — No UI exists (backend endpoint ready).
- [ ] **Empty states for all sections** — Only static placeholder text.

**Tests:**
- [x] test_analytics.py — 28 tests covering used rate, live hours, schema validation, CSV format
- [ ] Integration: session data → correct analytics — **No integration tests**
- [ ] Manual: dashboard loads under 2s — **Not verified**

**F5 Score: 8/8 backend, 0/7 frontend = 8/15 (53%)**

---

### F6 — Authentication + Billing + Multi-tenancy

**Auth:**
- [x] POST /auth/signup — email + password → hash → OTP
- [x] POST /auth/login — verify password → JWT pair
- [x] POST /auth/refresh — new token pair
- [x] POST /auth/verify-email — OTP verification
- [x] POST /auth/resend-otp — rate limited
- [x] POST /auth/forgot-password — anti-enumeration, reset link
- [x] POST /auth/reset-password — reset via JWT token
- [x] POST /auth/google — OAuth via token validation
- [x] GET /auth/me — current user info + shops
- [x] Password hashing (bcrypt via passlib)
- [x] JWT access 1h + refresh 30d
- [ ] **Refresh token rotation (JTI in Redis)** — NOT implemented. Old refresh tokens remain valid forever. No JTI, no Redis blacklist.
- [x] Rate limiting on auth endpoints — rate_limit.py, applied to login/signup/resend-otp

**Multi-tenancy:**
- [x] POST /shops — creates shop + 4 preset personas + 14-day trial
- [x] X-Shop-Id header required — `get_current_shop` dependency
- [x] Middleware verifies user membership — checks JWT shop_ids + DB role
- [x] SET LOCAL app.current_shop_id — in `get_current_shop`
- [x] RLS policies on all shop-scoped tables — 8 tables confirmed

**Team:**
- [x] GET /shops/current/members — list with user info
- [x] POST /shops/current/members — invite (checks seat limit)
- [x] PATCH /shops/current/members/:mid — change role
- [x] DELETE /shops/current/members/:mid — remove member
- [ ] **Invite email flow** — `send_invite_email()` exists in `services/email.py` but is **NEVER called** from the invite endpoint.

**Billing:**
- [x] POST /billing/checkout — creates LemonSqueezy checkout URL
- [x] POST /webhooks/lemonsqueezy — handle subscription events, HMAC verification
- [ ] **Webhook idempotency** — NOT implemented. No deduplication of events.
- [x] GET /billing/subscription — returns latest subscription
- [x] GET /billing/invoices — paginated
- [x] GET /billing/usage — usage meters
- [x] Plan limits enforcement (PLAN_LIMITS) — `services/usage.py`
- [x] UsageService.track() — writes usage_logs
- [x] UsageService.check_quota() — sums against limits

**Billing bugs:**
- `plan_variant_map` maps plan names to themselves (`"starter" -> "starter"`) instead of real LemonSqueezy variant IDs — **checkout will fail in production**
- `portal` endpoint returns hardcoded `https://app.lemonsqueezy.com/my-orders` — not customer-specific

**Frontend:**
- [x] Sign Up page (B1) — email + password form
- [x] Verify OTP page (B2) — 6 digit, auto-submit, resend timer
- [x] Login page — functional
- [x] Onboarding Wizard (B3-B6) — 4 steps with progress bar (step 3 product input non-functional)
- [x] Account Settings (E1) — profile edit, change password
- [x] Billing page (E2) — plan card, usage meters, invoices
- [x] Team Management (E3) — members list, invite form
- [x] Auth guard middleware — client-side redirect via auth-guard.tsx
- [x] API client with auto refresh token — lib/api.ts handles 401 → refresh
- [x] Zustand auth store — stores/auth.ts
- [x] Vietnamese validation messages — throughout auth pages

**Missing frontend:**
- [ ] **Google OAuth button on signup/login** — `googleLogin` in store but **NO UI anywhere**
- [ ] **Reset password page** — route in middleware PUBLIC_PATHS, store action exists, **NO page file**

**Tests:**
- [x] Password/JWT unit tests — test_auth_utils.py (6 tests)
- [x] OTP tests — test_otp.py (3 tests)
- [x] Schema validation — test_schemas.py (7 tests)
- [x] Slug generation — test_slugify.py (5 tests)
- [ ] Signup → verify → login → protected — **No integration test**
- [ ] Cross-tenant isolation — **No integration test**
- [ ] Quota exceeded → 429 — **No integration test**
- [ ] Webhook idempotency — **No test**

**F6 Score: 11/13 auth, 5/5 tenancy, 4/5 team, 7/9 billing, 11/13 frontend = 38/45 (84%)**

---

## BƯỚC 3: Cross-cutting Concerns

### Security

- [x] All shop-scoped endpoints have auth middleware — confirmed via `get_current_shop` dependency
- [x] All shop-scoped endpoints have X-Shop-Id validation — confirmed
- [x] RLS policies on all shop-scoped tables — 8 tables confirmed
- [ ] **CORS config broken for extension** — `chrome-extension://*` is NOT a valid origin pattern. FastAPI CORSMiddleware treats it as a literal string. Real extension origins like `chrome-extension://abc123` will NOT match. **Extension API calls will be blocked by CORS.**
- [ ] **API keys not hardcoded** — Generally good (uses env vars). BUT `constants.ts` in extension has hardcoded `http://localhost:8000` URLs.
- [ ] **Input validation on ALL endpoints** — Scripts router has NO validation at all. Sessions router has no limit/offset bounds.
- [x] SQL injection: all queries use parameterized statements (SQLAlchemy ORM)
- [ ] **XSS: frontend sanitize user input** — No explicit sanitization. React auto-escapes JSX, but `contenteditable` in SuggestionCard.tsx is a potential vector.
- [x] Rate limiting on public endpoints — auth endpoints covered
- [ ] **WebSocket bypasses RLS** — ws/handler.py uses `async_session()` directly without `SET LOCAL app.current_shop_id`. RLS policies are NOT enforced for WS DB operations.

### Performance

- [x] pgvector HNSW indexes — correct config (m=16, ef_construction=64)
- [ ] **Database indexes for frequent queries** — Not audited with EXPLAIN ANALYZE (requires running DB)
- [ ] **N+1 query check** — analytics `unnest` uses LATERAL join (good). Other queries not audited.
- [x] LLM calls have timeout — `soft_time_limit=30` on generate_suggestion
- [x] Redis cache for suggestions — 5-minute TTL
- [ ] **Image upload via presigned URL** — NOT implemented. No presigned URL endpoint exists. Image upload not wired in frontend.

### Reliability

- [ ] **LLM fallback: Gemini fail → DeepSeek V3** — NOT implemented. `deepseek_api_key` in config but never used.
- [x] Celery embed tasks have retry config — max 3, 10s delay
- [x] Celery LLM task has timeout — 30s soft limit
- [x] WebSocket auto-reconnect — exponential backoff, max 10
- [ ] **Graceful shutdown** — No SIGTERM handler in workers or WS server
- [x] Health check endpoint — GET /health returns {"status": "ok"}
- [ ] **Sentry error tracking** — NOT configured. No Sentry SDK in dependencies.

### UX

- [ ] **All text in Vietnamese** — MOSTLY. Issues:
  - Dashboard page: hardcoded "Demo User" instead of real name
  - Products list: "San sang" / "Dang index" / "Loi" (unaccented)
  - Forgot-password error messages not shown (swallowed)
  - Some error states use `alert()` (English browser dialog)
- [ ] **No English placeholder text** — Found: `"Loading..."` style patterns not checked per-component
- [ ] **Empty states with CTA** — Products page has good empty state. Dashboard/Scripts/Sessions have minimal "Chưa có dữ liệu" text only.
- [ ] **Error messages follow pattern** — Inconsistent. Some use red banners, some use `alert()`, some swallow errors.
- [ ] **Loading states for all async** — Products/auth pages have spinners. Billing page has NO loading skeleton.
- [ ] **Toast notifications** — NOT implemented. No toast/notification system exists.
- [ ] **Responsive on mobile** — Navbar hidden below md breakpoint with NO fallback. Dashboard usable but nav is inaccessible on mobile.

### Legal/Compliance

- [ ] **AI disclosure watermark** — `dh_videos.has_watermark` column exists but NO video feature implemented.
- [ ] **Voice clone consent form** — `voice_clones` table has consent fields but NO router/endpoint for voice clones.
- [ ] **Audit log** — voice_clones table has consent_confirmed_at/by. Not tested.
- [ ] **Terms of Service link in signup** — NOT present in signup page.
- [ ] **Privacy Policy link** — NOT present in any page.
- [ ] **Data retention cron job** — NOT implemented. No cron for deleting comments >90 days.

---

## BƯỚC 4: Inconsistencies (Code vs Spec)

### Critical Inconsistencies

| # | Area | Spec Says | Code Does | Impact |
|---|------|-----------|-----------|--------|
| 1 | Scripts router | Full CRUD + generate + export with auth | All 5 endpoints are stubs, NO auth | F3 completely broken |
| 2 | LLM fallback | Gemini → DeepSeek V3 auto-failover | Only Gemini, no fallback code | Suggestion pipeline fails if Gemini is down |
| 3 | Refresh token | JTI rotation in Redis, old tokens invalidated | Stateless JWT, old refresh tokens valid forever | Security: stolen refresh tokens cannot be revoked |
| 4 | CORS extension | Allow chrome-extension origins | `chrome-extension://*` literal string (non-functional) | Extension REST calls blocked by CORS |
| 5 | WebSocket RLS | All DB ops respect shop_id RLS | WS handler doesn't SET LOCAL app.current_shop_id | Cross-tenant data leak possible via WS |
| 6 | Billing checkout | Map plans to LemonSqueezy variant IDs | Maps `"starter" → "starter"` (self-referential) | Checkout always fails |
| 7 | Seed user | Should be loginable for demo | Uses PostgreSQL crypt() vs API's passlib bcrypt | Demo user cannot log in |
| 8 | Invite email | Send invitation email | Function exists but never called | Invited users have no way to know they were invited |
| 9 | Webhook idempotency | Skip duplicate events | No deduplication logic | Double-processing on webhook retries |
| 10 | Script samples | All 20 samples should have embeddings | seed.py inserts without embedding | Few-shot retrieval via pgvector will return 0 results |

### Medium Inconsistencies

| # | Area | Spec Says | Code Does |
|---|------|-----------|-----------|
| 11 | Dashboard home | Real stats, quick actions, usage meters | Hardcoded "Demo User", static placeholder |
| 12 | Session detail page | Full analytics + charts + export | Page does not exist |
| 13 | Extension auth refresh | Token refresh on expiry | `refreshAuthToken()` never called; 4001 → dead WS |
| 14 | TTS | Google Cloud TTS (vi-VN-Neural2-A) | Uses edge-tts (vi-VN-HoaiMyNeural) — free but lower quality |
| 15 | Popup product selection | User picks products + persona | Hardcoded `shopId: 1`, `personaId: 1`, `productIds: []` |
| 16 | Google OAuth UI | Button on signup/login pages | Store action implemented, NO UI button |
| 17 | Reset password page | Full page with token from email link | No page file exists |
| 18 | Session end summary | D4 wireframe: session stats summary | Session end just unmounts overlay |
| 19 | 30s pasted_not_sent timeout | Timer after paste to detect if user sent | Constant defined, never used |
| 20 | Rate limit on suggestions | 30/min/shop | Not implemented |

---

## BƯỚC 5: Gap Analysis

| # | Gap | Feature | Severity | Effort Est. | Notes |
|---|-----|---------|----------|-------------|-------|
| 1 | CORS broken for extension | F4/F2 | **Critical** | 1h | Fix origin to specific extension ID or `*` for dev |
| 2 | WebSocket bypasses RLS | F2/F4 | **Critical** | 2h | Add SET LOCAL in WS handler before each DB op |
| 3 | Scripts router completely stub | F3 | **Critical** | 16h | Full implementation needed: CRUD + generate + stream |
| 4 | Scripts Celery task stub | F3 | **Critical** | 8h | Implement full pipeline with few-shot + streaming |
| 5 | Billing checkout variant IDs | F6 | **Critical** | 1h | Replace self-map with real LemonSqueezy variant IDs |
| 6 | LLM fallback missing | F2 | **High** | 4h | Add try/except on Gemini call, fallback to DeepSeek |
| 7 | Refresh token not rotatable | F6 | **High** | 4h | Add JTI to Redis, invalidate old tokens |
| 8 | Dashboard home placeholder | F5 | **High** | 6h | Wire up analytics API, real user name, usage meters |
| 9 | Sessions list placeholder | F5 | **High** | 4h | Wire up sessions API with filters |
| 10 | Session detail page missing | F5 | **High** | 8h | Create page with charts (recharts), stats, export |
| 11 | Extension hardcoded localhost | F4 | **High** | 2h | Use env vars or build-time config |
| 12 | Extension popup hardcoded IDs | F4 | **High** | 4h | Add product/persona selection UI |
| 13 | Seed user cannot log in | F6 | **High** | 1h | Use passlib bcrypt in seed.py |
| 14 | Invite email not sent | F6 | **High** | 1h | Call send_invite_email() in shops router |
| 15 | Script samples no embeddings | F3 | **High** | 2h | Run embed task on seed or embed during seed |
| 16 | Google OAuth button missing | F6 | **Medium** | 2h | Add button UI to signup/login pages |
| 17 | Reset password page missing | F6 | **Medium** | 2h | Create page reading token from URL |
| 18 | Extension token refresh | F4 | **Medium** | 3h | Wire refreshAuthToken into WS reconnect + API calls |
| 19 | Webhook idempotency | F6 | **Medium** | 2h | Store processed event IDs in Redis |
| 20 | Onboarding step 3 product input | F1 | **Medium** | 2h | Wire extract-url API call |
| 21 | Vietnamese diacritics on products | F1 | **Medium** | 0.5h | Fix string literals in products/page.tsx |
| 22 | Forgot-password error handling | F6 | **Medium** | 0.5h | Add catch block |
| 23 | 30s pasted_not_sent timeout | F2 | **Medium** | 3h | Implement timer after smart paste |
| 24 | MutationObserver for sent detect | F2 | **Medium** | 4h | Watch DOM for comment appearing after paste |
| 25 | Session end summary (D4) | F4 | **Medium** | 3h | Show stats before unmounting overlay |
| 26 | Ctrl+E keyboard shortcut | F2 | **Low** | 0.5h | Wire in Overlay.tsx |
| 27 | Toast notification system | UX | **Low** | 3h | Add react-hot-toast or similar |
| 28 | First-time onboarding tooltip | F2 | **Low** | 1h | Read/write onboardingSeen storage key |
| 29 | Billing portal customer-specific | F6 | **Low** | 2h | Use LemonSqueezy customer portal API |
| 30 | Rate limit on suggestions | F2 | **Low** | 2h | Add Redis counter per shop in WS handler |
| 31 | Terms of Service link | Legal | **Low** | 0.5h | Add link to signup page |
| 32 | Privacy Policy link | Legal | **Low** | 0.5h | Add link to footer |
| 33 | Data retention cron | Legal | **Low** | 3h | Cron to delete comments >90 days |
| 34 | Mobile nav fallback | UX | **Low** | 2h | Add hamburger menu |
| 35 | Sentry integration | Ops | **Low** | 2h | Add sentry-sdk to deps, configure DSN |
| 36 | No integration tests | QA | **Low** | 16h+ | Significant effort; prioritize after features |
| 37 | No frontend/extension tests | QA | **Low** | 16h+ | Set up Vitest + testing-library |

---

## BƯỚC 6: Recommendations

### 6A. MUST Fix Before Launch (Critical + High) — Priority Order

| # | Problem | Files | Solution | Effort |
|---|---------|-------|----------|--------|
| 1 | CORS broken for extension | `apps/api/app/main.py` | Replace `chrome-extension://*` with actual extension ID or use `*` for dev. In production, set specific `chrome-extension://<id>` | 1h |
| 2 | WebSocket bypasses RLS | `apps/api/app/ws/handler.py` | Add `SET LOCAL app.current_shop_id` before every DB write in WS handler (session start, comment create, suggestion update) | 2h |
| 3 | Billing checkout variant IDs | `apps/api/app/routers/billing.py` | Replace `plan_variant_map` with real LemonSqueezy variant IDs from dashboard | 1h |
| 4 | Seed user login broken | `apps/api/seed.py` | Use `from app.auth.utils import hash_password` instead of PostgreSQL crypt() | 1h |
| 5 | LLM fallback (DeepSeek V3) | `apps/workers/tasks/llm.py` | Wrap Gemini streaming call in try/except, retry with DeepSeek V3 API on failure | 4h |
| 6 | Refresh token rotation | `apps/api/app/auth/utils.py`, `service.py` | Add JTI claim, store in Redis, check on refresh, delete old on rotation | 4h |
| 7 | Dashboard home placeholder | `apps/dashboard/src/app/(dashboard)/dashboard/page.tsx` | Call analytics/overview API, display real user name, stats, usage meters, recent sessions | 6h |
| 8 | Sessions list page | `apps/dashboard/src/app/(dashboard)/sessions/page.tsx` | Wire up analytics/sessions API with platform filter tabs, date filter | 4h |
| 9 | Session detail page | NEW: `apps/dashboard/src/app/(dashboard)/sessions/[id]/page.tsx` | Create page with stat cards, Recharts area chart, pie chart, top questions, CSV export | 8h |
| 10 | Scripts full implementation | `apps/api/app/routers/scripts.py`, `apps/workers/tasks/script.py` | Implement full CRUD + generate with auth, streaming, few-shot RAG, model routing | 24h |
| 11 | Scripts frontend | `apps/dashboard/src/app/(dashboard)/scripts/page.tsx`, NEW pages | Scripts library (grid), generator (split view), config panel, streaming preview | 16h |
| 12 | Extension hardcoded URLs | `apps/extension/src/lib/constants.ts` | Use `import.meta.env` or Vite define for build-time URL injection | 2h |
| 13 | Extension popup product/persona selection | `apps/extension/src/popup/popup.tsx` | Fetch products/personas from API, add selection UI | 4h |
| 14 | Invite email not sent | `apps/api/app/routers/shops.py` | Add `await email_service.send_invite_email(...)` after creating membership | 1h |
| 15 | Script samples need embeddings | `apps/api/seed.py` | Call Gemini embed API during seed, or enqueue embed tasks after seed | 2h |

**Total effort for Critical+High: ~80h**

### 6B. Should Fix Within Week 1 Post-Launch (Medium)

| # | Problem | Files | Solution | Effort |
|---|---------|-------|----------|--------|
| 1 | Google OAuth button | signup/login pages | Add "Đăng nhập bằng Google" button calling `googleLogin()` | 2h |
| 2 | Reset password page | NEW: `apps/dashboard/src/app/(auth)/reset-password/page.tsx` | Create page that reads token from URL, calls resetPassword() | 2h |
| 3 | Extension token refresh | `apps/extension/src/lib/auth.ts`, background/index.ts | Wire refreshAuthToken into WS 4001 handler and API error handler | 3h |
| 4 | Webhook idempotency | `apps/api/app/routers/webhooks.py` | Store `event_id` in Redis with TTL, skip if seen | 2h |
| 5 | Onboarding step 3 wired | `apps/dashboard/src/app/(auth)/onboarding/page.tsx` | Call extract-url API, create product on submit | 2h |
| 6 | Vietnamese diacritics fix | `apps/dashboard/src/app/(dashboard)/products/page.tsx` | Fix "San sang" → "Sẵn sàng", "Dang index" → "Đang index", "Loi" → "Lỗi" | 0.5h |
| 7 | Forgot-password error handling | `apps/dashboard/src/app/(auth)/forgot-password/page.tsx` | Add catch block to show error message | 0.5h |
| 8 | 30s pasted_not_sent timeout | `apps/extension/src/content/index.ts` | Start 30s timer after successful paste, send pasted_not_sent if no sent event | 3h |
| 9 | MutationObserver sent detection | Extension adapters | Watch for comment appearing in DOM after paste, mark as sent | 4h |
| 10 | Session end summary | `apps/extension/src/content/overlay/Overlay.tsx` | Show stats modal before unmount | 3h |

**Total effort for Medium: ~22h**

### 6C. Backlog — Fix When Time Allows (Low)

| # | Problem | Effort |
|---|---------|--------|
| 1 | Ctrl+E keyboard shortcut | 0.5h |
| 2 | Toast notification system | 3h |
| 3 | First-time onboarding tooltip in extension | 1h |
| 4 | Billing portal customer-specific URL | 2h |
| 5 | Rate limit on suggestion generation (30/min/shop) | 2h |
| 6 | Terms of Service link on signup | 0.5h |
| 7 | Privacy Policy link in footer | 0.5h |
| 8 | Data retention cron (comments >90 days) | 3h |
| 9 | Mobile nav hamburger menu | 2h |
| 10 | Sentry error tracking integration | 2h |
| 11 | Integration test suite (backend) | 16h+ |
| 12 | Frontend test suite (Vitest + RTL) | 16h+ |
| 13 | Extension test suite (Vitest) | 8h+ |

### 6D. Things NOT To Do Before 10 Paying Customers

| # | Feature | Why Not Now |
|---|---------|-------------|
| 1 | Digital Human Video (dh_videos) | Table exists, no endpoints. Expensive HeyGen integration. Zero demand signal yet. |
| 2 | Voice Cloning | Table exists with consent fields, no endpoints. ElevenLabs integration cost. Legal complexity. |
| 3 | Self-hosted TTS (CosyVoice) | edge-tts works fine for MVP. Only optimize when API cost exceeds $200/month. |
| 4 | Fine-tune Vietnamese LLM | Gemini Flash quality is sufficient. Fine-tuning requires data + compute + months of work. |
| 5 | Multi-language support | Vietnamese-only is correct for target market. |
| 6 | Public developer API | Zero developers waiting. Build when agencies request it. |
| 7 | Mobile companion app | Dashboard is responsive enough. Build only when mobile usage exceeds 20%. |
| 8 | 2FA/TOTP | `two_fa_enabled` column exists. No actual TOTP implementation. Not needed for MVP. |
| 9 | Selector config server endpoint | Hardcoded selectors work. Server-managed selectors only needed when updating without extension release. |
| 10 | Advanced analytics (heatmaps, funnels) | Basic session stats are enough. Analytics depth follows user count. |

---

## BƯỚC 7: Final Verification Report

```
═══════════════════════════════════════════════════════════════
         AI CO-HOST MVP — VERIFICATION REPORT
         Date: 2026-04-10
═══════════════════════════════════════════════════════════════

OVERALL STATUS: ██ NOT READY ██

Feature Completion:
  F1 Products:      [21/28] ██████████████░░░░░░ 75%
  F2 Comment AI:    [27/34] ████████████████░░░░ 79%
  F3 Scripts:       [ 2/26] ██░░░░░░░░░░░░░░░░░░  8%  ← BLOCKER
  F4 Extension:     [30/32] ██████████████████░░ 94%
  F5 Analytics:     [ 8/15] ██████████░░░░░░░░░░ 53%  ← BLOCKER
  F6 Auth/Billing:  [38/45] █████████████████░░░ 84%

Cross-cutting:
  Security:         [5/10]  █████░░░░░ 50%  ← CORS + RLS issues
  Performance:      [4/6]   ██████░░░░ 67%
  UX Vietnamese:    [2/7]   ███░░░░░░░ 29%
  Legal/Compliance: [0/6]   ░░░░░░░░░░  0%

Test Coverage:
  Backend unit:     47 pass / 2 skip (pure unit only)
  Backend integ:    0 tests
  Frontend:         0 tests
  Extension:        0 tests

Gaps Summary:
  Critical:   5 items  — MUST fix before launch
  High:      10 items  — SHOULD fix before launch
  Medium:    10 items  — fix within week 1 post-launch
  Low:       13 items  — backlog

Top 5 Risks:
  1. F3 Scripts is 8% complete — entire feature unimplemented
     (backend stubs, frontend placeholder, Celery stub)
  2. CORS blocks extension→API calls — no extension feature
     works in real Chrome until fixed
  3. WebSocket bypasses RLS — cross-tenant data leak in the
     most security-sensitive flow (live comments)
  4. F5 Dashboard/Sessions frontend is placeholder — users
     see nothing after login
  5. No LLM fallback — if Gemini API goes down, all AI
     features stop working (suggestions, highlights, FAQs)

════════════════════════════════════════════════════════════════
RECOMMENDATION: DELAY ~2 WEEKS
════════════════════════════════════════════════════════════════

Reasoning:
  The backend API layer is 85%+ complete with solid
  architecture (RLS, auth, Celery pipelines). F2 Comment AI
  and F4 Extension are production-quality. However, F3 Scripts
  is entirely unimplemented (8%), F5 Analytics frontend is
  placeholder (53%), and there are 5 Critical security/billing
  bugs. The 2 Critical security issues (CORS + WS RLS bypass)
  can be fixed in hours, but F3 requires ~40h of full-stack
  work. Recommend: fix Critical bugs (Week 1), implement F3 +
  F5 frontend (Week 2), then launch.
```

---

*Generated by QA Lead audit on 2026-04-10. All findings based on code reading — no live environment testing performed.*
