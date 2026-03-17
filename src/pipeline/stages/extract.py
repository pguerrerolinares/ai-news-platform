"""Extraction stage — run all enabled extractors concurrently."""

from __future__ import annotations

import asyncio

from src.core.config import get_settings
from src.core.logging import get_logger
from src.extractors.arxiv import ArxivExtractor
from src.extractors.base import BaseExtractor, ExtractedItem
from src.extractors.github_trending import GitHubTrendingExtractor
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
        extractors.append(GitHubTrendingExtractor())
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
