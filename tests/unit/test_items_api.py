"""Unit tests for items API endpoints (/today, /top, and /{item_id})."""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from src.api.app import app
from src.api.auth import require_auth_or_guest
from src.core.database import get_session
from src.core.models import NewsItem


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
    app.dependency_overrides[require_auth_or_guest] = lambda: "test-user"
    app.dependency_overrides[get_session] = _mock_get_session
    yield
    app.dependency_overrides.pop(require_auth_or_guest, None)
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

    async def test_latest_accepts_diversity_param(self, api_client: AsyncClient):
        resp = await api_client.get(
            "/api/items/latest",
            params={"diversity": "0.5"},
        )
        assert resp.status_code == 200

    async def test_latest_rejects_invalid_diversity(self, api_client: AsyncClient):
        resp = await api_client.get(
            "/api/items/latest",
            params={"diversity": "1.5"},
        )
        assert resp.status_code == 422

    async def test_latest_sort_recent_works(self, api_client: AsyncClient):
        resp = await api_client.get(
            "/api/items/latest",
            params={"sort": "recent"},
        )
        assert resp.status_code == 200
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


class TestGetItemEndpoint:
    """Tests for GET /api/items/{item_id}."""

    def _make_news_item(self, item_id: uuid.UUID) -> NewsItem:
        """Build a minimal NewsItem ORM instance for mock returns."""
        from datetime import UTC, datetime

        item = MagicMock(spec=NewsItem)
        item.id = item_id
        item.title = "Test Article"
        item.summary = "A test summary"
        item.url = "https://example.com/article"
        item.source = "hackernews"
        item.topic = "models"
        item.relevance_score = 0.9
        item.dev_value_score = 0.8
        item.credibility_score = 0.7
        item.priority = 1
        item.trending = False
        item.published_at = None
        item.created_at = datetime(2024, 1, 1, tzinfo=UTC)
        item.author = None
        item.score = 42
        item.composite_score = 0.85
        return item

    async def test_get_item_found_returns_200(self, api_client: AsyncClient):
        """Returns 200 with the item payload when the item exists."""
        item_id = uuid.uuid4()
        item = self._make_news_item(item_id)

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = item
        mock_result.scalar_one.return_value = 0
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        mock_result.scalars.return_value = mock_scalars

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)

        async def _found_session():
            yield mock_session

        app.dependency_overrides[get_session] = _found_session
        resp = await api_client.get(f"/api/items/{item_id}")
        app.dependency_overrides[get_session] = _mock_get_session

        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == str(item_id)
        assert data["title"] == "Test Article"
        assert data["source"] == "hackernews"
        assert data["score"] == 42

    async def test_get_item_not_found_returns_404(self, api_client: AsyncClient):
        """Returns 404 with error body when no item matches the given UUID."""
        item_id = uuid.uuid4()

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_result.scalar_one.return_value = 0
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        mock_result.scalars.return_value = mock_scalars

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)

        async def _missing_session():
            yield mock_session

        app.dependency_overrides[get_session] = _missing_session
        resp = await api_client.get(f"/api/items/{item_id}")
        app.dependency_overrides[get_session] = _mock_get_session

        assert resp.status_code == 404
        body = resp.json()
        assert body["error"]["code"] == "NOT_FOUND"

    async def test_get_item_malformed_uuid_returns_422(self, api_client: AsyncClient):
        """FastAPI path validation rejects non-UUID values with 422."""
        resp = await api_client.get("/api/items/not-a-valid-uuid")
        assert resp.status_code == 422

    async def test_get_item_requires_auth(self, api_client: AsyncClient):
        """Returns 401 when auth dependency is not satisfied."""
        from src.api.errors import APIError

        app.dependency_overrides.pop(require_auth_or_guest, None)
        app.dependency_overrides[require_auth_or_guest] = lambda: (_ for _ in ()).throw(
            APIError(401, "UNAUTHORIZED", "Authentication required")
        )
        try:
            item_id = uuid.uuid4()
            resp = await api_client.get(f"/api/items/{item_id}")
            assert resp.status_code == 401
        finally:
            app.dependency_overrides[require_auth_or_guest] = lambda: "test-user"
