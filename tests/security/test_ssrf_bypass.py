"""Security tests for SSRF bypass attempts against is_safe_url()."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from src.core.ssrf import is_safe_url

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
