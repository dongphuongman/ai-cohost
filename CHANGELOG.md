# Changelog

All notable changes to AI Co-host will be documented in this file.

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
