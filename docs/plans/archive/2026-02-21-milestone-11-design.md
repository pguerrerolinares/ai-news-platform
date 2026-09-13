# Milestone 11 — Security Hardening (Tests Only)

## Goal

Validate the "secure by default" principle holds under adversarial inputs. Penetration-style
tests that probe JWT manipulation, SSRF bypass, SQL injection, rate limit evasion, input
fuzzing, and auth boundary violations. Tests only — no production code changes. Gaps found
become documented findings for a future milestone.

## Current Security Posture

**Strengths (already implemented):**
- JWT auth with HS256, proper validation, 401 on any JWTError
- SQL injection prevention via SQLAlchemy ORM (parameterized queries)
- SSRF protection in `_is_safe_url()` — blocks private/loopback/link-local/reserved IPs
- Timing-safe password comparison (`hmac.compare_digest`)
- Input validation via Pydantic on all endpoints
- Rate limiting on auth (5/min) and chat (10/min) via slowapi
- Structured logging with correlation IDs
- Bandit scanning via ruff `-S` rules

**Known gaps (test, don't fix):**
- Missing security headers (CSP, X-Frame-Options, HSTS)
- No rate limiting on search/data endpoints
- CORS permissive (`allow_methods/headers = "*"`)
- No request body size limits
- Default JWT secret only validated at startup in non-debug mode

## Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Directory | `tests/security/` | Separate from unit/integration — different purpose |
| Marker | `@pytest.mark.security` | Run independently: `pytest -m security` |
| DB for SQL injection | Real PostgreSQL (reuse integration fixtures) | Proves injections fail at DB level, not just validation |
| DB for everything else | No DB needed | JWT, SSRF, rate limit, fuzzing test HTTP/auth layer only |
| Client | `AsyncClient` + `ASGITransport` | Same pattern as integration tests, no network needed |
| SSRF tests | Direct function calls to `_is_safe_url()` | Tests the actual protection function, not HTTP routes |
| Rate limit tests | Need slowapi test client setup | Must clear limiter state between tests |
| Timeout | 30s per test | Same as unit tests — these are fast |
| New dependencies | None | All infra already available |

## Success Criteria

- [x] All 37 security tests pass (`pytest tests/security/ -m security --timeout=30`)
- [x] No unit test regressions (702 still pass)
- [x] No integration test regressions (28 still pass)
- [x] `ruff check .` clean
- [x] CI pipeline runs security tests after integration tests
- [x] Every attack vector produces the expected defensive response (not a 500)

---

## Components

### 1. JWT Manipulation (`tests/security/test_jwt_manipulation.py`) — 6 tests

| Test | Attack | Expected |
|---|---|---|
| `test_algorithm_none` | Token with `"alg": "none"` | 401 rejected |
| `test_algorithm_confusion` | Sign with HS384 instead of HS256 | 401 rejected |
| `test_forged_signature` | Valid payload, random signature | 401 rejected |
| `test_expired_token` | Token with `exp` in the past | 401 rejected |
| `test_missing_sub_claim` | Valid signature, no `sub` in payload | 401 rejected |
| `test_tampered_payload` | Change `sub` after signing | 401 rejected |

### 2. SSRF Bypass (`tests/security/test_ssrf_bypass.py`) — 7 tests

Tests `_is_safe_url()` directly (the SSRF gate in `credibility.py`):

| Test | Attack | Expected |
|---|---|---|
| `test_ipv4_mapped_ipv6` | `http://[::ffff:127.0.0.1]/` | Blocked |
| `test_ipv6_loopback` | `http://[::1]/` | Blocked |
| `test_decimal_ip_encoding` | `http://2130706433/` (= 127.0.0.1) | Blocked |
| `test_octal_ip_encoding` | `http://0177.0.0.1/` | Blocked |
| `test_url_with_credentials` | `http://user:pass@127.0.0.1/` | Blocked |
| `test_file_scheme` | `file:///etc/passwd` | Blocked |
| `test_dns_rebinding` | Domain resolves to 127.0.0.1 (mocked) | Blocked |

### 3. SQL Injection (`tests/security/test_sql_injection.py`) — 5 tests

Against real PostgreSQL to prove SQLAlchemy parameterization holds:

| Test | Attack | Expected |
|---|---|---|
| `test_classic_drop_table` | `q="'; DROP TABLE news_items--"` | 200 with 0 results, table intact |
| `test_union_select` | `q="' UNION SELECT * FROM--"` | 200 or 422, no data leak |
| `test_filter_param_injection` | `topic="modelos' OR '1'='1"` | 0 results (exact match) |
| `test_null_byte_in_query` | `q="test\x00; DROP"` | 200 or 422, no crash |
| `test_oversized_query_string` | `q="A" * 10000` | 422 or 200, no crash |

### 4. Rate Limiting (`tests/security/test_rate_limiting.py`) — 3 tests

| Test | Attack | Expected |
|---|---|---|
| `test_auth_brute_force` | 6 rapid POST `/api/auth/token` | 6th returns 429 |
| `test_chat_spam` | 11 rapid POST `/api/chat` | 11th returns 429 |
| `test_rate_limit_headers` | After 429 response | `Retry-After` header present |

### 5. Input Fuzzing (`tests/security/test_input_fuzzing.py`) — 6 tests

| Test | Attack | Expected |
|---|---|---|
| `test_oversized_json_body` | 1MB `{"password": "A"*1000000}` | 413 or 422, no OOM |
| `test_unicode_edge_cases` | Search with BOM, ZWJ, RTL chars | 200 or 422, no crash |
| `test_null_bytes_in_headers` | `Authorization: Bearer \x00token` | 401 or 403, no crash |
| `test_header_injection` | `\r\n` in header value | No header splitting |
| `test_extremely_long_params` | `?topic=` + `"A"*50000` | 422 or truncated, no crash |
| `test_malformed_content_type` | `Content-Type: application/json; charset=evil` | Handled gracefully |

### 6. Auth Boundary (`tests/security/test_auth_boundary.py`) — 4 tests

| Test | Attack | Expected |
|---|---|---|
| `test_all_protected_endpoints_require_auth` | Hit every protected route without auth | All return 403 |
| `test_empty_bearer_token` | `Authorization: Bearer ` | 401 or 403 |
| `test_non_jwt_bearer` | `Authorization: Bearer not.a.jwt` | 401 |
| `test_wrong_auth_scheme` | `Authorization: Basic dXNlcjpwYXNz` | 403 |

---

## File Map

| File | Tests | What it covers |
|---|---|---|
| `tests/security/conftest.py` | — | Client fixture, auth helpers, rate limiter reset |
| `tests/security/test_jwt_manipulation.py` | 6 | JWT algorithm confusion, forgery, tampering |
| `tests/security/test_ssrf_bypass.py` | 7 | SSRF bypass via IP encoding, DNS, schemes |
| `tests/security/test_sql_injection.py` | 5 | SQL injection in search/filter params |
| `tests/security/test_rate_limiting.py` | 3 | Rate limit enforcement and headers |
| `tests/security/test_input_fuzzing.py` | 6 | Oversized payloads, unicode, null bytes, headers |
| `tests/security/test_auth_boundary.py` | 4 | Auth enforcement on all protected routes |
| **Total** | **31** | |

## Infrastructure

### `tests/security/conftest.py`

Fixtures:
- **`security_client`** — `AsyncClient` with `ASGITransport`, mock DB session (for non-SQL tests)
- **`db_client`** — `AsyncClient` with real PostgreSQL session (for SQL injection tests only)
- **`valid_token`** — Helper to create a valid JWT for comparison
- **`auth_headers`** — Valid `Authorization: Bearer <token>` dict
- **Rate limiter reset** — Clear slowapi state between tests

### CI Integration

Extend `.github/workflows/ci.yml`:
```yaml
- name: Run security tests
  env:
    DATABASE_URL: postgresql+asyncpg://ainews:testpassword@localhost:5432/ainews_test
    DATABASE_URL_SYNC: postgresql://ainews:testpassword@localhost:5432/ainews_test
    TESTING: "1"
  run: |
    pytest tests/security/ -v -m security --timeout=30
```

## Verification

1. `pytest tests/security/ -m security --timeout=30` — all pass
2. `pytest tests/unit/ -x --timeout=30` — no regressions (702 still pass)
3. `pytest tests/integration/ -m integration --timeout=60` — no regressions (28 still pass)
4. `ruff check . && ruff format --check .`
5. CI green with unit + integration + security steps

---

## Next Milestones (Outline)

### M12 — Security Fixes

Fix gaps documented by M11 findings: add security headers middleware, extend rate limiting
to search/data endpoints, tighten CORS, add request body size limits.
