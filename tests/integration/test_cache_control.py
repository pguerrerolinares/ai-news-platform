"""Integration tests for the public Cache-Control policy on read routers.

`Cache-Control: public, max-age=60` must be present on every successful (2xx)
response from items.py, briefings.py, stats.py, sources.py and topics.py, and
absent everywhere else: search.py, admin.py, auth.py, chat.py, and any error
response (4xx/5xx) from any router.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from tests.integration.conftest import seed_briefing, seed_embedding, seed_news_item

pytestmark = [pytest.mark.integration, pytest.mark.asyncio(loop_scope="session")]

_EXPECTED = "public, max-age=60"

# Simple GET endpoints that need no path params or seed data to return 2xx.
_CACHED_GET_PATHS = [
    "/api/items",
    "/api/items/count",
    "/api/items/today",
    "/api/items/trending",
    "/api/items/top",
    "/api/items/latest",
    "/api/briefings",
    "/api/stats/summary",
    "/api/stats/by-source",
    "/api/stats/by-topic",
    "/api/stats/by-date",
    "/api/stats/by-topic-date",
    "/api/stats/by-source-date",
    "/api/stats/trending-timeline",
    "/api/stats/score-distribution",
    "/api/sources",
    "/api/topics",
]


class TestCacheControlPresentOnPublicReads:
    @pytest.mark.parametrize("path", _CACHED_GET_PATHS)
    async def test_2xx_has_public_cache_control(self, client, db_session, auth_headers, path):
        resp = await client.get(path, headers=auth_headers)

        assert resp.status_code == 200
        assert resp.headers.get("cache-control") == _EXPECTED

    async def test_by_date_has_cache_control(self, client, db_session, auth_headers):
        today = datetime.now(tz=UTC).date()
        await seed_news_item(db_session, published_at=datetime.now(tz=UTC))

        resp = await client.get(f"/api/items/by-date/{today.isoformat()}", headers=auth_headers)

        assert resp.status_code == 200
        assert resp.headers.get("cache-control") == _EXPECTED

    async def test_get_item_has_cache_control(self, client, db_session, auth_headers):
        item = await seed_news_item(db_session)

        resp = await client.get(f"/api/items/{item.id}", headers=auth_headers)

        assert resp.status_code == 200
        assert resp.headers.get("cache-control") == _EXPECTED

    async def test_similar_items_has_cache_control(self, client, db_session, auth_headers):
        item = await seed_news_item(db_session)
        await seed_embedding(db_session, item)

        resp = await client.get(f"/api/items/{item.id}/similar", headers=auth_headers)

        assert resp.status_code == 200
        assert resp.headers.get("cache-control") == _EXPECTED

    async def test_get_briefing_has_cache_control(self, client, db_session, auth_headers):
        today = datetime.now(tz=UTC).date()
        await seed_briefing(db_session, date=today)

        resp = await client.get(f"/api/briefings/{today.isoformat()}", headers=auth_headers)

        assert resp.status_code == 200
        assert resp.headers.get("cache-control") == _EXPECTED


class TestCacheControlAbsentOnExcludedRouters:
    async def test_search_absent(self, client, db_session, auth_headers):
        """search.py is out of scope for this change — never gets the header."""
        resp = await client.get("/api/search?q=test", headers=auth_headers)

        assert resp.status_code == 200
        assert "cache-control" not in resp.headers

    async def test_admin_audit_absent(self, client, db_session, auth_headers):
        resp = await client.get("/api/admin/audit", headers=auth_headers)

        assert resp.status_code == 200
        assert "cache-control" not in resp.headers

    async def test_admin_pipeline_runs_absent(self, client, db_session, auth_headers):
        resp = await client.get("/api/admin/pipeline-runs", headers=auth_headers)

        assert resp.status_code == 200
        assert "cache-control" not in resp.headers

    async def test_admin_freshness_absent(self, client, db_session, auth_headers):
        resp = await client.get("/api/admin/freshness", headers=auth_headers)

        assert resp.status_code == 200
        assert "cache-control" not in resp.headers

    async def test_auth_guest_absent(self, client):
        resp = await client.post("/api/auth/guest")

        assert resp.status_code == 200
        assert "cache-control" not in resp.headers

    async def test_chat_never_gets_public_cache_control(self, client, db_session, auth_headers):
        """chat.py already sets its own `Cache-Control: no-cache` for SSE — it
        must never additionally carry our public max-age=60 value.

        Question is whitespace-only: passes the `min_length=3` schema check
        but makes `ChatService.chat_stream` return immediately on its
        empty-question branch, without calling the retriever or the LLM
        (no real network/LLM call).
        """
        resp = await client.post("/api/chat", json={"question": "   "}, headers=auth_headers)

        assert resp.status_code == 200
        assert resp.headers.get("cache-control") != _EXPECTED


class TestCacheControlAbsentOnErrors:
    async def test_item_404_absent(self, client, db_session, auth_headers):
        import uuid

        resp = await client.get(f"/api/items/{uuid.uuid4()}", headers=auth_headers)

        assert resp.status_code == 404
        assert "cache-control" not in resp.headers

    async def test_briefing_404_absent(self, client, db_session, auth_headers):
        resp = await client.get("/api/briefings/1999-01-01", headers=auth_headers)

        assert resp.status_code == 404
        assert "cache-control" not in resp.headers

    async def test_similar_items_404_absent(self, client, db_session, auth_headers):
        import uuid

        resp = await client.get(f"/api/items/{uuid.uuid4()}/similar", headers=auth_headers)

        assert resp.status_code == 404
        assert "cache-control" not in resp.headers
