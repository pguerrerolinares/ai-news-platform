"""Unit tests for items API endpoints (/today and /top)."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from src.api.app import app
from src.api.auth import require_auth
from src.core.database import get_session


def _make_mock_session():
    """Mock session that handles various query patterns for items."""
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


class TestTodayEndpoint:
    async def test_today_returns_200(self, api_client: AsyncClient):
        resp = await api_client.get("/api/items/today")
        assert resp.status_code == 200

    async def test_today_returns_list(self, api_client: AsyncClient):
        resp = await api_client.get("/api/items/today")
        assert isinstance(resp.json(), list)

    async def test_today_accepts_topic_filter(self, api_client: AsyncClient):
        resp = await api_client.get("/api/items/today", params={"topic": "models"})
        assert resp.status_code == 200

    async def test_today_accepts_limit_param(self, api_client: AsyncClient):
        resp = await api_client.get("/api/items/today", params={"limit": 10})
        assert resp.status_code == 200

    async def test_today_accepts_offset_param(self, api_client: AsyncClient):
        resp = await api_client.get("/api/items/today", params={"offset": 5})
        assert resp.status_code == 200

    async def test_today_rejects_excessive_limit(self, api_client: AsyncClient):
        resp = await api_client.get("/api/items/today", params={"limit": 999})
        assert resp.status_code == 422

    async def test_today_includes_total_count_header(self, api_client: AsyncClient):
        resp = await api_client.get("/api/items/today")
        assert "x-total-count" in resp.headers


class TestLatestEndpoint:
    async def test_latest_returns_200(self, api_client: AsyncClient):
        resp = await api_client.get("/api/items/latest")
        assert resp.status_code == 200

    async def test_latest_returns_list(self, api_client: AsyncClient):
        resp = await api_client.get("/api/items/latest")
        assert isinstance(resp.json(), list)

    async def test_latest_accepts_filters(self, api_client: AsyncClient):
        resp = await api_client.get(
            "/api/items/latest",
            params={"topic": "models", "source": "hackernews", "limit": "10"},
        )
        assert resp.status_code == 200

    async def test_latest_has_total_count_header(self, api_client: AsyncClient):
        resp = await api_client.get("/api/items/latest")
        assert "x-total-count" in resp.headers


class TestTopEndpoint:
    async def test_top_returns_200(self, api_client: AsyncClient):
        resp = await api_client.get("/api/items/top")
        assert resp.status_code == 200

    async def test_top_returns_list(self, api_client: AsyncClient):
        resp = await api_client.get("/api/items/top")
        assert isinstance(resp.json(), list)

    async def test_top_accepts_days_param(self, api_client: AsyncClient):
        resp = await api_client.get("/api/items/top", params={"days": 14})
        assert resp.status_code == 200

    async def test_top_accepts_topic_filter(self, api_client: AsyncClient):
        resp = await api_client.get("/api/items/top", params={"topic": "models"})
        assert resp.status_code == 200

    async def test_top_accepts_source_filter(self, api_client: AsyncClient):
        resp = await api_client.get("/api/items/top", params={"source": "hackernews"})
        assert resp.status_code == 200

    async def test_top_accepts_limit_param(self, api_client: AsyncClient):
        resp = await api_client.get("/api/items/top", params={"limit": 5})
        assert resp.status_code == 200

    async def test_top_accepts_large_days(self, api_client: AsyncClient):
        resp = await api_client.get("/api/items/top", params={"days": 3650})
        assert resp.status_code == 200

    async def test_top_rejects_excessive_days(self, api_client: AsyncClient):
        resp = await api_client.get("/api/items/top", params={"days": 3651})
        assert resp.status_code == 422

    async def test_top_rejects_excessive_limit(self, api_client: AsyncClient):
        resp = await api_client.get("/api/items/top", params={"limit": 999})
        assert resp.status_code == 422

    async def test_top_includes_total_count_header(self, api_client: AsyncClient):
        resp = await api_client.get("/api/items/top")
        assert "x-total-count" in resp.headers
