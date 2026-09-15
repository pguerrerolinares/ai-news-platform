"""The API logs every request with the real client IP (MCP forwards X-Forwarded-For)."""

from __future__ import annotations

import structlog
from httpx import ASGITransport, AsyncClient

from src.api.app import app


async def test_request_log_includes_forwarded_client_ip():
    # ASGITransport connects from 127.0.0.1, a trusted proxy for get_client_ip.
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        with structlog.testing.capture_logs() as logs:
            await client.get("/api/does-not-exist", headers={"X-Forwarded-For": "203.0.113.7"})

    entries = [log for log in logs if log["event"] == "api_request"]
    assert len(entries) == 1
    assert entries[0]["client_ip"] == "203.0.113.7"
    assert entries[0]["path"] == "/api/does-not-exist"
    assert entries[0]["status"] == 404


async def test_metrics_endpoint_is_not_logged():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        with structlog.testing.capture_logs() as logs:
            await client.get("/metrics")

    assert not [log for log in logs if log["event"] == "api_request"]
