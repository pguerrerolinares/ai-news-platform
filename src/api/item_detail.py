"""Detail view of a news item: full text, discussion link and typed engagement."""

from __future__ import annotations

from typing import Any

from src.api.schemas import (
    EngagementKind,
    EngagementResponse,
    NewsItemDetailResponse,
    NewsItemResponse,
)
from src.core.models import NewsItem

_KIND_BY_SOURCE: dict[str, EngagementKind] = {
    "hackernews": "points",
    "github": "stars",
    "github_search": "stars",
}
_KIND_BY_HF_TYPE: dict[str, EngagementKind] = {
    "model": "downloads",
    "daily_paper": "upvotes",
}


def engagement_for(
    source: str, score: int | None, metadata: dict[str, Any] | None
) -> EngagementResponse | None:
    """Typed engagement for sources whose score means something, else None.

    arxiv, rss and webscraper store score=0 (no engagement signal). Hugging Face mixes
    model downloads and daily-paper upvotes, told apart by ``metadata["type"]``; an HF
    item without a type gets None rather than a guess.
    """
    if score is None:
        return None
    if source == "huggingface":
        kind = _KIND_BY_HF_TYPE.get(str((metadata or {}).get("type", "")))
    else:
        kind = _KIND_BY_SOURCE.get(source)
    return EngagementResponse(kind=kind, value=score) if kind else None


def discussion_url_for(metadata: dict[str, Any] | None) -> str | None:
    """Hacker News thread URL when the extractor stored one."""
    value = (metadata or {}).get("hn_url")
    return value if isinstance(value, str) else None


def to_item_detail(item: NewsItem) -> NewsItemDetailResponse:
    """Build the detail response (full_text is never truncated)."""
    base = NewsItemResponse.model_validate(item)
    return NewsItemDetailResponse(
        **base.model_dump(),
        full_text=item.full_text,
        discussion_url=discussion_url_for(item.metadata_),
        engagement=engagement_for(item.source, item.score, item.metadata_),
    )
