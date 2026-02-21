"""Historical extractors with pagination for backfill."""

from __future__ import annotations

import asyncio
from calendar import monthrange
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import httpx

from src.core.logging import get_logger

logger = get_logger(__name__)

HN_BASE_URL = "https://hn.algolia.com/api/v1/search"
GH_SEARCH_URL = "https://api.github.com/search/repositories"
HF_API_URL = "https://huggingface.co/api/models"


def generate_month_ranges(from_month: str, to_month: str) -> list[tuple[str, str]]:
    """Generate (start, end) month pairs from 'YYYY-MM' strings."""
    ranges: list[tuple[str, str]] = []
    year, month = map(int, from_month.split("-"))
    to_year, to_month_int = map(int, to_month.split("-"))

    while (year, month) <= (to_year, to_month_int):
        start = f"{year:04d}-{month:02d}"
        ny, nm = (year + 1, 1) if month == 12 else (year, month + 1)
        end = f"{ny:04d}-{nm:02d}"
        ranges.append((start, end))
        year, month = ny, nm

    return ranges


def _month_to_ts(month_str: str) -> int:
    """Convert 'YYYY-MM' to unix timestamp at start of month."""
    y, m = map(int, month_str.split("-"))
    return int(datetime(y, m, 1, tzinfo=UTC).timestamp())


@dataclass
class RawItem:
    """Minimal container for a raw API response + metadata."""

    source: str
    source_id: str
    raw_json: dict[str, Any]
    title: str = ""
    score: int = 0
    published_at: datetime | None = None


class HistoricalHNExtractor:
    """Paginated HackerNews extractor via Algolia Search API."""

    def __init__(self, min_points: int = 50, queries: list[str] | None = None) -> None:
        self.min_points = min_points
        self.queries = queries or [
            "AI",
            "LLM",
            "GPT",
            "machine learning",
            "neural network",
            "deep learning",
        ]

    async def fetch_month(
        self,
        client: httpx.AsyncClient,
        start_month: str,
        end_month: str,
    ) -> list[RawItem]:
        """Fetch all HN stories for a month range, paginating through all pages."""
        since_ts = _month_to_ts(start_month)
        until_ts = _month_to_ts(end_month)
        seen_ids: set[str] = set()
        items: list[RawItem] = []

        for query in self.queries:
            page = 0
            while True:
                params = {
                    "query": query,
                    "tags": "story",
                    "numericFilters": (
                        f"created_at_i>{since_ts},"
                        f"created_at_i<{until_ts},"
                        f"points>{self.min_points}"
                    ),
                    "hitsPerPage": 50,
                    "page": page,
                }

                resp = await client.get(HN_BASE_URL, params=params)
                resp.raise_for_status()
                data = resp.json()

                for hit in data.get("hits", []):
                    story_id = hit.get("objectID", "")
                    if story_id in seen_ids:
                        continue
                    seen_ids.add(story_id)

                    try:
                        created_at = datetime.fromtimestamp(hit.get("created_at_i", 0), tz=UTC)
                    except (ValueError, OSError):
                        created_at = None

                    items.append(
                        RawItem(
                            source="hackernews",
                            source_id=story_id,
                            raw_json=hit,
                            title=hit.get("title", ""),
                            score=hit.get("points", 0),
                            published_at=created_at,
                        )
                    )

                nb_pages = data.get("nbPages", 1)
                page += 1
                if page >= nb_pages:
                    break

                await asyncio.sleep(0.5)

        logger.info(
            "hn_month_fetched",
            month=start_month,
            items=len(items),
            queries=len(self.queries),
        )
        return items


class HistoricalGitHubExtractor:
    """Paginated GitHub Search extractor."""

    def __init__(
        self,
        min_stars: int = 200,
        queries: list[str] | None = None,
        token: str = "",
    ) -> None:
        self.min_stars = min_stars
        self.queries = queries or ["AI", "LLM", "machine-learning", "generative-AI"]
        self.token = token

    async def fetch_month(
        self,
        client: httpx.AsyncClient,
        start_month: str,
        end_month: str,
    ) -> list[RawItem]:
        """Fetch repos pushed during a month range, with pagination (max 1000/query)."""
        y, m = map(int, start_month.split("-"))
        _, last_day = monthrange(y, m)
        date_from = f"{start_month}-01"
        date_to = f"{start_month}-{last_day:02d}"

        seen_names: set[str] = set()
        items: list[RawItem] = []

        for query in self.queries:
            page = 1
            while page <= 10:
                q = f"{query} stars:>{self.min_stars} pushed:{date_from}..{date_to}"
                params = {
                    "q": q,
                    "sort": "stars",
                    "order": "desc",
                    "per_page": 100,
                    "page": page,
                }

                resp = await client.get(GH_SEARCH_URL, params=params)
                resp.raise_for_status()
                data = resp.json()

                repos = data.get("items", [])
                if not repos:
                    break

                for repo in repos:
                    full_name = repo.get("full_name", "")
                    if full_name in seen_names:
                        continue
                    seen_names.add(full_name)

                    try:
                        pushed = datetime.fromisoformat(
                            repo.get("pushed_at", "").replace("Z", "+00:00")
                        )
                    except (ValueError, AttributeError):
                        pushed = None

                    items.append(
                        RawItem(
                            source="github",
                            source_id=full_name,
                            raw_json=repo,
                            title=repo.get("full_name", ""),
                            score=repo.get("stargazers_count", 0),
                            published_at=pushed,
                        )
                    )

                page += 1
                await asyncio.sleep(2)

                remaining = resp.headers.get("X-RateLimit-Remaining")
                if remaining and int(remaining) <= 2:
                    reset_ts = int(resp.headers.get("X-RateLimit-Reset", "0"))
                    wait = max(0, reset_ts - int(datetime.now(tz=UTC).timestamp())) + 1
                    logger.info("github_rate_limit_wait", seconds=wait)
                    await asyncio.sleep(wait)

        logger.info("github_month_fetched", month=start_month, items=len(items))
        return items


class HistoricalHFExtractor:
    """HuggingFace models extractor with offset pagination."""

    def __init__(self, min_downloads: int = 100, since_date: str = "2023-01") -> None:
        self.min_downloads = min_downloads
        self.since_ts = _month_to_ts(since_date)

    async def fetch_all(self, client: httpx.AsyncClient, max_items: int = 2000) -> list[RawItem]:
        """Fetch top models by downloads, filter by lastModified date."""
        seen_ids: set[str] = set()
        items: list[RawItem] = []
        offset = 0
        limit = 100

        while offset < max_items:
            params = {
                "sort": "downloads",
                "direction": "-1",
                "limit": limit,
                "offset": offset,
            }

            resp = await client.get(HF_API_URL, params=params)
            resp.raise_for_status()
            models = resp.json()

            if not models:
                break

            for model in models:
                model_id = model.get("modelId") or model.get("id", "")
                if model_id in seen_ids:
                    continue
                seen_ids.add(model_id)

                downloads = model.get("downloads", 0)
                if downloads < self.min_downloads:
                    continue

                try:
                    last_mod = datetime.fromisoformat(
                        model.get("lastModified", "").replace("Z", "+00:00")
                    )
                except (ValueError, AttributeError):
                    continue

                if last_mod.timestamp() < self.since_ts:
                    continue

                items.append(
                    RawItem(
                        source="huggingface",
                        source_id=model_id,
                        raw_json=model,
                        title=model_id,
                        score=downloads,
                        published_at=last_mod,
                    )
                )

            offset += limit
            await asyncio.sleep(1)

        logger.info("hf_fetched", items=len(items))
        return items
