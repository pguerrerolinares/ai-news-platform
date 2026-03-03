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
from src.core.ssrf import assert_safe_url
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
        logger.warning("extract_links_parse_failed", base_url=base_url)
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
        logger.warning("html_to_text_parse_failed", content_length=len(html_content))
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
                        new_items = await self._scrape_index_page(client, index_url, remaining)
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
        await assert_safe_url(index_url)
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
                await assert_safe_url(article_url)
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
