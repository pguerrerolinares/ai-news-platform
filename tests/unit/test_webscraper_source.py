"""Tests for webscraper source registration in VALID_SOURCES."""

from __future__ import annotations

from src.core.models import VALID_SOURCES


class TestWebscraperSource:
    """Ensure 'webscraper' is a recognized source."""

    def test_webscraper_in_valid_sources(self):
        assert "webscraper" in VALID_SOURCES

    def test_valid_sources_includes_all_expected(self):
        expected = {
            "hackernews",
            "arxiv",
            "reddit",
            "rss",
            "github",
            "huggingface",
            "webscraper",
        }
        assert set(VALID_SOURCES) == expected
