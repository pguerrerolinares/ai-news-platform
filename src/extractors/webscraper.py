"""Web scraper extractor using Crawl4AI for headless browser rendering.

Two-phase extraction per index URL:
1. Crawl configured index pages to discover article links.
2. Scrape each discovered article URL for markdown content.
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


def _filter_article_links(links: list[dict[str, str]], index_url: str) -> list[str]:
    """Filter Crawl4AI internal links to likely article URLs.

    Args:
        links: List of dicts with "href" (and optionally "text") keys
            as returned by Crawl4AI's result.links["internal"].
        index_url: The index page URL used to determine domain and depth.

    Returns:
        Deduplicated list of same-domain article URL strings.
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

        # Exclude root and same-as-index (shallow paths).
        if not path or path == index_path:
            continue

        # Require at least 2 path segments (e.g. /blog/article).
        segments = [s for s in path.split("/") if s]
        if len(segments) < 2:
            continue

        # Exclude non-content paths.
        lower_segments = {s.lower() for s in segments}
        if lower_segments & _NON_CONTENT_SEGMENTS:
            continue

        # Deduplicate by normalized URL (scheme + netloc + path).
        canonical = f"{parsed.scheme}://{parsed.netloc}{path}"
        if canonical in seen:
            continue
        seen.add(canonical)

        result.append(href)

    return result


def _extract_title_from_markdown(markdown: str, metadata: dict[str, str]) -> str:
    """Extract a title from crawled page content.

    Priority:
        1. metadata["title"]
        2. First H1 heading from markdown
        3. First non-empty line (truncated to 200 chars)
        4. "Untitled"
    """
    # 1. Metadata title.
    meta_title = (metadata or {}).get("title", "").strip()
    if meta_title:
        return meta_title

    # 2. First H1 heading.
    h1_match = re.search(r"^# (.+)$", markdown or "", re.MULTILINE)
    if h1_match:
        return h1_match.group(1).strip()

    # 3. First non-empty line.
    for line in (markdown or "").splitlines():
        stripped = line.strip()
        if stripped:
            return stripped[:200]

    # 4. Fallback.
    return "Untitled"


class WebScraperExtractor(BaseExtractor):
    """Extracts articles from configured websites using Crawl4AI."""

    @property
    def source_name(self) -> str:
        return "webscraper"

    async def extract(self, since_hours: int = 24) -> list[ExtractedItem]:
        """Extract articles from all configured webscraper URLs.

        For each index URL, discovers article links then scrapes each one
        to produce ExtractedItem instances with full markdown content.
        """
        settings = get_settings()
        urls = settings.webscraper_urls_list
        max_items = settings.max_items_per_source
        timeout_ms = settings.webscraper_page_timeout * 1000

        if not urls:
            logger.info("webscraper_no_urls_configured")
            return []

        items: list[ExtractedItem] = []

        browser_config = BrowserConfig(headless=True)
        crawl_config = CrawlerRunConfig(page_timeout=timeout_ms)

        with extractor_duration_seconds.labels(source=self.source_name).time():
            async with AsyncWebCrawler(config=browser_config) as crawler:
                for index_url in urls:
                    remaining = max_items - len(items)
                    if remaining <= 0:
                        break
                    try:
                        new_items = await self._scrape_index_page(
                            crawler, index_url, crawl_config, remaining
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
        crawler: AsyncWebCrawler,
        index_url: str,
        crawl_config: CrawlerRunConfig,
        remaining_budget: int,
    ) -> list[ExtractedItem]:
        """Scrape an index page and its discovered article links.

        Phase 1: Crawl the index page to discover links.
        Phase 2: Crawl each article link and map to ExtractedItem.
        """
        # Phase 1: Discover links from the index page.
        index_result = await crawler.arun(url=index_url, config=crawl_config)
        if not index_result.success:
            logger.warning(
                "webscraper_index_crawl_failed",
                index_url=index_url,
                error=getattr(index_result, "error_message", "unknown"),
            )
            return []

        internal_links = (index_result.links or {}).get("internal", [])
        article_urls = _filter_article_links(internal_links, index_url)

        # Phase 2: Scrape each article.
        items: list[ExtractedItem] = []
        domain = urlparse(index_url).netloc

        for article_url in article_urls[:remaining_budget]:
            try:
                result = await crawler.arun(url=article_url, config=crawl_config)
            except Exception as exc:
                logger.warning(
                    "webscraper_article_crawl_exception",
                    article_url=article_url,
                    error=str(exc),
                )
                continue

            if not result.success:
                logger.warning(
                    "webscraper_article_crawl_failed",
                    article_url=article_url,
                    error=getattr(result, "error_message", "unknown"),
                )
                continue

            markdown = result.markdown or ""
            metadata = result.metadata or {}
            title = _extract_title_from_markdown(markdown, metadata)
            word_count = len(markdown.split())

            items.append(
                ExtractedItem(
                    title=title,
                    source="webscraper",
                    url=article_url,
                    text=markdown,
                    author=domain,
                    published_at=None,
                    score=0,
                    metadata={
                        "domain": domain,
                        "scraper_source": "crawl4ai",
                        "word_count": word_count,
                        "index_url": index_url,
                    },
                )
            )

        return items
