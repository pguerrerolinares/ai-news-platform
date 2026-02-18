"""Hash-based deduplication for extracted items."""

from __future__ import annotations

from src.core.logging import get_logger
from src.extractors.base import ExtractedItem

logger = get_logger(__name__)


def deduplicate_items(items: list[ExtractedItem]) -> list[ExtractedItem]:
    """Remove duplicates using content hash and URL hash.

    Two passes:
    1. content_hash (title+url) — catches exact same post
    2. url_hash (url only) — catches cross-source duplicates, keeps highest score
    """
    if not items:
        return []

    # Pass 1: content hash dedup
    seen_content: set[str] = set()
    after_content: list[ExtractedItem] = []
    for item in items:
        h = item.content_hash
        if h not in seen_content:
            seen_content.add(h)
            after_content.append(item)

    content_deduped = len(items) - len(after_content)

    # Pass 2: url hash dedup (keep highest score per URL)
    url_map: dict[str, ExtractedItem] = {}
    for item in after_content:
        uh = item.url_hash
        if not uh:
            # No URL — can't dedup by URL, use content_hash as key
            url_map.setdefault(item.content_hash, item)
            continue
        existing = url_map.get(uh)
        if existing is None or (item.score or 0) > (existing.score or 0):
            url_map[uh] = item

    unique = list(url_map.values())
    url_deduped = len(after_content) - len(unique)
    total_deduped = content_deduped + url_deduped

    logger.info(
        "dedup_complete",
        input_count=len(items),
        output_count=len(unique),
        content_deduped=content_deduped,
        url_deduped=url_deduped,
        total_deduped=total_deduped,
    )

    return unique
