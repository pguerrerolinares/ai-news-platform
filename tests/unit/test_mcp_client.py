"""Tests for the MCP API client."""

from __future__ import annotations

import httpx
import pytest
import respx

from src.mcp.client import APIClient

BASE = "http://localhost:8000"


class TestAuth:
    @respx.mock
    def test_authenticates_on_init(self):
        respx.post(f"{BASE}/api/auth/token").mock(
            return_value=httpx.Response(200, json={"access_token": "test-jwt", "token_type": "bearer"})
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
        client.search(q="AI", topic="modelos")
        assert "topic=modelos" in str(respx.calls.last.request.url)


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
            return_value=httpx.Response(200, json={"access_token": "my-jwt", "token_type": "bearer"})
        )
        respx.get(f"{BASE}/api/items/today").mock(return_value=httpx.Response(200, json=[]))
        client = APIClient(base_url=BASE, password="p")
        client.get_latest()
        assert respx.calls.last.request.headers["Authorization"] == "Bearer my-jwt"
