# M11 Security Hardening — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 31 penetration-style security tests that validate existing defenses hold under adversarial inputs.

**Architecture:** New `tests/security/` directory with `@pytest.mark.security` marker. Tests use `AsyncClient` + `ASGITransport` against the FastAPI app. SQL injection tests reuse the integration DB fixtures; all other tests mock the DB session. CI adds a security test step after integration tests.

**Tech Stack:** pytest, httpx AsyncClient, python-jose (JWT crafting), slowapi (rate limiting)

---

### Task 1: Infrastructure — conftest + marker + CI

**Files:**
- Create: `tests/security/__init__.py`
- Create: `tests/security/conftest.py`
- Modify: `pyproject.toml` (add `security` marker)
- Modify: `.github/workflows/ci.yml` (add security test step)

**Step 1: Create conftest with fixtures**

```python
"""Security test fixtures — adversarial testing infrastructure."""

from __future__ import annotations

import os
from collections.abc import AsyncGenerator
from typing import Any
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

# ---------------------------------------------------------------------------
# Environment — must run BEFORE any application import that calls get_settings()
# ---------------------------------------------------------------------------
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://ainews:ainews@localhost:5432/ainews_test",
)
os.environ.setdefault(
    "DATABASE_URL_SYNC",
    "postgresql://ainews:ainews@localhost:5432/ainews_test",
)
os.environ["TESTING"] = "1"
os.environ["DEBUG"] = "true"
os.environ["TELEGRAM_BOT_TOKEN"] = ""
os.environ["TELEGRAM_CHAT_ID"] = ""
os.environ["TELEGRAM_ALERTS_ENABLED"] = "false"

from src.core.config import get_settings  # noqa: E402

get_settings.cache_clear()


# ---------------------------------------------------------------------------
# Lightweight client (no real DB — mocked session)
# ---------------------------------------------------------------------------
@pytest_asyncio.fixture(loop_scope="session")
async def security_client() -> AsyncGenerator[AsyncClient, None]:
    """ASGI client with a mocked DB session for non-DB security tests."""
    from src.api.app import app
    from src.core.database import get_session

    mock_session = AsyncMock(spec=AsyncSession)

    async def _override() -> AsyncGenerator[AsyncSession, None]:
        yield mock_session

    app.dependency_overrides[get_session] = _override

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac

    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------
@pytest.fixture()
def valid_token() -> str:
    """Create a valid JWT token for comparison/baseline tests."""
    from src.api.auth import create_access_token

    return create_access_token(subject="test-user")


@pytest.fixture()
def auth_headers(valid_token: str) -> dict[str, str]:
    """Valid Authorization headers."""
    return {"Authorization": f"Bearer {valid_token}"}
```

**Step 2: Create empty `__init__.py`**

Create `tests/security/__init__.py` as an empty file.

**Step 3: Add `security` marker to `pyproject.toml`**

In `pyproject.toml`, find the `markers` list (line 107) and add:

```toml
markers = [
    "integration: marks tests that require external services (deselect with '-m \"not integration\"')",
    "e2e: marks Playwright browser tests (deselect with '-m \"not e2e\"')",
    "security: marks penetration-style security tests (deselect with '-m \"not security\"')",
]
```

**Step 4: Add CI step to `.github/workflows/ci.yml`**

After the integration tests step, add:

```yaml
      - name: Run security tests
        env:
          DATABASE_URL: postgresql+asyncpg://ainews:testpassword@localhost:5432/ainews_test
          DATABASE_URL_SYNC: postgresql://ainews:testpassword@localhost:5432/ainews_test
          TESTING: "1"
        run: |
          pytest tests/security/ -v -m security --timeout=30
```

**Step 5: Verify lint passes**

Run: `ruff check tests/security/ && ruff format --check tests/security/`
Expected: All checks passed.

**Step 6: Commit**

```bash
git add tests/security/ pyproject.toml .github/workflows/ci.yml
git commit -m "test: M11 security test infrastructure — conftest, marker, CI [M11]"
```

---

### Task 2: JWT Manipulation Tests (6 tests)

**Files:**
- Create: `tests/security/test_jwt_manipulation.py`

**Context:**
- Auth module: `src/api/auth.py` — uses `jose.jwt.decode()` with `algorithms=[settings.jwt_algorithm]` (HS256)
- Settings: `src/core/config.py:36-37` — `jwt_secret = "change-me-in-production"`, `jwt_algorithm = "HS256"`
- All protected routes return 401 on JWTError, 403 if no Authorization header at all

**Step 1: Write all 6 tests**

```python
"""Security tests for JWT manipulation attacks."""

from __future__ import annotations

import base64
import json
import time

import pytest
from httpx import AsyncClient
from jose import jwt

from src.core.config import get_settings

pytestmark = [pytest.mark.security, pytest.mark.asyncio(loop_scope="session")]

# Target endpoint — any protected route works
_PROTECTED = "/api/items"


class TestJWTManipulation:
    """Adversarial JWT attacks that must all be rejected with 401."""

    async def test_algorithm_none(self, security_client: AsyncClient):
        """Token with alg=none must be rejected (algorithm confusion attack)."""
        header = base64.urlsafe_b64encode(json.dumps({"alg": "none", "typ": "JWT"}).encode()).decode().rstrip("=")
        payload = base64.urlsafe_b64encode(
            json.dumps({"sub": "attacker", "exp": int(time.time()) + 3600}).encode()
        ).decode().rstrip("=")
        fake_token = f"{header}.{payload}."

        resp = await security_client.get(_PROTECTED, headers={"Authorization": f"Bearer {fake_token}"})
        assert resp.status_code == 401

    async def test_algorithm_confusion_hs384(self, security_client: AsyncClient):
        """Token signed with HS384 when server expects HS256 must be rejected."""
        settings = get_settings()
        token = jwt.encode(
            {"sub": "attacker", "exp": int(time.time()) + 3600},
            settings.jwt_secret,
            algorithm="HS384",
        )

        resp = await security_client.get(_PROTECTED, headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 401

    async def test_forged_signature(self, security_client: AsyncClient):
        """Valid payload with a forged (wrong-secret) signature must be rejected."""
        token = jwt.encode(
            {"sub": "attacker", "exp": int(time.time()) + 3600},
            "wrong-secret-key",
            algorithm="HS256",
        )

        resp = await security_client.get(_PROTECTED, headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 401

    async def test_expired_token(self, security_client: AsyncClient):
        """Expired token must be rejected."""
        settings = get_settings()
        token = jwt.encode(
            {"sub": "user", "exp": int(time.time()) - 3600},
            settings.jwt_secret,
            algorithm="HS256",
        )

        resp = await security_client.get(_PROTECTED, headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 401

    async def test_missing_sub_claim(self, security_client: AsyncClient):
        """Token without 'sub' claim must be rejected."""
        settings = get_settings()
        token = jwt.encode(
            {"exp": int(time.time()) + 3600, "role": "admin"},
            settings.jwt_secret,
            algorithm="HS256",
        )

        resp = await security_client.get(_PROTECTED, headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 401

    async def test_tampered_payload(self, security_client: AsyncClient):
        """Token with payload modified after signing must be rejected."""
        settings = get_settings()
        token = jwt.encode(
            {"sub": "user", "exp": int(time.time()) + 3600},
            settings.jwt_secret,
            algorithm="HS256",
        )
        # Tamper: replace payload section with a different one
        parts = token.split(".")
        tampered_payload = base64.urlsafe_b64encode(
            json.dumps({"sub": "admin", "exp": int(time.time()) + 3600}).encode()
        ).decode().rstrip("=")
        tampered_token = f"{parts[0]}.{tampered_payload}.{parts[2]}"

        resp = await security_client.get(
            _PROTECTED, headers={"Authorization": f"Bearer {tampered_token}"}
        )
        assert resp.status_code == 401
```

**Step 2: Run tests**

Run: `pytest tests/security/test_jwt_manipulation.py -v --timeout=30`
Expected: 6 passed.

**Step 3: Lint check**

Run: `ruff check tests/security/test_jwt_manipulation.py && ruff format --check tests/security/test_jwt_manipulation.py`
Expected: Clean.

**Step 4: Commit**

```bash
git add tests/security/test_jwt_manipulation.py
git commit -m "test: M11 JWT manipulation tests — algorithm confusion, forgery, tampering [M11]"
```

---

### Task 3: SSRF Bypass Tests (7 tests)

**Files:**
- Create: `tests/security/test_ssrf_bypass.py`

**Context:**
- SSRF protection: `src/validators/credibility.py:239-268` — `_is_safe_url(url)` function
- Blocks: private IPs, loopback, link-local, reserved, non-http(s) schemes
- Uses DNS resolution via `asyncio.get_event_loop().getaddrinfo()`
- Existing unit tests cover basic cases; these test bypass techniques

**Step 1: Write all 7 tests**

```python
"""Security tests for SSRF bypass attempts against _is_safe_url()."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from src.validators.credibility import _is_safe_url

pytestmark = [pytest.mark.security, pytest.mark.asyncio(loop_scope="session")]


class TestSSRFBypass:
    """Adversarial SSRF bypass techniques that must all be blocked."""

    async def test_ipv4_mapped_ipv6(self):
        """IPv4-mapped IPv6 address (::ffff:127.0.0.1) must be blocked."""
        assert await _is_safe_url("http://[::ffff:127.0.0.1]/secret") is False

    async def test_ipv6_loopback(self):
        """IPv6 loopback (::1) must be blocked."""
        assert await _is_safe_url("http://[::1]/secret") is False

    async def test_decimal_ip_encoding(self):
        """Decimal IP encoding (2130706433 = 127.0.0.1) must be blocked."""
        # Most systems resolve http://2130706433 to 127.0.0.1
        # Mock DNS to simulate this resolution
        mock_addr_info = [(None, None, None, None, ("127.0.0.1", 0))]
        with patch("src.validators.credibility.asyncio") as mock_asyncio:
            mock_loop = AsyncMock()
            mock_loop.getaddrinfo.return_value = mock_addr_info
            mock_asyncio.get_event_loop.return_value = mock_loop
            assert await _is_safe_url("http://2130706433/secret") is False

    async def test_octal_ip_encoding(self):
        """Octal IP encoding (0177.0.0.1 = 127.0.0.1) must be blocked."""
        mock_addr_info = [(None, None, None, None, ("127.0.0.1", 0))]
        with patch("src.validators.credibility.asyncio") as mock_asyncio:
            mock_loop = AsyncMock()
            mock_loop.getaddrinfo.return_value = mock_addr_info
            mock_asyncio.get_event_loop.return_value = mock_loop
            assert await _is_safe_url("http://0177.0.0.1/secret") is False

    async def test_url_with_credentials(self):
        """URL with embedded credentials targeting localhost must be blocked."""
        mock_addr_info = [(None, None, None, None, ("127.0.0.1", 0))]
        with patch("src.validators.credibility.asyncio") as mock_asyncio:
            mock_loop = AsyncMock()
            mock_loop.getaddrinfo.return_value = mock_addr_info
            mock_asyncio.get_event_loop.return_value = mock_loop
            assert await _is_safe_url("http://user:pass@localhost/admin") is False

    async def test_file_scheme(self):
        """file:// scheme must be blocked (no DNS needed)."""
        assert await _is_safe_url("file:///etc/passwd") is False

    async def test_dns_rebinding(self):
        """Domain that resolves to private IP (DNS rebinding) must be blocked."""
        mock_addr_info = [(None, None, None, None, ("10.0.0.1", 0))]
        with patch("src.validators.credibility.asyncio") as mock_asyncio:
            mock_loop = AsyncMock()
            mock_loop.getaddrinfo.return_value = mock_addr_info
            mock_asyncio.get_event_loop.return_value = mock_loop
            assert await _is_safe_url("http://evil-rebind.attacker.com/steal") is False
```

**Step 2: Run tests**

Run: `pytest tests/security/test_ssrf_bypass.py -v --timeout=30`
Expected: 7 passed.

**Step 3: Lint check**

Run: `ruff check tests/security/test_ssrf_bypass.py && ruff format --check tests/security/test_ssrf_bypass.py`
Expected: Clean.

**Step 4: Commit**

```bash
git add tests/security/test_ssrf_bypass.py
git commit -m "test: M11 SSRF bypass tests — IPv6, decimal/octal IP, DNS rebinding [M11]"
```

---

### Task 4: SQL Injection Tests (5 tests)

**Files:**
- Create: `tests/security/test_sql_injection.py`

**Context:**
- Search route: `src/api/routes/search.py` — `func.plainto_tsquery("english", q)` (parameterized)
- Items route: `src/api/routes/items.py` — `NewsItem.topic == topic` (parameterized)
- All queries via SQLAlchemy ORM, no raw SQL
- These tests need real PostgreSQL to prove injections fail at the DB level
- Reuse integration engine/session from `tests/integration/conftest.py`

**Step 1: Write all 5 tests**

```python
"""Security tests for SQL injection attempts against real PostgreSQL."""

from __future__ import annotations

from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from tests.integration.conftest import db_session, integration_engine, seed_news_item  # noqa: F401

pytestmark = [pytest.mark.security, pytest.mark.asyncio(loop_scope="session")]


@pytest_asyncio.fixture(loop_scope="session")
async def db_client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:  # noqa: F811
    """ASGI client with real DB session for SQL injection tests."""
    from src.api.app import app
    from src.core.database import get_session

    async def _override() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    app.dependency_overrides[get_session] = _override
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest.fixture()
def _auth_headers() -> dict[str, str]:
    from src.api.auth import create_access_token

    return {"Authorization": f"Bearer {create_access_token()}"}


class TestSQLInjection:
    """SQL injection attempts that must not cause data leaks or crashes."""

    async def test_classic_drop_table(
        self, db_client: AsyncClient, db_session: AsyncSession, _auth_headers: dict[str, str]  # noqa: F811
    ):
        """Classic DROP TABLE injection in search query must be harmless."""
        await seed_news_item(db_session, title="Safe Article", url="https://example.com/safe-sql")

        resp = await db_client.get(
            "/api/search", params={"q": "'; DROP TABLE news_items--"}, headers=_auth_headers
        )
        assert resp.status_code in (200, 422)
        assert resp.status_code != 500

        # Verify table still exists and has data
        result = await db_session.execute(text("SELECT count(*) FROM news_items"))
        assert result.scalar_one() >= 1

    async def test_union_select(self, db_client: AsyncClient, _auth_headers: dict[str, str]):
        """UNION SELECT injection must not leak data from other tables."""
        resp = await db_client.get(
            "/api/search",
            params={"q": "' UNION SELECT password FROM users--"},
            headers=_auth_headers,
        )
        assert resp.status_code in (200, 422)
        assert resp.status_code != 500
        # If 200, response should be empty or contain only legitimate items
        if resp.status_code == 200:
            data = resp.json()
            for item in data:
                assert "password" not in item

    async def test_filter_param_injection(
        self, db_client: AsyncClient, db_session: AsyncSession, _auth_headers: dict[str, str]  # noqa: F811
    ):
        """Topic filter with SQL injection must match zero results (exact match)."""
        await seed_news_item(
            db_session, title="Legit Item", topic="modelos", url="https://example.com/filter-sql"
        )

        resp = await db_client.get(
            "/api/items", params={"topic": "modelos' OR '1'='1"}, headers=_auth_headers
        )
        assert resp.status_code == 200
        data = resp.json()
        # Injection should NOT return items — exact match fails
        assert len(data) == 0

    async def test_null_byte_in_query(self, db_client: AsyncClient, _auth_headers: dict[str, str]):
        """Null byte in search query must not crash the application."""
        resp = await db_client.get(
            "/api/search", params={"q": "test\x00; DROP TABLE news_items"}, headers=_auth_headers
        )
        assert resp.status_code in (200, 422)
        assert resp.status_code != 500

    async def test_oversized_query_string(
        self, db_client: AsyncClient, _auth_headers: dict[str, str]
    ):
        """Extremely long search query must not crash the application."""
        resp = await db_client.get(
            "/api/search", params={"q": "A" * 10000}, headers=_auth_headers
        )
        assert resp.status_code in (200, 422)
        assert resp.status_code != 500
```

**Step 2: Run tests**

Run: `pytest tests/security/test_sql_injection.py -v --timeout=30`
Expected: 5 passed.

**Step 3: Lint check**

Run: `ruff check tests/security/test_sql_injection.py && ruff format --check tests/security/test_sql_injection.py`
Expected: Clean.

**Step 4: Commit**

```bash
git add tests/security/test_sql_injection.py
git commit -m "test: M11 SQL injection tests — DROP TABLE, UNION, filter, null byte [M11]"
```

---

### Task 5: Rate Limiting Tests (3 tests)

**Files:**
- Create: `tests/security/test_rate_limiting.py`

**Context:**
- Rate limiting: `src/api/app.py:70-73` — global `Limiter(key_func=get_remote_address)`
- Auth: `src/api/routes/auth.py:19` — `@limiter.limit("5/minute")`
- Chat: `src/api/routes/chat.py:33` — `@limiter.limit("10/minute")`
- slowapi stores state in memory; need to clear between tests
- **Important:** slowapi uses the app-level limiter (`app.state.limiter`), not the route-level ones. The route-level `Limiter` instances in `routes/auth.py` and `routes/chat.py` are separate from the global one. Need to verify which one actually enforces.

**Step 1: Write all 3 tests**

```python
"""Security tests for rate limiting enforcement."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

pytestmark = [pytest.mark.security, pytest.mark.asyncio(loop_scope="session")]


class TestRateLimiting:
    """Verify rate limits are enforced on brute-force attempts."""

    async def test_auth_brute_force(self, security_client: AsyncClient):
        """6th login attempt within a minute must be rate-limited (429)."""
        for i in range(6):
            resp = await security_client.post(
                "/api/auth/token", json={"password": f"wrong-{i}"}
            )
            if resp.status_code == 429:
                # Rate limit hit — test passes
                assert i >= 5  # Should happen on 6th request (index 5)
                return

        # If we got here without 429, the rate limit is not enforced
        pytest.fail("Expected 429 after 6 requests, but all returned non-429 status")

    async def test_chat_rate_limit(self, security_client: AsyncClient):
        """11th chat request within a minute must be rate-limited (429)."""
        from src.api.auth import create_access_token

        token = create_access_token(subject="rate-test-user")
        headers = {"Authorization": f"Bearer {token}"}

        for i in range(11):
            resp = await security_client.post(
                "/api/chat",
                json={"question": f"Test question {i}?"},
                headers=headers,
            )
            if resp.status_code == 429:
                assert i >= 10  # Should happen on 11th request (index 10)
                return

        pytest.fail("Expected 429 after 11 requests, but all returned non-429 status")

    async def test_rate_limit_response_format(self, security_client: AsyncClient):
        """Rate limit response must include Retry-After information."""
        # Exhaust the auth limit
        for _ in range(10):
            resp = await security_client.post(
                "/api/auth/token", json={"password": "exhaust-limit"}
            )
            if resp.status_code == 429:
                # Verify the response has useful rate-limit info
                assert resp.status_code == 429
                # slowapi returns a detail message with the limit info
                body = resp.json()
                assert "detail" in body or "error" in body or "Retry-After" in resp.headers
                return

        pytest.fail("Could not trigger rate limit to test response format")
```

**Step 2: Run tests**

Run: `pytest tests/security/test_rate_limiting.py -v --timeout=30`
Expected: 3 passed.

Note: Rate limiting tests can be fragile because slowapi stores state in memory across the test session. If tests fail because the limiter state leaks from previous tests, you may need to add a fixture that resets the limiter storage. The simplest approach: add to conftest.py:

```python
@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    """Reset slowapi limiter state between tests."""
    from src.api.app import app
    if hasattr(app.state, "limiter") and hasattr(app.state.limiter, "_storage"):
        app.state.limiter._storage.reset()
    yield
```

If `_storage.reset()` doesn't exist, try `app.state.limiter._limiter.reset()` or inspect slowapi internals.

**Step 3: Lint check**

Run: `ruff check tests/security/test_rate_limiting.py && ruff format --check tests/security/test_rate_limiting.py`
Expected: Clean.

**Step 4: Commit**

```bash
git add tests/security/test_rate_limiting.py
git commit -m "test: M11 rate limiting tests — brute force auth, chat spam, 429 format [M11]"
```

---

### Task 6: Input Fuzzing Tests (6 tests)

**Files:**
- Create: `tests/security/test_input_fuzzing.py`

**Context:**
- Auth endpoint: `POST /api/auth/token` — accepts `{"password": str}`
- Search endpoint: `GET /api/search?q=...` — requires auth
- Chat endpoint: `POST /api/chat` — accepts `{"question": str}`, requires auth
- All validation via Pydantic models and FastAPI Query params

**Step 1: Write all 6 tests**

```python
"""Security tests for input fuzzing — oversized payloads, unicode, null bytes."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

pytestmark = [pytest.mark.security, pytest.mark.asyncio(loop_scope="session")]


class TestInputFuzzing:
    """Adversarial inputs that must not crash the application."""

    async def test_oversized_json_body(self, security_client: AsyncClient):
        """1MB password must not cause OOM or 500."""
        resp = await security_client.post(
            "/api/auth/token", json={"password": "A" * 1_000_000}
        )
        # Should be 401 (wrong password) or 413/422 (too large) — never 500
        assert resp.status_code in (401, 413, 422)
        assert resp.status_code != 500

    async def test_unicode_edge_cases(
        self, security_client: AsyncClient, auth_headers: dict[str, str]
    ):
        """Unicode BOM, ZWJ, RTL chars in search must not crash."""
        weird_inputs = [
            "\ufefftest",  # BOM
            "test\u200d\u200d",  # Zero-width joiners
            "\u202etest\u202c",  # RTL override
            "\U0001f4a9" * 100,  # Emoji flood
        ]
        for query in weird_inputs:
            resp = await security_client.get(
                "/api/search", params={"q": query}, headers=auth_headers
            )
            assert resp.status_code in (200, 422), f"Crash on input: {query!r}"
            assert resp.status_code != 500

    async def test_null_bytes_in_headers(self, security_client: AsyncClient):
        """Null bytes in Authorization header must not crash."""
        resp = await security_client.get(
            "/api/items", headers={"Authorization": "Bearer \x00fake-token"}
        )
        assert resp.status_code in (401, 403, 422)
        assert resp.status_code != 500

    async def test_header_injection(self, security_client: AsyncClient, auth_headers: dict[str, str]):
        """CRLF injection in custom header must not split headers."""
        # httpx may sanitize this, but we test the server's behavior
        try:
            resp = await security_client.get(
                "/api/items",
                headers={**auth_headers, "X-Custom": "value\r\nInjected: header"},
            )
            # Should either reject or ignore the malformed header
            assert resp.status_code != 500
        except ValueError:
            # httpx rejects the header client-side — that's also safe
            pass

    async def test_extremely_long_params(
        self, security_client: AsyncClient, auth_headers: dict[str, str]
    ):
        """50KB topic parameter must not crash the application."""
        resp = await security_client.get(
            "/api/items", params={"topic": "A" * 50_000}, headers=auth_headers
        )
        assert resp.status_code in (200, 414, 422)
        assert resp.status_code != 500

    async def test_malformed_content_type(self, security_client: AsyncClient):
        """Malformed Content-Type header must be handled gracefully."""
        resp = await security_client.post(
            "/api/auth/token",
            content=b'{"password": "test"}',
            headers={"Content-Type": "application/json; charset=evil"},
        )
        # Should parse JSON or reject — never 500
        assert resp.status_code in (200, 401, 415, 422)
        assert resp.status_code != 500
```

**Step 2: Run tests**

Run: `pytest tests/security/test_input_fuzzing.py -v --timeout=30`
Expected: 6 passed.

**Step 3: Lint check**

Run: `ruff check tests/security/test_input_fuzzing.py && ruff format --check tests/security/test_input_fuzzing.py`
Expected: Clean.

**Step 4: Commit**

```bash
git add tests/security/test_input_fuzzing.py
git commit -m "test: M11 input fuzzing tests — oversized, unicode, null bytes, CRLF [M11]"
```

---

### Task 7: Auth Boundary Tests (4 tests)

**Files:**
- Create: `tests/security/test_auth_boundary.py`

**Context:**
- Protected endpoints (all require `Depends(require_auth)`):
  - `GET /api/items` — `src/api/routes/items.py:29`
  - `GET /api/items/count` — `src/api/routes/items.py:79`
  - `GET /api/items/today` — `src/api/routes/items.py:104`
  - `GET /api/search?q=test` — `src/api/routes/search.py:27`
  - `GET /api/briefings/2026-01-01` — `src/api/routes/briefings.py:23`
  - `GET /api/briefings` — `src/api/routes/briefings.py:78`
  - `POST /api/chat` — `src/api/routes/chat.py:38`
- Without auth: HTTPBearer returns 403 (no header) or auth code returns 401 (bad token)

**Step 1: Write all 4 tests**

```python
"""Security tests for auth boundary enforcement on all protected endpoints."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

pytestmark = [pytest.mark.security, pytest.mark.asyncio(loop_scope="session")]

# Every protected endpoint with its HTTP method and required params
_PROTECTED_ENDPOINTS = [
    ("GET", "/api/items", None),
    ("GET", "/api/items/count", None),
    ("GET", "/api/items/today", None),
    ("GET", "/api/search", {"q": "test"}),
    ("GET", "/api/briefings/2026-01-01", None),
    ("GET", "/api/briefings", None),
    ("POST", "/api/chat", None),
]


class TestAuthBoundary:
    """Verify every protected endpoint rejects unauthenticated requests."""

    @pytest.mark.parametrize(
        ("method", "path", "params"),
        _PROTECTED_ENDPOINTS,
        ids=[f"{m} {p}" for m, p, _ in _PROTECTED_ENDPOINTS],
    )
    async def test_all_protected_endpoints_require_auth(
        self, security_client: AsyncClient, method: str, path: str, params: dict | None
    ):
        """Every protected endpoint must return 403 without auth."""
        if method == "GET":
            resp = await security_client.get(path, params=params)
        else:
            resp = await security_client.post(path, json={"question": "test?"})
        assert resp.status_code == 403, f"{method} {path} returned {resp.status_code}, expected 403"

    async def test_empty_bearer_token(self, security_client: AsyncClient):
        """Empty Bearer token must be rejected."""
        resp = await security_client.get(
            "/api/items", headers={"Authorization": "Bearer "}
        )
        assert resp.status_code in (401, 403)

    async def test_non_jwt_bearer(self, security_client: AsyncClient):
        """Non-JWT string as Bearer token must be rejected."""
        resp = await security_client.get(
            "/api/items", headers={"Authorization": "Bearer this-is-not-a-jwt"}
        )
        assert resp.status_code == 401

    async def test_wrong_auth_scheme(self, security_client: AsyncClient):
        """Basic auth scheme must be rejected (server expects Bearer)."""
        resp = await security_client.get(
            "/api/items", headers={"Authorization": "Basic dXNlcjpwYXNz"}
        )
        assert resp.status_code == 403
```

**Step 2: Run tests**

Run: `pytest tests/security/test_auth_boundary.py -v --timeout=30`
Expected: 4 tests (but `test_all_protected_endpoints_require_auth` is parametrized into 7 cases, so 10 total test cases pass).

**Step 3: Lint check**

Run: `ruff check tests/security/test_auth_boundary.py && ruff format --check tests/security/test_auth_boundary.py`
Expected: Clean.

**Step 4: Commit**

```bash
git add tests/security/test_auth_boundary.py
git commit -m "test: M11 auth boundary tests — all endpoints, empty/invalid tokens, wrong scheme [M11]"
```

---

### Task 8: Final Verification + Milestone Complete

**Files:**
- Modify: `docs/plans/2026-02-21-milestone-11-design.md` (mark success criteria)

**Step 1: Run ALL security tests**

Run: `pytest tests/security/ -v -m security --timeout=30`
Expected: 31 passed (6 JWT + 7 SSRF + 5 SQL + 3 rate limit + 6 fuzzing + 4 auth boundary).

Note: Auth boundary test is parametrized with 7 endpoints, so actual test count will be 37 (6 + 7 + 5 + 3 + 6 + 10). Update the design doc count accordingly.

**Step 2: Run unit tests (regression check)**

Run: `pytest tests/unit/ -x --timeout=30`
Expected: 702 passed.

**Step 3: Run integration tests (regression check)**

Run: `pytest tests/integration/ -v -m integration --timeout=60`
Expected: 28 passed.

**Step 4: Lint + format check**

Run: `ruff check . && ruff format --check .`
Expected: All clean.

**Step 5: Update design doc success criteria**

Change all `- [ ]` to `- [x]` in the Success Criteria section of `docs/plans/2026-02-21-milestone-11-design.md`. Update the test count to match actual.

**Step 6: Commit**

```bash
git add docs/plans/2026-02-21-milestone-11-design.md
git commit -m "test: M11 final — verification + milestone complete [M11]"
```

---

## Verification Summary

1. `pytest tests/security/ -v -m security --timeout=30` — all pass
2. `pytest tests/unit/ -x --timeout=30` — 702 pass (no regressions)
3. `pytest tests/integration/ -m integration --timeout=60` — 28 pass (no regressions)
4. `ruff check . && ruff format --check .` — clean
5. CI green with unit + integration + security steps
