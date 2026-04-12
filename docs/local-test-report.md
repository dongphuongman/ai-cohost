# Local Testing Report - AI Co-host MVP

**Date:** 2026-04-11
**Tester:** Claude Code (automated) + manual verification pending
**Environment:** macOS Darwin 24.6.0, Docker 29.1.3, Node v25.2.1, Python 3.13/3.14, pnpm 9.15.4

---

## INFRASTRUCTURE STATUS

| Service              | Status | Notes                                |
|----------------------|--------|--------------------------------------|
| PostgreSQL (pgvector)| PASS   | pgvector 0.8.2, port 5434            |
| Redis                | PASS   | v7-alpine, port 6379                 |
| Adminer              | PASS   | port 8080                            |
| Mailhog              | PASS   | SMTP 1025, UI 8025                   |
| API Server (:8000)   | PASS   | Uvicorn + FastAPI, hot reload        |
| Dashboard (:3000)    | PASS   | Next.js 16.2.3 (Turbopack)           |
| Extension (Vite)     | PASS   | CRXJS build, watch mode              |
| Celery Workers       | SKIP   | Not started (no LLM API keys)        |
| DB Tables            | PASS   | 16 tables + alembic_version          |
| Vector Indexes       | PASS   | 3 HNSW indexes (products, faqs, scripts) |
| RLS Policies         | PASS   | 8/8 tables with rowsecurity=true     |
| Seed Data            | PASS   | 1 shop, 1 user, 4 personas, 5 products, 20 script_samples |

---

## AUTOMATED TESTS

### Backend Unit Tests
**Result: 49 passed, 0 failed, 0 skipped**

| Test File            | Tests | Status |
|----------------------|-------|--------|
| test_analytics.py    | 24    | PASS   |
| test_auth_utils.py   | 6     | PASS   |
| test_otp.py          | 3     | PASS   |
| test_schemas.py      | 7     | PASS   |
| test_slugify.py      | 5     | PASS   |
| test_usage.py        | 4     | PASS   |

### Frontend Tests (Dashboard)
**Result: 10 passed, 0 failed**

| Test File            | Tests | Status |
|----------------------|-------|--------|
| toast-store.test.ts  | 4     | PASS   |
| api-client.test.ts   | 6     | PASS   |

### Extension Tests
**Result: 7 passed, 0 failed**

| Test File            | Tests | Status |
|----------------------|-------|--------|
| constants.test.ts    | 2     | PASS   |
| adapters.test.ts     | 5     | PASS   |

### API Endpoint Smoke Tests

| Endpoint                    | Method | Status | HTTP Code |
|-----------------------------|--------|--------|-----------|
| /api/v1/auth/signup         | POST   | PASS   | 201       |
| /api/v1/auth/login          | POST   | PASS   | 200       |
| /api/v1/auth/me             | GET    | PASS   | 200       |
| /api/v1/shops/              | GET    | PASS   | 200       |
| /api/v1/products/           | GET    | PASS   | 200       |
| /api/v1/products/           | POST   | PASS   | 201       |
| /api/v1/products/{id}       | GET    | PASS   | 200       |
| /api/v1/products/{id}       | PATCH  | PASS   | 200       |
| /api/v1/products/{id}       | DELETE | PASS   | 204       |
| /api/v1/products/{id}/faqs/ | GET    | PASS   | 200       |
| /api/v1/personas/           | GET    | PASS   | 200       |
| /api/v1/scripts/            | GET    | PASS   | 200       |
| /api/v1/sessions/           | GET    | PASS   | 200       |
| /api/v1/billing/subscription| GET    | PASS   | 200       |
| /api/v1/billing/usage       | GET    | PASS   | 200       |
| /api/v1/billing/invoices    | GET    | PASS   | 200       |
| /health                     | GET    | PASS   | 200       |

### WebSocket Tests

| Test                          | Status | Notes                                    |
|-------------------------------|--------|------------------------------------------|
| Connect with valid token      | PASS   |                                          |
| Ping/Pong                     | PASS   |                                          |
| session.start                 | PASS   | Returns session UUID                     |
| comment.new (ingest)          | PASS   | Comment saved to DB                      |
| Suggestion generation         | SKIP   | No LLM API key configured               |
| session.end                   | PASS   | Session ended_at written to DB           |
| Connect with invalid token    | PASS   | Rejected with HTTP 403                   |

---

## SECURITY TESTS

| Test                          | Status | Result                                   |
|-------------------------------|--------|------------------------------------------|
| No auth token                 | PASS   | HTTP 401 (Bearer scheme required)        |
| Invalid JWT token             | PASS   | HTTP 401                                 |
| Cross-tenant access           | PASS   | HTTP 403                                 |
| SQL injection in search       | PASS   | HTTP 200, query safe (parameterized)     |
| XSS in product name           | NOTE   | Stored as-is; frontend must escape       |
| Empty product name            | PASS   | HTTP 422 (validation error)              |
| Duplicate email signup        | PASS   | HTTP 409 (conflict)                      |
| Rate limiting (login)         | PASS   | HTTP 429 after threshold                 |
| WS without token              | PASS   | Connection rejected                      |

---

## PERFORMANCE TESTS

| Endpoint                    | Response Time | Target  | Status |
|-----------------------------|--------------|---------|--------|
| GET /api/v1/products/       | 4.7ms        | < 500ms | PASS   |
| GET /api/v1/sessions/       | 2.7ms        | < 500ms | PASS   |
| GET /api/v1/scripts/        | 4.9ms        | < 500ms | PASS   |
| GET /api/v1/billing/subscription | 3.3ms   | < 500ms | PASS   |
| GET /health                 | 3.3ms        | < 500ms | PASS   |

All endpoints well under 5ms locally.

---

## MANUAL TESTS (Pending - Requires Browser)

The following tests require a browser and cannot be fully automated via CLI.
Instructions provided for manual execution:

### F6 Auth Flow
- [ ] Test 1: Signup flow (/signup page)
- [ ] Test 2: Login with demo@cohost.vn / demo1234
- [ ] Test 3: Protected route redirect (incognito -> /dashboard -> /login)
- [ ] Test 4: Onboarding wizard (4 steps)

### F1 Products
- [ ] Test 5: Products empty state (new shop)
- [ ] Test 6: Add product manually via UI
- [ ] Test 7: AI generate highlights (SKIP if no GEMINI_API_KEY)
- [ ] Test 8: AI generate FAQ (SKIP if no GEMINI_API_KEY)
- [ ] Test 9: Product search
- [ ] Test 10: Delete product with confirm dialog

### F3 Scripts
- [ ] Test 11: Scripts empty state
- [ ] Test 12: Generate script (SKIP if no LLM API key)
- [ ] Test 13: Edit script
- [ ] Test 14: Export PDF
- [ ] Test 15: Script library grid view

### F4 Extension
- [ ] Test 16: Load unpacked extension from apps/extension/dist
- [ ] Test 17: Extension popup (no live detected)
- [ ] Test 18: Extension popup on live page
- [ ] Test 19: Start session via extension
- [ ] Test 20: Overlay UI (draggable, collapsible)
- [ ] Test 21: End session + summary

### F2 Comment Responder (Requires LLM API key)
- [ ] Test 22: Comment suggestion generation
- [ ] Test 23: Smart Paste / Quick Paste
- [ ] Test 24: TTS (requires Google TTS key)
- [ ] Test 25: Edit + Save as FAQ

### F5 Analytics
- [ ] Test 26: Dashboard home (stat cards, usage meter)
- [ ] Test 27: Session detail (charts, product mentions)
- [ ] Test 28: CSV export

---

## BUGS FOUND & FIXED

### Critical (Fixed during test)

1. **passlib/bcrypt incompatibility** (auth/utils.py)
   - **Symptom:** Login 500 error — `passlib` crashes with bcrypt 5.0.0
   - **Root cause:** passlib is abandoned, incompatible with bcrypt >= 4.1
   - **Fix:** Replaced `passlib.CryptContext` with direct `bcrypt.hashpw`/`bcrypt.checkpw`
   - **File:** `apps/api/app/auth/utils.py`

2. **SET LOCAL RLS parameter binding** (auth/dependencies.py)
   - **Symptom:** All shop-scoped endpoints return 500
   - **Root cause:** asyncpg does not support parameterized `SET LOCAL` (`$1` syntax error)
   - **Fix:** Changed to f-string with `int()` cast (safe — value is already validated as int by FastAPI)
   - **File:** `apps/api/app/auth/dependencies.py`

3. **Settings extra fields forbidden** (core/config.py)
   - **Symptom:** App fails to start when .env has vars not in Settings model (R2, Supabase, etc.)
   - **Root cause:** pydantic-settings defaults to `extra = "forbid"`
   - **Fix:** Added `"extra": "ignore"` to `model_config`
   - **File:** `apps/api/app/core/config.py`

### Medium

4. **XSS in product names** — HTML tags stored as-is in DB
   - **Impact:** Potential XSS if frontend renders with `v-html` or `dangerouslySetInnerHTML`
   - **Recommendation:** Add server-side HTML sanitization OR ensure all frontend rendering uses text interpolation (Vue `{{ }}` / React `{}` auto-escape)
   - **Status:** NOT FIXED — verify frontend escaping in manual tests

### Low

5. **Stale venv path** — `.venv` contained hardcoded path from old directory ("Ken Kid")
   - **Impact:** `uv run` commands fail until venv recreated
   - **Fix:** Deleted and recreated with `uv sync`
   - **Note:** This is a local dev environment issue, not a code bug

6. **Rate limit window accumulation** — Login rate limit triggered after only 2 attempts due to prior test runs in same window
   - **Impact:** None (correct behavior, just aggressive window)
   - **Note:** Rate limit key includes time window, resets naturally

---

## SUMMARY

| Category             | Result                              |
|----------------------|-------------------------------------|
| Backend Unit Tests   | 49/49 passed                        |
| Dashboard Tests      | 10/10 passed                        |
| Extension Tests      | 7/7 passed                          |
| API Smoke Tests      | 17/17 passed                        |
| WebSocket Tests      | 6/6 passed (1 skipped, no LLM key) |
| Security Tests       | 8/9 passed (1 note: XSS)           |
| Performance Tests    | 5/5 passed (all < 5ms)             |
| Manual UI Tests      | Pending (28 tests, requires browser)|

### Issues Found
- **Critical:** 3 (all fixed)
- **High:** 0
- **Medium:** 1 (XSS — needs frontend verification)
- **Low:** 2 (env issues)

### VERDICT: READY FOR MANUAL QA

All automated tests pass. Three critical bugs found and fixed during testing.
Before deploy, complete the manual browser tests (especially auth flow, extension overlay, and verify frontend XSS escaping).
LLM-dependent features (AI highlights, FAQ generation, script generation, comment suggestions) require API keys to test.
