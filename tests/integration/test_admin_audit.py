"""Integration tests for GET /api/admin/audit against real PostgreSQL.

These tests exist specifically to catch SQL-level bugs (e.g. nested aggregates)
that mocked-session unit tests cannot detect.
"""

from __future__ import annotations

import pytest

from tests.integration.conftest import seed_news_item

pytestmark = [pytest.mark.integration, pytest.mark.asyncio(loop_scope="session")]


class TestAdminAuditDuplicates:
    async def test_no_duplicates(self, client, db_session, auth_headers):
        """Audit returns 200 with zero duplicates when all URLs are unique."""
        await seed_news_item(db_session, url="https://example.com/unique-1")
        await seed_news_item(db_session, url="https://example.com/unique-2")

        resp = await client.get("/api/admin/audit", headers=auth_headers)

        assert resp.status_code == 200
        data = resp.json()
        assert data["duplicates"]["duplicate_groups"] == 0
        assert data["duplicates"]["extra_items"] == 0

    async def test_one_duplicated_url(self, client, db_session, auth_headers):
        """One URL duplicated twice → 1 group, 1 extra item."""
        shared_url = "https://example.com/dup-url-once"
        await seed_news_item(
            db_session,
            url=shared_url,
            content_hash="hash-a1",
            title="Dup Item A",
        )
        await seed_news_item(
            db_session,
            url=shared_url,
            content_hash="hash-a2",
            title="Dup Item B",
        )
        # One unique item — should not affect duplicate counts
        await seed_news_item(db_session, url="https://example.com/unique-99")

        resp = await client.get("/api/admin/audit", headers=auth_headers)

        assert resp.status_code == 200
        data = resp.json()
        dups = data["duplicates"]
        assert dups["duplicate_groups"] == 1
        assert dups["extra_items"] == 1

    async def test_multiple_duplicated_urls(self, client, db_session, auth_headers):
        """Two distinct URLs, each with 3 copies → 2 groups, 4 extra items."""
        for url_id in ("multi-dup-X", "multi-dup-Y"):
            url = f"https://example.com/{url_id}"
            for idx in range(3):
                await seed_news_item(
                    db_session,
                    url=url,
                    content_hash=f"hash-{url_id}-{idx}",
                    title=f"Item {url_id} {idx}",
                )

        resp = await client.get("/api/admin/audit", headers=auth_headers)

        assert resp.status_code == 200
        data = resp.json()
        dups = data["duplicates"]
        assert dups["duplicate_groups"] == 2
        assert dups["extra_items"] == 4  # (3-1) + (3-1)

    async def test_audit_response_shape(self, client, db_session, auth_headers):
        """Audit returns all expected top-level keys with sane values."""
        await seed_news_item(db_session, source="hackernews")

        resp = await client.get("/api/admin/audit", headers=auth_headers)

        assert resp.status_code == 200
        data = resp.json()
        assert "total_items" in data
        assert "date_range" in data
        assert "sources" in data
        assert "daily_breakdown" in data
        assert "duplicates" in data
        assert data["total_items"] >= 1
        assert isinstance(data["sources"], list)
        assert len(data["sources"]) >= 1
