"""Tests for WebAuthn route endpoints."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from src.api.app import app
from src.core.config import Settings

TEST_SECRET = "test-jwt-secret-key"
TEST_PASSWORD = "test-password-123"


def _make_test_settings(**overrides) -> Settings:
    defaults = {
        "jwt_secret": TEST_SECRET,
        "jwt_algorithm": "HS256",
        "jwt_access_expire_minutes": 30,
        "jwt_refresh_expire_days": 7,
        "shared_password": TEST_PASSWORD,
        "database_url": "postgresql+asyncpg://x:x@localhost/x",
        "database_url_sync": "postgresql://x:x@localhost/x",
        "telegram_bot_token": "",
        "telegram_chat_id": "",
        "telegram_alerts_enabled": False,
        "webauthn_rp_id": "localhost",
        "webauthn_rp_name": "AI News",
        "webauthn_origin": "http://localhost:5173",
    }
    defaults.update(overrides)
    return Settings(**defaults)


@pytest.fixture(autouse=True)
def _override_settings():
    test_settings = _make_test_settings()
    from src.api.routes.webauthn import limiter

    original_enabled = limiter.enabled
    limiter.enabled = False
    with patch("src.api.routes.webauthn.get_settings", return_value=test_settings):
        yield
    limiter.enabled = original_enabled


@pytest.fixture()
async def api_client() -> AsyncClient:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac  # type: ignore[misc]


def _auth_header() -> dict[str, str]:
    from src.api.auth import create_access_token

    test_settings = _make_test_settings()
    with patch("src.api.auth.get_settings", return_value=test_settings):
        token = create_access_token(
            subject=str(uuid.uuid4()),
            role="reader",
            email="test@example.com",
        )
    return {"Authorization": f"Bearer {token}"}


class TestRegisterOptions:
    async def test_unauthenticated_returns_403(self, api_client: AsyncClient):
        resp = await api_client.post("/api/auth/webauthn/register/options")
        assert resp.status_code == 403

    async def test_authenticated_returns_200(self, api_client: AsyncClient):
        test_settings = _make_test_settings()
        with patch("src.api.auth.get_settings", return_value=test_settings):
            mock_session = AsyncMock()
            mock_result = MagicMock()
            mock_result.scalars.return_value.all.return_value = []
            mock_session.execute = AsyncMock(return_value=mock_result)

            with patch("src.api.routes.webauthn.get_async_session") as mock_get_session:
                mock_get_session.return_value.__aenter__ = AsyncMock(return_value=mock_session)
                mock_get_session.return_value.__aexit__ = AsyncMock(return_value=False)
                resp = await api_client.post(
                    "/api/auth/webauthn/register/options",
                    headers=_auth_header(),
                )
            assert resp.status_code == 200
            data = resp.json()
            assert "challenge" in data or "publicKey" in data


class TestLoginOptions:
    async def test_missing_email_returns_422(self, api_client: AsyncClient):
        resp = await api_client.post("/api/auth/webauthn/login/options", json={})
        assert resp.status_code == 422

    async def test_no_credentials_returns_404(self, api_client: AsyncClient):
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)

        with patch("src.api.routes.webauthn.get_async_session") as mock_get_session:
            mock_get_session.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_get_session.return_value.__aexit__ = AsyncMock(return_value=False)
            resp = await api_client.post(
                "/api/auth/webauthn/login/options",
                json={"email": "nobody@test.com"},
            )
        assert resp.status_code == 404


class TestLegacySessionRejected:
    """Legacy (non-UUID sub) tokens must be rejected by all webauthn endpoints."""

    def _legacy_header(self) -> dict[str, str]:
        from src.api.auth import create_access_token

        test_settings = _make_test_settings()
        with patch("src.api.auth.get_settings", return_value=test_settings):
            token = create_access_token(subject="legacy", role="reader")
        return {"Authorization": f"Bearer {token}"}

    async def test_register_options_rejects_legacy(self, api_client: AsyncClient):
        test_settings = _make_test_settings()
        with patch("src.api.auth.get_settings", return_value=test_settings):
            resp = await api_client.post(
                "/api/auth/webauthn/register/options",
                headers=self._legacy_header(),
            )
        assert resp.status_code == 403
        assert resp.json()["error"]["code"] == "LEGACY_SESSION"

    async def test_list_credentials_rejects_legacy(self, api_client: AsyncClient):
        test_settings = _make_test_settings()
        with patch("src.api.auth.get_settings", return_value=test_settings):
            resp = await api_client.get(
                "/api/auth/webauthn/credentials",
                headers=self._legacy_header(),
            )
        assert resp.status_code == 403
        assert resp.json()["error"]["code"] == "LEGACY_SESSION"


class TestCredentialsList:
    async def test_unauthenticated_returns_403(self, api_client: AsyncClient):
        resp = await api_client.get("/api/auth/webauthn/credentials")
        assert resp.status_code == 403
