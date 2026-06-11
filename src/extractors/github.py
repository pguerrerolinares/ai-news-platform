"""GitHub Trending extractor via GitHub Search API."""

from __future__ import annotations

import asyncio
import html
from datetime import UTC, datetime, timedelta

import httpx

from src.core.config import get_settings
from src.core.dates import parse_iso_z
from src.core.logging import get_logger
from src.core.metrics import (
    extractor_duration_seconds,
    items_extracted_total,
)
from src.extractors.base import BaseExtractor, ExtractedItem

logger = get_logger(__name__)
SEARCH_URL = "https://api.github.com/search/repositories"


class GitHubExtractor(BaseExtractor):
    """Extracts trending AI repositories from GitHub Search API."""

    @property
    def source_name(self) -> str:
        return "github_search"

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
                        new_items, resp = await self._search(
                            client, query, since_date, min_stars, seen_urls
                        )
                        items.extend(new_items)
                        await self._check_rate_limit(resp)
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

        return items

    async def _search(
        self,
        client: httpx.AsyncClient,
        query: str,
        since_date: str,
        min_stars: int,
        seen_urls: set[str],
    ) -> tuple[list[ExtractedItem], httpx.Response]:
        q = f"{query} stars:>{min_stars} pushed:>={since_date}"
        params = {"q": q, "sort": "updated", "order": "desc", "per_page": 30}
        max_age_days = get_settings().github_max_repo_age_days

        resp = await client.get(SEARCH_URL, params=params)
        resp.raise_for_status()
        data = resp.json()

        items: list[ExtractedItem] = []
        for repo in data.get("items", []):
            url = repo.get("html_url", "")
            if url in seen_urls:
                continue
            seen_urls.add(url)

            name = html.unescape(repo.get("name", ""))
            description = html.unescape(repo.get("description") or "")
            title = f"{name}: {description}" if description else name

            pushed = parse_iso_z(repo.get("pushed_at", ""))
            created_at_dt = parse_iso_z(repo.get("created_at", ""))

            # Repo age filter: skip repos older than configured threshold
            if (
                created_at_dt is not None
                and max_age_days > 0
                and (datetime.now(tz=UTC) - created_at_dt).days > max_age_days
            ):
                continue

            items.append(
                ExtractedItem(
                    title=title,
                    source=self.source_name,
                    url=url,
                    text=description,
                    author=repo.get("owner", {}).get("login", "unknown"),
                    published_at=pushed,
                    score=repo.get("stargazers_count", 0),
                    source_created_at=created_at_dt,
                    metadata={
                        "language": repo.get("language"),
                        "stars": repo.get("stargazers_count", 0),
                        "forks": repo.get("forks_count", 0),
                        "topics": repo.get("topics", []),
                        "full_name": repo.get("full_name", ""),
                        "created_at": repo.get("created_at"),
                        "search_query": query,
                    },
                )
            )

        return items, resp

    async def _check_rate_limit(self, resp: httpx.Response) -> None:
        """Sleep if GitHub rate limit is nearly exhausted."""
        remaining = resp.headers.get("X-RateLimit-Remaining")
        if remaining is None:
            return
        try:
            if int(remaining) <= 1:
                reset_ts = int(resp.headers.get("X-RateLimit-Reset", "0"))
                now_ts = int(datetime.now(tz=UTC).timestamp())
                sleep_for = max(0, reset_ts - now_ts) + 1
                logger.info(
                    "github_rate_limit_near",
                    remaining=remaining,
                    sleep_seconds=sleep_for,
                )
                await asyncio.sleep(sleep_for)
        except (ValueError, TypeError):
            pass
