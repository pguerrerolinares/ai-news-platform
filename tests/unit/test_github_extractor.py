"""Tests for the GitHub Trending extractor."""

from __future__ import annotations

import time
from unittest.mock import AsyncMock, patch

import httpx
import respx

from src.core.config import Settings
from src.extractors.base import ExtractedItem
from src.extractors.github import SEARCH_URL, GitHubExtractor


def _make_repo(
    name: str = "cool-ai-project",
    full_name: str = "owner/cool-ai-project",
    description: str = "An AI project",
    html_url: str = "https://github.com/owner/cool-ai-project",
    stargazers_count: int = 200,
    forks_count: int = 30,
    language: str = "Python",
    owner_login: str = "owner",
    topics: list[str] | None = None,
    created_at: str = "2026-02-17T08:00:00Z",
    pushed_at: str = "2026-02-17T10:00:00Z",
) -> dict:
    return {
        "name": name,
        "full_name": full_name,
        "description": description,
        "html_url": html_url,
        "stargazers_count": stargazers_count,
        "forks_count": forks_count,
        "language": language,
        "owner": {"login": owner_login},
        "topics": topics or ["ai"],
        "created_at": created_at,
        "pushed_at": pushed_at,
    }


def _search_response(repos: list[dict]) -> dict:
    return {"total_count": len(repos), "incomplete_results": False, "items": repos}


def _mock_settings(**overrides):
    defaults = {
        "github_token": "",
        "github_search_queries": "AI",
        "github_min_stars": 500,
        "github_max_repo_age_days": 0,
        "max_items_per_source": 50,
        "enabled_sources": "github",
        "telegram_bot_token": "",
        "telegram_chat_id": "",
        "telegram_alerts_enabled": False,
    }
    defaults.update(overrides)
    return Settings(**defaults)


class TestSourceName:
    def test_returns_github(self):
        assert GitHubExtractor().source_name == "github"


class TestExtract:
    @respx.mock
    async def test_returns_list_of_extracted_items(self):
        repos = [
            _make_repo("repo-a", stargazers_count=300, html_url="https://github.com/owner/repo-a"),
            _make_repo("repo-b", stargazers_count=100, html_url="https://github.com/owner/repo-b"),
        ]
        respx.get(SEARCH_URL).mock(return_value=httpx.Response(200, json=_search_response(repos)))

        with patch("src.extractors.github.get_settings", return_value=_mock_settings()):
            result = await GitHubExtractor().extract()

        assert isinstance(result, list)
        assert len(result) == 2
        for item in result:
            assert isinstance(item, ExtractedItem)

    @respx.mock
    async def test_items_have_correct_source(self):
        respx.get(SEARCH_URL).mock(
            return_value=httpx.Response(200, json=_search_response([_make_repo()]))
        )
        with patch("src.extractors.github.get_settings", return_value=_mock_settings()):
            result = await GitHubExtractor().extract()
        assert all(item.source == "github" for item in result)

    @respx.mock
    async def test_items_sorted_by_stars_descending(self):
        repos = [
            _make_repo("low", stargazers_count=60),
            _make_repo("high", stargazers_count=500, html_url="https://github.com/o/high"),
            _make_repo("mid", stargazers_count=200, html_url="https://github.com/o/mid"),
        ]
        respx.get(SEARCH_URL).mock(return_value=httpx.Response(200, json=_search_response(repos)))

        with patch("src.extractors.github.get_settings", return_value=_mock_settings()):
            result = await GitHubExtractor().extract()

        scores = [item.score for item in result]
        assert scores == [500, 200, 60]

    @respx.mock
    async def test_deduplication_across_queries(self):
        repo = _make_repo("dup-repo")
        respx.get(SEARCH_URL).mock(
            return_value=httpx.Response(200, json=_search_response([repo, repo]))
        )
        with patch(
            "src.extractors.github.get_settings",
            return_value=_mock_settings(github_search_queries="AI,LLM"),
        ):
            result = await GitHubExtractor().extract()
        assert len(result) == 1

    @respx.mock
    async def test_title_includes_name_and_description(self):
        repo = _make_repo("my-tool", description="A useful tool")
        respx.get(SEARCH_URL).mock(return_value=httpx.Response(200, json=_search_response([repo])))
        with patch("src.extractors.github.get_settings", return_value=_mock_settings()):
            result = await GitHubExtractor().extract()
        assert "my-tool" in result[0].title
        assert "A useful tool" in result[0].title

    @respx.mock
    async def test_metadata_has_expected_keys(self):
        repo = _make_repo(
            language="Rust", stargazers_count=999, forks_count=42, topics=["llm", "ai"]
        )
        respx.get(SEARCH_URL).mock(return_value=httpx.Response(200, json=_search_response([repo])))
        with patch("src.extractors.github.get_settings", return_value=_mock_settings()):
            result = await GitHubExtractor().extract()
        meta = result[0].metadata
        assert meta["language"] == "Rust"
        assert meta["stars"] == 999
        assert meta["forks"] == 42
        assert "llm" in meta["topics"]

    @respx.mock
    async def test_respects_max_items_per_source(self):
        repos = [
            _make_repo(f"repo-{i}", html_url=f"https://github.com/o/repo-{i}") for i in range(10)
        ]
        respx.get(SEARCH_URL).mock(return_value=httpx.Response(200, json=_search_response(repos)))
        with patch(
            "src.extractors.github.get_settings",
            return_value=_mock_settings(max_items_per_source=3),
        ):
            result = await GitHubExtractor().extract()
        assert len(result) <= 3

    @respx.mock
    async def test_sends_auth_header_when_token_set(self):
        respx.get(SEARCH_URL).mock(return_value=httpx.Response(200, json=_search_response([])))
        with patch(
            "src.extractors.github.get_settings",
            return_value=_mock_settings(github_token="ghp_test123"),
        ):
            await GitHubExtractor().extract()
        request = respx.calls.last.request
        assert request.headers["Authorization"] == "Bearer ghp_test123"

    @respx.mock
    async def test_no_auth_header_without_token(self):
        respx.get(SEARCH_URL).mock(return_value=httpx.Response(200, json=_search_response([])))
        with patch(
            "src.extractors.github.get_settings", return_value=_mock_settings(github_token="")
        ):
            await GitHubExtractor().extract()
        request = respx.calls.last.request
        assert "Authorization" not in request.headers

    @respx.mock
    async def test_handles_api_error_gracefully(self):
        respx.get(SEARCH_URL).mock(
            return_value=httpx.Response(403, json={"message": "rate limited"})
        )
        with patch("src.extractors.github.get_settings", return_value=_mock_settings()):
            result = await GitHubExtractor().extract()
        assert result == []

    @respx.mock
    async def test_handles_network_error_gracefully(self):
        respx.get(SEARCH_URL).mock(side_effect=httpx.ConnectError("connection failed"))
        with patch("src.extractors.github.get_settings", return_value=_mock_settings()):
            result = await GitHubExtractor().extract()
        assert result == []

    @respx.mock
    async def test_empty_response_returns_empty_list(self):
        respx.get(SEARCH_URL).mock(return_value=httpx.Response(200, json=_search_response([])))
        with patch("src.extractors.github.get_settings", return_value=_mock_settings()):
            result = await GitHubExtractor().extract()
        assert result == []

    @respx.mock
    async def test_repo_without_description(self):
        repo = _make_repo(description=None)
        respx.get(SEARCH_URL).mock(return_value=httpx.Response(200, json=_search_response([repo])))
        with patch("src.extractors.github.get_settings", return_value=_mock_settings()):
            result = await GitHubExtractor().extract()
        assert len(result) == 1
        assert result[0].title  # should not crash

    @respx.mock
    async def test_multiple_queries_combine_results(self):
        repo_a = _make_repo("repo-a", html_url="https://github.com/o/a", stargazers_count=100)
        repo_b = _make_repo("repo-b", html_url="https://github.com/o/b", stargazers_count=200)
        call_count = 0

        def side_effect(request):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return httpx.Response(200, json=_search_response([repo_a]))
            return httpx.Response(200, json=_search_response([repo_b]))

        respx.get(SEARCH_URL).mock(side_effect=side_effect)
        with patch(
            "src.extractors.github.get_settings",
            return_value=_mock_settings(github_search_queries="AI,LLM"),
        ):
            result = await GitHubExtractor().extract()
        assert len(result) == 2

    @respx.mock
    async def test_rate_limit_header_triggers_sleep(self):
        repo = _make_repo("rate-limited-repo")
        reset_time = str(int(time.time()) + 2)
        respx.get(SEARCH_URL).mock(
            return_value=httpx.Response(
                200,
                json=_search_response([repo]),
                headers={
                    "X-RateLimit-Remaining": "1",
                    "X-RateLimit-Reset": reset_time,
                },
            )
        )
        with (
            patch("src.extractors.github.get_settings", return_value=_mock_settings()),
            patch("src.extractors.github.asyncio.sleep", new_callable=AsyncMock) as mock_sleep,
        ):
            result = await GitHubExtractor().extract()
        assert len(result) == 1
        mock_sleep.assert_awaited_once()

    @respx.mock
    async def test_rate_limit_header_not_present_no_sleep(self):
        repo = _make_repo("no-rate-limit-repo")
        respx.get(SEARCH_URL).mock(return_value=httpx.Response(200, json=_search_response([repo])))
        with (
            patch("src.extractors.github.get_settings", return_value=_mock_settings()),
            patch("src.extractors.github.asyncio.sleep", new_callable=AsyncMock) as mock_sleep,
        ):
            result = await GitHubExtractor().extract()
        assert len(result) == 1
        mock_sleep.assert_not_awaited()

    @respx.mock
    async def test_repo_without_owner_field(self):
        repo = _make_repo("orphan-repo")
        del repo["owner"]
        respx.get(SEARCH_URL).mock(return_value=httpx.Response(200, json=_search_response([repo])))
        with patch("src.extractors.github.get_settings", return_value=_mock_settings()):
            result = await GitHubExtractor().extract()
        assert len(result) == 1
        assert result[0].author == "unknown"

    @respx.mock
    async def test_invalid_pushed_at_returns_none(self):
        repo = _make_repo("bad-date-repo", pushed_at="not-a-date")
        respx.get(SEARCH_URL).mock(return_value=httpx.Response(200, json=_search_response([repo])))
        with patch("src.extractors.github.get_settings", return_value=_mock_settings()):
            result = await GitHubExtractor().extract()
        assert len(result) == 1
        assert result[0].published_at is None

    @respx.mock
    async def test_partial_query_failure(self):
        repo_b = _make_repo("repo-b", html_url="https://github.com/o/b", stargazers_count=150)
        call_count = 0

        def side_effect(request):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return httpx.Response(403, json={"message": "forbidden"})
            return httpx.Response(200, json=_search_response([repo_b]))

        respx.get(SEARCH_URL).mock(side_effect=side_effect)
        with patch(
            "src.extractors.github.get_settings",
            return_value=_mock_settings(github_search_queries="AI,LLM"),
        ):
            result = await GitHubExtractor().extract()
        assert len(result) == 1
        assert result[0].title.startswith("repo-b")

    @respx.mock
    async def test_search_query_appears_in_metadata(self):
        repo = _make_repo("meta-repo")
        respx.get(SEARCH_URL).mock(return_value=httpx.Response(200, json=_search_response([repo])))
        with patch(
            "src.extractors.github.get_settings",
            return_value=_mock_settings(github_search_queries="machine-learning"),
        ):
            result = await GitHubExtractor().extract()
        assert result[0].metadata["search_query"] == "machine-learning"

    @respx.mock
    async def test_search_query_uses_gte_for_pushed_date(self):
        """Verify pushed: uses >= (not >) to include today's repos."""
        respx.get(SEARCH_URL).mock(return_value=httpx.Response(200, json=_search_response([])))
        with patch("src.extractors.github.get_settings", return_value=_mock_settings()):
            await GitHubExtractor().extract()
        request = respx.calls.last.request
        query_param = str(request.url.params.get("q", ""))
        assert "pushed:>=" in query_param, f"Expected pushed:>= but got: {query_param}"

    @respx.mock
    async def test_title_with_no_description(self):
        repo = _make_repo("bare-repo", description=None)
        respx.get(SEARCH_URL).mock(return_value=httpx.Response(200, json=_search_response([repo])))
        with patch("src.extractors.github.get_settings", return_value=_mock_settings()):
            result = await GitHubExtractor().extract()
        assert result[0].title == "bare-repo"
        assert ": " not in result[0].title


class TestRepoAgeFilter:
    """Tests for github_max_repo_age_days filtering."""

    @respx.mock
    async def test_old_repo_filtered_out(self):
        """Repos older than github_max_repo_age_days are excluded."""
        old_repo = _make_repo("old-repo", created_at="2020-01-01T00:00:00Z")
        respx.get(SEARCH_URL).mock(
            return_value=httpx.Response(200, json=_search_response([old_repo]))
        )
        with patch(
            "src.extractors.github.get_settings",
            return_value=_mock_settings(github_max_repo_age_days=90),
        ):
            result = await GitHubExtractor().extract()
        assert len(result) == 0

    @respx.mock
    async def test_new_repo_passes_filter(self):
        """Repos newer than github_max_repo_age_days are kept."""
        from datetime import UTC, datetime, timedelta

        recent_date = (datetime.now(tz=UTC) - timedelta(days=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
        new_repo = _make_repo("new-repo", created_at=recent_date)
        respx.get(SEARCH_URL).mock(
            return_value=httpx.Response(200, json=_search_response([new_repo]))
        )
        with patch(
            "src.extractors.github.get_settings",
            return_value=_mock_settings(github_max_repo_age_days=90),
        ):
            result = await GitHubExtractor().extract()
        assert len(result) == 1

    @respx.mock
    async def test_none_created_at_passes_filter(self):
        """Repos with unparseable created_at are included (fail open)."""
        repo = _make_repo("no-date-repo", created_at="not-a-date")
        respx.get(SEARCH_URL).mock(return_value=httpx.Response(200, json=_search_response([repo])))
        with patch(
            "src.extractors.github.get_settings",
            return_value=_mock_settings(github_max_repo_age_days=90),
        ):
            result = await GitHubExtractor().extract()
        assert len(result) == 1

    @respx.mock
    async def test_zero_age_disables_filter(self):
        """github_max_repo_age_days=0 disables the filter."""
        old_repo = _make_repo("old-but-allowed", created_at="2020-01-01T00:00:00Z")
        respx.get(SEARCH_URL).mock(
            return_value=httpx.Response(200, json=_search_response([old_repo]))
        )
        with patch(
            "src.extractors.github.get_settings",
            return_value=_mock_settings(github_max_repo_age_days=0),
        ):
            result = await GitHubExtractor().extract()
        assert len(result) == 1


class TestSourceCreatedAt:
    """Tests for source_created_at capture."""

    @respx.mock
    async def test_extract_captures_repo_created_at(self):
        """source_created_at should be set from GitHub repo created_at field."""
        repo = _make_repo(created_at="2024-06-15T10:30:00Z")
        respx.get(SEARCH_URL).mock(return_value=httpx.Response(200, json=_search_response([repo])))
        with patch("src.extractors.github.get_settings", return_value=_mock_settings()):
            result = await GitHubExtractor().extract()
        assert result[0].source_created_at is not None
        assert result[0].source_created_at.year == 2024
        assert result[0].source_created_at.month == 6

    @respx.mock
    async def test_missing_created_at_returns_none(self):
        """source_created_at should be None when created_at is missing."""
        repo = _make_repo()
        del repo["created_at"]
        respx.get(SEARCH_URL).mock(return_value=httpx.Response(200, json=_search_response([repo])))
        with patch("src.extractors.github.get_settings", return_value=_mock_settings()):
            result = await GitHubExtractor().extract()
        assert result[0].source_created_at is None

    @respx.mock
    async def test_invalid_created_at_returns_none(self):
        """source_created_at should be None when created_at is invalid."""
        repo = _make_repo(created_at="not-a-date")
        respx.get(SEARCH_URL).mock(return_value=httpx.Response(200, json=_search_response([repo])))
        with patch("src.extractors.github.get_settings", return_value=_mock_settings()):
            result = await GitHubExtractor().extract()
        assert result[0].source_created_at is None


class TestEdgeCases:
    """Edge-case tests for GitHubExtractor robustness."""

    @respx.mock
    async def test_repo_missing_pushed_at(self):
        """Repo with missing pushed_at field returns None."""
        repo = _make_repo("no-push-repo")
        del repo["pushed_at"]
        respx.get(SEARCH_URL).mock(return_value=httpx.Response(200, json=_search_response([repo])))
        with patch("src.extractors.github.get_settings", return_value=_mock_settings()):
            result = await GitHubExtractor().extract()
        assert len(result) == 1
        assert result[0].published_at is None

    @respx.mock
    async def test_timeout_returns_empty(self):
        """TimeoutException returns []."""
        respx.get(SEARCH_URL).mock(side_effect=httpx.TimeoutException("read timed out"))
        with patch("src.extractors.github.get_settings", return_value=_mock_settings()):
            result = await GitHubExtractor().extract()
        assert result == []

    @respx.mock
    async def test_incomplete_results_still_returns_items(self):
        """incomplete_results=true in response still returns available items."""
        repo = _make_repo("partial-repo")
        data = {
            "total_count": 100,
            "incomplete_results": True,
            "items": [repo],
        }
        respx.get(SEARCH_URL).mock(return_value=httpx.Response(200, json=data))
        with patch("src.extractors.github.get_settings", return_value=_mock_settings()):
            result = await GitHubExtractor().extract()
        assert len(result) == 1
        assert result[0].title.startswith("partial-repo")
