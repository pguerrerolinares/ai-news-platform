"""Tests for src.pipeline.stages.seen_filter — persistent already-seen filter."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from src.extractors.base import ExtractedItem
from src.pipeline.stages.seen_filter import filter_already_seen


def _make_item(url: str | None = "https://example.com/test", title: str = "Test") -> ExtractedItem:
    return ExtractedItem(title=title, source="hackernews", url=url)


class TestFilterAlreadySeen:
    async def test_filters_out_items_with_known_url_hash(self):
        """Items whose url_hash exists in DB are filtered out."""
        item = _make_item("https://example.com/already-seen")

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [item.url_hash]
        mock_session.execute = AsyncMock(return_value=mock_result)

        with patch("src.pipeline.stages.seen_filter.get_settings") as mock_settings:
            mock_settings.return_value.seen_window_days = 7
            result = await filter_already_seen(mock_session, [item])

        assert len(result) == 0

    async def test_keeps_items_not_in_db(self):
        """Items whose url_hash is NOT in DB pass through."""
        item = _make_item("https://example.com/brand-new")

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute = AsyncMock(return_value=mock_result)

        with patch("src.pipeline.stages.seen_filter.get_settings") as mock_settings:
            mock_settings.return_value.seen_window_days = 7
            result = await filter_already_seen(mock_session, [item])

        assert len(result) == 1

    async def test_items_without_url_always_pass(self):
        """Items with url=None (no url_hash) are never filtered."""
        item = _make_item(url=None, title="No URL item")

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute = AsyncMock(return_value=mock_result)

        with patch("src.pipeline.stages.seen_filter.get_settings") as mock_settings:
            mock_settings.return_value.seen_window_days = 7
            result = await filter_already_seen(mock_session, [item])

        assert len(result) == 1

    async def test_empty_input_returns_empty(self):
        """Empty list returns empty list without DB query."""
        mock_session = AsyncMock()

        result = await filter_already_seen(mock_session, [])

        assert result == []
        mock_session.execute.assert_not_awaited()

    async def test_mixed_seen_and_unseen(self):
        """Mix of seen and unseen items: only unseen pass."""
        seen = _make_item("https://example.com/old")
        unseen = _make_item("https://example.com/new")
        no_url = _make_item(url=None, title="No URL")

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [seen.url_hash]
        mock_session.execute = AsyncMock(return_value=mock_result)

        with patch("src.pipeline.stages.seen_filter.get_settings") as mock_settings:
            mock_settings.return_value.seen_window_days = 7
            result = await filter_already_seen(mock_session, [seen, unseen, no_url])

        assert len(result) == 2
        urls = [i.url for i in result]
        assert "https://example.com/new" in urls
        assert None in urls
