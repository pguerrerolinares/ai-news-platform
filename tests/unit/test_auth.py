"""Tests for JWT authentication -- token endpoint and auth dependency."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient
from jose import jwt

from src.api.app import app
from src.core.config import Settings

# ---------------------------------------------------------------------------
# Test settings with known secret and password
# ---------------------------------------------------------------------------
TEST_SECRET = "test-jwt-secret-key"
TEST_PASSWORD = "test-password-123"
TEST_ALGORITHM = "HS256"


def _make_test_settings(**overrides) -> Settings:
    """Create a Settings instance for auth tests."""
    defaults = {
        "jwt_secret": TEST_SECRET,
        "jwt_algorithm": TEST_ALGORITHM,
        "jwt_access_expire_minutes": 30,
        "jwt_refresh_expire_days": 7,
        "shared_password": TEST_PASSWORD,
        "database_url": "postgresql+asyncpg://x:x@localhost/x",
        "database_url_sync": "postgresql://x:x@localhost/x",
        "telegram_bot_token": "",
        "telegram_chat_id": "",
        "telegram_alerts_enabled": False,
    }
    defaults.update(overrides)
    return Settings(**defaults)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture(autouse=True)
def _override_settings():
    """Override get_settings so every test uses a deterministic secret/password.

    Also disables the rate limiter so tests aren't throttled.
    """
    test_settings = _make_test_settings()
    from src.api.routes.auth import limiter

    original_enabled = limiter.enabled
    limiter.enabled = False
    with (
        patch("src.api.auth.get_settings", return_value=test_settings),
        patch("src.api.routes.auth.get_settings", return_value=test_settings),
    ):
        # Clear refresh token state between tests
        from src.api.auth import _refresh_tokens

        _refresh_tokens.clear()
        yield
    limiter.enabled = original_enabled


@pytest.fixture()
async def api_client() -> AsyncClient:
    """Create an httpx AsyncClient wired to the FastAPI app."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac  # type: ignore[misc]


# ---------------------------------------------------------------------------
# POST /api/auth/token -- success
# ---------------------------------------------------------------------------
class TestTokenEndpointSuccess:
    """Tests for successful authentication."""

    async def test_correct_password_returns_200(self, api_client: AsyncClient):
        """POST with the correct password should return HTTP 200."""
        resp = await api_client.post("/api/auth/token", json={"password": TEST_PASSWORD})
        assert resp.status_code == 200

    async def test_correct_password_returns_access_token(self, api_client: AsyncClient):
        """Response should contain an access_token field."""
        resp = await api_client.post("/api/auth/token", json={"password": TEST_PASSWORD})
        data = resp.json()
        assert "access_token" in data
        assert len(data["access_token"]) > 0

    async def test_correct_password_returns_bearer_type(self, api_client: AsyncClient):
        """Response token_type should be 'bearer'."""
        resp = await api_client.post("/api/auth/token", json={"password": TEST_PASSWORD})
        data = resp.json()
        assert data["token_type"] == "bearer"

    async def test_token_is_decodable(self, api_client: AsyncClient):
        """Returned JWT should be decodable with the configured secret."""
        resp = await api_client.post("/api/auth/token", json={"password": TEST_PASSWORD})
        token = resp.json()["access_token"]
        payload = jwt.decode(token, TEST_SECRET, algorithms=[TEST_ALGORITHM])
        assert isinstance(payload, dict)

    async def test_token_contains_sub_claim(self, api_client: AsyncClient):
        """Decoded JWT should contain a 'sub' claim."""
        resp = await api_client.post("/api/auth/token", json={"password": TEST_PASSWORD})
        token = resp.json()["access_token"]
        payload = jwt.decode(token, TEST_SECRET, algorithms=[TEST_ALGORITHM])
        assert "sub" in payload
        assert payload["sub"] == "user"

    async def test_token_contains_exp_claim(self, api_client: AsyncClient):
        """Decoded JWT should contain an 'exp' claim."""
        resp = await api_client.post("/api/auth/token", json={"password": TEST_PASSWORD})
        token = resp.json()["access_token"]
        payload = jwt.decode(token, TEST_SECRET, algorithms=[TEST_ALGORITHM])
        assert "exp" in payload


# ---------------------------------------------------------------------------
# POST /api/auth/token -- failure
# ---------------------------------------------------------------------------
class TestTokenEndpointFailure:
    """Tests for failed authentication."""

    async def test_wrong_password_returns_401(self, api_client: AsyncClient):
        """POST with an incorrect password should return HTTP 401."""
        resp = await api_client.post("/api/auth/token", json={"password": "wrong-password"})
        assert resp.status_code == 401

    async def test_wrong_password_has_error_object(self, api_client: AsyncClient):
        """401 response should include a standardized error object."""
        resp = await api_client.post("/api/auth/token", json={"password": "wrong-password"})
        data = resp.json()
        assert "error" in data
        assert "code" in data["error"]

    async def test_missing_password_returns_422(self, api_client: AsyncClient):
        """POST with no password field should return HTTP 422."""
        resp = await api_client.post("/api/auth/token", json={})
        assert resp.status_code == 422

    async def test_empty_body_returns_422(self, api_client: AsyncClient):
        """POST with an empty body should return HTTP 422."""
        resp = await api_client.post("/api/auth/token")
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# require_auth dependency
# ---------------------------------------------------------------------------
class TestRequireAuth:
    """Tests for the require_auth dependency function."""

    async def test_valid_token_passes(self, api_client: AsyncClient):
        """A protected endpoint should return 200 with a valid token."""
        # Get a valid token first
        resp = await api_client.post("/api/auth/token", json={"password": TEST_PASSWORD})
        token = resp.json()["access_token"]

        # Use it to access a protected route (items endpoint, with session override)
        from src.core.database import get_session

        async def _mock_session():
            from unittest.mock import AsyncMock, MagicMock

            mock_result = MagicMock()
            mock_scalars = MagicMock()
            mock_scalars.all.return_value = []
            mock_result.scalars.return_value = mock_scalars
            mock_result.scalar_one.return_value = 0
            session = AsyncMock()
            session.execute = AsyncMock(return_value=mock_result)
            yield session

        app.dependency_overrides[get_session] = _mock_session
        try:
            resp = await api_client.get("/api/items", headers={"Authorization": f"Bearer {token}"})
            assert resp.status_code == 200
        finally:
            app.dependency_overrides.pop(get_session, None)

    async def test_expired_token_returns_401(self, api_client: AsyncClient):
        """An expired JWT should result in HTTP 401."""
        # Create a token that expired 1 hour ago
        expired_payload = {
            "sub": "user",
            "exp": datetime.now(tz=UTC) - timedelta(hours=1),
        }
        expired_token = jwt.encode(expired_payload, TEST_SECRET, algorithm=TEST_ALGORITHM)

        from src.core.database import get_session

        async def _mock_session():
            from unittest.mock import AsyncMock, MagicMock

            session = AsyncMock()
            session.execute = AsyncMock(return_value=MagicMock())
            yield session

        app.dependency_overrides[get_session] = _mock_session
        try:
            resp = await api_client.get(
                "/api/items", headers={"Authorization": f"Bearer {expired_token}"}
            )
            assert resp.status_code == 401
        finally:
            app.dependency_overrides.pop(get_session, None)

    async def test_invalid_token_returns_401(self, api_client: AsyncClient):
        """A malformed JWT should result in HTTP 401."""
        from src.core.database import get_session

        async def _mock_session():
            from unittest.mock import AsyncMock, MagicMock

            session = AsyncMock()
            session.execute = AsyncMock(return_value=MagicMock())
            yield session

        app.dependency_overrides[get_session] = _mock_session
        try:
            resp = await api_client.get(
                "/api/items", headers={"Authorization": "Bearer not-a-real-jwt-token"}
            )
            assert resp.status_code == 401
        finally:
            app.dependency_overrides.pop(get_session, None)

    async def test_no_token_returns_403(self, api_client: AsyncClient):
        """A request with no Authorization header should return 403 (HTTPBearer default)."""
        from src.core.database import get_session

        async def _mock_session():
            from unittest.mock import AsyncMock, MagicMock

            session = AsyncMock()
            session.execute = AsyncMock(return_value=MagicMock())
            yield session

        app.dependency_overrides[get_session] = _mock_session
        try:
            resp = await api_client.get("/api/items")
            assert resp.status_code == 403
        finally:
            app.dependency_overrides.pop(get_session, None)

    async def test_wrong_secret_returns_401(self, api_client: AsyncClient):
        """A JWT signed with a different secret should result in HTTP 401."""
        bad_payload = {
            "sub": "user",
            "exp": datetime.now(tz=UTC) + timedelta(hours=1),
        }
        bad_token = jwt.encode(bad_payload, "wrong-secret", algorithm=TEST_ALGORITHM)

        from src.core.database import get_session

        async def _mock_session():
            from unittest.mock import AsyncMock, MagicMock

            session = AsyncMock()
            session.execute = AsyncMock(return_value=MagicMock())
            yield session

        app.dependency_overrides[get_session] = _mock_session
        try:
            resp = await api_client.get(
                "/api/items", headers={"Authorization": f"Bearer {bad_token}"}
            )
            assert resp.status_code == 401
        finally:
            app.dependency_overrides.pop(get_session, None)


# ---------------------------------------------------------------------------
# Refresh tokens
# ---------------------------------------------------------------------------
class TestRefreshTokens:
    """Tests for refresh token functionality."""

    async def test_login_returns_refresh_token(self, api_client: AsyncClient):
        """Login should return both access_token and refresh_token."""
        resp = await api_client.post("/api/auth/token", json={"password": TEST_PASSWORD})
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert "expires_in" in data

    async def test_refresh_returns_new_tokens(self, api_client: AsyncClient):
        """Refresh endpoint returns new access and refresh tokens."""
        login = await api_client.post("/api/auth/token", json={"password": TEST_PASSWORD})
        refresh_token = login.json()["refresh_token"]

        resp = await api_client.post("/api/auth/refresh", json={"refresh_token": refresh_token})
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert "refresh_token" in data

    async def test_refresh_with_invalid_token_fails(self, api_client: AsyncClient):
        """Refresh with invalid token returns 401."""
        resp = await api_client.post("/api/auth/refresh", json={"refresh_token": "invalid-token"})
        assert resp.status_code == 401

    async def test_old_refresh_token_rejected_after_rotation(self, api_client: AsyncClient):
        """After refreshing, the old refresh token should be invalid."""
        login = await api_client.post("/api/auth/token", json={"password": TEST_PASSWORD})
        old_refresh = login.json()["refresh_token"]

        # Use the refresh token once
        await api_client.post("/api/auth/refresh", json={"refresh_token": old_refresh})

        # Try to use the same refresh token again -- should fail
        resp = await api_client.post("/api/auth/refresh", json={"refresh_token": old_refresh})
        assert resp.status_code == 401

    async def test_access_token_with_refresh_type_rejected(self, api_client: AsyncClient):
        """Using a refresh token as access token should fail."""
        login = await api_client.post("/api/auth/token", json={"password": TEST_PASSWORD})
        refresh_token = login.json()["refresh_token"]

        from src.core.database import get_session
        from unittest.mock import AsyncMock, MagicMock

        async def _mock_session():
            mock_result = MagicMock()
            mock_scalars = MagicMock()
            mock_scalars.all.return_value = []
            mock_result.scalars.return_value = mock_scalars
            mock_result.scalar_one.return_value = 0
            session = AsyncMock()
            session.execute = AsyncMock(return_value=mock_result)
            yield session

        app.dependency_overrides[get_session] = _mock_session
        try:
            resp = await api_client.get(
                "/api/items", headers={"Authorization": f"Bearer {refresh_token}"}
            )
            assert resp.status_code == 401
        finally:
            app.dependency_overrides.pop(get_session, None)
