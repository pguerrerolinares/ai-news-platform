"""Shared SSRF protection utility.

Validates URLs before fetching to prevent Server-Side Request Forgery.
Blocks private, loopback, link-local, and reserved IP addresses.
"""

from __future__ import annotations

import asyncio
import ipaddress
import socket
from urllib.parse import urljoin, urlparse

import httpx

from src.core.logging import get_logger

logger = get_logger(__name__)

# Default ceiling on fetched response bodies (5 MB) to bound memory use.
MAX_FETCH_BYTES = 5 * 1024 * 1024
MAX_FETCH_REDIRECTS = 5


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


async def safe_get(
    client: httpx.AsyncClient,
    url: str,
    *,
    headers: dict[str, str] | None = None,
    max_bytes: int = MAX_FETCH_BYTES,
    max_redirects: int = MAX_FETCH_REDIRECTS,
) -> httpx.Response:
    """GET ``url`` with SSRF-safe redirect handling and a response-size cap.

    Every hop — the initial URL and each redirect ``Location`` — is validated
    with :func:`assert_safe_url` *before* it is fetched, closing the gap where
    httpx would otherwise follow a 3xx to a private IP (e.g. cloud metadata).
    The body is streamed and aborted past ``max_bytes`` so a hostile feed
    cannot OOM the process.

    The supplied ``client`` MUST be created with ``follow_redirects=False`` so
    redirects reach this function instead of httpx's auto-follow. Returns a
    fully-read response whose body is at most ``max_bytes``.
    """
    current = url
    for _ in range(max_redirects + 1):
        await assert_safe_url(current)
        async with client.stream("GET", current, headers=headers) as resp:
            # has_redirect_location is True only for 301/302/303/307/308 WITH a
            # Location header -- unlike is_redirect, it excludes 304 Not Modified.
            if resp.has_redirect_location:
                location = resp.headers["location"]
                current = urljoin(current, location)
                continue

            chunks: list[bytes] = []
            total = 0
            async for chunk in resp.aiter_bytes():
                total += len(chunk)
                if total > max_bytes:
                    raise ValueError(f"Response body exceeded {max_bytes} bytes for {url!r}")
                chunks.append(chunk)

            return httpx.Response(
                status_code=resp.status_code,
                headers=resp.headers,
                content=b"".join(chunks),
                request=resp.request,
            )

    raise ValueError(f"Too many redirects (>{max_redirects}) for {url!r}")


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
