"""Pre-storage validation for extracted items."""

from __future__ import annotations

from typing import Any


def validate_extracted_item(item: dict[str, Any]) -> list[str]:
    """Validate an extracted item before classification/storage.

    Returns a list of error strings. Empty list means valid.
    """
    errors: list[str] = []

    title = item.get("title")
    if not title or not str(title).strip():
        errors.append("missing or empty title")

    url = item.get("url")
    if not url or not str(url).strip():
        errors.append("missing or empty url")

    return errors
