"""Shared text utilities for title comparison and similarity."""

from __future__ import annotations

from difflib import SequenceMatcher

TITLE_SIMILARITY_THRESHOLD = 0.80


def title_similarity(a: str, b: str) -> float:
    """Compute title similarity ratio using SequenceMatcher."""
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()
