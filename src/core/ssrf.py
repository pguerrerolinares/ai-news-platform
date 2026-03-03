"""Shared SSRF protection utility.

Validates URLs before fetching to prevent Server-Side Request Forgery.
Blocks private, loopback, link-local, and reserved IP addresses.
"""

from __future__ import annotations

import asyncio
import ipaddress
import socket
from urllib.parse import urlparse

from src.core.logging import get_logger

logger = get_logger(__name__)


async def assert_safe_url(url: str) -> None:
    """Validate that a URL is safe to fetch (no SSRF to private networks).

    Raises ValueError if the URL targets a private, loopback, link-local,
    or reserved IP address, or uses a non-HTTP(S) scheme.
    """
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError(f"Blocked non-HTTP scheme: {parsed.scheme!r}")

    hostname = parsed.hostname
    if not hostname:
        raise ValueError("URL has no hostname")

    # Non-blocking DNS resolution
    loop = asyncio.get_event_loop()
    try:
        addr_infos = await loop.getaddrinfo(
            hostname, None, family=socket.AF_UNSPEC, type=socket.SOCK_STREAM
        )
    except (socket.gaierror, OSError) as exc:
        raise ValueError(f"DNS resolution failed for {hostname!r}: {exc}") from exc

    for addr_info in addr_infos:
        ip_str = addr_info[4][0]
        ip = ipaddress.ip_address(ip_str)
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
            raise ValueError(f"Blocked private/reserved IP {ip} for {hostname!r}")


async def is_safe_url(url: str) -> bool:
    """Check whether a URL is safe to fetch. Returns bool (no exception).

    Thin wrapper around assert_safe_url for call sites that prefer a
    boolean check instead of exception handling.
    """
    try:
        await assert_safe_url(url)
        return True
    except ValueError:
        return False
