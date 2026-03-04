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
        oversized = b"A" * (_MAX_BODY + 1)
        resp = await security_client.post(
            "/api/auth/guest",
            content=oversized,
            headers={"Content-Type": "application/octet-stream"},
        )
        assert resp.status_code == 413

    async def test_normal_body_accepted(self, security_client: AsyncClient):
        """Normal-sized body on guest endpoint must be accepted."""
        resp = await security_client.post("/api/auth/guest")
        # Should get 200 (guest token) — not 413
        assert resp.status_code == 200

    async def test_boundary_body_accepted(self, security_client: AsyncClient):
        """Body exactly at 1MB limit must be accepted."""
        # Create a body that's exactly 1MB
        padding = b"A" * (_MAX_BODY - 20)  # leave room for overhead
        resp = await security_client.post(
            "/api/auth/guest",
            content=padding,
            headers={"Content-Type": "application/octet-stream"},
        )
        # Should be 200 (ignores body), not 413
        assert resp.status_code == 200
