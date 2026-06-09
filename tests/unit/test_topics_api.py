"""Tests for GET /api/topics endpoint."""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from src.api.app import app
from src.api.auth import require_auth_or_guest


@pytest.fixture(autouse=True)
def _override_auth():
    app.dependency_overrides[require_auth_or_guest] = lambda: "test-user"
    yield
    app.dependency_overrides.pop(require_auth_or_guest, None)


@pytest.fixture()
async def api_client() -> AsyncClient:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac  # type: ignore[misc]


class TestTopicsEndpoint:
    """Verify GET /api/topics returns topic list from config."""

    async def test_returns_200(self, api_client: AsyncClient):
        resp = await api_client.get("/api/topics")
        assert resp.status_code == 200

    async def test_returns_topics_list(self, api_client: AsyncClient):
        resp = await api_client.get("/api/topics")
        data = resp.json()
        assert "topics" in data
        assert isinstance(data["topics"], list)
        assert len(data["topics"]) > 0

    async def test_contains_known_topics(self, api_client: AsyncClient):
        resp = await api_client.get("/api/topics")
        topics = resp.json()["topics"]
        assert "models" in topics
        assert "tools" in topics
        assert "papers" in topics

    async def test_requires_auth_or_guest(self, api_client: AsyncClient):
        """Without a token the endpoint is rejected (deny-by-default)."""
        app.dependency_overrides.pop(require_auth_or_guest, None)
        resp = await api_client.get("/api/topics")
        assert resp.status_code in (401, 403)
