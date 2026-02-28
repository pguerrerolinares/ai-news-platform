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
    def test_authenticates_on_init(self):
        respx.post(f"{BASE}/api/auth/token").mock(
            return_value=httpx.Response(
                200, json={"access_token": "test-jwt", "token_type": "bearer"}
            )
        )
        client = APIClient(base_url=BASE, password="secret")
        assert client.token == "test-jwt"

    @respx.mock
    def test_auth_failure_raises(self):
        respx.post(f"{BASE}/api/auth/token").mock(
            return_value=httpx.Response(401, json={"detail": "Invalid"})
        )
        with pytest.raises(RuntimeError, match="authentication failed"):
            APIClient(base_url=BASE, password="wrong")


class TestClose:
    @respx.mock
    def test_close_closes_http_client(self):
        respx.post(f"{BASE}/api/auth/token").mock(
            return_value=httpx.Response(200, json={"access_token": "jwt", "token_type": "bearer"})
        )
        client = APIClient(base_url=BASE, password="p")
        with patch.object(client._http, "close") as mock_close:
            client.close()
            mock_close.assert_called_once()

    @respx.mock
    def test_context_manager_closes(self):
        respx.post(f"{BASE}/api/auth/token").mock(
            return_value=httpx.Response(200, json={"access_token": "jwt", "token_type": "bearer"})
        )
        client = APIClient(base_url=BASE, password="p")
        with patch.object(client._http, "close") as mock_close:
            with client:
                pass
            mock_close.assert_called_once()


class TestSearch:
    @respx.mock
    def test_search_sends_query(self):
        respx.post(f"{BASE}/api/auth/token").mock(
            return_value=httpx.Response(200, json={"access_token": "jwt", "token_type": "bearer"})
        )
        respx.get(f"{BASE}/api/search").mock(
            return_value=httpx.Response(200, json=[{"title": "Test", "source": "hackernews"}])
        )
        client = APIClient(base_url=BASE, password="p")
        result = client.search(q="AI")
        assert len(result) == 1
        assert "q=AI" in str(respx.calls.last.request.url)

    @respx.mock
    def test_search_with_topic_filter(self):
        respx.post(f"{BASE}/api/auth/token").mock(
            return_value=httpx.Response(200, json={"access_token": "jwt", "token_type": "bearer"})
        )
        respx.get(f"{BASE}/api/search").mock(return_value=httpx.Response(200, json=[]))
        client = APIClient(base_url=BASE, password="p")
        client.search(q="AI", topic="models")
        assert "topic=models" in str(respx.calls.last.request.url)

    @respx.mock
    def test_search_with_date_range(self):
        respx.post(f"{BASE}/api/auth/token").mock(
            return_value=httpx.Response(200, json={"access_token": "jwt", "token_type": "bearer"})
        )
        respx.get(f"{BASE}/api/search").mock(return_value=httpx.Response(200, json=[]))
        client = APIClient(base_url=BASE, password="p")
        client.search(q="AI", date_from="2026-01-01", date_to="2026-02-01")
        url = str(respx.calls.last.request.url)
        assert "date_from=2026-01-01" in url
        assert "date_to=2026-02-01" in url


class TestGetLatest:
    @respx.mock
    def test_get_latest_calls_today(self):
        respx.post(f"{BASE}/api/auth/token").mock(
            return_value=httpx.Response(200, json={"access_token": "jwt", "token_type": "bearer"})
        )
        respx.get(f"{BASE}/api/items/today").mock(
            return_value=httpx.Response(200, json=[{"title": "News"}])
        )
        client = APIClient(base_url=BASE, password="p")
        result = client.get_latest(limit=5)
        assert len(result) == 1

    @respx.mock
    def test_get_latest_with_topic(self):
        respx.post(f"{BASE}/api/auth/token").mock(
            return_value=httpx.Response(200, json={"access_token": "jwt", "token_type": "bearer"})
        )
        respx.get(f"{BASE}/api/items/today").mock(return_value=httpx.Response(200, json=[]))
        client = APIClient(base_url=BASE, password="p")
        client.get_latest(topic="models")
        assert "topic=models" in str(respx.calls.last.request.url)


class TestGetTrending:
    @respx.mock
    def test_get_trending_sends_filter(self):
        respx.post(f"{BASE}/api/auth/token").mock(
            return_value=httpx.Response(200, json={"access_token": "jwt", "token_type": "bearer"})
        )
        respx.get(f"{BASE}/api/items").mock(return_value=httpx.Response(200, json=[]))
        client = APIClient(base_url=BASE, password="p")
        client.get_trending()
        assert "trending=true" in str(respx.calls.last.request.url).lower()

    @respx.mock
    def test_trending_returns_list(self):
        respx.post(f"{BASE}/api/auth/token").mock(
            return_value=httpx.Response(200, json={"access_token": "jwt", "token_type": "bearer"})
        )
        respx.get(f"{BASE}/api/items").mock(
            return_value=httpx.Response(200, json=[{"title": "Hot"}, {"title": "Hotter"}])
        )
        client = APIClient(base_url=BASE, password="p")
        result = client.get_trending()
        assert isinstance(result, list)
        assert len(result) == 2


class TestGetBriefing:
    @respx.mock
    def test_get_briefing_by_date(self):
        respx.post(f"{BASE}/api/auth/token").mock(
            return_value=httpx.Response(200, json={"access_token": "jwt", "token_type": "bearer"})
        )
        respx.get(f"{BASE}/api/briefings/2026-02-17").mock(
            return_value=httpx.Response(200, json={"date": "2026-02-17", "total_items": 50})
        )
        client = APIClient(base_url=BASE, password="p")
        result = client.get_briefing("2026-02-17")
        assert result["date"] == "2026-02-17"

    @respx.mock
    def test_sends_auth_header(self):
        respx.post(f"{BASE}/api/auth/token").mock(
            return_value=httpx.Response(
                200, json={"access_token": "my-jwt", "token_type": "bearer"}
            )
        )
        respx.get(f"{BASE}/api/items/today").mock(return_value=httpx.Response(200, json=[]))
        client = APIClient(base_url=BASE, password="p")
        client.get_latest()
        assert respx.calls.last.request.headers["Authorization"] == "Bearer my-jwt"

    @respx.mock
    def test_get_briefing_defaults_to_today(self):
        today = datetime.now(tz=UTC).strftime("%Y-%m-%d")
        respx.post(f"{BASE}/api/auth/token").mock(
            return_value=httpx.Response(200, json={"access_token": "jwt", "token_type": "bearer"})
        )
        respx.get(f"{BASE}/api/briefings/{today}").mock(
            return_value=httpx.Response(200, json={"date": today})
        )
        client = APIClient(base_url=BASE, password="p")
        result = client.get_briefing()
        assert today in str(respx.calls.last.request.url)
        assert result["date"] == today
