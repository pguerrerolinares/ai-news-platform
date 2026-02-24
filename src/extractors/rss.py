"""Generic RSS extractor for curated blog feeds.

Fetches posts from trusted RSS feeds (OpenAI blog, Google AI blog,
HuggingFace blog, etc.), applies a 48-hour lookback window,
cleans HTML content, and deduplicates by URL.

No keyword filtering is applied since these are trusted sources.
"""

from __future__ import annotations

import hashlib
import re
from datetime import UTC, datetime, timedelta
from time import mktime
from urllib.parse import urlparse

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


class RSSExtractor(BaseExtractor):
    """Extracts posts from curated RSS/Atom feeds."""

    def __init__(self) -> None:
        self._etag_cache: dict[str, dict[str, str]] = {}

    @property
    def source_name(self) -> str:
        return "rss"

    async def extract(self, since_hours: int = 48) -> list[ExtractedItem]:
        """Extract recent posts from all configured RSS feeds.

        Uses a 48-hour lookback window by default (since trusted sources
        may not post daily). No keyword filtering is applied.
        """
        settings = get_settings()
        feeds = settings.rss_feeds_list
        max_items = settings.max_items_per_source

        cutoff = datetime.now(tz=UTC) - timedelta(hours=since_hours)
        seen_urls: set[str] = set()
        items: list[ExtractedItem] = []

        with extractor_duration_seconds.labels(source=self.source_name).time():
            async with httpx.AsyncClient(
                timeout=30,
                headers={"User-Agent": "AI-News-Platform/1.0"},
            ) as client:
                for feed_url in feeds:
                    try:
                        new_items = await self._fetch_feed(client, feed_url, cutoff, seen_urls)
                        items.extend(new_items)
                    except Exception as exc:
                        logger.warning(
                            "rss_fetch_failed",
                            feed_url=feed_url,
                            error=str(exc),
                        )
                        continue

        items.sort(key=lambda x: x.published_at or datetime.min.replace(tzinfo=UTC), reverse=True)
        items = items[:max_items]

        items_extracted_total.labels(source=self.source_name).inc(len(items))
        logger.info(
            "extraction_complete",
            source=self.source_name,
            count=len(items),
            feeds=len(feeds),
        )

        if not items:
            extractor_errors_total.labels(source=self.source_name).inc()

        return items

    async def _fetch_feed(
        self,
        client: httpx.AsyncClient,
        feed_url: str,
        cutoff: datetime,
        seen_urls: set[str],
    ) -> list[ExtractedItem]:
        """Fetch and parse a single RSS/Atom feed."""
        # Build conditional request headers from cache
        headers: dict[str, str] = {}
        cached = self._etag_cache.get(feed_url, {})
        if cached.get("etag"):
            headers["If-None-Match"] = cached["etag"]
        if cached.get("last_modified"):
            headers["If-Modified-Since"] = cached["last_modified"]

        resp = await client.get(feed_url, headers=headers)

        # 304 Not Modified: feed unchanged since last fetch
        if resp.status_code == 304:
            logger.info("rss_feed_unchanged", feed_url=feed_url)
            return []

        resp.raise_for_status()

        # Store conditional request headers for next fetch
        new_cache: dict[str, str] = {}
        if resp.headers.get("etag"):
            new_cache["etag"] = resp.headers["etag"]
        if resp.headers.get("last-modified"):
            new_cache["last_modified"] = resp.headers["last-modified"]
        if new_cache:
            self._etag_cache[feed_url] = new_cache

        feed = feedparser.parse(resp.text)
        source_name = self._get_source_name(feed, feed_url)
        items: list[ExtractedItem] = []

        for entry in feed.entries:
            # Get entry URL for dedup
            entry_url = entry.get("link", "") or ""
            if not entry_url:
                continue

            # Dedup by URL
            if entry_url in seen_urls:
                continue
            seen_urls.add(entry_url)

            # 48h lookback window
            published = self._parse_published(entry)
            if published and published < cutoff:
                continue

            title = entry.get("title", "")
            text = self._extract_text(entry)
            author = self._extract_author(entry)
            tags = self._extract_tags(entry)

            url_hash = hashlib.sha256(entry_url.encode()).hexdigest()[:16]

            items.append(
                ExtractedItem(
                    title=title,
                    source=self.source_name,
                    url=entry_url,
                    text=text,
                    author=author,
                    published_at=published,
                    score=0,
                    metadata={
                        "feed_url": feed_url,
                        "source_name": source_name,
                        "tags": tags,
                        "rss_id": f"rss-{url_hash}",
                    },
                )
            )

        return items

    @staticmethod
    def _get_source_name(feed: feedparser.FeedParserDict, feed_url: str) -> str:
        """Extract a human-readable source name from the feed or URL."""
        if hasattr(feed, "feed") and hasattr(feed.feed, "title") and feed.feed.title:
            return feed.feed.title
        # Fallback to domain
        parsed = urlparse(feed_url)
        return parsed.netloc or feed_url

    @staticmethod
    def _extract_text(entry: dict) -> str:
        """Extract and clean text content from an entry."""
        # Try content field first (Atom feeds)
        if hasattr(entry, "content") and entry.content:
            raw = entry.content[0].get("value", "")
        elif hasattr(entry, "summary") and entry.summary:
            raw = entry.summary
        elif hasattr(entry, "description") and entry.description:
            raw = entry.description
        else:
            raw = ""

        return RSSExtractor._strip_html(raw)

    @staticmethod
    def _strip_html(text: str) -> str:
        """Remove HTML tags and normalize whitespace."""
        # Remove HTML tags
        text = re.sub(r"<[^>]+>", "", text)
        # Decode common HTML entities
        text = text.replace("&amp;", "&")
        text = text.replace("&lt;", "<")
        text = text.replace("&gt;", ">")
        text = text.replace("&quot;", '"')
        text = text.replace("&#39;", "'")
        text = text.replace("&nbsp;", " ")
        # Normalize whitespace
        text = re.sub(r"\s+", " ", text)
        return text.strip()

    @staticmethod
    def _extract_author(entry: dict) -> str:
        """Extract author name from entry."""
        if hasattr(entry, "authors") and entry.authors:
            return ", ".join(a.get("name", "") for a in entry.authors if a.get("name"))
        if hasattr(entry, "author") and entry.author:
            return entry.author
        return "unknown"

    @staticmethod
    def _extract_tags(entry: dict) -> list[str]:
        """Extract tags/categories from entry."""
        if hasattr(entry, "tags") and entry.tags:
            return [t.get("term", "") for t in entry.tags if t.get("term")]
        return []

    @staticmethod
    def _parse_published(entry: dict) -> datetime | None:
        """Parse the published date from an entry."""
        if hasattr(entry, "published_parsed") and entry.published_parsed:
            try:
                return datetime.fromtimestamp(mktime(entry.published_parsed), tz=UTC)
            except (ValueError, OverflowError, OSError):
                pass
        if hasattr(entry, "updated_parsed") and entry.updated_parsed:
            try:
                return datetime.fromtimestamp(mktime(entry.updated_parsed), tz=UTC)
            except (ValueError, OverflowError, OSError):
                pass
        return None
