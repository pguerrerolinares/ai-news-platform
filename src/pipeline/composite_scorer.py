"""Composite scoring for news item ranking."""

from __future__ import annotations

from datetime import UTC, datetime

from src.classifiers.base import ClassifiedItem
from src.core.config import get_settings
from src.core.logging import get_logger

log = get_logger(__name__)

TOPIC_WEIGHTS: dict[str, float] = {
    "models": 1.0,
    "products": 1.0,
    "regulation": 1.0,
    "agents": 0.95,
    "tools": 0.85,
    "open_source": 0.85,
    "papers": 0.70,
}

DEFAULT_TOPIC_WEIGHT = 0.5

# Sources that have no engagement data
_NO_VELOCITY_SOURCES = frozenset({"arxiv", "rss"})

# Minimum age floor to avoid division by zero
_MIN_AGE_HOURS = 1.0
_MIN_AGE_DAYS = _MIN_AGE_HOURS / 24.0


def compute_velocity(
    source: str,
    score: int | None,
    source_created_at: datetime | None = None,
    published_at: datetime | None = None,
    metadata: dict | None = None,
    now: datetime | None = None,
) -> float | None:
    """Compute engagement velocity for a source.

    Returns None for sources without engagement data (arxiv, rss).
    """
    if source in _NO_VELOCITY_SOURCES:
        return None

    if score is None or score <= 0:
        return 0.0

    if now is None:
        now = datetime.now(UTC)

    metadata = metadata or {}

    if source == "github":
        # GitHub: stars / days since repo creation
        ref_date = source_created_at or published_at
        if ref_date is None:
            return 0.0
        age_days = max(_MIN_AGE_DAYS, (now - ref_date).total_seconds() / 86400)
        return score / age_days

    if source == "huggingface" and metadata.get("type") == "daily_paper":
        # HF papers: upvotes / hours since publication
        if published_at is None:
            return 0.0
        age_hours = max(_MIN_AGE_HOURS, (now - published_at).total_seconds() / 3600)
        return score / age_hours

    if source == "huggingface":
        # HF models: downloads field is already 24h velocity
        return float(score)

    # HN, Reddit: score / hours since publication
    if published_at is None:
        return 0.0
    age_hours = max(_MIN_AGE_HOURS, (now - published_at).total_seconds() / 3600)
    return score / age_hours


class CompositeScorer:
    """Computes composite ranking score from velocity, relevance, recency, topic."""

    def __init__(self) -> None:
        settings = get_settings()
        self._w_vel = settings.composite_w_velocity
        self._w_rel = settings.composite_w_relevance
        self._w_rec = settings.composite_w_recency
        self._w_top = settings.composite_w_topic
        self._nv_w_rel = settings.composite_no_velocity_w_relevance
        self._nv_w_rec = settings.composite_no_velocity_w_recency
        self._nv_w_top = settings.composite_no_velocity_w_topic
        self._recency_window = settings.composite_recency_window_hours
        self._velocity_thresholds = {
            "github": settings.velocity_threshold_github,
            "hackernews": settings.velocity_threshold_hackernews,
            "reddit": settings.velocity_threshold_reddit,
            "huggingface": settings.velocity_threshold_huggingface,
            "huggingface_paper": settings.velocity_threshold_huggingface_paper,
        }

    def _normalize_velocity(
        self, velocity: float, source: str, metadata: dict | None = None
    ) -> float:
        metadata = metadata or {}
        key = source
        if source == "huggingface" and metadata.get("type") == "daily_paper":
            key = "huggingface_paper"
        threshold = self._velocity_thresholds.get(key, 500.0)
        return min(1.0, velocity / threshold)

    def _normalize_relevance(self, relevance: float) -> float:
        return max(0.0, min(1.0, (relevance - 0.75) / 0.25))

    def _compute_recency(self, published_at: datetime | None, now: datetime) -> float:
        if published_at is None:
            return 0.0
        age_hours = (now - published_at).total_seconds() / 3600
        return max(0.0, 1.0 - (age_hours / self._recency_window))

    def score(self, item: ClassifiedItem, now: datetime | None = None) -> float:
        """Compute composite score for a single classified item."""
        if now is None:
            now = datetime.now(UTC)

        ei = item.item  # ExtractedItem
        relevance_norm = self._normalize_relevance(item.relevance_score)
        recency = self._compute_recency(ei.published_at, now)
        topic_weight = TOPIC_WEIGHTS.get(item.topic, DEFAULT_TOPIC_WEIGHT)

        velocity = compute_velocity(
            source=ei.source,
            score=ei.score,
            source_created_at=ei.source_created_at,
            published_at=ei.published_at,
            metadata=ei.metadata,
            now=now,
        )

        if velocity is None:
            # No velocity: Arxiv, RSS
            return (
                self._nv_w_rel * relevance_norm
                + self._nv_w_rec * recency
                + self._nv_w_top * topic_weight
            )

        velocity_norm = self._normalize_velocity(velocity, ei.source, ei.metadata)
        return (
            self._w_vel * velocity_norm
            + self._w_rel * relevance_norm
            + self._w_rec * recency
            + self._w_top * topic_weight
        )

    def score_batch(self, items: list[ClassifiedItem]) -> list[ClassifiedItem]:
        """Compute composite scores for a batch, setting composite_score on each."""
        now = datetime.now(UTC)
        for item in items:
            item.composite_score = self.score(item, now=now)
        log.info("composite_scoring_complete", count=len(items))
        return items
