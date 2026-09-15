"""Tests for the async MCP API client."""

from __future__ import annotations

import asyncio

import httpx
import pytest
import respx

from src.mcp.client import APIClient, APIRequestError

BASE = "http://localhost:8000"
ITEM_ID = "3f1c8a52-8a55-4a7e-9a36-1a2b3c4d5e6f"


def _guest(token: str = "test-jwt") -> httpx.Response:  # noqa: S107 test fixture, not a secret
    return httpx.Response(200, json={"access_token": token, "token_type": "bearer"})


class TestAuth:
    @respx.mock
    async def test_acquires_guest_token_lazily_on_first_call(self):
        guest = respx.post(f"{BASE}/api/auth/guest").mock(return_value=_guest())
        top = respx.get(f"{BASE}/api/items/top").mock(return_value=httpx.Response(200, json=[]))

        client = APIClient(base_url=BASE)
        assert guest.call_count == 0
        await client.get_top()

        assert guest.call_count == 1
        assert top.calls.last.request.headers["Authorization"] == "Bearer test-jwt"

    @respx.mock
    async def test_guest_token_failure_raises_actionable_error(self):
        respx.post(f"{BASE}/api/auth/guest").mock(return_value=httpx.Response(500))

        client = APIClient(base_url=BASE)
        with pytest.raises(APIRequestError, match="guest token acquisition failed"):
            await client.get_top()

    @respx.mock
    async def test_explicit_token_skips_guest(self):
        guest = respx.post(f"{BASE}/api/auth/guest").mock(return_value=_guest())
        respx.get(f"{BASE}/api/items/top").mock(return_value=httpx.Response(200, json=[]))

        client = APIClient(base_url=BASE, token="pre-existing-jwt")
        await client.get_top()

        assert guest.call_count == 0


class TestTokenRefresh:
    @respx.mock
    async def test_refreshes_token_and_retries_once_on_401(self):
        respx.post(f"{BASE}/api/auth/guest").mock(side_effect=[_guest("stale"), _guest("fresh")])
        top = respx.get(f"{BASE}/api/items/top").mock(
            side_effect=[httpx.Response(401), httpx.Response(200, json=[{"title": "Fresh"}])]
        )

        client = APIClient(base_url=BASE)
        result = await client.get_top()

        assert result == [{"title": "Fresh"}]
        assert top.calls.last.request.headers["Authorization"] == "Bearer fresh"

    @respx.mock
    async def test_concurrent_401s_trigger_a_single_guest_refresh(self):
        """Regression: the 401-refresh used to run outside the token lock, so N
        coroutines hitting 401 on the same stale token each fired their own
        POST /api/auth/guest. Fixed with the same double-checked lock as the initial
        guest-token acquisition (decision: Paul).

        Both mocked side effects below are ``async def`` and genuinely suspend
        (``await asyncio.sleep(...)``). respx resolves a *sync* side effect (or a
        plain ``return_value``) with no real await inside, so under respx's mocked
        transport a task runs start-to-finish before the next one is scheduled —
        there is never real interleaving, and this test passes 5/5 even with the
        lock removed (verified separately; see task-11-report.md). Forcing a real
        suspension point in both the 401 response and the guest-token response is
        what makes N concurrent ``get_top()`` calls actually race on the token:
        without the lock, all N see the same stale token and each fires its own
        guest POST while the others are suspended inside their own POST call; with
        the lock, only the first to acquire it refreshes and the rest see the
        already-fresh token once they get the lock.
        """

        async def top_response(request: httpx.Request) -> httpx.Response:
            if request.headers["Authorization"] == "Bearer stale":
                await asyncio.sleep(0.01)
                return httpx.Response(401)
            return httpx.Response(200, json=[])

        async def guest_response(request: httpx.Request) -> httpx.Response:
            await asyncio.sleep(0.01)
            return _guest("fresh")

        guest = respx.post(f"{BASE}/api/auth/guest").mock(side_effect=guest_response)
        respx.get(f"{BASE}/api/items/top").mock(side_effect=top_response)

        client = APIClient(base_url=BASE, token="stale")
        results = await asyncio.gather(*(client.get_top() for _ in range(5)))

        assert guest.call_count == 1
        assert results == [[]] * 5
        assert client.token == "fresh"


class TestForwardedFor:
    @respx.mock
    async def test_forwards_client_ip_header(self):
        respx.post(f"{BASE}/api/auth/guest").mock(return_value=_guest())
        top = respx.get(f"{BASE}/api/items/top").mock(return_value=httpx.Response(200, json=[]))

        await APIClient(base_url=BASE).get_top(forwarded_for="203.0.113.7")

        assert top.calls.last.request.headers["X-Forwarded-For"] == "203.0.113.7"

    @respx.mock
    async def test_no_header_when_nothing_to_forward(self):
        respx.post(f"{BASE}/api/auth/guest").mock(return_value=_guest())
        top = respx.get(f"{BASE}/api/items/top").mock(return_value=httpx.Response(200, json=[]))

        await APIClient(base_url=BASE).get_top()

        assert "X-Forwarded-For" not in top.calls.last.request.headers


class TestEndpoints:
    @respx.mock
    async def test_semantic_search_disables_recency_and_passes_filters(self):
        respx.post(f"{BASE}/api/auth/guest").mock(return_value=_guest())
        route = respx.get(f"{BASE}/api/search/semantic").mock(
            return_value=httpx.Response(200, json=[])
        )

        await APIClient(base_url=BASE).search(
            "agent memory", mode="semantic", source="arxiv", date_from="2026-01-01", limit=5
        )

        params = route.calls.last.request.url.params
        assert params["q"] == "agent memory"
        assert params["recent_first"] == "false"
        assert params["source"] == "arxiv"
        assert params["date_from"] == "2026-01-01"
        assert params["limit"] == "5"
        assert "topic" not in params

    @respx.mock
    async def test_keyword_search_uses_fts_endpoint(self):
        respx.post(f"{BASE}/api/auth/guest").mock(return_value=_guest())
        route = respx.get(f"{BASE}/api/search").mock(return_value=httpx.Response(200, json=[]))

        await APIClient(base_url=BASE).search("GLM-5", mode="keyword", topic="models")

        params = route.calls.last.request.url.params
        assert params["q"] == "GLM-5"
        assert params["topic"] == "models"
        assert "recent_first" not in params

    @respx.mock
    async def test_get_item_find_similar_trend_and_top_paths(self):
        respx.post(f"{BASE}/api/auth/guest").mock(return_value=_guest())
        item = respx.get(f"{BASE}/api/items/{ITEM_ID}").mock(
            return_value=httpx.Response(200, json={"id": ITEM_ID})
        )
        similar = respx.get(f"{BASE}/api/items/{ITEM_ID}/similar").mock(
            return_value=httpx.Response(200, json=[])
        )
        trend = respx.get(f"{BASE}/api/stats/trend").mock(
            return_value=httpx.Response(200, json={"buckets": []})
        )
        top = respx.get(f"{BASE}/api/items/top").mock(return_value=httpx.Response(200, json=[]))

        client = APIClient(base_url=BASE)
        assert await client.get_item(ITEM_ID) == {"id": ITEM_ID}
        await client.find_similar(ITEM_ID, limit=7)
        await client.topic_trend(
            "agents", method="semantic", granularity="week", since="2026-06-01"
        )
        await client.get_top(days=3, source="hackernews", limit=4)

        assert item.called
        assert similar.calls.last.request.url.params["limit"] == "7"
        trend_params = trend.calls.last.request.url.params
        assert (trend_params["q"], trend_params["method"], trend_params["granularity"]) == (
            "agents",
            "semantic",
            "week",
        )
        assert trend_params["since"] == "2026-06-01"
        assert "max_distance" not in trend_params
        top_params = top.calls.last.request.url.params
        assert (top_params["days"], top_params["source"], top_params["limit"]) == (
            "3",
            "hackernews",
            "4",
        )

    @respx.mock
    async def test_topic_trend_sends_max_distance_only_when_given(self):
        respx.post(f"{BASE}/api/auth/guest").mock(return_value=_guest())
        trend = respx.get(f"{BASE}/api/stats/trend").mock(
            return_value=httpx.Response(200, json={"buckets": []})
        )

        client = APIClient(base_url=BASE)
        await client.topic_trend("agents", method="semantic", granularity="week", max_distance=0.5)

        assert trend.calls.last.request.url.params["max_distance"] == "0.5"


class TestErrorMapping:
    @pytest.fixture()
    def api(self):
        with respx.mock(base_url=BASE) as router:
            router.post("/api/auth/guest").mock(return_value=_guest())
            yield router

    async def test_not_found_code(self, api):
        api.get(f"/api/items/{ITEM_ID}").mock(
            return_value=httpx.Response(
                404, json={"error": {"code": "NOT_FOUND", "message": "Item x not found"}}
            )
        )
        with pytest.raises(APIRequestError, match="^item not found$"):
            await APIClient(base_url=BASE).get_item(ITEM_ID)

    async def test_embedding_not_found_code(self, api):
        api.get(f"/api/items/{ITEM_ID}/similar").mock(
            return_value=httpx.Response(
                404, json={"error": {"code": "EMBEDDING_NOT_FOUND", "message": "No embedding"}}
            )
        )
        with pytest.raises(APIRequestError, match="no embedding yet; similar unavailable"):
            await APIClient(base_url=BASE).find_similar(ITEM_ID)

    async def test_fastapi_validation_detail(self, api):
        api.get("/api/stats/trend").mock(
            return_value=httpx.Response(
                422,
                json={"detail": [{"loc": ["query", "granularity"], "msg": "String should match"}]},
            )
        )
        with pytest.raises(APIRequestError, match="invalid arguments: granularity: String should"):
            await APIClient(base_url=BASE).topic_trend("x", method="keyword", granularity="day")

    async def test_api_error_validation_message(self, api):
        api.get("/api/stats/trend").mock(
            return_value=httpx.Response(
                422,
                json={"error": {"code": "VALIDATION_ERROR", "message": "since must be within"}},
            )
        )
        with pytest.raises(APIRequestError, match="invalid arguments: since must be within"):
            await APIClient(base_url=BASE).topic_trend("x", method="keyword", granularity="week")

    async def test_rate_limited_uses_retry_after(self, api):
        api.get("/api/items/top").mock(
            return_value=httpx.Response(
                429, headers={"Retry-After": "12"}, json={"error": "Rate limit exceeded"}
            )
        )
        with pytest.raises(APIRequestError, match="rate limited, retry in 12s"):
            await APIClient(base_url=BASE).get_top()

    async def test_server_error_is_backend_unavailable(self, api):
        api.get("/api/items/top").mock(return_value=httpx.Response(503, text="down"))
        with pytest.raises(APIRequestError, match=r"backend unavailable \(HTTP 503\)"):
            await APIClient(base_url=BASE).get_top()

    async def test_timeout_is_backend_unavailable(self, api):
        api.get("/api/items/top").mock(side_effect=httpx.ReadTimeout("slow"))
        with pytest.raises(APIRequestError, match=r"backend unavailable \(timeout\)"):
            await APIClient(base_url=BASE).get_top()
