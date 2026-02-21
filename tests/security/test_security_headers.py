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
