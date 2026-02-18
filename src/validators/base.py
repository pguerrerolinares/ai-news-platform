"""Base interface for all content validators."""

from __future__ import annotations

from abc import ABC, abstractmethod

from src.classifiers.base import ClassifiedItem


class BaseValidator(ABC):
    """Abstract base class for content validators.

    Validators check credibility, accessibility, and quality of classified items.
    """

    @abstractmethod
    async def validate(self, items: list[ClassifiedItem]) -> list[ClassifiedItem]:
        """Validate a batch of classified items.

        Sets credibility_score and may filter out low-quality items.

        Args:
            items: Classified items to validate.

        Returns:
            Validated items (may be fewer than input if items are filtered out).
        """
        ...
