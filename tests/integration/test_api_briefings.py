"""Integration tests for GET /api/briefings endpoints."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import event

from tests.integration.conftest import seed_briefing, seed_news_item

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


class TestListBriefings:
    async def test_returns_seeded_briefings(self, client, db_session, auth_headers):
        """GET /api/briefings returns briefing summaries."""
        today = datetime.now(tz=UTC).date()
        yesterday = today - timedelta(days=1)

        await seed_briefing(db_session, date=today, total_items=10)
        await seed_briefing(db_session, date=yesterday, total_items=5)

        resp = await client.get("/api/briefings", headers=auth_headers)

        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2


class TestGetBriefingByDate:
    async def test_includes_items_for_date(self, client, db_session, auth_headers):
        """GET /api/briefings/{date} returns briefing with items."""
        today = datetime.now(tz=UTC).date()
        await seed_briefing(db_session, date=today, total_items=2)
        # Seed items — created_at defaults to now() via server_default
        await seed_news_item(db_session, title="Today A", url="https://x.com/ba")
        await seed_news_item(db_session, title="Today B", url="https://x.com/bb")

        resp = await client.get(f"/api/briefings/{today.isoformat()}", headers=auth_headers)

        assert resp.status_code == 200
        data = resp.json()
        assert data["total_items"] == 2
        assert len(data["items"]) == 2


class TestDeferredHeavyColumns:
    """full_text must never be selected when serving briefing items."""

    async def test_get_briefing_defers_full_text(
        self, client, db_session, integration_engine, auth_headers
    ):
        today = datetime.now(tz=UTC).date()
        await seed_briefing(db_session, date=today, total_items=1)
        await seed_news_item(db_session, title="Heavy", full_text="x" * 5000)

        resp, statements = await _capture_sql(
            integration_engine,
            client.get(f"/api/briefings/{today.isoformat()}", headers=auth_headers),
        )

        assert resp.status_code == 200
        leaking = [s for s in statements if "FROM news_items" in s and "full_text" in s]
        assert not leaking, f"full_text leaked into SQL: {leaking}"

    async def test_get_briefing_without_record_defers_full_text(
        self, client, db_session, integration_engine, auth_headers
    ):
        """Synthesized-from-items-only path (no DailyBriefing row) also defers."""
        today = datetime.now(tz=UTC).date()
        await seed_news_item(db_session, title="Heavy", full_text="x" * 5000)

        resp, statements = await _capture_sql(
            integration_engine,
            client.get(f"/api/briefings/{today.isoformat()}", headers=auth_headers),
        )

        assert resp.status_code == 200
        leaking = [s for s in statements if "FROM news_items" in s and "full_text" in s]
        assert not leaking, f"full_text leaked into SQL: {leaking}"
