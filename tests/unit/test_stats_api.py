"""Unit tests for stats API endpoints."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from src.api.app import app
from src.api.auth import require_auth
from src.core.database import get_session


def _make_mock_session():
    """Mock session that handles various query patterns for stats."""
    mock_result = MagicMock()
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = []
    mock_result.scalars.return_value = mock_scalars
    mock_result.scalar_one.return_value = 0
    mock_result.scalar_one_or_none.return_value = None
    mock_result.all.return_value = []

    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(return_value=mock_result)
    return mock_session


async def _mock_get_session():
    yield _make_mock_session()


@pytest.fixture(autouse=True)
def _override_dependencies():
    app.dependency_overrides[require_auth] = lambda: "test-user"
    app.dependency_overrides[get_session] = _mock_get_session
    yield
    app.dependency_overrides.pop(require_auth, None)
    app.dependency_overrides.pop(get_session, None)


@pytest.fixture()
async def api_client() -> AsyncClient:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac  # type: ignore[misc]


class TestStatsSummary:
    async def test_summary_returns_200(self, api_client: AsyncClient):
        resp = await api_client.get("/api/stats/summary")
        assert resp.status_code == 200

    async def test_summary_returns_expected_fields(self, api_client: AsyncClient):
        resp = await api_client.get("/api/stats/summary")
        data = resp.json()
        assert "total_items" in data
        assert "items_today" in data
        assert "sources_count" in data
        assert "topics_count" in data
        assert "trending_today" in data

    async def test_summary_requires_auth(self, api_client: AsyncClient):
        app.dependency_overrides.pop(require_auth, None)
        resp = await api_client.get("/api/stats/summary")
        assert resp.status_code == 403


class TestStatsBySource:
    async def test_by_source_returns_200(self, api_client: AsyncClient):
        resp = await api_client.get("/api/stats/by-source")
        assert resp.status_code == 200

    async def test_by_source_returns_list(self, api_client: AsyncClient):
        resp = await api_client.get("/api/stats/by-source")
        assert isinstance(resp.json(), list)


class TestStatsByTopic:
    async def test_by_topic_returns_200(self, api_client: AsyncClient):
        resp = await api_client.get("/api/stats/by-topic")
        assert resp.status_code == 200

    async def test_by_topic_returns_list(self, api_client: AsyncClient):
        resp = await api_client.get("/api/stats/by-topic")
        assert isinstance(resp.json(), list)


class TestStatsByDate:
    async def test_by_date_returns_200(self, api_client: AsyncClient):
        resp = await api_client.get("/api/stats/by-date")
        assert resp.status_code == 200

    async def test_by_date_returns_list(self, api_client: AsyncClient):
        resp = await api_client.get("/api/stats/by-date")
        assert isinstance(resp.json(), list)

    async def test_by_date_accepts_days_param(self, api_client: AsyncClient):
        resp = await api_client.get("/api/stats/by-date", params={"days": 7})
        assert resp.status_code == 200

    async def test_by_date_rejects_excessive_days(self, api_client: AsyncClient):
        resp = await api_client.get("/api/stats/by-date", params={"days": 999})
        assert resp.status_code == 422


class TestStatsByTopicDate:
    async def test_returns_200(self, api_client: AsyncClient):
        resp = await api_client.get("/api/stats/by-topic-date")
        assert resp.status_code == 200

    async def test_returns_list(self, api_client: AsyncClient):
        resp = await api_client.get("/api/stats/by-topic-date")
        assert isinstance(resp.json(), list)

    async def test_accepts_days_param(self, api_client: AsyncClient):
        resp = await api_client.get("/api/stats/by-topic-date", params={"days": 7})
        assert resp.status_code == 200

    async def test_rejects_excessive_days(self, api_client: AsyncClient):
        resp = await api_client.get("/api/stats/by-topic-date", params={"days": 999})
        assert resp.status_code == 422


class TestStatsBySourceDate:
    async def test_returns_200(self, api_client: AsyncClient):
        resp = await api_client.get("/api/stats/by-source-date")
        assert resp.status_code == 200

    async def test_returns_list(self, api_client: AsyncClient):
        resp = await api_client.get("/api/stats/by-source-date")
        assert isinstance(resp.json(), list)

    async def test_accepts_days_param(self, api_client: AsyncClient):
        resp = await api_client.get("/api/stats/by-source-date", params={"days": 14})
        assert resp.status_code == 200


class TestTrendingTimeline:
    async def test_returns_200(self, api_client: AsyncClient):
        resp = await api_client.get("/api/stats/trending-timeline")
        assert resp.status_code == 200

    async def test_returns_list(self, api_client: AsyncClient):
        resp = await api_client.get("/api/stats/trending-timeline")
        assert isinstance(resp.json(), list)

    async def test_accepts_days_param(self, api_client: AsyncClient):
        resp = await api_client.get("/api/stats/trending-timeline", params={"days": 60})
        assert resp.status_code == 200
