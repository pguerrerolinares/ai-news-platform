"""Integration tests for GET /api/search — PostgreSQL full-text search."""

from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.dialects.postgresql import asyncpg as pg_asyncpg

from src.api.routes.search import _build_search_query
from tests.integration.conftest import _FTS_PIN, _MIGRATIONS, seed_news_item

pytestmark = pytest.mark.integration


class TestSearch:
    pytestmark = pytest.mark.asyncio(loop_scope="session")

    async def test_finds_matching_items(self, client, db_session, auth_headers):
        """FTS with plainto_tsquery finds items by keyword in title/text."""
        await seed_news_item(
            db_session,
            title="Transformer Architecture Breakthrough",
            full_text="A new transformer model achieves state-of-the-art results.",
        )
        await seed_news_item(
            db_session,
            title="Python Web Framework",
            full_text="A guide to building REST APIs with FastAPI.",
        )

        resp = await client.get("/api/search?q=transformer", headers=auth_headers)

        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert "Transformer" in data[0]["title"]

    async def test_ranks_by_relevance(self, client, db_session, auth_headers):
        """Items with higher keyword density rank first (ts_rank)."""
        await seed_news_item(
            db_session,
            title="Machine Learning Overview",
            full_text="Brief mention of neural networks.",
            url="https://example.com/low-rank",
        )
        await seed_news_item(
            db_session,
            title="Neural Networks Deep Dive",
            full_text="Neural networks neural networks training neural networks.",
            url="https://example.com/high-rank",
        )

        resp = await client.get("/api/search?q=neural+networks", headers=auth_headers)

        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        # Higher density item should rank first
        assert "Deep Dive" in data[0]["title"]

    async def test_search_with_topic_filter(self, client, db_session, auth_headers):
        """Search + topic filter returns intersection."""
        await seed_news_item(
            db_session,
            title="Reinforcement Learning Training Techniques",
            topic="models",
            url="https://example.com/rl-models",
        )
        await seed_news_item(
            db_session,
            title="Reinforcement Learning Development Tools",
            topic="tools",
            url="https://example.com/rl-tools",
        )

        resp = await client.get(
            "/api/search?q=reinforcement+learning&topic=models", headers=auth_headers
        )

        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["topic"] == "models"

    async def test_finds_term_only_in_summary(self, client, db_session, auth_headers):
        """A term present only in summary (not title/full_text) is found.

        search_vector (migration 019) indexes summary alongside
        title/full_text/source, so FTS alone — no ILIKE fallback — must
        find it.
        """
        await seed_news_item(
            db_session,
            title="Weekly Roundup",
            full_text="Nothing notable to report this week.",
            summary="Deep dive into quantization techniques for LLM inference.",
        )

        resp = await client.get("/api/search?q=quantization", headers=auth_headers)

        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["title"] == "Weekly Roundup"

    async def test_uses_gin_index_not_seq_scan(self, db_session):
        """The FTS query plan hits the GIN index — no ILIKE forcing a seq scan.

        On a tiny table Postgres prefers a seq scan regardless, so
        enable_seqscan is forced off to make the planner reveal what index it
        *would* use. An OR'd ILIKE fallback prevents a clean GIN bitmap scan.
        """
        await seed_news_item(db_session, title="Index probe", full_text="lorem ipsum")

        query = _build_search_query(q="probe", topic=None, date_from=None, date_to=None)
        # Compile with the real asyncpg dialect (native $n placeholders +
        # explicit ::REGCONFIG cast) and send it straight to the driver —
        # asyncpg's extended protocol can't infer plainto_tsquery's first
        # argument type from a plain bind parameter.
        compiled = query.compile(dialect=pg_asyncpg.dialect())
        assert compiled.positiontup is not None
        params = [compiled.params[name] for name in compiled.positiontup]

        conn = await db_session.connection()
        await conn.execute(text("SET LOCAL enable_seqscan = off"))
        result = await conn.exec_driver_sql(f"EXPLAIN {compiled}", tuple(params))
        plan = "\n".join(row[0] for row in result)

        assert "idx_news_items_search" in plan

    async def test_prefix_matches_plural(self, client, db_session, auth_headers):
        """A 3+ char term matches as a prefix: 'agent' finds 'Agents' (ADR-005).

        Mutant check: removing the ':*' from _PREFIX_REPLACEMENT makes this fail.
        """
        await seed_news_item(db_session, title="AI Agents framework")

        resp = await client.get("/api/search?q=agent", headers=auth_headers)

        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1

    async def test_prefix_matches_acronym_plural(self, client, db_session, auth_headers):
        """'LLM' matches 'LLMs' via prefix (ADR-005)."""
        await seed_news_item(db_session, title="New LLMs benchmark")

        resp = await client.get("/api/search?q=LLM", headers=auth_headers)

        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1

    async def test_prefix_matches_source(self, client, db_session, auth_headers):
        """'hacker' matches source 'hackernews' via prefix (ADR-005)."""
        await seed_news_item(db_session, title="Some article", source="hackernews")

        resp = await client.get("/api/search?q=hacker", headers=auth_headers)

        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1

    async def test_short_lexeme_is_exact_not_prefix(self, client, db_session, auth_headers):
        """A <3 char term matches exactly, not as a prefix (ADR-005).

        'ai' must NOT match an item whose only lexeme starting with 'ai' is
        'aircraft'. Mutant check: lowering the {3,} threshold to {2,} makes
        this fail.
        """
        await seed_news_item(
            db_session,
            title="Aircraft carriers of the future",
            full_text="Naval engineering and shipbuilding report.",
        )

        resp = await client.get("/api/search?q=ai", headers=auth_headers)

        assert resp.status_code == 200
        assert resp.json() == []

    @pytest.mark.parametrize(
        "q",
        ["a & b | !c", "foo:* <-> bar", "'quoted'", "C:\\path"],
    )
    async def test_tsquery_operators_are_neutralized(self, client, auth_headers, q):
        """User input reaching tsquery syntax never breaks the query (200, not 500)."""
        resp = await client.get("/api/search", params={"q": q}, headers=auth_headers)

        assert resp.status_code == 200

    async def test_empty_tsquery_returns_no_results(self, client, auth_headers):
        """A query that plainto_tsquery reduces to nothing returns an empty list."""
        resp = await client.get("/api/search?q=%3F", headers=auth_headers)

        assert resp.status_code == 200
        assert resp.json() == []


def test_search_query_defers_heavy_columns() -> None:
    """The search SELECT list omits full_text/search_vector (#17 partial).

    Unit test, no DB: compiles the query and inspects the column list.
    """
    sql = str(_build_search_query(q="x", topic=None, date_from=None, date_to=None).compile())
    select_list = sql.split("FROM")[0]

    assert "full_text" not in select_list
    assert "search_vector" not in select_list


def test_fts_pin_matches_latest_trigger_migration() -> None:
    """conftest's _FTS_PIN must point at the migration that last redefined the trigger.

    Guards against a silent staleness: if a future migration (020+) redefines
    news_items_search_trigger() and nobody bumps _FTS_PIN, integration tests
    would install the old (019) function on top of a head-migrated DB in CI
    without failing (see M4, review 2026-09-13).
    """
    latest = max(
        p.name
        for p in _MIGRATIONS.glob("[0-9][0-9][0-9]_*.py")
        if "news_items_search_trigger()" in p.read_text()
    )

    assert latest == _FTS_PIN, f"bump FTS pin to {latest}"
