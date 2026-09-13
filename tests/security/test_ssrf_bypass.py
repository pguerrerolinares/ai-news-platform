"""Security tests for SSRF bypass attempts against is_safe_url()."""

from __future__ import annotations

import asyncio
import socket
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from src.core.ssrf import is_safe_url, safe_get

pytestmark = [pytest.mark.security, pytest.mark.asyncio(loop_scope="session")]


class TestSSRFBypass:
    """Adversarial SSRF bypass techniques that must all be blocked."""

    async def test_ipv4_mapped_ipv6(self):
        """IPv4-mapped IPv6 address (::ffff:127.0.0.1) must be blocked."""
        assert await is_safe_url("http://[::ffff:127.0.0.1]/secret") is False

    async def test_ipv6_loopback(self):
        """IPv6 loopback (::1) must be blocked."""
        assert await is_safe_url("http://[::1]/secret") is False

    async def test_decimal_ip_encoding(self):
        """Decimal IP encoding (2130706433 = 127.0.0.1) must be blocked."""
        mock_addr_info = [(None, None, None, None, ("127.0.0.1", 0))]
        with patch("src.core.ssrf.asyncio") as mock_asyncio:
            mock_loop = AsyncMock()
            mock_loop.getaddrinfo.return_value = mock_addr_info
            mock_asyncio.get_event_loop.return_value = mock_loop
            assert await is_safe_url("http://2130706433/secret") is False

    async def test_octal_ip_encoding(self):
        """Octal IP encoding (0177.0.0.1 = 127.0.0.1) must be blocked."""
        mock_addr_info = [(None, None, None, None, ("127.0.0.1", 0))]
        with patch("src.core.ssrf.asyncio") as mock_asyncio:
            mock_loop = AsyncMock()
            mock_loop.getaddrinfo.return_value = mock_addr_info
            mock_asyncio.get_event_loop.return_value = mock_loop
            assert await is_safe_url("http://0177.0.0.1/secret") is False

    async def test_url_with_credentials(self):
        """URL with embedded credentials targeting localhost must be blocked."""
        mock_addr_info = [(None, None, None, None, ("127.0.0.1", 0))]
        with patch("src.core.ssrf.asyncio") as mock_asyncio:
            mock_loop = AsyncMock()
            mock_loop.getaddrinfo.return_value = mock_addr_info
            mock_asyncio.get_event_loop.return_value = mock_loop
            assert await is_safe_url("http://user:pass@localhost/admin") is False

    async def test_file_scheme(self):
        """file:// scheme must be blocked (no DNS needed)."""
        assert await is_safe_url("file:///etc/passwd") is False

    async def test_dns_rebinding(self):
        """Domain that resolves to private IP (DNS rebinding) must be blocked."""
        mock_addr_info = [(None, None, None, None, ("10.0.0.1", 0))]
        with patch("src.core.ssrf.asyncio") as mock_asyncio:
            mock_loop = AsyncMock()
            mock_loop.getaddrinfo.return_value = mock_addr_info
            mock_asyncio.get_event_loop.return_value = mock_loop
            assert await is_safe_url("http://evil-rebind.attacker.com/steal") is False


class TestDnsRebindingRace:
    """The single-lookup check above doesn't cover the real TOCTOU: a hostile
    resolver can answer *differently* for the safety check than it does a
    moment later, when the connection is actually made. If the two are two
    separate DNS lookups, the attacker just needs the second answer to be
    the private one -- irrespective of what the first (checked) answer was.

    ``safe_get`` must resolve exactly once and connect to that exact,
    already-validated IP, so a second (rebound) answer never has anywhere to
    be used.
    """

    async def test_second_dns_answer_is_never_connected_to(self):
        public_addrinfo = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 0))]
        private_addrinfo = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 0))]

        loop = asyncio.get_event_loop()
        # First call = safe_get's own safety check (assert_safe_url). Second
        # call = what httpx/anyio would do on its OWN if handed the raw
        # hostname instead of a pinned IP -- the attacker's rebind window.
        mock_getaddrinfo = AsyncMock(side_effect=[public_addrinfo, private_addrinfo])

        connect_targets: list[str] = []

        async def _fake_connect_tcp(
            cls: object, host: str, port: int, local_address: str | None = None
        ) -> None:
            connect_targets.append(host)
            raise OSError(f"blocked in test before any real I/O (target was {host})")

        with (
            patch.object(loop, "getaddrinfo", mock_getaddrinfo),
            patch(
                "anyio._backends._asyncio.AsyncIOBackend.connect_tcp",
                classmethod(_fake_connect_tcp),
            ),
        ):
            async with httpx.AsyncClient(follow_redirects=False) as client:
                with pytest.raises(httpx.ConnectError):
                    await safe_get(client, "https://evil-rebind.attacker.com/steal")

        # The connection must have gone to the FIRST (validated) answer only.
        assert connect_targets == ["93.184.216.34"]
        assert "127.0.0.1" not in connect_targets
        # And the second (rebound) DNS answer must never even have been asked
        # for: safe_get resolves once and reuses that pinned IP, it doesn't
        # let httpx re-resolve the hostname on its own.
        assert mock_getaddrinfo.call_count == 1
