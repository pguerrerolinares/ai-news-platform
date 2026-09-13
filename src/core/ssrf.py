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


async def assert_safe_url(url: str) -> str:
    """Validate that a URL is safe to fetch (no SSRF to private networks).

    Resolves the hostname once and validates *every* returned address, then
    returns one validated IP literal that the caller MUST connect to directly
    (single attempt against the first validated address; no happy-eyeballs
    fallback across A/AAAA).

    This closes a DNS-rebinding TOCTOU gap: if the caller only checked here
    and let httpx re-resolve the hostname when actually connecting, a hostile
    DNS server could answer with a public IP for this check and a private IP
    (e.g. cloud metadata) a moment later for the real connection -- two
    separate lookups, two different answers. Pinning the connection to the
    IP validated here removes the second lookup entirely.

    Raises ValueError if any resolved address is private, loopback,
    link-local, or reserved, or if the URL uses a non-HTTP(S) scheme.
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

    if not addr_infos:
        raise ValueError(f"DNS resolution returned no addresses for {hostname!r}")

    resolved_ips: list[str] = []
    for addr_info in addr_infos:
        ip_str = addr_info[4][0]
        ip = ipaddress.ip_address(ip_str)
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_reserved
            or ip.is_multicast
            or not ip.is_global
        ):
            raise ValueError(f"Blocked private/reserved IP {ip} for {hostname!r}")
        resolved_ips.append(str(ip))

    # Pin to the first validated address: this exact IP is what the caller
    # connects to, so no later (possibly attacker-controlled) DNS answer can
    # be substituted between validation and connection.
    return resolved_ips[0]


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

    The connection itself is pinned to the IP that :func:`assert_safe_url`
    validated: the request is sent to that IP literal (never the hostname),
    while ``Host`` and the TLS SNI are overridden back to the original
    hostname via the ``sni_hostname`` extension so the connection still
    reaches the right virtual host. This is what closes the DNS-rebinding
    TOCTOU gap -- without pinning, httpx would re-resolve the hostname on its
    own right after validation, and a hostile DNS server could answer
    differently the second time.

    The supplied ``client`` MUST be created with ``follow_redirects=False`` so
    redirects reach this function instead of httpx's auto-follow, MUST NOT
    enable ``http2`` (the per-request ``Connection: close`` that prevents
    cross-host connection reuse only exists in HTTP/1.1), and MUST use
    ``trust_env=False`` (with a proxy configured via the environment, the
    proxy tunnel's TLS would be done against the pinned IP and ignore
    ``sni_hostname`` -- a silent fail-closed at best). Returns a fully-read
    response whose body is at most ``max_bytes``.
    """
    current = url
    for _ in range(max_redirects + 1):
        original = httpx.URL(current)
        pinned_ip = await assert_safe_url(current)
        pinned_url = original.copy_with(host=pinned_ip)

        request_headers = dict(headers or {})
        request_headers.setdefault("Host", original.netloc.decode("ascii"))
        # httpcore keys pooled connections by (scheme, host, port) and ignores sni_hostname.
        # With host pinned to an IP, a kept-alive connection verified for hostname A would be
        # reused for hostname B on the same IP, skipping B's certificate check. Force a fresh
        # connection per request (HTTP/1.1 semantics: the client MUST NOT enable http2).
        request_headers["Connection"] = "close"

        async with client.stream(
            "GET",
            pinned_url,
            headers=request_headers,
            extensions={"sni_hostname": original.host},
        ) as resp:
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

            # ``aiter_bytes`` already decoded any Content-Encoding (gzip/br/...),
            # so ``chunks`` is the plain body. Drop the now-stale content-coding
            # and length headers; otherwise the reconstructed Response would try
            # to decompress the already-plain body again and raise DecodingError.
            headers_out = httpx.Headers(
                [
                    (k, v)
                    for k, v in resp.headers.raw
                    if k.lower() not in (b"content-encoding", b"content-length")
                ]
            )

            return httpx.Response(
                status_code=resp.status_code,
                headers=headers_out,
                content=b"".join(chunks),
                request=httpx.Request("GET", current, headers=resp.request.headers),
            )

    raise ValueError(f"Too many redirects (>{max_redirects}) for {url!r}")


async def is_safe_url(url: str) -> bool:
    """Check whether a URL is safe to fetch. Returns bool (no exception).

    Thin wrapper around assert_safe_url for call sites that prefer a
    boolean check instead of exception handling.

    Check-only: does NOT protect a later fetch against DNS rebinding -- use
    :func:`safe_get`.
    """
    try:
        await assert_safe_url(url)
        return True
    except ValueError:
        return False
