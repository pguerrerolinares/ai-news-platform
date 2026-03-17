"""Tests for the GitHub Trending extractor."""

from __future__ import annotations

from unittest.mock import patch

import httpx
import respx

from src.core.config import Settings
from src.extractors.base import ExtractedItem
from src.extractors.github_trending import (
    TRENDING_URL,
    GitHubTrendingExtractor,
    _is_ai_related,
    _parse_trending_html,
)


def _mock_settings(**overrides):
    defaults = {
        "max_items_per_source": 50,
        "enabled_sources": "github",
    }
    defaults.update(overrides)
    return Settings(**defaults)


def _make_trending_html(repos: list[dict]) -> str:
    """Build minimal GitHub trending HTML for testing."""
    rows = []
    for r in repos:
        desc = f'<p class="col-9 color-fg-muted my-1 pr-4">{r.get("description", "")}</p>'
        lang = ""
        if r.get("language"):
            lang = f'<span itemprop="programmingLanguage">{r["language"]}</span>'
        stars_link = (
            f'<a href="/{r["full_name"]}/stargazers" class="Link">'
            f'  {r.get("total_stars", 0):,}</a>'
        )
        stars_today = f'{r.get("stars_today", 0):,} stars today' if r.get("stars_today") else ""
        rows.append(
            f'<article class="Box-row">'
            f'<h2 class="h3 lh-condensed">'
            f'<a href="/{r["full_name"]}" data-view-component="true">'
            f'<span class="text-normal">{r["full_name"].split("/")[0]} /</span>'
            f'{r["full_name"].split("/")[1]}'
            f"</a></h2>"
            f"{desc}{lang}{stars_link}"
            f'<span class="d-inline-block float-sm-right">{stars_today}</span>'
            f"</article>"
        )
    return "<html><body>" + "\n".join(rows) + "</body></html>"


class TestParseHtml:
    def test_parses_repo_fields(self):
        html = _make_trending_html(
            [
                {
                    "full_name": "owner/ai-tool",
                    "description": "An AI framework",
                    "language": "Python",
                    "total_stars": 5000,
                    "stars_today": 200,
                }
            ]
        )
        repos = _parse_trending_html(html)
        assert len(repos) == 1
        assert repos[0]["full_name"] == "owner/ai-tool"
        assert repos[0]["description"] == "An AI framework"
        assert repos[0]["language"] == "Python"
        assert repos[0]["total_stars"] == 5000
        assert repos[0]["stars_today"] == 200

    def test_handles_missing_description(self):
        html = _make_trending_html(
            [
                {
                    "full_name": "owner/bare-repo",
                    "total_stars": 100,
                }
            ]
        )
        repos = _parse_trending_html(html)
        assert len(repos) == 1
        assert repos[0]["description"] == ""

    def test_multiple_repos(self):
        html = _make_trending_html(
            [
                {"full_name": "a/repo-1", "total_stars": 100},
                {"full_name": "b/repo-2", "total_stars": 200},
            ]
        )
        repos = _parse_trending_html(html)
        assert len(repos) == 2


class TestAiFilter:
    def test_ai_repo_detected(self):
        assert _is_ai_related({"name": "llm-tool", "description": "A tool for LLMs"})

    def test_ml_repo_detected(self):
        assert _is_ai_related({"name": "trainer", "description": "Machine learning framework"})

    def test_non_ai_repo_rejected(self):
        assert not _is_ai_related({"name": "todo-app", "description": "A simple todo application"})

    def test_ai_in_name_only(self):
        assert _is_ai_related({"name": "pytorch-lib", "description": "Utility library"})

    def test_agent_detected(self):
        assert _is_ai_related({"name": "helper", "description": "Autonomous agent framework"})


class TestExtract:
    @respx.mock
    async def test_returns_ai_filtered_items(self):
        html = _make_trending_html(
            [
                {
                    "full_name": "o/ai-tool",
                    "description": "LLM framework",
                    "total_stars": 5000,
                    "stars_today": 200,
                    "language": "Python",
                },
                {
                    "full_name": "o/todo-app",
                    "description": "A todo app",
                    "total_stars": 3000,
                    "stars_today": 100,
                },
            ]
        )
        respx.get(TRENDING_URL).mock(return_value=httpx.Response(200, text=html))
        with patch("src.extractors.github_trending.get_settings", return_value=_mock_settings()):
            result = await GitHubTrendingExtractor().extract()
        assert len(result) == 1
        assert "ai-tool" in result[0].title
        assert result[0].source == "github"

    @respx.mock
    async def test_source_name_is_github(self):
        assert GitHubTrendingExtractor().source_name == "github"

    @respx.mock
    async def test_handles_fetch_error(self):
        respx.get(TRENDING_URL).mock(side_effect=httpx.ConnectError("failed"))
        with patch("src.extractors.github_trending.get_settings", return_value=_mock_settings()):
            result = await GitHubTrendingExtractor().extract()
        assert result == []

    @respx.mock
    async def test_items_sorted_by_stars(self):
        html = _make_trending_html(
            [
                {"full_name": "o/small-ai", "description": "AI tool", "total_stars": 100},
                {"full_name": "o/big-ai", "description": "AI framework", "total_stars": 9000},
            ]
        )
        respx.get(TRENDING_URL).mock(return_value=httpx.Response(200, text=html))
        with patch("src.extractors.github_trending.get_settings", return_value=_mock_settings()):
            result = await GitHubTrendingExtractor().extract()
        assert len(result) == 2
        assert result[0].score > result[1].score

    @respx.mock
    async def test_metadata_includes_trending_flag(self):
        html = _make_trending_html(
            [
                {
                    "full_name": "o/ml-lib",
                    "description": "Deep learning lib",
                    "total_stars": 500,
                    "stars_today": 50,
                    "language": "Python",
                },
            ]
        )
        respx.get(TRENDING_URL).mock(return_value=httpx.Response(200, text=html))
        with patch("src.extractors.github_trending.get_settings", return_value=_mock_settings()):
            result = await GitHubTrendingExtractor().extract()
        assert result[0].metadata["trending"] is True
        assert result[0].metadata["stars_today"] == 50

    @respx.mock
    async def test_respects_max_items(self):
        repos = [
            {"full_name": f"o/ai-{i}", "description": "LLM tool", "total_stars": i * 100}
            for i in range(10)
        ]
        html = _make_trending_html(repos)
        respx.get(TRENDING_URL).mock(return_value=httpx.Response(200, text=html))
        with patch(
            "src.extractors.github_trending.get_settings",
            return_value=_mock_settings(max_items_per_source=3),
        ):
            result = await GitHubTrendingExtractor().extract()
        assert len(result) <= 3

    @respx.mock
    async def test_empty_page_returns_empty(self):
        respx.get(TRENDING_URL).mock(return_value=httpx.Response(200, text="<html></html>"))
        with patch("src.extractors.github_trending.get_settings", return_value=_mock_settings()):
            result = await GitHubTrendingExtractor().extract()
        assert result == []

    @respx.mock
    async def test_all_non_ai_returns_empty(self):
        html = _make_trending_html(
            [
                {"full_name": "o/todo-app", "description": "A simple todo", "total_stars": 5000},
                {"full_name": "o/css-lib", "description": "CSS framework", "total_stars": 3000},
            ]
        )
        respx.get(TRENDING_URL).mock(return_value=httpx.Response(200, text=html))
        with patch("src.extractors.github_trending.get_settings", return_value=_mock_settings()):
            result = await GitHubTrendingExtractor().extract()
        assert result == []

    @respx.mock
    async def test_items_are_extracted_items(self):
        html = _make_trending_html(
            [
                {"full_name": "o/ai-tool", "description": "LLM helper", "total_stars": 1000},
            ]
        )
        respx.get(TRENDING_URL).mock(return_value=httpx.Response(200, text=html))
        with patch("src.extractors.github_trending.get_settings", return_value=_mock_settings()):
            result = await GitHubTrendingExtractor().extract()
        assert all(isinstance(item, ExtractedItem) for item in result)
