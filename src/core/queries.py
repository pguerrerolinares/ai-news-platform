"""Shared query expressions for reuse across route modules."""

from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta

from sqlalchemy import func, text
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.models import NewsItem

effective_date = func.coalesce(NewsItem.published_at, NewsItem.created_at)


async def force_exact_scan(session: AsyncSession) -> None:
    """Disable index scans for the rest of the current transaction.

    pgvector's HNSW index returns at most ``hnsw.ef_search`` rows (40 by default) and
    applies WHERE filters after the ANN step, so a filtered query or ``limit > 40``
    silently returns fewer rows. An exact scan over the corpus (~17k x 512 dims) costs
    tens of milliseconds (ADR-006).
    """
    await session.execute(text("SET LOCAL enable_indexscan = off"))


def day_start(d: date) -> datetime:
    """Return midnight UTC for *d* (inclusive range start)."""
    return datetime.combine(d, time.min, tzinfo=UTC)


def day_end_exclusive(d: date) -> datetime:
    """Return midnight UTC of the day after *d* (exclusive range end)."""
    return day_start(d + timedelta(days=1))


def since_days(days: int) -> datetime:
    """Return midnight UTC of the date *days* ago (inclusive range start)."""
    return day_start((datetime.now(tz=UTC) - timedelta(days=days)).date())
