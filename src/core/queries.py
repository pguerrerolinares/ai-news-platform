"""Shared query expressions for reuse across route modules."""

from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta

from sqlalchemy import func

from src.core.models import NewsItem

effective_date = func.coalesce(NewsItem.published_at, NewsItem.created_at)


def day_start(d: date) -> datetime:
    """Return midnight UTC for *d* (inclusive range start)."""
    return datetime.combine(d, time.min, tzinfo=UTC)


def day_end_exclusive(d: date) -> datetime:
    """Return midnight UTC of the day after *d* (exclusive range end)."""
    return day_start(d + timedelta(days=1))


def since_days(days: int) -> datetime:
    """Return midnight UTC of the date *days* ago (inclusive range start)."""
    return day_start((datetime.now(tz=UTC) - timedelta(days=days)).date())
