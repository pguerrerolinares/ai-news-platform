# Design: Public Access with Guest Tokens + Legacy Auth Removal

> Date: 2026-03-04
> Status: Approved

## Problem

The platform requires authentication for all endpoints, blocking public access.
Goal: open the platform to the general public while protecting resource-intensive
features (LLM chat) behind auth.

## Design

### Guest Token Mechanism

- `POST /api/auth/guest` — no auth required. Returns JWT with `role: "guest"`,
  `sub: "guest:{uuid4}"`, TTL 24h. No refresh token.
- Frontend requests a guest token on first load (no existing session).
- Guest tokens are read-only by design (all public endpoints are GET).

### Auth Dependencies

- **`require_auth_or_guest`** (new) — accepts both `guest` and authenticated tokens.
  Used on public endpoints: items, search, briefings, stats.
- **`require_auth`** (unchanged) — rejects guest tokens. Used on chat, settings,
  OTP, webauthn.

### Rate Limiting (differentiated)

- Guest: 30 req/min (keyed by token `jti`)
- Authenticated: 120 req/min (keyed by user `sub`)
- Custom slowapi key function extracts identifier from JWT.

### Route Access Tiers

| Tier | Routes | Auth Dependency |
|------|--------|-----------------|
| Public | `/`, `/top`, `/search`, `/timeline` | `require_auth_or_guest` |
| Private | `/chat`, `/settings` | `require_auth` |
| Auth | `/login` | None (unauthenticated page) |

### Frontend UX Changes

- `RequireAuth` wrapper removed from `Layout` in `App.tsx`.
- `RequireAuth` applied only to `/chat` and `/settings` routes.
- Nav bar: "Sign in" button when unauthenticated, avatar/logout when authenticated.
- `/chat` redirects to `/login` with `state.from = /chat` if not authenticated.
- Guest token acquired automatically via `use-auth` hook on first load.

### Legacy Auth Removal

- Delete `POST /api/auth/token` (shared password endpoint) from `routes/auth.py`.
- Remove `shared_password` from Settings config.
- Remove `loginLegacy` from frontend `use-auth.tsx`.
- Remove legacy step from `Login.tsx`.

### Nginx Security (already done)

- Scanner paths (`wp-admin`, `xmlrpc.php`, etc.) return 444 (connection drop).

### Endpoints Changed

| File | Change |
|------|--------|
| `auth.py` | +`create_guest_token()`, +`require_auth_or_guest()` |
| `routes/auth.py` | +`POST /api/auth/guest`, -`POST /api/auth/token` |
| `routes/items.py` (8) | `require_auth` -> `require_auth_or_guest` |
| `routes/search.py` (1) | `require_auth` -> `require_auth_or_guest` |
| `routes/briefings.py` (2) | `require_auth` -> `require_auth_or_guest` |
| `routes/stats.py` (8) | `require_auth` -> `require_auth_or_guest` |
| `routes/chat.py` (1) | Unchanged (`require_auth`) |
| `routes/otp.py` | Unchanged |
| `routes/webauthn.py` | Unchanged |
| `frontend/src/App.tsx` | Route restructure |
| `frontend/src/hooks/use-auth.tsx` | +guest token, -loginLegacy |
| `frontend/src/pages/Login.tsx` | -legacy step |
| `frontend/src/components/layout.tsx` | +Sign in / logout in nav |
