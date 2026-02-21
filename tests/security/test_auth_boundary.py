"""Security tests for auth boundary enforcement on all protected endpoints."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

pytestmark = [pytest.mark.security, pytest.mark.asyncio(loop_scope="session")]

# Every protected endpoint with its HTTP method and required params
_PROTECTED_ENDPOINTS = [
    ("GET", "/api/items", None),
    ("GET", "/api/items/count", None),
    ("GET", "/api/items/today", None),
    ("GET", "/api/search", {"q": "test"}),
    ("GET", "/api/briefings/2026-01-01", None),
    ("GET", "/api/briefings", None),
    ("POST", "/api/chat", None),
]


class TestAuthBoundary:
    """Verify every protected endpoint rejects unauthenticated requests."""

    @pytest.mark.parametrize(
        ("method", "path", "params"),
        _PROTECTED_ENDPOINTS,
        ids=[f"{m} {p}" for m, p, _ in _PROTECTED_ENDPOINTS],
    )
    async def test_all_protected_endpoints_require_auth(
        self, security_client: AsyncClient, method: str, path: str, params: dict | None
    ):
        """Every protected endpoint must return 403 without auth."""
        if method == "GET":
            resp = await security_client.get(path, params=params)
        else:
            resp = await security_client.post(path, json={"question": "test?"})
        assert resp.status_code == 403, f"{method} {path} returned {resp.status_code}, expected 403"

    async def test_empty_bearer_token(self, security_client: AsyncClient):
        """Empty Bearer token must be rejected."""
        resp = await security_client.get("/api/items", headers={"Authorization": "Bearer "})
        assert resp.status_code in (401, 403)

    async def test_non_jwt_bearer(self, security_client: AsyncClient):
        """Non-JWT string as Bearer token must be rejected."""
        resp = await security_client.get(
            "/api/items", headers={"Authorization": "Bearer this-is-not-a-jwt"}
        )
        assert resp.status_code == 401

    async def test_wrong_auth_scheme(self, security_client: AsyncClient):
        """Basic auth scheme must be rejected (server expects Bearer)."""
        resp = await security_client.get(
            "/api/items", headers={"Authorization": "Basic dXNlcjpwYXNz"}
        )
        assert resp.status_code == 403
