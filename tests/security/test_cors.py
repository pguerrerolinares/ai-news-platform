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
