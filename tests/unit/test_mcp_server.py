"""Tests for the MCP server tool handlers."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

import src.mcp.server
from src.mcp.server import (
    _format_items,
    _get_client,
    _resolve_transport,
    get_briefing,
    get_latest,
    get_trending,
    search_news,
    semantic_search,
)


def _mock_client():
    return MagicMock()


class TestTransportSelection:
    """Tests for _resolve_transport() — transport env-var parsing without starting the server."""

    def test_stdio_is_default(self):
        env = {k: v for k, v in __import__("os").environ.items() if k != "MCP_TRANSPORT"}
        with patch.dict("os.environ", env, clear=True):
            assert _resolve_transport() == "stdio"

    def test_explicit_stdio(self):
        with patch.dict("os.environ", {"MCP_TRANSPORT": "stdio"}, clear=False):
            assert _resolve_transport() == "stdio"

    def test_streamable_http_accepted(self):
        import os

        env = {
            k: v
            for k, v in os.environ.items()
            if k not in ("MCP_TRANSPORT", "MCP_PORT", "FASTMCP_PORT", "FASTMCP_HOST")
        }
        env["MCP_TRANSPORT"] = "streamable-http"
        with patch.dict("os.environ", env, clear=True):
            result = _resolve_transport()
        assert result == "streamable-http"

    def test_invalid_transport_raises(self):
        with (
            patch.dict("os.environ", {"MCP_TRANSPORT": "grpc"}, clear=False),
            pytest.raises(ValueError, match="Unsupported MCP_TRANSPORT"),
        ):
            _resolve_transport()

    def test_streamable_http_sets_settings_port(self):
        import os

        env = {k: v for k, v in os.environ.items() if k != "MCP_PORT"}
        env["MCP_TRANSPORT"] = "streamable-http"
        env["MCP_PORT"] = "9001"
        original = (src.mcp.server.mcp.settings.host, src.mcp.server.mcp.settings.port)
        try:
            with patch.dict("os.environ", env, clear=True):
                _resolve_transport()
            assert src.mcp.server.mcp.settings.port == 9001
        finally:
            src.mcp.server.mcp.settings.host, src.mcp.server.mcp.settings.port = original

    def test_streamable_http_default_port_8001(self):
        import os

        env = {k: v for k, v in os.environ.items() if k not in ("MCP_PORT", "MCP_TRANSPORT")}
        env["MCP_TRANSPORT"] = "streamable-http"
        original = (src.mcp.server.mcp.settings.host, src.mcp.server.mcp.settings.port)
        try:
            with patch.dict("os.environ", env, clear=True):
                _resolve_transport()
            assert src.mcp.server.mcp.settings.port == 8001
        finally:
            src.mcp.server.mcp.settings.host, src.mcp.server.mcp.settings.port = original

    def test_streamable_http_sets_settings_host(self):
        import os

        env = {k: v for k, v in os.environ.items() if k not in ("MCP_PORT", "MCP_TRANSPORT")}
        env["MCP_TRANSPORT"] = "streamable-http"
        original = (src.mcp.server.mcp.settings.host, src.mcp.server.mcp.settings.port)
        try:
            with patch.dict("os.environ", env, clear=True):
                _resolve_transport()
            assert src.mcp.server.mcp.settings.host == "0.0.0.0"
        finally:
            src.mcp.server.mcp.settings.host, src.mcp.server.mcp.settings.port = original


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
            env = {k: v for k, v in __import__("os").environ.items() if k != "MCP_API_BASE_URL"}
            with patch.dict("os.environ", env, clear=True):
                _get_client()
            mock_api_client.assert_called_once_with(base_url="http://localhost:8000")
        finally:
            src.mcp.server._client = original


class TestFormatItems:
    def test_empty_list(self):
        assert _format_items([]) == "No items found."

    def test_formats_item_with_all_fields(self):
        items = [
            {
                "source": "hackernews",
                "title": "AI News",
                "topic": "models",
                "score": 100,
                "summary": "Big news",
                "url": "https://example.com",
            }
        ]
        result = _format_items(items)
        assert "[hackernews]" in result
        assert "AI News" in result
        assert "100 pts" in result
        assert "[models]" in result
        assert "Big news" in result
        assert "https://example.com" in result

    def test_handles_missing_fields(self):
        items = [{"title": "Minimal"}]
        result = _format_items(items)
        assert "Minimal" in result

    def test_score_zero_is_displayed(self):
        items = [{"title": "Zero Score", "source": "test", "score": 0}]
        result = _format_items(items)
        assert "0 pts" in result

    def test_score_none_not_displayed(self):
        items = [{"title": "No Score", "source": "test", "score": None}]
        result = _format_items(items)
        assert "pts" not in result


class TestSearchNews:
    @patch("src.mcp.server._get_client")
    def test_returns_formatted_results(self, mock_get):
        client = _mock_client()
        client.search.return_value = [{"title": "Result", "source": "arxiv"}]
        mock_get.return_value = client
        result = search_news(query="LLM")
        assert "1 results" in result
        assert "Result" in result
        client.search.assert_called_once_with(
            q="LLM", topic=None, date_from=None, date_to=None, limit=10
        )

    @patch("src.mcp.server._get_client")
    def test_passes_topic_filter(self, mock_get):
        client = _mock_client()
        client.search.return_value = []
        mock_get.return_value = client
        search_news(query="AI", topic="papers")
        client.search.assert_called_once_with(
            q="AI", topic="papers", date_from=None, date_to=None, limit=10
        )

    @patch("src.mcp.server._get_client")
    def test_empty_results(self, mock_get):
        client = _mock_client()
        client.search.return_value = []
        mock_get.return_value = client
        result = search_news(query="nothing")
        assert "0 results" in result


class TestGetLatest:
    @patch("src.mcp.server._get_client")
    def test_returns_formatted_items(self, mock_get):
        client = _mock_client()
        client.get_latest.return_value = [{"title": "New", "source": "reddit"}]
        mock_get.return_value = client
        result = get_latest(limit=5)
        assert "1 items" in result
        assert "New" in result

    @patch("src.mcp.server._get_client")
    def test_passes_topic_to_client(self, mock_get):
        client = _mock_client()
        client.get_latest.return_value = []
        mock_get.return_value = client
        get_latest(topic="models")
        client.get_latest.assert_called_once_with(topic="models", limit=10)


class TestGetTrending:
    @patch("src.mcp.server._get_client")
    def test_returns_trending(self, mock_get):
        client = _mock_client()
        client.get_trending.return_value = [
            {"title": "Hot", "source": "hackernews", "trending": True}
        ]
        mock_get.return_value = client
        result = get_trending()
        assert "Hot" in result


class TestGetBriefing:
    @patch("src.mcp.server._get_client")
    def test_formats_briefing(self, mock_get):
        client = _mock_client()
        client.get_briefing.return_value = {
            "date": "2026-02-17",
            "total_items": 50,
            "items_extracted": 120,
            "items_after_dedup": 80,
            "items_filtered": 50,
            "trending_count": 5,
            "duration_seconds": 42.0,
            "items": [{"title": "Top Item", "source": "hackernews"}],
        }
        mock_get.return_value = client
        result = get_briefing(date="2026-02-17")
        assert "2026-02-17" in result
        assert "total_items: 50" in result
        assert "Top Item" in result

    @patch("src.mcp.server._get_client")
    def test_briefing_without_items(self, mock_get):
        client = _mock_client()
        client.get_briefing.return_value = {
            "date": "2026-02-18",
            "total_items": 0,
        }
        mock_get.return_value = client
        result = get_briefing(date="2026-02-18")
        assert "2026-02-18" in result
        assert "Top" not in result


class TestSemanticSearch:
    @patch("src.mcp.server._get_client")
    def test_returns_formatted_results(self, mock_get):
        client = _mock_client()
        client.semantic_search.return_value = [{"title": "Vector Result", "source": "arxiv"}]
        mock_get.return_value = client
        result = semantic_search(query="transformer architecture")
        assert "1 results" in result
        assert "Vector Result" in result
        client.semantic_search.assert_called_once_with(q="transformer architecture", limit=10)

    @patch("src.mcp.server._get_client")
    def test_passes_limit_to_client(self, mock_get):
        client = _mock_client()
        client.semantic_search.return_value = []
        mock_get.return_value = client
        semantic_search(query="LLM", limit=5)
        client.semantic_search.assert_called_once_with(q="LLM", limit=5)

    @patch("src.mcp.server._get_client")
    def test_empty_results(self, mock_get):
        client = _mock_client()
        client.semantic_search.return_value = []
        mock_get.return_value = client
        result = semantic_search(query="nothing")
        assert "0 results" in result
        assert "No items found." in result

    @patch("src.mcp.server._get_client")
    def test_error_propagates(self, mock_get):
        client = _mock_client()
        client.semantic_search.side_effect = RuntimeError("API down")
        mock_get.return_value = client
        with pytest.raises(RuntimeError, match="API down"):
            semantic_search(query="AI")
