"""Event deduplication: groups items covering the same event within each topic.

Uses fuzzy title matching to identify items about the same event, picks the
best item per group, and marks winners as trending with a priority boost.
"""

from __future__ import annotations

from difflib import SequenceMatcher

from src.classifiers.base import ClassifiedItem
from src.core.logging import get_logger

logger = get_logger(__name__)

SIMILARITY_THRESHOLD = 0.80


def _pick_winner(group: list[ClassifiedItem]) -> ClassifiedItem:
    """Pick the best item from a group based on score + relevance.

    The winner gets trending=True and a priority boost of -1.
    """
    best = max(
        group,
        key=lambda ci: (ci.item.score or 0) + ci.relevance_score * 100,
    )
    best.trending = True
    best.source_count = len(group)
    best.priority = max(1, best.priority - 1)
    return best


def _title_similarity(a: str, b: str) -> float:
    """Compute title similarity ratio using SequenceMatcher."""
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def _group_by_similarity(items: list[ClassifiedItem]) -> list[list[int]]:
    """Group item indices by fuzzy title similarity using union-find.

    Items with title similarity >= SIMILARITY_THRESHOLD are placed in
    the same group. Returns list of groups (each a list of indices).
    """
    n = len(items)
    parent = list(range(n))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: int, b: int) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    for i in range(n):
        for j in range(i + 1, n):
            if _title_similarity(items[i].item.title, items[j].item.title) >= SIMILARITY_THRESHOLD:
                union(i, j)

    groups: dict[int, list[int]] = {}
    for i in range(n):
        root = find(i)
        groups.setdefault(root, []).append(i)

    return list(groups.values())


def deduplicate_events(items: list[ClassifiedItem]) -> list[ClassifiedItem]:
    """Deduplicate items by event within each topic.

    Groups items covering the same event using fuzzy title matching,
    picks the best item per group (highest score + relevance), marks
    it as trending with priority boost.
    """
    if not items:
        return []

    # Group items by topic
    by_topic: dict[str, list[ClassifiedItem]] = {}
    for ci in items:
        by_topic.setdefault(ci.topic, []).append(ci)

    results: list[ClassifiedItem] = []

    for topic, topic_items in by_topic.items():
        if len(topic_items) <= 1:
            results.extend(topic_items)
            continue

        groups = _group_by_similarity(topic_items)
        deduped_count = 0

        for group_indices in groups:
            group_items = [topic_items[idx] for idx in group_indices]
            if len(group_items) == 1:
                results.append(group_items[0])
            else:
                winner = _pick_winner(group_items)
                results.append(winner)
                deduped_count += len(group_items) - 1

        if deduped_count > 0:
            logger.info(
                "event_dedup_fuzzy",
                topic=topic,
                input_count=len(topic_items),
                deduped=deduped_count,
            )

    return results
