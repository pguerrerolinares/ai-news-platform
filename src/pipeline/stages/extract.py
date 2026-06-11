"""Extraction stage — run all enabled extractors concurrently."""

from __future__ import annotations

import asyncio

from src.core.config import get_settings
from src.core.logging import get_logger
from src.extractors import EXTRACTOR_REGISTRY
from src.extractors.base import BaseExtractor, ExtractedItem

logger = get_logger(__name__)


def get_extractors(sources: list[str] | None = None) -> list[BaseExtractor]:
    """Build list of enabled extractors, optionally filtered by source names.

    Raises KeyError if a source name in ``enabled`` is not present in
    EXTRACTOR_REGISTRY (fail-fast on misconfiguration).
    """
    settings = get_settings()
    enabled = settings.enabled_sources_list

    if sources is not None:
        enabled = [s for s in enabled if s in sources]

    extractors: list[BaseExtractor] = []
    for source in enabled:
        if source not in EXTRACTOR_REGISTRY:
            raise KeyError(
                f"Unknown extractor source {source!r}. " f"Available: {sorted(EXTRACTOR_REGISTRY)}"
            )
        extractors.append(EXTRACTOR_REGISTRY[source]())

    return extractors


async def run_extraction(
    extractors: list[BaseExtractor],
    since_hours: int,
) -> list[ExtractedItem]:
    """Run all extractors concurrently and collect results."""

    async def _run_one(extractor: BaseExtractor) -> list[ExtractedItem]:
        try:
            items = await extractor.extract(since_hours=since_hours)
            logger.info(
                "extractor_result",
                source=extractor.source_name,
                count=len(items),
            )
            return items
        except Exception as exc:
            logger.error(
                "extractor_failed",
                source=extractor.source_name,
                error=str(exc),
            )
            return []

    results = await asyncio.gather(*[_run_one(ext) for ext in extractors])

    all_items: list[ExtractedItem] = []
    for result in results:
        all_items.extend(result)

    return all_items
