# WebAuthn Passkeys — Design Document

**Date**: 2026-03-01
**Status**: Implemented

## Problem

The current login flow relies on shared password (legacy) and email OTP. Users want to log in with biometrics (fingerprint, Face ID) without typing a password or waiting for an email code.

## Decision

Add WebAuthn/FIDO2 passkey support using `py_webauthn` (backend) and `@simplewebauthn/browser` (frontend). Keep OTP as primary login and recovery fallback. Keep legacy password login temporarily during migration.

## Requirements

- Users register passkeys after initial OTP login
- Multiple passkeys per user (phone + laptop, etc.)
- OTP always available as fallback/recovery
- Legacy password login kept temporarily
- Small team scale (5-50 users)

## Architecture

### Database: `WebAuthnCredential` model

```python
class WebAuthnCredential(Base):
    __tablename__ = "webauthn_credentials"

    id: Mapped[uuid.UUID]           # PK, gen_random_uuid()
    user_id: Mapped[uuid.UUID]      # FK → users.id, ON DELETE CASCADE
    credential_id: Mapped[bytes]    # unique, raw credential ID from authenticator
    public_key: Mapped[bytes]       # COSE public key
    sign_count: Mapped[int]         # replay attack protection counter
    device_name: Mapped[str]        # user-friendly label ("Paul's iPhone")
    transports: Mapped[dict | None] # JSONB, e.g. ["usb", "ble", "nfc", "internal"]
    backed_up: Mapped[bool]         # whether credential is synced/backed up
    last_used_at: Mapped[datetime | None]  # last successful login with this credential
    created_at: Mapped[datetime]    # server_default=func.now()
```

One Alembic migration adding this table. Index on `user_id` and unique constraint on `credential_id`.

### API Endpoints

All under `src/api/routes/webauthn.py`, prefix `/api/auth/webauthn`.

#### Registration (authenticated)

| Endpoint | Rate limit | Description |
|----------|-----------|-------------|
| `POST /register/options` | 3/min | Generate challenge + PublicKeyCredentialCreationOptions |
| `POST /register/verify` | 3/min | Verify attestation, store credential with `device_name` |

#### Login (unauthenticated)

| Endpoint | Rate limit | Description |
|----------|-----------|-------------|
| `POST /login/options` | 5/min | Takes `email`, generates challenge + PublicKeyCredentialRequestOptions |
| `POST /login/verify` | 5/min | Verify assertion, update sign_count + last_used_at, return JWT tokens |

#### Credential management (authenticated)

| Endpoint | Rate limit | Description |
|----------|-----------|-------------|
| `GET /credentials` | 10/min | List user's registered passkeys |
| `DELETE /credentials/{id}` | 3/min | Remove a passkey |

#### Challenge storage

In-memory dict keyed by user email/id, value is `(challenge_bytes, expiry_timestamp)`. 5-minute TTL, auto-pruned on access. Same pattern as `_refresh_tokens`.

### Frontend

**Login page** (`Login.tsx`):
- Add "Sign in with Passkey" button on the email step
- Clicking it: enter email → call `/webauthn/login/options` → `navigator.credentials.get()` (browser biometric prompt) → `/webauthn/login/verify` → JWT tokens
- OTP flow unchanged

**Settings page** (new `/settings` route):
- Security section listing registered passkeys (device name, created date, last used)
- "Register new passkey" button → enter device name → `navigator.credentials.create()` → verify
- Delete passkey button per row

**New dependency**: `@simplewebauthn/browser` for `startRegistration()` / `startAuthentication()` helpers.

### Configuration

Added to `Settings` in `src/core/config.py`:

| Setting | Default | Description |
|---------|---------|-------------|
| `webauthn_rp_id` | `"pguerrero.me"` | Relying Party ID (domain) |
| `webauthn_rp_name` | `"AI News"` | Human-readable name in browser prompts |
| `webauthn_origin` | `"https://pguerrero.me"` | Expected origin for verification |

### Security

- **Challenge expiry**: 5 minutes in-memory
- **sign_count**: Verified on each login (detects cloned authenticators)
- **User verification**: `"preferred"` (uses biometrics if available)
- **Attestation**: `"none"` (no manufacturer verification needed)
- **Resident key**: `"preferred"` (allows passkey syncing)
- **Rate limiting**: Per-endpoint, consistent with existing patterns

## Dependencies

| Package | Side | Purpose |
|---------|------|---------|
| `py_webauthn` | Backend | WebAuthn registration/authentication verification |
| `@simplewebauthn/browser` | Frontend | Browser credential API helpers |

## Migration Path

1. Add WebAuthn alongside existing OTP + legacy login
2. Legacy password login kept temporarily
3. Future PR: remove legacy login after team migrates to passkeys

## Files Changed

- `src/core/models.py` — add `WebAuthnCredential`
- `src/core/config.py` — add WebAuthn settings
- `src/api/routes/webauthn.py` — new route file (6 endpoints)
- `src/api/schemas.py` — new request/response schemas
- `src/api/app.py` — register webauthn router
- `alembic/versions/` — new migration
- `frontend/src/pages/Login.tsx` — add passkey login button
- `frontend/src/pages/Settings.tsx` — new settings page
- `frontend/src/hooks/use-auth.tsx` — add passkey auth methods
- `frontend/src/lib/webauthn.ts` — new WebAuthn browser helpers
- `frontend/package.json` — add `@simplewebauthn/browser`
- `pyproject.toml` — add `py_webauthn`
