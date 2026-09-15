"""Structured output models and argument types for the MCP discovery tools."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

Topic = Literal["models", "tools", "papers", "products", "open_source", "agents", "regulation"]
Source = Literal[
    "github", "arxiv", "rss", "hackernews", "huggingface", "github_search", "webscraper"
]
SearchMode = Literal["semantic", "keyword"]
TrendMethod = Literal["keyword", "semantic"]
Granularity = Literal["week", "month"]


def _day(value: str | None) -> str | None:
    return value[:10] if value else None


class ItemSummary(BaseModel):
    id: str
    title: str
    source: str
    topic: str | None = None
    published_at: str | None = Field(
        None, description="YYYY-MM-DD; publication date, or first capture for repos/models"
    )
    composite_score: float | None = Field(
        None, description="0-1 cross-source rank (velocity, relevance, recency, topic)"
    )
    summary: str | None = None
    url: str | None = None

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> ItemSummary:
        score = data.get("composite_score")
        return cls(
            id=str(data["id"]),
            title=data["title"],
            source=data["source"],
            topic=data.get("topic"),
            published_at=_day(data.get("published_at") or data.get("created_at")),
            composite_score=round(score, 3) if score is not None else None,
            summary=data.get("summary"),
            url=data.get("url"),
        )


class Engagement(BaseModel):
    kind: Literal["points", "stars", "downloads", "upvotes"]
    value: int


class ItemDetail(ItemSummary):
    author: str | None = None
    full_text: str | None = Field(None, description="Complete stored text, never truncated")
    discussion_url: str | None = Field(None, description="Hacker News thread, when available")
    engagement: Engagement | None = Field(
        None, description="Null for sources without an engagement signal (arxiv, rss, webscraper)"
    )

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> ItemDetail:
        engagement = data.get("engagement")
        return cls(
            **ItemSummary.from_api(data).model_dump(),
            author=data.get("author"),
            full_text=data.get("full_text"),
            discussion_url=data.get("discussion_url"),
            engagement=Engagement(**engagement) if engagement else None,
        )


class SearchResult(BaseModel):
    query: str
    mode: SearchMode
    items: list[ItemSummary]


class SimilarResult(BaseModel):
    item_id: str
    items: list[ItemSummary]


class TrendBucketOut(BaseModel):
    bucket: str
    count: int
    total_in_bucket: int
    share: float
    by_source: dict[str, int]
    by_distance: dict[str, int] | None = None


class TrendResult(BaseModel):
    query: str
    method: TrendMethod
    granularity: Granularity
    since: str
    max_distance: float | None = None
    distance_edges: list[float] | None = None
    buckets: list[TrendBucketOut]


class TopResult(BaseModel):
    days: int
    topic: str | None = None
    source: str | None = None
    items: list[ItemSummary]
