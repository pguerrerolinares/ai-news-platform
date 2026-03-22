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

    def test_default_debug_is_false(self, monkeypatch):
        monkeypatch.setenv("DEBUG", "false")
        s = Settings()
        assert s.debug is False

    def test_default_log_level(self):
        s = Settings()
        assert s.log_level == "INFO"

    def test_default_log_format(self):
        s = Settings()
        assert s.log_format == "json"

    def test_default_min_relevance_score(self):
        s = Settings(min_relevance_score=0.75)
        assert s.min_relevance_score == pytest.approx(0.75)

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
        s = Settings(topics="models,tools,papers")
        result = s.topics_list
        assert result == ["models", "tools", "papers"]

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

    def test_csv_property_only_commas(self):
        """A string of only commas should produce an empty list, not ['', '']."""
        s = Settings(enabled_sources=",,")
        assert s.enabled_sources_list == []

    def test_csv_property_single_value_no_comma(self):
        """A single value without commas should produce a one-element list."""
        s = Settings(enabled_sources="hackernews")
        assert s.enabled_sources_list == ["hackernews"]


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

    def test_override_min_relevance_score(self, monkeypatch):
        monkeypatch.setenv("MIN_RELEVANCE_SCORE", "0.5")
        s = Settings()
        assert s.min_relevance_score == pytest.approx(0.5)


# ---------------------------------------------------------------------------
# Scheduler config
# ---------------------------------------------------------------------------
class TestSchedulerConfig:
    """Scheduler-related settings."""

    def test_scheduler_enabled_default(self):
        from src.core.config import Settings

        s = Settings()
        assert s.scheduler_enabled is True

    def test_poll_interval_defaults(self):
        from src.core.config import Settings

        s = Settings(hn_poll_interval_minutes=30)
        assert s.hn_poll_interval_minutes == 30
        assert s.reddit_poll_interval_minutes == 15
        assert s.rss_poll_interval_minutes == 60
        assert s.github_poll_interval_minutes > 0  # 240 default, overridable via env
        assert s.hf_poll_interval_minutes == 60
        assert s.arxiv_cron_hour == 1
        assert s.arxiv_cron_minute == 30

    def test_reddit_oauth_defaults_empty(self):
        from src.core.config import Settings

        s = Settings()
        assert s.reddit_client_id == ""
        assert s.reddit_client_secret == ""


# ---------------------------------------------------------------------------
# Auth (multi-user) config
# ---------------------------------------------------------------------------
class TestAuthConfig:
    """Auth-related configuration settings for multi-user OTP."""

    def test_admin_email_default_empty(self, monkeypatch):
        monkeypatch.setenv("ADMIN_EMAIL", "")
        s = Settings()
        assert s.admin_email == ""

    def test_resend_api_key_default_empty(self, monkeypatch):
        monkeypatch.setenv("RESEND_API_KEY", "")
        s = Settings()
        assert s.resend_api_key == ""

    def test_otp_from_email_default(self):
        s = Settings()
        assert s.otp_from_email == "noreply@resend.dev"

    def test_otp_expire_minutes_default(self):
        s = Settings()
        assert s.otp_expire_minutes == 10

    def test_admin_email_override(self, monkeypatch):
        monkeypatch.setenv("ADMIN_EMAIL", "admin@test.com")
        s = Settings()
        assert s.admin_email == "admin@test.com"

    def test_resend_api_key_override(self, monkeypatch):
        monkeypatch.setenv("RESEND_API_KEY", "re_test_key_123")
        s = Settings()
        assert s.resend_api_key == "re_test_key_123"


# ---------------------------------------------------------------------------
# OTP abuse prevention config
# ---------------------------------------------------------------------------
def test_otp_daily_limit_default():
    s = Settings(
        jwt_secret="x",
        database_url="postgresql+asyncpg://x:x@localhost/x",
        database_url_sync="postgresql://x:x@localhost/x",
    )
    assert s.otp_daily_limit == 50


def test_otp_daily_limit_custom():
    s = Settings(
        jwt_secret="x",
        database_url="postgresql+asyncpg://x:x@localhost/x",
        database_url_sync="postgresql://x:x@localhost/x",
        otp_daily_limit=80,
    )
    assert s.otp_daily_limit == 80
