"""Tests for src.core.config -- Settings loading and CSV-list properties."""

from __future__ import annotations

import pytest

from src.core.config import Settings


# ---------------------------------------------------------------------------
# Default values
# ---------------------------------------------------------------------------
class TestSettingsDefaults:
    """Verify that sensible defaults are applied when no env vars are set."""

    def test_default_database_url(self):
        s = Settings(database_url="postgresql+asyncpg://ainews:ainews@localhost:5432/ainews")
        assert "asyncpg" in s.database_url
        assert "ainews" in s.database_url

    def test_default_api_port(self):
        s = Settings()
        assert s.api_port == 8000

    def test_default_api_host(self):
        s = Settings()
        assert s.api_host == "0.0.0.0"

    def test_default_debug_is_false(self):
        s = Settings()
        assert s.debug is False

    def test_default_log_level(self):
        s = Settings()
        assert s.log_level == "INFO"

    def test_default_log_format(self):
        s = Settings()
        assert s.log_format == "json"

    def test_default_min_relevance_score(self):
        s = Settings()
        assert s.min_relevance_score == pytest.approx(0.8)

    def test_default_pipeline_schedule(self):
        s = Settings()
        assert s.pipeline_schedule_hour == 8
        assert s.pipeline_schedule_minute == 0

    def test_default_max_items_per_source(self):
        s = Settings()
        assert s.max_items_per_source == 50

    def test_default_jwt_algorithm(self):
        s = Settings()
        assert s.jwt_algorithm == "HS256"


# ---------------------------------------------------------------------------
# CSV list properties
# ---------------------------------------------------------------------------
class TestCSVListProperties:
    """Verify that comma-separated string fields are split into lists."""

    def test_enabled_sources_list(self):
        s = Settings(enabled_sources="hackernews,arxiv,reddit,rss")
        result = s.enabled_sources_list
        assert result == ["hackernews", "arxiv", "reddit", "rss"]

    def test_enabled_sources_list_strips_whitespace(self):
        s = Settings(enabled_sources=" hackernews , arxiv ")
        result = s.enabled_sources_list
        assert result == ["hackernews", "arxiv"]

    def test_enabled_sources_list_empty_string(self):
        s = Settings(enabled_sources="")
        assert s.enabled_sources_list == []

    def test_topics_list(self):
        s = Settings(topics="modelos,herramientas,papers")
        result = s.topics_list
        assert result == ["modelos", "herramientas", "papers"]

    def test_hn_search_queries_list(self):
        s = Settings(hn_search_queries="AI,LLM,GPT")
        assert s.hn_search_queries_list == ["AI", "LLM", "GPT"]

    def test_arxiv_categories_list(self):
        s = Settings(arxiv_categories="cs.AI,cs.CL")
        assert s.arxiv_categories_list == ["cs.AI", "cs.CL"]

    def test_arxiv_keywords_list(self):
        s = Settings(arxiv_keywords="LLM,transformer")
        assert s.arxiv_keywords_list == ["LLM", "transformer"]

    def test_reddit_subreddits_list(self):
        s = Settings(reddit_subreddits="MachineLearning,LocalLLaMA")
        assert s.reddit_subreddits_list == ["MachineLearning", "LocalLLaMA"]

    def test_rss_feeds_list(self):
        s = Settings(rss_feeds="https://a.com/feed.xml,https://b.com/rss")
        result = s.rss_feeds_list
        assert len(result) == 2
        assert result[0] == "https://a.com/feed.xml"

    def test_trusted_news_domains_list(self):
        s = Settings(trusted_news_domains="openai.com,arxiv.org")
        assert s.trusted_news_domains_list == ["openai.com", "arxiv.org"]


# ---------------------------------------------------------------------------
# Env var overrides via monkeypatch
# ---------------------------------------------------------------------------
class TestEnvVarOverride:
    """Ensure environment variables override default settings."""

    def test_override_api_port(self, monkeypatch):
        monkeypatch.setenv("API_PORT", "9999")
        s = Settings()
        assert s.api_port == 9999

    def test_override_debug(self, monkeypatch):
        monkeypatch.setenv("DEBUG", "true")
        s = Settings()
        assert s.debug is True

    def test_override_database_url(self, monkeypatch):
        monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@db:5432/custom")
        s = Settings()
        assert s.database_url == "postgresql+asyncpg://u:p@db:5432/custom"

    def test_override_enabled_sources(self, monkeypatch):
        monkeypatch.setenv("ENABLED_SOURCES", "github,huggingface")
        s = Settings()
        assert s.enabled_sources_list == ["github", "huggingface"]

    def test_override_log_level(self, monkeypatch):
        monkeypatch.setenv("LOG_LEVEL", "DEBUG")
        s = Settings()
        assert s.log_level == "DEBUG"

    def test_override_telegram_bot_token(self, monkeypatch):
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123:ABC")
        s = Settings()
        assert s.telegram_bot_token == "123:ABC"

    def test_override_min_relevance_score(self, monkeypatch):
        monkeypatch.setenv("MIN_RELEVANCE_SCORE", "0.5")
        s = Settings()
        assert s.min_relevance_score == pytest.approx(0.5)
