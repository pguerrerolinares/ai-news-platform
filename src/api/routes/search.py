"""API routes for full-text search."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.auth import require_auth
from src.api.schemas import NewsItemResponse
from src.core.database import get_session
from src.core.models import NewsItem

router = APIRouter(prefix="/api/search", tags=["search"])


@router.get("", response_model=list[NewsItemResponse])
async def search_items(
    q: str = Query(..., min_length=1, description="Search text"),
    topic: str | None = Query(None, description="Filter by topic"),
    date_from: date | None = Query(None, description="Start date (inclusive)"),
    date_to: date | None = Query(None, description="End date (inclusive)"),
    limit: int = Query(50, ge=1, le=200, description="Max results to return"),
    session: AsyncSession = Depends(get_session),
    _user: str = Depends(require_auth),
) -> list[NewsItemResponse]:
    """Search news items using PostgreSQL full-text search.

    Searches across title and full_text columns. Results are ranked by
    relevance and can be filtered by topic and date range.
    """
    ts_query = func.plainto_tsquery("english", q)
    ts_vector = func.to_tsvector(
        "english",
        func.coalesce(NewsItem.title, "") + " " + func.coalesce(NewsItem.full_text, ""),
    )

    query = select(NewsItem).where(ts_vector.bool_op("@@")(ts_query))

    if topic:
        query = query.where(NewsItem.topic == topic)
    if date_from:
        query = query.where(func.date(NewsItem.published_at) >= date_from)
    if date_to:
        query = query.where(func.date(NewsItem.published_at) <= date_to)

    query = query.order_by(func.ts_rank(ts_vector, ts_query).desc()).limit(limit)

    result = await session.execute(query)
    items = result.scalars().all()

    return [
        NewsItemResponse(
            id=item.id,
            title=item.title,
            summary=item.summary,
            url=item.url,
            source=item.source,
            topic=item.topic,
            relevance_score=item.relevance_score,
            dev_value_score=item.dev_value_score,
            credibility_score=item.credibility_score,
            priority=item.priority,
            trending=item.trending,
            published_at=item.published_at,
            created_at=item.created_at,
            author=item.author,
            score=item.score,
        )
        for item in items
    ]
