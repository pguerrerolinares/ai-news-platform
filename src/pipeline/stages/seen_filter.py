"""Seen filter stage — skip items already stored in recent days.

Two passes:
1. URL hash + content signal: same URL within the window is only filtered
   if its content_hash also matches what's stored (fast, indexed).
   A same-URL item whose content changed is treated as an update, not a dup.
2. Title similarity: fuzzy match against recent titles (cross-source event dedup)
"""

from __future__ import annotations

import asyncio

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import get_settings
from src.core.logging import get_logger
from src.core.models import NewsItem
from src.core.text_utils import TITLE_SIMILARITY_THRESHOLD, title_similarity
from src.extractors.base import ExtractedItem

logger = get_logger(__name__)


def _title_filter_sync(
    candidates: list[ExtractedItem],
    recent_titles: list[str],
    threshold: float,
) -> tuple[list[ExtractedItem], int]:
    """Pure-CPU title-similarity loop; safe to run in a thread pool."""
    after_title: list[ExtractedItem] = []
    title_filtered = 0
    for item in candidates:
        item_title = item.title.lower()
        is_duplicate = any(title_similarity(item_title, rt) >= threshold for rt in recent_titles)
        if is_duplicate:
            title_filtered += 1
        else:
            after_title.append(item)
    return after_title, title_filtered


async def filter_already_seen(
    session: AsyncSession,
    items: list[ExtractedItem],
) -> list[ExtractedItem]:
    """Filter out items already stored: by URL hash or by similar title.

    Pass 1 — URL hash: items whose url_hash exists in DB are only filtered
    if their content_hash also matches the stored one. A same-URL item with
    a different content_hash is a content update, not a duplicate, and is
    passed through (logged as `content_updated`) so it reaches storage,
    where store_classified_items() upserts it on the url_hash conflict.
    Pass 2 — Title similarity: items whose title is >=80% similar to a
    recently stored title are filtered (cross-source event dedup).

    Items without a URL (url_hash is None) still go through title check.
    """
    if not items:
        return []

    settings = get_settings()
    window_days = settings.seen_window_days
    cutoff = func.now() - func.make_interval(0, 0, 0, window_days)

    # --- Pass 1: URL hash dedup, guarded by content signal ---
    # A url_hash match alone doesn't mean "already seen": a source can
    # update the same URL later, the same day (or any day within the
    # window), with different content. content_hash is fetched alongside
    # url_hash in the same indexed, batched query (no N+1) so a same-URL
    # item whose content actually changed is treated as an update rather
    # than silently dropped.
    items_with_url = [i for i in items if i.url_hash is not None]
    items_without_url = [i for i in items if i.url_hash is None]

    stored_content_by_url_hash: dict[str, str | None] = {}
    if items_with_url:
        url_hashes = [i.url_hash for i in items_with_url]
        stmt = select(NewsItem.url_hash, NewsItem.content_hash).where(
            NewsItem.url_hash.in_(url_hashes),
            NewsItem.created_at >= cutoff,
        )
        result = await session.execute(stmt)
        stored_content_by_url_hash = dict(result.all())

    after_url: list[ExtractedItem] = []
    url_filtered = 0
    content_updated = 0
    for i in items_with_url:
        if i.url_hash not in stored_content_by_url_hash:
            after_url.append(i)  # URL not seen before in the window
        elif stored_content_by_url_hash[i.url_hash] != i.content_hash:
            content_updated += 1  # same URL, content changed -> pass through as update
            after_url.append(i)
        else:
            url_filtered += 1  # identical to what's already stored

    candidates = after_url + items_without_url

    if not candidates:
        if url_filtered > 0 or content_updated > 0:
            logger.info(
                "seen_filter_applied",
                input_count=len(items),
                url_filtered=url_filtered,
                content_updated=content_updated,
                title_filtered=0,
                window_days=window_days,
            )
        return []

    # --- Pass 2: Title similarity (cross-source event dedup) ---
    # Limit to most recent titles to bound O(N*M) comparison cost
    stmt = (
        select(NewsItem.title)
        .where(NewsItem.created_at >= cutoff)
        .order_by(NewsItem.created_at.desc())
        .limit(2000)
    )
    result = await session.execute(stmt)
    recent_titles = [t.lower() for t in result.scalars().all()]

    after_title, title_filtered = await asyncio.to_thread(
        _title_filter_sync, candidates, recent_titles, TITLE_SIMILARITY_THRESHOLD
    )

    total_filtered = url_filtered + title_filtered
    if total_filtered > 0 or content_updated > 0:
        logger.info(
            "seen_filter_applied",
            input_count=len(items),
            url_filtered=url_filtered,
            content_updated=content_updated,
            title_filtered=title_filtered,
            window_days=window_days,
        )

    return after_title
