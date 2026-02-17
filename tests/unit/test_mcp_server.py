"""Tests for the MCP server tool handlers."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from src.mcp.server import _format_items, get_briefing, get_latest, get_trending, search_news


def _mock_client():
    return MagicMock()


class TestFormatItems:
    def test_empty_list(self):
        assert _format_items([]) == "No items found."

    def test_formats_item_with_all_fields(self):
        items = [
            {
                "source": "hackernews",
                "title": "AI News",
                "topic": "modelos",
                "score": 100,
                "summary": "Big news",
                "url": "https://example.com",
            }
        ]
        result = _format_items(items)
        assert "[hackernews]" in result
        assert "AI News" in result
        assert "100 pts" in result
        assert "[modelos]" in result
        assert "Big news" in result
        assert "https://example.com" in result

    def test_handles_missing_fields(self):
        items = [{"title": "Minimal"}]
        result = _format_items(items)
        assert "Minimal" in result


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


class TestGetLatest:
    @patch("src.mcp.server._get_client")
    def test_returns_formatted_items(self, mock_get):
        client = _mock_client()
        client.get_latest.return_value = [{"title": "New", "source": "reddit"}]
        mock_get.return_value = client
        result = get_latest(limit=5)
        assert "1 items" in result
        assert "New" in result


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
