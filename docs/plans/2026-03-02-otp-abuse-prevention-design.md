# OTP Abuse Prevention — Design Document

**Date**: 2026-03-02
**Status**: Approved

## Problem

The OTP email system uses Resend (free tier: 100 emails/day). Current protection
is only IP-based rate limiting (3/min via slowapi), which is easily bypassed with
IP rotation. A bot or malicious user could exhaust the daily email quota, blocking
legitimate users from logging in.

## Context

- **Auth methods available**: OTP (email), Passkeys (WebAuthn), Legacy password (pending removal)
- **Passkeys are free and unlimited** — no API cost per login
- **OTP is only needed for**: first login (new user) or new device without synced passkey
- **Resend free tier**: 100 emails/day, 3000/month

## Approach: OTP as Minimal Fallback + Backend Hardening

Protect OTP with layered backend rate limits and promote passkeys as the primary
auth method to reduce OTP usage organically.

## Design

### 1. Per-Email Rate Limit (5/hour)

**File**: `src/api/routes/otp.py`

Before creating a new OTP code, count recent codes for that email:

```sql
SELECT COUNT(*) FROM otp_codes
WHERE email = :email AND created_at > now() - interval '1 hour'
```

If count >= 5 → respond `429 Too Many Requests` with generic message.

**Rationale**: Prevents a single email from being spammed. 5/hour is generous for
legitimate retries but limits per-email abuse.

### 2. Global Daily Cap (configurable, default 50)

**Files**: `src/core/config.py`, `src/api/routes/otp.py`

New setting: `otp_daily_limit: int = 50`

Before sending any OTP email, count today's total:

```sql
SELECT COUNT(*) FROM otp_codes
WHERE created_at >= date_trunc('day', now() AT TIME ZONE 'UTC')
```

If count >= `settings.otp_daily_limit` → respond `503 Service Unavailable`.

Log `otp_daily_cap_reached` via structlog. Passkeys continue working unaffected.

**Rationale**: Hard ceiling prevents total quota exhaustion. Configurable via env
var (`OTP_DAILY_LIMIT`) without redeploy. Default 50 leaves 50% margin on Resend
free tier.

### 3. Generic Error Messages

Do not reveal exact limits to attackers:
- 429: "Demasiados intentos. Intenta mas tarde."
- 503: "Servicio temporalmente no disponible."

### 4. Passkey Promotion Banner (Frontend)

**Files**: New `PasskeyPrompt` component, modify Dashboard page

After OTP login, if user has no registered passkeys:
- Show a dismissable banner: "Registra tu huella digital para iniciar sesion sin codigos"
- Check: `GET /api/auth/webauthn/credentials` → if empty array, show banner
- Dismiss with "Ahora no" → persist in `sessionStorage` (reappears on next login)

**Rationale**: Reduces OTP usage organically by converting users to passkeys.

## Protection Summary

```
Request OTP flow:
  |-- IP rate limit (3/min)      [existing - slowapi]
  |-- Email rate limit (5/hour)  [NEW - DB query]
  |-- Global daily cap (50/day)  [NEW - DB query]
  \-- send_otp_email()           [existing - Resend API]
```

Worst case for an attacker: 50 wasted emails in a day (not 100).

## Out of Scope

- CAPTCHA/Turnstile (unnecessary with this approach + passkey strategy)
- Removing legacy password (separate effort)
- Disposable email domain blocking (overkill for current volume)

## Testing Strategy

- Unit tests for per-email rate limit (mock DB counts)
- Unit tests for global daily cap (mock DB counts)
- Unit test for generic error messages (no limit leakage)
- Frontend: manual verification of PasskeyPrompt banner behavior
