"""Integration tests for GET /api/search — PostgreSQL full-text search."""

from __future__ import annotations

import pytest

from tests.integration.conftest import seed_news_item

pytestmark = [pytest.mark.integration, pytest.mark.asyncio(loop_scope="session")]


class TestSearch:
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
            topic="modelos",
            url="https://example.com/rl-modelos",
        )
        await seed_news_item(
            db_session,
            title="Reinforcement Learning Development Tools",
            topic="herramientas",
            url="https://example.com/rl-tools",
        )

        resp = await client.get(
            "/api/search?q=reinforcement+learning&topic=modelos", headers=auth_headers
        )

        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["topic"] == "modelos"
