"""Tests for OTP auth endpoints."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from src.api.app import app
from src.core.config import Settings

TEST_SECRET = "test-jwt-secret-key"


def _make_test_settings(**overrides) -> Settings:
    defaults = {
        "jwt_secret": TEST_SECRET,
        "jwt_algorithm": "HS256",
        "jwt_access_expire_minutes": 30,
        "jwt_refresh_expire_days": 7,
        "database_url": "postgresql+asyncpg://x:x@localhost/x",
        "database_url_sync": "postgresql://x:x@localhost/x",
        "admin_email": "admin@test.com",
        "resend_api_key": "",
        "otp_expire_minutes": 10,
    }
    defaults.update(overrides)
    return Settings(**defaults)


@pytest.fixture(autouse=True)
def _override_settings():
    test_settings = _make_test_settings()
    # Disable rate limiters
    from src.api.routes.auth import limiter as auth_limiter
    from src.api.routes.otp import limiter as otp_limiter

    auth_orig = auth_limiter.enabled
    otp_orig = otp_limiter.enabled
    auth_limiter.enabled = False
    otp_limiter.enabled = False

    with (
        patch("src.api.auth.get_settings", return_value=test_settings),
        patch("src.api.routes.auth.get_settings", return_value=test_settings),
        patch("src.api.routes.otp.get_settings", return_value=test_settings),
    ):
        from src.api.auth import _refresh_tokens

        _refresh_tokens.clear()
        yield

    auth_limiter.enabled = auth_orig
    otp_limiter.enabled = otp_orig


@pytest.fixture()
async def api_client() -> AsyncClient:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac  # type: ignore[misc]


# ---------------------------------------------------------------------------
# POST /api/auth/otp/request
# ---------------------------------------------------------------------------
class TestOtpRequest:
    async def test_request_otp_returns_200(self, api_client: AsyncClient):
        """POST /api/auth/otp/request sends OTP and returns success."""
        mock_session = AsyncMock()
        mock_count_result = MagicMock()
        mock_count_result.scalar_one.return_value = 0  # email rate limit: OK
        mock_daily_result = MagicMock()
        mock_daily_result.scalar_one.return_value = 0  # daily cap: OK
        mock_session.execute = AsyncMock(
            side_effect=[mock_count_result, mock_daily_result, MagicMock()]
        )
        mock_session.add = MagicMock()
        mock_session.commit = AsyncMock()

        from contextlib import asynccontextmanager

        @asynccontextmanager
        async def mock_get_session():
            yield mock_session

        with (
            patch("src.api.routes.otp.get_async_session", mock_get_session),
            patch("src.api.routes.otp.send_otp_email", new_callable=AsyncMock) as mock_send,
            patch("src.api.routes.otp.generate_otp_code", return_value="123456"),
        ):
            resp = await api_client.post(
                "/api/auth/otp/request",
                json={"email": "test@example.com"},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["message"] == "Code sent"
        mock_send.assert_called_once_with("test@example.com", "123456")

    async def test_request_otp_invalid_email(self, api_client: AsyncClient):
        resp = await api_client.post(
            "/api/auth/otp/request",
            json={"email": "not-an-email"},
        )
        assert resp.status_code == 422

    async def test_request_otp_email_rate_limit(self, api_client: AsyncClient):
        """Returns 429 when email has 5+ OTPs in the last hour."""
        mock_session = AsyncMock()

        # email rate limit count returns 5 (at limit)
        mock_count_result = MagicMock()
        mock_count_result.scalar_one.return_value = 5
        mock_session.execute = AsyncMock(return_value=mock_count_result)
        mock_session.add = MagicMock()
        mock_session.commit = AsyncMock()

        from contextlib import asynccontextmanager

        @asynccontextmanager
        async def mock_get_session():
            yield mock_session

        with (
            patch("src.api.routes.otp.get_async_session", mock_get_session),
            patch("src.api.routes.otp.send_otp_email", new_callable=AsyncMock) as mock_send,
        ):
            resp = await api_client.post(
                "/api/auth/otp/request",
                json={"email": "spam@example.com"},
            )

        assert resp.status_code == 429
        assert resp.json()["error"]["code"] == "OTP_EMAIL_RATE_LIMITED"
        mock_send.assert_not_called()

    async def test_request_otp_daily_cap(self, api_client: AsyncClient):
        """Returns 503 when global daily OTP cap is reached."""
        mock_session = AsyncMock()

        # First execute: email rate limit count returns 0 (OK)
        mock_email_count = MagicMock()
        mock_email_count.scalar_one.return_value = 0
        # Second execute: daily cap count returns 50 (at limit)
        mock_daily_count = MagicMock()
        mock_daily_count.scalar_one.return_value = 50
        mock_session.execute = AsyncMock(side_effect=[mock_email_count, mock_daily_count])
        mock_session.add = MagicMock()
        mock_session.commit = AsyncMock()

        from contextlib import asynccontextmanager

        @asynccontextmanager
        async def mock_get_session():
            yield mock_session

        with (
            patch("src.api.routes.otp.get_async_session", mock_get_session),
            patch("src.api.routes.otp.send_otp_email", new_callable=AsyncMock) as mock_send,
        ):
            resp = await api_client.post(
                "/api/auth/otp/request",
                json={"email": "legit@example.com"},
            )

        assert resp.status_code == 503
        assert resp.json()["error"]["code"] == "OTP_DAILY_CAP_REACHED"
        mock_send.assert_not_called()

    async def test_request_otp_normalizes_email(self, api_client: AsyncClient):
        """Email should be lowercased."""
        mock_session = AsyncMock()
        mock_count_result = MagicMock()
        mock_count_result.scalar_one.return_value = 0  # email rate limit: OK
        mock_daily_result = MagicMock()
        mock_daily_result.scalar_one.return_value = 0  # daily cap: OK
        mock_session.execute = AsyncMock(
            side_effect=[mock_count_result, mock_daily_result, MagicMock()]
        )
        mock_session.add = MagicMock()
        mock_session.commit = AsyncMock()

        from contextlib import asynccontextmanager

        @asynccontextmanager
        async def mock_get_session():
            yield mock_session

        with (
            patch("src.api.routes.otp.get_async_session", mock_get_session),
            patch("src.api.routes.otp.send_otp_email", new_callable=AsyncMock) as mock_send,
            patch("src.api.routes.otp.generate_otp_code", return_value="654321"),
        ):
            resp = await api_client.post(
                "/api/auth/otp/request",
                json={"email": "Test@Example.COM"},
            )

        assert resp.status_code == 200
        mock_send.assert_called_once_with("test@example.com", "654321")


# ---------------------------------------------------------------------------
# POST /api/auth/otp/verify
# ---------------------------------------------------------------------------
class TestOtpVerify:
    async def test_verify_valid_code_returns_tokens(self, api_client: AsyncClient):
        """POST /api/auth/otp/verify with valid code returns JWT tokens."""
        mock_user = MagicMock()
        mock_user.id = uuid.uuid4()
        mock_user.email = "test@example.com"
        mock_user.name = "test"
        mock_user.role = "reader"

        with patch(
            "src.api.routes.otp._verify_and_login",
            new_callable=AsyncMock,
        ) as mock_verify:
            mock_verify.return_value = mock_user
            resp = await api_client.post(
                "/api/auth/otp/verify",
                json={"email": "test@example.com", "code": "123456"},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"
        assert "expires_in" in data

    async def test_verify_invalid_code_returns_401(self, api_client: AsyncClient):
        from src.api.errors import APIError

        with patch(
            "src.api.routes.otp._verify_and_login",
            new_callable=AsyncMock,
        ) as mock_verify:
            mock_verify.side_effect = APIError(
                401,
                "INVALID_OTP",
                "Invalid or expired code",
            )
            resp = await api_client.post(
                "/api/auth/otp/verify",
                json={"email": "test@example.com", "code": "999999"},
            )

        assert resp.status_code == 401

    async def test_verify_bad_code_format_returns_422(self, api_client: AsyncClient):
        """Code must be exactly 6 digits."""
        resp = await api_client.post(
            "/api/auth/otp/verify",
            json={"email": "test@example.com", "code": "abc"},
        )
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# GET /api/auth/me
# ---------------------------------------------------------------------------
class TestGetMe:
    async def test_me_returns_user_info(self, api_client: AsyncClient):
        """GET /api/auth/me returns current user info from JWT claims."""
        from src.api.auth import create_access_token

        test_settings = _make_test_settings()
        with patch("src.api.auth.get_settings", return_value=test_settings):
            token = create_access_token(
                subject=str(uuid.uuid4()),
                role="reader",
                email="test@example.com",
            )

        mock_user = MagicMock()
        mock_user.id = uuid.uuid4()
        mock_user.email = "test@example.com"
        mock_user.name = "test"
        mock_user.role = "reader"

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_user

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)

        from contextlib import asynccontextmanager

        @asynccontextmanager
        async def mock_get_session():
            yield mock_session

        with patch("src.api.routes.otp.get_async_session", mock_get_session):
            resp = await api_client.get(
                "/api/auth/me",
                headers={"Authorization": f"Bearer {token}"},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["email"] == "test@example.com"
        assert data["role"] == "reader"

    async def test_me_without_token_returns_403(self, api_client: AsyncClient):
        resp = await api_client.get("/api/auth/me")
        assert resp.status_code == 403

    async def test_me_legacy_token_returns_synthetic_user(self, api_client: AsyncClient):
        """Legacy tokens (no email) return a synthetic user response."""
        from src.api.auth import create_access_token

        test_settings = _make_test_settings()
        with patch("src.api.auth.get_settings", return_value=test_settings):
            token = create_access_token(subject="legacy", role="reader")

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)

        from contextlib import asynccontextmanager

        @asynccontextmanager
        async def mock_get_session():
            yield mock_session

        with patch("src.api.routes.otp.get_async_session", mock_get_session):
            resp = await api_client.get(
                "/api/auth/me",
                headers={"Authorization": f"Bearer {token}"},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["role"] == "reader"
