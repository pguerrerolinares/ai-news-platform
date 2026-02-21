"""Integration tests for the pipeline → DB interaction."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from sqlalchemy import func, select

from src.core.models import DailyBriefing, ItemEmbedding, NewsItem
from src.pipeline.pipeline import _embed_new_items, _save_briefing, _store_classified_items
from src.rag.embeddings import EmbeddingService
from tests.factories import make_classified_item
from tests.integration.conftest import seed_news_item

pytestmark = [pytest.mark.integration, pytest.mark.asyncio(loop_scope="session")]


class TestStoreClassifiedItems:
    """Tests for _store_classified_items against real PostgreSQL."""

    async def test_stores_items_in_db(self, db_session):
        """Classified items are written as NewsItem rows."""
        items = [
            make_classified_item(
                title=f"Article {i}",
                url=f"https://example.com/store-{i}",
            )
            for i in range(5)
        ]

        count = await _store_classified_items(db_session, items)

        assert count == 5
        result = await db_session.execute(select(func.count(NewsItem.id)))
        assert result.scalar_one() == 5

    async def test_dedup_by_content_hash(self, db_session):
        """Duplicate content_hash is silently skipped (ON CONFLICT DO NOTHING)."""
        item = make_classified_item(title="Same Title", url="https://example.com/same")
        await _store_classified_items(db_session, [item])
        count2 = await _store_classified_items(db_session, [item])

        assert count2 == 0
        result = await db_session.execute(select(func.count(NewsItem.id)))
        assert result.scalar_one() == 1

    async def test_batch_commit(self, db_session):
        """30 items (> BATCH_COMMIT_SIZE=25) are all stored across 2 batches."""
        items = [
            make_classified_item(
                title=f"Batch {i}",
                url=f"https://example.com/batch-{i}",
            )
            for i in range(30)
        ]

        count = await _store_classified_items(db_session, items)

        assert count == 30
        result = await db_session.execute(select(func.count(NewsItem.id)))
        assert result.scalar_one() == 30

    async def test_stores_correct_fields(self, db_session):
        """All ClassifiedItem fields map correctly to NewsItem columns."""
        item = make_classified_item(
            title="Field Test",
            url="https://example.com/fields",
            topic="herramientas",
            relevance_score=0.88,
            priority=3,
            trending=True,
            summary="Test summary",
            dev_value_score=0.77,
        )

        await _store_classified_items(db_session, [item])

        result = await db_session.execute(select(NewsItem))
        row = result.scalar_one()

        assert row.title == "Field Test"
        assert row.source == "hackernews"
        assert row.topic == "herramientas"
        assert row.relevance_score == pytest.approx(0.88)
        assert row.priority == 3
        assert row.trending is True
        assert row.summary == "Test summary"
        assert row.dev_value_score == pytest.approx(0.77)
        assert row.content_hash is not None
        assert row.url == "https://example.com/fields"


class TestSaveBriefing:
    """Tests for _save_briefing against real PostgreSQL."""

    async def test_briefing_created(self, db_session):
        """A new DailyBriefing row is created with correct stats."""
        await _save_briefing(
            db_session,
            items_extracted=20,
            items_after_dedup=15,
            items_stored=10,
            sources_used=["hackernews", "arxiv"],
            duration_seconds=3.5,
            trending_count=2,
        )

        # Savepoint isolation guarantees only our test's data exists
        result = await db_session.execute(select(DailyBriefing))
        briefing = result.scalar_one()

        assert briefing.items_extracted == 20
        assert briefing.items_after_dedup == 15
        assert briefing.total_items == 10
        assert briefing.trending_count == 2
        assert briefing.duration_seconds == pytest.approx(3.5)
        assert briefing.sources_used == {"sources": ["hackernews", "arxiv"]}

    async def test_briefing_accumulates(self, db_session):
        """Running twice in the same day accumulates stats, not replaces."""
        await _save_briefing(
            db_session,
            items_extracted=10,
            items_after_dedup=8,
            items_stored=5,
            sources_used=["hackernews"],
            duration_seconds=2.0,
            trending_count=1,
        )
        await _save_briefing(
            db_session,
            items_extracted=6,
            items_after_dedup=4,
            items_stored=3,
            sources_used=["arxiv"],
            duration_seconds=1.5,
            trending_count=0,
        )

        result = await db_session.execute(select(DailyBriefing))
        briefing = result.scalar_one()

        assert briefing.items_extracted == 16  # 10 + 6
        assert briefing.total_items == 8  # 5 + 3
        assert briefing.trending_count == 1  # 1 + 0
        assert briefing.duration_seconds == pytest.approx(3.5)  # 2.0 + 1.5

    async def test_empty_pipeline(self, db_session):
        """Briefing with 0 items stored is valid."""
        await _save_briefing(
            db_session,
            items_extracted=0,
            items_after_dedup=0,
            items_stored=0,
            sources_used=[],
            duration_seconds=0.1,
        )

        result = await db_session.execute(select(DailyBriefing))
        briefing = result.scalar_one()
        assert briefing.total_items == 0


class TestEmbedNewItems:
    """Test _embed_new_items writes embeddings to item_embeddings table."""

    async def test_embeds_items_without_embeddings(self, db_session):
        """Items without embeddings get new rows in item_embeddings."""
        for i in range(3):
            await seed_news_item(
                db_session,
                title=f"Embed {i}",
                url=f"https://example.com/embed-{i}",
            )

        mock_embed = AsyncMock(spec=EmbeddingService)
        mock_embed.prepare_text = EmbeddingService.prepare_text
        mock_embed.embed_batch.return_value = [[0.5] * 1536] * 3

        count = await _embed_new_items(db_session, embed_service=mock_embed)

        assert count == 3
        result = await db_session.execute(select(func.count(ItemEmbedding.item_id)))
        assert result.scalar_one() == 3
