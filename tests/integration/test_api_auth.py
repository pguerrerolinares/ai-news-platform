"""Integration tests for authentication flow."""

from __future__ import annotations

import pytest

from src.core.config import get_settings

pytestmark = [pytest.mark.integration, pytest.mark.asyncio(loop_scope="session")]


class TestAuthFlow:
    async def test_login_returns_jwt(self, client):
        """POST /api/auth/token with correct password returns JWT."""
        settings = get_settings()
        resp = await client.post(
            "/api/auth/token",
            json={"password": settings.shared_password},
        )

        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    async def test_protected_route_with_jwt(self, client):
        """Login, then use JWT to access protected route."""
        settings = get_settings()

        # Login
        login_resp = await client.post(
            "/api/auth/token",
            json={"password": settings.shared_password},
        )
        token = login_resp.json()["access_token"]

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
