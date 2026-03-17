"""Tests for src.pipeline.stages.seen_filter — URL hash + title similarity filter."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from src.extractors.base import ExtractedItem
from src.pipeline.stages.seen_filter import filter_already_seen


def _make_item(url: str | None = "https://example.com/test", title: str = "Test") -> ExtractedItem:
    return ExtractedItem(title=title, source="hackernews", url=url)


def _mock_session_two_queries(url_hashes: list[str], titles: list[str]) -> AsyncMock:
    """Mock session that returns url_hashes on first execute, titles on second."""
    session = AsyncMock()

    result_url = MagicMock()
    result_url.scalars.return_value.all.return_value = url_hashes

    result_titles = MagicMock()
    result_titles.scalars.return_value.all.return_value = titles

    session.execute = AsyncMock(side_effect=[result_url, result_titles])
    return session


class TestUrlHashFilter:
    async def test_filters_out_items_with_known_url_hash(self):
        """Items whose url_hash exists in DB are filtered out."""
        item = _make_item("https://example.com/already-seen")
        session = _mock_session_two_queries([item.url_hash], [])

        with patch("src.pipeline.stages.seen_filter.get_settings") as mock_settings:
            mock_settings.return_value.seen_window_days = 7
            result = await filter_already_seen(session, [item])

        assert len(result) == 0

    async def test_keeps_items_not_in_db(self):
        """Items whose url_hash is NOT in DB pass through."""
        item = _make_item("https://example.com/brand-new", title="Unique Article Title XYZ")
        session = _mock_session_two_queries([], [])

        with patch("src.pipeline.stages.seen_filter.get_settings") as mock_settings:
            mock_settings.return_value.seen_window_days = 7
            result = await filter_already_seen(session, [item])

        assert len(result) == 1


class TestTitleSimilarityFilter:
    async def test_filters_similar_title_cross_source(self):
        """Item with similar title to a stored item is filtered (cross-source dedup)."""
        item = _make_item(
            "https://example.com/new-source",
            title="GPT-5 Released by OpenAI today",
        )
        # DB has a similar title from a previous tier
        session = _mock_session_two_queries([], ["GPT-5 Released by OpenAI"])

        with patch("src.pipeline.stages.seen_filter.get_settings") as mock_settings:
            mock_settings.return_value.seen_window_days = 7
            result = await filter_already_seen(session, [item])

        assert len(result) == 0

    async def test_keeps_different_title(self):
        """Item with a different title passes through."""
        item = _make_item(
            "https://example.com/different",
            title="EU AI Act Regulation Update",
        )
        session = _mock_session_two_queries([], ["GPT-5 Released by OpenAI"])

        with patch("src.pipeline.stages.seen_filter.get_settings") as mock_settings:
            mock_settings.return_value.seen_window_days = 7
            result = await filter_already_seen(session, [item])

        assert len(result) == 1

    async def test_no_url_item_checked_by_title(self):
        """Items without URL still go through title similarity check."""
        item = _make_item(url=None, title="GPT-5 Released by OpenAI now")
        # No URL items skip the url hash query — only title query runs
        result_titles = MagicMock()
        result_titles.scalars.return_value.all.return_value = ["GPT-5 Released by OpenAI"]
        session = AsyncMock()
        session.execute = AsyncMock(return_value=result_titles)

        with patch("src.pipeline.stages.seen_filter.get_settings") as mock_settings:
            mock_settings.return_value.seen_window_days = 7
            result = await filter_already_seen(session, [item])

        assert len(result) == 0  # filtered by title similarity


class TestCombinedFilter:
    async def test_empty_input_returns_empty(self):
        """Empty list returns empty list without DB query."""
        session = AsyncMock()
        result = await filter_already_seen(session, [])
        assert result == []
        session.execute.assert_not_awaited()

    async def test_mixed_url_and_title_filtering(self):
        """URL-seen, title-similar, and unique items handled correctly."""
        url_seen = _make_item("https://example.com/old", title="Old Article")
        title_similar = _make_item(
            "https://example.com/cross-source",
            title="GPT-5 Released by OpenAI today",
        )
        unique = _make_item("https://example.com/unique", title="Completely New Topic XYZ")

        session = _mock_session_two_queries(
            [url_seen.url_hash],  # url_seen filtered by hash
            ["GPT-5 Released by OpenAI"],  # title_similar filtered by title
        )

        with patch("src.pipeline.stages.seen_filter.get_settings") as mock_settings:
            mock_settings.return_value.seen_window_days = 7
            result = await filter_already_seen(session, [url_seen, title_similar, unique])

        assert len(result) == 1
        assert result[0].title == "Completely New Topic XYZ"

    async def test_no_url_items_pass_when_no_similar_titles(self):
        """Items without URL pass if title is unique."""
        item = _make_item(url=None, title="Totally New Research Direction ABC")
        # Only url query needed when no items have URLs, but title query still runs
        result_titles = MagicMock()
        result_titles.scalars.return_value.all.return_value = ["Something Completely Different"]

        session = AsyncMock()
        session.execute = AsyncMock(return_value=result_titles)

        with patch("src.pipeline.stages.seen_filter.get_settings") as mock_settings:
            mock_settings.return_value.seen_window_days = 7
            result = await filter_already_seen(session, [item])

        assert len(result) == 1
