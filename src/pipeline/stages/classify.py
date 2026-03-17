"""Classification stage — two-phase keyword/LLM + event dedup + variant collapse."""

from __future__ import annotations

from src.classifiers.base import ClassifiedItem
from src.classifiers.event_dedup import deduplicate_events
from src.classifiers.keyword import (
    KeywordClassifier,
    _calculate_priority,
    classify_by_keywords,
)
from src.classifiers.llm import LLMClassifier
from src.core.config import get_settings
from src.core.logging import get_logger
from src.core.metrics import classification_duration_seconds, items_classified_total
from src.extractors.base import ExtractedItem
from src.feed.variant_collapse import collapse_variants

logger = get_logger(__name__)

# Items with >= this many keyword matches skip LLM (high confidence)
_HIGH_CONFIDENCE_THRESHOLD = 3


async def run_classification(items: list[ExtractedItem]) -> list[ClassifiedItem]:
    """Classify items, deduplicate events, and collapse HF variants.

    Steps:
    1. Two-phase classification:
       a. Keyword pre-filter: >=3 matches → auto-accept, 0 → reject
       b. Ambiguous (1-2 matches) → LLM for precise topic + summary
    2. Event deduplication (fuzzy title matching)
    3. HuggingFace variant collapse
    """
    if not items:
        return []

    settings = get_settings()
    enabled_topics = settings.topics_list
    min_relevance = settings.min_relevance_score

    # 1. Two-phase classification.
    with classification_duration_seconds.time():
        auto_accepted: list[ClassifiedItem] = []
        ambiguous: list[ExtractedItem] = []

        for item in items:
            topic, relevance, match_count = classify_by_keywords(item)

            if match_count >= _HIGH_CONFIDENCE_THRESHOLD:
                # High confidence: auto-accept with keyword classification
                if topic and topic in enabled_topics and relevance >= min_relevance:
                    priority = _calculate_priority(item, relevance)
                    auto_accepted.append(
                        ClassifiedItem(
                            item=item,
                            topic=topic,
                            relevance_score=relevance,
                            summary=None,
                            priority=priority,
                        )
                    )
            elif match_count >= 1:
                # Ambiguous: send to LLM for precise classification + summary
                ambiguous.append(item)
            # match_count == 0: auto-reject (no AI keywords at all)

        # Classify ambiguous items via LLM (or keyword fallback if no API key)
        llm_classified: list[ClassifiedItem] = []
        if ambiguous:
            classifier = LLMClassifier() if settings.openai_api_key else KeywordClassifier()
            llm_classified = await classifier.classify(ambiguous)

        classified = auto_accepted + llm_classified

    items_classified_total.inc(len(classified))
    logger.info(
        "classification_complete",
        count=len(classified),
        auto_accepted=len(auto_accepted),
        llm_classified=len(llm_classified),
        rejected=len(items) - len(auto_accepted) - len(ambiguous),
    )

    # 2. Event dedup (fuzzy title matching, no LLM needed).
    if len(classified) > 1:
        classified = deduplicate_events(classified)
        logger.info("event_dedup_complete", count=len(classified))

    # 3. Variant collapse.
    before = len(classified)
    classified = collapse_variants(classified)
    logger.info("variant_collapse_complete", before=before, after=len(classified))

    return classified
