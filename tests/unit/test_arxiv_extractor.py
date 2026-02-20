"""Tests for src.extractors.arxiv -- ArxivExtractor."""

from __future__ import annotations

from unittest.mock import patch

import httpx
import respx

from src.extractors.arxiv import RSS_BASE, ArxivExtractor
from src.extractors.base import ExtractedItem


# ---------------------------------------------------------------------------
# Sample arXiv RSS feed data
# ---------------------------------------------------------------------------
def _make_entry(
    arxiv_id: str = "2401.12345",
    title: str = "A Novel Transformer Architecture for LLM Training",
    summary: str = "Announce Type: new\nWe present a new approach to training LLMs.",
    author: str = "John Doe",
    link: str | None = None,
) -> str:
    """Build a single RSS <item> XML element."""
    if link is None:
        link = f"https://arxiv.org/abs/{arxiv_id}"
    return f"""
    <item>
      <title>{title}</title>
      <link>{link}</link>
      <description>{summary}</description>
      <author>{author}</author>
      <pubDate>Mon, 15 Feb 2024 00:00:00 GMT</pubDate>
    </item>"""


def _make_feed(items_xml: list[str], category: str = "cs.AI") -> str:
    """Wrap <item> elements in a minimal RSS 2.0 feed."""
    items_joined = "\n".join(items_xml)
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>ArXiv {category}</title>
    <link>https://arxiv.org</link>
    <description>arXiv {category} papers</description>
    {items_joined}
  </channel>
</rss>"""


def _mock_settings(**overrides):
    """Return a minimal Settings-like object for ArXiv extraction."""
    from src.core.config import Settings

    defaults = {
        "arxiv_categories": "cs.AI",
        "arxiv_keywords": "LLM,transformer,language model",
        "max_items_per_source": 50,
        "enabled_sources": "arxiv",
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
    """ArxivExtractor.source_name property."""

    def test_source_name_returns_arxiv(self):
        extractor = ArxivExtractor()
        assert extractor.source_name == "arxiv"


class TestExtract:
    """ArxivExtractor.extract() with mocked HTTP responses."""

    @respx.mock
    async def test_extract_returns_list_of_extracted_items(self):
        """extract() should return a list of ExtractedItem instances."""
        entries = [
            _make_entry("2401.00001", "Transformer Advances in LLM"),
            _make_entry("2401.00002", "Language Model Fine-tuning"),
        ]
        feed_xml = _make_feed(entries)
        respx.get(f"{RSS_BASE}/cs.AI").mock(
            return_value=httpx.Response(200, text=feed_xml),
        )

        settings = _mock_settings()
        with patch("src.extractors.arxiv.get_settings", return_value=settings):
            extractor = ArxivExtractor()
            result = await extractor.extract(since_hours=24)

        assert isinstance(result, list)
        assert len(result) == 2
        for item in result:
            assert isinstance(item, ExtractedItem)

    @respx.mock
    async def test_items_have_correct_source(self):
        """Every returned item must have source='arxiv'."""
        entries = [_make_entry("2401.00001", "LLM Paper")]
        feed_xml = _make_feed(entries)
        respx.get(f"{RSS_BASE}/cs.AI").mock(
            return_value=httpx.Response(200, text=feed_xml),
        )

        settings = _mock_settings()
        with patch("src.extractors.arxiv.get_settings", return_value=settings):
            extractor = ArxivExtractor()
            result = await extractor.extract()

        assert all(item.source == "arxiv" for item in result)

    @respx.mock
    async def test_filters_non_new_announcements(self):
        """Only entries with 'Announce Type: new' should pass."""
        entries = [
            _make_entry(
                "2401.00001",
                "New LLM Paper",
                summary="Announce Type: new\nA new paper about transformers.",
            ),
            _make_entry(
                "2401.00002",
                "Replacement Paper",
                summary="Announce Type: replace\nReplacement of an older paper.",
            ),
            _make_entry(
                "2401.00003",
                "Cross-list LLM Paper",
                summary="Announce Type: cross\nCross-listed from cs.CL.",
            ),
        ]
        feed_xml = _make_feed(entries)
        respx.get(f"{RSS_BASE}/cs.AI").mock(
            return_value=httpx.Response(200, text=feed_xml),
        )

        settings = _mock_settings()
        with patch("src.extractors.arxiv.get_settings", return_value=settings):
            extractor = ArxivExtractor()
            result = await extractor.extract()

        # Only the "new" announcement should pass
        assert len(result) == 1
        assert result[0].metadata["arxiv_id"] == "2401.00001"

    @respx.mock
    async def test_keyword_filtering(self):
        """Only entries matching keyword regex should pass."""
        entries = [
            _make_entry(
                "2401.00001",
                "Advances in Transformer Networks",
                summary="Announce Type: new\nA paper about transformer architectures.",
            ),
            _make_entry(
                "2401.00002",
                "Quantum Computing in Biology",
                summary="Announce Type: new\nA paper about quantum biology applications.",
            ),
        ]
        feed_xml = _make_feed(entries)
        respx.get(f"{RSS_BASE}/cs.AI").mock(
            return_value=httpx.Response(200, text=feed_xml),
        )

        settings = _mock_settings(arxiv_keywords="transformer,LLM")
        with patch("src.extractors.arxiv.get_settings", return_value=settings):
            extractor = ArxivExtractor()
            result = await extractor.extract()

        # Only the transformer paper matches
        assert len(result) == 1
        assert "Transformer" in result[0].title

    @respx.mock
    async def test_deduplication_by_arxiv_id(self):
        """Duplicate arXiv IDs across categories should be deduplicated."""
        entry = _make_entry("2401.00001", "LLM Paper Appearing Twice")
        feed_xml = _make_feed([entry])

        respx.get(f"{RSS_BASE}/cs.AI").mock(
            return_value=httpx.Response(200, text=feed_xml),
        )
        respx.get(f"{RSS_BASE}/cs.CL").mock(
            return_value=httpx.Response(200, text=feed_xml),
        )

        settings = _mock_settings(arxiv_categories="cs.AI,cs.CL")
        with patch("src.extractors.arxiv.get_settings", return_value=settings):
            extractor = ArxivExtractor()
            result = await extractor.extract()

        # Same arXiv ID in both categories -> only 1 item
        assert len(result) == 1
        assert result[0].metadata["arxiv_id"] == "2401.00001"

    @respx.mock
    async def test_empty_feed_returns_empty_list(self):
        """An RSS feed with no entries should return an empty list."""
        feed_xml = _make_feed([])
        respx.get(f"{RSS_BASE}/cs.AI").mock(
            return_value=httpx.Response(200, text=feed_xml),
        )

        settings = _mock_settings()
        with patch("src.extractors.arxiv.get_settings", return_value=settings):
            extractor = ArxivExtractor()
            result = await extractor.extract()

        assert result == []

    @respx.mock
    async def test_http_error_returns_empty_list(self):
        """An HTTP 500 error should be handled gracefully, returning []."""
        respx.get(f"{RSS_BASE}/cs.AI").mock(
            return_value=httpx.Response(500, text="Internal Server Error"),
        )

        settings = _mock_settings()
        with patch("src.extractors.arxiv.get_settings", return_value=settings):
            extractor = ArxivExtractor()
            result = await extractor.extract()

        assert result == []

    @respx.mock
    async def test_network_error_returns_empty_list(self):
        """A network-level exception should be caught, returning []."""
        respx.get(f"{RSS_BASE}/cs.AI").mock(
            side_effect=httpx.ConnectError("Connection refused"),
        )

        settings = _mock_settings()
        with patch("src.extractors.arxiv.get_settings", return_value=settings):
            extractor = ArxivExtractor()
            result = await extractor.extract()

        assert result == []

    @respx.mock
    async def test_item_metadata_contains_expected_keys(self):
        """Extracted items should carry arxiv_id, category, pdf_url in metadata."""
        entries = [_make_entry("2401.12345", "LLM Training Advances")]
        feed_xml = _make_feed(entries, category="cs.AI")
        respx.get(f"{RSS_BASE}/cs.AI").mock(
            return_value=httpx.Response(200, text=feed_xml),
        )

        settings = _mock_settings()
        with patch("src.extractors.arxiv.get_settings", return_value=settings):
            extractor = ArxivExtractor()
            result = await extractor.extract()

        assert len(result) == 1
        meta = result[0].metadata
        assert meta["arxiv_id"] == "2401.12345"
        assert meta["category"] == "cs.AI"
        assert meta["pdf_url"] == "https://arxiv.org/pdf/2401.12345"

    @respx.mock
    async def test_max_items_per_source_limits_output(self):
        """Result should be truncated to max_items_per_source."""
        entries = [_make_entry(f"2401.{i:05d}", f"LLM Paper {i}") for i in range(10)]
        feed_xml = _make_feed(entries)
        respx.get(f"{RSS_BASE}/cs.AI").mock(
            return_value=httpx.Response(200, text=feed_xml),
        )

        settings = _mock_settings(max_items_per_source=3)
        with patch("src.extractors.arxiv.get_settings", return_value=settings):
            extractor = ArxivExtractor()
            result = await extractor.extract()

        assert len(result) == 3

    @respx.mock
    async def test_multiple_categories_fetched(self):
        """Each configured category should be fetched."""
        entry_ai = _make_entry("2401.00001", "AI Transformer Paper")
        entry_cl = _make_entry("2401.00002", "CL Language Model Paper")

        respx.get(f"{RSS_BASE}/cs.AI").mock(
            return_value=httpx.Response(200, text=_make_feed([entry_ai])),
        )
        respx.get(f"{RSS_BASE}/cs.CL").mock(
            return_value=httpx.Response(200, text=_make_feed([entry_cl], category="cs.CL")),
        )

        settings = _mock_settings(arxiv_categories="cs.AI,cs.CL")
        with patch("src.extractors.arxiv.get_settings", return_value=settings):
            extractor = ArxivExtractor()
            result = await extractor.extract()

        assert len(result) == 2
        arxiv_ids = {item.metadata["arxiv_id"] for item in result}
        assert arxiv_ids == {"2401.00001", "2401.00002"}

    @respx.mock
    async def test_version_suffix_stripped_from_arxiv_id(self):
        """Version suffixes like v1, v2 should be stripped from arXiv IDs."""
        entry = _make_entry(
            "2401.12345v2",
            "LLM Paper v2",
            link="https://arxiv.org/abs/2401.12345v2",
        )
        feed_xml = _make_feed([entry])
        respx.get(f"{RSS_BASE}/cs.AI").mock(
            return_value=httpx.Response(200, text=feed_xml),
        )

        settings = _mock_settings()
        with patch("src.extractors.arxiv.get_settings", return_value=settings):
            extractor = ArxivExtractor()
            result = await extractor.extract()

        assert len(result) == 1
        assert result[0].metadata["arxiv_id"] == "2401.12345"


class TestHelpers:
    """Test static helper methods."""

    def test_build_keyword_regex_matches(self):
        pattern = ArxivExtractor._build_keyword_regex(["LLM", "transformer"])
        assert pattern is not None
        assert pattern.search("This paper is about LLM training")
        assert pattern.search("A new Transformer architecture")
        assert not pattern.search("Quantum computing advances")

    def test_build_keyword_regex_empty(self):
        pattern = ArxivExtractor._build_keyword_regex([])
        assert pattern is None

    def test_is_new_announcement_true(self):
        entry = {"summary": "Announce Type: new\nSome description."}
        assert ArxivExtractor._is_new_announcement(entry) is True

    def test_is_new_announcement_false_for_replace(self):
        entry = {"summary": "Announce Type: replace\nReplacement."}
        assert ArxivExtractor._is_new_announcement(entry) is False

    def test_is_new_announcement_no_marker(self):
        entry = {"summary": "Just a plain description with no announce type."}
        assert ArxivExtractor._is_new_announcement(entry) is True

    def test_extract_arxiv_id(self):
        entry = {"link": "https://arxiv.org/abs/2401.12345"}
        assert ArxivExtractor._extract_arxiv_id(entry) == "2401.12345"

    def test_extract_arxiv_id_strips_version(self):
        entry = {"link": "https://arxiv.org/abs/2401.12345v3"}
        assert ArxivExtractor._extract_arxiv_id(entry) == "2401.12345"

    def test_extract_arxiv_id_no_link(self):
        entry = {"link": ""}
        assert ArxivExtractor._extract_arxiv_id(entry) is None

    def test_clean_description(self):
        text = "<p>Announce Type: new\nThis is a <b>bold</b> paper about AI.</p>"
        result = ArxivExtractor._clean_description(text)
        assert "<" not in result
        assert "Announce Type" not in result
        assert "bold" in result


class TestEdgeCases:
    """Edge cases for ArxivExtractor."""

    @respx.mock
    async def test_malformed_xml_returns_empty(self):
        """Malformed RSS body returns empty list, no crash."""
        respx.get(f"{RSS_BASE}/cs.AI").mock(
            return_value=httpx.Response(200, text="<broken xml"),
        )

        settings = _mock_settings()
        with patch("src.extractors.arxiv.get_settings", return_value=settings):
            result = await ArxivExtractor().extract()

        assert result == []

    @respx.mock
    async def test_entry_no_link(self):
        """Entry without link field is skipped (no arxiv_id extractable)."""
        entry_xml = """
        <item>
          <title>LLM Paper With No Link</title>
          <description>Announce Type: new\nA paper about transformers.</description>
          <author>Jane Doe</author>
        </item>"""
        feed_xml = _make_feed([entry_xml])
        respx.get(f"{RSS_BASE}/cs.AI").mock(
            return_value=httpx.Response(200, text=feed_xml),
        )

        settings = _mock_settings()
        with patch("src.extractors.arxiv.get_settings", return_value=settings):
            result = await ArxivExtractor().extract()

        assert result == []

    @respx.mock
    async def test_duplicate_paper_across_categories(self):
        """Same paper appearing in two categories is deduplicated."""
        entry_xml = (
            '<item rdf:about="http://arxiv.org/abs/2401.99999v1">'
            "<title>Announce Type: new\nDuplicated LLM Paper</title>"
            "<link>http://arxiv.org/abs/2401.99999v1</link>"
            "<description>Announce Type: new\nA paper about transformer LLM models.</description>"
            "</item>"
        )
        feed_xml = _make_feed([entry_xml])
        # Both categories return the same paper
        respx.get(f"{RSS_BASE}/cs.AI").mock(
            return_value=httpx.Response(200, text=feed_xml),
        )

        settings = _mock_settings()
        with patch("src.extractors.arxiv.get_settings", return_value=settings):
            result = await ArxivExtractor().extract()

        # Should be deduplicated to 1 item despite appearing in feed
        assert len(result) == 1

    @respx.mock
    async def test_feed_no_entries(self):
        """Valid RSS with zero entries returns empty list."""
        feed_xml = _make_feed([])
        respx.get(f"{RSS_BASE}/cs.AI").mock(
            return_value=httpx.Response(200, text=feed_xml),
        )

        settings = _mock_settings()
        with patch("src.extractors.arxiv.get_settings", return_value=settings):
            result = await ArxivExtractor().extract()

        assert result == []

    @respx.mock
    async def test_timeout_returns_empty(self):
        """Network timeout is handled gracefully."""
        respx.get(f"{RSS_BASE}/cs.AI").mock(
            side_effect=httpx.ReadTimeout("Read timed out"),
        )

        settings = _mock_settings()
        with patch("src.extractors.arxiv.get_settings", return_value=settings):
            result = await ArxivExtractor().extract()

        assert result == []

    def test_build_keyword_regex_empty_list(self):
        """Empty keyword list returns None pattern."""
        assert ArxivExtractor._build_keyword_regex([]) is None
