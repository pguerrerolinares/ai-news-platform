"""Tests for src.extractors.base -- ExtractedItem and BaseExtractor."""

from __future__ import annotations

import pytest

from src.extractors.base import BaseExtractor, ExtractedItem


# ---------------------------------------------------------------------------
# ExtractedItem.content_hash
# ---------------------------------------------------------------------------
class TestExtractedItemContentHash:
    """Verify content_hash is deterministic and based on title + url."""

    def test_content_hash_is_deterministic(self):
        item1 = ExtractedItem(title="Hello", source="hackernews", url="https://example.com")
        item2 = ExtractedItem(title="Hello", source="hackernews", url="https://example.com")
        assert item1.content_hash == item2.content_hash

    def test_content_hash_changes_with_title(self):
        item1 = ExtractedItem(title="Title A", source="hackernews", url="https://example.com")
        item2 = ExtractedItem(title="Title B", source="hackernews", url="https://example.com")
        assert item1.content_hash != item2.content_hash

    def test_content_hash_changes_with_url(self):
        item1 = ExtractedItem(title="Same", source="hackernews", url="https://a.com")
        item2 = ExtractedItem(title="Same", source="hackernews", url="https://b.com")
        assert item1.content_hash != item2.content_hash

    def test_content_hash_is_16_chars(self):
        item = ExtractedItem(title="Test", source="arxiv", url="https://arxiv.org/123")
        assert len(item.content_hash) == 16

    def test_content_hash_with_no_url(self):
        """When url is None, content_hash uses empty string for the url part."""
        item = ExtractedItem(title="No URL", source="reddit")
        h = item.content_hash
        assert isinstance(h, str)
        assert len(h) == 16

    def test_content_hash_same_title_none_url_is_deterministic(self):
        item1 = ExtractedItem(title="Same Title", source="rss")
        item2 = ExtractedItem(title="Same Title", source="rss")
        assert item1.content_hash == item2.content_hash

    def test_content_hash_ignores_source_field(self):
        """content_hash should depend only on title + url, not on source."""
        item1 = ExtractedItem(title="Title", source="hackernews", url="https://x.com")
        item2 = ExtractedItem(title="Title", source="arxiv", url="https://x.com")
        assert item1.content_hash == item2.content_hash


# ---------------------------------------------------------------------------
# ExtractedItem.url_hash
# ---------------------------------------------------------------------------
class TestExtractedItemUrlHash:
    """Verify url_hash behavior with and without URLs."""

    def test_url_hash_is_none_when_no_url(self):
        item = ExtractedItem(title="No URL", source="reddit")
        assert item.url_hash is None

    def test_url_hash_is_none_when_url_is_none_explicitly(self):
        item = ExtractedItem(title="No URL", source="reddit", url=None)
        assert item.url_hash is None

    def test_url_hash_is_string_when_url_present(self):
        item = ExtractedItem(title="Has URL", source="hackernews", url="https://example.com")
        assert isinstance(item.url_hash, str)

    def test_url_hash_is_16_chars(self):
        item = ExtractedItem(title="X", source="hackernews", url="https://example.com")
        assert len(item.url_hash) == 16

    def test_url_hash_is_deterministic(self):
        item1 = ExtractedItem(title="A", source="hackernews", url="https://example.com/same")
        item2 = ExtractedItem(title="B", source="arxiv", url="https://example.com/same")
        assert item1.url_hash == item2.url_hash

    def test_url_hash_differs_for_different_urls(self):
        item1 = ExtractedItem(title="X", source="rss", url="https://a.com")
        item2 = ExtractedItem(title="X", source="rss", url="https://b.com")
        assert item1.url_hash != item2.url_hash


# ---------------------------------------------------------------------------
# BaseExtractor cannot be instantiated
# ---------------------------------------------------------------------------
class TestBaseExtractorAbstract:
    """Verify that BaseExtractor is abstract and cannot be instantiated directly."""

    def test_cannot_instantiate(self):
        with pytest.raises(TypeError):
            BaseExtractor()  # type: ignore[abstract]

    def test_subclass_must_implement_source_name(self):
        """A subclass missing source_name should raise TypeError."""

        class Incomplete(BaseExtractor):
            async def extract(self, since_hours: int = 24) -> list[ExtractedItem]:
                return []

        with pytest.raises(TypeError):
            Incomplete()  # type: ignore[abstract]

    def test_subclass_must_implement_extract(self):
        """A subclass missing extract should raise TypeError."""

        class Incomplete(BaseExtractor):
            @property
            def source_name(self) -> str:
                return "test"

        with pytest.raises(TypeError):
            Incomplete()  # type: ignore[abstract]

    def test_complete_subclass_works(self):
        """A fully implemented subclass can be instantiated."""

        class Complete(BaseExtractor):
            @property
            def source_name(self) -> str:
                return "test"

            async def extract(self, since_hours: int = 24) -> list[ExtractedItem]:
                return []

        extractor = Complete()
        assert extractor.source_name == "test"


# ---------------------------------------------------------------------------
# Edge cases for ExtractedItem hashing and sorting
# ---------------------------------------------------------------------------
class TestEdgeCases:
    """Edge cases for ExtractedItem hashing and sorting."""

    def test_content_hash_empty_title(self):
        """Empty title still produces a deterministic hash."""
        item = ExtractedItem(title="", source="test", url="https://x.com")
        assert isinstance(item.content_hash, str)
        assert len(item.content_hash) == 16

    def test_url_hash_empty_url(self):
        """Empty URL returns None (no URL to hash)."""
        item = ExtractedItem(title="Foo", source="test", url="")
        assert item.url_hash is None

    def test_url_hash_none_url(self):
        """None URL returns None."""
        item = ExtractedItem(title="Foo", source="test", url=None)
        assert item.url_hash is None
