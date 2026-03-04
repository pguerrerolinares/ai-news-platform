"""Tests for GET /api/search -- full-text search endpoint."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from src.api.app import app
from src.api.auth import require_auth_or_guest
from src.core.database import get_session


# ---------------------------------------------------------------------------
# Mock helpers
# ---------------------------------------------------------------------------
def _make_mock_news_item(**overrides):
    """Create a mock NewsItem ORM object."""
    defaults = {
        "id": uuid.uuid4(),
        "title": "Test AI Article",
        "summary": "A summary of the article",
        "url": "https://example.com/article",
        "source": "hackernews",
        "topic": "models",
        "relevance_score": 0.9,
        "dev_value_score": 0.8,
        "credibility_score": 0.95,
        "priority": 1,
        "trending": False,
        "published_at": datetime(2026, 2, 15, 12, 0, tzinfo=UTC),
        "created_at": datetime(2026, 2, 15, 12, 0, tzinfo=UTC),
        "author": "test-author",
        "score": 42,
    }
    defaults.update(overrides)
    item = MagicMock()
    for k, v in defaults.items():
        setattr(item, k, v)
    return item


def _make_mock_session(items=None):
    """Create a mock AsyncSession that returns the given items."""
    if items is None:
        items = []

    mock_result = MagicMock()
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = items
    mock_result.scalars.return_value = mock_scalars

    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(return_value=mock_result)

    return mock_session


async def _mock_get_session_empty():
    """Dependency override that yields a mock session with no results."""
    yield _make_mock_session([])


async def _mock_get_session_with_items():
    """Dependency override that yields a mock session with sample items."""
    items = [
        _make_mock_news_item(title="GPT-5 Released", topic="models", score=100),
        _make_mock_news_item(title="New AI Framework", topic="tools", score=80),
        _make_mock_news_item(title="LLM Research Paper", topic="papers", score=60),
    ]
    yield _make_mock_session(items)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture(autouse=True)
def _override_dependencies():
    """Override auth and session dependencies for all tests.

    Auth is bypassed. Session is set to empty by default (individual tests
    can override the session dependency again).
    """
    app.dependency_overrides[require_auth_or_guest] = lambda: "test-user"
    app.dependency_overrides[get_session] = _mock_get_session_empty
    yield
    app.dependency_overrides.pop(require_auth_or_guest, None)
    app.dependency_overrides.pop(get_session, None)


@pytest.fixture()
async def api_client() -> AsyncClient:
    """Create an httpx AsyncClient wired to the FastAPI app."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Basic search
# ---------------------------------------------------------------------------
class TestSearchBasic:
    """Basic search endpoint tests."""

    async def test_search_returns_200(self, api_client: AsyncClient):
        """GET /api/search?q=test should return HTTP 200."""
        resp = await api_client.get("/api/search", params={"q": "test"})
        assert resp.status_code == 200

    async def test_search_returns_list(self, api_client: AsyncClient):
        """Response should be a JSON array."""
        resp = await api_client.get("/api/search", params={"q": "test"})
        data = resp.json()
        assert isinstance(data, list)

    async def test_search_empty_results(self, api_client: AsyncClient):
        """With no matching items, the response should be an empty list."""
        resp = await api_client.get("/api/search", params={"q": "nonexistent"})
        data = resp.json()
        assert data == []

    async def test_search_with_results(self, api_client: AsyncClient):
        """When items match, the response should contain them."""
        app.dependency_overrides[get_session] = _mock_get_session_with_items
        resp = await api_client.get("/api/search", params={"q": "GPT"})
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) == 3  # mock returns all 3 items regardless of query

    async def test_search_result_has_expected_fields(self, api_client: AsyncClient):
        """Each result should have the NewsItemResponse fields."""
        app.dependency_overrides[get_session] = _mock_get_session_with_items
        resp = await api_client.get("/api/search", params={"q": "AI"})
        data = resp.json()
        assert len(data) > 0
        item = data[0]
        assert "id" in item
        assert "title" in item
        assert "source" in item
        assert "created_at" in item


# ---------------------------------------------------------------------------
# Auth requirement
# ---------------------------------------------------------------------------
class TestSearchAuth:
    """Verify that the search endpoint requires authentication."""

    async def test_search_requires_auth(self, api_client: AsyncClient):
        """Without auth override, search should return 403 (no token)."""
        # Remove the auth override so the real dependency runs
        app.dependency_overrides.pop(require_auth_or_guest, None)
        resp = await api_client.get("/api/search", params={"q": "test"})
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------
class TestSearchValidation:
    """Validate query parameter constraints."""

    async def test_empty_query_returns_422(self, api_client: AsyncClient):
        """GET /api/search without 'q' parameter should return 422."""
        resp = await api_client.get("/api/search")
        assert resp.status_code == 422

    async def test_empty_string_query_returns_422(self, api_client: AsyncClient):
        """GET /api/search?q= (empty string) should return 422."""
        resp = await api_client.get("/api/search", params={"q": ""})
        assert resp.status_code == 422

    async def test_limit_too_large_returns_422(self, api_client: AsyncClient):
        """Limit above 200 should return 422."""
        resp = await api_client.get("/api/search", params={"q": "test", "limit": 999})
        assert resp.status_code == 422

    async def test_limit_zero_returns_422(self, api_client: AsyncClient):
        """Limit of 0 should return 422."""
        resp = await api_client.get("/api/search", params={"q": "test", "limit": 0})
        assert resp.status_code == 422

    async def test_sql_injection_attempt_is_safe(self, api_client: AsyncClient):
        """SQL injection in query parameter must not cause a 500 error."""
        resp = await api_client.get("/api/search", params={"q": "'; DROP TABLE--"})
        assert resp.status_code in (200, 422)
        assert resp.status_code != 500


# ---------------------------------------------------------------------------
# Filters
# ---------------------------------------------------------------------------
class TestSearchFilters:
    """Verify that optional filter parameters are accepted."""

    async def test_topic_filter_accepted(self, api_client: AsyncClient):
        """The ?topic= parameter should be accepted."""
        resp = await api_client.get("/api/search", params={"q": "test", "topic": "models"})
        assert resp.status_code == 200

    async def test_date_from_filter_accepted(self, api_client: AsyncClient):
        """The ?date_from= parameter should be accepted."""
        resp = await api_client.get("/api/search", params={"q": "test", "date_from": "2026-01-01"})
        assert resp.status_code == 200

    async def test_date_to_filter_accepted(self, api_client: AsyncClient):
        """The ?date_to= parameter should be accepted."""
        resp = await api_client.get("/api/search", params={"q": "test", "date_to": "2026-12-31"})
        assert resp.status_code == 200

    async def test_date_range_filter_accepted(self, api_client: AsyncClient):
        """Both date filters together should be accepted."""
        resp = await api_client.get(
            "/api/search",
            params={"q": "test", "date_from": "2026-01-01", "date_to": "2026-12-31"},
        )
        assert resp.status_code == 200

    async def test_all_filters_together(self, api_client: AsyncClient):
        """All optional filters combined should be accepted."""
        resp = await api_client.get(
            "/api/search",
            params={
                "q": "test",
                "topic": "papers",
                "date_from": "2026-01-01",
                "date_to": "2026-12-31",
                "limit": 10,
            },
        )
        assert resp.status_code == 200

    async def test_limit_parameter_accepted(self, api_client: AsyncClient):
        """The ?limit= parameter should work within bounds."""
        resp = await api_client.get("/api/search", params={"q": "test", "limit": 25})
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Pagination
# ---------------------------------------------------------------------------
class TestSearchPagination:
    """Tests for search offset and sort_by parameters."""

    async def test_search_accepts_offset_parameter(self, api_client: AsyncClient):
        """Search endpoint should accept offset query parameter."""
        resp = await api_client.get("/api/search", params={"q": "test", "offset": 10})
        assert resp.status_code == 200

    async def test_search_accepts_sort_by_parameter(self, api_client: AsyncClient):
        """Search endpoint should accept sort_by query parameter."""
        for sort in ["relevance", "date", "score"]:
            resp = await api_client.get("/api/search", params={"q": "test", "sort_by": sort})
            assert resp.status_code == 200

    async def test_search_invalid_sort_by_rejected(self, api_client: AsyncClient):
        """Search endpoint should reject invalid sort_by values."""
        resp = await api_client.get("/api/search", params={"q": "test", "sort_by": "invalid"})
        assert resp.status_code == 422

    async def test_search_returns_total_count_header(self, api_client: AsyncClient):
        """Search endpoint should return X-Total-Count header."""
        resp = await api_client.get("/api/search", params={"q": "test"})
        assert "X-Total-Count" in resp.headers
