"""Tests for src.pipeline.stages.store — storage stage."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from src.classifiers.base import ClassifiedItem
from src.extractors.base import ExtractedItem
from src.pipeline.stages.store import store_classified_items


def _make_classified(title="Test", url="https://example.com"):
    item = ExtractedItem(title=title, source="hackernews", url=url, score=100)
    return ClassifiedItem(item=item, topic="models", relevance_score=0.9, summary="Test")


class TestStoreClassifiedItems:
    async def test_stores_items_and_returns_count(self):
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.rowcount = 1
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.commit = AsyncMock()

        items = [_make_classified()]
        stored = await store_classified_items(mock_session, items)

        assert stored == 1
        assert mock_session.commit.called

    async def test_returns_zero_for_empty_input(self):
        mock_session = AsyncMock()
        stored = await store_classified_items(mock_session, [])
        assert stored == 0


class TestUrlHashUpsert:
    """Tests for url_hash-based upsert-on-better-score."""

    async def test_item_with_url_uses_url_hash_conflict(self):
        """Items with URL use ON CONFLICT url_hash DO UPDATE."""
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.rowcount = 1
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.commit = AsyncMock()

        item = _make_classified(title="Test", url="https://example.com/repo")
        await store_classified_items(mock_session, [item])

        call_args = mock_session.execute.call_args_list[0]
        stmt = call_args.args[0]
        # Import the dialect for compilation
        from sqlalchemy.dialects.postgresql import dialect as pg_dialect

        compiled = stmt.compile(dialect=pg_dialect())
        sql = str(compiled)
        assert "ON CONFLICT" in sql
        assert "DO UPDATE" in sql

    async def test_item_without_url_uses_content_hash_conflict(self):
        """Items without URL use ON CONFLICT content_hash DO NOTHING."""
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.rowcount = 1
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.commit = AsyncMock()

        item = _make_classified(title="No URL Item", url=None)
        await store_classified_items(mock_session, [item])

        call_args = mock_session.execute.call_args_list[0]
        stmt = call_args.args[0]
        from sqlalchemy.dialects.postgresql import dialect as pg_dialect

        compiled = stmt.compile(dialect=pg_dialect())
        sql = str(compiled)
        assert "DO NOTHING" in sql
