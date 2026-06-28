"""Tests for the MCP API client."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import patch

import httpx
import pytest
import respx

from src.mcp.client import APIClient

BASE = "http://localhost:8000"


class TestAuth:
    @respx.mock
    def test_acquires_guest_token_on_init(self):
        respx.post(f"{BASE}/api/auth/guest").mock(
            return_value=httpx.Response(
                200, json={"access_token": "test-jwt", "token_type": "bearer", "expires_in": 86400}
            )
        )
        client = APIClient(base_url=BASE)
        assert client.token == "test-jwt"

    @respx.mock
    def test_guest_token_failure_raises(self):
        respx.post(f"{BASE}/api/auth/guest").mock(
            return_value=httpx.Response(500, json={"detail": "Server error"})
        )
        with pytest.raises(RuntimeError, match="guest token acquisition failed"):
            APIClient(base_url=BASE)

    def test_explicit_token_skips_guest(self):
        """Providing a token directly should skip the guest endpoint."""
        client = APIClient(base_url=BASE, token="pre-existing-jwt")
        assert client.token == "pre-existing-jwt"


class TestTokenRefresh:
    """A long-lived client must recover from an expired guest token (401)."""

    @respx.mock
    def test_refreshes_token_and_retries_on_401(self):
        respx.post(f"{BASE}/api/auth/guest").mock(
            side_effect=[
                httpx.Response(200, json={"access_token": "token-1", "token_type": "bearer"}),
                httpx.Response(200, json={"access_token": "token-2", "token_type": "bearer"}),
            ]
        )
        respx.get(f"{BASE}/api/items/today").mock(
            side_effect=[
                httpx.Response(401, json={"detail": "Token expired"}),
                httpx.Response(200, json=[{"title": "Fresh"}]),
            ]
        )
        client = APIClient(base_url=BASE)
        result = client.get_latest()
        assert result == [{"title": "Fresh"}]
        # Guest endpoint hit twice: once on init, once to refresh after 401.
        assert respx.calls.call_count == 4  # guest, 401 GET, guest, 200 GET

    @respx.mock
    def test_retried_request_uses_refreshed_token(self):
        respx.post(f"{BASE}/api/auth/guest").mock(
            side_effect=[
                httpx.Response(200, json={"access_token": "stale", "token_type": "bearer"}),
                httpx.Response(200, json={"access_token": "fresh", "token_type": "bearer"}),
            ]
        )
        respx.get(f"{BASE}/api/items/today").mock(
            side_effect=[
                httpx.Response(401, json={"detail": "Token expired"}),
                httpx.Response(200, json=[]),
            ]
        )
        client = APIClient(base_url=BASE)
        client.get_latest()
        assert client.token == "fresh"
        assert respx.calls.last.request.headers["Authorization"] == "Bearer fresh"

    @respx.mock
    def test_persistent_401_raises_without_infinite_retry(self):
        respx.post(f"{BASE}/api/auth/guest").mock(
            return_value=httpx.Response(200, json={"access_token": "jwt", "token_type": "bearer"})
        )
        guest_route = respx.routes[0]
        items_route = respx.get(f"{BASE}/api/items/today").mock(
            return_value=httpx.Response(401, json={"detail": "Token expired"})
        )
        client = APIClient(base_url=BASE)
        with pytest.raises(httpx.HTTPStatusError):
            client.get_latest()
        # One refresh attempt only: init + one retry = 2 guest acquisitions, 2 GETs.
        assert guest_route.call_count == 2
        assert items_route.call_count == 2


class TestClose:
    @respx.mock
    def test_close_closes_http_client(self):
        respx.post(f"{BASE}/api/auth/guest").mock(
            return_value=httpx.Response(
                200, json={"access_token": "jwt", "token_type": "bearer", "expires_in": 86400}
            )
        )
        client = APIClient(base_url=BASE)
        with patch.object(client._http, "close") as mock_close:
            client.close()
            mock_close.assert_called_once()

    @respx.mock
    def test_context_manager_closes(self):
        respx.post(f"{BASE}/api/auth/guest").mock(
            return_value=httpx.Response(
                200, json={"access_token": "jwt", "token_type": "bearer", "expires_in": 86400}
            )
        )
        client = APIClient(base_url=BASE)
        with patch.object(client._http, "close") as mock_close:
            with client:
                pass
            mock_close.assert_called_once()


class TestSearch:
    @respx.mock
    def test_search_sends_query(self):
        respx.post(f"{BASE}/api/auth/guest").mock(
            return_value=httpx.Response(
                200, json={"access_token": "jwt", "token_type": "bearer", "expires_in": 86400}
            )
        )
        respx.get(f"{BASE}/api/search").mock(
            return_value=httpx.Response(200, json=[{"title": "Test", "source": "hackernews"}])
        )
        client = APIClient(base_url=BASE)
        result = client.search(q="AI")
        assert len(result) == 1
        assert "q=AI" in str(respx.calls.last.request.url)

    @respx.mock
    def test_search_with_topic_filter(self):
        respx.post(f"{BASE}/api/auth/guest").mock(
            return_value=httpx.Response(
                200, json={"access_token": "jwt", "token_type": "bearer", "expires_in": 86400}
            )
        )
        respx.get(f"{BASE}/api/search").mock(return_value=httpx.Response(200, json=[]))
        client = APIClient(base_url=BASE)
        client.search(q="AI", topic="models")
        assert "topic=models" in str(respx.calls.last.request.url)

    @respx.mock
    def test_search_with_date_range(self):
        respx.post(f"{BASE}/api/auth/guest").mock(
            return_value=httpx.Response(
                200, json={"access_token": "jwt", "token_type": "bearer", "expires_in": 86400}
            )
        )
        respx.get(f"{BASE}/api/search").mock(return_value=httpx.Response(200, json=[]))
        client = APIClient(base_url=BASE)
        client.search(q="AI", date_from="2026-01-01", date_to="2026-02-01")
        url = str(respx.calls.last.request.url)
        assert "date_from=2026-01-01" in url
        assert "date_to=2026-02-01" in url


class TestGetLatest:
    @respx.mock
    def test_get_latest_calls_today(self):
        respx.post(f"{BASE}/api/auth/guest").mock(
            return_value=httpx.Response(
                200, json={"access_token": "jwt", "token_type": "bearer", "expires_in": 86400}
            )
        )
        respx.get(f"{BASE}/api/items/today").mock(
            return_value=httpx.Response(200, json=[{"title": "News"}])
        )
        client = APIClient(base_url=BASE)
        result = client.get_latest(limit=5)
        assert len(result) == 1

    @respx.mock
    def test_get_latest_with_topic(self):
        respx.post(f"{BASE}/api/auth/guest").mock(
            return_value=httpx.Response(
                200, json={"access_token": "jwt", "token_type": "bearer", "expires_in": 86400}
            )
        )
        respx.get(f"{BASE}/api/items/today").mock(return_value=httpx.Response(200, json=[]))
        client = APIClient(base_url=BASE)
        client.get_latest(topic="models")
        assert "topic=models" in str(respx.calls.last.request.url)


class TestGetTrending:
    @respx.mock
    def test_get_trending_sends_filter(self):
        respx.post(f"{BASE}/api/auth/guest").mock(
            return_value=httpx.Response(
                200, json={"access_token": "jwt", "token_type": "bearer", "expires_in": 86400}
            )
        )
        respx.get(f"{BASE}/api/items").mock(return_value=httpx.Response(200, json=[]))
        client = APIClient(base_url=BASE)
        client.get_trending()
        assert "trending=true" in str(respx.calls.last.request.url).lower()

    @respx.mock
    def test_trending_returns_list(self):
        respx.post(f"{BASE}/api/auth/guest").mock(
            return_value=httpx.Response(
                200, json={"access_token": "jwt", "token_type": "bearer", "expires_in": 86400}
            )
        )
        respx.get(f"{BASE}/api/items").mock(
            return_value=httpx.Response(200, json=[{"title": "Hot"}, {"title": "Hotter"}])
        )
        client = APIClient(base_url=BASE)
        result = client.get_trending()
        assert isinstance(result, list)
        assert len(result) == 2


class TestSemanticSearch:
    @respx.mock
    def test_semantic_search_sends_query(self):
        respx.post(f"{BASE}/api/auth/guest").mock(
            return_value=httpx.Response(
                200, json={"access_token": "jwt", "token_type": "bearer", "expires_in": 86400}
            )
        )
        respx.get(f"{BASE}/api/search/semantic").mock(
            return_value=httpx.Response(200, json=[{"title": "Vector Result", "source": "arxiv"}])
        )
        client = APIClient(base_url=BASE)
        result = client.semantic_search(q="transformer architecture")
        assert len(result) == 1
        assert "q=transformer+architecture" in str(respx.calls.last.request.url).replace(
            "%20", "+"
        ) or "q=transformer" in str(respx.calls.last.request.url)

    @respx.mock
    def test_semantic_search_sends_limit(self):
        respx.post(f"{BASE}/api/auth/guest").mock(
            return_value=httpx.Response(
                200, json={"access_token": "jwt", "token_type": "bearer", "expires_in": 86400}
            )
        )
        respx.get(f"{BASE}/api/search/semantic").mock(return_value=httpx.Response(200, json=[]))
        client = APIClient(base_url=BASE)
        client.semantic_search(q="LLM", limit=5)
        assert "limit=5" in str(respx.calls.last.request.url)

    @respx.mock
    def test_semantic_search_sends_auth_header(self):
        respx.post(f"{BASE}/api/auth/guest").mock(
            return_value=httpx.Response(
                200, json={"access_token": "my-jwt", "token_type": "bearer", "expires_in": 86400}
            )
        )
        respx.get(f"{BASE}/api/search/semantic").mock(return_value=httpx.Response(200, json=[]))
        client = APIClient(base_url=BASE)
        client.semantic_search(q="AI")
        assert respx.calls.last.request.headers["Authorization"] == "Bearer my-jwt"

    @respx.mock
    def test_semantic_search_raises_on_http_error(self):
        respx.post(f"{BASE}/api/auth/guest").mock(
            return_value=httpx.Response(
                200, json={"access_token": "jwt", "token_type": "bearer", "expires_in": 86400}
            )
        )
        respx.get(f"{BASE}/api/search/semantic").mock(
            return_value=httpx.Response(500, json={"detail": "Server error"})
        )
        client = APIClient(base_url=BASE)
        with pytest.raises(httpx.HTTPStatusError):
            client.semantic_search(q="AI")

    @respx.mock
    def test_semantic_search_returns_parsed_json(self):
        respx.post(f"{BASE}/api/auth/guest").mock(
            return_value=httpx.Response(
                200, json={"access_token": "jwt", "token_type": "bearer", "expires_in": 86400}
            )
        )
        items = [{"title": "A"}, {"title": "B"}]
        respx.get(f"{BASE}/api/search/semantic").mock(return_value=httpx.Response(200, json=items))
        client = APIClient(base_url=BASE)
        result = client.semantic_search(q="neural")
        assert result == items


class TestGetBriefing:
    @respx.mock
    def test_get_briefing_by_date(self):
        respx.post(f"{BASE}/api/auth/guest").mock(
            return_value=httpx.Response(
                200, json={"access_token": "jwt", "token_type": "bearer", "expires_in": 86400}
            )
        )
        respx.get(f"{BASE}/api/briefings/2026-02-17").mock(
            return_value=httpx.Response(200, json={"date": "2026-02-17", "total_items": 50})
        )
        client = APIClient(base_url=BASE)
        result = client.get_briefing("2026-02-17")
        assert result["date"] == "2026-02-17"

    @respx.mock
    def test_sends_auth_header(self):
        respx.post(f"{BASE}/api/auth/guest").mock(
            return_value=httpx.Response(
                200, json={"access_token": "my-jwt", "token_type": "bearer", "expires_in": 86400}
            )
        )
        respx.get(f"{BASE}/api/items/today").mock(return_value=httpx.Response(200, json=[]))
        client = APIClient(base_url=BASE)
        client.get_latest()
        assert respx.calls.last.request.headers["Authorization"] == "Bearer my-jwt"

    @respx.mock
    def test_get_briefing_defaults_to_today(self):
        today = datetime.now(tz=UTC).strftime("%Y-%m-%d")
        respx.post(f"{BASE}/api/auth/guest").mock(
            return_value=httpx.Response(
                200, json={"access_token": "jwt", "token_type": "bearer", "expires_in": 86400}
            )
        )
        respx.get(f"{BASE}/api/briefings/{today}").mock(
            return_value=httpx.Response(200, json={"date": today})
        )
        client = APIClient(base_url=BASE)
        result = client.get_briefing()
        assert today in str(respx.calls.last.request.url)
        assert result["date"] == today
