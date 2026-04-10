# Changelog

All notable changes to AI Co-host will be documented in this file.

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
