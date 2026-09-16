"""Integration tests for GET /api/items endpoints against real PostgreSQL."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import ClassVar

import pytest
from sqlalchemy import event

from tests.integration.conftest import seed_embedding, seed_news_item

pytestmark = [pytest.mark.integration, pytest.mark.asyncio(loop_scope="session")]


async def _capture_sql(integration_engine, coro):
    """Run *coro* while capturing every SQL statement executed on the engine."""
    statements: list[str] = []

    def _capture(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement)

    event.listen(integration_engine.sync_engine, "before_cursor_execute", _capture)
    try:
        result = await coro
    finally:
        event.remove(integration_engine.sync_engine, "before_cursor_execute", _capture)
    return result, statements


class TestListItems:
    async def test_returns_seeded_data(self, client, db_session, auth_headers):
        """Seeded items are returned by GET /api/items."""
        for i in range(5):
            await seed_news_item(db_session, title=f"Item {i}", url=f"https://x.com/{i}")

        resp = await client.get("/api/items", headers=auth_headers)

        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 5

    async def test_filter_by_topic(self, client, db_session, auth_headers):
        """?topic=models returns only items with that topic."""
        await seed_news_item(db_session, title="Models A", topic="models")
        await seed_news_item(db_session, title="Tools B", topic="tools")

        resp = await client.get("/api/items?topic=models", headers=auth_headers)

        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["topic"] == "models"

    async def test_filter_by_source(self, client, db_session, auth_headers):
        """?source=arxiv returns only items from that source."""
        await seed_news_item(db_session, title="HN Item", source="hackernews")
        await seed_news_item(db_session, title="Arxiv Item", source="arxiv")

        resp = await client.get("/api/items?source=arxiv", headers=auth_headers)

        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["source"] == "arxiv"

    async def test_filter_by_date_range(self, client, db_session, auth_headers):
        """?date_from=...&date_to=... returns items in that window."""
        today = datetime.now(tz=UTC)
        yesterday = today - timedelta(days=1)
        three_days_ago = today - timedelta(days=3)

        await seed_news_item(db_session, title="Recent", published_at=yesterday)
        await seed_news_item(db_session, title="Old", published_at=three_days_ago)

        date_from = (today - timedelta(days=2)).strftime("%Y-%m-%d")
        date_to = today.strftime("%Y-%m-%d")
        resp = await client.get(
            f"/api/items?date_from={date_from}&date_to={date_to}",
            headers=auth_headers,
        )

        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["title"] == "Recent"

    async def test_pagination(self, client, db_session, auth_headers):
        """limit and offset paginate correctly."""
        now = datetime.now(tz=UTC)
        for i in range(10):
            await seed_news_item(
                db_session,
                title=f"Page {i}",
                url=f"https://x.com/page-{i}",
                published_at=now - timedelta(minutes=i),  # deterministic order
            )

        resp1 = await client.get("/api/items?limit=3&offset=0", headers=auth_headers)
        resp2 = await client.get("/api/items?limit=3&offset=3", headers=auth_headers)

        assert len(resp1.json()) == 3
        assert len(resp2.json()) == 3
        # No overlap between pages
        ids1 = {item["id"] for item in resp1.json()}
        ids2 = {item["id"] for item in resp2.json()}
        assert ids1.isdisjoint(ids2)


class TestItemsCount:
    async def test_count_matches(self, client, db_session, auth_headers):
        """GET /api/items/count returns correct count."""
        for i in range(4):
            await seed_news_item(db_session, title=f"Count {i}", url=f"https://x.com/c-{i}")

        resp = await client.get("/api/items/count", headers=auth_headers)

        assert resp.status_code == 200
        assert resp.json()["count"] == 4


class TestItemsToday:
    async def test_returns_only_today(self, client, db_session, auth_headers):
        """GET /api/items/today returns only items created today."""
        # created_at defaults to now() via server_default — these are "today"
        await seed_news_item(db_session, title="Today Item", url="https://x.com/today")

        resp = await client.get("/api/items/today", headers=auth_headers)

        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 1
        assert any(item["title"] == "Today Item" for item in data)


def _assert_full_text_not_selected(statements: list[str], context: str) -> None:
    """Fail if any SELECT against news_items includes the heavy full_text column."""
    leaking = [s for s in statements if "FROM news_items" in s and "full_text" in s]
    assert not leaking, f"{context}: full_text leaked into SQL: {leaking}"


class TestDeferredHeavyColumns:
    """`full_text`/`search_vector` must never be selected in read listings.

    Uses a `before_cursor_execute` listener to inspect the literal SQL sent to
    PostgreSQL — a direct, falsifiable check that the ORM-level `defer()` is
    actually applied (unlike counting queries, which would stay constant here
    regardless of `defer()` since `NewsItemResponse` never triggers a lazy
    load on these columns after the session closes).
    """

    _LIST_PATHS: ClassVar[list[str]] = [
        "/api/items",
        "/api/items/today",
        "/api/items/trending",
        "/api/items/top",
        "/api/items/latest?sort=recent",
    ]

    @pytest.mark.parametrize("path", _LIST_PATHS)
    async def test_list_endpoints_defer_full_text(
        self, client, db_session, integration_engine, auth_headers, path
    ):
        await seed_news_item(
            db_session,
            full_text="x" * 5000,
            trending=True,
            composite_score=1.0,
        )

        resp, statements = await _capture_sql(
            integration_engine, client.get(path, headers=auth_headers)
        )

        assert resp.status_code == 200
        assert resp.json(), f"{path}: expected at least one seeded item in the response"
        _assert_full_text_not_selected(statements, path)

    async def test_latest_default_sort_defers_full_text(
        self, client, db_session, integration_engine, auth_headers
    ):
        """`/api/items/latest` with the default sort (relevance) goes through
        FeedBuilder._fetch_candidates, a separate query from the ones above.
        """
        await seed_news_item(
            db_session,
            full_text="x" * 5000,
            composite_score=1.0,
            published_at=datetime.now(tz=UTC),
        )

        resp, statements = await _capture_sql(
            integration_engine, client.get("/api/items/latest", headers=auth_headers)
        )

        assert resp.status_code == 200
        assert resp.json(), "expected at least one seeded item in the response"
        _assert_full_text_not_selected(statements, "/api/items/latest (default sort)")

    async def test_by_date_defers_full_text(
        self, client, db_session, integration_engine, auth_headers
    ):
        today = datetime.now(tz=UTC).date()
        await seed_news_item(db_session, full_text="x" * 5000, published_at=datetime.now(tz=UTC))

        resp, statements = await _capture_sql(
            integration_engine,
            client.get(f"/api/items/by-date/{today.isoformat()}", headers=auth_headers),
        )

        assert resp.status_code == 200
        assert resp.json()
        _assert_full_text_not_selected(statements, "/api/items/by-date/{date}")

    # NOTE: GET /api/items/{item_id} is a detail endpoint (Task 3) and now selects
    # full_text on purpose — it is intentionally excluded from this class. See
    # TestGetItemDetail below for its full_text/discussion_url/engagement contract.

    async def test_similar_items_defers_full_text(
        self, client, db_session, integration_engine, auth_headers
    ):
        from tests.integration.conftest import seed_embedding

        item = await seed_news_item(db_session, full_text="x" * 5000)
        await seed_embedding(db_session, item)
        other = await seed_news_item(db_session, full_text="y" * 5000, url="https://x.com/other")
        await seed_embedding(db_session, other, vector=[0.2] * 512)

        resp, statements = await _capture_sql(
            integration_engine,
            client.get(f"/api/items/{item.id}/similar", headers=auth_headers),
        )

        assert resp.status_code == 200
        _assert_full_text_not_selected(statements, "/api/items/{item_id}/similar")


class TestSimilarItemsNotFound:
    """GET /{item_id}/similar must not claim EMBEDDING_NOT_FOUND for an item
    that doesn't exist at all — that used to make the MCP client's find_similar
    lie ("item exists but has no embedding yet") about items that don't exist
    (finding 2, 2026-09-16 whole-branch review).
    """

    @pytest.fixture(autouse=True)
    def _reset_items_limiter(self):
        from src.api.routes.items import limiter

        limiter.reset()

    async def test_nonexistent_item_returns_404_not_found(self, client, auth_headers):
        resp = await client.get(f"/api/items/{uuid.uuid4()}/similar", headers=auth_headers)

        assert resp.status_code == 404
        assert resp.json()["error"]["code"] == "NOT_FOUND"

    async def test_existing_item_without_embedding_returns_embedding_not_found(
        self, client, db_session, auth_headers
    ):
        item = await seed_news_item(db_session)

        resp = await client.get(f"/api/items/{item.id}/similar", headers=auth_headers)

        assert resp.status_code == 404
        assert resp.json()["error"]["code"] == "EMBEDDING_NOT_FOUND"

    async def test_existing_item_with_embedding_still_returns_neighbours(
        self, client, db_session, auth_headers
    ):
        item = await seed_news_item(db_session)
        await seed_embedding(db_session, item)
        other = await seed_news_item(db_session, url="https://x.com/other")
        await seed_embedding(db_session, other, vector=[0.1] * 512)

        resp = await client.get(f"/api/items/{item.id}/similar", headers=auth_headers)

        assert resp.status_code == 200
        assert len(resp.json()) == 1


class TestGetItemDetail:
    @pytest.fixture(autouse=True)
    def _reset_items_limiter(self):
        from src.api.routes.items import limiter

        limiter.reset()

    async def test_detail_has_full_text_discussion_and_engagement(
        self, client, db_session, auth_headers
    ):
        item = await seed_news_item(
            db_session,
            source="hackernews",
            score=321,
            full_text="Full body of the story.",
            metadata_={"hn_url": "https://news.ycombinator.com/item?id=42"},
        )

        resp = await client.get(f"/api/items/{item.id}", headers=auth_headers)

        assert resp.status_code == 200
        data = resp.json()
        assert data["full_text"] == "Full body of the story."
        assert data["discussion_url"] == "https://news.ycombinator.com/item?id=42"
        assert data["engagement"] == {"kind": "points", "value": 321}

    async def test_detail_engagement_null_for_arxiv(self, client, db_session, auth_headers):
        item = await seed_news_item(db_session, source="arxiv", score=0, metadata_={})

        resp = await client.get(f"/api/items/{item.id}", headers=auth_headers)

        assert resp.status_code == 200
        data = resp.json()
        assert data["engagement"] is None
        assert data["discussion_url"] is None
