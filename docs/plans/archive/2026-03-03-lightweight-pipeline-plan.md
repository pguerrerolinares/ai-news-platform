# Lightweight Pipeline Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Reduce VPS resource consumption by replacing Crawl4AI with httpx+readability-lxml, splitting pipeline.py into 5 composable stages, and creating separate Dockerfiles for API and pipeline.

**Architecture:** Three sequential changes on a single branch. Phase 1 swaps the web scraping engine (crawl4ai → httpx+readability). Phase 2 extracts pipeline.py's inline steps into 5 stage modules with a thin orchestrator. Phase 3 splits dependencies and Dockerfiles so the API image drops from ~1.2GB to ~300MB.

**Tech Stack:** httpx (existing), readability-lxml (new ~200KB), Python 3.12+, FastAPI, SQLAlchemy async, APScheduler.

**Design doc:** `docs/plans/2026-03-03-lightweight-pipeline-design.md`

---

## Phase 1: Replace Crawl4AI with httpx + readability-lxml

### Task 1: Swap dependencies in pyproject.toml

**Files:**
- Modify: `pyproject.toml:34-35`

**Step 1: Replace crawl4ai with readability-lxml**

In `pyproject.toml`, change:

```toml
    # Web scraping
    "crawl4ai~=0.8",
```

To:

```toml
    # Web scraping (lightweight: no Chromium)
    "readability-lxml~=0.8",
```

**Step 2: Install the new dependency**

Run: `pip install -e ".[dev]"`
Expected: readability-lxml installs successfully. crawl4ai is no longer in the dependency tree.

**Step 3: Verify crawl4ai is gone**

Run: `pip show crawl4ai 2>&1 || echo "crawl4ai not installed (good)"`
Expected: "crawl4ai not installed (good)"

**Step 4: Verify readability-lxml installed**

Run: `python -c "from readability import Document; print('OK')"`
Expected: "OK"

**Step 5: Commit**

```bash
git add pyproject.toml
git commit -m "refactor: replace crawl4ai with readability-lxml in dependencies

Drop Chromium/Playwright (~500MB-1GB RAM) in favor of readability-lxml (~200KB).
Web scraper targets are manually-configured static blogs that don't need JS rendering."
```

---

### Task 2: Rewrite WebScraperExtractor to use httpx + readability

**Files:**
- Modify: `src/extractors/webscraper.py`

**Step 1: Rewrite the webscraper module**

Replace the entire contents of `src/extractors/webscraper.py` with:

```python
"""Web scraper extractor using httpx + readability-lxml.

Two-phase extraction per index URL:
1. Crawl configured index pages to discover article links.
2. Scrape each discovered article URL for clean text content.

Uses httpx for async HTTP and readability-lxml for content extraction.
No browser/Chromium dependency.
"""

from __future__ import annotations

import re
from urllib.parse import urljoin, urlparse

import httpx
from lxml import html as lxml_html
from readability import Document

from src.core.config import get_settings
from src.core.logging import get_logger
from src.core.metrics import (
    extractor_duration_seconds,
    extractor_errors_total,
    items_extracted_total,
)
from src.extractors.base import BaseExtractor, ExtractedItem

logger = get_logger(__name__)

# Path segments that indicate non-content pages.
_NON_CONTENT_SEGMENTS = frozenset(
    {
        "about",
        "careers",
        "contact",
        "cookie",
        "faq",
        "help",
        "legal",
        "login",
        "logout",
        "pricing",
        "privacy",
        "register",
        "signup",
        "sign-up",
        "signin",
        "sign-in",
        "subscribe",
        "terms",
        "tos",
    }
)

_USER_AGENT = "ai-news-platform/1.0 (+https://pguerrero.me)"


def _extract_links_from_html(raw_html: str, base_url: str) -> list[dict[str, str]]:
    """Parse <a> tags from raw HTML, resolving relative URLs.

    Returns list of dicts with "href" and "text" keys,
    matching the format previously provided by Crawl4AI.
    """
    try:
        tree = lxml_html.fromstring(raw_html)
    except Exception:
        return []

    links: list[dict[str, str]] = []
    for anchor in tree.iter("a"):
        href = anchor.get("href", "").strip()
        if not href or href.startswith(("#", "javascript:", "mailto:")):
            continue
        # Resolve relative URLs.
        absolute = urljoin(base_url, href)
        text = (anchor.text_content() or "").strip()
        links.append({"href": absolute, "text": text})

    return links


def _filter_article_links(links: list[dict[str, str]], index_url: str) -> list[str]:
    """Filter discovered links to keep only likely article URLs.

    Rules:
    - Same domain as the index page
    - At least 2 path segments (e.g. /blog/article)
    - Not in the non-content paths blocklist
    - Deduplicated by normalized URL
    """
    parsed_index = urlparse(index_url)
    index_domain = parsed_index.netloc.lower()
    index_path = parsed_index.path.rstrip("/")

    seen: set[str] = set()
    result: list[str] = []

    for link in links:
        href = link.get("href", "").strip()
        if not href:
            continue

        parsed = urlparse(href)

        # Same domain only.
        if parsed.netloc.lower() != index_domain:
            continue

        # Normalize path.
        path = parsed.path.rstrip("/")

        # Exclude root and same-as-index.
        if not path or path == index_path:
            continue

        # Require at least 2 path segments.
        segments = [s for s in path.split("/") if s]
        if len(segments) < 2:
            continue

        # Exclude non-content paths.
        lower_segments = {s.lower() for s in segments}
        if lower_segments & _NON_CONTENT_SEGMENTS:
            continue

        # Deduplicate by normalized URL.
        canonical = f"{parsed.scheme}://{parsed.netloc}{path}"
        if canonical in seen:
            continue
        seen.add(canonical)

        result.append(href)

    return result


def _extract_title(doc: Document, clean_text: str) -> str:
    """Extract article title from readability Document or text content."""
    title = doc.title().strip()
    if title:
        return title

    # Fallback: first non-empty line.
    for line in clean_text.splitlines():
        stripped = line.strip()
        if stripped:
            return stripped[:200]

    return "Untitled"


def _html_to_text(html_content: str) -> str:
    """Convert HTML to plain text, stripping all tags."""
    try:
        tree = lxml_html.fromstring(html_content)
        return tree.text_content().strip()
    except Exception:
        # Fallback: crude regex strip.
        return re.sub(r"<[^>]+>", "", html_content).strip()


class WebScraperExtractor(BaseExtractor):
    """Extracts articles from configured websites using httpx + readability."""

    @property
    def source_name(self) -> str:
        return "webscraper"

    async def extract(self, since_hours: int = 24) -> list[ExtractedItem]:
        """Extract articles from all configured webscraper URLs.

        For each index URL, discovers article links then fetches each one
        to produce ExtractedItem instances with clean text content.
        """
        settings = get_settings()
        urls = settings.webscraper_urls_list
        max_items = settings.max_items_per_source
        timeout = settings.webscraper_page_timeout

        if not urls:
            logger.info("webscraper_no_urls_configured")
            return []

        items: list[ExtractedItem] = []

        with extractor_duration_seconds.labels(source=self.source_name).time():
            async with httpx.AsyncClient(
                timeout=timeout,
                follow_redirects=True,
                headers={"User-Agent": _USER_AGENT},
            ) as client:
                for index_url in urls:
                    remaining = max_items - len(items)
                    if remaining <= 0:
                        break
                    try:
                        new_items = await self._scrape_index_page(
                            client, index_url, remaining
                        )
                        items.extend(new_items)
                    except Exception as exc:
                        extractor_errors_total.labels(source=self.source_name).inc()
                        logger.warning(
                            "webscraper_index_failed",
                            index_url=index_url,
                            error=str(exc),
                        )
                        continue

        items = items[:max_items]
        items_extracted_total.labels(source=self.source_name).inc(len(items))
        logger.info(
            "extraction_complete",
            source=self.source_name,
            count=len(items),
            index_urls=len(urls),
        )

        return items

    async def _scrape_index_page(
        self,
        client: httpx.AsyncClient,
        index_url: str,
        remaining_budget: int,
    ) -> list[ExtractedItem]:
        """Scrape an index page and its discovered article links."""
        # Phase 1: Fetch index page and discover links.
        resp = await client.get(index_url)
        resp.raise_for_status()

        raw_html = resp.text
        all_links = _extract_links_from_html(raw_html, index_url)
        article_urls = _filter_article_links(all_links, index_url)

        if not article_urls:
            logger.info("webscraper_no_articles_found", index_url=index_url)
            return []

        # Phase 2: Scrape each article.
        domain = urlparse(index_url).netloc
        items: list[ExtractedItem] = []

        for article_url in article_urls[:remaining_budget]:
            try:
                article_resp = await client.get(article_url)
                article_resp.raise_for_status()
            except Exception as exc:
                logger.warning(
                    "webscraper_article_fetch_failed",
                    article_url=article_url,
                    error=str(exc),
                )
                continue

            article_html = article_resp.text
            if not article_html.strip():
                continue

            doc = Document(article_html)
            content_html = doc.summary()
            clean_text = _html_to_text(content_html)

            if not clean_text.strip():
                continue

            title = _extract_title(doc, clean_text)
            word_count = len(clean_text.split())

            items.append(
                ExtractedItem(
                    title=title,
                    source="webscraper",
                    url=article_url,
                    text=clean_text,
                    author=domain,
                    published_at=None,
                    score=0,
                    metadata={
                        "domain": domain,
                        "scraper_source": "readability",
                        "word_count": word_count,
                        "index_url": index_url,
                    },
                )
            )

        logger.info(
            "webscraper_index_done",
            index_url=index_url,
            discovered=len(article_urls),
            scraped=len(items),
        )

        return items
```

**Step 2: Verify syntax**

Run: `python -c "import ast; ast.parse(open('src/extractors/webscraper.py').read()); print('Syntax OK')"`
Expected: "Syntax OK"

---

### Task 3: Rewrite webscraper tests for httpx + readability

**Files:**
- Modify: `tests/unit/test_webscraper_extractor.py`

**Step 1: Rewrite the test file**

Replace the entire contents of `tests/unit/test_webscraper_extractor.py` with:

```python
"""Tests for src.extractors.webscraper -- WebScraperExtractor (httpx + readability)."""

from __future__ import annotations

from unittest.mock import patch

import httpx
import pytest

from src.extractors.base import ExtractedItem
from src.extractors.webscraper import (
    WebScraperExtractor,
    _extract_links_from_html,
    _filter_article_links,
    _html_to_text,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _mock_settings(**overrides):
    """Return a minimal Settings for webscraper tests."""
    from src.core.config import Settings

    defaults = {
        "webscraper_urls": "https://example.com/news",
        "max_items_per_source": 50,
        "webscraper_max_concurrent": 3,
        "webscraper_page_timeout": 30,
        "enabled_sources": "webscraper",
        "telegram_bot_token": "",
        "telegram_chat_id": "",
        "telegram_alerts_enabled": False,
    }
    defaults.update(overrides)
    return Settings(**defaults)


_INDEX_HTML = """\
<html><body>
<h1>News Index</h1>
<a href="https://example.com/blog/ai-article">AI Article</a>
<a href="https://example.com/blog/ml-article">ML Article</a>
<a href="https://other.com/external">External</a>
<a href="/about">About</a>
</body></html>
"""

_ARTICLE_HTML = """\
<html><head><title>{title}</title></head>
<body>
<article>
<h1>{title}</h1>
<p>{content}</p>
</article>
<nav>Navigation stuff</nav>
<footer>Footer stuff</footer>
</body></html>
"""


def _make_article_html(
    title: str = "Test Article",
    content: str = "A detailed article about artificial intelligence breakthroughs.",
) -> str:
    return _ARTICLE_HTML.format(title=title, content=content)


# ---------------------------------------------------------------------------
# TestExtractLinksFromHtml
# ---------------------------------------------------------------------------
class TestExtractLinksFromHtml:
    """Tests for the _extract_links_from_html helper."""

    def test_extracts_links_with_absolute_urls(self):
        html = '<html><body><a href="https://example.com/post">Post</a></body></html>'
        links = _extract_links_from_html(html, "https://example.com")
        assert len(links) == 1
        assert links[0]["href"] == "https://example.com/post"
        assert links[0]["text"] == "Post"

    def test_resolves_relative_urls(self):
        html = '<html><body><a href="/blog/post">Post</a></body></html>'
        links = _extract_links_from_html(html, "https://example.com/news")
        assert len(links) == 1
        assert links[0]["href"] == "https://example.com/blog/post"

    def test_skips_anchors_and_javascript(self):
        html = """<html><body>
        <a href="#section">Anchor</a>
        <a href="javascript:void(0)">JS</a>
        <a href="mailto:test@example.com">Email</a>
        <a href="https://example.com/real">Real</a>
        </body></html>"""
        links = _extract_links_from_html(html, "https://example.com")
        assert len(links) == 1
        assert "real" in links[0]["href"]

    def test_handles_invalid_html(self):
        links = _extract_links_from_html("not html at all {{{{", "https://example.com")
        assert links == []


# ---------------------------------------------------------------------------
# TestFilterArticleLinks
# ---------------------------------------------------------------------------
class TestFilterArticleLinks:
    """Tests for the _filter_article_links helper."""

    def test_filters_same_domain_only(self):
        links = [
            {"href": "https://example.com/blog/article-one", "text": "Article 1"},
            {"href": "https://other.com/blog/article-two", "text": "Article 2"},
            {"href": "https://example.com/news/story", "text": "Story"},
        ]
        result = _filter_article_links(links, "https://example.com/news")
        assert len(result) == 2
        assert all("example.com" in url for url in result)

    def test_filters_shallow_paths(self):
        links = [
            {"href": "https://example.com/", "text": "Home"},
            {"href": "https://example.com/news", "text": "News (same as index)"},
            {"href": "https://example.com/single", "text": "Single segment"},
            {"href": "https://example.com/blog/deep-article", "text": "Deep article"},
        ]
        result = _filter_article_links(links, "https://example.com/news")
        assert len(result) == 1
        assert "blog/deep-article" in result[0]

    def test_deduplicates_links(self):
        links = [
            {"href": "https://example.com/blog/article", "text": "Link 1"},
            {"href": "https://example.com/blog/article", "text": "Link 2"},
            {"href": "https://example.com/blog/article/", "text": "Link 3 trailing slash"},
        ]
        result = _filter_article_links(links, "https://example.com/news")
        assert len(result) == 1

    def test_filters_non_content_paths(self):
        links = [
            {"href": "https://example.com/company/about", "text": "About"},
            {"href": "https://example.com/user/login", "text": "Login"},
            {"href": "https://example.com/legal/privacy", "text": "Privacy"},
            {"href": "https://example.com/legal/terms", "text": "Terms"},
            {"href": "https://example.com/site/contact", "text": "Contact"},
            {"href": "https://example.com/blog/real-article", "text": "Article"},
        ]
        result = _filter_article_links(links, "https://example.com")
        assert len(result) == 1
        assert "real-article" in result[0]

    def test_handles_empty_links(self):
        result = _filter_article_links([], "https://example.com/news")
        assert result == []

    def test_handles_links_without_href(self):
        links = [
            {"text": "No href key"},
            {"href": "", "text": "Empty href"},
            {"href": "https://example.com/blog/valid", "text": "Valid"},
        ]
        result = _filter_article_links(links, "https://example.com")
        assert len(result) == 1
        assert "valid" in result[0]


# ---------------------------------------------------------------------------
# TestHtmlToText
# ---------------------------------------------------------------------------
class TestHtmlToText:
    """Tests for the _html_to_text helper."""

    def test_strips_tags(self):
        result = _html_to_text("<p>Hello <b>world</b></p>")
        assert "Hello" in result
        assert "world" in result
        assert "<" not in result

    def test_handles_empty_string(self):
        assert _html_to_text("") == ""

    def test_handles_plain_text(self):
        result = _html_to_text("No tags here")
        assert "No tags here" in result


# ---------------------------------------------------------------------------
# TestSourceName
# ---------------------------------------------------------------------------
class TestSourceName:
    """WebScraperExtractor.source_name property."""

    def test_source_name_returns_webscraper(self):
        extractor = WebScraperExtractor()
        assert extractor.source_name == "webscraper"


# ---------------------------------------------------------------------------
# TestExtract
# ---------------------------------------------------------------------------
class TestExtract:
    """WebScraperExtractor.extract() with mocked httpx."""

    async def test_extract_returns_empty_when_no_urls_configured(self):
        settings = _mock_settings(webscraper_urls="")
        with patch("src.extractors.webscraper.get_settings", return_value=settings):
            extractor = WebScraperExtractor()
            result = await extractor.extract()
        assert result == []

    async def test_extract_returns_extracted_items(self):
        """Full two-phase extraction returns ExtractedItem instances."""
        index_html = _INDEX_HTML
        article1_html = _make_article_html(title="AI Article", content="Content about AI.")
        article2_html = _make_article_html(title="ML Article", content="Content about ML.")

        responses = {
            "https://example.com/news": httpx.Response(200, text=index_html),
            "https://example.com/blog/ai-article": httpx.Response(200, text=article1_html),
            "https://example.com/blog/ml-article": httpx.Response(200, text=article2_html),
        }

        async def mock_get(url, **kwargs):
            if str(url) in responses:
                return responses[str(url)]
            return httpx.Response(404)

        settings = _mock_settings()
        with patch("src.extractors.webscraper.get_settings", return_value=settings):
            extractor = WebScraperExtractor()
            with patch.object(httpx.AsyncClient, "get", side_effect=mock_get):
                result = await extractor.extract()

        assert len(result) == 2
        assert all(isinstance(item, ExtractedItem) for item in result)
        titles = {item.title for item in result}
        assert "AI Article" in titles
        assert "ML Article" in titles

    async def test_extract_handles_failed_index_fetch(self):
        """If index page returns error, return empty list."""

        async def mock_get(url, **kwargs):
            raise httpx.HTTPStatusError(
                "Server Error",
                request=httpx.Request("GET", url),
                response=httpx.Response(500),
            )

        settings = _mock_settings()
        with patch("src.extractors.webscraper.get_settings", return_value=settings):
            extractor = WebScraperExtractor()
            with patch.object(httpx.AsyncClient, "get", side_effect=mock_get):
                result = await extractor.extract()

        assert result == []

    async def test_extract_skips_failed_article_fetch(self):
        """Failed article fetches are skipped; successful ones are returned."""
        index_html = """\
        <html><body>
        <a href="https://example.com/blog/good-article">Good</a>
        <a href="https://example.com/blog/bad-article">Bad</a>
        </body></html>
        """
        good_html = _make_article_html(title="Good Article")

        call_count = 0

        async def mock_get(url, **kwargs):
            nonlocal call_count
            call_count += 1
            url_str = str(url)
            if "news" in url_str:
                return httpx.Response(200, text=index_html)
            if "good-article" in url_str:
                return httpx.Response(200, text=good_html)
            raise httpx.ConnectError("Connection refused")

        settings = _mock_settings()
        with patch("src.extractors.webscraper.get_settings", return_value=settings):
            extractor = WebScraperExtractor()
            with patch.object(httpx.AsyncClient, "get", side_effect=mock_get):
                result = await extractor.extract()

        assert len(result) == 1
        assert result[0].title == "Good Article"

    async def test_extract_respects_max_items_per_source(self):
        """Output is truncated to max_items_per_source."""
        links_html = "".join(
            f'<a href="https://example.com/blog/post-{i}">Post {i}</a>'
            for i in range(10)
        )
        index_html = f"<html><body>{links_html}</body></html>"

        async def mock_get(url, **kwargs):
            url_str = str(url)
            if "news" in url_str:
                return httpx.Response(200, text=index_html)
            return httpx.Response(200, text=_make_article_html(title=f"Post"))

        settings = _mock_settings(max_items_per_source=3)
        with patch("src.extractors.webscraper.get_settings", return_value=settings):
            extractor = WebScraperExtractor()
            with patch.object(httpx.AsyncClient, "get", side_effect=mock_get):
                result = await extractor.extract()

        assert len(result) == 3

    async def test_extract_maps_fields_correctly(self):
        """Verify all ExtractedItem fields are mapped correctly."""
        index_html = """\
        <html><body>
        <a href="https://example.com/blog/test-post">Test</a>
        </body></html>
        """
        article_html = _make_article_html(
            title="Test Post",
            content="This is the article body content for testing.",
        )

        async def mock_get(url, **kwargs):
            url_str = str(url)
            if "news" in url_str:
                return httpx.Response(200, text=index_html)
            return httpx.Response(200, text=article_html)

        settings = _mock_settings()
        with patch("src.extractors.webscraper.get_settings", return_value=settings):
            extractor = WebScraperExtractor()
            with patch.object(httpx.AsyncClient, "get", side_effect=mock_get):
                result = await extractor.extract()

        assert len(result) == 1
        item = result[0]
        assert item.title == "Test Post"
        assert item.source == "webscraper"
        assert item.url == "https://example.com/blog/test-post"
        assert item.text is not None
        assert "article body content" in item.text
        assert item.author == "example.com"
        assert item.published_at is None
        assert item.score == 0
        assert item.metadata["domain"] == "example.com"
        assert item.metadata["scraper_source"] == "readability"
        assert item.metadata["word_count"] > 0
        assert item.metadata["index_url"] == "https://example.com/news"

    async def test_extract_handles_connection_error(self):
        """If httpx raises for all index pages, return empty."""

        async def mock_get(url, **kwargs):
            raise httpx.ConnectError("Connection refused")

        settings = _mock_settings()
        with patch("src.extractors.webscraper.get_settings", return_value=settings):
            extractor = WebScraperExtractor()
            with patch.object(httpx.AsyncClient, "get", side_effect=mock_get):
                result = await extractor.extract()

        assert result == []
```

**Step 2: Run tests**

Run: `pytest tests/unit/test_webscraper_extractor.py -v`
Expected: All tests PASS

**Step 3: Run linters on changed files**

Run: `ruff check src/extractors/webscraper.py tests/unit/test_webscraper_extractor.py && ruff format --check src/extractors/webscraper.py tests/unit/test_webscraper_extractor.py`
Expected: No errors. Fix any issues before continuing.

**Step 4: Update config comment**

In `src/core/config.py:96`, change the comment:

```python
    # WebScraper (crawl4ai)
```

To:

```python
    # WebScraper (httpx + readability)
```

**Step 5: Run full test suite**

Run: `pytest tests/unit/ -x --timeout=30`
Expected: All tests PASS

**Step 6: Commit**

```bash
git add src/extractors/webscraper.py tests/unit/test_webscraper_extractor.py src/core/config.py
git commit -m "refactor: rewrite WebScraperExtractor to use httpx + readability-lxml

Replace Crawl4AI's AsyncWebCrawler with httpx.AsyncClient + readability.Document.
Two-phase architecture unchanged (discover links -> scrape articles).
Link discovery now uses lxml to parse <a> tags from raw HTML.
Content extraction uses readability-lxml for article text.
Eliminates Chromium dependency (~500MB-1GB RAM savings)."
```

---

## Phase 2: Split pipeline.py into 5 composable stages

### Task 4: Create stages/extract.py

**Files:**
- Create: `src/pipeline/stages/__init__.py`
- Create: `src/pipeline/stages/extract.py`
- Create: `tests/unit/test_stage_extract.py`

**Step 1: Create the stages package**

Create `src/pipeline/stages/__init__.py` as an empty file.

**Step 2: Write the failing test**

Create `tests/unit/test_stage_extract.py`:

```python
"""Tests for src.pipeline.stages.extract — extraction stage."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from src.extractors.base import ExtractedItem
from src.pipeline.stages.extract import get_extractors, run_extraction


def _mock_settings(**overrides):
    from src.core.config import Settings

    defaults = {
        "enabled_sources": "hackernews",
        "telegram_bot_token": "",
        "telegram_chat_id": "",
        "telegram_alerts_enabled": False,
    }
    defaults.update(overrides)
    return Settings(**defaults)


def _make_item(title="Test", source="hackernews", url="https://example.com"):
    return ExtractedItem(title=title, source=source, url=url, score=100)


class TestGetExtractors:
    def test_returns_enabled_extractors(self):
        settings = _mock_settings(enabled_sources="hackernews,arxiv")
        with patch("src.pipeline.stages.extract.get_settings", return_value=settings):
            extractors = get_extractors()
        names = [e.source_name for e in extractors]
        assert "hackernews" in names
        assert "arxiv" in names

    def test_filters_by_sources_param(self):
        settings = _mock_settings(enabled_sources="hackernews,arxiv,rss")
        with patch("src.pipeline.stages.extract.get_settings", return_value=settings):
            extractors = get_extractors(sources=["hackernews"])
        names = [e.source_name for e in extractors]
        assert names == ["hackernews"]

    def test_webscraper_included_when_enabled(self):
        settings = _mock_settings(enabled_sources="webscraper")
        with patch("src.pipeline.stages.extract.get_settings", return_value=settings):
            extractors = get_extractors()
        assert any(e.source_name == "webscraper" for e in extractors)


class TestRunExtraction:
    async def test_returns_items_from_all_extractors(self):
        mock_extractor = AsyncMock()
        mock_extractor.source_name = "hackernews"
        mock_extractor.extract = AsyncMock(return_value=[_make_item()])

        settings = _mock_settings()
        with patch("src.pipeline.stages.extract.get_settings", return_value=settings):
            result = await run_extraction(
                extractors=[mock_extractor], since_hours=24
            )

        assert len(result) == 1

    async def test_handles_extractor_failure(self):
        mock_extractor = AsyncMock()
        mock_extractor.source_name = "hackernews"
        mock_extractor.extract = AsyncMock(side_effect=RuntimeError("API down"))

        settings = _mock_settings()
        with patch("src.pipeline.stages.extract.get_settings", return_value=settings):
            result = await run_extraction(
                extractors=[mock_extractor], since_hours=24
            )

        assert result == []

    async def test_returns_empty_when_no_extractors(self):
        settings = _mock_settings()
        with patch("src.pipeline.stages.extract.get_settings", return_value=settings):
            result = await run_extraction(extractors=[], since_hours=24)
        assert result == []
```

**Step 3: Run test to verify it fails**

Run: `pytest tests/unit/test_stage_extract.py -v`
Expected: FAIL — module `src.pipeline.stages.extract` doesn't exist

**Step 4: Create the extract stage**

Create `src/pipeline/stages/extract.py`:

```python
"""Extraction stage — run all enabled extractors concurrently."""

from __future__ import annotations

import asyncio

from src.core.config import get_settings
from src.core.logging import get_logger
from src.extractors.arxiv import ArxivExtractor
from src.extractors.base import BaseExtractor, ExtractedItem
from src.extractors.github import GitHubExtractor
from src.extractors.hackernews import HackerNewsExtractor
from src.extractors.huggingface import HuggingFaceExtractor
from src.extractors.reddit import RedditExtractor
from src.extractors.rss import RSSExtractor
from src.extractors.webscraper import WebScraperExtractor
from src.notifiers.alerts import AlertService

logger = get_logger(__name__)


def get_extractors(sources: list[str] | None = None) -> list[BaseExtractor]:
    """Build list of enabled extractors, optionally filtered by source names."""
    settings = get_settings()
    enabled = settings.enabled_sources_list

    if sources is not None:
        enabled = [s for s in enabled if s in sources]

    extractors: list[BaseExtractor] = []

    if "hackernews" in enabled:
        extractors.append(HackerNewsExtractor())
    if "arxiv" in enabled:
        extractors.append(ArxivExtractor())
    if "reddit" in enabled:
        extractors.append(RedditExtractor())
    if "rss" in enabled:
        extractors.append(RSSExtractor())
    if "github" in enabled:
        extractors.append(GitHubExtractor())
    if "huggingface" in enabled:
        extractors.append(HuggingFaceExtractor())
    if "webscraper" in enabled:
        extractors.append(WebScraperExtractor())

    return extractors


async def run_extraction(
    extractors: list[BaseExtractor],
    since_hours: int,
    alerts: AlertService | None = None,
) -> list[ExtractedItem]:
    """Run all extractors concurrently and collect results."""
    settings = get_settings()
    if alerts is None:
        alerts = AlertService()

    async def _run_one(extractor: BaseExtractor) -> list[ExtractedItem]:
        try:
            items = await extractor.extract(since_hours=since_hours)
            logger.info(
                "extractor_result",
                source=extractor.source_name,
                count=len(items),
            )
            if not items:
                await alerts.extractor_empty(extractor.source_name)
            return items
        except Exception as exc:
            logger.error(
                "extractor_failed",
                source=extractor.source_name,
                error=str(exc),
            )
            await alerts.extractor_empty(extractor.source_name)
            return []

    results = await asyncio.gather(*[_run_one(ext) for ext in extractors])

    all_items: list[ExtractedItem] = []
    for result in results:
        all_items.extend(result)

    return all_items
```

**Step 5: Run test to verify it passes**

Run: `pytest tests/unit/test_stage_extract.py -v`
Expected: All PASS

**Step 6: Commit**

```bash
git add src/pipeline/stages/__init__.py src/pipeline/stages/extract.py tests/unit/test_stage_extract.py
git commit -m "refactor: extract extraction stage into stages/extract.py

Move get_extractors() and run_extraction() from pipeline.py into
their own module. Independently testable and importable."
```

---

### Task 5: Create stages/classify.py

**Files:**
- Create: `src/pipeline/stages/classify.py`
- Create: `tests/unit/test_stage_classify.py`

**Step 1: Write the failing test**

Create `tests/unit/test_stage_classify.py`:

```python
"""Tests for src.pipeline.stages.classify — classification stage."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from src.classifiers.base import ClassifiedItem
from src.extractors.base import ExtractedItem
from src.pipeline.stages.classify import run_classification


def _mock_settings(**overrides):
    from src.core.config import Settings

    defaults = {
        "enabled_sources": "hackernews",
        "openai_api_key": "",
        "telegram_bot_token": "",
        "telegram_chat_id": "",
        "telegram_alerts_enabled": False,
    }
    defaults.update(overrides)
    return Settings(**defaults)


def _make_item(title="Test", source="hackernews", url="https://example.com"):
    return ExtractedItem(title=title, source=source, url=url, score=100)


def _make_classified(item, topic="models"):
    return ClassifiedItem(
        item=item, topic=topic, relevance_score=0.9, summary="Test summary",
    )


class TestRunClassification:
    async def test_uses_keyword_classifier_when_no_api_key(self):
        settings = _mock_settings(openai_api_key="")
        items = [_make_item()]

        with patch("src.pipeline.stages.classify.get_settings", return_value=settings):
            with patch(
                "src.pipeline.stages.classify.KeywordClassifier"
            ) as mock_cls:
                mock_instance = AsyncMock()
                mock_instance.classify = AsyncMock(
                    return_value=[_make_classified(items[0])]
                )
                mock_cls.return_value = mock_instance
                result = await run_classification(items)

        assert len(result) == 1
        mock_cls.assert_called_once()

    async def test_uses_llm_classifier_when_api_key_present(self):
        settings = _mock_settings(openai_api_key="sk-test")
        items = [_make_item()]

        with patch("src.pipeline.stages.classify.get_settings", return_value=settings):
            with patch("src.pipeline.stages.classify.LLMClassifier") as mock_cls:
                mock_instance = AsyncMock()
                mock_instance.classify = AsyncMock(
                    return_value=[_make_classified(items[0])]
                )
                mock_cls.return_value = mock_instance
                # Also mock event dedup since it requires LLM
                with patch(
                    "src.pipeline.stages.classify.deduplicate_events",
                    new_callable=AsyncMock,
                    return_value=[_make_classified(items[0])],
                ):
                    result = await run_classification(items)

        assert len(result) == 1

    async def test_returns_empty_for_empty_input(self):
        settings = _mock_settings()
        with patch("src.pipeline.stages.classify.get_settings", return_value=settings):
            result = await run_classification([])
        assert result == []
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_stage_classify.py -v`
Expected: FAIL — module doesn't exist

**Step 3: Create the classify stage**

Create `src/pipeline/stages/classify.py`:

```python
"""Classification stage — LLM/keyword classify + event dedup + variant collapse."""

from __future__ import annotations

from src.classifiers.base import ClassifiedItem
from src.classifiers.event_dedup import deduplicate_events
from src.classifiers.keyword import KeywordClassifier
from src.classifiers.llm import LLMClassifier
from src.core.config import get_settings
from src.core.logging import get_logger
from src.core.metrics import classification_duration_seconds, items_classified_total
from src.extractors.base import ExtractedItem
from src.feed.variant_collapse import collapse_variants

logger = get_logger(__name__)


async def run_classification(items: list[ExtractedItem]) -> list[ClassifiedItem]:
    """Classify items, deduplicate events, and collapse HF variants.

    Steps:
    1. LLM or keyword classification
    2. Event deduplication (LLM only, >1 item)
    3. HuggingFace variant collapse
    """
    if not items:
        return []

    settings = get_settings()

    # 1. Classify.
    with classification_duration_seconds.time():
        classifier = LLMClassifier() if settings.openai_api_key else KeywordClassifier()
        classified = await classifier.classify(items)
    items_classified_total.inc(len(classified))
    logger.info("classification_complete", count=len(classified))

    # 2. Event dedup (only if LLM available and >1 item).
    if settings.openai_api_key and len(classified) > 1:
        classified = await deduplicate_events(classified)
        logger.info("event_dedup_complete", count=len(classified))

    # 3. Variant collapse.
    before = len(classified)
    classified = collapse_variants(classified)
    logger.info("variant_collapse_complete", before=before, after=len(classified))

    return classified
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_stage_classify.py -v`
Expected: All PASS

**Step 5: Commit**

```bash
git add src/pipeline/stages/classify.py tests/unit/test_stage_classify.py
git commit -m "refactor: extract classification stage into stages/classify.py

Move LLM/keyword classification, event dedup, and variant collapse
from pipeline.py into a composable stage module."
```

---

### Task 6: Create stages/score.py

**Files:**
- Create: `src/pipeline/stages/score.py`
- Create: `tests/unit/test_stage_score.py`

**Step 1: Write the failing test**

Create `tests/unit/test_stage_score.py`:

```python
"""Tests for src.pipeline.stages.score — composite scoring stage."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from src.classifiers.base import ClassifiedItem
from src.extractors.base import ExtractedItem
from src.pipeline.stages.score import run_scoring


def _make_classified(title="Test", score=100):
    item = ExtractedItem(title=title, source="hackernews", url="https://example.com", score=score)
    return ClassifiedItem(item=item, topic="models", relevance_score=0.9, summary="Test")


class TestRunScoring:
    def test_scores_all_items(self):
        items = [_make_classified(), _make_classified(title="Second")]
        result = run_scoring(items)
        assert len(result) == 2

    def test_returns_empty_for_empty_input(self):
        result = run_scoring([])
        assert result == []
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_stage_score.py -v`
Expected: FAIL

**Step 3: Create the score stage**

Create `src/pipeline/stages/score.py`:

```python
"""Scoring stage — apply composite scoring to classified items."""

from __future__ import annotations

from src.classifiers.base import ClassifiedItem
from src.core.logging import get_logger
from src.pipeline.composite_scorer import CompositeScorer

logger = get_logger(__name__)


def run_scoring(items: list[ClassifiedItem]) -> list[ClassifiedItem]:
    """Apply composite scoring to all classified items."""
    if not items:
        return []

    scorer = CompositeScorer()
    scored = scorer.score_batch(items)
    logger.info("scoring_complete", count=len(scored))
    return scored
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_stage_score.py -v`
Expected: All PASS

**Step 5: Commit**

```bash
git add src/pipeline/stages/score.py tests/unit/test_stage_score.py
git commit -m "refactor: extract scoring stage into stages/score.py"
```

---

### Task 7: Create stages/store.py

**Files:**
- Create: `src/pipeline/stages/store.py`
- Create: `tests/unit/test_stage_store.py`

**Step 1: Write the failing test**

Create `tests/unit/test_stage_store.py`:

```python
"""Tests for src.pipeline.stages.store — storage stage."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from src.classifiers.base import ClassifiedItem
from src.extractors.base import ExtractedItem
from src.pipeline.stages.store import store_classified_items


def _make_classified(title="Test", url="https://example.com"):
    item = ExtractedItem(title=title, source="hackernews", url=url, score=100)
    return ClassifiedItem(item=item, topic="models", relevance_score=0.9, summary="Test")


class TestStoreClassifiedItems:
    async def test_stores_items_and_returns_count(self):
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.rowcount = 1
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.commit = AsyncMock()

        items = [_make_classified()]
        stored = await store_classified_items(mock_session, items)

        assert stored == 1
        assert mock_session.commit.called

    async def test_returns_zero_for_empty_input(self):
        mock_session = AsyncMock()
        stored = await store_classified_items(mock_session, [])
        assert stored == 0
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_stage_store.py -v`
Expected: FAIL

**Step 3: Create the store stage**

Create `src/pipeline/stages/store.py`:

```python
"""Storage stage — persist classified items, briefing stats, and embeddings."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.classifiers.base import ClassifiedItem
from src.core.config import get_settings
from src.core.logging import get_logger
from src.core.metrics import items_stored_total
from src.core.models import DailyBriefing, ItemEmbedding, NewsItem
from src.rag.embeddings import EmbeddingService

logger = get_logger(__name__)

_BATCH_COMMIT_SIZE = 25


async def store_classified_items(session: AsyncSession, items: list[ClassifiedItem]) -> int:
    """Store classified items in PostgreSQL with batch commits.

    Commits every _BATCH_COMMIT_SIZE items to avoid losing all work
    if a late commit fails. Returns count of new items inserted.
    """
    if not items:
        return 0

    stored = 0
    for i, ci in enumerate(items):
        item = ci.item
        stmt = (
            insert(NewsItem)
            .values(
                title=item.title,
                url=item.url,
                source=item.source,
                published_at=item.published_at,
                content_hash=item.content_hash,
                url_hash=item.url_hash,
                full_text=item.text,
                author=item.author,
                score=item.score,
                source_created_at=item.source_created_at,
                metadata_=item.metadata,
                topic=ci.topic,
                relevance_score=ci.relevance_score,
                credibility_score=ci.credibility_score,
                summary=ci.summary,
                priority=ci.priority,
                trending=ci.trending,
                dev_value_score=ci.dev_value_score,
                composite_score=ci.composite_score,
            )
            .on_conflict_do_nothing(index_elements=["content_hash"])
        )
        result = await session.execute(stmt)
        if result.rowcount and result.rowcount > 0:
            stored += 1

        if (i + 1) % _BATCH_COMMIT_SIZE == 0:
            await session.commit()

    await session.commit()
    items_stored_total.inc(stored)
    logger.info("items_stored", count=stored, skipped=len(items) - stored)
    return stored


async def save_briefing(
    session: AsyncSession,
    *,
    items_extracted: int,
    items_after_dedup: int,
    items_stored: int,
    sources_used: list[str],
    duration_seconds: float,
    trending_count: int = 0,
) -> None:
    """Upsert the daily briefing record."""
    today = datetime.now(tz=UTC).date()

    existing = await session.execute(select(DailyBriefing).where(DailyBriefing.date == today))
    briefing = existing.scalar_one_or_none()

    if briefing:
        briefing.total_items = (briefing.total_items or 0) + items_stored
        briefing.items_extracted = items_extracted
        briefing.items_after_dedup = items_after_dedup
        briefing.items_filtered = items_stored
        briefing.trending_count = trending_count
        briefing.duration_seconds = duration_seconds
        existing_sources = set(
            briefing.sources_used.get("sources", []) if briefing.sources_used else []
        )
        existing_sources.update(sources_used)
        briefing.sources_used = {"sources": sorted(existing_sources)}
    else:
        session.add(
            DailyBriefing(
                date=today,
                total_items=items_stored,
                items_extracted=items_extracted,
                items_after_dedup=items_after_dedup,
                items_filtered=items_stored,
                trending_count=trending_count,
                duration_seconds=duration_seconds,
                sources_used={"sources": sources_used},
            )
        )

    await session.commit()


async def embed_new_items(
    session: AsyncSession,
    embed_service: EmbeddingService | None = None,
) -> int:
    """Generate embeddings for items that don't have one yet."""
    settings = get_settings()

    if embed_service is None:
        embed_service = EmbeddingService()

    model_name = settings.embedding_model

    subquery = select(ItemEmbedding.item_id).where(ItemEmbedding.model == model_name)
    stmt = select(NewsItem).where(~NewsItem.id.in_(subquery))
    result = await session.execute(stmt)
    items = list(result.scalars().all())

    if not items:
        logger.info("embed_no_new_items")
        return 0

    try:
        texts = [embed_service.prepare_text(item.title, item.summary) for item in items]
        embeddings = await embed_service.embed_batch(texts)

        rows = [
            {"item_id": item.id, "model": model_name, "embedding": embedding}
            for item, embedding in zip(items, embeddings, strict=True)
        ]
        stmt = (
            insert(ItemEmbedding)
            .values(rows)
            .on_conflict_do_nothing(index_elements=["item_id", "model"])
        )
        await session.execute(stmt)
        await session.commit()
        logger.info("embed_items_stored", count=len(items))
        return len(items)

    except Exception as exc:
        from src.core.metrics import embedding_failures_total

        embedding_failures_total.inc()
        logger.error("embed_items_failed", error=str(exc), item_count=len(items))
        await session.rollback()
        return 0
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_stage_store.py -v`
Expected: All PASS

**Step 5: Commit**

```bash
git add src/pipeline/stages/store.py tests/unit/test_stage_store.py
git commit -m "refactor: extract storage stage into stages/store.py

Move store_classified_items(), save_briefing(), and embed_new_items()
from pipeline.py into their own module."
```

---

### Task 8: Create stages/notify.py

**Files:**
- Create: `src/pipeline/stages/notify.py`
- Create: `tests/unit/test_stage_notify.py`

**Step 1: Write the failing test**

Create `tests/unit/test_stage_notify.py`:

```python
"""Tests for src.pipeline.stages.notify — notification stage."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from src.classifiers.base import ClassifiedItem
from src.extractors.base import ExtractedItem
from src.pipeline.stages.notify import run_notification


def _mock_settings(**overrides):
    from src.core.config import Settings

    defaults = {
        "telegram_bot_token": "fake-token",
        "telegram_chat_id": "12345",
        "telegram_alerts_enabled": True,
    }
    defaults.update(overrides)
    return Settings(**defaults)


def _make_classified():
    item = ExtractedItem(title="Test", source="hackernews", url="https://example.com", score=100)
    return ClassifiedItem(item=item, topic="models", relevance_score=0.9, summary="Test")


class TestRunNotification:
    async def test_sends_notification_when_configured(self):
        settings = _mock_settings()
        items = [_make_classified()]

        with patch("src.pipeline.stages.notify.get_settings", return_value=settings):
            with patch("src.pipeline.stages.notify.TelegramNotifier") as mock_cls:
                mock_notifier = AsyncMock()
                mock_cls.return_value = mock_notifier
                await run_notification(items, duration_seconds=1.5)

        mock_notifier.send_briefing.assert_called_once()

    async def test_skips_when_no_token(self):
        settings = _mock_settings(telegram_bot_token="", telegram_chat_id="")

        with patch("src.pipeline.stages.notify.get_settings", return_value=settings):
            # Should not raise
            await run_notification([], duration_seconds=1.0)
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_stage_notify.py -v`
Expected: FAIL

**Step 3: Create the notify stage**

Create `src/pipeline/stages/notify.py`:

```python
"""Notification stage — send Telegram alerts after pipeline run."""

from __future__ import annotations

from src.classifiers.base import ClassifiedItem
from src.core.config import get_settings
from src.core.logging import get_logger
from src.core.metrics import notification_duration_seconds, notification_errors_total
from src.notifiers.telegram import TelegramNotifier

logger = get_logger(__name__)


async def run_notification(
    items: list[ClassifiedItem],
    duration_seconds: float,
) -> None:
    """Send pipeline results via Telegram if configured."""
    settings = get_settings()

    if not settings.telegram_bot_token or not settings.telegram_chat_id:
        return

    try:
        with notification_duration_seconds.time():
            notifier = TelegramNotifier()
            await notifier.send_briefing(items, duration_seconds=duration_seconds)
    except Exception as exc:
        notification_errors_total.inc()
        logger.warning("notification_failed", error=str(exc))
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_stage_notify.py -v`
Expected: All PASS

**Step 5: Commit**

```bash
git add src/pipeline/stages/notify.py tests/unit/test_stage_notify.py
git commit -m "refactor: extract notification stage into stages/notify.py"
```

---

### Task 9: Rewrite pipeline.py as thin orchestrator

**Files:**
- Modify: `src/pipeline/pipeline.py`

**Step 1: Rewrite pipeline.py**

Replace the entire contents of `src/pipeline/pipeline.py` with:

```python
"""Pipeline orchestrator — chains composable stages.

extract -> dedup -> validate -> classify -> score -> validate -> store -> notify -> embed
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import get_settings
from src.core.logging import get_logger, set_correlation_id
from src.core.metrics import (
    items_validated_total,
    items_validation_failed_total,
    pipeline_duration_seconds,
    pipeline_runs_total,
    validation_duration_seconds,
)
from src.notifiers.alerts import AlertService
from src.pipeline.dedup import deduplicate_items
from src.pipeline.stages.classify import run_classification
from src.pipeline.stages.extract import get_extractors, run_extraction
from src.pipeline.stages.notify import run_notification
from src.pipeline.stages.score import run_scoring
from src.pipeline.stages.store import embed_new_items, save_briefing, store_classified_items
from src.pipeline.validation import validate_extracted_item
from src.validators.credibility import CredibilityValidator

logger = get_logger(__name__)


async def run_pipeline(
    session: AsyncSession,
    sources: list[str] | None = None,
    since_hours: int | None = None,
) -> bool:
    """Execute the full news pipeline.

    Steps:
    1. Extract from enabled sources (parallel)
    2. Deduplicate by hash (content + URL)
    3. Pre-validate (reject items without title/URL)
    4. Classify (LLM or keyword) + event dedup + variant collapse
    5. Composite scoring
    6. Credibility validation
    7. Store in PostgreSQL
    8. Save daily briefing stats
    9. Notify via Telegram
    10. Generate embeddings
    """
    cid = set_correlation_id()
    start = datetime.now(tz=UTC)
    alerts = AlertService()
    settings = get_settings()

    logger.info("pipeline_start", correlation_id=cid)

    try:
        # 1. Extract
        extractors = get_extractors(sources=sources)
        sources_used = [e.source_name for e in extractors]
        logger.info("pipeline_extract", sources=sources_used)

        effective_since = since_hours if since_hours is not None else settings.extraction_since_hours
        all_items = await run_extraction(extractors, effective_since, alerts=alerts)
        items_extracted = len(all_items)

        if not all_items:
            logger.warning("pipeline_no_items")
            await alerts.pipeline_failure("No items extracted from any source", stage="extraction")
            pipeline_runs_total.labels(status="empty").inc()
            return False

        # 2. Dedup
        logger.info("pipeline_dedup", input_count=items_extracted)
        unique_items = deduplicate_items(all_items)
        items_after_dedup = len(unique_items)

        # 3. Pre-validate
        valid_items = []
        for item in unique_items:
            errors = validate_extracted_item({"title": item.title, "url": item.url})
            if errors:
                for reason in errors:
                    items_validation_failed_total.labels(reason=reason).inc()
                logger.warning(
                    "item_validation_failed",
                    errors=errors,
                    title=item.title[:80] if item.title else None,
                )
            else:
                valid_items.append(item)

        if valid_items != unique_items:
            logger.info(
                "pipeline_validation",
                valid=len(valid_items),
                rejected=len(unique_items) - len(valid_items),
            )

        # 4. Classify + event dedup + variant collapse
        classified = await run_classification(valid_items)
        logger.info("pipeline_classified", count=len(classified))

        # 5. Composite scoring
        scored = run_scoring(classified)
        logger.info("pipeline_scoring", count=len(scored))

        # 6. Credibility validation
        with validation_duration_seconds.time():
            validator = CredibilityValidator()
            validated = await validator.validate(scored)
        items_validated_total.inc(len(validated))
        logger.info("pipeline_validated", count=len(validated))

        # 7. Store
        items_stored = await store_classified_items(session, validated)

        # 8. Briefing
        trending_count = sum(1 for i in validated if i.trending)
        duration = (datetime.now(tz=UTC) - start).total_seconds()
        await save_briefing(
            session,
            items_extracted=items_extracted,
            items_after_dedup=items_after_dedup,
            items_stored=items_stored,
            sources_used=sources_used,
            duration_seconds=duration,
            trending_count=trending_count,
        )

        # 9. Notify
        await run_notification(validated, duration_seconds=duration)

        # 10. Embeddings
        if settings.embedding_api_key:
            try:
                embedded_count = await embed_new_items(session)
                logger.info("pipeline_embeddings", count=embedded_count)
            except Exception as exc:
                from src.core.metrics import embedding_failures_total

                embedding_failures_total.inc()
                logger.error("pipeline_embedding_failed", error=str(exc))

        pipeline_runs_total.labels(status="success").inc()
        pipeline_duration_seconds.observe(duration)

        logger.info(
            "pipeline_complete",
            items_extracted=items_extracted,
            items_classified=len(classified),
            items_validated=len(validated),
            items_stored=items_stored,
            duration_seconds=round(duration, 1),
            sources=sources_used,
        )

        await alerts.pipeline_success(
            items_count=items_stored,
            duration_seconds=duration,
            sources=sources_used,
        )
        return True

    except Exception as exc:
        duration = (datetime.now(tz=UTC) - start).total_seconds()
        pipeline_runs_total.labels(status="error").inc()
        logger.error("pipeline_failed", error=str(exc), duration_seconds=round(duration, 1))
        await alerts.pipeline_failure(str(exc), stage="unknown")
        raise
```

**Step 2: Run existing pipeline tests**

Run: `pytest tests/unit/test_pipeline.py -v`
Expected: Some tests will FAIL because they import private functions that moved. That's expected — we fix them in the next task.

---

### Task 10: Update all import sites and tests

**Files:**
- Modify: `tests/unit/test_pipeline.py:16-22` — update imports
- Modify: `tests/unit/test_pipeline_embedding.py:9` — update import
- Modify: `tests/integration/test_pipeline.py:11` — update import
- Modify: `tests/integration/test_rag.py:87` — update import
- Modify: `scripts/backfill.py:464` — update import
- Modify: `src/main.py:10` — verify import still works (it should, `run_pipeline` stays in pipeline.py)

**Step 1: Update test_pipeline.py imports**

In `tests/unit/test_pipeline.py`, change the imports (lines 16-22) from:

```python
from src.pipeline.pipeline import (
    _extract_all,
    _get_extractors,
    _save_briefing,
    _store_classified_items,
    run_pipeline,
)
```

To:

```python
from src.pipeline.pipeline import run_pipeline
from src.pipeline.stages.extract import get_extractors, run_extraction
from src.pipeline.stages.store import save_briefing, store_classified_items
```

Then search-and-replace in the file:
- `_get_extractors` → `get_extractors`
- `_extract_all` → `run_extraction`
- `_store_classified_items` → `store_classified_items`
- `_save_briefing` → `save_briefing`

Also update any `patch()` targets:
- `"src.pipeline.pipeline._get_extractors"` → `"src.pipeline.stages.extract.get_extractors"`
- `"src.pipeline.pipeline._extract_all"` → `"src.pipeline.stages.extract.run_extraction"`
- `"src.pipeline.pipeline._store_classified_items"` → `"src.pipeline.stages.store.store_classified_items"`
- `"src.pipeline.pipeline._save_briefing"` → `"src.pipeline.stages.store.save_briefing"`

**Step 2: Update test_pipeline_embedding.py import**

In `tests/unit/test_pipeline_embedding.py:9`, change:

```python
from src.pipeline.pipeline import _embed_new_items
```

To:

```python
from src.pipeline.stages.store import embed_new_items
```

And update all references from `_embed_new_items` to `embed_new_items` in that file.

**Step 3: Update integration test imports**

In `tests/integration/test_pipeline.py:11`, change:

```python
from src.pipeline.pipeline import _embed_new_items, _save_briefing, _store_classified_items
```

To:

```python
from src.pipeline.stages.store import embed_new_items, save_briefing, store_classified_items
```

And update references (drop leading underscores).

In `tests/integration/test_rag.py:87`, change:

```python
from src.pipeline.pipeline import _embed_new_items
```

To:

```python
from src.pipeline.stages.store import embed_new_items
```

**Step 4: Update scripts/backfill.py**

In `scripts/backfill.py:464`, change:

```python
from src.pipeline.pipeline import _embed_new_items as embed_new_items
```

To:

```python
from src.pipeline.stages.store import embed_new_items
```

**Step 5: Run full test suite**

Run: `pytest tests/unit/ -x --timeout=30`
Expected: All tests PASS

**Step 6: Run linters**

Run: `ruff check . && ruff format --check .`
Expected: No errors

**Step 7: Commit**

```bash
git add src/pipeline/pipeline.py tests/ scripts/backfill.py
git commit -m "refactor: rewrite pipeline.py as thin orchestrator using stage modules

Pipeline.py drops from 469 LOC to ~130 LOC. Each stage is independently
testable and importable. All import sites updated to use new module paths."
```

---

## Phase 3: Split Dockerfiles

### Task 11: Split pyproject.toml into dependency groups

**Files:**
- Modify: `pyproject.toml:10-46`

**Step 1: Reorganize dependencies into core + optional groups**

In `pyproject.toml`, change the `[project]` dependencies to keep only core deps shared by API and pipeline:

```toml
dependencies = [
    # Web framework
    "fastapi~=0.115.0",
    "uvicorn[standard]~=0.34.0",
    # Database
    "sqlalchemy[asyncio]~=2.0.36",
    "asyncpg~=0.30.0",
    "psycopg2-binary~=2.9.0",
    "alembic~=1.14.0",
    "pgvector~=0.3.6",
    # Configuration
    "pydantic~=2.10.0",
    "pydantic-settings~=2.7.0",
    # HTTP client
    "httpx~=0.28.0",
    # LLM (OpenAI-compatible API for Kimi/Moonshot)
    "openai~=1.59.0",
    # Logging & monitoring
    "structlog~=24.4.0",
    "prometheus-client~=0.21.0",
    # Auth
    "python-jose[cryptography]~=3.3.0",
    "passlib[bcrypt]~=1.7.0",
]
```

Add new optional dependency groups after the existing `dev` group:

```toml
[project.optional-dependencies]
api = [
    # Rate limiting
    "slowapi~=0.1.0",
    # WebAuthn (Passkeys)
    "webauthn~=2.5.0",
    # MCP server
    "mcp~=1.6.0",
]
pipeline = [
    # RSS parsing
    "feedparser~=6.0.0",
    # Web scraping (lightweight: no Chromium)
    "readability-lxml~=0.8",
    # Notifications
    "python-telegram-bot~=21.9",
    # Scheduling
    "apscheduler~=3.10",
]
dev = [
    # Linting & formatting
    "ruff~=0.8.0",
    # Type checking
    "pyright~=1.1.390",
    # Testing
    "pytest~=8.3.0",
    "pytest-asyncio~=0.24.0",
    "pytest-timeout~=2.3.0",
    "coverage~=7.6.0",
    # Security scanning
    "bandit~=1.8.0",
    # HTTP mocking
    "respx~=0.22.0",
    # Factory for test data
    "factory-boy~=3.3.0",
    # E2E browser testing
    "pytest-playwright~=0.6.0",
]
```

**Step 2: Install all groups for local dev**

Run: `pip install -e ".[api,pipeline,dev]"`
Expected: All dependencies install successfully

**Step 3: Run tests to verify nothing broke**

Run: `pytest tests/unit/ -x --timeout=30`
Expected: All PASS

**Step 4: Commit**

```bash
git add pyproject.toml
git commit -m "refactor: split pyproject.toml dependencies into core + api + pipeline groups

Core deps shared by both images. API-only: slowapi, webauthn, mcp.
Pipeline-only: feedparser, readability-lxml, python-telegram-bot, apscheduler.
Local dev installs all: pip install -e '.[api,pipeline,dev]'"
```

---

### Task 12: Create Dockerfile.api

**Files:**
- Create: `Dockerfile.api`

**Step 1: Create the lightweight API Dockerfile**

Create `Dockerfile.api`:

```dockerfile
FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN groupadd --gid 1000 appuser && \
    useradd --uid 1000 --gid appuser --create-home appuser

WORKDIR /app

# Install system dependencies for asyncpg
RUN apt-get update && \
    apt-get install -y --no-install-recommends curl && \
    rm -rf /var/lib/apt/lists/*

# Install Python dependencies (core + api only, no pipeline deps)
COPY pyproject.toml ./
RUN pip install --no-cache-dir . 2>/dev/null || true && \
    pip install --no-cache-dir ".[api]" 2>/dev/null || true

# Copy source and install package
COPY src/ src/
COPY alembic/ alembic/
COPY alembic.ini ./
COPY docker-entrypoint.sh ./
RUN pip install --no-cache-dir ".[api]" && \
    pip cache purge

RUN chmod +x docker-entrypoint.sh && \
    chown -R appuser:appuser /app
USER appuser

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=5 \
    CMD curl -f http://localhost:8000/health || exit 1

EXPOSE 8000

ENTRYPOINT ["./docker-entrypoint.sh"]
```

**Step 2: Verify it builds**

Run: `docker build -f Dockerfile.api -t ainews-api:test .`
Expected: Build succeeds. Image is significantly smaller than current.

**Step 3: Commit**

```bash
git add Dockerfile.api
git commit -m "feat: add Dockerfile.api — lightweight API image without pipeline deps

Installs core + api optional deps only (no feedparser, readability-lxml,
python-telegram-bot, apscheduler). Target: ~300MB image."
```

---

### Task 13: Create Dockerfile.pipeline + entrypoint

**Files:**
- Rename: `Dockerfile` → `Dockerfile.pipeline`
- Create: `docker-entrypoint-pipeline.sh`

**Step 1: Rename existing Dockerfile**

Run: `git mv Dockerfile Dockerfile.pipeline`

**Step 2: Update Dockerfile.pipeline**

Modify `Dockerfile.pipeline` to install the pipeline optional group:

```dockerfile
FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN groupadd --gid 1000 appuser && \
    useradd --uid 1000 --gid appuser --create-home appuser

WORKDIR /app

# Install system dependencies for asyncpg + lxml
RUN apt-get update && \
    apt-get install -y --no-install-recommends curl && \
    rm -rf /var/lib/apt/lists/*

# Install Python dependencies (core + pipeline)
COPY pyproject.toml ./
RUN pip install --no-cache-dir . 2>/dev/null || true && \
    pip install --no-cache-dir ".[pipeline]" 2>/dev/null || true

# Copy source and install package
COPY src/ src/
COPY alembic/ alembic/
COPY alembic.ini ./
COPY docker-entrypoint-pipeline.sh ./
RUN pip install --no-cache-dir ".[pipeline]" && \
    pip cache purge

RUN chmod +x docker-entrypoint-pipeline.sh && \
    chown -R appuser:appuser /app
USER appuser

ENTRYPOINT ["./docker-entrypoint-pipeline.sh"]
```

**Step 3: Create pipeline entrypoint**

Create `docker-entrypoint-pipeline.sh`:

```bash
#!/usr/bin/env bash
set -e

echo "Running database migrations..."
alembic upgrade head

echo "Starting pipeline scheduler..."
exec python -m src.pipeline.scheduler
```

**Step 4: Make it executable**

Run: `chmod +x docker-entrypoint-pipeline.sh`

**Step 5: Verify it builds**

Run: `docker build -f Dockerfile.pipeline -t ainews-pipeline:test .`
Expected: Build succeeds.

**Step 6: Commit**

```bash
git add Dockerfile.pipeline docker-entrypoint-pipeline.sh
git commit -m "feat: add Dockerfile.pipeline with separate entrypoint

Pipeline image installs core + pipeline deps (feedparser, readability-lxml,
python-telegram-bot, apscheduler). Runs scheduler directly, no uvicorn."
```

---

### Task 14: Update docker-compose.coolify.yml

**Files:**
- Modify: `docker-compose.coolify.yml`
- Remove: `Dockerfile` (if still exists — should have been renamed in Task 13)

**Step 1: Update compose to use new Dockerfiles**

In `docker-compose.coolify.yml`, change the `api` service:

```yaml
  api:
    build:
      context: .
      dockerfile: Dockerfile.api
```

Change the `pipeline-cron` service:

```yaml
  pipeline-cron:
    build:
      context: .
      dockerfile: Dockerfile.pipeline
```

**Step 2: Verify compose config is valid**

Run: `docker compose -f docker-compose.coolify.yml config --quiet && echo "Config valid"`
Expected: "Config valid"

**Step 3: Commit**

```bash
git add docker-compose.coolify.yml
git commit -m "feat: update docker-compose to use split Dockerfiles

api service uses Dockerfile.api (lightweight, ~300MB).
pipeline-cron service uses Dockerfile.pipeline (full deps, ~500MB)."
```

---

### Task 15: Final quality checks and documentation

**Step 1: Run ruff**

Run: `ruff check . && ruff format --check .`
Expected: No errors

**Step 2: Run pyright**

Run: `pyright .`
Expected: No new errors

**Step 3: Run full test suite**

Run: `pytest tests/unit/ -x --timeout=30`
Expected: All tests PASS

**Step 4: Update AGENTS.md**

Add a section documenting the new pipeline stages structure and the Dockerfile split. Update the webscraper entry to note it now uses httpx + readability-lxml instead of Crawl4AI.

**Step 5: Update backlog**

In `docs/plans/ideas-backlog.md`, mark these items as done:
- [x] Replace Crawl4AI with httpx + readability
- [x] Separate Dockerfiles: API vs Pipeline
- [x] Break pipeline.py into composable stages

**Step 6: Final commit**

```bash
git add AGENTS.md docs/plans/ideas-backlog.md
git commit -m "docs: update AGENTS.md and backlog for lightweight pipeline refactor

Mark 3 Tier 1 architecture items as done:
- Crawl4AI replaced with httpx + readability-lxml
- pipeline.py split into 5 composable stages
- Separate Dockerfiles for API and pipeline"
```

---

## Summary of tasks

| # | Task | Phase | Files |
|---|------|-------|-------|
| 1 | Swap deps in pyproject.toml | 1: Crawl4AI | `pyproject.toml` |
| 2 | Rewrite webscraper.py | 1: Crawl4AI | `src/extractors/webscraper.py` |
| 3 | Rewrite webscraper tests | 1: Crawl4AI | `tests/unit/test_webscraper_extractor.py` |
| 4 | Create stages/extract.py | 2: Pipeline | `src/pipeline/stages/extract.py`, test |
| 5 | Create stages/classify.py | 2: Pipeline | `src/pipeline/stages/classify.py`, test |
| 6 | Create stages/score.py | 2: Pipeline | `src/pipeline/stages/score.py`, test |
| 7 | Create stages/store.py | 2: Pipeline | `src/pipeline/stages/store.py`, test |
| 8 | Create stages/notify.py | 2: Pipeline | `src/pipeline/stages/notify.py`, test |
| 9 | Rewrite pipeline.py orchestrator | 2: Pipeline | `src/pipeline/pipeline.py` |
| 10 | Update all import sites + tests | 2: Pipeline | tests, scripts, pipeline.py |
| 11 | Split pyproject.toml deps | 3: Docker | `pyproject.toml` |
| 12 | Create Dockerfile.api | 3: Docker | `Dockerfile.api` |
| 13 | Create Dockerfile.pipeline | 3: Docker | `Dockerfile.pipeline`, entrypoint |
| 14 | Update docker-compose | 3: Docker | `docker-compose.coolify.yml` |
| 15 | Final quality checks + docs | 3: Docker | `AGENTS.md`, backlog |
