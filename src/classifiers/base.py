"""Base interface for all content classifiers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from src.extractors.base import ExtractedItem


@dataclass
class ClassifiedItem:
    """An item after classification with topic, relevance, and summary."""

    item: ExtractedItem
    topic: str  # models, papers, agents, products, tools, open_source, regulation
    relevance_score: float  # 0.0 - 1.0
    dev_value_score: float | None = None  # 0.0 - 1.0: utility for AI development
    credibility_score: float | None = None  # 0.0 - 1.0: source credibility
    summary: str | None = None  # English summary (max 25 words)
    priority: int = 3  # 1 (highest) - 5 (lowest)
    trending: bool = False
    source_count: int = 1
    composite_score: float | None = None  # 0.0-1.0, computed by CompositeScorer


class BaseClassifier(ABC):
    """Abstract base class for content classifiers.

    Classifiers assign topic, relevance score, and optional summary
    to extracted items.
    """

    @abstractmethod
    async def classify(self, items: list[ExtractedItem]) -> list[ClassifiedItem]:
        """Classify a batch of extracted items.

        Args:
            items: Raw extracted items to classify.

        Returns:
            Classified items (may be fewer than input if items are filtered out).
        """
        ...
