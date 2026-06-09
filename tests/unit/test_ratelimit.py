"""Tests for rate limiting IP extraction and JWT-aware key function."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import jwt
import pytest

from src.api.ratelimit import _is_trusted_proxy, get_client_ip, get_rate_limit_key
from src.core.config import Settings


class TestIsTrustedProxy:
    """Tests for private/loopback IP detection."""

    @pytest.mark.parametrize("ip", ["10.0.2.5", "172.17.0.1", "192.168.1.1", "127.0.0.1"])
    def test_private_ips_are_trusted(self, ip: str) -> None:
        assert _is_trusted_proxy(ip) is True

    def test_ipv6_loopback_is_trusted(self) -> None:
        assert _is_trusted_proxy("::1") is True

    @pytest.mark.parametrize("ip", ["8.8.8.8", "203.0.113.50", "1.2.3.4"])
    def test_public_ips_are_not_trusted(self, ip: str) -> None:
        assert _is_trusted_proxy(ip) is False

    def test_invalid_ip_is_not_trusted(self) -> None:
        assert _is_trusted_proxy("not-an-ip") is False

    def test_empty_string_is_not_trusted(self) -> None:
        assert _is_trusted_proxy("") is False


def _make_request(
    client_host: str | None = "127.0.0.1",
    forwarded_for: str | None = None,
) -> MagicMock:
    """Create a mock Starlette Request with optional X-Forwarded-For."""
    request = MagicMock()
    if client_host is not None:
        request.client.host = client_host
    else:
        request.client = None
    request.headers = {}
    if forwarded_for is not None:
        request.headers["X-Forwarded-For"] = forwarded_for
    return request


class TestGetClientIp:
    """Tests for get_client_ip extraction logic."""

    def test_no_forwarded_header_returns_client_host(self) -> None:
        request = _make_request(client_host="203.0.113.50")
        assert get_client_ip(request) == "203.0.113.50"

    def test_no_client_returns_localhost(self) -> None:
        request = _make_request(client_host=None)
        assert get_client_ip(request) == "127.0.0.1"

    def test_forwarded_from_trusted_proxy_returns_rightmost_public(self) -> None:
        """Nginx behind docker appends real client IP as last entry."""
        request = _make_request(
            client_host="10.0.2.5",
            forwarded_for="203.0.113.50",
        )
        assert get_client_ip(request) == "203.0.113.50"

    def test_forwarded_chain_returns_rightmost_non_private(self) -> None:
        """Spoofed first IP + real client appended by nginx."""
        request = _make_request(
            client_host="172.17.0.1",
            forwarded_for="1.1.1.1, 203.0.113.50",
        )
        assert get_client_ip(request) == "203.0.113.50"

    def test_forwarded_with_spoofed_first_ignores_spoofed(self) -> None:
        """Attacker sets X-Forwarded-For: fake, nginx appends real."""
        request = _make_request(
            client_host="10.0.2.5",
            forwarded_for="9.9.9.9, 203.0.113.50",
        )
        # Rightmost non-private is 203.0.113.50 (appended by nginx)
        assert get_client_ip(request) == "203.0.113.50"

    def test_forwarded_all_private_returns_first(self) -> None:
        """Edge case: all IPs in chain are private."""
        request = _make_request(
            client_host="10.0.2.5",
            forwarded_for="192.168.1.1, 10.0.0.1",
        )
        assert get_client_ip(request) == "192.168.1.1"

    def test_forwarded_from_public_client_ignores_header(self) -> None:
        """Direct connection from public IP — don't trust spoofed header."""
        request = _make_request(
            client_host="203.0.113.50",
            forwarded_for="1.2.3.4",
        )
        assert get_client_ip(request) == "203.0.113.50"

    def test_forwarded_whitespace_handling(self) -> None:
        """Whitespace around IPs in the chain is stripped."""
        request = _make_request(
            client_host="10.0.2.5",
            forwarded_for="  203.0.113.50 ,  10.0.0.1 ",
        )
        assert get_client_ip(request) == "203.0.113.50"

    def test_single_ip_from_trusted_proxy(self) -> None:
        """Single-hop proxy (most common Coolify/nginx setup)."""
        request = _make_request(
            client_host="10.0.2.5",
            forwarded_for="85.123.45.67",
        )
        assert get_client_ip(request) == "85.123.45.67"


def _make_test_settings(**overrides: object) -> Settings:
    defaults: dict[str, object] = {
        "jwt_secret": "test-secret",
        "database_url": "postgresql+asyncpg://x:x@localhost/x",
        "database_url_sync": "postgresql://x:x@localhost/x",
    }
    defaults.update(overrides)
    return Settings(**defaults)


class TestGetRateLimitKey:
    """Tests for JWT-aware rate limit key extraction."""

    def test_guest_token_keyed_by_jti(self) -> None:
        token = jwt.encode(
            {"sub": "guest:abc", "role": "guest", "jti": "unique-jti-123", "type": "access"},
            "test-secret",
            algorithm="HS256",
        )
        request = MagicMock()
        request.headers = {"Authorization": f"Bearer {token}"}
        request.client = MagicMock()
        request.client.host = "10.0.1.5"

        with patch("src.api.ratelimit.get_settings", return_value=_make_test_settings()):
            key = get_rate_limit_key(request)
        assert key == "guest:unique-jti-123"

    def test_authenticated_token_keyed_by_sub(self) -> None:
        token = jwt.encode(
            {"sub": "user-uuid-456", "role": "reader", "type": "access"},
            "test-secret",
            algorithm="HS256",
        )
        request = MagicMock()
        request.headers = {"Authorization": f"Bearer {token}"}
        request.client = MagicMock()
        request.client.host = "10.0.1.5"

        with patch("src.api.ratelimit.get_settings", return_value=_make_test_settings()):
            key = get_rate_limit_key(request)
        assert key == "user:user-uuid-456"

    def test_no_token_falls_back_to_ip(self) -> None:
        request = MagicMock()
        request.headers = {}
        request.client = MagicMock()
        request.client.host = "1.2.3.4"

        key = get_rate_limit_key(request)
        assert key == "ip:1.2.3.4"

    def test_invalid_token_falls_back_to_ip(self) -> None:
        request = MagicMock()
        request.headers = {"Authorization": "Bearer not-a-valid-jwt"}
        request.client = MagicMock()
        request.client.host = "5.6.7.8"

        with patch("src.api.ratelimit.get_settings", return_value=_make_test_settings()):
            key = get_rate_limit_key(request)
        assert key == "ip:5.6.7.8"

    def test_no_auth_header_falls_back_to_ip(self) -> None:
        request = MagicMock()
        request.headers = {"Content-Type": "application/json"}
        request.client = MagicMock()
        request.client.host = "9.8.7.6"

        key = get_rate_limit_key(request)
        assert key == "ip:9.8.7.6"
