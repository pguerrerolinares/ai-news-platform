"""Tests for src.pipeline.dedup -- hash-based deduplication."""

from __future__ import annotations

from datetime import UTC, datetime

from src.extractors.base import ExtractedItem
from src.pipeline.dedup import deduplicate_items


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _item(
    title: str = "Default Title",
    url: str | None = "https://example.com/default",
    source: str = "hackernews",
    score: int | None = 100,
) -> ExtractedItem:
    """Shorthand factory for creating an ExtractedItem."""
    return ExtractedItem(
        title=title,
        source=source,
        url=url,
        text=title,
        author="test",
        published_at=datetime(2025, 6, 15, 12, 0, 0, tzinfo=UTC),
        score=score,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------
class TestEmptyInput:
    """Edge case: no items to deduplicate."""

    def test_empty_list_returns_empty_list(self):
        result = deduplicate_items([])
        assert result == []


class TestSingleItem:
    """Edge case: only one item."""

    def test_single_item_returns_unchanged(self):
        item = _item("Solo Story", "https://solo.com")
        result = deduplicate_items([item])
        assert len(result) == 1
        assert result[0] is item


class TestContentHashDedup:
    """Pass 1: content_hash dedup (title + url)."""

    def test_same_title_and_url_deduplicates(self):
        """Two items with identical title and url should collapse to one."""
        a = _item("Same Title", "https://same.com", score=50)
        b = _item("Same Title", "https://same.com", score=80)

        result = deduplicate_items([a, b])

        # content_hash pass keeps the first encountered
        assert len(result) == 1

    def test_different_title_same_url_are_both_kept_after_content_pass(self):
        """Different titles but same URL pass content_hash but get deduped by url_hash."""
        a = _item("Title A", "https://same.com", score=50)
        b = _item("Title B", "https://same.com", score=80)

        # Both have different content_hash (different titles)
        assert a.content_hash != b.content_hash

        result = deduplicate_items([a, b])

        # url_hash pass keeps the one with highest score
        assert len(result) == 1
        assert result[0].score == 80

    def test_same_title_different_url_are_distinct(self):
        """Same title, different URL = different content_hash, different url_hash."""
        a = _item("Same Title", "https://a.com", score=50)
        b = _item("Same Title", "https://b.com", score=80)

        result = deduplicate_items([a, b])

        assert len(result) == 2


class TestUrlHashDedup:
    """Pass 2: url_hash dedup (same URL, keep highest score)."""

    def test_same_url_different_titles_keeps_highest_score(self):
        """Two items with the same URL but different titles: keep the one with higher score."""
        low = _item("Low Score Version", "https://article.com", score=30)
        high = _item("High Score Version", "https://article.com", score=300)

        result = deduplicate_items([low, high])

        assert len(result) == 1
        assert result[0].score == 300
        assert result[0].title == "High Score Version"

    def test_same_url_first_has_higher_score(self):
        """When the first item has the higher score, it is the one kept."""
        high = _item("First High", "https://article.com", score=200)
        low = _item("Second Low", "https://article.com", score=10)

        result = deduplicate_items([high, low])

        assert len(result) == 1
        assert result[0].score == 200

    def test_same_url_none_scores_keeps_first(self):
        """When both have None scores (treated as 0), the first one is kept."""
        a = _item("First", "https://article.com", score=None)
        b = _item("Second", "https://article.com", score=None)

        result = deduplicate_items([a, b])

        assert len(result) == 1
        assert result[0].title == "First"


class TestItemsWithoutUrl:
    """Items without a URL (url=None) should not be deduplicated by url_hash."""

    def test_no_url_items_are_kept(self):
        """Items with url=None should all be kept (each has unique content_hash)."""
        a = _item("No URL Story A", url=None, score=50)
        b = _item("No URL Story B", url=None, score=80)

        result = deduplicate_items([a, b])

        assert len(result) == 2

    def test_no_url_same_title_deduped_by_content_hash(self):
        """Items with url=None and same title have the same content_hash -> deduped."""
        a = _item("Identical Title", url=None, score=50)
        b = _item("Identical Title", url=None, score=80)

        # Both have same content_hash because title+'' is the same
        assert a.content_hash == b.content_hash

        result = deduplicate_items([a, b])

        assert len(result) == 1

    def test_url_hash_is_none_for_no_url(self):
        """ExtractedItem.url_hash should return None when url is None."""
        item = _item("No URL", url=None)
        assert item.url_hash is None


class TestMixedScenario:
    """Combined scenario with multiple dedup types."""

    def test_five_items_with_content_and_url_dupes(self):
        """5 items: 2 content dupes + 1 url dupe -> correct final count.

        Items:
        1. "Story A" / https://a.com / score=100
        2. "Story A" / https://a.com / score=200  -- content dupe of #1
        3. "Story B" / https://b.com / score=150
        4. "Story C" / https://b.com / score=300  -- url dupe of #3 (different title, same URL)
        5. "Story D" / https://d.com / score=50   -- unique

        After content dedup: #1, #3, #4, #5 (4 items) -- #2 removed
        After url dedup: keeps #4 (score 300 > 150 for https://b.com), #1, #5 -> 3 items
        """
        items = [
            _item("Story A", "https://a.com", score=100),
            _item("Story A", "https://a.com", score=200),  # content dupe
            _item("Story B", "https://b.com", score=150),
            _item("Story C", "https://b.com", score=300),  # url dupe, higher score
            _item("Story D", "https://d.com", score=50),  # unique
        ]

        result = deduplicate_items(items)

        assert len(result) == 3

        result_titles = {item.title for item in result}
        assert "Story A" in result_titles
        assert "Story D" in result_titles
        # For the https://b.com URL, Story C (score 300) should win
        assert "Story C" in result_titles
        assert "Story B" not in result_titles

    def test_mixed_with_no_url_items(self):
        """Mix of items with and without URLs.

        Items:
        1. "News A" / https://a.com / score=100  -- unique
        2. "News B" / None           / score=50   -- unique (no URL)
        3. "News C" / https://a.com / score=200  -- url dupe of #1
        4. "News D" / None           / score=80   -- unique (no URL, different title)
        """
        items = [
            _item("News A", "https://a.com", score=100),
            _item("News B", url=None, score=50),
            _item("News C", "https://a.com", score=200),
            _item("News D", url=None, score=80),
        ]

        result = deduplicate_items(items)

        # #1 and #3 share the same URL; #3 has higher score -> #3 kept
        # #2 and #4 have no URL but different titles -> both kept
        assert len(result) == 3

        result_titles = {item.title for item in result}
        assert "News C" in result_titles  # url winner
        assert "News B" in result_titles
        assert "News D" in result_titles

    def test_cross_source_dedup(self):
        """Items from different sources with the same URL should be deduped."""
        hn_item = _item("AI Tool Launch", "https://tool.ai", source="hackernews", score=200)
        reddit_item = _item("AI Tool Launch (Reddit)", "https://tool.ai", source="reddit", score=50)

        result = deduplicate_items([hn_item, reddit_item])

        # Same URL -> url_hash dedup keeps higher score
        assert len(result) == 1
        assert result[0].source == "hackernews"
        assert result[0].score == 200


class TestContentHashProperty:
    """Verify that content_hash is deterministic and correct."""

    def test_same_title_url_produces_same_hash(self):
        a = _item("X", "https://x.com")
        b = _item("X", "https://x.com")
        assert a.content_hash == b.content_hash

    def test_different_title_produces_different_hash(self):
        a = _item("A", "https://x.com")
        b = _item("B", "https://x.com")
        assert a.content_hash != b.content_hash

    def test_hash_length_is_16(self):
        item = _item("Test", "https://test.com")
        assert len(item.content_hash) == 16

    def test_url_hash_length_is_16(self):
        item = _item("Test", "https://test.com")
        assert item.url_hash is not None
        assert len(item.url_hash) == 16
