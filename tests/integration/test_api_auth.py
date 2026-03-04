"""Integration tests for authentication flow."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from src.api.auth import create_access_token
from src.core.config import get_settings

pytestmark = [pytest.mark.integration, pytest.mark.asyncio(loop_scope="session")]


class TestAuthFlow:
    async def test_guest_endpoint_returns_token(self, client):
        """POST /api/auth/guest returns a guest JWT."""
        resp = await client.post("/api/auth/guest")

        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    async def test_protected_route_with_jwt(self, client):
        """Use a valid JWT to access a protected route."""
        settings = get_settings()

        with patch("src.api.auth.get_settings", return_value=settings):
            token = create_access_token(subject="test-user", role="reader", email="t@test.com")

        # Access protected route
        resp = await client.get(
            "/api/items",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200

    async def test_protected_route_without_jwt(self, client):
        """Access protected route without token returns 403."""
        resp = await client.get("/api/items")
        assert resp.status_code == 403
