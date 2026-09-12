"""Cache-Control header helper for public read endpoints."""

from __future__ import annotations

from fastapi import Response

PUBLIC_CACHE_CONTROL = "public, max-age=60"


def set_cache_header(response: Response) -> None:
    """Set a short public Cache-Control header on a successful read response.

    Only call this from the success path of a handler — error responses
    (raised as HTTPException/APIError) never go through this, since they are
    built by their own exception handlers in src/api/errors.py.
    """
    response.headers["Cache-Control"] = PUBLIC_CACHE_CONTROL
