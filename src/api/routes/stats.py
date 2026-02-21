"""API routes for aggregate statistics."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, Query, Request
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.auth import require_auth
from src.api.schemas import StatsDateResponse, StatsGroupResponse, StatsSummaryResponse
from src.core.database import get_session
from src.core.models import NewsItem

router = APIRouter(prefix="/api/stats", tags=["stats"])
limiter = Limiter(key_func=get_remote_address)


@router.get("/summary", response_model=StatsSummaryResponse)
@limiter.limit("30/minute")
async def stats_summary(
    request: Request,
    session: AsyncSession = Depends(get_session),
    _user: str = Depends(require_auth),
) -> StatsSummaryResponse:
    """Get summary statistics for the platform."""
    today = datetime.now(tz=UTC).date()

    total = (await session.execute(select(func.count(NewsItem.id)))).scalar_one()
    items_today = (
        await session.execute(
            select(func.count(NewsItem.id)).where(func.date(NewsItem.created_at) == today)
        )
    ).scalar_one()
    sources = (
        await session.execute(select(func.count(func.distinct(NewsItem.source))))
    ).scalar_one()
    topics = (
        await session.execute(
            select(func.count(func.distinct(NewsItem.topic))).where(NewsItem.topic.isnot(None))
        )
    ).scalar_one()
    trending = (
        await session.execute(
            select(func.count(NewsItem.id)).where(
                NewsItem.trending.is_(True), func.date(NewsItem.created_at) == today
            )
        )
    ).scalar_one()

    return StatsSummaryResponse(
        total_items=total,
        items_today=items_today,
        sources_count=sources,
        topics_count=topics,
        trending_today=trending,
    )


@router.get("/by-source", response_model=list[StatsGroupResponse])
@limiter.limit("30/minute")
async def stats_by_source(
    request: Request,
    session: AsyncSession = Depends(get_session),
    _user: str = Depends(require_auth),
) -> list[StatsGroupResponse]:
    """Get item count grouped by source."""
    result = await session.execute(
        select(NewsItem.source, func.count(NewsItem.id).label("count"))
        .group_by(NewsItem.source)
        .order_by(func.count(NewsItem.id).desc())
    )
    return [StatsGroupResponse(name=row.source, count=row.count) for row in result.all()]


@router.get("/by-topic", response_model=list[StatsGroupResponse])
@limiter.limit("30/minute")
async def stats_by_topic(
    request: Request,
    session: AsyncSession = Depends(get_session),
    _user: str = Depends(require_auth),
) -> list[StatsGroupResponse]:
    """Get item count grouped by topic."""
    result = await session.execute(
        select(NewsItem.topic, func.count(NewsItem.id).label("count"))
        .where(NewsItem.topic.isnot(None))
        .group_by(NewsItem.topic)
        .order_by(func.count(NewsItem.id).desc())
    )
    return [StatsGroupResponse(name=row.topic, count=row.count) for row in result.all()]


@router.get("/by-date", response_model=list[StatsDateResponse])
@limiter.limit("30/minute")
async def stats_by_date(
    request: Request,
    days: int = Query(30, ge=1, le=365, description="Number of days to include"),
    session: AsyncSession = Depends(get_session),
    _user: str = Depends(require_auth),
) -> list[StatsDateResponse]:
    """Get item count grouped by date for the last N days."""
    since = datetime.now(tz=UTC).date() - timedelta(days=days)
    result = await session.execute(
        select(
            func.date(NewsItem.created_at).label("date"),
            func.count(NewsItem.id).label("count"),
        )
        .where(func.date(NewsItem.created_at) >= since)
        .group_by(func.date(NewsItem.created_at))
        .order_by(func.date(NewsItem.created_at).desc())
    )
    return [StatsDateResponse(date=row.date, count=row.count) for row in result.all()]
