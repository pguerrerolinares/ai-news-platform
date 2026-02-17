"""API routes for news items."""

from __future__ import annotations

from datetime import UTC, date, datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.auth import require_auth
from src.api.schemas import NewsItemResponse
from src.core.database import get_session
from src.core.models import NewsItem

router = APIRouter(prefix="/api/items", tags=["items"])


@router.get("", response_model=list[NewsItemResponse])
async def list_items(
    source: str | None = Query(None, description="Filter by source"),
    topic: str | None = Query(None, description="Filter by topic"),
    date_from: date | None = Query(None, description="Start date (inclusive)"),
    date_to: date | None = Query(None, description="End date (inclusive)"),
    trending: bool | None = Query(None, description="Filter trending items only"),
    limit: int = Query(50, ge=1, le=200, description="Max items to return"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    session: AsyncSession = Depends(get_session),
    _user: str = Depends(require_auth),
) -> list[NewsItemResponse]:
    """List news items with optional filters."""
    query = select(NewsItem)

    if source:
        query = query.where(NewsItem.source == source)
    if topic:
        query = query.where(NewsItem.topic == topic)
    if date_from:
        query = query.where(func.date(NewsItem.published_at) >= date_from)
    if date_to:
        query = query.where(func.date(NewsItem.published_at) <= date_to)
    if trending is not None:
        query = query.where(NewsItem.trending == trending)

    query = query.order_by(NewsItem.published_at.desc()).offset(offset).limit(limit)

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


@router.get("/count")
async def count_items(
    source: str | None = Query(None),
    topic: str | None = Query(None),
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    session: AsyncSession = Depends(get_session),
    _user: str = Depends(require_auth),
) -> dict[str, int]:
    """Count items matching filters."""
    query = select(func.count(NewsItem.id))

    if source:
        query = query.where(NewsItem.source == source)
    if topic:
        query = query.where(NewsItem.topic == topic)
    if date_from:
        query = query.where(func.date(NewsItem.published_at) >= date_from)
    if date_to:
        query = query.where(func.date(NewsItem.published_at) <= date_to)

    result = await session.execute(query)
    count = result.scalar_one()

    return {"count": count}


@router.get("/today", response_model=list[NewsItemResponse])
async def list_today_items(
    limit: int = Query(100, ge=1, le=200),
    session: AsyncSession = Depends(get_session),
    _user: str = Depends(require_auth),
) -> list[NewsItemResponse]:
    """List today's news items, sorted by score descending."""
    today = datetime.now(tz=UTC).date()

    query = (
        select(NewsItem)
        .where(func.date(NewsItem.created_at) == today)
        .order_by(NewsItem.score.desc().nulls_last())
        .limit(limit)
    )

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
