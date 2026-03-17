"""Tests for JWT authentication -- auth dependency and refresh tokens."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient
from jose import jwt

from src.api.app import app
from src.api.auth import UserClaims, create_access_token
from src.core.config import Settings

# ---------------------------------------------------------------------------
# Test settings with known secret
# ---------------------------------------------------------------------------
TEST_SECRET = "test-jwt-secret-key"
TEST_ALGORITHM = "HS256"


def _make_test_settings(**overrides) -> Settings:
    """Create a Settings instance for auth tests."""
    defaults = {
        "jwt_secret": TEST_SECRET,
        "jwt_algorithm": TEST_ALGORITHM,
        "jwt_access_expire_minutes": 30,
        "jwt_refresh_expire_days": 7,
        "database_url": "postgresql+asyncpg://x:x@localhost/x",
        "database_url_sync": "postgresql://x:x@localhost/x",
    }
    defaults.update(overrides)
    return Settings(**defaults)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture(autouse=True)
def _override_settings():
    """Override get_settings so every test uses a deterministic secret.

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
# require_auth dependency
# ---------------------------------------------------------------------------
class TestRequireAuth:
    """Tests for the require_auth dependency function."""

    async def test_valid_token_passes(self, api_client: AsyncClient):
        """A protected endpoint should return 200 with a valid token."""
        # Create a valid token directly
        test_settings = _make_test_settings()
        with patch("src.api.auth.get_settings", return_value=test_settings):
            token = create_access_token(subject="test-user", role="reader", email="t@test.com")

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

    async def test_refresh_returns_new_tokens(self, api_client: AsyncClient):
        """Refresh endpoint returns new access and refresh tokens."""
        from src.api.auth import create_refresh_token

        test_settings = _make_test_settings()
        with patch("src.api.auth.get_settings", return_value=test_settings):
            refresh_token = create_refresh_token(subject="test-user", role="reader")

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
        from src.api.auth import create_refresh_token

        test_settings = _make_test_settings()
        with patch("src.api.auth.get_settings", return_value=test_settings):
            old_refresh = create_refresh_token(subject="test-user", role="reader")

        # Use the refresh token once
        await api_client.post("/api/auth/refresh", json={"refresh_token": old_refresh})

        # Try to use the same refresh token again -- should fail
        resp = await api_client.post("/api/auth/refresh", json={"refresh_token": old_refresh})
        assert resp.status_code == 401

    async def test_refresh_propagates_claims(self, api_client: AsyncClient):
        """Refreshed tokens should carry the same role/email claims."""
        from src.api.auth import create_refresh_token

        test_settings = _make_test_settings()
        with (
            patch("src.api.auth.get_settings", return_value=test_settings),
            patch("src.api.routes.auth.get_settings", return_value=test_settings),
        ):
            refresh_token = create_refresh_token(
                subject="test-uuid",
                role="admin",
                email="admin@test.com",
            )

        resp = await api_client.post(
            "/api/auth/refresh",
            json={"refresh_token": refresh_token},
        )
        assert resp.status_code == 200
        data = resp.json()
        # Decode the new access token to verify claims propagated
        new_payload = jwt.decode(
            data["access_token"],
            TEST_SECRET,
            algorithms=[TEST_ALGORITHM],
        )
        assert new_payload["role"] == "admin"
        assert new_payload["email"] == "admin@test.com"
        assert new_payload["sub"] == "test-uuid"

    async def test_access_token_with_refresh_type_rejected(self, api_client: AsyncClient):
        """Using a refresh token as access token should fail."""
        from src.api.auth import create_refresh_token

        test_settings = _make_test_settings()
        with patch("src.api.auth.get_settings", return_value=test_settings):
            refresh_token = create_refresh_token(subject="test-user", role="reader")

        from unittest.mock import AsyncMock, MagicMock

        from src.core.database import get_session

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


# ---------------------------------------------------------------------------
# UserClaims + require_admin
# ---------------------------------------------------------------------------
class TestUserClaims:
    """Tests for UserClaims dataclass and token claim propagation."""

    def test_access_token_with_role_and_email(self):
        test_settings = _make_test_settings()
        with patch("src.api.auth.get_settings", return_value=test_settings):
            token = create_access_token(
                subject="550e8400-e29b-41d4-a716-446655440000",
                role="admin",
                email="admin@test.com",
            )
        payload = jwt.decode(token, TEST_SECRET, algorithms=[TEST_ALGORITHM])
        assert payload["sub"] == "550e8400-e29b-41d4-a716-446655440000"
        assert payload["role"] == "admin"
        assert payload["email"] == "admin@test.com"

    def test_access_token_backward_compatible(self):
        """Old-style tokens without role/email still work."""
        test_settings = _make_test_settings()
        with patch("src.api.auth.get_settings", return_value=test_settings):
            token = create_access_token(subject="user")
        payload = jwt.decode(token, TEST_SECRET, algorithms=[TEST_ALGORITHM])
        assert payload["sub"] == "user"
        assert "role" not in payload
        assert "email" not in payload

    def test_user_claims_dataclass(self):
        claims = UserClaims(sub="uuid-123", role="admin", email="a@b.com")
        assert claims.sub == "uuid-123"
        assert claims.role == "admin"
        assert claims.email == "a@b.com"


class TestRequireAdmin:
    """Tests for the require_admin dependency."""

    async def test_admin_role_passes(self):
        test_settings = _make_test_settings()
        from fastapi.security import HTTPAuthorizationCredentials

        from src.api.auth import require_admin, require_auth

        with patch("src.api.auth.get_settings", return_value=test_settings):
            token = create_access_token(
                subject="uuid-admin",
                role="admin",
                email="admin@test.com",
            )
            creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
            user = await require_auth(creds)
            result = await require_admin(user)
        assert result.role == "admin"

    async def test_reader_role_blocked(self):
        test_settings = _make_test_settings()
        from fastapi.security import HTTPAuthorizationCredentials

        from src.api.auth import require_admin, require_auth
        from src.api.errors import APIError

        with patch("src.api.auth.get_settings", return_value=test_settings):
            token = create_access_token(
                subject="uuid-reader",
                role="reader",
                email="reader@test.com",
            )
            creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
            user = await require_auth(creds)
            with pytest.raises(APIError) as exc_info:
                await require_admin(user)
            assert exc_info.value.status_code == 403


# ---------------------------------------------------------------------------
# Guest tokens
# ---------------------------------------------------------------------------
class TestGuestTokens:
    """Tests for guest token creation and require_auth_or_guest."""

    def test_create_guest_token_has_guest_role(self):
        test_settings = _make_test_settings()
        with patch("src.api.auth.get_settings", return_value=test_settings):
            from src.api.auth import create_guest_token

            token = create_guest_token()
        payload = jwt.decode(token, TEST_SECRET, algorithms=[TEST_ALGORITHM])
        assert payload["role"] == "guest"
        assert payload["sub"].startswith("guest:")
        assert payload["type"] == "access"

    def test_create_guest_token_has_jti(self):
        test_settings = _make_test_settings()
        with patch("src.api.auth.get_settings", return_value=test_settings):
            from src.api.auth import create_guest_token

            token = create_guest_token()
        payload = jwt.decode(token, TEST_SECRET, algorithms=[TEST_ALGORITHM])
        assert "exp" in payload
        assert "jti" in payload

    async def test_require_auth_or_guest_accepts_guest_token(self):
        test_settings = _make_test_settings()
        from fastapi.security import HTTPAuthorizationCredentials

        from src.api.auth import create_guest_token, require_auth_or_guest

        with patch("src.api.auth.get_settings", return_value=test_settings):
            token = create_guest_token()
            creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
            user = await require_auth_or_guest(creds)
        assert user.role == "guest"
        assert user.sub.startswith("guest:")

    async def test_require_auth_or_guest_accepts_regular_token(self):
        test_settings = _make_test_settings()
        from fastapi.security import HTTPAuthorizationCredentials

        from src.api.auth import require_auth_or_guest

        with patch("src.api.auth.get_settings", return_value=test_settings):
            token = create_access_token(subject="user-uuid", role="reader", email="u@test.com")
            creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
            user = await require_auth_or_guest(creds)
        assert user.role == "reader"

    async def test_require_auth_rejects_guest_token(self):
        test_settings = _make_test_settings()
        from fastapi.security import HTTPAuthorizationCredentials

        from src.api.auth import create_guest_token, require_auth
        from src.api.errors import APIError

        with patch("src.api.auth.get_settings", return_value=test_settings):
            token = create_guest_token()
            creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
            with pytest.raises(APIError) as exc_info:
                await require_auth(creds)
            assert exc_info.value.status_code == 401


# ---------------------------------------------------------------------------
# POST /api/auth/guest endpoint
# ---------------------------------------------------------------------------
class TestGuestEndpoint:
    """Tests for POST /api/auth/guest."""

    async def test_guest_endpoint_returns_200(self, api_client: AsyncClient):
        resp = await api_client.post("/api/auth/guest")
        assert resp.status_code == 200

    async def test_guest_endpoint_returns_access_token(self, api_client: AsyncClient):
        resp = await api_client.post("/api/auth/guest")
        data = resp.json()
        assert "access_token" in data
        assert "expires_in" in data
        assert data["token_type"] == "bearer"
        # Guest tokens should NOT have refresh tokens
        assert "refresh_token" not in data

    async def test_guest_token_is_valid_jwt(self, api_client: AsyncClient):
        resp = await api_client.post("/api/auth/guest")
        token = resp.json()["access_token"]
        payload = jwt.decode(token, TEST_SECRET, algorithms=[TEST_ALGORITHM])
        assert payload["role"] == "guest"
        assert payload["sub"].startswith("guest:")


# ---------------------------------------------------------------------------
# Guest flow integration test
# ---------------------------------------------------------------------------
class TestGuestFlow:
    """End-to-end: get guest token, use it on public endpoint, fail on chat."""

    async def test_full_guest_flow(self, api_client: AsyncClient):
        from unittest.mock import AsyncMock, MagicMock

        from src.core.database import get_session

        # 1. Get guest token
        resp = await api_client.post("/api/auth/guest")
        assert resp.status_code == 200
        token = resp.json()["access_token"]

        # 2. Access public endpoint
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
            resp = await api_client.get("/api/items", headers={"Authorization": f"Bearer {token}"})
            assert resp.status_code == 200
        finally:
            app.dependency_overrides.pop(get_session, None)

        # 3. Chat should be blocked for guest
        resp = await api_client.post(
            "/api/chat",
            json={"question": "test question"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 401
