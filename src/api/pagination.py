"""Pagination utilities for API endpoints."""
from __future__ import annotations

from starlette.responses import Response


def set_total_count_header(response: Response, count: int) -> None:
    """Set X-Total-Count header on a response."""
    response.headers["X-Total-Count"] = str(count)
