# Changelog

All notable changes to AI Co-host will be documented in this file.

## [0.1.0.0] - 2026-04-12

### Added
- F6 Auth / Billing / Multi-tenancy: new routers, schemas, migrations, and service wiring for shop-scoped access control and plan-based gating
- AI Insights: allowed-actions registry with plan-based filtering so the LLM can only recommend dashboard features a shop actually has access to
- Plan-gate test coverage for `prefer_quality` digital-human video path (Pro/Enterprise only)
- Insights orchestration tests covering cache hit, Gemini init failure fallback, retry loop on generic output, and final-attempt hallucination filtering
- Local test report, setup guide (md + docx), and live-stream simulator under `docs/` / repo root

### Changed
- Session Insights: LLM responses are now validated against the allowed-actions registry and rejected when they reference features that don't exist (hallucination guard)
- Session Insights: hallucinated-item tracking uses list identity (`is`) instead of `id(obj)`, avoiding the theoretical GC-reuse false-positive
- Session Insights: `_format_duration` rewritten with named `total_minutes` / `hours` / `remaining_minutes` locals for readability
- Allowed Actions: duplicate-key guard is now a runtime `raise RuntimeError` (not `assert`) so `python -O` cannot strip it
- Auto-Reply: added public `get_redis()` accessor; `ws/handler.py` now imports the public name instead of the module-private `_get_redis`
- WebSocket handler: lifted inline suggestion-action whitelist to module-level `_ALLOWED_SUGGESTION_ACTIONS` frozenset (renamed from the colliding `_ALLOWED_ACTIONS`)
- WebSocket handler: removed duplicate inline `from datetime import ...`
- Worker DH providers (HeyGen): updated pipeline handling
- Extension: test layout migrated from `__tests__/` to `tests/`

### Fixed
- Grounding AI Insights in real UI via `FORBIDDEN_PHRASES` + retry-with-suffix feedback, preventing stale feature names from leaking through cached prompts

## [0.0.5.0] - 2026-04-12

### Added
- F7 Voice Cloning: CRUD endpoints for voice clones with audio/consent file upload, magic byte validation
- F8 Digital Human Video: generation pipeline via HeyGen, video status tracking, paginated listing
- F9 Auto-Reply: comment classifier (rule-based + LLM fallback), suggestion routing, WebSocket auto-reply flow with countdown UI, popup toggle, and kill switch
- F10 Moderation: content filtering rules (blocked keywords, regex patterns), comment flagging, bulk approve/dismiss with validation

### Changed
- Voice clone and video list endpoints now support pagination (limit/offset)
- LLM classifier runs in thread pool to avoid blocking the event loop
- Auto-reply rate limiter persists disable state via DB commit
- Session action counters map auto_sent and auto_cancelled to correct columns
- Extension forwards auto_reply and auto_reply.disabled message types

### Fixed
- Regex pattern validation at write time prevents ReDoS via malicious moderation rules
- Bulk moderation request validates comment_ids length (1-1000)
- Audio upload validates magic bytes (MP3/WAV/M4A), consent upload validates PDF header
- Session status values corrected (active to running) for WebSocket reconnection
- Error capture bug, utcnow deprecation, lazy Redis init, shadowed import fixes

## [0.0.4.0] - 2026-04-11

### Added
- Shop config endpoint returning industry, platform, and team size options for onboarding forms
- Production settings validator: fail-fast on default JWT_SECRET in non-development environments
- Extension test infrastructure: vitest config and adapter/constants test suites
- Test coverage for config validation, product schema HTML sanitization, and reset token JTI

### Fixed
- Refresh token replay attack: JTI rotation ensures each refresh token can only be used once
- Password reset link reuse: reset tokens now enforce single-use via JTI consumption
- CORS wildcard for extensions: restricted to specific extension ID instead of `chrome-extension://*`
- Google OAuth bypass when client ID unconfigured: now returns 503 instead of silently skipping validation
- PDF export SSRF: blocked external URL fetching in WeasyPrint renderer
- PDF export blocking: moved rendering to thread pool via `asyncio.to_thread()`
- Script title XSS in PDF export: HTML-escaped title before embedding in template
- Prompt injection in script generation: user notes wrapped in XML delimiters with explicit data-only instruction
- Redundant string replacement in worker sync DB URL construction

### Changed
- `extension_id` config field added to Settings for explicit CORS origin matching

## [0.0.3.0] - 2026-04-10

### Added
- Dashboard analytics API: overview stats (live hours, comments, used rate, scripts count), session list with pagination and filtering, session detail drill-down
- Comments-per-minute chart endpoint with date_trunc bucketing
- Product mentions endpoint using LATERAL unnest on suggestion RAG product IDs
- Top questions endpoint filtered by intent category
- Comments with latest suggestion via LEFT JOIN LATERAL pattern
- CSV export endpoint with Vietnamese headers and StreamingResponse
- Monthly usage summary with per-plan quota meters
- 24 unit tests covering business logic, all 10 Pydantic schemas, CSV format, and chart bucketing

### Fixed
- Defense-in-depth: all analytics session sub-queries now enforce shop_id at the data layer, not just the router auth check
- Cross-tenant product leak: added shop_id filter on products table join in product mentions query
- Usage summary period parameter now auto-normalizes to first-of-month

## [0.0.2.0] - 2026-04-10

### Added
- Product CRUD service with search, pagination, sort, and embedding status tracking
- FAQ CRUD service with bulk creation, ordering, and auto-embedding on create/update
- AI generation endpoints: product highlights and FAQ generation via Gemini Flash
- URL extraction service for Shopee and TikTok product pages (API + HTML fallback)
- WebSocket handler for real-time livestream sessions with JWT auth, comment ingestion, and Redis pub/sub suggestion streaming
- Session lifecycle service: start, end, interrupt, comment tracking, suggestion action counts
- Intent classification service (keyword-based, 9 intents, no LLM call)
- RAG retrieval service using pgvector CTE queries (top 2 products + top 3 FAQs)
- Celery worker for LLM suggestion generation: classify, embed, RAG, prompt, stream via Gemini Flash
- Celery worker for product and FAQ embedding generation via Gemini text-embedding-004
- TTS endpoint using edge-tts for reading suggestions aloud
- Chrome extension: comment reader, smart paste, overlay UI, platform adapters (Facebook, YouTube, TikTok, Shopee)
- Pydantic response schemas for products, FAQs, personas, AI generation, and URL extraction

### Fixed
- SSRF protection on URL extraction: replaced broken denylist with domain allowlist
- IDOR on suggestion actions and session end: added shop_id scoping
- IDOR on FAQ update/delete: added product_id verification in WHERE clause
- SQL LIKE wildcard injection: escape % and _ before ILIKE queries
- LLM output sanitization: strip HTML tags from generated responses
- Persona set-default race condition: atomic UPDATE instead of select-then-update
- Deactivated products now removed from RAG index on is_active=false

## [0.0.1.0] - 2026-04-10

### Added
- Email OTP verification flow (signup sends OTP, verify-email endpoint validates and creates personal shop)
- Google OAuth login/registration with audience and email_verified validation
- Password reset flow (forgot-password + reset-password with JWT tokens)
- Rate limiting on auth endpoints (signup, login, forgot-password, verify-email, resend-otp) via Redis
- Email service using Resend API (OTP, password reset, team invitations)
- Billing endpoints: subscription view, invoice listing, usage metering, plan listing, checkout (LemonSqueezy), cancel, portal
- Usage tracking and quota enforcement (per-plan limits on live hours, products, scripts, videos, voice clones, team seats)
- Preset persona templates (4 Vietnamese-language personalities) auto-created on shop creation
- Seat limit enforcement on team member invitations
- Redis client module for OTP storage and rate limiting

### Changed
- Signup no longer returns tokens directly. Returns user_id + message, requiring email verification first
- Login now enforces email_verified check before issuing tokens
