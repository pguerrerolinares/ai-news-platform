"""Tests for src.core.ssrf — shared SSRF protection utility."""

from __future__ import annotations

import socket
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.core.ssrf import assert_safe_url, is_safe_url

pytestmark = pytest.mark.asyncio(loop_scope="session")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _mock_loop_getaddrinfo(return_value=None, side_effect=None):
    """Create a patch for asyncio.get_event_loop().getaddrinfo."""
    mock_loop = MagicMock()
    mock_loop.getaddrinfo = AsyncMock(return_value=return_value, side_effect=side_effect)
    return patch("src.core.ssrf.asyncio.get_event_loop", return_value=mock_loop)


def _make_public_addrinfo(ip: str = "93.184.216.34"):
    return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, 0))]


def _make_private_addrinfo(ip: str = "192.168.1.1"):
    return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, 0))]


# ---------------------------------------------------------------------------
# assert_safe_url — raises ValueError
# ---------------------------------------------------------------------------
class TestAssertSafeUrl:
    async def test_public_ip_passes(self):
        with _mock_loop_getaddrinfo(return_value=_make_public_addrinfo()):
            await assert_safe_url("https://example.com/article")

    async def test_private_ip_raises(self):
        with (
            _mock_loop_getaddrinfo(return_value=_make_private_addrinfo("192.168.1.1")),
            pytest.raises(ValueError, match="private/reserved"),
        ):
            await assert_safe_url("https://internal.corp/secret")

    async def test_loopback_raises(self):
        with (
            _mock_loop_getaddrinfo(return_value=_make_private_addrinfo("127.0.0.1")),
            pytest.raises(ValueError, match="private/reserved"),
        ):
            await assert_safe_url("https://localhost/admin")

    async def test_link_local_raises(self):
        with (
            _mock_loop_getaddrinfo(return_value=_make_private_addrinfo("169.254.169.254")),
            pytest.raises(ValueError, match="private/reserved"),
        ):
            await assert_safe_url("http://169.254.169.254/latest/meta-data")

    async def test_non_http_scheme_raises(self):
        with pytest.raises(ValueError, match="non-HTTP scheme"):
            await assert_safe_url("ftp://example.com/file")

    async def test_file_scheme_raises(self):
        with pytest.raises(ValueError, match="non-HTTP scheme"):
            await assert_safe_url("file:///etc/passwd")

    async def test_no_hostname_raises(self):
        with pytest.raises(ValueError, match="no hostname"):
            await assert_safe_url("https://")

    async def test_dns_failure_raises(self):
        with (
            _mock_loop_getaddrinfo(side_effect=socket.gaierror("DNS lookup failed")),
            pytest.raises(ValueError, match="DNS resolution failed"),
        ):
            await assert_safe_url("https://nonexistent.invalid/page")

    async def test_reserved_ip_raises(self):
        with (
            _mock_loop_getaddrinfo(return_value=_make_private_addrinfo("10.0.0.1")),
            pytest.raises(ValueError, match="private/reserved"),
        ):
            await assert_safe_url("https://internal.example.com/api")

    async def test_ipv6_loopback_raises(self):
        ipv6_result = [(socket.AF_INET6, socket.SOCK_STREAM, 6, "", ("::1", 0, 0, 0))]
        with (
            _mock_loop_getaddrinfo(return_value=ipv6_result),
            pytest.raises(ValueError, match="private/reserved"),
        ):
            await assert_safe_url("https://[::1]/admin")


# ---------------------------------------------------------------------------
# is_safe_url — boolean wrapper
# ---------------------------------------------------------------------------
class TestIsSafeUrl:
    async def test_public_ip_returns_true(self):
        with _mock_loop_getaddrinfo(return_value=_make_public_addrinfo()):
            assert await is_safe_url("https://example.com/article") is True

    async def test_private_ip_returns_false(self):
        with _mock_loop_getaddrinfo(return_value=_make_private_addrinfo("192.168.1.1")):
            assert await is_safe_url("https://internal.corp/secret") is False

    async def test_non_http_scheme_returns_false(self):
        assert await is_safe_url("ftp://example.com/file") is False

    async def test_no_hostname_returns_false(self):
        assert await is_safe_url("https://") is False

    async def test_dns_failure_returns_false(self):
        with _mock_loop_getaddrinfo(side_effect=socket.gaierror("DNS lookup failed")):
            result = await is_safe_url("https://nonexistent.invalid/page")
            assert result is False

    async def test_empty_url_returns_false(self):
        assert await is_safe_url("") is False
