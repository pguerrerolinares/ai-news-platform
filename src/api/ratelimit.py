"""Rate limiting utilities for the API behind a reverse proxy."""

from __future__ import annotations

import ipaddress

from starlette.requests import Request

from src.core.config import get_settings
from src.core.logging import get_logger

logger = get_logger(__name__)

_PRIVATE_NETWORKS = (
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("::1/128"),
)


def _is_trusted_proxy(ip: str) -> bool:
    """Return True if the IP belongs to a private/loopback network."""
    try:
        addr = ipaddress.ip_address(ip)
        return any(addr in net for net in _PRIVATE_NETWORKS)
    except ValueError:
        return False


def get_client_ip(request: Request) -> str:
    """Extract real client IP, only trusting X-Forwarded-For from private proxies.

    When the direct connection comes from a trusted proxy (private/docker network),
    we read the rightmost non-private IP from X-Forwarded-For — this is the IP
    that the reverse proxy (nginx) appended, not a client-spoofed value.

    Falls back to the direct client address otherwise.
    """
    client_host = request.client.host if request.client else "127.0.0.1"

    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded and _is_trusted_proxy(client_host):
        ips = [ip.strip() for ip in forwarded.split(",")]
        for ip in reversed(ips):
            if not _is_trusted_proxy(ip):
                return ip
        return ips[0]

    return client_host


def get_rate_limit_key(request: Request) -> str:
    """Extract rate-limit key from JWT (if present) or fall back to IP.

    - Guest tokens: keyed by "guest:{jti}"
    - Authenticated tokens: keyed by "user:{sub}"
    - No token: keyed by "ip:{client_ip}"
    """
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]
        try:
            from jose import jwt as jose_jwt

            settings = get_settings()
            payload = jose_jwt.decode(
                token,
                settings.jwt_secret,
                algorithms=[settings.jwt_algorithm],
                options={"verify_exp": False},
            )
            role = payload.get("role", "")
            if role == "guest":
                jti = payload.get("jti", "unknown")
                return f"guest:{jti}"
            sub = payload.get("sub", "unknown")
            return f"user:{sub}"
        except Exception:
            logger.debug("jwt_decode_failed_for_rate_limit", token_prefix=token[:10])
    return f"ip:{get_client_ip(request)}"
