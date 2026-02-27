"""Rate limiting utilities for the API behind a reverse proxy."""

from starlette.requests import Request


def get_client_ip(request: Request) -> str:
    """Extract real client IP from X-Forwarded-For header.

    Falls back to the direct client address when no proxy header is present.
    """
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        # First IP in the chain is the original client
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "127.0.0.1"
