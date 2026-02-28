"""Integration tests for GET /api/items endpoints against real PostgreSQL."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from tests.integration.conftest import seed_news_item

pytestmark = [pytest.mark.integration, pytest.mark.asyncio(loop_scope="session")]


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
