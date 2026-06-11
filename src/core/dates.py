"""Date parsing utilities shared across extractors."""

from __future__ import annotations

from datetime import datetime


def parse_iso_z(s: str) -> datetime | None:
    """Parse an ISO-8601 datetime string, tolerating a trailing 'Z' suffix.

    Python 3.12+ fromisoformat accepts 'Z' natively.  The try/except ensures
    callers get None instead of a ValueError on malformed or empty input.
    """
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None
