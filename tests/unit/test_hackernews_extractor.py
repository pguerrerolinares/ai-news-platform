"""Tests for src.extractors.hackernews -- HackerNewsExtractor."""

from __future__ import annotations

from unittest.mock import patch

import httpx
import respx

from src.extractors.base import ExtractedItem
from src.extractors.hackernews import BASE_URL, HackerNewsExtractor


# ---------------------------------------------------------------------------
# Sample Algolia response data
# ---------------------------------------------------------------------------
def _make_hit(
    object_id: str = "123",
    title: str = "Test AI Story",
    url: str = "https://example.com",
    points: int = 100,
    num_comments: int = 50,
    author: str = "testuser",
    created_at_i: int = 1708000000,
) -> dict:
    """Build a single HN Algolia hit dict."""
    return {
        "objectID": object_id,
        "title": title,
        "url": url,
        "points": points,
        "num_comments": num_comments,
        "author": author,
        "created_at_i": created_at_i,
    }


def _algolia_response(hits: list[dict]) -> dict:
    """Wrap hits in the Algolia search response structure."""
    return {
        "hits": hits,
        "nbHits": len(hits),
        "page": 0,
        "nbPages": 1,
        "hitsPerPage": 50,
    }


def _mock_settings(**overrides):
    """Return a minimal Settings-like object for HN extraction."""
    from src.core.config import Settings

    defaults = {
        "hn_min_points": 10,
        "hn_search_queries": "AI",
        "max_items_per_source": 50,
        "extraction_since_hours": 24,
        "enabled_sources": "hackernews",
        "telegram_bot_token": "",
        "telegram_chat_id": "",
        "telegram_alerts_enabled": False,
    }
    defaults.update(overrides)
    return Settings(**defaults)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------
class TestSourceName:
    """HackerNewsExtractor.source_name property."""

    def test_source_name_returns_hackernews(self):
        extractor = HackerNewsExtractor()
        assert extractor.source_name == "hackernews"


class TestExtract:
    """HackerNewsExtractor.extract() with mocked HTTP responses."""

    @respx.mock
    async def test_extract_returns_list_of_extracted_items(self):
        """extract() should return a list of ExtractedItem instances."""
        hits = [
            _make_hit("1", "Story A", "https://a.com", 200),
            _make_hit("2", "Story B", "https://b.com", 150),
        ]
        respx.get(BASE_URL).mock(
            return_value=httpx.Response(200, json=_algolia_response(hits)),
        )

        settings = _mock_settings()
        with patch("src.extractors.hackernews.get_settings", return_value=settings):
            extractor = HackerNewsExtractor()
            result = await extractor.extract(since_hours=24)

        assert isinstance(result, list)
        assert len(result) == 2
        for item in result:
            assert isinstance(item, ExtractedItem)

    @respx.mock
    async def test_items_have_correct_source(self):
        """Every returned item must have source='hackernews'."""
        hits = [_make_hit("10", "AI Paper", "https://paper.com", 300)]
        respx.get(BASE_URL).mock(
            return_value=httpx.Response(200, json=_algolia_response(hits)),
        )

        settings = _mock_settings()
        with patch("src.extractors.hackernews.get_settings", return_value=settings):
            extractor = HackerNewsExtractor()
            result = await extractor.extract()

        assert all(item.source == "hackernews" for item in result)

    @respx.mock
    async def test_items_sorted_by_score_descending(self):
        """Items must be sorted by score in descending order."""
        hits = [
            _make_hit("1", "Low Score", "https://a.com", 50),
            _make_hit("2", "High Score", "https://b.com", 500),
            _make_hit("3", "Mid Score", "https://c.com", 200),
        ]
        respx.get(BASE_URL).mock(
            return_value=httpx.Response(200, json=_algolia_response(hits)),
        )

        settings = _mock_settings()
        with patch("src.extractors.hackernews.get_settings", return_value=settings):
            extractor = HackerNewsExtractor()
            result = await extractor.extract()

        scores = [item.score for item in result]
        assert scores == sorted(scores, reverse=True)
        assert scores == [500, 200, 50]

    @respx.mock
    async def test_deduplication_by_story_id(self):
        """Duplicate objectIDs across queries should be deduplicated."""
        hits = [
            _make_hit("42", "Same Story", "https://same.com", 100),
            _make_hit("42", "Same Story", "https://same.com", 100),
            _make_hit("99", "Different Story", "https://other.com", 80),
        ]
        respx.get(BASE_URL).mock(
            return_value=httpx.Response(200, json=_algolia_response(hits)),
        )

        settings = _mock_settings()
        with patch("src.extractors.hackernews.get_settings", return_value=settings):
            extractor = HackerNewsExtractor()
            result = await extractor.extract()

        # Only two unique story IDs (42 and 99)
        story_ids = [item.metadata["story_id"] for item in result]
        assert len(result) == 2
        assert "42" in story_ids
        assert "99" in story_ids

    @respx.mock
    async def test_dedup_across_multiple_queries(self):
        """When multiple queries return the same story ID, only one item is kept."""
        hit_shared = _make_hit("77", "Shared Story", "https://shared.com", 300)
        hit_unique_a = _make_hit("10", "Only in AI", "https://only-ai.com", 200)
        hit_unique_b = _make_hit("20", "Only in LLM", "https://only-llm.com", 100)

        # Two queries, both return story 77, each also has a unique story
        call_count = 0

        def side_effect(request):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return httpx.Response(
                    200,
                    json=_algolia_response([hit_shared, hit_unique_a]),
                )
            return httpx.Response(
                200,
                json=_algolia_response([hit_shared, hit_unique_b]),
            )

        respx.get(BASE_URL).mock(side_effect=side_effect)

        settings = _mock_settings(hn_search_queries="AI,LLM")
        with patch("src.extractors.hackernews.get_settings", return_value=settings):
            extractor = HackerNewsExtractor()
            result = await extractor.extract()

        story_ids = {item.metadata["story_id"] for item in result}
        assert story_ids == {"77", "10", "20"}
        assert len(result) == 3

    @respx.mock
    async def test_empty_response_returns_empty_list(self):
        """An API response with no hits should return an empty list."""
        respx.get(BASE_URL).mock(
            return_value=httpx.Response(200, json=_algolia_response([])),
        )

        settings = _mock_settings()
        with patch("src.extractors.hackernews.get_settings", return_value=settings):
            extractor = HackerNewsExtractor()
            result = await extractor.extract()

        assert result == []

    @respx.mock
    async def test_http_error_returns_empty_list(self):
        """An HTTP 500 error should be handled gracefully, returning []."""
        respx.get(BASE_URL).mock(
            return_value=httpx.Response(500, text="Internal Server Error"),
        )

        settings = _mock_settings()
        with patch("src.extractors.hackernews.get_settings", return_value=settings):
            extractor = HackerNewsExtractor()
            result = await extractor.extract()

        assert result == []

    @respx.mock
    async def test_network_error_returns_empty_list(self):
        """A network-level exception should be caught, returning []."""
        respx.get(BASE_URL).mock(side_effect=httpx.ConnectError("Connection refused"))

        settings = _mock_settings()
        with patch("src.extractors.hackernews.get_settings", return_value=settings):
            extractor = HackerNewsExtractor()
            result = await extractor.extract()

        assert result == []

    @respx.mock
    async def test_item_metadata_contains_expected_keys(self):
        """Extracted items should carry story_id, hn_url, num_comments in metadata."""
        hits = [_make_hit("555", "Meta Test", "https://meta.com", 100, num_comments=42)]
        respx.get(BASE_URL).mock(
            return_value=httpx.Response(200, json=_algolia_response(hits)),
        )

        settings = _mock_settings()
        with patch("src.extractors.hackernews.get_settings", return_value=settings):
            extractor = HackerNewsExtractor()
            result = await extractor.extract()

        assert len(result) == 1
        meta = result[0].metadata
        assert meta["story_id"] == "555"
        assert meta["hn_url"] == "https://news.ycombinator.com/item?id=555"
        assert meta["num_comments"] == 42
        assert "search_query" in meta

    @respx.mock
    async def test_hit_without_url_uses_hn_url(self):
        """If a hit has no url field, the item URL should fall back to the HN item page."""
        hit = {
            "objectID": "999",
            "title": "Ask HN: Something",
            "url": None,
            "points": 120,
            "num_comments": 30,
            "author": "asker",
            "created_at_i": 1708000000,
        }
        respx.get(BASE_URL).mock(
            return_value=httpx.Response(200, json=_algolia_response([hit])),
        )

        settings = _mock_settings()
        with patch("src.extractors.hackernews.get_settings", return_value=settings):
            extractor = HackerNewsExtractor()
            result = await extractor.extract()

        assert len(result) == 1
        assert result[0].url == "https://news.ycombinator.com/item?id=999"

    @respx.mock
    async def test_max_items_per_source_limits_output(self):
        """Result should be truncated to max_items_per_source."""
        hits = [_make_hit(str(i), f"Story {i}", f"https://s{i}.com", 100 - i) for i in range(10)]
        respx.get(BASE_URL).mock(
            return_value=httpx.Response(200, json=_algolia_response(hits)),
        )

        settings = _mock_settings(max_items_per_source=3)
        with patch("src.extractors.hackernews.get_settings", return_value=settings):
            extractor = HackerNewsExtractor()
            result = await extractor.extract()

        assert len(result) == 3

    @respx.mock
    async def test_published_at_is_set(self):
        """Items should have published_at derived from created_at_i timestamp."""
        hits = [_make_hit("1", "Dated Story", "https://d.com", 100, created_at_i=1708000000)]
        respx.get(BASE_URL).mock(
            return_value=httpx.Response(200, json=_algolia_response(hits)),
        )

        settings = _mock_settings()
        with patch("src.extractors.hackernews.get_settings", return_value=settings):
            extractor = HackerNewsExtractor()
            result = await extractor.extract()

        assert result[0].published_at is not None
        assert result[0].published_at.year == 2024
