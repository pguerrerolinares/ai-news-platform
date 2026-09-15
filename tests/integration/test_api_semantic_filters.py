"""Integration: /api/search/semantic returns full result sets with filters and limit > 40.

pgvector's HNSW index returns at most hnsw.ef_search (40) rows and filters after the ANN
step. On small test tables the planner never picks HNSW on its own, so every test sets
enable_sort = off, which makes the HNSW plan preferable whenever index scans are allowed.
Measured locally (200 rows): without the exact-scan fix these queries return 3/10 and
40/50 rows; with it, 10/10 and 50/50.
"""

from __future__ import annotations

import random
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from sqlalchemy import text

from src.core.models import ItemEmbedding, NewsItem
from src.rag.embeddings import EmbeddingService
from src.rag.retriever import Retriever

pytestmark = [pytest.mark.integration, pytest.mark.asyncio(loop_scope="session")]

_MODEL = "text-embedding-3-small"
_CORPUS_SIZE = 200


@pytest.fixture(autouse=True)
def _reset_search_limiter():
    from src.api.routes.search import limiter

    limiter.reset()


async def _seed_corpus(db_session) -> list[float]:
    """Insert 200 items (every 20th is arxiv) with random embeddings; return a query vector."""
    rng = random.Random(42)  # noqa: S311
    items = [
        NewsItem(
            title=f"Corpus item {i}",
            source="arxiv" if i % 20 == 0 else "github",
            topic="papers",
            url=f"https://example.com/corpus/{i}",
            content_hash=uuid4().hex,
            trending=False,
        )
        for i in range(_CORPUS_SIZE)
    ]
    db_session.add_all(items)
    await db_session.flush()
    db_session.add_all(
        [
            ItemEmbedding(
                item_id=item.id,
                model=_MODEL,
                embedding=[rng.uniform(-1, 1) for _ in range(512)],
            )
            for item in items
        ]
    )
    await db_session.flush()
    return [rng.uniform(-1, 1) for _ in range(512)]


def _use_fake_embedding(monkeypatch, vector: list[float]) -> None:
    fake = AsyncMock(spec=EmbeddingService)
    fake.embed_text.return_value = vector
    monkeypatch.setattr("src.api.routes.search._retriever", Retriever(embedding_service=fake))


class TestSemanticFullResults:
    async def test_filtered_search_returns_full_limit(
        self, client, db_session, auth_headers, monkeypatch
    ):
        _use_fake_embedding(monkeypatch, await _seed_corpus(db_session))
        await db_session.execute(text("SET LOCAL enable_sort = off"))

        resp = await client.get(
            "/api/search/semantic",
            params={"q": "anything", "source": "arxiv", "limit": 10, "recent_first": "false"},
            headers=auth_headers,
        )

        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 10
        assert {item["source"] for item in data} == {"arxiv"}

    async def test_limit_above_ef_search_returns_full_limit(
        self, client, db_session, auth_headers, monkeypatch
    ):
        _use_fake_embedding(monkeypatch, await _seed_corpus(db_session))
        await db_session.execute(text("SET LOCAL enable_sort = off"))

        resp = await client.get(
            "/api/search/semantic",
            params={"q": "anything", "limit": 50, "recent_first": "false"},
            headers=auth_headers,
        )

        assert resp.status_code == 200
        assert len(resp.json()) == 50
