"""Reddit extractor using the public JSON API.

Fetches top posts from configured subreddits (e.g. MachineLearning,
LocalLLaMA, artificial), skips stickied posts, and deduplicates by
Reddit post ID.

API endpoint: https://www.reddit.com/r/{subreddit}/top/.json?t=day&limit=25
"""

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

BASE_URL = "https://www.reddit.com"


class RedditExtractor(BaseExtractor):
    """Extracts AI-related posts from Reddit subreddits."""

    @property
    def source_name(self) -> str:
        return "reddit"

    async def extract(self, since_hours: int = 24) -> list[ExtractedItem]:
        """Extract top posts from configured subreddits.

        Fetches top daily posts, skips stickied posts, deduplicates by
        Reddit post ID, and sorts by score descending.
        """
        settings = get_settings()
        subreddits = settings.reddit_subreddits_list
        limit = settings.reddit_top_limit
        max_items = settings.max_items_per_source

        seen_ids: set[str] = set()
        items: list[ExtractedItem] = []

        with extractor_duration_seconds.labels(source=self.source_name).time():
            async with httpx.AsyncClient(
                timeout=30,
                headers={"User-Agent": "AI-News-Platform/1.0"},
            ) as client:
                for subreddit in subreddits:
                    try:
                        new_items = await self._fetch_subreddit(client, subreddit, limit, seen_ids)
                        items.extend(new_items)
                    except Exception as exc:
                        logger.warning(
                            "reddit_fetch_failed",
                            subreddit=subreddit,
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
            subreddits=len(subreddits),
        )

        if not items:
            extractor_errors_total.labels(source=self.source_name).inc()

        return items

    async def _fetch_subreddit(
        self,
        client: httpx.AsyncClient,
        subreddit: str,
        limit: int,
        seen_ids: set[str],
    ) -> list[ExtractedItem]:
        """Fetch top posts from a single subreddit."""
        url = f"{BASE_URL}/r/{subreddit}/top/.json"
        params = {"t": "day", "limit": limit}

        resp = await client.get(url, params=params)
        resp.raise_for_status()
        data = resp.json()

        items: list[ExtractedItem] = []
        children = data.get("data", {}).get("children", [])

        for child in children:
            post = child.get("data", {})

            # Skip stickied posts
            if post.get("stickied", False):
                continue

            post_id = post.get("id", "")
            if not post_id:
                continue

            # Dedup by post ID
            if post_id in seen_ids:
                continue
            seen_ids.add(post_id)

            # Handle self posts vs link posts
            is_self = post.get("is_self", False)
            permalink = f"https://www.reddit.com{post.get('permalink', '')}"
            if is_self:
                url = permalink
                text = post.get("selftext", "") or post.get("title", "")
            else:
                url = post.get("url", permalink)
                text = post.get("title", "")

            # Parse creation time
            created_utc = post.get("created_utc", 0)
            try:
                published = datetime.fromtimestamp(created_utc, tz=UTC)
            except (ValueError, OSError):
                published = datetime.now(tz=UTC)

            flair = post.get("link_flair_text", "") or ""
            domain = post.get("domain", "") or ""

            items.append(
                ExtractedItem(
                    title=post.get("title", ""),
                    source=self.source_name,
                    url=url,
                    text=text,
                    author=post.get("author", "unknown"),
                    published_at=published,
                    score=post.get("score", 0),
                    metadata={
                        "subreddit": subreddit,
                        "post_id": post_id,
                        "num_comments": post.get("num_comments", 0),
                        "upvote_ratio": post.get("upvote_ratio", 0.0),
                        "is_self": is_self,
                        "flair": flair,
                        "domain": domain,
                    },
                )
            )

        return items
