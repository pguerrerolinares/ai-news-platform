"""Tests for src.extractors.rss -- RSSExtractor."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import httpx
import pytest
import respx

from src.extractors.base import ExtractedItem
from src.extractors.rss import RSSExtractor


@pytest.fixture(autouse=True)
def _skip_ssrf_dns():
    """Neutralize assert_safe_url's real DNS lookups so tests stay hermetic.

    safe_get re-validates every hop; respx mocks the HTTP but not getaddrinfo.
    """

    async def _noop(_url: str) -> None:
        return None

    with patch("src.core.ssrf.assert_safe_url", _noop):
        yield

# ---------------------------------------------------------------------------
# Sample RSS feed data
# ---------------------------------------------------------------------------
FEED_URL_OPENAI = "https://openai.com/blog/rss.xml"
FEED_URL_GOOGLE = "https://blog.google/technology/ai/rss/"


def _recent_rfc2822() -> str:
    """Return an RFC 2822 date string for 1 hour ago (always within 48h window)."""
    dt = datetime.now(tz=UTC) - timedelta(hours=1)
    return dt.strftime("%a, %d %b %Y %H:%M:%S +0000")


def _old_rfc2822() -> str:
    """Return an RFC 2822 date string for 72 hours ago (outside 48h window)."""
    dt = datetime.now(tz=UTC) - timedelta(hours=72)
    return dt.strftime("%a, %d %b %Y %H:%M:%S +0000")


def _make_entry(
    title: str = "New AI Feature Announced",
    link: str = "https://openai.com/blog/new-feature",
    description: str = "<p>We are excited to announce a <b>new feature</b>.</p>",
    author: str = "OpenAI Team",
    pub_date: str | None = None,
    tags: str = "",
) -> str:
    """Build a single RSS <item> XML element."""
    if pub_date is None:
        pub_date = _recent_rfc2822()
    tag_xml = ""
    if tags:
        for tag in tags.split(","):
            tag_xml += f"<category>{tag.strip()}</category>\n"
    return f"""
    <item>
      <title>{title}</title>
      <link>{link}</link>
      <description>{description}</description>
      <author>{author}</author>
      <pubDate>{pub_date}</pubDate>
      {tag_xml}
    </item>"""


def _make_feed(items_xml: list[str], feed_title: str = "OpenAI Blog") -> str:
    """Wrap <item> elements in a minimal RSS 2.0 feed."""
    items_joined = "\n".join(items_xml)
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>{feed_title}</title>
    <link>https://openai.com/blog</link>
    <description>Latest posts from {feed_title}</description>
    {items_joined}
  </channel>
</rss>"""


def _mock_settings(**overrides):
    """Return a minimal Settings-like object for RSS extraction."""
    from src.core.config import Settings

    defaults = {
        "rss_feeds": FEED_URL_OPENAI,
        "max_items_per_source": 50,
        "enabled_sources": "rss",
    }
    defaults.update(overrides)
    return Settings(**defaults)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------
class TestSourceName:
    """RSSExtractor.source_name property."""

    def test_source_name_returns_rss(self):
        extractor = RSSExtractor()
        assert extractor.source_name == "rss"


class TestExtract:
    """RSSExtractor.extract() with mocked HTTP responses."""

    @respx.mock
    async def test_extract_returns_list_of_extracted_items(self):
        """extract() should return a list of ExtractedItem instances."""
        entries = [
            _make_entry("Post A", "https://openai.com/blog/a"),
            _make_entry("Post B", "https://openai.com/blog/b"),
        ]
        feed_xml = _make_feed(entries)
        respx.get(FEED_URL_OPENAI).mock(
            return_value=httpx.Response(200, text=feed_xml),
        )

        settings = _mock_settings()
        with patch("src.extractors.rss.get_settings", return_value=settings):
            extractor = RSSExtractor()
            result = await extractor.extract(since_hours=48)

        assert isinstance(result, list)
        assert len(result) == 2
        for item in result:
            assert isinstance(item, ExtractedItem)

    @respx.mock
    async def test_items_have_correct_source(self):
        """Every returned item must have source='rss'."""
        entries = [_make_entry("AI Post", "https://openai.com/blog/ai")]
        feed_xml = _make_feed(entries)
        respx.get(FEED_URL_OPENAI).mock(
            return_value=httpx.Response(200, text=feed_xml),
        )

        settings = _mock_settings()
        with patch("src.extractors.rss.get_settings", return_value=settings):
            extractor = RSSExtractor()
            result = await extractor.extract()

        assert all(item.source == "rss" for item in result)

    @respx.mock
    async def test_48h_lookback_filters_old_entries(self):
        """Entries older than 48 hours should be filtered out."""
        entries = [
            _make_entry(
                "Recent Post", "https://openai.com/blog/recent", pub_date=_recent_rfc2822()
            ),
            _make_entry("Old Post", "https://openai.com/blog/old", pub_date=_old_rfc2822()),
        ]
        feed_xml = _make_feed(entries)
        respx.get(FEED_URL_OPENAI).mock(
            return_value=httpx.Response(200, text=feed_xml),
        )

        settings = _mock_settings()
        with patch("src.extractors.rss.get_settings", return_value=settings):
            extractor = RSSExtractor()
            result = await extractor.extract(since_hours=48)

        assert len(result) == 1
        assert result[0].title == "Recent Post"

    @respx.mock
    async def test_deduplication_by_url(self):
        """Duplicate URLs across feeds should be deduplicated."""
        entry = _make_entry("Same Post", "https://openai.com/blog/same")
        feed_xml = _make_feed([entry])

        respx.get(FEED_URL_OPENAI).mock(
            return_value=httpx.Response(200, text=feed_xml),
        )
        respx.get(FEED_URL_GOOGLE).mock(
            return_value=httpx.Response(200, text=feed_xml),
        )

        settings = _mock_settings(rss_feeds=f"{FEED_URL_OPENAI},{FEED_URL_GOOGLE}")
        with patch("src.extractors.rss.get_settings", return_value=settings):
            extractor = RSSExtractor()
            result = await extractor.extract()

        assert len(result) == 1

    @respx.mock
    async def test_html_cleanup_on_content(self):
        """HTML tags should be stripped from content text."""
        entries = [
            _make_entry(
                "HTML Post",
                "https://openai.com/blog/html",
                description="<p>This is <b>bold</b> and <i>italic</i> text.</p>",
            ),
        ]
        feed_xml = _make_feed(entries)
        respx.get(FEED_URL_OPENAI).mock(
            return_value=httpx.Response(200, text=feed_xml),
        )

        settings = _mock_settings()
        with patch("src.extractors.rss.get_settings", return_value=settings):
            extractor = RSSExtractor()
            result = await extractor.extract()

        assert len(result) == 1
        assert "<" not in result[0].text
        assert "bold" in result[0].text
        assert "italic" in result[0].text

    @respx.mock
    async def test_empty_feed_returns_empty_list(self):
        """An RSS feed with no entries should return an empty list."""
        feed_xml = _make_feed([])
        respx.get(FEED_URL_OPENAI).mock(
            return_value=httpx.Response(200, text=feed_xml),
        )

        settings = _mock_settings()
        with patch("src.extractors.rss.get_settings", return_value=settings):
            extractor = RSSExtractor()
            result = await extractor.extract()

        assert result == []

    @respx.mock
    async def test_http_error_returns_empty_list(self):
        """An HTTP 500 error should be handled gracefully, returning []."""
        respx.get(FEED_URL_OPENAI).mock(
            return_value=httpx.Response(500, text="Internal Server Error"),
        )

        settings = _mock_settings()
        with patch("src.extractors.rss.get_settings", return_value=settings):
            extractor = RSSExtractor()
            result = await extractor.extract()

        assert result == []

    @respx.mock
    async def test_network_error_returns_empty_list(self):
        """A network-level exception should be caught, returning []."""
        respx.get(FEED_URL_OPENAI).mock(
            side_effect=httpx.ConnectError("Connection refused"),
        )

        settings = _mock_settings()
        with patch("src.extractors.rss.get_settings", return_value=settings):
            extractor = RSSExtractor()
            result = await extractor.extract()

        assert result == []

    @respx.mock
    async def test_item_metadata_contains_expected_keys(self):
        """Extracted items should carry feed_url, source_name, tags, rss_id in metadata."""
        entries = [
            _make_entry(
                "Tagged Post",
                "https://openai.com/blog/tagged",
                tags="AI,GPT",
            ),
        ]
        feed_xml = _make_feed(entries, feed_title="OpenAI Blog")
        respx.get(FEED_URL_OPENAI).mock(
            return_value=httpx.Response(200, text=feed_xml),
        )

        settings = _mock_settings()
        with patch("src.extractors.rss.get_settings", return_value=settings):
            extractor = RSSExtractor()
            result = await extractor.extract()

        assert len(result) == 1
        meta = result[0].metadata
        assert meta["feed_url"] == FEED_URL_OPENAI
        assert meta["source_name"] == "OpenAI Blog"
        assert isinstance(meta["tags"], list)
        assert "AI" in meta["tags"]
        assert "GPT" in meta["tags"]
        assert meta["rss_id"].startswith("rss-")

    @respx.mock
    async def test_max_items_per_source_limits_output(self):
        """Result should be truncated to max_items_per_source."""
        entries = [_make_entry(f"Post {i}", f"https://openai.com/blog/post-{i}") for i in range(10)]
        feed_xml = _make_feed(entries)
        respx.get(FEED_URL_OPENAI).mock(
            return_value=httpx.Response(200, text=feed_xml),
        )

        settings = _mock_settings(max_items_per_source=3)
        with patch("src.extractors.rss.get_settings", return_value=settings):
            extractor = RSSExtractor()
            result = await extractor.extract()

        assert len(result) == 3

    @respx.mock
    async def test_multiple_feeds_fetched(self):
        """Each configured feed should be fetched."""
        entry_openai = _make_entry("OpenAI Post", "https://openai.com/blog/new")
        entry_google = _make_entry("Google AI Post", "https://blog.google/ai/new")

        respx.get(FEED_URL_OPENAI).mock(
            return_value=httpx.Response(200, text=_make_feed([entry_openai], "OpenAI Blog")),
        )
        respx.get(FEED_URL_GOOGLE).mock(
            return_value=httpx.Response(
                200,
                text=_make_feed([entry_google], "Google AI Blog"),
            ),
        )

        settings = _mock_settings(rss_feeds=f"{FEED_URL_OPENAI},{FEED_URL_GOOGLE}")
        with patch("src.extractors.rss.get_settings", return_value=settings):
            extractor = RSSExtractor()
            result = await extractor.extract()

        assert len(result) == 2
        urls = {item.url for item in result}
        assert "https://openai.com/blog/new" in urls
        assert "https://blog.google/ai/new" in urls

    @respx.mock
    async def test_entries_without_url_are_skipped(self):
        """Entries with no link should be skipped."""
        # Create feed with an entry that has an empty link
        pub_date = _recent_rfc2822()
        feed_xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Test Blog</title>
    <item>
      <title>No Link Post</title>
      <link></link>
      <description>This post has no link.</description>
    </item>
    <item>
      <title>Has Link Post</title>
      <link>https://example.com/post</link>
      <description>This post has a link.</description>
      <pubDate>{pub_date}</pubDate>
    </item>
  </channel>
</rss>"""
        respx.get(FEED_URL_OPENAI).mock(
            return_value=httpx.Response(200, text=feed_xml),
        )

        settings = _mock_settings()
        with patch("src.extractors.rss.get_settings", return_value=settings):
            extractor = RSSExtractor()
            result = await extractor.extract()

        # Only the entry with a link should be returned
        assert len(result) <= 1
        if result:
            assert result[0].url == "https://example.com/post"

    @respx.mock
    async def test_entries_without_date_are_included(self):
        """Entries without a published date should still be included (no cutoff check)."""
        feed_xml = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Test Blog</title>
    <item>
      <title>No Date Post</title>
      <link>https://example.com/nodate</link>
      <description>This post has no date.</description>
    </item>
  </channel>
</rss>"""
        respx.get(FEED_URL_OPENAI).mock(
            return_value=httpx.Response(200, text=feed_xml),
        )

        settings = _mock_settings()
        with patch("src.extractors.rss.get_settings", return_value=settings):
            extractor = RSSExtractor()
            result = await extractor.extract()

        assert len(result) == 1
        assert result[0].published_at is None


class TestHelpers:
    """Test static helper methods."""

    def test_strip_html_removes_tags(self):
        result = RSSExtractor._strip_html("<p>Hello <b>world</b></p>")
        assert result == "Hello world"

    def test_strip_html_decodes_entities(self):
        result = RSSExtractor._strip_html("A &amp; B &lt; C &gt; D")
        assert result == "A & B < C > D"

    def test_strip_html_normalizes_whitespace(self):
        result = RSSExtractor._strip_html("  too   many    spaces  ")
        assert result == "too many spaces"

    def test_get_source_name_from_feed_title(self):
        import feedparser

        feed = feedparser.parse("<rss><channel><title>My Blog</title></channel></rss>")
        assert RSSExtractor._get_source_name(feed, "https://example.com/rss") == "My Blog"

    def test_get_source_name_fallback_to_domain(self):
        import feedparser

        feed = feedparser.parse("<rss><channel></channel></rss>")
        assert RSSExtractor._get_source_name(feed, "https://example.com/rss") == "example.com"


class TestEdgeCases:
    """Edge-case tests for RSSExtractor robustness."""

    @respx.mock
    async def test_feed_http_404(self):
        """Feed returning 404 is skipped, returns []."""
        respx.get(FEED_URL_OPENAI).mock(
            return_value=httpx.Response(404, text="Not Found"),
        )

        settings = _mock_settings()
        with patch("src.extractors.rss.get_settings", return_value=settings):
            extractor = RSSExtractor()
            result = await extractor.extract()

        assert result == []

    @respx.mock
    async def test_timeout_returns_empty(self):
        """Feed timeout is handled gracefully, returning []."""
        respx.get(FEED_URL_OPENAI).mock(
            side_effect=httpx.TimeoutException("read timed out"),
        )

        settings = _mock_settings()
        with patch("src.extractors.rss.get_settings", return_value=settings):
            extractor = RSSExtractor()
            result = await extractor.extract()

        assert result == []


class TestRSSETags:
    """RSSExtractor conditional request behavior with ETags."""

    @respx.mock
    async def test_stores_etag_and_sends_on_next_request(self):
        """After a response with ETag, next request sends If-None-Match."""
        entries = [_make_entry("Post A", "https://openai.com/blog/a")]
        feed_xml = _make_feed(entries)

        # First request: response includes ETag header
        respx.get(FEED_URL_OPENAI).mock(
            return_value=httpx.Response(200, text=feed_xml, headers={"ETag": '"abc123"'}),
        )

        settings = _mock_settings()
        with patch("src.extractors.rss.get_settings", return_value=settings):
            extractor = RSSExtractor()
            result1 = await extractor.extract(since_hours=48)

        assert len(result1) == 1

        # Second request: server returns 304 (no changes)
        route = respx.get(FEED_URL_OPENAI).mock(
            return_value=httpx.Response(304),
        )

        with patch("src.extractors.rss.get_settings", return_value=settings):
            result2 = await extractor.extract(since_hours=48)

        assert result2 == []
        # Verify If-None-Match header was sent
        request = route.calls.last.request
        assert request.headers.get("if-none-match") == '"abc123"'

    @respx.mock
    async def test_304_returns_empty_list(self):
        """HTTP 304 Not Modified returns empty (feed unchanged)."""
        extractor = RSSExtractor()
        extractor._etag_cache[FEED_URL_OPENAI] = {"etag": '"cached"'}

        respx.get(FEED_URL_OPENAI).mock(
            return_value=httpx.Response(304),
        )

        settings = _mock_settings()
        with patch("src.extractors.rss.get_settings", return_value=settings):
            result = await extractor.extract(since_hours=48)

        assert result == []
