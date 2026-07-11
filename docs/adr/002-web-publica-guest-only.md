# ADR-002: Web pública guest-only — descontinuación del auth de usuarios (OTP, WebAuthn, admin)

**Date**: 2026-07-11
**Status**: Accepted
**Track**: C (high risk — destructive DB migration, security-relevant)

## Context

Following the 2026-07-11 auth audit, Paul decided the web frontend should be **public, guest-only**: no login, no registered users, no admin. The registered-user auth stack (OTP codes emailed via Resend, WebAuthn/passkeys, JWT access + refresh token rotation, `require_admin`) added significant surface — extra tables, extra endpoints, extra scheduler job, extra frontend pages — for a platform with no actual multi-user need. Guest tokens (`POST /api/auth/guest`, `require_auth_or_guest`) already covered the platform's only real requirement: read-only public access with rate limiting.

`POST /api/chat` (RAG Q&A) is the one endpoint that still requires full auth (`require_auth`, which rejects guests). With no user-token issuer left, it is currently unreachable from the web. This is intentional, not an oversight: chat runs LLM calls, and leaving it open to any guest would mean unmetered LLM spend from anonymous traffic. The endpoint stays wired to `require_auth` so it re-activates automatically if a token issuer is reintroduced later (e.g. the MCP server issuing scoped tokens), rather than needing a security review to re-gate it at that point.

## Decision

- Remove passwordless OTP login (`src/api/otp.py`, `POST /api/auth/otp/request`, `POST /api/auth/otp/verify`, Resend API integration, daily OTP-cleanup scheduler job).
- Remove WebAuthn/passkeys (`src/api/webauthn.py`, `POST/GET/DELETE /api/auth/webauthn/*`).
- Remove access/refresh token rotation (`POST /api/auth/refresh`) and `GET /api/auth/me`.
- Remove the registered-user and admin-user model (`require_admin`, `User` ORM model, admin promotion via `ADMIN_EMAIL`).
- Remove the corresponding frontend surface: Login and Settings pages, the Chat page (chat is not reachable without a full-auth token), `use-auth` hook, `webauthn.ts` client.
- Drop `users`, `otp_codes`, `webauthn_credentials` tables in **migration 018** (`alembic/versions/018_drop_user_auth_tables.py`).
- Keep untouched: guest tokens, `require_auth_or_guest`, rate limiting (guest by `jti`, user by `sub`, fallback IP), and `POST /api/chat` wired to `require_auth`.

## Consequences

- **Chat is inaccessible from the public web.** This is accepted, not a bug: it removes an open LLM-spend vector. If a legitimate need for authenticated chat resurfaces (e.g. via MCP issuing user tokens), `require_auth` already gates it correctly — no code change needed to re-enable, only a token issuer.
- **Migration 018 is destructive.** `downgrade()` recreates the `users` / `otp_codes` / `webauthn_credentials` schema (accumulated from migrations 005, 006, 009, 016) with its indexes and constraints, but does **not** restore data — these are login credentials/codes for a discontinued auth system, not business data, so data loss on downgrade is acceptable. Teams that want a safety net can run a manual dump before deploying this migration:
  ```
  pg_dump -t users -t otp_codes -t webauthn_credentials <db> > pre-018-auth-dump.sql
  ```
- `ADMIN_EMAIL`, `RESEND_*`, `WEBAUTHN_*`, and OTP-related env vars are no longer read by the app; they can be removed from deployment secrets.
- Alembic history is now 18 versions; `alembic check`/`upgrade head` in CI covers the drop.

## Alternatives considered

- **Keep OTP/WebAuthn dormant (feature-flagged) instead of deleting.** Rejected: dead code with security surface (dependencies, endpoints, DB tables) that nobody maintains or tests is a liability, not an option held in reserve. YAGNI — if user auth is needed again, it can be rebuilt against then-current requirements (which may differ, e.g. a different identity provider).
- **Drop tables without a migration (manual SQL in production).** Rejected: violates reproducibility — schema state must be derivable from `alembic upgrade head` alone.
