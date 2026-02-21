"""Security tests for rate limiting enforcement."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

pytestmark = [pytest.mark.security, pytest.mark.asyncio(loop_scope="session")]


class TestRateLimiting:
    """Verify rate limits are enforced on brute-force attempts."""

    async def test_auth_brute_force(self, security_client: AsyncClient) -> None:
        """6th login attempt within a minute must be rate-limited (429)."""
        for i in range(6):
            resp = await security_client.post("/api/auth/token", json={"password": f"wrong-{i}"})
            if resp.status_code == 429:
                # Rate limit hit — test passes
                assert i >= 5  # Should happen on 6th request (index 5)
                return

        # If we got here without 429, the rate limit is not enforced
        pytest.fail("Expected 429 after 6 requests, but all returned non-429 status")

    async def test_chat_rate_limit(self, security_client: AsyncClient) -> None:
        """11th chat request within a minute must be rate-limited (429)."""
        from unittest.mock import AsyncMock, patch

        from src.api.auth import create_access_token

        token = create_access_token(subject="rate-test-user")
        headers = {"Authorization": f"Bearer {token}"}

        # Mock ChatService so requests don't hit OpenAI
        async def _fake_stream(*args, **kwargs):
            yield "data: fake\n\n"

        mock_service = AsyncMock()
        mock_service.chat_stream = _fake_stream

        with patch("src.api.routes.chat._get_chat_service", return_value=mock_service):
            for i in range(11):
                resp = await security_client.post(
                    "/api/chat",
                    json={"question": f"Test question {i}?"},
                    headers=headers,
                )
                if resp.status_code == 429:
                    assert i >= 10  # Should happen on 11th request (index 10)
                    return

        pytest.fail("Expected 429 after 11 requests, but all returned non-429 status")

    async def test_rate_limit_response_format(self, security_client: AsyncClient) -> None:
        """Rate limit response must include useful error information."""
        # Exhaust the auth limit
        for _ in range(10):
            resp = await security_client.post("/api/auth/token", json={"password": "exhaust-limit"})
            if resp.status_code == 429:
                # Verify the response has useful rate-limit info
                assert resp.status_code == 429
                # slowapi returns a JSON body with an "error" key
                body = resp.json()
                assert "detail" in body or "error" in body or "Retry-After" in resp.headers
                return

        pytest.fail("Could not trigger rate limit to test response format")


class TestDataEndpointRateLimiting:
    """Verify rate limits on data endpoints added in M12."""

    async def test_search_rate_limit(
        self, security_client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        """21st search request within a minute must be rate-limited (429)."""
        for i in range(21):
            resp = await security_client.get(
                "/api/search", params={"q": f"test-{i}"}, headers=auth_headers
            )
            if resp.status_code == 429:
                assert i >= 20  # Should happen on 21st request (index 20)
                return

        pytest.fail("Expected 429 after 21 search requests, but all returned non-429")

    async def test_items_rate_limit(
        self, security_client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        """31st items request within a minute must be rate-limited (429)."""
        for i in range(31):
            resp = await security_client.get("/api/items", headers=auth_headers)
            if resp.status_code == 429:
                assert i >= 30  # Should happen on 31st request (index 30)
                return

        pytest.fail("Expected 429 after 31 items requests, but all returned non-429")

    async def test_topics_rate_limit(self, security_client: AsyncClient) -> None:
        """31st topics request within a minute must be rate-limited (429)."""
        for i in range(31):
            resp = await security_client.get("/api/topics")
            if resp.status_code == 429:
                assert i >= 30
                return

        pytest.fail("Expected 429 after 31 topics requests, but all returned non-429")
