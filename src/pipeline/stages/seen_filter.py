"""Seen filter stage — skip items already stored in recent days.

Two passes:
1. URL hash: exact match against stored url_hashes (fast, indexed)
2. Title similarity: fuzzy match against recent titles (cross-source event dedup)
"""

from __future__ import annotations

from difflib import SequenceMatcher

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import get_settings
from src.core.logging import get_logger
from src.core.models import NewsItem
from src.extractors.base import ExtractedItem

logger = get_logger(__name__)

_TITLE_SIMILARITY_THRESHOLD = 0.80


async def filter_already_seen(
    session: AsyncSession,
    items: list[ExtractedItem],
) -> list[ExtractedItem]:
    """Filter out items already stored: by URL hash or by similar title.

    Pass 1 — URL hash: items whose url_hash exists in DB are filtered.
    Pass 2 — Title similarity: items whose title is >=80% similar to a
    recently stored title are filtered (cross-source event dedup).

    Items without a URL (url_hash is None) still go through title check.
    """
    if not items:
        return []

    settings = get_settings()
    window_days = settings.seen_window_days
    cutoff = func.now() - func.make_interval(0, 0, 0, window_days)

    # --- Pass 1: URL hash dedup ---
    items_with_url = [i for i in items if i.url_hash is not None]
    items_without_url = [i for i in items if i.url_hash is None]

    existing_hashes: set[str] = set()
    if items_with_url:
        url_hashes = [i.url_hash for i in items_with_url]
        stmt = select(NewsItem.url_hash).where(
            NewsItem.url_hash.in_(url_hashes),
            NewsItem.created_at >= cutoff,
        )
        result = await session.execute(stmt)
        existing_hashes = set(result.scalars().all())

    after_url = [i for i in items_with_url if i.url_hash not in existing_hashes]
    url_filtered = len(items_with_url) - len(after_url)
    candidates = after_url + items_without_url

    if not candidates:
        if url_filtered > 0:
            logger.info(
                "seen_filter_applied",
                input_count=len(items),
                url_filtered=url_filtered,
                title_filtered=0,
                window_days=window_days,
            )
        return []

    # --- Pass 2: Title similarity (cross-source event dedup) ---
    stmt = select(NewsItem.title).where(NewsItem.created_at >= cutoff)
    result = await session.execute(stmt)
    recent_titles = [t.lower() for t in result.scalars().all()]

    after_title: list[ExtractedItem] = []
    title_filtered = 0
    for item in candidates:
        item_title = item.title.lower()
        is_duplicate = any(
            SequenceMatcher(None, item_title, rt).ratio() >= _TITLE_SIMILARITY_THRESHOLD
            for rt in recent_titles
        )
        if is_duplicate:
            title_filtered += 1
        else:
            after_title.append(item)

    total_filtered = url_filtered + title_filtered
    if total_filtered > 0:
        logger.info(
            "seen_filter_applied",
            input_count=len(items),
            url_filtered=url_filtered,
            title_filtered=title_filtered,
            window_days=window_days,
        )

    return after_title
