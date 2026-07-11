"""Extraction stage — run all enabled extractors concurrently."""

from __future__ import annotations

import asyncio

from src.core.config import get_settings
from src.core.logging import get_logger
from src.core.metrics import extractor_errors_total
from src.extractors import load_extractor
from src.extractors.base import BaseExtractor, ExtractedItem
from src.pipeline.circuit_breaker import CircuitBreaker

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

    return [load_extractor(source)() for source in enabled]


async def run_extraction(
    extractors: list[BaseExtractor],
    since_hours: int,
    circuit_breaker: CircuitBreaker | None = None,
) -> list[ExtractedItem]:
    """Run all extractors concurrently and collect results.

    Each extractor's outcome is fed back into ``circuit_breaker`` (if given),
    per source: a failure trips that source's breaker without affecting the
    others, and a success resets it. A source whose circuit is already open
    is skipped without being called.
    """

    async def _run_one(extractor: BaseExtractor) -> list[ExtractedItem]:
        source = extractor.source_name

        if circuit_breaker is not None and circuit_breaker.is_open(source):
            logger.warning("extractor_skipped_circuit_open", source=source)
            return []

        try:
            items = await extractor.extract(since_hours=since_hours)
            logger.info(
                "extractor_result",
                source=source,
                count=len(items),
            )
            if circuit_breaker is not None:
                circuit_breaker.record_success(source)
            return items
        except Exception as exc:
            logger.error(
                "extractor_failed",
                source=source,
                error=str(exc),
            )
            extractor_errors_total.labels(source=source).inc()
            if circuit_breaker is not None:
                circuit_breaker.record_failure(source)
            return []

    results = await asyncio.gather(*[_run_one(ext) for ext in extractors])

    all_items: list[ExtractedItem] = []
    for result in results:
        all_items.extend(result)

    return all_items
