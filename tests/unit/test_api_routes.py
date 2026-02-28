"""Tests for API routes -- /api/items and /api/briefings endpoints."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from src.api.app import app
from src.api.auth import require_auth
from src.core.database import get_session


# ---------------------------------------------------------------------------
# Mock session setup
# ---------------------------------------------------------------------------
def _make_mock_session():
    """Create a mock AsyncSession that returns empty results by default.

    Configures:
    - session.execute() -> mock result
    - result.scalars().all() -> []  (for list endpoints)
    - result.scalar_one_or_none() -> None  (for detail endpoints, triggers 404)
    - result.scalar_one() -> 0  (for count endpoint)
    """
    mock_result = MagicMock()

    # For list endpoints: result.scalars().all() -> []
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = []
    mock_result.scalars.return_value = mock_scalars

    # For detail endpoints: result.scalar_one_or_none() -> None
    mock_result.scalar_one_or_none.return_value = None

    # For count endpoint: result.scalar_one() -> 0
    mock_result.scalar_one.return_value = 0

    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(return_value=mock_result)

    return mock_session


async def _mock_get_session():
    """Dependency override that yields a mock session."""
    yield _make_mock_session()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture(autouse=True)
def _override_dependencies():
    """Override get_session and require_auth dependencies for all tests.

    The overrides are removed after each test to avoid leaking state.
    """
    app.dependency_overrides[get_session] = _mock_get_session
    app.dependency_overrides[require_auth] = lambda: "test-user"
    yield
    app.dependency_overrides.pop(get_session, None)
    app.dependency_overrides.pop(require_auth, None)


@pytest.fixture()
async def api_client() -> AsyncClient:
    """Create an httpx AsyncClient wired to the FastAPI app."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac  # type: ignore[misc]


# ---------------------------------------------------------------------------
# GET /api/items
# ---------------------------------------------------------------------------
class TestListItems:
    """Tests for GET /api/items endpoint."""

    async def test_list_items_returns_200(self, api_client: AsyncClient):
        """GET /api/items should return HTTP 200."""
        resp = await api_client.get("/api/items")
        assert resp.status_code == 200

    async def test_list_items_returns_list(self, api_client: AsyncClient):
        """Response body should be a JSON array."""
        resp = await api_client.get("/api/items")
        data = resp.json()
        assert isinstance(data, list)

    async def test_list_items_empty_by_default(self, api_client: AsyncClient):
        """With a mock session returning no items, the list should be empty."""
        resp = await api_client.get("/api/items")
        data = resp.json()
        assert data == []

    async def test_list_items_with_source_filter(self, api_client: AsyncClient):
        """Endpoint should accept ?source= query parameter without error."""
        resp = await api_client.get("/api/items", params={"source": "hackernews"})
        assert resp.status_code == 200

    async def test_list_items_with_pagination(self, api_client: AsyncClient):
        """Endpoint should accept limit and offset query parameters."""
        resp = await api_client.get("/api/items", params={"limit": 10, "offset": 5})
        assert resp.status_code == 200

    async def test_negative_limit_returns_422(self, api_client: AsyncClient):
        """GET /api/items?limit=-1 should return 422 (ge=1 constraint)."""
        resp = await api_client.get("/api/items", params={"limit": -1})
        assert resp.status_code == 422

    async def test_very_large_limit_returns_422(self, api_client: AsyncClient):
        """GET /api/items?limit=99999 should return 422 (le=200 constraint)."""
        resp = await api_client.get("/api/items", params={"limit": 99999})
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# GET /api/items/today
# ---------------------------------------------------------------------------
class TestListTodayItems:
    """Tests for GET /api/items/today endpoint."""

    async def test_today_returns_200(self, api_client: AsyncClient):
        """GET /api/items/today should return HTTP 200."""
        resp = await api_client.get("/api/items/today")
        assert resp.status_code == 200

    async def test_today_returns_list(self, api_client: AsyncClient):
        """Response body should be a JSON array."""
        resp = await api_client.get("/api/items/today")
        data = resp.json()
        assert isinstance(data, list)

    async def test_today_empty_by_default(self, api_client: AsyncClient):
        """With no items in the mock DB, list should be empty."""
        resp = await api_client.get("/api/items/today")
        data = resp.json()
        assert data == []

    async def test_today_accepts_limit_param(self, api_client: AsyncClient):
        """Endpoint should accept ?limit= query parameter."""
        resp = await api_client.get("/api/items/today", params={"limit": 25})
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# GET /api/items/count
# ---------------------------------------------------------------------------
class TestCountItems:
    """Tests for GET /api/items/count endpoint."""

    async def test_count_returns_200(self, api_client: AsyncClient):
        """GET /api/items/count should return HTTP 200."""
        resp = await api_client.get("/api/items/count")
        assert resp.status_code == 200

    async def test_count_response_has_count_key(self, api_client: AsyncClient):
        """Response JSON must include a 'count' key."""
        resp = await api_client.get("/api/items/count")
        data = resp.json()
        assert "count" in data

    async def test_count_returns_zero_for_empty_db(self, api_client: AsyncClient):
        """With empty mock DB, count should be 0."""
        resp = await api_client.get("/api/items/count")
        data = resp.json()
        assert data["count"] == 0

    async def test_count_value_is_integer(self, api_client: AsyncClient):
        """The count value should be an integer."""
        resp = await api_client.get("/api/items/count")
        data = resp.json()
        assert isinstance(data["count"], int)

    async def test_count_with_source_filter(self, api_client: AsyncClient):
        """Endpoint should accept ?source= query parameter."""
        resp = await api_client.get("/api/items/count", params={"source": "arxiv"})
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# GET /api/briefings
# ---------------------------------------------------------------------------
class TestListBriefings:
    """Tests for GET /api/briefings endpoint."""

    async def test_list_briefings_returns_200(self, api_client: AsyncClient):
        """GET /api/briefings should return HTTP 200."""
        resp = await api_client.get("/api/briefings")
        assert resp.status_code == 200

    async def test_list_briefings_returns_list(self, api_client: AsyncClient):
        """Response body should be a JSON array."""
        resp = await api_client.get("/api/briefings")
        data = resp.json()
        assert isinstance(data, list)

    async def test_list_briefings_empty_by_default(self, api_client: AsyncClient):
        """With mock session returning no briefings, the list should be empty."""
        resp = await api_client.get("/api/briefings")
        data = resp.json()
        assert data == []

    async def test_list_briefings_accepts_limit(self, api_client: AsyncClient):
        """Endpoint should accept ?limit= query parameter."""
        resp = await api_client.get("/api/briefings", params={"limit": 7})
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# GET /api/briefings/{date}
# ---------------------------------------------------------------------------
class TestGetBriefingByDate:
    """Tests for GET /api/briefings/{date} endpoint."""

    async def test_nonexistent_briefing_returns_404(self, api_client: AsyncClient):
        """When no briefing exists for the given date, the endpoint returns 404."""
        resp = await api_client.get("/api/briefings/2026-02-17")
        assert resp.status_code == 404

    async def test_404_response_has_error_object(self, api_client: AsyncClient):
        """404 response should include a standardized error object."""
        resp = await api_client.get("/api/briefings/2026-02-17")
        data = resp.json()
        assert "error" in data
        assert "code" in data["error"]

    async def test_invalid_date_returns_422(self, api_client: AsyncClient):
        """An invalid date string should result in 422 validation error."""
        resp = await api_client.get("/api/briefings/not-a-date")
        assert resp.status_code == 422

    async def test_another_date_returns_404(self, api_client: AsyncClient):
        """Any date without a briefing should return 404."""
        resp = await api_client.get("/api/briefings/2025-01-01")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# /api/items/today pagination
# ---------------------------------------------------------------------------
class TestItemsTodayPagination:
    """Tests for /api/items/today pagination."""

    async def test_today_accepts_offset(self, api_client: AsyncClient):
        resp = await api_client.get("/api/items/today", params={"offset": 10})
        assert resp.status_code == 200

    async def test_today_returns_total_count_header(self, api_client: AsyncClient):
        resp = await api_client.get("/api/items/today")
        assert "X-Total-Count" in resp.headers


# ---------------------------------------------------------------------------
# /api/items X-Total-Count header
# ---------------------------------------------------------------------------
class TestItemsListTotalCount:
    """Tests for /api/items X-Total-Count header."""

    async def test_list_items_returns_total_count_header(self, api_client: AsyncClient):
        resp = await api_client.get("/api/items")
        assert "X-Total-Count" in resp.headers


class TestBriefingsPagination:
    """Tests for briefings pagination."""

    async def test_briefing_date_accepts_limit_offset(self, api_client: AsyncClient):
        """GET /api/briefings/{date} should accept limit and offset."""
        resp = await api_client.get(
            "/api/briefings/2026-02-21",
            params={"limit": 10, "offset": 0},
        )
        # 404 is ok (no briefing in mock), we just test params are accepted
        assert resp.status_code in (200, 404)

    async def test_list_briefings_accepts_offset(self, api_client: AsyncClient):
        """GET /api/briefings should accept offset."""
        resp = await api_client.get("/api/briefings", params={"offset": 5})
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# GET /api/items/by-date/{date}
# ---------------------------------------------------------------------------
class TestItemsByDate:
    async def test_by_date_returns_200(self, api_client: AsyncClient):
        resp = await api_client.get("/api/items/by-date/2026-02-22")
        assert resp.status_code == 200

    async def test_by_date_returns_list(self, api_client: AsyncClient):
        resp = await api_client.get("/api/items/by-date/2026-02-22")
        assert isinstance(resp.json(), list)

    async def test_by_date_has_total_count_header(self, api_client: AsyncClient):
        resp = await api_client.get("/api/items/by-date/2026-02-22")
        assert "X-Total-Count" in resp.headers

    async def test_by_date_accepts_filters(self, api_client: AsyncClient):
        resp = await api_client.get(
            "/api/items/by-date/2026-02-22",
            params={"topic": "models", "source": "hackernews", "limit": 10, "offset": 5},
        )
        assert resp.status_code == 200

    async def test_by_date_invalid_date_returns_422(self, api_client: AsyncClient):
        resp = await api_client.get("/api/items/by-date/not-a-date")
        assert resp.status_code == 422

    async def test_by_date_requires_auth(self, api_client: AsyncClient):
        app.dependency_overrides.pop(require_auth, None)
        resp = await api_client.get("/api/items/by-date/2026-02-22")
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# GET /api/briefings/{date} — resilient synthesis
# ---------------------------------------------------------------------------
class TestResilientBriefing:
    """Briefing endpoint should return synthesized response when no DailyBriefing exists."""

    async def test_briefing_no_record_returns_200_when_items_exist(self, api_client: AsyncClient):
        """When no DailyBriefing but items exist for that date, return 200."""
        mock_session = _make_mock_session()
        call_count = 0

        async def _side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            result = MagicMock()
            mock_scalars = MagicMock()
            mock_scalars.all.return_value = []
            result.scalars.return_value = mock_scalars
            if call_count == 1:
                result.scalar_one_or_none.return_value = None  # no briefing
            elif call_count == 2:
                result.scalar_one.return_value = 5  # items exist
            else:
                pass  # items query
            return result

        mock_session.execute = AsyncMock(side_effect=_side_effect)

        async def _session_override():
            yield mock_session

        app.dependency_overrides[get_session] = _session_override
        resp = await api_client.get("/api/briefings/2026-02-22")
        assert resp.status_code == 200
        data = resp.json()
        assert data["date"] == "2026-02-22"
        assert data["generated_at"] is None
        assert data["total_items"] is None

    async def test_briefing_no_record_no_items_returns_404(self, api_client: AsyncClient):
        """When no DailyBriefing and no items, return 404."""
        resp = await api_client.get("/api/briefings/2026-02-22")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# GET /api/items/trending
# ---------------------------------------------------------------------------
class TestTrendingItems:
    async def test_trending_returns_200(self, api_client: AsyncClient):
        resp = await api_client.get("/api/items/trending")
        assert resp.status_code == 200

    async def test_trending_returns_list(self, api_client: AsyncClient):
        resp = await api_client.get("/api/items/trending")
        assert isinstance(resp.json(), list)

    async def test_trending_has_total_count(self, api_client: AsyncClient):
        resp = await api_client.get("/api/items/trending")
        assert "X-Total-Count" in resp.headers

    async def test_trending_accepts_filters(self, api_client: AsyncClient):
        resp = await api_client.get(
            "/api/items/trending",
            params={"topic": "models", "source": "hackernews", "days": 14, "limit": 5},
        )
        assert resp.status_code == 200

    async def test_trending_rejects_excessive_days(self, api_client: AsyncClient):
        resp = await api_client.get("/api/items/trending", params={"days": 999})
        assert resp.status_code == 422

    async def test_trending_requires_auth(self, api_client: AsyncClient):
        app.dependency_overrides.pop(require_auth, None)
        resp = await api_client.get("/api/items/trending")
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# GET /api/items/{item_id}/similar
# ---------------------------------------------------------------------------
class TestSimilarItems:
    async def test_similar_returns_404_when_no_embedding(self, api_client: AsyncClient):
        """Default mock returns None for scalar_one_or_none — no embedding."""
        item_id = str(uuid.uuid4())
        resp = await api_client.get(f"/api/items/{item_id}/similar")
        assert resp.status_code == 404

    async def test_similar_accepts_limit_param(self, api_client: AsyncClient):
        item_id = str(uuid.uuid4())
        resp = await api_client.get(f"/api/items/{item_id}/similar", params={"limit": 3})
        # 404 because no embedding, but param is accepted (not 422)
        assert resp.status_code == 404

    async def test_similar_rejects_excessive_limit(self, api_client: AsyncClient):
        item_id = str(uuid.uuid4())
        resp = await api_client.get(f"/api/items/{item_id}/similar", params={"limit": 999})
        assert resp.status_code == 422

    async def test_similar_requires_auth(self, api_client: AsyncClient):
        app.dependency_overrides.pop(require_auth, None)
        item_id = str(uuid.uuid4())
        resp = await api_client.get(f"/api/items/{item_id}/similar")
        assert resp.status_code == 403

    async def test_similar_invalid_uuid_returns_422(self, api_client: AsyncClient):
        resp = await api_client.get("/api/items/not-a-uuid/similar")
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# GET /api/items/top
# ---------------------------------------------------------------------------
class TestTopItems:
    async def test_returns_200(self, api_client: AsyncClient):
        resp = await api_client.get("/api/items/top")
        assert resp.status_code == 200

    async def test_returns_list(self, api_client: AsyncClient):
        resp = await api_client.get("/api/items/top")
        assert isinstance(resp.json(), list)

    async def test_accepts_filters(self, api_client: AsyncClient):
        resp = await api_client.get(
            "/api/items/top",
            params={"days": 14, "limit": 5, "topic": "papers", "source": "arxiv"},
        )
        assert resp.status_code == 200

    async def test_rejects_excessive_days(self, api_client: AsyncClient):
        resp = await api_client.get("/api/items/top", params={"days": 999})
        assert resp.status_code == 422

    async def test_requires_auth(self, api_client: AsyncClient):
        app.dependency_overrides.pop(require_auth, None)
        resp = await api_client.get("/api/items/top")
        assert resp.status_code == 403
