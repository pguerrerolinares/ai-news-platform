"""Telegram notifier for daily AI briefings.

Implements BaseNotifier and adds send_briefing() for formatted daily digests.
Uses httpx directly (same pattern as AlertService) for minimal dependency.
"""

from __future__ import annotations

import asyncio
from collections import Counter
from datetime import UTC, datetime

import httpx

from src.classifiers.base import ClassifiedItem
from src.core.config import get_settings
from src.core.logging import get_logger
from src.notifiers.base import BaseNotifier

logger = get_logger(__name__)

MAX_MSG_LEN = 4096

SOURCE_LABEL: dict[str, str] = {
    "hackernews": "HN",
    "arxiv": "arXiv",
    "reddit": "Reddit",
    "rss": "Blog",
}

TOPIC_EMOJI: dict[str, str] = {
    "modelos": "\U0001f9e0",  # brain
    "herramientas": "\U0001f6e0",  # wrench
    "papers": "\U0001f4c4",  # page
    "productos": "\U0001f4e6",  # package
    "open_source": "\U0001f513",  # unlock
    "agentes": "\U0001f916",  # robot
    "regulacion": "\u2696\ufe0f",  # scales
}

PRIORITY_DOT: dict[int, str] = {
    1: "\U0001f534",  # red
    2: "\U0001f7e0",  # orange
    3: "\U0001f7e1",  # yellow
    4: "\U0001f7e2",  # green
    5: "\u26aa",  # white
}

TOPIC_ORDER = [
    "modelos",
    "herramientas",
    "papers",
    "productos",
    "open_source",
    "agentes",
    "regulacion",
]


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


def _esc(text: str) -> str:
    """Escape text for Telegram HTML parse mode."""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#x27;")
    )


def _safe_url(url: str) -> str:
    """Sanitize a URL for use inside HTML href attributes."""
    return url.replace("&", "&amp;").replace('"', "%22").replace("<", "%3C").replace(">", "%3E")


def _split_text(text: str, limit: int) -> list[str]:
    """Split text into chunks at newline boundaries, respecting a character limit."""
    chunks: list[str] = []
    while len(text) > limit:
        split_at = text.rfind("\n", 0, limit)
        if split_at == -1:
            split_at = limit
        chunks.append(text[:split_at])
        text = text[split_at:].lstrip("\n")
    if text:
        chunks.append(text)
    return chunks


def _source_label(source: str) -> str:
    """Get display label for a source name."""
    return SOURCE_LABEL.get(source, source)


def _topic_emoji(topic: str) -> str:
    """Get emoji for a topic, fallback to generic."""
    return TOPIC_EMOJI.get(topic, "\U0001f4cc")  # pushpin as fallback


def _sort_items(items: list[ClassifiedItem]) -> list[ClassifiedItem]:
    """Sort items by trending DESC, priority ASC, relevance DESC."""
    return sorted(
        items,
        key=lambda it: (not it.trending, it.priority, -it.relevance_score),
    )


# ---------------------------------------------------------------------------
# TelegramNotifier
# ---------------------------------------------------------------------------


class TelegramNotifier(BaseNotifier):
    """Sends formatted AI briefings via Telegram Bot API.

    Inherits from BaseNotifier (send_message, send_error) and adds
    send_briefing() for rich daily digest delivery.
    """

    def __init__(
        self,
        bot_token: str | None = None,
        chat_id: str | None = None,
    ) -> None:
        settings = get_settings()
        self.bot_token = bot_token or settings.telegram_bot_token
        self.chat_id = chat_id or settings.telegram_chat_id
        self.enabled = settings.telegram_alerts_enabled and bool(self.bot_token and self.chat_id)
        self._base_url = f"https://api.telegram.org/bot{self.bot_token}"

    # ------------------------------------------------------------------
    # BaseNotifier implementation
    # ------------------------------------------------------------------

    async def send_message(self, message: str) -> bool:
        """Send a plain text message via Telegram."""
        return await self._send(message)

    async def send_error(self, error: str, context: str = "") -> bool:
        """Send an error notification via Telegram."""
        ctx = f" en <b>{_esc(context)}</b>" if context else ""
        text = f"\U0001f6a8 <b>Error{ctx}</b>\n<code>{_esc(error[:500])}</code>"
        return await self._send(text)

    # ------------------------------------------------------------------
    # Briefing
    # ------------------------------------------------------------------

    async def send_briefing(
        self,
        items: list[ClassifiedItem],
        duration_seconds: float = 0.0,
    ) -> bool:
        """Build and send a full daily briefing.

        Args:
            items: Classified items to include in the briefing.
            duration_seconds: Pipeline duration for footer stats.

        Returns:
            True if all messages were sent successfully.
        """
        if not items:
            logger.warning("telegram_briefing_empty", reason="no items to send")
            return await self._send("\U0001f4ed No hay noticias relevantes hoy.")

        sorted_items = _sort_items(items)
        grouped = self._group_by_topic(sorted_items)

        parts: list[str] = []

        # Header
        parts.append(self._build_header(items, grouped))

        # Top 3
        top3 = self._build_top3(sorted_items)
        if top3:
            parts.append(top3)

        # Topic blocks
        for topic in TOPIC_ORDER:
            if topic in grouped:
                block = self._build_topic_block(topic, grouped[topic])
                parts.append(block)

        # Footer
        parts.append(self._build_footer(items, duration_seconds))

        full_text = "\n\n".join(parts)

        # Split and send
        chunks = _split_text(full_text, MAX_MSG_LEN)
        all_ok = True
        for i, chunk in enumerate(chunks):
            if i > 0:
                await asyncio.sleep(0.3)
            ok = await self._send(chunk)
            if not ok:
                all_ok = False

        logger.info(
            "telegram_briefing_sent",
            items=len(items),
            chunks=len(chunks),
        )
        return all_ok

    # ------------------------------------------------------------------
    # Building blocks
    # ------------------------------------------------------------------

    @staticmethod
    def _group_by_topic(items: list[ClassifiedItem]) -> dict[str, list[ClassifiedItem]]:
        """Group items by topic, maintaining sort order within each group."""
        grouped: dict[str, list[ClassifiedItem]] = {}
        for it in items:
            grouped.setdefault(it.topic, []).append(it)
        return grouped

    @staticmethod
    def _build_header(
        items: list[ClassifiedItem],
        grouped: dict[str, list[ClassifiedItem]],
    ) -> str:
        """Build the briefing header with date, topic counts, source breakdown."""
        today = datetime.now(tz=UTC).strftime("%d/%m/%Y")
        lines = [f"\U0001f4f0 <b>AI Briefing \u2014 {today}</b>\n"]

        # Topic summary lines
        for topic in TOPIC_ORDER:
            topic_items = grouped.get(topic, [])
            if not topic_items:
                continue
            emoji = _topic_emoji(topic)
            label = topic.replace("_", " ").capitalize()
            trending_count = sum(1 for it in topic_items if it.trending)
            line = f"  {emoji} {label}: {len(topic_items)}"
            if trending_count:
                line += f" \U0001f525{trending_count}"
            lines.append(line)

        # Source breakdown
        source_counts = Counter(it.item.source for it in items)
        source_parts = [f"{_source_label(s)} {c}" for s, c in source_counts.most_common()]
        source_str = " \u00b7 ".join(source_parts)
        lines.append(f"\n\U0001f4ca {len(items)} noticias  \u00b7 {source_str}")

        return "\n".join(lines)

    @staticmethod
    def _build_top3(items: list[ClassifiedItem]) -> str:
        """Build the Top 3 section from the best-sorted items."""
        top = items[:3]
        if not top:
            return ""

        lines = ["\u2b50 <b>TOP 3 DEL DIA</b>\n"]
        for idx, it in enumerate(top, 1):
            title = _esc(it.item.title)
            trending_marker = "\U0001f525" if it.trending else ""

            if it.item.url:
                url = _safe_url(it.item.url)
                lines.append(f'<b>{idx}.</b> <a href="{url}">{title}</a>{trending_marker}')
            else:
                lines.append(f"<b>{idx}.</b> {title}{trending_marker}")

            if it.summary:
                lines.append(f"    {_esc(it.summary)}")

            # Source and score
            source = _source_label(it.item.source)
            score_part = f" \u00b7 {it.item.score}pts" if it.item.score else ""
            lines.append(f"    <i>{source}{score_part}</i>")

        return "\n".join(lines)

    @staticmethod
    def _build_topic_block(topic: str, items: list[ClassifiedItem]) -> str:
        """Build a formatted block for a single topic."""
        emoji = _topic_emoji(topic)
        label = topic.replace("_", " ").upper()
        lines = [f"{emoji} <b>{label}</b>"]

        for idx, it in enumerate(items, 1):
            lines.append(TelegramNotifier._format_item_compact(it, idx))

        return "\n".join(lines)

    @staticmethod
    def _format_item_compact(item: ClassifiedItem, idx: int) -> str:
        """Format a single item in compact style for topic blocks."""
        title = _esc(item.item.title)
        trending_marker = "\U0001f525" if item.trending else ""

        if item.item.url:
            url = _safe_url(item.item.url)
            line = f'<b>{idx}.</b> <a href="{url}">{title}</a>{trending_marker}'
        else:
            line = f"<b>{idx}.</b> {title}{trending_marker}"

        parts = [line]

        # Summary only if it adds information beyond the title
        if item.summary and item.summary.lower().strip(".") != item.item.title.lower().strip("."):
            parts.append(f"    {_esc(item.summary)}")

        # Source and score
        source = _source_label(item.item.source)
        score_str = f" {item.item.score}" if item.item.score else ""
        parts.append(f"    <i>{source}{score_str}</i>")

        return "\n".join(parts)

    @staticmethod
    def _build_footer(items: list[ClassifiedItem], duration_seconds: float = 0.0) -> str:
        """Build the footer with pipeline stats."""
        sources = len({it.item.source for it in items})
        trending = sum(1 for it in items if it.trending)
        duration_str = f"{duration_seconds / 60:.1f} min" if duration_seconds else ""

        parts = [f"{len(items)} analizados", f"{sources} fuentes"]
        if duration_str:
            parts.append(duration_str)
        if trending:
            parts.append(f"{trending} trending")

        stats = " \u00b7 ".join(parts)
        return f"\u2500\u2500\u2500\n\U0001f4c8 {stats}"

    # ------------------------------------------------------------------
    # Transport
    # ------------------------------------------------------------------

    async def _send(self, text: str) -> bool:
        """Send a single message, splitting if it exceeds MAX_MSG_LEN."""
        if not self.enabled:
            logger.warning("telegram_notifier_disabled", reason="missing credentials or disabled")
            return False

        chunks = _split_text(text, MAX_MSG_LEN)
        all_ok = True

        async with httpx.AsyncClient(timeout=10) as client:
            for i, chunk in enumerate(chunks):
                if i > 0:
                    await asyncio.sleep(0.3)
                try:
                    resp = await client.post(
                        f"{self._base_url}/sendMessage",
                        json={
                            "chat_id": self.chat_id,
                            "text": chunk,
                            "parse_mode": "HTML",
                            "disable_web_page_preview": True,
                        },
                    )
                    resp.raise_for_status()
                    logger.info("telegram_message_sent", length=len(chunk))
                except Exception as exc:
                    logger.error("telegram_send_failed", error=str(exc))
                    all_ok = False

        return all_ok
