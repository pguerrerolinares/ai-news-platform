"""Classification stage — LLM/keyword classify + event dedup + variant collapse."""

from __future__ import annotations

from src.classifiers.base import ClassifiedItem
from src.classifiers.event_dedup import deduplicate_events
from src.classifiers.keyword import KeywordClassifier
from src.classifiers.llm import LLMClassifier
from src.core.config import get_settings
from src.core.logging import get_logger
from src.core.metrics import classification_duration_seconds, items_classified_total
from src.extractors.base import ExtractedItem
from src.feed.variant_collapse import collapse_variants

logger = get_logger(__name__)


async def run_classification(items: list[ExtractedItem]) -> list[ClassifiedItem]:
    """Classify items, deduplicate events, and collapse HF variants.

    Steps:
    1. LLM or keyword classification
    2. Event deduplication (LLM only, >1 item)
    3. HuggingFace variant collapse
    """
    if not items:
        return []

    settings = get_settings()

    # 1. Classify.
    with classification_duration_seconds.time():
        classifier = LLMClassifier() if settings.openai_api_key else KeywordClassifier()
        classified = await classifier.classify(items)
    items_classified_total.inc(len(classified))
    logger.info("classification_complete", count=len(classified))

    # 2. Event dedup (fuzzy title matching, no LLM needed).
    if len(classified) > 1:
        classified = deduplicate_events(classified)
        logger.info("event_dedup_complete", count=len(classified))

    # 3. Variant collapse.
    before = len(classified)
    classified = collapse_variants(classified)
    logger.info("variant_collapse_complete", before=before, after=len(classified))

    return classified
