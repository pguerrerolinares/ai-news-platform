"""Base interface for all news extractors."""

from __future__ import annotations

import hashlib
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class ExtractedItem:
    """Raw item extracted from a source, before classification."""

    title: str
    source: str  # hackernews, arxiv, reddit, rss, github, huggingface
    url: str | None = None
    text: str | None = None
    author: str | None = None
    published_at: datetime | None = None
    score: int | None = None
    source_created_at: datetime | None = None  # actual creation date on source platform
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def content_hash(self) -> str:
        """Hash for deduplication based on title + url."""
        content = f"{self.title}|{self.url or ''}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    @property
    def url_hash(self) -> str | None:
        """Hash for URL-based deduplication."""
        if not self.url:
            return None
        return hashlib.sha256(self.url.encode()).hexdigest()[:16]


class BaseExtractor(ABC):
    """Abstract base class for all news extractors.

    Each extractor fetches items from a single source and returns
    a list of ExtractedItem instances.
    """

    @property
    @abstractmethod
    def source_name(self) -> str:
        """Unique identifier for this source (e.g., 'hackernews')."""
        ...

    @abstractmethod
    async def extract(self, since_hours: int = 24) -> list[ExtractedItem]:
        """Extract items from the source.

        Args:
            since_hours: Look back this many hours.

        Returns:
            List of extracted items, sorted by relevance/score descending.
        """
        ...
