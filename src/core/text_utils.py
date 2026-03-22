"""Shared text utilities for title comparison and similarity."""

from __future__ import annotations

from rapidfuzz.fuzz import ratio as rapidfuzz_ratio

TITLE_SIMILARITY_THRESHOLD = 0.80


def title_similarity(a: str, b: str) -> float:
    """Compute title similarity ratio using rapidfuzz (10-50x faster than difflib)."""
    # Pre-filter: titles with >40% length difference can't be 80% similar
    la, lb = len(a), len(b)
    if la == 0 or lb == 0:
        return 0.0
    if min(la, lb) / max(la, lb) < 0.6:
        return 0.0
    return rapidfuzz_ratio(a.lower(), b.lower()) / 100.0
