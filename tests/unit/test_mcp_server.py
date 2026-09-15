"""Tests for the MCP server: discovery tools, contract and transport."""

from __future__ import annotations

import asyncio
import os
import time
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

import pytest
from starlette.testclient import TestClient

import src.mcp.server
from mcp.server.fastmcp.exceptions import ToolError
from src.mcp.client import APIClient, APIRequestError
from src.mcp.server import _forwarded_for, _get_client, _resolve_transport, mcp

ITEM_ID = "3f1c8a52-8a55-4a7e-9a36-1a2b3c4d5e6f"
API_ITEM = {
    "id": ITEM_ID,
    "title": "Memory consolidation for LLM agents",
    "summary": "Consolidates episodic notes into semantic memory",
    "url": "https://arxiv.org/abs/2608.00001",
    "source": "arxiv",
    "topic": "papers",
    "published_at": "2026-08-26T04:00:00Z",
    "created_at": "2026-08-26T05:10:00Z",
    "score": 0,
    "composite_score": 0.85288,
}
SUMMARY = {
    "id": ITEM_ID,
    "title": "Memory consolidation for LLM agents",
    "source": "arxiv",
    "topic": "papers",
    "published_at": "2026-08-26",
    "composite_score": 0.853,
    "summary": "Consolidates episodic notes into semantic memory",
    "url": "https://arxiv.org/abs/2608.00001",
}
TOPICS = ["models", "tools", "papers", "products", "open_source", "agents", "regulation"]
SOURCES = ["github", "arxiv", "rss", "hackernews", "huggingface", "github_search", "webscraper"]


@pytest.fixture()
def fake_client():
    client = AsyncMock(spec=APIClient)
    with patch("src.mcp.server._get_client", return_value=client):
        yield client


def _enum(prop: dict) -> list[str] | None:
    """Enum values of a JSON-schema property, looking inside anyOf for optionals."""
    if "enum" in prop:
        return prop["enum"]
    for option in prop.get("anyOf", []):
        if "enum" in option:
            return option["enum"]
    return None


class TestToolContract:
    """Projection of tools/list — names, enums, required, annotations (not a full snapshot)."""

    async def _tools(self) -> dict:
        return {tool.name: tool for tool in await mcp.list_tools()}

    async def test_exact_tool_surface(self):
        assert set(await self._tools()) == {
            "search",
            "get_item",
            "find_similar",
            "topic_trend",
            "get_top",
        }

    async def test_all_tools_are_read_only_closed_world_with_output_schema(self):
        for tool in (await self._tools()).values():
            assert tool.annotations is not None
            assert tool.annotations.model_dump(exclude_none=True) == {
                "readOnlyHint": True,
                "openWorldHint": False,
            }
            assert tool.outputSchema is not None

    async def test_enums_and_required(self):
        tools = await self._tools()
        search = tools["search"].inputSchema
        assert _enum(search["properties"]["topic"]) == TOPICS
        assert _enum(search["properties"]["source"]) == SOURCES
        assert _enum(search["properties"]["mode"]) == ["semantic", "keyword"]
        assert search["required"] == ["query"]
        trend = tools["topic_trend"].inputSchema
        assert _enum(trend["properties"]["method"]) == ["keyword", "semantic"]
        assert _enum(trend["properties"]["granularity"]) == ["week", "month"]
        assert trend["required"] == ["query"]
        assert tools["get_item"].inputSchema["required"] == ["item_id"]
        assert tools["find_similar"].inputSchema["required"] == ["item_id"]
        assert tools["get_top"].inputSchema.get("required", []) == []
        assert _enum(tools["get_top"].inputSchema["properties"]["topic"]) == TOPICS

    async def test_ctx_is_not_exposed_as_an_argument(self):
        for tool in (await self._tools()).values():
            assert "ctx" not in tool.inputSchema["properties"]


class TestSearch:
    async def test_semantic_search_maps_compact_items(self, fake_client):
        fake_client.search.return_value = [API_ITEM]

        _, out = await mcp.call_tool(
            "search", {"query": "agent memory", "source": "arxiv", "date_from": "2026-01-01"}
        )

        fake_client.search.assert_awaited_once_with(
            "agent memory",
            mode="semantic",
            topic=None,
            source="arxiv",
            date_from="2026-01-01",
            date_to=None,
            limit=10,
            forwarded_for=None,
        )
        assert out == {"query": "agent memory", "mode": "semantic", "items": [SUMMARY]}

    async def test_invalid_topic_is_an_error_not_an_empty_list(self, fake_client):
        with pytest.raises(ToolError, match="Input should be"):
            await mcp.call_tool("search", {"query": "agents", "topic": "foo"})
        fake_client.search.assert_not_awaited()

    async def test_limit_above_50_is_rejected(self, fake_client):
        with pytest.raises(ToolError, match="less than or equal to 50"):
            await mcp.call_tool("search", {"query": "agents", "limit": 99})

    async def test_published_at_falls_back_to_created_at(self, fake_client):
        fake_client.search.return_value = [{**API_ITEM, "published_at": None}]

        _, out = await mcp.call_tool("search", {"query": "agents", "mode": "keyword"})

        assert isinstance(out, dict)
        assert out["items"][0]["published_at"] == "2026-08-26"


class TestGetItem:
    async def test_returns_full_detail(self, fake_client):
        fake_client.get_item.return_value = {
            **API_ITEM,
            "author": "Ada",
            "full_text": "Abstract, not truncated.",
            "discussion_url": None,
            "engagement": None,
        }

        _, out = await mcp.call_tool("get_item", {"item_id": ITEM_ID})

        fake_client.get_item.assert_awaited_once_with(ITEM_ID, forwarded_for=None)
        assert out == {
            **SUMMARY,
            "author": "Ada",
            "full_text": "Abstract, not truncated.",
            "discussion_url": None,
            "engagement": None,
        }

    async def test_api_error_message_reaches_the_agent(self, fake_client):
        fake_client.get_item.side_effect = APIRequestError("item not found")

        with pytest.raises(ToolError, match="item not found"):
            await mcp.call_tool("get_item", {"item_id": ITEM_ID})

    async def test_malformed_id_is_rejected_before_calling_the_api(self, fake_client):
        with pytest.raises(ToolError, match="item_id"):
            await mcp.call_tool("get_item", {"item_id": "not-a-uuid"})
        fake_client.get_item.assert_not_awaited()


class TestFindSimilarTrendTop:
    async def test_find_similar(self, fake_client):
        fake_client.find_similar.return_value = [API_ITEM]

        _, out = await mcp.call_tool("find_similar", {"item_id": ITEM_ID, "limit": 3})

        fake_client.find_similar.assert_awaited_once_with(ITEM_ID, limit=3, forwarded_for=None)
        assert out == {"item_id": ITEM_ID, "items": [SUMMARY]}

    async def test_topic_trend_passes_through_series(self, fake_client):
        series = {
            "query": "agents",
            "method": "semantic",
            "granularity": "week",
            "since": "2026-08-31",
            "max_distance": 0.42,
            "distance_edges": [0.30, 0.35, 0.40, 0.45, 0.50],
            "buckets": [
                {
                    "bucket": "2026-08-31",
                    "count": 3,
                    "total_in_bucket": 120,
                    "share": 0.025,
                    "by_source": {"arxiv": 3},
                    "by_distance": {"0.30": 1, "0.35": 1, "0.40": 3, "0.45": 3, "0.50": 5},
                }
            ],
        }
        fake_client.topic_trend.return_value = series

        _, out = await mcp.call_tool(
            "topic_trend",
            {
                "query": "agents",
                "method": "semantic",
                "granularity": "week",
                "since": "2026-09-01",
                "max_distance": 0.42,
            },
        )

        fake_client.topic_trend.assert_awaited_once_with(
            "agents",
            method="semantic",
            granularity="week",
            since="2026-09-01",
            max_distance=0.42,
            forwarded_for=None,
        )
        assert out == series

    async def test_topic_trend_max_distance_out_of_range_is_rejected(self, fake_client):
        with pytest.raises(ToolError, match="less than or equal to 0.6"):
            await mcp.call_tool("topic_trend", {"query": "agents", "max_distance": 0.9})
        fake_client.topic_trend.assert_not_awaited()

    async def test_get_top_defaults(self, fake_client):
        fake_client.get_top.return_value = [API_ITEM]

        _, out = await mcp.call_tool("get_top", {})

        fake_client.get_top.assert_awaited_once_with(
            days=7, topic=None, source=None, limit=10, forwarded_for=None
        )
        assert out == {"days": 7, "topic": None, "source": None, "items": [SUMMARY]}


class TestForwardedFor:
    def test_reads_header_from_http_request(self):
        ctx = MagicMock()
        ctx.request_context.request.headers = {"x-forwarded-for": "203.0.113.7"}
        assert _forwarded_for(ctx) == "203.0.113.7"

    def test_stdio_has_no_request(self):
        ctx = MagicMock()
        ctx.request_context.request = None
        assert _forwarded_for(ctx) is None

    def test_outside_a_request_context(self):
        ctx = MagicMock()
        type(ctx).request_context = PropertyMock(side_effect=ValueError("no request"))
        assert _forwarded_for(ctx) is None

    async def test_tools_forward_the_client_ip(self, fake_client):
        fake_client.get_top.return_value = []
        with patch("src.mcp.server._forwarded_for", return_value="203.0.113.7"):
            await mcp.call_tool("get_top", {})
        assert fake_client.get_top.await_args.kwargs["forwarded_for"] == "203.0.113.7"


class TestConcurrency:
    """Regression: sync tools ran on the event loop and serialized every client (ADR-006)."""

    async def test_tool_calls_do_not_block_each_other(self):
        client = AsyncMock(spec=APIClient)

        async def slow_search(*args, **kwargs):
            await asyncio.sleep(0.3)
            return []

        client.search.side_effect = slow_search
        with patch("src.mcp.server._get_client", return_value=client):
            start = time.monotonic()
            await asyncio.gather(
                mcp.call_tool("search", {"query": "a"}),
                mcp.call_tool("search", {"query": "b"}),
            )
            elapsed = time.monotonic() - start

        assert elapsed < 1.5 * 0.3


class TestTransportSelection:
    """Tests for _resolve_transport() — transport env-var parsing without starting the server."""

    def _env(self, **overrides: str) -> dict[str, str]:
        env = {
            k: v
            for k, v in os.environ.items()
            if k not in ("MCP_TRANSPORT", "MCP_PORT", "FASTMCP_PORT", "FASTMCP_HOST")
        }
        env.update(overrides)
        return env

    def test_stdio_is_default(self):
        with patch.dict("os.environ", self._env(), clear=True):
            assert _resolve_transport() == "stdio"

    def test_invalid_transport_raises(self):
        with (
            patch.dict("os.environ", self._env(MCP_TRANSPORT="grpc"), clear=True),
            pytest.raises(ValueError, match="Unsupported MCP_TRANSPORT"),
        ):
            _resolve_transport()

    def test_streamable_http_settings(self):
        settings = src.mcp.server.mcp.settings
        original = (settings.host, settings.port, settings.stateless_http)
        try:
            env = self._env(MCP_TRANSPORT="streamable-http", MCP_PORT="9001")
            with patch.dict("os.environ", env, clear=True):
                assert _resolve_transport() == "streamable-http"
            assert settings.host == "0.0.0.0"
            assert settings.port == 9001
            assert settings.stateless_http is True
        finally:
            settings.host, settings.port, settings.stateless_http = original

    def test_streamable_http_default_port_8001(self):
        settings = src.mcp.server.mcp.settings
        original = (settings.host, settings.port, settings.stateless_http)
        try:
            with patch.dict("os.environ", self._env(MCP_TRANSPORT="streamable-http"), clear=True):
                _resolve_transport()
            assert settings.port == 8001
        finally:
            settings.host, settings.port, settings.stateless_http = original


class TestHealthEndpoint:
    """GET /health bypasses MCP JSON-RPC so the container healthcheck is falsifiable (ADR-004)."""

    def test_health_returns_200_ok(self):
        with TestClient(mcp.streamable_http_app()) as client:
            response = client.get("/health")
            assert response.status_code == 200
            assert response.json() == {"status": "ok"}

            mcp_response = client.get("/mcp")
            assert mcp_response.status_code in (406, 421)


class TestGetClient:
    @patch("src.mcp.server.APIClient")
    def test_uses_mcp_api_base_url_env(self, mock_api_client):
        original = src.mcp.server._client
        src.mcp.server._client = None
        try:
            with patch.dict("os.environ", {"MCP_API_BASE_URL": "http://custom:9000"}, clear=False):
                _get_client()
            mock_api_client.assert_called_once_with(base_url="http://custom:9000")
        finally:
            src.mcp.server._client = original

    @patch("src.mcp.server.APIClient")
    def test_defaults_to_localhost(self, mock_api_client):
        original = src.mcp.server._client
        src.mcp.server._client = None
        try:
            env = {k: v for k, v in os.environ.items() if k != "MCP_API_BASE_URL"}
            with patch.dict("os.environ", env, clear=True):
                _get_client()
            mock_api_client.assert_called_once_with(base_url="http://localhost:8000")
        finally:
            src.mcp.server._client = original
