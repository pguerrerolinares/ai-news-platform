"""Tests for webscraper settings in src.core.config."""

from __future__ import annotations

from src.core.config import Settings


# ---------------------------------------------------------------------------
# Default values
# ---------------------------------------------------------------------------
class TestWebscraperDefaults:
    """Verify webscraper settings have correct defaults."""

    def test_webscraper_urls_default_has_sources(self):
        s = Settings()
        assert "techcrunch.com" in s.webscraper_urls
        assert "arstechnica.com" in s.webscraper_urls

    def test_webscraper_urls_list_default_has_sources(self):
        s = Settings()
        assert len(s.webscraper_urls_list) >= 2

    def test_webscraper_max_concurrent_default(self):
        s = Settings()
        assert s.webscraper_max_concurrent == 3

    def test_webscraper_page_timeout_default(self):
        s = Settings()
        assert s.webscraper_page_timeout == 30

    def test_webscraper_poll_interval_default(self):
        s = Settings()
        assert s.webscraper_poll_interval_minutes == 60


# ---------------------------------------------------------------------------
# Env var overrides
# ---------------------------------------------------------------------------
class TestWebscraperEnvOverride:
    """Ensure environment variables override webscraper defaults."""

    def test_override_webscraper_urls(self, monkeypatch):
        monkeypatch.setenv("WEBSCRAPER_URLS", "https://a.com,https://b.com")
        s = Settings()
        assert s.webscraper_urls_list == ["https://a.com", "https://b.com"]

    def test_override_webscraper_urls_strips_whitespace(self, monkeypatch):
        monkeypatch.setenv("WEBSCRAPER_URLS", " https://a.com , https://b.com ")
        s = Settings()
        assert s.webscraper_urls_list == ["https://a.com", "https://b.com"]

    def test_override_webscraper_max_concurrent(self, monkeypatch):
        monkeypatch.setenv("WEBSCRAPER_MAX_CONCURRENT", "5")
        s = Settings()
        assert s.webscraper_max_concurrent == 5

    def test_override_webscraper_page_timeout(self, monkeypatch):
        monkeypatch.setenv("WEBSCRAPER_PAGE_TIMEOUT", "60")
        s = Settings()
        assert s.webscraper_page_timeout == 60

    def test_override_webscraper_poll_interval(self, monkeypatch):
        monkeypatch.setenv("WEBSCRAPER_POLL_INTERVAL_MINUTES", "30")
        s = Settings()
        assert s.webscraper_poll_interval_minutes == 30
