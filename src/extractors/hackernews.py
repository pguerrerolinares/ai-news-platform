"""HackerNews extractor using the Algolia Search API.

API docs: https://hn.algolia.com/api
- Free, no auth required
- Supports keyword search + numeric filters (points, date)
- Returns: title, url, points, num_comments, created_at
"""

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

BASE_URL = "https://hn.algolia.com/api/v1/search"


class HackerNewsExtractor(BaseExtractor):
    """Extracts AI-related stories from HackerNews via Algolia Search."""

    @property
    def source_name(self) -> str:
        return "hackernews"

    async def extract(self, since_hours: int = 24) -> list[ExtractedItem]:
        """Extract AI stories from HN.

        Performs one search per query keyword, deduplicates by story ID,
        returns items sorted by points descending.
        """
        settings = get_settings()
        min_points = settings.hn_min_points
        queries = settings.hn_search_queries_list
        max_items = settings.max_items_per_source

        since_ts = int((datetime.now(tz=UTC) - timedelta(hours=since_hours)).timestamp())
        seen_ids: set[str] = set()
        items: list[ExtractedItem] = []

        with extractor_duration_seconds.labels(source=self.source_name).time():
            async with httpx.AsyncClient(
                timeout=30,
                headers={"User-Agent": "AI-News-Platform/1.0"},
            ) as client:
                for query in queries:
                    try:
                        new_items = await self._search(
                            client, query, since_ts, min_points, seen_ids
                        )
                        items.extend(new_items)
                    except Exception as exc:
                        logger.warning(
                            "hn_search_failed",
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
            min_points=min_points,
        )

        if not items:
            extractor_errors_total.labels(source=self.source_name).inc()

        return items

    async def _search(
        self,
        client: httpx.AsyncClient,
        query: str,
        since_ts: int,
        min_points: int,
        seen_ids: set[str],
    ) -> list[ExtractedItem]:
        """Search HN Algolia for a single query."""
        params = {
            "query": query,
            "tags": "story",
            "numericFilters": f"created_at_i>{since_ts},points>{min_points}",
            "hitsPerPage": 50,
        }

        resp = await client.get(BASE_URL, params=params)
        resp.raise_for_status()
        data = resp.json()

        items: list[ExtractedItem] = []
        for hit in data.get("hits", []):
            story_id = hit.get("objectID", "")
            if story_id in seen_ids:
                continue
            seen_ids.add(story_id)

            url = hit.get("url") or f"https://news.ycombinator.com/item?id={story_id}"
            hn_url = f"https://news.ycombinator.com/item?id={story_id}"

            try:
                created_at = datetime.fromtimestamp(hit.get("created_at_i", 0), tz=UTC)
            except (ValueError, OSError):
                created_at = datetime.now(tz=UTC)

            items.append(
                ExtractedItem(
                    title=hit.get("title", ""),
                    source=self.source_name,
                    url=url,
                    text=hit.get("title", ""),
                    author=hit.get("author", "unknown"),
                    published_at=created_at,
                    score=hit.get("points", 0),
                    metadata={
                        "num_comments": hit.get("num_comments", 0),
                        "story_id": story_id,
                        "hn_url": hn_url,
                        "search_query": query,
                    },
                )
            )

        return items
