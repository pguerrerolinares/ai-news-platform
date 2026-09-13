# WebScraperExtractor Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a new `WebScraperExtractor` that uses Crawl4AI to scrape websites without APIs/RSS, integrated into the existing pipeline and scheduler.

**Architecture:** New `BaseExtractor` implementation using Crawl4AI's `AsyncWebCrawler` as an in-process library. Two-phase approach: discover article links from index pages, then scrape new articles for full markdown content. Registered as source `"webscraper"` in Tier 2 scheduling (every 60 min).

**Tech Stack:** Crawl4AI (~=0.8), Python 3.12+, async, existing pipeline infrastructure.

**Design doc:** `docs/plans/2026-03-02-webscraper-crawl4ai-design.md`

---

### Task 1: Add crawl4ai dependency

**Files:**
- Modify: `pyproject.toml:10-44`

**Step 1: Add crawl4ai to dependencies**

In `pyproject.toml`, add `crawl4ai` to the `dependencies` list, after the RSS parsing entry (line 33):

```toml
    # Web scraping
    "crawl4ai~=0.8",
```

**Step 2: Install the dependency**

Run: `pip install -e ".[dev]"`
Expected: crawl4ai installs successfully with Playwright/Chromium

**Step 3: Install Playwright browsers**

Run: `playwright install chromium`
Expected: Chromium browser downloaded for Crawl4AI's headless rendering

**Step 4: Commit**

```bash
git add pyproject.toml
git commit -m "feat: add crawl4ai dependency for web scraping extractor"
```

---

### Task 2: Add webscraper configuration to Settings

**Files:**
- Modify: `src/core/config.py:82-94` (after RSS/GitHub/HuggingFace settings)

**Step 1: Write the failing test**

Create `tests/unit/test_webscraper_config.py`:

```python
"""Tests for webscraper configuration in Settings."""

from __future__ import annotations

from src.core.config import Settings


class TestWebScraperSettings:
    """Verify webscraper settings parse correctly."""

    def test_default_webscraper_urls_is_empty(self):
        settings = Settings(webscraper_urls=[])
        assert settings.webscraper_urls == []

    def test_webscraper_urls_from_list(self):
        urls = ["https://anthropic.com/research", "https://deepmind.google/research/"]
        settings = Settings(webscraper_urls=urls)
        assert settings.webscraper_urls == urls

    def test_webscraper_max_concurrent_default(self):
        settings = Settings()
        assert settings.webscraper_max_concurrent == 3

    def test_webscraper_page_timeout_default(self):
        settings = Settings()
        assert settings.webscraper_page_timeout == 30
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_webscraper_config.py -v`
Expected: FAIL — `webscraper_urls`, `webscraper_max_concurrent`, `webscraper_page_timeout` don't exist on Settings

**Step 3: Add settings fields to config.py**

In `src/core/config.py`, after the HuggingFace settings (line 94), add:

```python
    # Web scraper
    webscraper_urls: list[str] = []
    webscraper_max_concurrent: int = 3
    webscraper_page_timeout: int = 30  # seconds
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_webscraper_config.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/core/config.py tests/unit/test_webscraper_config.py
git commit -m "feat: add webscraper settings to config (urls, max_concurrent, page_timeout)"
```

---

### Task 3: Add "webscraper" to VALID_SOURCES

**Files:**
- Modify: `src/core/models.py:45-52`

**Step 1: Write the failing test**

Create `tests/unit/test_webscraper_source.py`:

```python
"""Tests for webscraper source registration."""

from __future__ import annotations

from src.core.models import VALID_SOURCES


class TestWebScraperSource:
    def test_webscraper_in_valid_sources(self):
        assert "webscraper" in VALID_SOURCES
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_webscraper_source.py -v`
Expected: FAIL — "webscraper" not in VALID_SOURCES

**Step 3: Add webscraper to VALID_SOURCES**

In `src/core/models.py`, modify `VALID_SOURCES` (line 45-52):

```python
VALID_SOURCES = (
    "hackernews",
    "arxiv",
    "reddit",
    "rss",
    "github",
    "huggingface",
    "webscraper",
)
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_webscraper_source.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/core/models.py tests/unit/test_webscraper_source.py
git commit -m "feat: add 'webscraper' to VALID_SOURCES"
```

---

### Task 4: Create WebScraperExtractor — core implementation with tests

This is the main task. We build the extractor using TDD.

**Files:**
- Create: `src/extractors/webscraper.py`
- Create: `tests/unit/test_webscraper_extractor.py`

**Step 1: Write the test file with all test cases**

Create `tests/unit/test_webscraper_extractor.py`:

```python
"""Tests for src.extractors.webscraper -- WebScraperExtractor."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.core.config import Settings
from src.extractors.base import ExtractedItem
from src.extractors.webscraper import WebScraperExtractor, _filter_article_links


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _mock_settings(**overrides):
    """Return a minimal Settings-like object for webscraper tests."""
    defaults = {
        "webscraper_urls": ["https://example.com/blog"],
        "webscraper_max_concurrent": 2,
        "webscraper_page_timeout": 10,
        "max_items_per_source": 50,
        "enabled_sources": "webscraper",
        "telegram_bot_token": "",
        "telegram_chat_id": "",
        "telegram_alerts_enabled": False,
    }
    defaults.update(overrides)
    return Settings(**defaults)


@dataclass
class FakeCrawlResult:
    """Mimics Crawl4AI's CrawlResult."""

    success: bool
    markdown: str
    links: dict  # {"internal": [{"href": "...", "text": "..."}], "external": [...]}
    metadata: dict | None = None


# ---------------------------------------------------------------------------
# Tests: source_name
# ---------------------------------------------------------------------------
class TestSourceName:
    def test_source_name_returns_webscraper(self):
        extractor = WebScraperExtractor()
        assert extractor.source_name == "webscraper"


# ---------------------------------------------------------------------------
# Tests: _filter_article_links
# ---------------------------------------------------------------------------
class TestFilterArticleLinks:
    def test_filters_same_domain_only(self):
        links = [
            {"href": "https://example.com/blog/article-1", "text": "Article 1"},
            {"href": "https://other.com/page", "text": "External"},
        ]
        result = _filter_article_links(links, "https://example.com/blog")
        assert len(result) == 1
        assert result[0] == "https://example.com/blog/article-1"

    def test_filters_shallow_paths(self):
        """Root path and base path should be excluded."""
        links = [
            {"href": "https://example.com/", "text": "Home"},
            {"href": "https://example.com/blog", "text": "Blog index"},
            {"href": "https://example.com/blog/my-post", "text": "Article"},
        ]
        result = _filter_article_links(links, "https://example.com/blog")
        assert result == ["https://example.com/blog/my-post"]

    def test_deduplicates_links(self):
        links = [
            {"href": "https://example.com/blog/post-1", "text": "Post 1"},
            {"href": "https://example.com/blog/post-1", "text": "Post 1 again"},
        ]
        result = _filter_article_links(links, "https://example.com/blog")
        assert len(result) == 1

    def test_filters_non_content_paths(self):
        """Paths like /about, /contact, /careers should be excluded."""
        links = [
            {"href": "https://example.com/about", "text": "About"},
            {"href": "https://example.com/careers", "text": "Careers"},
            {"href": "https://example.com/contact", "text": "Contact"},
            {"href": "https://example.com/blog/real-post", "text": "Real Post"},
        ]
        result = _filter_article_links(links, "https://example.com/blog")
        assert result == ["https://example.com/blog/real-post"]

    def test_handles_empty_links(self):
        result = _filter_article_links([], "https://example.com/blog")
        assert result == []

    def test_handles_links_without_href(self):
        links = [{"text": "No href"}, {"href": "", "text": "Empty href"}]
        result = _filter_article_links(links, "https://example.com/blog")
        assert result == []


# ---------------------------------------------------------------------------
# Tests: extract()
# ---------------------------------------------------------------------------
class TestExtract:
    @patch("src.extractors.webscraper.get_settings")
    async def test_extract_returns_empty_when_no_urls_configured(self, mock_settings):
        mock_settings.return_value = _mock_settings(webscraper_urls=[])
        extractor = WebScraperExtractor()
        result = await extractor.extract()
        assert result == []

    @patch("src.extractors.webscraper.get_settings")
    async def test_extract_returns_extracted_items(self, mock_settings):
        mock_settings.return_value = _mock_settings()

        # Mock the index page crawl (returns links)
        index_result = FakeCrawlResult(
            success=True,
            markdown="# Blog Index",
            links={
                "internal": [
                    {"href": "https://example.com/blog/post-1", "text": "Post 1"},
                    {"href": "https://example.com/blog/post-2", "text": "Post 2"},
                ],
                "external": [],
            },
        )
        # Mock individual article crawls
        article_result_1 = FakeCrawlResult(
            success=True,
            markdown="# Post 1\n\nThis is the full content of post 1.",
            links={"internal": [], "external": []},
            metadata={"title": "Post 1"},
        )
        article_result_2 = FakeCrawlResult(
            success=True,
            markdown="# Post 2\n\nThis is the full content of post 2.",
            links={"internal": [], "external": []},
            metadata={"title": "Post 2"},
        )

        mock_crawler = AsyncMock()
        mock_crawler.arun = AsyncMock(side_effect=[index_result, article_result_1, article_result_2])
        mock_crawler.__aenter__ = AsyncMock(return_value=mock_crawler)
        mock_crawler.__aexit__ = AsyncMock(return_value=False)

        with patch("src.extractors.webscraper.AsyncWebCrawler", return_value=mock_crawler):
            extractor = WebScraperExtractor()
            result = await extractor.extract()

        assert len(result) == 2
        assert all(isinstance(item, ExtractedItem) for item in result)
        assert all(item.source == "webscraper" for item in result)

    @patch("src.extractors.webscraper.get_settings")
    async def test_extract_handles_failed_index_crawl(self, mock_settings):
        mock_settings.return_value = _mock_settings()

        index_result = FakeCrawlResult(
            success=False,
            markdown="",
            links={"internal": [], "external": []},
        )

        mock_crawler = AsyncMock()
        mock_crawler.arun = AsyncMock(return_value=index_result)
        mock_crawler.__aenter__ = AsyncMock(return_value=mock_crawler)
        mock_crawler.__aexit__ = AsyncMock(return_value=False)

        with patch("src.extractors.webscraper.AsyncWebCrawler", return_value=mock_crawler):
            extractor = WebScraperExtractor()
            result = await extractor.extract()

        assert result == []

    @patch("src.extractors.webscraper.get_settings")
    async def test_extract_skips_failed_article_crawl(self, mock_settings):
        mock_settings.return_value = _mock_settings()

        index_result = FakeCrawlResult(
            success=True,
            markdown="# Blog",
            links={
                "internal": [
                    {"href": "https://example.com/blog/ok", "text": "OK"},
                    {"href": "https://example.com/blog/fail", "text": "Fail"},
                ],
                "external": [],
            },
        )
        ok_result = FakeCrawlResult(
            success=True,
            markdown="# OK Post\n\nContent here.",
            links={"internal": [], "external": []},
            metadata={"title": "OK Post"},
        )
        fail_result = FakeCrawlResult(
            success=False,
            markdown="",
            links={"internal": [], "external": []},
        )

        mock_crawler = AsyncMock()
        mock_crawler.arun = AsyncMock(side_effect=[index_result, ok_result, fail_result])
        mock_crawler.__aenter__ = AsyncMock(return_value=mock_crawler)
        mock_crawler.__aexit__ = AsyncMock(return_value=False)

        with patch("src.extractors.webscraper.AsyncWebCrawler", return_value=mock_crawler):
            extractor = WebScraperExtractor()
            result = await extractor.extract()

        assert len(result) == 1
        assert result[0].url == "https://example.com/blog/ok"

    @patch("src.extractors.webscraper.get_settings")
    async def test_extract_respects_max_items_per_source(self, mock_settings):
        mock_settings.return_value = _mock_settings(max_items_per_source=1)

        links = [
            {"href": f"https://example.com/blog/post-{i}", "text": f"Post {i}"}
            for i in range(5)
        ]
        index_result = FakeCrawlResult(
            success=True,
            markdown="# Blog",
            links={"internal": links, "external": []},
        )
        article_result = FakeCrawlResult(
            success=True,
            markdown="# Post\n\nContent.",
            links={"internal": [], "external": []},
            metadata={"title": "Post"},
        )

        mock_crawler = AsyncMock()
        mock_crawler.arun = AsyncMock(side_effect=[index_result, article_result])
        mock_crawler.__aenter__ = AsyncMock(return_value=mock_crawler)
        mock_crawler.__aexit__ = AsyncMock(return_value=False)

        with patch("src.extractors.webscraper.AsyncWebCrawler", return_value=mock_crawler):
            extractor = WebScraperExtractor()
            result = await extractor.extract()

        assert len(result) <= 1

    @patch("src.extractors.webscraper.get_settings")
    async def test_extract_maps_fields_correctly(self, mock_settings):
        mock_settings.return_value = _mock_settings()

        index_result = FakeCrawlResult(
            success=True,
            markdown="# Blog",
            links={
                "internal": [
                    {"href": "https://example.com/blog/test-post", "text": "Test Post"},
                ],
                "external": [],
            },
        )
        article_result = FakeCrawlResult(
            success=True,
            markdown="# Test Post\n\nFull article content here with details.",
            links={"internal": [], "external": []},
            metadata={"title": "Test Post"},
        )

        mock_crawler = AsyncMock()
        mock_crawler.arun = AsyncMock(side_effect=[index_result, article_result])
        mock_crawler.__aenter__ = AsyncMock(return_value=mock_crawler)
        mock_crawler.__aexit__ = AsyncMock(return_value=False)

        with patch("src.extractors.webscraper.AsyncWebCrawler", return_value=mock_crawler):
            extractor = WebScraperExtractor()
            result = await extractor.extract()

        assert len(result) == 1
        item = result[0]
        assert item.title == "Test Post"
        assert item.source == "webscraper"
        assert item.url == "https://example.com/blog/test-post"
        assert "Full article content" in item.text
        assert item.score == 0
        assert item.metadata["domain"] == "example.com"

    @patch("src.extractors.webscraper.get_settings")
    async def test_extract_handles_crawler_exception(self, mock_settings):
        mock_settings.return_value = _mock_settings()

        mock_crawler = AsyncMock()
        mock_crawler.arun = AsyncMock(side_effect=RuntimeError("Chromium crashed"))
        mock_crawler.__aenter__ = AsyncMock(return_value=mock_crawler)
        mock_crawler.__aexit__ = AsyncMock(return_value=False)

        with patch("src.extractors.webscraper.AsyncWebCrawler", return_value=mock_crawler):
            extractor = WebScraperExtractor()
            with pytest.raises(RuntimeError, match="Chromium crashed"):
                await extractor.extract()
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/test_webscraper_extractor.py -v`
Expected: FAIL — `src.extractors.webscraper` module doesn't exist

**Step 3: Create the WebScraperExtractor implementation**

Create `src/extractors/webscraper.py`:

```python
"""Web scraper extractor using Crawl4AI for sites without APIs or RSS feeds.

Two-phase approach:
1. Discover article links from configured index pages
2. Scrape new articles for full markdown content

Uses AsyncWebCrawler (Crawl4AI) for headless browser rendering.
"""

from __future__ import annotations

import re
from urllib.parse import urlparse

from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig

from src.core.config import get_settings
from src.core.logging import get_logger
from src.core.metrics import (
    extractor_duration_seconds,
    extractor_errors_total,
    items_extracted_total,
)
from src.extractors.base import BaseExtractor, ExtractedItem

logger = get_logger(__name__)

# Paths that are unlikely to be article content
_NON_CONTENT_PATHS = frozenset({
    "about", "contact", "careers", "login", "signup", "register",
    "privacy", "terms", "faq", "help", "search", "tag", "category",
    "author", "page", "feed", "rss", "sitemap", "api", "admin",
    "static", "assets", "images", "css", "js",
})


def _filter_article_links(links: list[dict], index_url: str) -> list[str]:
    """Filter discovered links to keep only likely article URLs.

    Rules:
    - Same domain as the index page
    - Path depth > base path (not the index page itself)
    - Not in the non-content paths blocklist
    - Deduplicated
    """
    parsed_index = urlparse(index_url)
    index_domain = parsed_index.netloc
    index_path = parsed_index.path.rstrip("/")

    seen: set[str] = set()
    result: list[str] = []

    for link in links:
        href = link.get("href", "")
        if not href:
            continue

        parsed = urlparse(href)

        # Same domain only
        if parsed.netloc != index_domain:
            continue

        path = parsed.path.rstrip("/")

        # Must be deeper than index path or root
        if not path or path == index_path or path == "/":
            continue

        # Check first path segment against blocklist
        segments = [s for s in path.split("/") if s]
        if segments and segments[0].lower() in _NON_CONTENT_PATHS:
            continue

        # Deduplicate
        clean_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
        if clean_url in seen:
            continue
        seen.add(clean_url)

        result.append(clean_url)

    return result


def _extract_title_from_markdown(markdown: str, metadata: dict | None) -> str:
    """Extract the article title from metadata or first markdown heading."""
    if metadata and metadata.get("title"):
        return metadata["title"]

    # Try first H1 heading
    match = re.search(r"^#\s+(.+)$", markdown, re.MULTILINE)
    if match:
        return match.group(1).strip()

    # Fallback: first non-empty line
    for line in markdown.split("\n"):
        line = line.strip()
        if line:
            return line[:200]

    return "Untitled"


class WebScraperExtractor(BaseExtractor):
    """Extracts articles from websites using Crawl4AI headless browser."""

    @property
    def source_name(self) -> str:
        return "webscraper"

    async def extract(self, since_hours: int = 24) -> list[ExtractedItem]:
        """Extract articles from configured web pages.

        Phase 1: Crawl each index page to discover article links.
        Phase 2: Scrape each new article URL for full content.
        """
        settings = get_settings()
        target_urls = settings.webscraper_urls

        if not target_urls:
            logger.info("webscraper_no_urls_configured")
            return []

        max_items = settings.max_items_per_source
        timeout = settings.webscraper_page_timeout * 1000  # Crawl4AI uses ms

        browser_config = BrowserConfig(headless=True)
        crawl_config = CrawlerRunConfig(page_timeout=timeout)

        all_items: list[ExtractedItem] = []

        with extractor_duration_seconds.labels(source=self.source_name).time():
            async with AsyncWebCrawler(config=browser_config) as crawler:
                for index_url in target_urls:
                    try:
                        page_items = await self._scrape_index_page(
                            crawler, index_url, crawl_config, max_items - len(all_items),
                        )
                        all_items.extend(page_items)
                    except Exception as exc:
                        logger.warning(
                            "webscraper_index_failed",
                            index_url=index_url,
                            error=str(exc),
                        )
                        continue

                    if len(all_items) >= max_items:
                        break

        all_items = all_items[:max_items]
        items_extracted_total.labels(source=self.source_name).inc(len(all_items))

        logger.info(
            "extraction_complete",
            source=self.source_name,
            count=len(all_items),
            index_pages=len(target_urls),
        )

        if not all_items:
            extractor_errors_total.labels(source=self.source_name).inc()

        return all_items

    async def _scrape_index_page(
        self,
        crawler: AsyncWebCrawler,
        index_url: str,
        crawl_config: CrawlerRunConfig,
        remaining_budget: int,
    ) -> list[ExtractedItem]:
        """Discover and scrape articles from a single index page."""
        # Phase 1: Discover links
        index_result = await crawler.arun(url=index_url, config=crawl_config)

        if not index_result.success:
            logger.warning("webscraper_index_crawl_failed", index_url=index_url)
            return []

        internal_links = index_result.links.get("internal", [])
        article_urls = _filter_article_links(internal_links, index_url)

        if not article_urls:
            logger.info("webscraper_no_articles_found", index_url=index_url)
            return []

        # Limit to remaining budget
        article_urls = article_urls[:remaining_budget]

        # Phase 2: Scrape each article
        parsed_index = urlparse(index_url)
        domain = parsed_index.netloc
        items: list[ExtractedItem] = []

        for article_url in article_urls:
            try:
                article_result = await crawler.arun(url=article_url, config=crawl_config)

                if not article_result.success:
                    logger.warning(
                        "webscraper_article_crawl_failed", article_url=article_url,
                    )
                    continue

                markdown = article_result.markdown or ""
                if not markdown.strip():
                    continue

                title = _extract_title_from_markdown(markdown, article_result.metadata)
                word_count = len(markdown.split())

                items.append(
                    ExtractedItem(
                        title=title,
                        source=self.source_name,
                        url=article_url,
                        text=markdown,
                        author=domain,
                        published_at=None,
                        score=0,
                        metadata={
                            "domain": domain,
                            "scraper_source": domain,
                            "word_count": word_count,
                            "index_url": index_url,
                        },
                    )
                )
            except Exception as exc:
                logger.warning(
                    "webscraper_article_failed",
                    article_url=article_url,
                    error=str(exc),
                )
                continue

        logger.info(
            "webscraper_index_done",
            index_url=index_url,
            discovered=len(article_urls),
            scraped=len(items),
        )

        return items
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/unit/test_webscraper_extractor.py -v`
Expected: All tests PASS

**Step 5: Run linters**

Run: `ruff check src/extractors/webscraper.py tests/unit/test_webscraper_extractor.py && ruff format --check src/extractors/webscraper.py tests/unit/test_webscraper_extractor.py`
Expected: No errors. Fix any issues before committing.

**Step 6: Commit**

```bash
git add src/extractors/webscraper.py tests/unit/test_webscraper_extractor.py
git commit -m "feat: add WebScraperExtractor with Crawl4AI for web scraping"
```

---

### Task 5: Register WebScraperExtractor in the pipeline

**Files:**
- Modify: `src/pipeline/pipeline.py:37-84`

**Step 1: Add import**

In `src/pipeline/pipeline.py`, after the HuggingFace import (line 41), add:

```python
from src.extractors.webscraper import WebScraperExtractor
```

**Step 2: Add webscraper to `_get_extractors()`**

In the `_get_extractors()` function (after line 82), add:

```python
    if "webscraper" in enabled:
        extractors.append(WebScraperExtractor())
```

**Step 3: Run existing pipeline tests to verify no regression**

Run: `pytest tests/unit/test_pipeline.py -v`
Expected: All existing tests PASS

**Step 4: Commit**

```bash
git add src/pipeline/pipeline.py
git commit -m "feat: register WebScraperExtractor in pipeline _get_extractors()"
```

---

### Task 6: Add webscraper to scheduler Tier 2

**Files:**
- Modify: `src/pipeline/scheduler.py:78-85`

**Step 1: Update Tier 2 job to include webscraper**

In `src/pipeline/scheduler.py`, modify the Tier 2 job (lines 79-85). Change the sources list and job ID:

```python
    # Tier 2: RSS + GitHub + HuggingFace + WebScraper (every 60 min, extract last 3h)
    scheduler.add_job(
        run_scheduled_pipeline,
        IntervalTrigger(minutes=settings.rss_poll_interval_minutes),
        id="tier2_rss_gh_hf_ws",
        kwargs={"sources": ["rss", "github", "huggingface", "webscraper"], "since_hours": 3},
        replace_existing=True,
    )
```

**Step 2: Run scheduler tests**

Run: `pytest tests/unit/test_scheduler.py -v`
Expected: PASS (or update tests if they assert on job IDs/source lists)

**Step 3: Commit**

```bash
git add src/pipeline/scheduler.py
git commit -m "feat: add webscraper to scheduler Tier 2 (every 60 min)"
```

---

### Task 7: Run full quality checks

**Step 1: Run ruff linter**

Run: `ruff check .`
Expected: No errors

**Step 2: Run ruff formatter**

Run: `ruff format --check .`
Expected: No formatting issues

**Step 3: Run pyright**

Run: `pyright .`
Expected: No new errors (existing warnings acceptable)

**Step 4: Run full test suite**

Run: `pytest tests/ -x --timeout=30`
Expected: All tests PASS

**Step 5: Fix any issues found, then commit**

If fixes were needed:
```bash
git add -A
git commit -m "fix: address lint/type/test issues from webscraper integration"
```

---

### Task 8: Update AGENTS.md documentation

**Files:**
- Modify: `AGENTS.md`

**Step 1: Add WebScraperExtractor to the extractors section**

Add the following entry alongside the other extractors:

```markdown
- `src/extractors/webscraper.py` — WebScraperExtractor: Crawl4AI-based scraper for sites without APIs/RSS. Two-phase: discover links from index pages → scrape articles for full markdown. Source: `"webscraper"`. Tier 2 scheduling (every 60 min).
```

**Step 2: Update the sources table if one exists**

Add webscraper to any table listing sources, with: Schedule=60min, Type=Web scraping (Crawl4AI).

**Step 3: Commit**

```bash
git add AGENTS.md
git commit -m "docs: add WebScraperExtractor to AGENTS.md"
```

---

## Summary of tasks

| # | Task | Files | Est. |
|---|------|-------|------|
| 1 | Add crawl4ai dependency | `pyproject.toml` | 2 min |
| 2 | Add webscraper settings | `config.py`, test | 5 min |
| 3 | Add to VALID_SOURCES | `models.py`, test | 3 min |
| 4 | Create WebScraperExtractor + tests | `webscraper.py`, test | 15 min |
| 5 | Register in pipeline | `pipeline.py` | 3 min |
| 6 | Add to scheduler Tier 2 | `scheduler.py` | 3 min |
| 7 | Full quality checks | — | 5 min |
| 8 | Update docs | `AGENTS.md` | 3 min |
