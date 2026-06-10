"""Tests for src.api.app -- FastAPI endpoints (health, metrics)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from src.api.app import app


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
@pytest.fixture()
async def api_client() -> AsyncClient:
    """Create an httpx AsyncClient wired to the FastAPI app.

    We use a local fixture (rather than the conftest ``client``) so this
    test module is fully self-contained and does not depend on the DB
    fixtures or the lifespan events that call init_db().
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac  # type: ignore[misc]


# ---------------------------------------------------------------------------
# /health endpoint
# ---------------------------------------------------------------------------
class TestHealthEndpoint:
    """Verify /health returns expected responses."""

    async def test_health_returns_200(self, api_client: AsyncClient):
        """Health endpoint returns 200 when DB is connected."""
        # Patch the engine to avoid needing a real database
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock()

        mock_connect = AsyncMock()
        mock_connect.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_connect.__aexit__ = AsyncMock(return_value=False)

        mock_engine = MagicMock()
        mock_engine.connect.return_value = mock_connect

        with patch("src.api.app.get_engine", return_value=mock_engine):
            resp = await api_client.get("/health")

        assert resp.status_code == 200

    async def test_health_returns_status_key(self, api_client: AsyncClient):
        """Response JSON must contain a 'status' key."""
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock()

        mock_connect = AsyncMock()
        mock_connect.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_connect.__aexit__ = AsyncMock(return_value=False)

        mock_engine = MagicMock()
        mock_engine.connect.return_value = mock_connect

        with patch("src.api.app.get_engine", return_value=mock_engine):
            resp = await api_client.get("/health")

        data = resp.json()
        assert "status" in data

    async def test_health_healthy_when_db_ok(self, api_client: AsyncClient):
        """When the DB is reachable, status should be 'healthy'."""
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock()

        mock_connect = AsyncMock()
        mock_connect.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_connect.__aexit__ = AsyncMock(return_value=False)

        mock_engine = MagicMock()
        mock_engine.connect.return_value = mock_connect

        with patch("src.api.app.get_engine", return_value=mock_engine):
            resp = await api_client.get("/health")

        data = resp.json()
        assert data["status"] == "healthy"
        assert data["database"] == "connected"

    async def test_health_unhealthy_when_db_fails(self, api_client: AsyncClient):
        """When the DB is unreachable, status should be 'unhealthy'."""
        mock_connect = AsyncMock()
        mock_connect.__aenter__ = AsyncMock(side_effect=ConnectionError("refused"))
        mock_connect.__aexit__ = AsyncMock(return_value=False)

        mock_engine = MagicMock()
        mock_engine.connect.return_value = mock_connect

        with patch("src.api.app.get_engine", return_value=mock_engine):
            resp = await api_client.get("/health")

        assert resp.status_code == 503
        data = resp.json()
        assert data["status"] == "unhealthy"

    async def test_health_does_not_leak_exception_detail(self, api_client: AsyncClient):
        """The 503 body must not echo the raw exception string (info leak)."""
        mock_connect = AsyncMock()
        mock_connect.__aenter__ = AsyncMock(
            side_effect=ConnectionError("could not connect to secret-host:5432")
        )
        mock_connect.__aexit__ = AsyncMock(return_value=False)

        mock_engine = MagicMock()
        mock_engine.connect.return_value = mock_connect

        with patch("src.api.app.get_engine", return_value=mock_engine):
            resp = await api_client.get("/health")

        assert resp.status_code == 503
        assert "secret-host" not in resp.text
        assert "could not connect" not in resp.text

    async def test_health_returns_503_when_db_fails(self, api_client: AsyncClient):
        """When the DB is unreachable, HTTP status should be 503."""
        mock_connect = AsyncMock()
        mock_connect.__aenter__ = AsyncMock(side_effect=ConnectionError("refused"))
        mock_connect.__aexit__ = AsyncMock(return_value=False)

        mock_engine = MagicMock()
        mock_engine.connect.return_value = mock_connect

        with patch("src.api.app.get_engine", return_value=mock_engine):
            resp = await api_client.get("/health")

        assert resp.status_code == 503
        data = resp.json()
        assert data["status"] == "unhealthy"


# ---------------------------------------------------------------------------
# /metrics endpoint
# ---------------------------------------------------------------------------
class TestMetricsEndpoint:
    """Verify /metrics returns Prometheus output."""

    async def test_metrics_returns_200(self, api_client: AsyncClient):
        resp = await api_client.get("/metrics")
        assert resp.status_code == 200

    async def test_metrics_content_type(self, api_client: AsyncClient):
        resp = await api_client.get("/metrics")
        ct = resp.headers.get("content-type", "")
        assert "text/plain" in ct

    async def test_metrics_contains_prometheus_data(self, api_client: AsyncClient):
        resp = await api_client.get("/metrics")
        body = resp.text
        # Prometheus output should contain at least the app info metric
        assert "ainews" in body

    async def test_metrics_contains_help_lines(self, api_client: AsyncClient):
        resp = await api_client.get("/metrics")
        body = resp.text
        # Prometheus exposition format includes HELP and TYPE lines
        assert "# HELP" in body or "# TYPE" in body


# ---------------------------------------------------------------------------
# Correlation ID header
# ---------------------------------------------------------------------------
class TestCorrelationIdHeader:
    """Verify that responses include the X-Correlation-ID header."""

    async def test_correlation_id_present(self, api_client: AsyncClient):
        resp = await api_client.get("/metrics")
        assert "x-correlation-id" in resp.headers

    async def test_correlation_id_is_string(self, api_client: AsyncClient):
        resp = await api_client.get("/metrics")
        cid = resp.headers["x-correlation-id"]
        assert isinstance(cid, str)
        assert len(cid) > 0


# ---------------------------------------------------------------------------
# Production settings guard
# ---------------------------------------------------------------------------
class TestValidateProductionSettings:
    """_validate_production_settings hard-fails on insecure prod config."""

    @staticmethod
    def _settings(**overrides):
        from src.core.config import Settings

        defaults = {
            "debug": False,
            "jwt_secret": "x" * 64,
            "database_url": "postgresql+asyncpg://x:x@localhost/x",
            "database_url_sync": "postgresql://x:x@localhost/x",
        }
        defaults.update(overrides)
        return Settings(**defaults)

    def test_valid_secret_passes(self):
        from src.api.app import _validate_production_settings

        _validate_production_settings(self._settings(jwt_secret="x" * 64))  # no raise

    def test_default_secret_raises(self):
        from src.api.app import _validate_production_settings

        with pytest.raises(RuntimeError, match="JWT_SECRET"):
            _validate_production_settings(self._settings(jwt_secret="change-me-in-production"))

    def test_short_secret_raises(self):
        from src.api.app import _validate_production_settings

        with pytest.raises(RuntimeError, match="32"):
            _validate_production_settings(self._settings(jwt_secret="x" * 31))

    def test_admin_email_without_resend_raises(self):
        from src.api.app import _validate_production_settings

        with pytest.raises(RuntimeError, match="RESEND_API_KEY"):
            _validate_production_settings(self._settings(admin_email="a@b.com", resend_api_key=""))

    def test_debug_mode_skips_all_checks(self):
        from src.api.app import _validate_production_settings

        # In debug, even a short/default secret is allowed (local dev).
        _validate_production_settings(self._settings(debug=True, jwt_secret="short"))
