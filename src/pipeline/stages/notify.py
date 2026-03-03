"""Notification stage — send Telegram alerts after pipeline run."""

from __future__ import annotations

from src.classifiers.base import ClassifiedItem
from src.core.config import get_settings
from src.core.logging import get_logger
from src.core.metrics import notification_duration_seconds, notification_errors_total
from src.notifiers.telegram import TelegramNotifier

logger = get_logger(__name__)


async def run_notification(
    items: list[ClassifiedItem],
    duration_seconds: float,
) -> None:
    """Send pipeline results via Telegram if configured."""
    settings = get_settings()

    if not settings.telegram_bot_token or not settings.telegram_chat_id:
        return

    try:
        with notification_duration_seconds.time():
            notifier = TelegramNotifier()
            await notifier.send_briefing(items, duration_seconds=duration_seconds)
    except Exception as exc:
        notification_errors_total.inc()
        logger.warning("notification_failed", error=str(exc))
