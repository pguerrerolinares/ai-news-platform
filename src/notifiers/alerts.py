"""Telegram alert service for pipeline, deploy, and backup notifications."""

from __future__ import annotations

from datetime import UTC, datetime

import httpx

from src.core.config import get_settings
from src.core.logging import get_logger

logger = get_logger(__name__)


class AlertService:
    """Sends operational alerts via Telegram.

    Reusable by pipeline, CI/CD, backup scripts, and health checks.
    Uses httpx directly (not python-telegram-bot) for minimal dependency.
    """

    def __init__(self, bot_token: str | None = None, chat_id: str | None = None) -> None:
        settings = get_settings()
        self.bot_token = bot_token or settings.telegram_bot_token
        self.chat_id = chat_id or settings.telegram_chat_id
        self.enabled = settings.telegram_alerts_enabled and bool(self.bot_token and self.chat_id)
        self._base_url = f"https://api.telegram.org/bot{self.bot_token}"

    async def _send(self, text: str) -> bool:
        """Send a message via Telegram Bot API."""
        if not self.enabled:
            logger.warning("telegram_alerts_disabled", reason="missing credentials or disabled")
            return False

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(
                    f"{self._base_url}/sendMessage",
                    json={
                        "chat_id": self.chat_id,
                        "text": text,
                        "parse_mode": "HTML",
                        "disable_web_page_preview": True,
                    },
                )
                resp.raise_for_status()
                logger.info("telegram_alert_sent", length=len(text))
                return True
        except Exception as exc:
            logger.error("telegram_alert_failed", error=str(exc))
            return False

    async def pipeline_success(
        self, items_count: int, duration_seconds: float, sources: list[str]
    ) -> bool:
        """Alert: pipeline completed successfully."""
        now = datetime.now(tz=UTC).strftime("%Y-%m-%d %H:%M UTC")
        text = (
            f"<b>Pipeline OK</b> {now}\n"
            f"Items: {items_count}\n"
            f"Duration: {duration_seconds:.1f}s\n"
            f"Sources: {', '.join(sources)}"
        )
        return await self._send(text)

    async def pipeline_failure(self, error: str, stage: str = "") -> bool:
        """Alert: pipeline failed."""
        now = datetime.now(tz=UTC).strftime("%Y-%m-%d %H:%M UTC")
        stage_info = f" at <b>{stage}</b>" if stage else ""
        text = f"<b>Pipeline FAILED</b>{stage_info} {now}\n<code>{error[:500]}</code>"
        return await self._send(text)

    async def extractor_empty(self, source: str) -> bool:
        """Alert: extractor returned 0 items."""
        text = f"<b>Extractor WARNING</b>\n<code>{source}</code> returned 0 items"
        return await self._send(text)

    async def deploy_success(self, version: str) -> bool:
        """Alert: deploy completed successfully."""
        text = f"<b>Deploy OK</b>\nVersion: <code>{version}</code>"
        return await self._send(text)

    async def deploy_failure(self, error: str, version: str = "") -> bool:
        """Alert: deploy failed."""
        text = f"<b>Deploy FAILED</b>\nVersion: <code>{version}</code>\n<code>{error[:500]}</code>"
        return await self._send(text)

    async def backup_success(self, size_mb: float) -> bool:
        """Alert: backup completed successfully."""
        now = datetime.now(tz=UTC).strftime("%Y-%m-%d %H:%M UTC")
        text = f"<b>Backup OK</b> {now}\nSize: {size_mb:.1f} MB"
        return await self._send(text)

    async def backup_failure(self, error: str) -> bool:
        """Alert: backup failed."""
        text = f"<b>Backup FAILED</b>\n<code>{error[:500]}</code>"
        return await self._send(text)

    async def health_check_failure(self, service: str, error: str) -> bool:
        """Alert: health check failed."""
        text = (
            f"<b>Health Check FAILED</b>\n"
            f"Service: <code>{service}</code>\n<code>{error[:500]}</code>"
        )
        return await self._send(text)
