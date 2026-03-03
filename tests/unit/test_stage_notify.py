"""Tests for src.pipeline.stages.notify — notification stage."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from src.classifiers.base import ClassifiedItem
from src.extractors.base import ExtractedItem
from src.pipeline.stages.notify import run_notification


def _mock_settings(**overrides):
    from src.core.config import Settings

    defaults = {
        "telegram_bot_token": "fake-token",
        "telegram_chat_id": "12345",
        "telegram_alerts_enabled": True,
    }
    defaults.update(overrides)
    return Settings(**defaults)


def _make_classified():
    item = ExtractedItem(title="Test", source="hackernews", url="https://example.com", score=100)
    return ClassifiedItem(item=item, topic="models", relevance_score=0.9, summary="Test")


class TestRunNotification:
    async def test_sends_notification_when_configured(self):
        settings = _mock_settings()
        items = [_make_classified()]

        with patch("src.pipeline.stages.notify.get_settings", return_value=settings):
            with patch("src.pipeline.stages.notify.TelegramNotifier") as mock_cls:
                mock_notifier = AsyncMock()
                mock_cls.return_value = mock_notifier
                await run_notification(items, duration_seconds=1.5)

        mock_notifier.send_briefing.assert_called_once()

    async def test_skips_when_no_token(self):
        settings = _mock_settings(telegram_bot_token="", telegram_chat_id="")

        with patch("src.pipeline.stages.notify.get_settings", return_value=settings):
            # Should not raise
            await run_notification([], duration_seconds=1.0)
