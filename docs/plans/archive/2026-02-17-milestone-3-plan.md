# Milestone 3 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add GitHub + HuggingFace extractors, MCP server for AI agents, and frontend polish with Highcharts analytics.

**Architecture:** Two new extractors following the existing BaseExtractor pattern. MCP server as a thin stdio wrapper over the existing FastAPI API. Highcharts-powered analytics page in Angular. Rate limiting and CORS middleware in FastAPI.

**Tech Stack:** Python 3.12, httpx, mcp SDK, slowapi, FastAPI CORSMiddleware, Angular 21, highcharts-angular, pytest + respx

---

## Task 1: GitHub Trending Extractor

**Files:**
- Create: `src/extractors/github.py`
- Modify: `src/core/config.py` (add GitHub config fields)
- Modify: `src/pipeline/pipeline.py` (register extractor)
- Test: `tests/unit/test_github_extractor.py`

### Step 1: Add config fields

In `src/core/config.py`, add after the RSS feeds section (line ~79):

```python
    # GitHub
    github_token: str = ""
    github_search_queries: str = "AI,LLM,machine-learning,generative-AI"
    github_min_stars: int = 50
```

And add the property after `rss_feeds_list`:

```python
    @property
    def github_search_queries_list(self) -> list[str]:
        return [q.strip() for q in self.github_search_queries.split(",") if q.strip()]
```

### Step 2: Write the test file

Create `tests/unit/test_github_extractor.py`:

```python
"""Tests for the GitHub Trending extractor."""

from __future__ import annotations

from unittest.mock import patch

import httpx
import pytest
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
        "github_min_stars": 50,
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
        repos = [_make_repo("repo-a", stargazers_count=300), _make_repo("repo-b", stargazers_count=100)]
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
        with patch("src.extractors.github.get_settings", return_value=_mock_settings(github_search_queries="AI,LLM")):
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
        repo = _make_repo(language="Rust", stargazers_count=999, forks_count=42, topics=["llm", "ai"])
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
        repos = [_make_repo(f"repo-{i}", html_url=f"https://github.com/o/repo-{i}") for i in range(10)]
        respx.get(SEARCH_URL).mock(return_value=httpx.Response(200, json=_search_response(repos)))
        with patch("src.extractors.github.get_settings", return_value=_mock_settings(max_items_per_source=3)):
            result = await GitHubExtractor().extract()
        assert len(result) <= 3

    @respx.mock
    async def test_sends_auth_header_when_token_set(self):
        respx.get(SEARCH_URL).mock(return_value=httpx.Response(200, json=_search_response([])))
        with patch("src.extractors.github.get_settings", return_value=_mock_settings(github_token="ghp_test123")):
            await GitHubExtractor().extract()
        request = respx.calls.last.request
        assert request.headers["Authorization"] == "Bearer ghp_test123"

    @respx.mock
    async def test_no_auth_header_without_token(self):
        respx.get(SEARCH_URL).mock(return_value=httpx.Response(200, json=_search_response([])))
        with patch("src.extractors.github.get_settings", return_value=_mock_settings(github_token="")):
            await GitHubExtractor().extract()
        request = respx.calls.last.request
        assert "Authorization" not in request.headers

    @respx.mock
    async def test_handles_api_error_gracefully(self):
        respx.get(SEARCH_URL).mock(return_value=httpx.Response(403, json={"message": "rate limited"}))
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
        with patch("src.extractors.github.get_settings", return_value=_mock_settings(github_search_queries="AI,LLM")):
            result = await GitHubExtractor().extract()
        assert len(result) == 2
```

### Step 3: Run tests to verify they fail

```bash
pytest tests/unit/test_github_extractor.py -v
```

Expected: FAIL (module `src.extractors.github` not found)

### Step 4: Implement the extractor

Create `src/extractors/github.py`:

```python
"""GitHub Trending extractor via GitHub Search API."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import httpx

from src.core.config import get_settings
from src.core.logging import get_logger
from src.core.metrics import (
    extractor_duration_seconds,
    extractor_errors_total,
    items_extracted_total,
)
from src.extractors.base import BaseExtractor, ExtractedItem

logger = get_logger(__name__)
SEARCH_URL = "https://api.github.com/search/repositories"


class GitHubExtractor(BaseExtractor):
    """Extracts trending AI repositories from GitHub Search API."""

    @property
    def source_name(self) -> str:
        return "github"

    async def extract(self, since_hours: int = 48) -> list[ExtractedItem]:
        settings = get_settings()
        queries = settings.github_search_queries_list
        min_stars = settings.github_min_stars
        max_items = settings.max_items_per_source
        token = settings.github_token

        since_date = (datetime.now(tz=UTC) - timedelta(hours=since_hours)).strftime("%Y-%m-%d")
        seen_urls: set[str] = set()
        items: list[ExtractedItem] = []

        headers: dict[str, str] = {
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "AI-News-Platform/1.0",
        }
        if token:
            headers["Authorization"] = f"Bearer {token}"

        with extractor_duration_seconds.labels(source=self.source_name).time():
            async with httpx.AsyncClient(timeout=30, headers=headers) as client:
                for query in queries:
                    try:
                        new_items = await self._search(
                            client, query, since_date, min_stars, seen_urls
                        )
                        items.extend(new_items)
                    except Exception as exc:
                        logger.warning(
                            "github_search_failed",
                            query=query,
                            error=str(exc),
                        )
                        continue

        items.sort(key=lambda x: x.score or 0, reverse=True)
        items = items[:max_items]

        items_extracted_total.labels(source=self.source_name).inc(len(items))
        logger.info(
            "extraction_complete",
            source=self.source_name,
            count=len(items),
            queries=len(queries),
        )

        if not items:
            extractor_errors_total.labels(source=self.source_name).inc()

        return items

    async def _search(
        self,
        client: httpx.AsyncClient,
        query: str,
        since_date: str,
        min_stars: int,
        seen_urls: set[str],
    ) -> list[ExtractedItem]:
        q = f"{query} stars:>{min_stars} pushed:>{since_date}"
        params = {"q": q, "sort": "stars", "order": "desc", "per_page": 30}

        resp = await client.get(SEARCH_URL, params=params)
        resp.raise_for_status()
        data = resp.json()

        items: list[ExtractedItem] = []
        for repo in data.get("items", []):
            url = repo.get("html_url", "")
            if url in seen_urls:
                continue
            seen_urls.add(url)

            name = repo.get("name", "")
            description = repo.get("description") or ""
            title = f"{name}: {description}" if description else name

            try:
                pushed = datetime.fromisoformat(
                    repo.get("pushed_at", "").replace("Z", "+00:00")
                )
            except (ValueError, AttributeError):
                pushed = datetime.now(tz=UTC)

            items.append(
                ExtractedItem(
                    title=title,
                    source=self.source_name,
                    url=url,
                    text=description,
                    author=repo.get("owner", {}).get("login", "unknown"),
                    published_at=pushed,
                    score=repo.get("stargazers_count", 0),
                    metadata={
                        "language": repo.get("language"),
                        "stars": repo.get("stargazers_count", 0),
                        "forks": repo.get("forks_count", 0),
                        "topics": repo.get("topics", []),
                        "full_name": repo.get("full_name", ""),
                        "search_query": query,
                    },
                )
            )

        return items
```

### Step 5: Run tests to verify they pass

```bash
pytest tests/unit/test_github_extractor.py -v
```

Expected: ALL PASS

### Step 6: Register in pipeline

In `src/pipeline/pipeline.py`, add import at the top (after line 40):

```python
from src.extractors.github import GitHubExtractor
```

In `_get_extractors()`, add before `return extractors`:

```python
    if "github" in enabled:
        extractors.append(GitHubExtractor())
```

### Step 7: Commit

```bash
git add src/extractors/github.py src/core/config.py src/pipeline/pipeline.py tests/unit/test_github_extractor.py
git commit -m "feat: add GitHub Trending extractor (M3)"
```

---

## Task 2: HuggingFace Extractor

**Files:**
- Create: `src/extractors/huggingface.py`
- Modify: `src/core/config.py` (add HF config fields)
- Modify: `src/pipeline/pipeline.py` (register extractor)
- Test: `tests/unit/test_huggingface_extractor.py`

### Step 1: Add config fields

In `src/core/config.py`, add after the GitHub section:

```python
    # HuggingFace
    hf_min_downloads: int = 100
```

### Step 2: Write the test file

Create `tests/unit/test_huggingface_extractor.py`:

```python
"""Tests for the HuggingFace extractor."""

from __future__ import annotations

from unittest.mock import patch

import httpx
import pytest
import respx

from src.core.config import Settings
from src.extractors.base import ExtractedItem
from src.extractors.huggingface import API_URL, HuggingFaceExtractor


def _make_model(
    model_id: str = "meta-llama/Llama-3-8B",
    author: str = "meta-llama",
    downloads: int = 50000,
    likes: int = 1200,
    pipeline_tag: str = "text-generation",
    tags: list[str] | None = None,
    last_modified: str = "2026-02-17T10:00:00.000Z",
    card_data: dict | None = None,
) -> dict:
    return {
        "modelId": model_id,  # This is the actual field name from HF API
        "id": model_id,
        "author": author,
        "downloads": downloads,
        "likes": likes,
        "pipeline_tag": pipeline_tag,
        "tags": tags or ["text-generation", "pytorch"],
        "lastModified": last_modified,
        "cardData": card_data,
    }


def _mock_settings(**overrides):
    defaults = {
        "hf_min_downloads": 100,
        "max_items_per_source": 50,
        "enabled_sources": "huggingface",
        "telegram_bot_token": "",
        "telegram_chat_id": "",
        "telegram_alerts_enabled": False,
    }
    defaults.update(overrides)
    return Settings(**defaults)


class TestSourceName:
    def test_returns_huggingface(self):
        assert HuggingFaceExtractor().source_name == "huggingface"


class TestExtract:
    @respx.mock
    async def test_returns_list_of_extracted_items(self):
        models = [_make_model("org/model-a", downloads=5000), _make_model("org/model-b", downloads=3000)]
        respx.get(API_URL).mock(return_value=httpx.Response(200, json=models))

        with patch("src.extractors.huggingface.get_settings", return_value=_mock_settings()):
            result = await HuggingFaceExtractor().extract()

        assert isinstance(result, list)
        assert len(result) == 2
        for item in result:
            assert isinstance(item, ExtractedItem)

    @respx.mock
    async def test_items_have_correct_source(self):
        respx.get(API_URL).mock(return_value=httpx.Response(200, json=[_make_model()]))
        with patch("src.extractors.huggingface.get_settings", return_value=_mock_settings()):
            result = await HuggingFaceExtractor().extract()
        assert all(item.source == "huggingface" for item in result)

    @respx.mock
    async def test_items_sorted_by_downloads_descending(self):
        models = [
            _make_model("a/low", downloads=200),
            _make_model("a/high", downloads=90000),
            _make_model("a/mid", downloads=5000),
        ]
        respx.get(API_URL).mock(return_value=httpx.Response(200, json=models))
        with patch("src.extractors.huggingface.get_settings", return_value=_mock_settings()):
            result = await HuggingFaceExtractor().extract()
        scores = [item.score for item in result]
        assert scores == [90000, 5000, 200]

    @respx.mock
    async def test_filters_below_min_downloads(self):
        models = [
            _make_model("a/popular", downloads=5000),
            _make_model("a/unpopular", downloads=10),
        ]
        respx.get(API_URL).mock(return_value=httpx.Response(200, json=models))
        with patch("src.extractors.huggingface.get_settings", return_value=_mock_settings(hf_min_downloads=100)):
            result = await HuggingFaceExtractor().extract()
        assert len(result) == 1
        assert result[0].title == "a/popular"

    @respx.mock
    async def test_url_points_to_huggingface(self):
        respx.get(API_URL).mock(return_value=httpx.Response(200, json=[_make_model("org/my-model")]))
        with patch("src.extractors.huggingface.get_settings", return_value=_mock_settings()):
            result = await HuggingFaceExtractor().extract()
        assert result[0].url == "https://huggingface.co/org/my-model"

    @respx.mock
    async def test_metadata_has_expected_keys(self):
        model = _make_model(pipeline_tag="image-classification", downloads=9999, likes=500, tags=["pytorch", "vision"])
        respx.get(API_URL).mock(return_value=httpx.Response(200, json=[model]))
        with patch("src.extractors.huggingface.get_settings", return_value=_mock_settings()):
            result = await HuggingFaceExtractor().extract()
        meta = result[0].metadata
        assert meta["pipeline_tag"] == "image-classification"
        assert meta["downloads"] == 9999
        assert meta["likes"] == 500
        assert "pytorch" in meta["tags"]

    @respx.mock
    async def test_respects_max_items_per_source(self):
        models = [_make_model(f"org/model-{i}", downloads=1000 + i) for i in range(10)]
        respx.get(API_URL).mock(return_value=httpx.Response(200, json=models))
        with patch("src.extractors.huggingface.get_settings", return_value=_mock_settings(max_items_per_source=3)):
            result = await HuggingFaceExtractor().extract()
        assert len(result) <= 3

    @respx.mock
    async def test_handles_api_error(self):
        respx.get(API_URL).mock(return_value=httpx.Response(500, text="Internal Server Error"))
        with patch("src.extractors.huggingface.get_settings", return_value=_mock_settings()):
            result = await HuggingFaceExtractor().extract()
        assert result == []

    @respx.mock
    async def test_handles_network_error(self):
        respx.get(API_URL).mock(side_effect=httpx.ConnectError("connection failed"))
        with patch("src.extractors.huggingface.get_settings", return_value=_mock_settings()):
            result = await HuggingFaceExtractor().extract()
        assert result == []

    @respx.mock
    async def test_empty_response(self):
        respx.get(API_URL).mock(return_value=httpx.Response(200, json=[]))
        with patch("src.extractors.huggingface.get_settings", return_value=_mock_settings()):
            result = await HuggingFaceExtractor().extract()
        assert result == []

    @respx.mock
    async def test_deduplication_by_model_url(self):
        model = _make_model("org/same-model")
        respx.get(API_URL).mock(return_value=httpx.Response(200, json=[model, model]))
        with patch("src.extractors.huggingface.get_settings", return_value=_mock_settings()):
            result = await HuggingFaceExtractor().extract()
        assert len(result) == 1

    @respx.mock
    async def test_author_from_model_id(self):
        respx.get(API_URL).mock(return_value=httpx.Response(200, json=[_make_model("google/gemma-2b", author="google")]))
        with patch("src.extractors.huggingface.get_settings", return_value=_mock_settings()):
            result = await HuggingFaceExtractor().extract()
        assert result[0].author == "google"
```

### Step 3: Run tests to verify they fail

```bash
pytest tests/unit/test_huggingface_extractor.py -v
```

Expected: FAIL (module not found)

### Step 4: Implement the extractor

Create `src/extractors/huggingface.py`:

```python
"""HuggingFace Trending models extractor."""

from __future__ import annotations

from datetime import UTC, datetime

import httpx

from src.core.config import get_settings
from src.core.logging import get_logger
from src.core.metrics import (
    extractor_duration_seconds,
    extractor_errors_total,
    items_extracted_total,
)
from src.extractors.base import BaseExtractor, ExtractedItem

logger = get_logger(__name__)
API_URL = "https://huggingface.co/api/models"


class HuggingFaceExtractor(BaseExtractor):
    """Extracts trending AI models from HuggingFace Hub API."""

    @property
    def source_name(self) -> str:
        return "huggingface"

    async def extract(self, since_hours: int = 48) -> list[ExtractedItem]:
        settings = get_settings()
        min_downloads = settings.hf_min_downloads
        max_items = settings.max_items_per_source

        seen_urls: set[str] = set()
        items: list[ExtractedItem] = []

        with extractor_duration_seconds.labels(source=self.source_name).time():
            try:
                async with httpx.AsyncClient(
                    timeout=30,
                    headers={"User-Agent": "AI-News-Platform/1.0"},
                ) as client:
                    params = {
                        "sort": "trending",
                        "direction": "-1",
                        "limit": 50,
                    }
                    resp = await client.get(API_URL, params=params)
                    resp.raise_for_status()
                    models = resp.json()

                    for model in models:
                        downloads = model.get("downloads", 0)
                        if downloads < min_downloads:
                            continue

                        model_id = model.get("modelId") or model.get("id", "")
                        url = f"https://huggingface.co/{model_id}"

                        if url in seen_urls:
                            continue
                        seen_urls.add(url)

                        try:
                            last_mod = datetime.fromisoformat(
                                model.get("lastModified", "").replace("Z", "+00:00")
                            )
                        except (ValueError, AttributeError):
                            last_mod = datetime.now(tz=UTC)

                        items.append(
                            ExtractedItem(
                                title=model_id,
                                source=self.source_name,
                                url=url,
                                text=model_id,
                                author=model.get("author", model_id.split("/")[0] if "/" in model_id else "unknown"),
                                published_at=last_mod,
                                score=downloads,
                                metadata={
                                    "pipeline_tag": model.get("pipeline_tag"),
                                    "downloads": downloads,
                                    "likes": model.get("likes", 0),
                                    "tags": model.get("tags", []),
                                },
                            )
                        )
            except Exception as exc:
                logger.warning("huggingface_fetch_failed", error=str(exc))

        items.sort(key=lambda x: x.score or 0, reverse=True)
        items = items[:max_items]

        items_extracted_total.labels(source=self.source_name).inc(len(items))
        logger.info("extraction_complete", source=self.source_name, count=len(items))

        if not items:
            extractor_errors_total.labels(source=self.source_name).inc()

        return items
```

### Step 5: Run tests to verify they pass

```bash
pytest tests/unit/test_huggingface_extractor.py -v
```

Expected: ALL PASS

### Step 6: Register in pipeline

In `src/pipeline/pipeline.py`, add import:

```python
from src.extractors.huggingface import HuggingFaceExtractor
```

In `_get_extractors()`, add before `return extractors`:

```python
    if "huggingface" in enabled:
        extractors.append(HuggingFaceExtractor())
```

### Step 7: Run all extractor tests

```bash
pytest tests/unit/test_github_extractor.py tests/unit/test_huggingface_extractor.py -v
```

Expected: ALL PASS

### Step 8: Commit

```bash
git add src/extractors/huggingface.py src/core/config.py src/pipeline/pipeline.py tests/unit/test_huggingface_extractor.py
git commit -m "feat: add HuggingFace Trending extractor (M3)"
```

---

## Task 3: API — Add Trending Filter + Rate Limiting + CORS

**Files:**
- Modify: `src/api/routes/items.py` (add `trending` query param)
- Modify: `src/api/app.py` (add CORS + rate limit middleware)
- Modify: `src/core/config.py` (add `cors_origins`)
- Modify: `pyproject.toml` (add `slowapi`)
- Test: `tests/unit/test_api_routes.py` (add trending filter tests)

### Step 1: Add config field

In `src/core/config.py`, add in the API section (after `debug`):

```python
    cors_origins: str = "http://localhost:4200"
```

And the property:

```python
    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]
```

### Step 2: Add trending filter to items route

In `src/api/routes/items.py`, modify `list_items` to add the `trending` param:

```python
@router.get("", response_model=list[NewsItemResponse])
async def list_items(
    source: str | None = Query(None, description="Filter by source"),
    topic: str | None = Query(None, description="Filter by topic"),
    trending: bool | None = Query(None, description="Filter trending items only"),
    date_from: date | None = Query(None, description="Start date (inclusive)"),
    date_to: date | None = Query(None, description="End date (inclusive)"),
    limit: int = Query(50, ge=1, le=200, description="Max items to return"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    session: AsyncSession = Depends(get_session),
    _user: str = Depends(require_auth),
) -> list[NewsItemResponse]:
```

And add the filter logic after the existing filters:

```python
    if trending is not None:
        query = query.where(NewsItem.trending == trending)
```

### Step 3: Add slowapi dependency

In `pyproject.toml`, add to main dependencies:

```
    "slowapi~=0.1.0",
```

### Step 4: Add CORS + rate limiting to app

In `src/api/app.py`, add imports and middleware:

```python
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
```

After `app = FastAPI(...)`, add:

```python
# CORS
settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Rate limiting
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
```

In `src/api/routes/auth.py`, add rate limit to the token endpoint:

```python
from slowapi import Limiter
from slowapi.util import get_remote_address
from starlette.requests import Request

limiter = Limiter(key_func=get_remote_address)

@router.post("/api/auth/token")
@limiter.limit("5/minute")
async def login(request: Request, body: LoginRequest) -> TokenResponse:
```

**Note:** The `request: Request` parameter must be the first parameter for slowapi.

### Step 5: Run tests

```bash
pytest tests/unit/test_api_routes.py -v -k "trending or rate or cors"
```

### Step 6: Commit

```bash
git add src/api/routes/items.py src/api/routes/auth.py src/api/app.py src/core/config.py pyproject.toml
git commit -m "feat: add trending filter, rate limiting, CORS (M3)"
```

---

## Task 4: MCP Server

**Files:**
- Create: `src/mcp/client.py`
- Create: `src/mcp/server.py`
- Modify: `pyproject.toml` (add `mcp` SDK)
- Test: `tests/unit/test_mcp_client.py`
- Test: `tests/unit/test_mcp_server.py`

### Step 1: Add mcp dependency

In `pyproject.toml`, add to main dependencies:

```
    "mcp~=1.0",
```

Install:

```bash
pip install "mcp~=1.0"
```

### Step 2: Write client tests

Create `tests/unit/test_mcp_client.py`:

```python
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
```

### Step 3: Implement the client

Create `src/mcp/client.py`:

```python
"""HTTP client for the AI News Platform API."""

from __future__ import annotations

from datetime import UTC, datetime

import httpx


class APIClient:
    """Synchronous client that wraps the FastAPI REST API."""

    def __init__(self, base_url: str = "http://localhost:8000", password: str = ""):
        self.base_url = base_url.rstrip("/")
        self._http = httpx.Client(base_url=self.base_url, timeout=30)
        self.token = self._authenticate(password)

    def _authenticate(self, password: str) -> str:
        resp = self._http.post("/api/auth/token", json={"password": password})
        if resp.status_code != 200:
            raise RuntimeError(f"MCP authentication failed: {resp.status_code}")
        return resp.json()["access_token"]

    @property
    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.token}"}

    def search(
        self,
        q: str,
        topic: str | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
        limit: int = 10,
    ) -> list[dict]:
        params: dict[str, str | int] = {"q": q, "limit": limit}
        if topic:
            params["topic"] = topic
        if date_from:
            params["date_from"] = date_from
        if date_to:
            params["date_to"] = date_to
        resp = self._http.get("/api/search", params=params, headers=self._headers)
        resp.raise_for_status()
        return resp.json()

    def get_latest(self, topic: str | None = None, limit: int = 10) -> list[dict]:
        params: dict[str, str | int] = {"limit": limit}
        resp = self._http.get("/api/items/today", params=params, headers=self._headers)
        resp.raise_for_status()
        return resp.json()

    def get_trending(self) -> list[dict]:
        params = {"trending": "true", "limit": 20}
        resp = self._http.get("/api/items", params=params, headers=self._headers)
        resp.raise_for_status()
        return resp.json()

    def get_briefing(self, date: str | None = None) -> dict:
        if not date:
            date = datetime.now(tz=UTC).strftime("%Y-%m-%d")
        resp = self._http.get(f"/api/briefings/{date}", headers=self._headers)
        resp.raise_for_status()
        return resp.json()
```

### Step 4: Run client tests

```bash
pytest tests/unit/test_mcp_client.py -v
```

Expected: ALL PASS

### Step 5: Implement the MCP server

Create `src/mcp/server.py`:

```python
"""MCP server for AI News Platform.

Run with: python -m src.mcp.server
"""

from __future__ import annotations

import os
import sys

from mcp.server.fastmcp import FastMCP

from src.mcp.client import APIClient

mcp = FastMCP("AI News Platform")

_client: APIClient | None = None


def _get_client() -> APIClient:
    global _client
    if _client is None:
        base_url = os.environ.get("MCP_API_BASE_URL", "http://localhost:8000")
        password = os.environ.get("SHARED_PASSWORD", "")
        if not password:
            raise RuntimeError("SHARED_PASSWORD env var is required")
        _client = APIClient(base_url=base_url, password=password)
    return _client


def _format_items(items: list[dict]) -> str:
    if not items:
        return "No items found."
    lines: list[str] = []
    for i, item in enumerate(items, 1):
        source = item.get("source", "?")
        title = item.get("title", "Untitled")
        topic = item.get("topic", "")
        score = item.get("score")
        summary = item.get("summary", "")
        url = item.get("url", "")

        header = f"{i}. [{source}] {title}"
        if score:
            header += f" ({score} pts)"
        if topic:
            header += f" [{topic}]"

        lines.append(header)
        if summary:
            lines.append(f"   {summary}")
        if url:
            lines.append(f"   {url}")
        lines.append("")
    return "\n".join(lines)


@mcp.tool()
def search_news(
    query: str,
    topic: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    limit: int = 10,
) -> str:
    """Search AI news articles by keyword. Returns matching items with title, source, topic, summary, and URL."""
    client = _get_client()
    items = client.search(q=query, topic=topic, date_from=date_from, date_to=date_to, limit=limit)
    header = f"Found {len(items)} results for \"{query}\""
    if topic:
        header += f" (topic: {topic})"
    return f"{header}:\n\n{_format_items(items)}"


@mcp.tool()
def get_latest(topic: str | None = None, limit: int = 10) -> str:
    """Get the most recent AI news items from today."""
    client = _get_client()
    items = client.get_latest(topic=topic, limit=limit)
    return f"Latest {len(items)} items:\n\n{_format_items(items)}"


@mcp.tool()
def get_trending() -> str:
    """Get currently trending AI news items."""
    client = _get_client()
    items = client.get_trending()
    return f"Trending items ({len(items)}):\n\n{_format_items(items)}"


@mcp.tool()
def get_briefing(date: str | None = None) -> str:
    """Get the daily briefing summary with pipeline stats and top items."""
    client = _get_client()
    briefing = client.get_briefing(date=date)

    lines = [f"Daily Briefing — {briefing.get('date', 'today')}"]
    lines.append("=" * 40)

    for key in ("total_items", "items_extracted", "items_after_dedup", "items_filtered", "trending_count"):
        val = briefing.get(key)
        if val is not None:
            lines.append(f"  {key}: {val}")

    duration = briefing.get("duration_seconds")
    if duration:
        lines.append(f"  duration: {duration:.0f}s")

    items = briefing.get("items", [])
    if items:
        lines.append(f"\nTop {min(len(items), 5)} items:")
        lines.append(_format_items(items[:5]))

    return "\n".join(lines)


if __name__ == "__main__":
    mcp.run(transport="stdio")
```

### Step 6: Write server tests

Create `tests/unit/test_mcp_server.py`:

```python
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
        items = [{"source": "hackernews", "title": "AI News", "topic": "modelos", "score": 100, "summary": "Big news", "url": "https://example.com"}]
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
        client.search.assert_called_once_with(q="LLM", topic=None, date_from=None, date_to=None, limit=10)

    @patch("src.mcp.server._get_client")
    def test_passes_topic_filter(self, mock_get):
        client = _mock_client()
        client.search.return_value = []
        mock_get.return_value = client
        search_news(query="AI", topic="papers")
        client.search.assert_called_once_with(q="AI", topic="papers", date_from=None, date_to=None, limit=10)


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
        client.get_trending.return_value = [{"title": "Hot", "source": "hackernews", "trending": True}]
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
```

### Step 7: Run tests

```bash
pytest tests/unit/test_mcp_client.py tests/unit/test_mcp_server.py -v
```

Expected: ALL PASS

### Step 8: Commit

```bash
git add src/mcp/client.py src/mcp/server.py tests/unit/test_mcp_client.py tests/unit/test_mcp_server.py pyproject.toml
git commit -m "feat: add MCP server with 4 tools (M3)"
```

---

## Task 5: Frontend — Highcharts Analytics Page

**Files:**
- Create: `web/src/app/pages/analytics.ts`
- Modify: `web/src/app/app.routes.ts` (add route)
- Modify: `web/src/app/app.ts` (add nav link)
- Modify: `web/src/app/services/news.service.ts` (add getBriefings limit param)
- Install: `highcharts`, `highcharts-angular` npm packages

### Step 1: Install Highcharts

```bash
cd web && npm install highcharts highcharts-angular
```

### Step 2: Create the analytics page

Create `web/src/app/pages/analytics.ts`:

```typescript
import { Component, OnInit, inject, signal, computed } from '@angular/core';
import { CommonModule } from '@angular/common';
import { HighchartsChartModule } from 'highcharts-angular';
import * as Highcharts from 'highcharts';
import { NewsService } from '../services/news.service';
import { Briefing, NewsItem } from '../models/news-item';

@Component({
  selector: 'app-analytics',
  imports: [CommonModule, HighchartsChartModule],
  template: `
    <div class="analytics">
      @if (loading()) {
        <div class="loading">Cargando analytics...</div>
      }

      @if (error()) {
        <div class="error">{{ error() }}</div>
      }

      @if (!loading() && !error()) {
        <div class="chart-grid">
          <div class="chart-card">
            <h3>Items por dia (ultimos 14 dias)</h3>
            <highcharts-chart
              [Highcharts]="Highcharts"
              [options]="itemsPerDayOptions()"
              style="width: 100%; display: block;"
            />
          </div>

          <div class="chart-card">
            <h3>Distribucion por tema</h3>
            <highcharts-chart
              [Highcharts]="Highcharts"
              [options]="topicOptions()"
              style="width: 100%; display: block;"
            />
          </div>

          <div class="chart-card">
            <h3>Fuentes</h3>
            <highcharts-chart
              [Highcharts]="Highcharts"
              [options]="sourcesOptions()"
              style="width: 100%; display: block;"
            />
          </div>
        </div>
      }
    </div>
  `,
  styles: [`
    :host { display: block; }
    .loading, .error {
      padding: 24px;
      text-align: center;
      border-radius: 8px;
      margin: 20px 0;
    }
    .loading { background: #f1f5f9; color: #475569; }
    .error { background: #fef2f2; color: #dc2626; }
    .chart-grid {
      display: flex;
      flex-direction: column;
      gap: 20px;
    }
    .chart-card {
      border: 1px solid #e2e8f0;
      border-radius: 8px;
      padding: 16px;
    }
    .chart-card h3 {
      margin: 0 0 12px;
      font-size: 0.95rem;
      color: #475569;
      font-weight: 600;
    }
  `],
})
export class AnalyticsPage implements OnInit {
  private newsService = inject(NewsService);

  Highcharts = Highcharts;
  briefings = signal<Briefing[]>([]);
  todayItems = signal<NewsItem[]>([]);
  loading = signal(true);
  error = signal<string | null>(null);

  itemsPerDayOptions = computed<Highcharts.Options>(() => {
    const data = this.briefings()
      .map(b => ({ date: b.date, count: b.total_items ?? 0 }))
      .sort((a, b) => a.date.localeCompare(b.date));
    return {
      chart: { type: 'line', height: 280 },
      title: { text: undefined },
      xAxis: { categories: data.map(d => d.date), labels: { rotation: -45, style: { fontSize: '11px' } } },
      yAxis: { title: { text: 'Items' }, min: 0 },
      series: [{ type: 'line', name: 'Items', data: data.map(d => d.count), color: '#2563eb' }],
      credits: { enabled: false },
      legend: { enabled: false },
    };
  });

  topicOptions = computed<Highcharts.Options>(() => {
    const counts = new Map<string, number>();
    for (const item of this.todayItems()) {
      const topic = item.topic || 'sin tema';
      counts.set(topic, (counts.get(topic) || 0) + 1);
    }
    const data = Array.from(counts.entries()).map(([name, y]) => ({ name, y }));
    return {
      chart: { type: 'pie', height: 280 },
      title: { text: undefined },
      series: [{ type: 'pie', name: 'Items', data, innerSize: '50%' }],
      credits: { enabled: false },
      plotOptions: { pie: { dataLabels: { format: '{point.name}: {point.y}' } } },
    };
  });

  sourcesOptions = computed<Highcharts.Options>(() => {
    const counts = new Map<string, number>();
    for (const item of this.todayItems()) {
      counts.set(item.source, (counts.get(item.source) || 0) + 1);
    }
    const sourceColors: Record<string, string> = {
      hackernews: '#ff6600', arxiv: '#b31b1b', reddit: '#ff4500',
      rss: '#f59e0b', github: '#333333', huggingface: '#ffcc00',
    };
    const categories = Array.from(counts.keys());
    const data = categories.map(s => ({ y: counts.get(s) || 0, color: sourceColors[s] || '#94a3b8' }));
    return {
      chart: { type: 'bar', height: 280 },
      title: { text: undefined },
      xAxis: { categories, labels: { style: { fontSize: '12px' } } },
      yAxis: { title: { text: 'Items' }, min: 0 },
      series: [{ type: 'bar', name: 'Items', data }],
      credits: { enabled: false },
      legend: { enabled: false },
    };
  });

  ngOnInit() {
    this.newsService.getBriefings().subscribe({
      next: (briefings) => {
        this.briefings.set(briefings.slice(0, 14));
        const today = new Date().toISOString().slice(0, 10);
        const todayBriefing = briefings.find(b => b.date === today);
        if (todayBriefing?.items) {
          this.todayItems.set(todayBriefing.items);
          this.loading.set(false);
        } else {
          this.newsService.getTodayItems().subscribe({
            next: (items) => { this.todayItems.set(items); this.loading.set(false); },
            error: () => this.loading.set(false),
          });
        }
      },
      error: (err) => {
        this.error.set('Error al cargar analytics.');
        this.loading.set(false);
      },
    });
  }
}
```

### Step 3: Add route

In `web/src/app/app.routes.ts`, add import and route:

```typescript
import { AnalyticsPage } from './pages/analytics';
```

Add before the catch-all redirects:

```typescript
  { path: 'analytics', component: AnalyticsPage, canActivate: [authGuard] },
```

### Step 4: Add nav link

In `web/src/app/app.ts`, add the Analytics link in the nav-links div, after Buscar:

```html
          <a routerLink="/analytics" routerLinkActive="active">Analytics</a>
```

### Step 5: Build and test

```bash
cd web && npx ng build
```

### Step 6: Commit

```bash
git add web/src/app/pages/analytics.ts web/src/app/app.routes.ts web/src/app/app.ts web/package.json web/package-lock.json
git commit -m "feat: add Highcharts analytics page (M3)"
```

---

## Task 6: Frontend — Responsive Hamburger Nav

**Files:**
- Modify: `web/src/app/app.ts` (add hamburger toggle)

### Step 1: Update app component

In `web/src/app/app.ts`, add a `menuOpen` signal and toggle:

```typescript
export class App {
  private auth = inject(AuthService);
  private router = inject(Router);

  menuOpen = signal(false);

  showNav(): boolean {
    return this.auth.isAuthenticated() && !this.router.url.includes('/login');
  }

  toggleMenu() {
    this.menuOpen.update(v => !v);
  }

  onLogout() {
    this.auth.logout();
    this.router.navigate(['/login']);
  }

  onNavClick() {
    this.menuOpen.set(false);
  }
}
```

Update the template nav-links to include hamburger button and conditional display:

```html
    @if (showNav()) {
      <nav class="navbar">
        <div class="nav-brand">AI News Platform</div>
        <button class="hamburger" (click)="toggleMenu()">☰</button>
        <div class="nav-links" [class.open]="menuOpen()">
          <a routerLink="/dashboard" routerLinkActive="active" (click)="onNavClick()">Dashboard</a>
          <a routerLink="/archive" routerLinkActive="active" (click)="onNavClick()">Archivo</a>
          <a routerLink="/search" routerLinkActive="active" (click)="onNavClick()">Buscar</a>
          <a routerLink="/analytics" routerLinkActive="active" (click)="onNavClick()">Analytics</a>
          <button class="logout-btn" (click)="onLogout()">Salir</button>
        </div>
      </nav>
    }
```

Add styles for hamburger:

```css
    .hamburger {
      display: none;
      background: none;
      border: none;
      color: white;
      font-size: 1.4rem;
      cursor: pointer;
      padding: 4px 8px;
    }
    @media (max-width: 640px) {
      .hamburger { display: block; }
      .nav-links {
        display: none;
        position: absolute;
        top: 48px;
        left: 0;
        right: 0;
        background: #1e293b;
        flex-direction: column;
        padding: 8px 12px;
        gap: 4px;
      }
      .nav-links.open { display: flex; }
      .nav-links a { padding: 8px 12px; }
    }
```

### Step 2: Build and test

```bash
cd web && npx ng build
```

### Step 3: Commit

```bash
git add web/src/app/app.ts
git commit -m "feat: add responsive hamburger nav (M3)"
```

---

## Task 7: E2E Tests for Analytics + Navigation Update

**Files:**
- Create: `tests/e2e/test_analytics.py`
- Modify: `tests/e2e/conftest.py` (add briefings mock route)
- Modify: `tests/e2e/test_navigation.py` (add Analytics link test)

### Step 1: Update conftest mock routes

In `tests/e2e/conftest.py`, add a briefings list mock. In `setup_mock_routes`, add:

```python
    def handle_briefings_list(route):
        route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps([_briefing]),
        )

    page.route("**/api/briefings", handle_briefings_list)
```

**Important:** Register `**/api/briefings` BEFORE `**/api/briefings/*` so the more specific pattern takes priority (Playwright LIFO ordering).

### Step 2: Create analytics E2E tests

Create `tests/e2e/test_analytics.py`:

```python
"""E2E tests for the analytics page."""

from __future__ import annotations

import pytest
from playwright.sync_api import Page, expect

pytestmark = pytest.mark.e2e


def test_analytics_page_renders_charts(authed_page: Page, base_url: str):
    authed_page.goto(base_url + "/analytics")
    expect(authed_page.locator("text=Items por dia")).to_be_visible()
    expect(authed_page.locator("text=Distribucion por tema")).to_be_visible()
    expect(authed_page.locator("text=Fuentes")).to_be_visible()


def test_analytics_accessible_from_nav(authed_page: Page, base_url: str):
    authed_page.goto(base_url + "/dashboard")
    authed_page.click("a[href='/analytics']")
    authed_page.wait_for_url("**/analytics")
    expect(authed_page.locator("text=Items por dia")).to_be_visible()
```

### Step 3: Update navigation tests

In `tests/e2e/test_navigation.py`, update `test_navbar_visible_on_authenticated_pages` to include:

```python
    expect(authed_page.locator("text=Analytics")).to_be_visible()
```

### Step 4: Rebuild Angular and run E2E tests

```bash
cd web && npx ng build
cd .. && pytest tests/e2e/ -v
```

Expected: ALL PASS

### Step 5: Commit

```bash
git add tests/e2e/test_analytics.py tests/e2e/conftest.py tests/e2e/test_navigation.py
git commit -m "test: add analytics E2E tests (M3)"
```

---

## Task 8: Final Verification

### Step 1: Run full test suite

```bash
pytest tests/e2e/ -v
pytest tests/unit/test_github_extractor.py tests/unit/test_huggingface_extractor.py tests/unit/test_mcp_client.py tests/unit/test_mcp_server.py -v
```

### Step 2: Lint and type check

```bash
ruff check src/extractors/github.py src/extractors/huggingface.py src/mcp/client.py src/mcp/server.py
ruff format --check src/
pyright src/extractors/github.py src/extractors/huggingface.py src/mcp/client.py src/mcp/server.py
```

### Step 3: Verify the MCP server starts

```bash
echo '{}' | SHARED_PASSWORD=test python -m src.mcp.server 2>&1 | head -5
```

(Will fail to connect but should start without import errors)

### Step 4: Commit any fixes and tag

```bash
git tag -a m3-complete -m "Milestone 3: New sources + MCP + Polish"
```
