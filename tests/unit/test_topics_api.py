"""Tests for GET /api/topics endpoint."""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from src.api.app import app


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
        assert "modelos" in topics
        assert "herramientas" in topics
        assert "papers" in topics

    async def test_no_auth_required(self, api_client: AsyncClient):
        """Topics endpoint should be accessible without JWT."""
        resp = await api_client.get("/api/topics")
        assert resp.status_code == 200
