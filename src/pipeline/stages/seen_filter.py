"""Seen filter stage — skip items already stored in recent days."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import get_settings
from src.core.logging import get_logger
from src.core.models import NewsItem
from src.extractors.base import ExtractedItem

logger = get_logger(__name__)


async def filter_already_seen(
    session: AsyncSession,
    items: list[ExtractedItem],
) -> list[ExtractedItem]:
    """Filter out items whose url_hash already exists in news_items.

    Items without a URL (url_hash is None) always pass through.
    Only checks items stored within the configured seen_window_days.
    """
    if not items:
        return []

    settings = get_settings()
    window_days = settings.seen_window_days

    # Separate items with and without URLs
    items_with_url = [i for i in items if i.url_hash is not None]
    items_without_url = [i for i in items if i.url_hash is None]

    if not items_with_url:
        return items

    # Query DB for existing url_hashes (no f-string SQL — uses SQLAlchemy func)
    url_hashes = [i.url_hash for i in items_with_url]
    cutoff = func.now() - func.make_interval(0, 0, 0, window_days)
    stmt = select(NewsItem.url_hash).where(
        NewsItem.url_hash.in_(url_hashes),
        NewsItem.created_at >= cutoff,
    )
    result = await session.execute(stmt)
    existing_hashes = set(result.scalars().all())

    # Filter
    new_items = [i for i in items_with_url if i.url_hash not in existing_hashes]
    filtered_count = len(items_with_url) - len(new_items)

    if filtered_count > 0:
        logger.info(
            "seen_filter_applied",
            input_count=len(items),
            filtered=filtered_count,
            window_days=window_days,
        )

    return new_items + items_without_url
