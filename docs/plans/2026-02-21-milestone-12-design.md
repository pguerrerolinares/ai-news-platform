# Milestone 12 — Security Fixes

## Goal

Fix the 4 security gaps documented by M11 Security Hardening: add security headers middleware,
extend rate limiting to data endpoints, tighten CORS, and add request body size limits.
Production code changes + tests.

## Current State (from M11 findings)

| Gap | Current | Risk |
|-----|---------|------|
| Security headers | Only `X-Correlation-ID` | High — no XSS, clickjacking, MIME sniffing protection |
| Rate limiting | Auth (5/min), Chat (10/min) only | High — search/items/briefings have no DoS protection |
| CORS | `allow_methods/headers = "*"` | Medium — overly permissive |
| Body size | No limit | High — potential OOM with large payloads |

## Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Security headers location | ASGI middleware in `app.py` | Applies to all responses, single place |
| CSP header | Skip | API-only backend, no HTML served — CSP is a frontend concern |
| HSTS | Only when `DEBUG=false` | Don't break local dev with HTTPS enforcement |
| Headers configurable? | No — hardcoded | YAGNI, standard values that rarely change |
| CORS methods | `["GET", "POST", "OPTIONS"]` | Only methods the API uses |
| CORS headers | `["Authorization", "Content-Type"]` | Only headers the frontend sends |
| Rate limits for data endpoints | 30/min items+briefings+topics, 20/min search | Search is heavier; all require auth except topics |
| Body size limit | 1MB | Generous for JSON payloads, prevents abuse |
| Body limit implementation | ASGI middleware checking Content-Length | Simple, no dependency needed |

## Components

### 1. Security Headers Middleware (`src/api/app.py`)

New ASGI middleware class added before CORS:

| Header | Value | Purpose |
|--------|-------|---------|
| `X-Content-Type-Options` | `nosniff` | Prevent MIME sniffing |
| `X-Frame-Options` | `DENY` | Prevent clickjacking |
| `Strict-Transport-Security` | `max-age=31536000; includeSubDomains` | Enforce HTTPS (non-debug only) |
| `Referrer-Policy` | `strict-origin-when-cross-origin` | Control referrer leakage |
| `Permissions-Policy` | `camera=(), microphone=(), geolocation=()` | Disable unused browser features |
| `X-XSS-Protection` | `0` | Modern recommendation — CSP replaces it |

### 2. CORS Tightening (`src/api/app.py`)

Change existing CORSMiddleware config:
- `allow_methods=["GET", "POST", "OPTIONS"]` (was `"*"`)
- `allow_headers=["Authorization", "Content-Type"]` (was `"*"`)
- `allow_origins` stays as `settings.cors_origins_list` (already correct)
- `allow_credentials` stays `True`

### 3. Rate Limiting Extension

Add `@limiter.limit()` to unprotected routes:

| Route | Limit | File |
|-------|-------|------|
| `GET /api/items` | 30/minute | `src/api/routes/items.py` |
| `GET /api/items/count` | 30/minute | `src/api/routes/items.py` |
| `GET /api/items/today` | 30/minute | `src/api/routes/items.py` |
| `GET /api/search` | 20/minute | `src/api/routes/search.py` |
| `GET /api/briefings/{date}` | 30/minute | `src/api/routes/briefings.py` |
| `GET /api/briefings` | 30/minute | `src/api/routes/briefings.py` |
| `GET /api/topics` | 30/minute | `src/api/routes/topics.py` |

### 4. Request Body Size Limit (`src/api/app.py`)

New ASGI middleware:
- Check `Content-Length` header, reject if > 1MB (1_048_576 bytes)
- Return 413 with JSON body `{"detail": "Request body too large"}`
- For requests without `Content-Length`, let them through (chunked transfers are rare for this API)

## Test Plan (~12 new tests)

| File | Tests | What |
|------|-------|------|
| `tests/security/test_security_headers.py` | 3 | Headers present, HSTS only non-debug, correct values |
| `tests/security/test_cors.py` | 3 | Allowed methods/headers work, disallowed rejected, preflight OK |
| `tests/security/test_rate_limiting.py` | 3 | Search/items/briefings limits enforced (extend existing) |
| `tests/security/test_body_size.py` | 3 | >1MB rejected 413, normal body accepted, boundary test |

## Success Criteria

- [ ] All security headers present on API responses
- [ ] CORS rejects disallowed methods/headers
- [ ] Rate limits enforced on all data endpoints
- [ ] Request body > 1MB returns 413
- [ ] All new tests pass
- [ ] No regressions (unit: 702, integration: 28, security: 37+12)
- [ ] `ruff check .` clean

## Files to Modify

| File | Change |
|------|--------|
| `src/api/app.py` | Add SecurityHeadersMiddleware, BodySizeLimitMiddleware, tighten CORS |
| `src/api/routes/items.py` | Add `@limiter.limit("30/minute")` to 3 routes |
| `src/api/routes/search.py` | Add `@limiter.limit("20/minute")` to 1 route |
| `src/api/routes/briefings.py` | Add `@limiter.limit("30/minute")` to 2 routes |
| `src/api/routes/topics.py` | Add `@limiter.limit("30/minute")` to 1 route |
| `tests/security/test_security_headers.py` | New — 3 tests |
| `tests/security/test_cors.py` | New — 3 tests |
| `tests/security/test_rate_limiting.py` | Extend — 3 tests |
| `tests/security/test_body_size.py` | New — 3 tests |
