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
        resp = await security_client.post("/api/auth/token", json={"password": "test-password"})
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
