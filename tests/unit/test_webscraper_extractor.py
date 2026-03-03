"""Tests for src.extractors.webscraper -- WebScraperExtractor (httpx + readability)."""

from __future__ import annotations

from unittest.mock import patch

import httpx

from src.extractors.base import ExtractedItem
from src.extractors.webscraper import (
    WebScraperExtractor,
    _extract_links_from_html,
    _filter_article_links,
    _html_to_text,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _mock_settings(**overrides):
    """Return a minimal Settings for webscraper tests."""
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


_INDEX_HTML = """\
<html><body>
<h1>News Index</h1>
<a href="https://example.com/blog/ai-article">AI Article</a>
<a href="https://example.com/blog/ml-article">ML Article</a>
<a href="https://other.com/external">External</a>
<a href="/about">About</a>
</body></html>
"""

_ARTICLE_HTML = """\
<html><head><title>{title}</title></head>
<body>
<article>
<h1>{title}</h1>
<p>{content}</p>
</article>
<nav>Navigation stuff</nav>
<footer>Footer stuff</footer>
</body></html>
"""


def _make_article_html(
    title: str = "Test Article",
    content: str = "A detailed article about artificial intelligence breakthroughs.",
) -> str:
    return _ARTICLE_HTML.format(title=title, content=content)


def _response(status: int, text: str, url: str = "https://example.com") -> httpx.Response:
    """Create an httpx.Response with request set (needed for raise_for_status)."""
    return httpx.Response(status, text=text, request=httpx.Request("GET", url))


# ---------------------------------------------------------------------------
# TestExtractLinksFromHtml
# ---------------------------------------------------------------------------
class TestExtractLinksFromHtml:
    """Tests for the _extract_links_from_html helper."""

    def test_extracts_links_with_absolute_urls(self):
        html = '<html><body><a href="https://example.com/post">Post</a></body></html>'
        links = _extract_links_from_html(html, "https://example.com")
        assert len(links) == 1
        assert links[0]["href"] == "https://example.com/post"
        assert links[0]["text"] == "Post"

    def test_resolves_relative_urls(self):
        html = '<html><body><a href="/blog/post">Post</a></body></html>'
        links = _extract_links_from_html(html, "https://example.com/news")
        assert len(links) == 1
        assert links[0]["href"] == "https://example.com/blog/post"

    def test_skips_anchors_and_javascript(self):
        html = """<html><body>
        <a href="#section">Anchor</a>
        <a href="javascript:void(0)">JS</a>
        <a href="mailto:test@example.com">Email</a>
        <a href="https://example.com/real">Real</a>
        </body></html>"""
        links = _extract_links_from_html(html, "https://example.com")
        assert len(links) == 1
        assert "real" in links[0]["href"]

    def test_handles_invalid_html(self):
        links = _extract_links_from_html("not html at all {{{{", "https://example.com")
        assert links == []


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
# TestHtmlToText
# ---------------------------------------------------------------------------
class TestHtmlToText:
    """Tests for the _html_to_text helper."""

    def test_strips_tags(self):
        result = _html_to_text("<p>Hello <b>world</b></p>")
        assert "Hello" in result
        assert "world" in result
        assert "<" not in result

    def test_handles_empty_string(self):
        assert _html_to_text("") == ""

    def test_handles_plain_text(self):
        result = _html_to_text("No tags here")
        assert "No tags here" in result


# ---------------------------------------------------------------------------
# TestSourceName
# ---------------------------------------------------------------------------
class TestSourceName:
    """WebScraperExtractor.source_name property."""

    def test_source_name_returns_webscraper(self):
        extractor = WebScraperExtractor()
        assert extractor.source_name == "webscraper"


# ---------------------------------------------------------------------------
# TestExtract
# ---------------------------------------------------------------------------
class TestExtract:
    """WebScraperExtractor.extract() with mocked httpx."""

    async def test_extract_returns_empty_when_no_urls_configured(self):
        settings = _mock_settings(webscraper_urls="")
        with patch("src.extractors.webscraper.get_settings", return_value=settings):
            extractor = WebScraperExtractor()
            result = await extractor.extract()
        assert result == []

    async def test_extract_returns_extracted_items(self):
        """Full two-phase extraction returns ExtractedItem instances."""
        index_html = _INDEX_HTML
        article1_html = _make_article_html(title="AI Article", content="Content about AI.")
        article2_html = _make_article_html(title="ML Article", content="Content about ML.")

        responses = {
            "https://example.com/news": _response(200, index_html, "https://example.com/news"),
            "https://example.com/blog/ai-article": _response(
                200, article1_html, "https://example.com/blog/ai-article"
            ),
            "https://example.com/blog/ml-article": _response(
                200, article2_html, "https://example.com/blog/ml-article"
            ),
        }

        async def mock_get(url, **kwargs):
            if str(url) in responses:
                return responses[str(url)]
            return _response(404, "", str(url))

        settings = _mock_settings()
        with patch("src.extractors.webscraper.get_settings", return_value=settings):
            extractor = WebScraperExtractor()
            with patch.object(httpx.AsyncClient, "get", side_effect=mock_get):
                result = await extractor.extract()

        assert len(result) == 2
        assert all(isinstance(item, ExtractedItem) for item in result)
        titles = {item.title for item in result}
        assert "AI Article" in titles
        assert "ML Article" in titles

    async def test_extract_handles_failed_index_fetch(self):
        """If index page returns error, return empty list."""

        async def mock_get(url, **kwargs):
            raise httpx.HTTPStatusError(
                "Server Error",
                request=httpx.Request("GET", url),
                response=httpx.Response(500),
            )

        settings = _mock_settings()
        with patch("src.extractors.webscraper.get_settings", return_value=settings):
            extractor = WebScraperExtractor()
            with patch.object(httpx.AsyncClient, "get", side_effect=mock_get):
                result = await extractor.extract()

        assert result == []

    async def test_extract_skips_failed_article_fetch(self):
        """Failed article fetches are skipped; successful ones are returned."""
        index_html = """\
        <html><body>
        <a href="https://example.com/blog/good-article">Good</a>
        <a href="https://example.com/blog/bad-article">Bad</a>
        </body></html>
        """
        good_html = _make_article_html(title="Good Article")

        call_count = 0

        async def mock_get(url, **kwargs):
            nonlocal call_count
            call_count += 1
            url_str = str(url)
            if "news" in url_str:
                return _response(200, index_html, url_str)
            if "good-article" in url_str:
                return _response(200, good_html, url_str)
            raise httpx.ConnectError("Connection refused")

        settings = _mock_settings()
        with patch("src.extractors.webscraper.get_settings", return_value=settings):
            extractor = WebScraperExtractor()
            with patch.object(httpx.AsyncClient, "get", side_effect=mock_get):
                result = await extractor.extract()

        assert len(result) == 1
        assert result[0].title == "Good Article"

    async def test_extract_respects_max_items_per_source(self):
        """Output is truncated to max_items_per_source."""
        links_html = "".join(
            f'<a href="https://example.com/blog/post-{i}">Post {i}</a>' for i in range(10)
        )
        index_html = f"<html><body>{links_html}</body></html>"

        async def mock_get(url, **kwargs):
            url_str = str(url)
            if "news" in url_str:
                return _response(200, index_html, url_str)
            return _response(200, _make_article_html(title="Post"), url_str)

        settings = _mock_settings(max_items_per_source=3)
        with patch("src.extractors.webscraper.get_settings", return_value=settings):
            extractor = WebScraperExtractor()
            with patch.object(httpx.AsyncClient, "get", side_effect=mock_get):
                result = await extractor.extract()

        assert len(result) == 3

    async def test_extract_maps_fields_correctly(self):
        """Verify all ExtractedItem fields are mapped correctly."""
        index_html = """\
        <html><body>
        <a href="https://example.com/blog/test-post">Test</a>
        </body></html>
        """
        article_html = _make_article_html(
            title="Test Post",
            content="This is the article body content for testing.",
        )

        async def mock_get(url, **kwargs):
            url_str = str(url)
            if "news" in url_str:
                return _response(200, index_html, url_str)
            return _response(200, article_html, url_str)

        settings = _mock_settings()
        with patch("src.extractors.webscraper.get_settings", return_value=settings):
            extractor = WebScraperExtractor()
            with patch.object(httpx.AsyncClient, "get", side_effect=mock_get):
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
        assert item.metadata["domain"] == "example.com"
        assert item.metadata["scraper_source"] == "readability"
        assert item.metadata["word_count"] > 0
        assert item.metadata["index_url"] == "https://example.com/news"

    async def test_extract_handles_connection_error(self):
        """If httpx raises for all index pages, return empty."""

        async def mock_get(url, **kwargs):
            raise httpx.ConnectError("Connection refused")

        settings = _mock_settings()
        with patch("src.extractors.webscraper.get_settings", return_value=settings):
            extractor = WebScraperExtractor()
            with patch.object(httpx.AsyncClient, "get", side_effect=mock_get):
                result = await extractor.extract()

        assert result == []
