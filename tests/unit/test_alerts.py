"""Tests for src.notifiers.alerts -- AlertService."""

from __future__ import annotations

import pytest

from src.core.config import get_settings
from src.notifiers.alerts import AlertService


@pytest.fixture(autouse=True)
def _clear_settings_cache():
    """Clear the lru_cache on get_settings so env var changes take effect."""
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


# ---------------------------------------------------------------------------
# AlertService disabled state
# ---------------------------------------------------------------------------
class TestAlertServiceDisabled:
    """Verify AlertService is disabled when credentials are missing."""

    def test_disabled_when_no_token(self, monkeypatch):
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "")
        monkeypatch.setenv("TELEGRAM_CHAT_ID", "12345")
        monkeypatch.setenv("TELEGRAM_ALERTS_ENABLED", "true")
        svc = AlertService(bot_token="", chat_id="12345")
        assert svc.enabled is False

    def test_disabled_when_no_chat_id(self, monkeypatch):
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123:ABC")
        monkeypatch.setenv("TELEGRAM_CHAT_ID", "")
        monkeypatch.setenv("TELEGRAM_ALERTS_ENABLED", "true")
        svc = AlertService(bot_token="123:ABC", chat_id="")
        assert svc.enabled is False

    def test_disabled_when_both_missing(self, monkeypatch):
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "")
        monkeypatch.setenv("TELEGRAM_CHAT_ID", "")
        monkeypatch.setenv("TELEGRAM_ALERTS_ENABLED", "true")
        svc = AlertService(bot_token="", chat_id="")
        assert svc.enabled is False

    def test_disabled_when_alerts_disabled_in_settings(self, monkeypatch):
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123:ABC")
        monkeypatch.setenv("TELEGRAM_CHAT_ID", "12345")
        monkeypatch.setenv("TELEGRAM_ALERTS_ENABLED", "false")
        svc = AlertService(bot_token="123:ABC", chat_id="12345")
        assert svc.enabled is False

    def test_enabled_when_all_provided(self, monkeypatch):
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123:ABC")
        monkeypatch.setenv("TELEGRAM_CHAT_ID", "12345")
        monkeypatch.setenv("TELEGRAM_ALERTS_ENABLED", "true")
        svc = AlertService(bot_token="123:ABC", chat_id="12345")
        assert svc.enabled is True


# ---------------------------------------------------------------------------
# AlertService._send returns False when disabled
# ---------------------------------------------------------------------------
class TestAlertServiceSendDisabled:
    """Verify that _send returns False when the service is disabled."""

    async def test_send_returns_false_when_disabled(self):
        svc = AlertService(bot_token="", chat_id="")
        result = await svc._send("test message")
        assert result is False

    async def test_pipeline_success_returns_false_when_disabled(self):
        svc = AlertService(bot_token="", chat_id="")
        result = await svc.pipeline_success(
            items_count=10,
            duration_seconds=5.0,
            sources=["hackernews"],
        )
        assert result is False

    async def test_pipeline_failure_returns_false_when_disabled(self):
        svc = AlertService(bot_token="", chat_id="")
        result = await svc.pipeline_failure(error="boom", stage="extraction")
        assert result is False

    async def test_extractor_empty_returns_false_when_disabled(self):
        svc = AlertService(bot_token="", chat_id="")
        result = await svc.extractor_empty(source="arxiv")
        assert result is False

    async def test_deploy_success_returns_false_when_disabled(self):
        svc = AlertService(bot_token="", chat_id="")
        result = await svc.deploy_success(version="1.0.0")
        assert result is False

    async def test_deploy_failure_returns_false_when_disabled(self):
        svc = AlertService(bot_token="", chat_id="")
        result = await svc.deploy_failure(error="deploy failed", version="1.0.0")
        assert result is False

    async def test_backup_success_returns_false_when_disabled(self):
        svc = AlertService(bot_token="", chat_id="")
        result = await svc.backup_success(size_mb=512.5)
        assert result is False

    async def test_backup_failure_returns_false_when_disabled(self):
        svc = AlertService(bot_token="", chat_id="")
        result = await svc.backup_failure(error="disk full")
        assert result is False

    async def test_health_check_failure_returns_false_when_disabled(self):
        svc = AlertService(bot_token="", chat_id="")
        result = await svc.health_check_failure(service="db", error="connection refused")
        assert result is False


# ---------------------------------------------------------------------------
# AlertService base URL construction
# ---------------------------------------------------------------------------
class TestAlertServiceBaseUrl:
    """Verify the Telegram base URL is constructed correctly."""

    def test_base_url_contains_token(self):
        svc = AlertService(bot_token="my-token-123", chat_id="999")
        assert "my-token-123" in svc._base_url
        assert svc._base_url == "https://api.telegram.org/botmy-token-123"

    def test_chat_id_is_stored(self):
        svc = AlertService(bot_token="tok", chat_id="12345")
        assert svc.chat_id == "12345"
