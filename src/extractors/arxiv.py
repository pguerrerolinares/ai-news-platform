"""ArXiv extractor using RSS feeds.

Fetches new paper announcements from arXiv RSS feeds for configured
categories (e.g. cs.AI, cs.CL, cs.LG), filters by keyword relevance,
and deduplicates by arXiv paper ID.

RSS endpoint: https://rss.arxiv.org/rss/{category}
"""

from __future__ import annotations

import html
import re
from datetime import UTC, datetime

import feedparser
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

RSS_BASE = "https://rss.arxiv.org/rss"


class ArxivExtractor(BaseExtractor):
    """Extracts AI-related papers from arXiv RSS feeds."""

    @property
    def source_name(self) -> str:
        return "arxiv"

    async def extract(self, since_hours: int = 24) -> list[ExtractedItem]:
        """Extract new papers from arXiv RSS feeds.

        3-stage filter:
        1. Only "new" announcements (not cross-listings or replacements)
        2. Keyword regex matching on title + description
        3. Deduplication by arXiv paper ID
        """
        settings = get_settings()
        categories = settings.arxiv_categories_list
        keywords = settings.arxiv_keywords_list
        max_items = settings.max_items_per_source

        keyword_pattern = self._build_keyword_regex(keywords)
        seen_ids: set[str] = set()
        items: list[ExtractedItem] = []

        with extractor_duration_seconds.labels(source=self.source_name).time():
            async with httpx.AsyncClient(
                timeout=30,
                headers={"User-Agent": "AI-News-Platform/1.0"},
            ) as client:
                for category in categories:
                    try:
                        new_items = await self._fetch_category(
                            client, category, keyword_pattern, seen_ids
                        )
                        items.extend(new_items)
                    except Exception as exc:
                        logger.warning(
                            "arxiv_fetch_failed",
                            category=category,
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
            categories=len(categories),
        )

        if not items:
            extractor_errors_total.labels(source=self.source_name).inc()

        return items

    async def _fetch_category(
        self,
        client: httpx.AsyncClient,
        category: str,
        keyword_pattern: re.Pattern[str] | None,
        seen_ids: set[str],
    ) -> list[ExtractedItem]:
        """Fetch and parse a single arXiv RSS category feed."""
        url = f"{RSS_BASE}/{category}"
        resp = await client.get(url)
        resp.raise_for_status()

        feed = feedparser.parse(resp.text)
        items: list[ExtractedItem] = []

        for entry in feed.entries:
            # Stage 1: Only new announcements
            if not self._is_new_announcement(entry):
                continue

            # Extract arXiv ID for dedup
            arxiv_id = self._extract_arxiv_id(entry)
            if not arxiv_id:
                continue

            # Stage 3: Dedup by arXiv ID
            if arxiv_id in seen_ids:
                continue
            seen_ids.add(arxiv_id)

            # Stage 2: Keyword filtering
            title = html.unescape(entry.get("title", ""))
            description = self._clean_description(entry.get("summary", ""))
            if keyword_pattern and not keyword_pattern.search(f"{title} {description}"):
                continue

            link = entry.get("link", "")
            pdf_url = link.replace("/abs/", "/pdf/") if "/abs/" in link else ""
            authors = self._extract_authors(entry)
            published = self._parse_published(entry)

            items.append(
                ExtractedItem(
                    title=title,
                    source=self.source_name,
                    url=link,
                    text=description,
                    author=authors,
                    published_at=published,
                    score=0,
                    metadata={
                        "arxiv_id": arxiv_id,
                        "category": category,
                        "pdf_url": pdf_url,
                    },
                )
            )

        return items

    @staticmethod
    def _build_keyword_regex(keywords: list[str]) -> re.Pattern[str] | None:
        """Build a compiled regex OR-pattern from keyword list."""
        if not keywords:
            return None
        escaped = [re.escape(kw) for kw in keywords]
        pattern = "|".join(escaped)
        return re.compile(pattern, re.IGNORECASE)

    @staticmethod
    def _is_new_announcement(entry: dict) -> bool:
        """Check if an entry is a 'new' announcement (not replacement/cross-list)."""
        summary = entry.get("summary", "") or ""
        lower = summary.lower()
        # arXiv RSS uses "Announce Type: new" in the description
        if "announce type: new" in lower:
            return True
        # Also accept entries without announce type marker (some feeds omit it)
        return "announce type:" not in lower

    @staticmethod
    def _extract_arxiv_id(entry: dict) -> str | None:
        """Extract the arXiv paper ID from entry link or id field."""
        link = entry.get("link", "") or entry.get("id", "") or ""
        match = re.search(r"arxiv\.org/abs/([^\s?#]+)", link)
        if match:
            # Strip version suffix (e.g. v1, v2)
            arxiv_id = re.sub(r"v\d+$", "", match.group(1))
            return arxiv_id
        return None

    @staticmethod
    def _clean_description(text: str) -> str:
        """Remove HTML tags and 'Announce Type:' lines from description."""
        # Remove HTML tags
        text = re.sub(r"<[^>]+>", "", text)
        # Remove Announce Type lines
        text = re.sub(r"Announce Type:.*?\n?", "", text, flags=re.IGNORECASE)
        return text.strip()

    @staticmethod
    def _extract_authors(entry: dict) -> str:
        """Extract author names from entry."""
        # feedparser may put authors in different fields
        if hasattr(entry, "authors") and entry.authors:
            return ", ".join(a.get("name", "") for a in entry.authors if a.get("name"))
        if hasattr(entry, "author") and entry.author:
            return entry.author
        # Try extracting from description
        summary = entry.get("summary", "") or ""
        match = re.search(r"Authors?:\s*(.+?)(?:\n|<)", summary)
        if match:
            return match.group(1).strip()
        return "unknown"

    @staticmethod
    def _parse_published(entry: dict) -> datetime | None:
        """Parse the published date from an entry."""
        if hasattr(entry, "published_parsed") and entry.published_parsed:
            try:
                from time import mktime

                return datetime.fromtimestamp(mktime(entry.published_parsed), tz=UTC)
            except (ValueError, OverflowError, OSError):
                pass
        if hasattr(entry, "updated_parsed") and entry.updated_parsed:
            try:
                from time import mktime

                return datetime.fromtimestamp(mktime(entry.updated_parsed), tz=UTC)
            except (ValueError, OverflowError, OSError):
                pass
        return None
