"""Maximal Marginal Relevance (MMR) diversification for feed ranking."""

from __future__ import annotations

import re

from src.core.logging import get_logger

log = get_logger(__name__)

_WORD_RE = re.compile(r"[a-zA-Z0-9]+")


def _jaccard(text_a: str, text_b: str) -> float:
    """Jaccard similarity on word tokens."""
    tokens_a = set(_WORD_RE.findall(text_a.lower()))
    tokens_b = set(_WORD_RE.findall(text_b.lower()))
    if not tokens_a or not tokens_b:
        return 0.0
    return len(tokens_a & tokens_b) / len(tokens_a | tokens_b)


def item_similarity(a: object, b: object) -> float:
    """Compute similarity between two feed items.

    Based on source, topic, author, and title overlap.
    """
    score = 0.0
    if getattr(a, "source", None) == getattr(b, "source", None):
        score += 0.3
    if getattr(a, "topic", None) == getattr(b, "topic", None):
        score += 0.3
    if (
        getattr(a, "author", None)
        and getattr(b, "author", None)
        and getattr(a, "author", "") == getattr(b, "author", "")
    ):
        score += 0.2
    title_a = getattr(a, "title", "") or ""
    title_b = getattr(b, "title", "") or ""
    if title_a and title_b:
        score += _jaccard(title_a, title_b) * 0.2
    return score


def mmr_rank(
    candidates: list,
    lambda_: float = 0.7,
    limit: int = 20,
) -> list:
    """Rank items using Maximal Marginal Relevance.

    Balances quality (composite_score) with diversity (low similarity to
    already-selected items).

    Args:
        candidates: Items with composite_score attribute.
        lambda_: 0.0=max diversity, 1.0=pure quality. Default 0.7.
        limit: Max items to return.
    """
    if not candidates:
        return []

    remaining = list(candidates)
    selected: list = []

    for _ in range(min(limit, len(candidates))):
        best_score = float("-inf")
        best_idx = 0

        for i, item in enumerate(remaining):
            quality = getattr(item, "composite_score", 0.0) or 0.0

            # Max similarity to any already-selected item
            max_sim = max(item_similarity(item, s) for s in selected) if selected else 0.0

            mmr_score = lambda_ * quality - (1 - lambda_) * max_sim

            if mmr_score > best_score:
                best_score = mmr_score
                best_idx = i

        selected.append(remaining.pop(best_idx))

    log.info("mmr_ranking_complete", candidates=len(candidates), selected=len(selected))
    return selected
