"""Rate limiting utilities for the API behind a reverse proxy."""

from __future__ import annotations

import ipaddress

from starlette.requests import Request

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
