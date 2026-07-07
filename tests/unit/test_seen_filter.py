"""Tests for src.pipeline.stages.seen_filter — URL hash + title similarity filter."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from src.core.text_utils import TITLE_SIMILARITY_THRESHOLD, title_similarity
from src.extractors.base import ExtractedItem
from src.pipeline.stages.seen_filter import filter_already_seen


def _make_item(url: str | None = "https://example.com/test", title: str = "Test") -> ExtractedItem:
    return ExtractedItem(title=title, source="hackernews", url=url)


def _mock_session_two_queries(
    url_content_pairs: list[tuple[str, str | None]], titles: list[str]
) -> AsyncMock:
    """Mock session that returns (url_hash, content_hash) rows on first
    execute, titles on second.

    `url_content_pairs` models the DB rows matched by url_hash within the
    seen window, each paired with its stored content_hash — this is what
    filter_already_seen() now compares against an incoming item's own
    content_hash to tell an unchanged duplicate from a content update.
    """
    session = AsyncMock()

    result_url = MagicMock()
    result_url.all.return_value = url_content_pairs

    result_titles = MagicMock()
    result_titles.scalars.return_value.all.return_value = titles

    session.execute = AsyncMock(side_effect=[result_url, result_titles])
    return session


class TestUrlHashFilter:
    async def test_filters_out_items_with_known_url_hash(self):
        """Items whose url_hash AND content_hash both match a stored row
        are filtered out as an unchanged duplicate."""
        item = _make_item("https://example.com/already-seen")
        session = _mock_session_two_queries([(item.url_hash, item.content_hash)], [])

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

    async def test_same_url_different_content_hash_passes_through(self):
        """A known url_hash whose stored content_hash differs from the
        incoming item's is a content update, not a duplicate -- it must
        not be silently dropped."""
        item = _make_item("https://example.com/already-seen", title="Updated headline")
        stale_content_hash = "0123456789abcdef"  # deliberately not item.content_hash
        session = _mock_session_two_queries([(item.url_hash, stale_content_hash)], [])

        with patch("src.pipeline.stages.seen_filter.get_settings") as mock_settings:
            mock_settings.return_value.seen_window_days = 7
            result = await filter_already_seen(session, [item])

        assert len(result) == 1

    async def test_content_update_with_minor_title_edit_skips_title_pass(self):
        """A same-URL content update whose new title is a MINOR edit of the
        stored one (capitalization only, here) must still pass through --
        Pass 2 exists for cross-source dedup between different articles,
        not to re-check a row against its own stale stored title. If a
        content update went through Pass 2, this pair would score >=80%
        similar and get wrongly dropped as a "duplicate"."""
        original_title = "OpenAI launches GPT-5 today"
        updated_title = "OpenAI launches GPT-5 Today"  # capitalization-only edit
        item = _make_item("https://example.com/breaking-news", title=updated_title)
        original = _make_item("https://example.com/breaking-news", title=original_title)
        assert original.content_hash != item.content_hash  # sanity: a real content change

        # Sanity: if Pass 2 ran on this pair, it WOULD filter it as a dup.
        similarity = title_similarity(updated_title.lower(), original_title.lower())
        assert similarity >= TITLE_SIMILARITY_THRESHOLD

        # DB has the stale original title/content_hash for this url_hash,
        # and recent_titles (Pass 2's snapshot) still holds that same stale
        # title -- if Pass 2 ran on this item, it would self-match.
        session = _mock_session_two_queries(
            [(item.url_hash, original.content_hash)],
            [original_title.lower()],
        )

        with patch("src.pipeline.stages.seen_filter.get_settings") as mock_settings:
            mock_settings.return_value.seen_window_days = 7
            result = await filter_already_seen(session, [item])

        assert len(result) == 1, (
            "content update was re-filtered by Pass 2 title similarity "
            "against its own stale stored title"
        )


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
            [(url_seen.url_hash, url_seen.content_hash)],  # url_seen: unchanged, filtered by hash
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
