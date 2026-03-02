"""Tests for src.extractors.webscraper -- WebScraperExtractor."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from src.extractors.base import ExtractedItem
from src.extractors.webscraper import (
    WebScraperExtractor,
    _extract_title_from_markdown,
    _filter_article_links,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _mock_settings(**overrides):
    """Return a minimal Settings-like object for webscraper extraction."""
    from src.core.config import Settings

    defaults = {
        "webscraper_urls": "https://example.com/news",
        "max_items_per_source": 50,
        "webscraper_max_concurrent": 3,
        "webscraper_page_timeout": 30,
        "enabled_sources": "webscraper",
        "telegram_bot_token": "",
        "telegram_chat_id": "",
        "telegram_alerts_enabled": False,
    }
    defaults.update(overrides)
    return Settings(**defaults)


@dataclass
class FakeCrawlResult:
    """Mimics Crawl4AI's CrawlResult for testing."""

    success: bool = True
    markdown: str = "# Test Article\n\nThis is a test article with enough content."
    links: dict[str, list[dict[str, str]]] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    error_message: str | None = None


def _make_index_result(internal_links: list[dict[str, str]]) -> FakeCrawlResult:
    """Build a FakeCrawlResult for an index page with article links."""
    return FakeCrawlResult(
        markdown="# News Index\n\nLatest articles.",
        links={"internal": internal_links, "external": []},
        metadata={"title": "News Index"},
    )


def _make_article_result(
    title: str = "Test Article",
    content: str = "A detailed article about artificial intelligence breakthroughs.",
) -> FakeCrawlResult:
    """Build a FakeCrawlResult for an article page."""
    return FakeCrawlResult(
        markdown=f"# {title}\n\n{content}",
        metadata={"title": title},
        links={"internal": [], "external": []},
    )


def _mock_crawler_context(arun_side_effect):
    """Create a mock AsyncWebCrawler that works as an async context manager.

    Args:
        arun_side_effect: A callable or list for mock.side_effect on arun().
    """
    mock_crawler_instance = MagicMock()
    mock_crawler_instance.arun = MagicMock(side_effect=arun_side_effect)
    # Make arun an async function.
    original_side_effect = mock_crawler_instance.arun.side_effect

    async def async_arun(url, config=None):
        if callable(original_side_effect) and not isinstance(original_side_effect, list):
            result = original_side_effect(url, config)
            return result
        # If it's a list, pop from it manually isn't needed;
        # we handle list via the call_count approach.
        raise NotImplementedError  # pragma: no cover

    # We'll use a different approach: build a proper async mock.
    call_results: dict[str, FakeCrawlResult] = {}
    if callable(arun_side_effect):
        _resolver = arun_side_effect
    else:
        _resolver = None

    class FakeAsyncCrawler:
        async def arun(self, url: str, config: Any = None) -> FakeCrawlResult:
            if _resolver is not None:
                return _resolver(url, config)
            raise RuntimeError(f"No result configured for {url}")  # pragma: no cover

    mock_class = MagicMock()
    fake_instance = FakeAsyncCrawler()
    mock_class.return_value.__aenter__ = MagicMock(return_value=fake_instance)
    mock_class.return_value.__aexit__ = MagicMock(return_value=None)

    # Make __aenter__ and __aexit__ async.
    async def aenter(*args):
        return fake_instance

    async def aexit(*args):
        pass

    mock_class.return_value.__aenter__ = aenter
    mock_class.return_value.__aexit__ = aexit

    return mock_class, fake_instance


def _build_mock_crawler_class(results_by_url: dict[str, FakeCrawlResult]):
    """Build a replacement AsyncWebCrawler class that returns results by URL."""

    class MockAsyncWebCrawler:
        def __init__(self, config=None):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def arun(self, url: str, config=None) -> FakeCrawlResult:
            if url in results_by_url:
                return results_by_url[url]
            return FakeCrawlResult(success=False, error_message="Not found")

    return MockAsyncWebCrawler


def _build_raising_crawler_class(exc: Exception):
    """Build a replacement AsyncWebCrawler class that raises on arun."""

    class RaisingCrawler:
        def __init__(self, config=None):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def arun(self, url: str, config=None):
            raise exc

    return RaisingCrawler


# ---------------------------------------------------------------------------
# TestSourceName
# ---------------------------------------------------------------------------
class TestSourceName:
    """WebScraperExtractor.source_name property."""

    def test_source_name_returns_webscraper(self):
        extractor = WebScraperExtractor()
        assert extractor.source_name == "webscraper"


# ---------------------------------------------------------------------------
# TestFilterArticleLinks
# ---------------------------------------------------------------------------
class TestFilterArticleLinks:
    """Tests for the _filter_article_links helper."""

    def test_filters_same_domain_only(self):
        links = [
            {"href": "https://example.com/blog/article-one", "text": "Article 1"},
            {"href": "https://other.com/blog/article-two", "text": "Article 2"},
            {"href": "https://example.com/news/story", "text": "Story"},
        ]
        result = _filter_article_links(links, "https://example.com/news")
        assert len(result) == 2
        assert all("example.com" in url for url in result)

    def test_filters_shallow_paths(self):
        links = [
            {"href": "https://example.com/", "text": "Home"},
            {"href": "https://example.com/news", "text": "News (same as index)"},
            {"href": "https://example.com/single", "text": "Single segment"},
            {"href": "https://example.com/blog/deep-article", "text": "Deep article"},
        ]
        result = _filter_article_links(links, "https://example.com/news")
        assert len(result) == 1
        assert "blog/deep-article" in result[0]

    def test_deduplicates_links(self):
        links = [
            {"href": "https://example.com/blog/article", "text": "Link 1"},
            {"href": "https://example.com/blog/article", "text": "Link 2"},
            {"href": "https://example.com/blog/article/", "text": "Link 3 trailing slash"},
        ]
        result = _filter_article_links(links, "https://example.com/news")
        assert len(result) == 1

    def test_filters_non_content_paths(self):
        links = [
            {"href": "https://example.com/company/about", "text": "About"},
            {"href": "https://example.com/user/login", "text": "Login"},
            {"href": "https://example.com/legal/privacy", "text": "Privacy"},
            {"href": "https://example.com/legal/terms", "text": "Terms"},
            {"href": "https://example.com/site/contact", "text": "Contact"},
            {"href": "https://example.com/blog/real-article", "text": "Article"},
        ]
        result = _filter_article_links(links, "https://example.com")
        assert len(result) == 1
        assert "real-article" in result[0]

    def test_handles_empty_links(self):
        result = _filter_article_links([], "https://example.com/news")
        assert result == []

    def test_handles_links_without_href(self):
        links = [
            {"text": "No href key"},
            {"href": "", "text": "Empty href"},
            {"href": "https://example.com/blog/valid", "text": "Valid"},
        ]
        result = _filter_article_links(links, "https://example.com")
        assert len(result) == 1
        assert "valid" in result[0]


# ---------------------------------------------------------------------------
# TestExtractTitleFromMarkdown
# ---------------------------------------------------------------------------
class TestExtractTitleFromMarkdown:
    """Tests for the _extract_title_from_markdown helper."""

    def test_uses_metadata_title(self):
        result = _extract_title_from_markdown(
            "# Some Heading\n\nBody text.", {"title": "Metadata Title"}
        )
        assert result == "Metadata Title"

    def test_falls_back_to_h1(self):
        result = _extract_title_from_markdown(
            "# My Article Title\n\nContent here.", {}
        )
        assert result == "My Article Title"

    def test_falls_back_to_first_line(self):
        result = _extract_title_from_markdown(
            "This is the first line\n\nMore content.", {}
        )
        assert result == "This is the first line"

    def test_truncates_long_first_line(self):
        long_line = "A" * 300
        result = _extract_title_from_markdown(long_line, {})
        assert len(result) == 200

    def test_returns_untitled_for_empty_markdown(self):
        result = _extract_title_from_markdown("", {})
        assert result == "Untitled"

    def test_returns_untitled_for_none_metadata(self):
        result = _extract_title_from_markdown("", None)
        assert result == "Untitled"

    def test_empty_metadata_title_falls_back_to_h1(self):
        result = _extract_title_from_markdown(
            "# Heading Title\n\nBody.", {"title": ""}
        )
        assert result == "Heading Title"


# ---------------------------------------------------------------------------
# TestExtract
# ---------------------------------------------------------------------------
class TestExtract:
    """WebScraperExtractor.extract() with mocked crawler."""

    async def test_extract_returns_empty_when_no_urls_configured(self):
        settings = _mock_settings(webscraper_urls="")
        with patch("src.extractors.webscraper.get_settings", return_value=settings):
            extractor = WebScraperExtractor()
            result = await extractor.extract()
        assert result == []

    async def test_extract_returns_extracted_items(self):
        """Full two-phase extraction returns ExtractedItem instances."""
        index_result = _make_index_result([
            {"href": "https://example.com/blog/ai-article", "text": "AI Article"},
            {"href": "https://example.com/blog/ml-article", "text": "ML Article"},
        ])
        article1 = _make_article_result(title="AI Article", content="Content about AI.")
        article2 = _make_article_result(title="ML Article", content="Content about ML.")

        results_by_url = {
            "https://example.com/news": index_result,
            "https://example.com/blog/ai-article": article1,
            "https://example.com/blog/ml-article": article2,
        }
        mock_crawler_cls = _build_mock_crawler_class(results_by_url)

        settings = _mock_settings()
        with (
            patch("src.extractors.webscraper.get_settings", return_value=settings),
            patch("src.extractors.webscraper.AsyncWebCrawler", mock_crawler_cls),
        ):
            extractor = WebScraperExtractor()
            result = await extractor.extract()

        assert len(result) == 2
        assert all(isinstance(item, ExtractedItem) for item in result)
        titles = {item.title for item in result}
        assert "AI Article" in titles
        assert "ML Article" in titles

    async def test_extract_handles_failed_index_crawl(self):
        """If index page crawl fails, return empty list."""
        failed_result = FakeCrawlResult(success=False, error_message="Timeout")

        results_by_url = {"https://example.com/news": failed_result}
        mock_crawler_cls = _build_mock_crawler_class(results_by_url)

        settings = _mock_settings()
        with (
            patch("src.extractors.webscraper.get_settings", return_value=settings),
            patch("src.extractors.webscraper.AsyncWebCrawler", mock_crawler_cls),
        ):
            extractor = WebScraperExtractor()
            result = await extractor.extract()

        assert result == []

    async def test_extract_skips_failed_article_crawl(self):
        """Failed article crawls are skipped; successful ones are returned."""
        index_result = _make_index_result([
            {"href": "https://example.com/blog/good-article", "text": "Good"},
            {"href": "https://example.com/blog/bad-article", "text": "Bad"},
        ])
        good_article = _make_article_result(title="Good Article")
        bad_article = FakeCrawlResult(success=False, error_message="500 Error")

        results_by_url = {
            "https://example.com/news": index_result,
            "https://example.com/blog/good-article": good_article,
            "https://example.com/blog/bad-article": bad_article,
        }
        mock_crawler_cls = _build_mock_crawler_class(results_by_url)

        settings = _mock_settings()
        with (
            patch("src.extractors.webscraper.get_settings", return_value=settings),
            patch("src.extractors.webscraper.AsyncWebCrawler", mock_crawler_cls),
        ):
            extractor = WebScraperExtractor()
            result = await extractor.extract()

        assert len(result) == 1
        assert result[0].title == "Good Article"

    async def test_extract_respects_max_items_per_source(self):
        """Output is truncated to max_items_per_source."""
        links = [
            {"href": f"https://example.com/blog/post-{i}", "text": f"Post {i}"}
            for i in range(10)
        ]
        index_result = _make_index_result(links)

        results_by_url: dict[str, FakeCrawlResult] = {
            "https://example.com/news": index_result,
        }
        for i in range(10):
            url = f"https://example.com/blog/post-{i}"
            results_by_url[url] = _make_article_result(title=f"Post {i}")

        mock_crawler_cls = _build_mock_crawler_class(results_by_url)

        settings = _mock_settings(max_items_per_source=3)
        with (
            patch("src.extractors.webscraper.get_settings", return_value=settings),
            patch("src.extractors.webscraper.AsyncWebCrawler", mock_crawler_cls),
        ):
            extractor = WebScraperExtractor()
            result = await extractor.extract()

        assert len(result) == 3

    async def test_extract_maps_fields_correctly(self):
        """Verify all ExtractedItem fields are mapped correctly."""
        index_result = _make_index_result([
            {"href": "https://example.com/blog/test-post", "text": "Test"},
        ])
        article_result = _make_article_result(
            title="Test Post",
            content="This is the article body content for testing.",
        )

        results_by_url = {
            "https://example.com/news": index_result,
            "https://example.com/blog/test-post": article_result,
        }
        mock_crawler_cls = _build_mock_crawler_class(results_by_url)

        settings = _mock_settings()
        with (
            patch("src.extractors.webscraper.get_settings", return_value=settings),
            patch("src.extractors.webscraper.AsyncWebCrawler", mock_crawler_cls),
        ):
            extractor = WebScraperExtractor()
            result = await extractor.extract()

        assert len(result) == 1
        item = result[0]
        assert item.title == "Test Post"
        assert item.source == "webscraper"
        assert item.url == "https://example.com/blog/test-post"
        assert item.text is not None
        assert "article body content" in item.text
        assert item.author == "example.com"
        assert item.published_at is None
        assert item.score == 0
        # Metadata fields.
        assert item.metadata["domain"] == "example.com"
        assert item.metadata["scraper_source"] == "crawl4ai"
        assert item.metadata["word_count"] > 0
        assert item.metadata["index_url"] == "https://example.com/news"

    async def test_extract_handles_crawler_exception(self):
        """If crawler.arun raises for the index page, the error propagates
        through the try/except in extract() and that index is skipped."""
        raising_cls = _build_raising_crawler_class(RuntimeError("Browser crashed"))

        settings = _mock_settings()
        with (
            patch("src.extractors.webscraper.get_settings", return_value=settings),
            patch("src.extractors.webscraper.AsyncWebCrawler", raising_cls),
        ):
            extractor = WebScraperExtractor()
            # The exception is caught in extract() per-index, returns [].
            result = await extractor.extract()

        assert result == []

    async def test_extract_handles_article_crawl_exception(self):
        """If crawler.arun raises for an article, that article is skipped."""
        index_result = _make_index_result([
            {"href": "https://example.com/blog/exploding", "text": "Boom"},
        ])

        call_count = 0

        class PartialFailCrawler:
            def __init__(self, config=None):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                pass

            async def arun(self, url: str, config=None):
                nonlocal call_count
                call_count += 1
                if call_count == 1:
                    return index_result
                raise ConnectionError("Network error")

        settings = _mock_settings()
        with (
            patch("src.extractors.webscraper.get_settings", return_value=settings),
            patch("src.extractors.webscraper.AsyncWebCrawler", PartialFailCrawler),
        ):
            extractor = WebScraperExtractor()
            result = await extractor.extract()

        assert result == []
