"""Shared text utilities for title comparison and similarity."""

from __future__ import annotations

import html
import re
from typing import Any

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


def strip_html(text: str) -> str:
    """Remove HTML tags, decode entities, and collapse whitespace.

    Semantics preserved from the three callers:
    - rss._strip_html: tag removal + entity decode + whitespace collapse
    - arxiv._clean_description: tag removal + whitespace collapse (no entities needed there)
    - webscraper._html_to_text fallback: tag removal + strip
    """
    text = re.sub(r"<[^>]+>", "", text)
    text = html.unescape(text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def extract_feed_author(entry: Any) -> str | None:
    """Extract author name from a feedparser entry.

    Returns None when no author can be found (callers provide their own fallback).
    """
    if hasattr(entry, "authors") and entry.authors:
        names = [a.get("name", "") for a in entry.authors if a.get("name")]
        if names:
            return ", ".join(names)
    if hasattr(entry, "author") and entry.author:
        return entry.author
    return None
