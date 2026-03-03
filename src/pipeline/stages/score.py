"""Scoring stage — apply composite scoring to classified items."""

from __future__ import annotations

from src.classifiers.base import ClassifiedItem
from src.core.logging import get_logger
from src.pipeline.composite_scorer import CompositeScorer

logger = get_logger(__name__)


def run_scoring(items: list[ClassifiedItem]) -> list[ClassifiedItem]:
    """Apply composite scoring to all classified items."""
    if not items:
        return []

    scorer = CompositeScorer()
    scored = scorer.score_batch(items)
    logger.info("scoring_complete", count=len(scored))
    return scored
