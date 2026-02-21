"""API routes for aggregate statistics."""

from datetime import UTC, datetime, time, timedelta

from fastapi import APIRouter, Depends, Query, Request
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.auth import require_auth
from src.api.schemas import (
    ErrorWrapper,
    StatsDateResponse,
    StatsGroupResponse,
    StatsSummaryResponse,
)
from src.core.database import get_session
from src.core.models import NewsItem

router = APIRouter(prefix="/api/stats", tags=["stats"])
limiter = Limiter(key_func=get_remote_address)


@router.get(
    "/summary",
    response_model=StatsSummaryResponse,
    responses={401: {"model": ErrorWrapper}},
)
@limiter.limit("30/minute")
async def stats_summary(
    request: Request,
    session: AsyncSession = Depends(get_session),
    _user: str = Depends(require_auth),
) -> StatsSummaryResponse:
    """Get summary statistics for the platform in a single query."""
    today_start = datetime.combine(datetime.now(tz=UTC).date(), time.min, tzinfo=UTC)
    today_end = today_start + timedelta(days=1)

    is_today = (NewsItem.created_at >= today_start) & (NewsItem.created_at < today_end)

    result = await session.execute(
        select(
            func.count(NewsItem.id).label("total"),
            func.count(case((is_today, NewsItem.id))).label("items_today"),
            func.count(func.distinct(NewsItem.source)).label("sources"),
            func.count(
                func.distinct(case((NewsItem.topic.isnot(None), NewsItem.topic)))
            ).label("topics"),
            func.count(
                case((NewsItem.trending.is_(True) & is_today, NewsItem.id))
            ).label("trending"),
        )
    )
    row = result.one()

    return StatsSummaryResponse(
        total_items=row.total,
        items_today=row.items_today,
        sources_count=row.sources,
        topics_count=row.topics,
        trending_today=row.trending,
    )


@router.get(
    "/by-source",
    response_model=list[StatsGroupResponse],
    responses={401: {"model": ErrorWrapper}},
)
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


@router.get(
    "/by-topic",
    response_model=list[StatsGroupResponse],
    responses={401: {"model": ErrorWrapper}},
)
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


@router.get(
    "/by-date",
    response_model=list[StatsDateResponse],
    responses={401: {"model": ErrorWrapper}},
)
@limiter.limit("30/minute")
async def stats_by_date(
    request: Request,
    days: int = Query(30, ge=1, le=365, description="Number of days to include"),
    session: AsyncSession = Depends(get_session),
    _user: str = Depends(require_auth),
) -> list[StatsDateResponse]:
    """Get item count grouped by date for the last N days."""
    since_date = datetime.now(tz=UTC).date() - timedelta(days=days)
    since_dt = datetime.combine(since_date, time.min, tzinfo=UTC)
    created_date = func.date(NewsItem.created_at)
    result = await session.execute(
        select(
            created_date.label("date"),
            func.count(NewsItem.id).label("count"),
        )
        .where(NewsItem.created_at >= since_dt)
        .group_by(created_date)
        .order_by(created_date.desc())
    )
    return [StatsDateResponse(date=row.date, count=row.count) for row in result.all()]
