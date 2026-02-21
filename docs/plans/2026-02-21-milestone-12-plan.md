# M12 Security Fixes — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix 4 security gaps found by M11: security headers, rate limiting on data endpoints, CORS tightening, request body size limits.

**Architecture:** All production changes in existing files — two new middleware classes in `app.py`, rate limit decorators on route files, CORS config edit. Tests in `tests/security/`.

**Tech Stack:** FastAPI middleware, slowapi Limiter, httpx AsyncClient for tests

---

### Task 1: Security Headers Middleware + Tests

**Files:**
- Modify: `src/api/app.py` (add SecurityHeadersMiddleware class + register it)
- Create: `tests/security/test_security_headers.py`

**Step 1: Write tests**

Create `tests/security/test_security_headers.py`:

```python
"""Security tests for response security headers."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

pytestmark = [pytest.mark.security, pytest.mark.asyncio(loop_scope="session")]


class TestSecurityHeaders:
    """Verify security headers are present on all API responses."""

    async def test_standard_security_headers_present(self, security_client: AsyncClient):
        """All standard security headers must be present on every response."""
        resp = await security_client.get("/health")
        assert resp.headers["X-Content-Type-Options"] == "nosniff"
        assert resp.headers["X-Frame-Options"] == "DENY"
        assert resp.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"
        assert resp.headers["X-XSS-Protection"] == "0"
        assert "camera=()" in resp.headers["Permissions-Policy"]

    async def test_hsts_only_in_non_debug(self, security_client: AsyncClient):
        """HSTS header must NOT be present when DEBUG=true (test env)."""
        resp = await security_client.get("/health")
        # Test env runs with DEBUG=true, so HSTS should be absent
        assert "Strict-Transport-Security" not in resp.headers

    async def test_headers_on_error_responses(self, security_client: AsyncClient):
        """Security headers must be present even on 4xx/5xx responses."""
        resp = await security_client.get("/api/items")  # 403 — no auth
        assert resp.status_code == 403
        assert resp.headers["X-Content-Type-Options"] == "nosniff"
        assert resp.headers["X-Frame-Options"] == "DENY"
```

**Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/security/test_security_headers.py -v --timeout=30`
Expected: FAIL — headers not present yet.

**Step 3: Implement SecurityHeadersMiddleware**

In `src/api/app.py`, add after the imports (before the `lifespan` function):

```python
class SecurityHeadersMiddleware:
    """ASGI middleware that adds standard security headers to every response."""

    _HEADERS: ClassVar[list[tuple[bytes, bytes]]] = [
        (b"x-content-type-options", b"nosniff"),
        (b"x-frame-options", b"DENY"),
        (b"referrer-policy", b"strict-origin-when-cross-origin"),
        (b"permissions-policy", b"camera=(), microphone=(), geolocation=()"),
        (b"x-xss-protection", b"0"),
    ]

    def __init__(self, app: ASGIApplication) -> None:
        self.app = app

    async def __call__(self, scope: dict, receive: object, send: object) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        is_debug = get_settings().debug

        async def _send_with_headers(message: dict) -> None:
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                headers.extend(self._HEADERS)
                if not is_debug:
                    headers.append(
                        (b"strict-transport-security", b"max-age=31536000; includeSubDomains")
                    )
                message["headers"] = headers
            await send(message)

        await self.app(scope, receive, _send_with_headers)
```

Also add these imports at the top of `app.py`:

```python
from typing import ClassVar

# Type alias for ASGI
type ASGIApplication = object
```

Register the middleware BEFORE the CORS middleware (so headers are added to all responses including CORS preflight):

```python
app.add_middleware(SecurityHeadersMiddleware)  # type: ignore[arg-type]
```

Add this line right after the `app = FastAPI(...)` block, BEFORE the CORS middleware.

**Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/security/test_security_headers.py -v --timeout=30`
Expected: 3 passed.

**Step 5: Lint check**

Run: `.venv/bin/ruff check src/api/app.py tests/security/test_security_headers.py && .venv/bin/ruff format --check src/api/app.py tests/security/test_security_headers.py`

**Step 6: Commit**

```bash
git add src/api/app.py tests/security/test_security_headers.py
git commit -m "feat: M12 security headers middleware — X-Frame-Options, nosniff, HSTS, Referrer-Policy [M12]"
```

---

### Task 2: CORS Tightening + Tests

**Files:**
- Modify: `src/api/app.py` (change CORS config)
- Create: `tests/security/test_cors.py`

**Step 1: Write tests**

Create `tests/security/test_cors.py`:

```python
"""Security tests for CORS configuration."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

pytestmark = [pytest.mark.security, pytest.mark.asyncio(loop_scope="session")]

_ORIGIN = "http://localhost:4200"


class TestCORS:
    """Verify CORS is properly restricted."""

    async def test_preflight_allowed_method(self, security_client: AsyncClient):
        """OPTIONS preflight for GET must succeed with correct CORS headers."""
        resp = await security_client.options(
            "/api/items",
            headers={
                "Origin": _ORIGIN,
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "Authorization",
            },
        )
        assert resp.status_code == 200
        assert resp.headers["Access-Control-Allow-Origin"] == _ORIGIN
        assert "GET" in resp.headers["Access-Control-Allow-Methods"]

    async def test_preflight_disallowed_method(self, security_client: AsyncClient):
        """OPTIONS preflight for DELETE must not include DELETE in allowed methods."""
        resp = await security_client.options(
            "/api/items",
            headers={
                "Origin": _ORIGIN,
                "Access-Control-Request-Method": "DELETE",
            },
        )
        allow_methods = resp.headers.get("Access-Control-Allow-Methods", "")
        assert "DELETE" not in allow_methods

    async def test_disallowed_origin_gets_no_cors(self, security_client: AsyncClient):
        """Request from unknown origin must not get CORS headers."""
        resp = await security_client.get(
            "/health",
            headers={"Origin": "https://evil.example.com"},
        )
        assert "Access-Control-Allow-Origin" not in resp.headers
```

**Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/security/test_cors.py -v --timeout=30`
Expected: At least `test_preflight_disallowed_method` FAILS (currently allows all methods).

**Step 3: Tighten CORS config**

In `src/api/app.py`, change the CORS middleware registration from:

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

To:

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)
```

**Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/security/test_cors.py -v --timeout=30`
Expected: 3 passed.

**Step 5: Lint check**

Run: `.venv/bin/ruff check src/api/app.py tests/security/test_cors.py && .venv/bin/ruff format --check src/api/app.py tests/security/test_cors.py`

**Step 6: Commit**

```bash
git add src/api/app.py tests/security/test_cors.py
git commit -m "feat: M12 tighten CORS — restrict methods to GET/POST/OPTIONS, headers to Auth/Content-Type [M12]"
```

---

### Task 3: Rate Limiting on Data Endpoints + Tests

**Files:**
- Modify: `src/api/routes/items.py` (add limiter + decorators to 3 routes)
- Modify: `src/api/routes/search.py` (add limiter + decorator)
- Modify: `src/api/routes/briefings.py` (add limiter + decorators to 2 routes)
- Modify: `src/api/routes/topics.py` (add limiter + decorator)
- Modify: `tests/security/conftest.py` (add new limiters to reset fixture)
- Modify: `tests/security/test_rate_limiting.py` (add 3 new tests)

**Context:** Each route file creates its own `Limiter` instance (same pattern as `auth.py` and `chat.py`). The conftest `_reset_rate_limiters` fixture must include the new limiters.

**Step 1: Add rate limiter to items.py**

In `src/api/routes/items.py`, add imports:

```python
from fastapi import APIRouter, Depends, Query, Request
from slowapi import Limiter
from slowapi.util import get_remote_address
```

Add limiter after `router`:

```python
limiter = Limiter(key_func=get_remote_address)
```

Add `request: Request` parameter and `@limiter.limit("30/minute")` decorator to all 3 routes:

- `list_items`: add `request: Request,` as first param, add `@limiter.limit("30/minute")` before `async def`
- `count_items`: same
- `list_today_items`: same

**Step 2: Add rate limiter to search.py**

In `src/api/routes/search.py`, add imports:

```python
from fastapi import APIRouter, Depends, Query, Request
from slowapi import Limiter
from slowapi.util import get_remote_address
```

Add limiter after `router`:

```python
limiter = Limiter(key_func=get_remote_address)
```

Add `request: Request,` as first param and `@limiter.limit("20/minute")` to `search_items`.

**Step 3: Add rate limiter to briefings.py**

In `src/api/routes/briefings.py`, add imports:

```python
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from slowapi import Limiter
from slowapi.util import get_remote_address
```

Add limiter after `router`:

```python
limiter = Limiter(key_func=get_remote_address)
```

Add `request: Request,` as first param and `@limiter.limit("30/minute")` to both `get_briefing` and `list_briefings`.

**Step 4: Add rate limiter to topics.py**

In `src/api/routes/topics.py`, add imports:

```python
from fastapi import APIRouter, Request
from slowapi import Limiter
from slowapi.util import get_remote_address
```

Add limiter after `router`:

```python
limiter = Limiter(key_func=get_remote_address)
```

Add `request: Request,` param and `@limiter.limit("30/minute")` to `get_topics`.

**Step 5: Update conftest rate limiter reset**

In `tests/security/conftest.py`, update `_reset_rate_limiters` to include the new limiters:

```python
@pytest.fixture(autouse=True)
def _reset_rate_limiters() -> None:
    """Reset all slowapi rate limiter storage so tests don't leak state."""
    from src.api.app import limiter as app_limiter
    from src.api.routes.auth import limiter as auth_limiter
    from src.api.routes.briefings import limiter as briefings_limiter
    from src.api.routes.chat import limiter as chat_limiter
    from src.api.routes.items import limiter as items_limiter
    from src.api.routes.search import limiter as search_limiter
    from src.api.routes.topics import limiter as topics_limiter

    all_limiters = (
        app_limiter, auth_limiter, briefings_limiter,
        chat_limiter, items_limiter, search_limiter, topics_limiter,
    )
    for lim in all_limiters:
        lim.reset()
    yield  # type: ignore[misc]
    for lim in all_limiters:
        lim.reset()
```

**Step 6: Add rate limit tests**

Append to `tests/security/test_rate_limiting.py`:

```python
class TestDataEndpointRateLimiting:
    """Verify rate limits on data endpoints added in M12."""

    async def test_search_rate_limit(
        self, security_client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        """21st search request within a minute must be rate-limited (429)."""
        for i in range(21):
            resp = await security_client.get(
                "/api/search", params={"q": f"test-{i}"}, headers=auth_headers
            )
            if resp.status_code == 429:
                assert i >= 20  # Should happen on 21st request (index 20)
                return

        pytest.fail("Expected 429 after 21 search requests, but all returned non-429")

    async def test_items_rate_limit(
        self, security_client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        """31st items request within a minute must be rate-limited (429)."""
        for i in range(31):
            resp = await security_client.get("/api/items", headers=auth_headers)
            if resp.status_code == 429:
                assert i >= 30  # Should happen on 31st request (index 30)
                return

        pytest.fail("Expected 429 after 31 items requests, but all returned non-429")

    async def test_topics_rate_limit(self, security_client: AsyncClient) -> None:
        """31st topics request within a minute must be rate-limited (429)."""
        for i in range(31):
            resp = await security_client.get("/api/topics")
            if resp.status_code == 429:
                assert i >= 30
                return

        pytest.fail("Expected 429 after 31 topics requests, but all returned non-429")
```

**Step 7: Run all rate limit tests**

Run: `.venv/bin/pytest tests/security/test_rate_limiting.py -v --timeout=30`
Expected: 6 passed (3 existing + 3 new).

**Step 8: Lint check**

Run: `.venv/bin/ruff check src/api/routes/items.py src/api/routes/search.py src/api/routes/briefings.py src/api/routes/topics.py tests/security/test_rate_limiting.py tests/security/conftest.py && .venv/bin/ruff format --check src/api/routes/items.py src/api/routes/search.py src/api/routes/briefings.py src/api/routes/topics.py tests/security/test_rate_limiting.py tests/security/conftest.py`

**Step 9: Commit**

```bash
git add src/api/routes/items.py src/api/routes/search.py src/api/routes/briefings.py src/api/routes/topics.py tests/security/conftest.py tests/security/test_rate_limiting.py
git commit -m "feat: M12 extend rate limiting — items 30/min, search 20/min, briefings 30/min, topics 30/min [M12]"
```

---

### Task 4: Request Body Size Limit + Tests

**Files:**
- Modify: `src/api/app.py` (add BodySizeLimitMiddleware)
- Create: `tests/security/test_body_size.py`

**Step 1: Write tests**

Create `tests/security/test_body_size.py`:

```python
"""Security tests for request body size limits."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

pytestmark = [pytest.mark.security, pytest.mark.asyncio(loop_scope="session")]

_MAX_BODY = 1_048_576  # 1MB


class TestBodySizeLimit:
    """Verify oversized request bodies are rejected."""

    async def test_oversized_body_rejected(self, security_client: AsyncClient):
        """Body > 1MB must be rejected with 413."""
        oversized = "A" * (_MAX_BODY + 1)
        resp = await security_client.post(
            "/api/auth/token",
            content=f'{{"password": "{oversized}"}}'.encode(),
            headers={"Content-Type": "application/json"},
        )
        assert resp.status_code == 413

    async def test_normal_body_accepted(self, security_client: AsyncClient):
        """Normal-sized body must be accepted (not blocked by size limit)."""
        resp = await security_client.post(
            "/api/auth/token", json={"password": "test-password"}
        )
        # Should get 401 (wrong password), not 413
        assert resp.status_code == 401

    async def test_boundary_body_accepted(self, security_client: AsyncClient):
        """Body exactly at 1MB limit must be accepted."""
        # Create a body that's exactly 1MB (including JSON structure)
        padding = "A" * (_MAX_BODY - 20)  # leave room for JSON wrapper
        resp = await security_client.post(
            "/api/auth/token",
            content=f'{{"password": "{padding}"}}'.encode(),
            headers={"Content-Type": "application/json"},
        )
        # Should be 401 (wrong password), not 413
        assert resp.status_code == 401
```

**Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/security/test_body_size.py -v --timeout=30`
Expected: `test_oversized_body_rejected` FAILS (no size limit yet).

**Step 3: Implement BodySizeLimitMiddleware**

In `src/api/app.py`, add after `SecurityHeadersMiddleware`:

```python
_MAX_BODY_SIZE = 1_048_576  # 1MB


class BodySizeLimitMiddleware:
    """ASGI middleware that rejects request bodies larger than _MAX_BODY_SIZE."""

    def __init__(self, app: ASGIApplication) -> None:
        self.app = app

    async def __call__(self, scope: dict, receive: object, send: object) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # Check Content-Length header if present
        headers = dict(scope.get("headers", []))
        content_length = headers.get(b"content-length")
        if content_length and int(content_length) > _MAX_BODY_SIZE:
            response = JSONResponse(
                status_code=413,
                content={"detail": "Request body too large"},
            )
            await response(scope, receive, send)
            return

        await self.app(scope, receive, send)
```

Register it after `SecurityHeadersMiddleware` (before CORS):

```python
app.add_middleware(BodySizeLimitMiddleware)  # type: ignore[arg-type]
```

**Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/security/test_body_size.py -v --timeout=30`
Expected: 3 passed.

**Step 5: Lint check**

Run: `.venv/bin/ruff check src/api/app.py tests/security/test_body_size.py && .venv/bin/ruff format --check src/api/app.py tests/security/test_body_size.py`

**Step 6: Commit**

```bash
git add src/api/app.py tests/security/test_body_size.py
git commit -m "feat: M12 request body size limit — reject >1MB with 413 [M12]"
```

---

### Task 5: Final Verification + Milestone Complete

**Files:**
- Modify: `docs/plans/2026-02-21-milestone-12-design.md` (mark success criteria)

**Step 1: Run ALL security tests**

Run: `.venv/bin/pytest tests/security/ -v -m security --timeout=30`
Expected: 49 passed (37 from M11 + 3 headers + 3 CORS + 3 rate limit + 3 body size).

**Step 2: Run unit tests (regression check)**

Run: `.venv/bin/pytest tests/unit/ -x --timeout=30`
Expected: 702 passed.

**Step 3: Run integration tests (regression check)**

Run: `.venv/bin/pytest tests/integration/ -m integration --timeout=60`
Expected: 28 passed.

**Step 4: Lint + format check**

Run: `.venv/bin/ruff check . && .venv/bin/ruff format --check .`
Expected: All clean.

**Step 5: Update design doc success criteria**

Change all `- [ ]` to `- [x]` in `docs/plans/2026-02-21-milestone-12-design.md`. Update test count to match actual.

**Step 6: Commit**

```bash
git add docs/plans/2026-02-21-milestone-12-design.md
git commit -m "feat: M12 complete — security fixes verified, all tests passing [M12]"
```

---

## Verification Summary

1. `pytest tests/security/ -v -m security --timeout=30` — all pass (~49 total)
2. `pytest tests/unit/ -x --timeout=30` — 702 pass (no regressions)
3. `pytest tests/integration/ -m integration --timeout=60` — 28 pass (no regressions)
4. `ruff check . && ruff format --check .` — clean
