"""Test data factories for creating ExtractedItem and ClassifiedItem instances."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from src.classifiers.base import ClassifiedItem
from src.extractors.base import ExtractedItem


def make_extracted_item(
    title: str = "Test AI Breakthrough",
    source: str = "hackernews",
    url: str | None = "https://example.com/article-1",
    text: str | None = "This is the body text of the article about AI.",
    author: str | None = "testuser",
    published_at: datetime | None = None,
    score: int | None = 42,
    metadata: dict[str, Any] | None = None,
) -> ExtractedItem:
    """Create an ExtractedItem with sensible defaults.

    All parameters can be overridden for specific test scenarios.
    """
    return ExtractedItem(
        title=title,
        source=source,
        url=url,
        text=text,
        author=author,
        published_at=published_at or datetime(2025, 6, 15, 12, 0, 0, tzinfo=UTC),
        score=score,
        metadata=metadata or {},
    )


def make_classified_item(
    title: str = "Test AI Breakthrough",
    source: str = "hackernews",
    url: str | None = "https://example.com/article-1",
    text: str | None = "This is the body text of the article about AI.",
    topic: str = "modelos",
    relevance_score: float = 0.92,
    dev_value_score: float | None = 0.85,
    summary: str | None = "Resumen de prueba sobre avances en IA.",
    priority: int = 2,
    trending: bool = False,
    source_count: int = 1,
    item: ExtractedItem | None = None,
) -> ClassifiedItem:
    """Create a ClassifiedItem with sensible defaults.

    Builds an internal ExtractedItem automatically unless one is provided.
    """
    if item is None:
        item = make_extracted_item(title=title, source=source, url=url, text=text)
    return ClassifiedItem(
        item=item,
        topic=topic,
        relevance_score=relevance_score,
        dev_value_score=dev_value_score,
        summary=summary,
        priority=priority,
        trending=trending,
        source_count=source_count,
    )
