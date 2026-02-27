"""API routes for aggregate statistics."""

from datetime import UTC, datetime, time, timedelta

from fastapi import APIRouter, Depends, Query, Request
from slowapi import Limiter
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.auth import UserClaims, require_auth
from src.api.ratelimit import get_client_ip
from src.api.schemas import (
    ErrorWrapper,
    ScoreDistributionResponse,
    StatsDateResponse,
    StatsGroupDateResponse,
    StatsGroupResponse,
    StatsSummaryResponse,
)
from src.core.database import get_session
from src.core.models import NewsItem

router = APIRouter(prefix="/api/stats", tags=["stats"])
limiter = Limiter(key_func=get_client_ip)

# Effective date: prefer published_at, fall back to created_at for items without it
_effective_date = func.coalesce(NewsItem.published_at, NewsItem.created_at)


@router.get(
    "/summary",
    response_model=StatsSummaryResponse,
    responses={401: {"model": ErrorWrapper}},
)
@limiter.limit("30/minute")
async def stats_summary(
    request: Request,
    session: AsyncSession = Depends(get_session),
    _user: UserClaims = Depends(require_auth),
) -> StatsSummaryResponse:
    """Get summary statistics for the platform in a single query."""
    today_start = datetime.combine(datetime.now(tz=UTC).date(), time.min, tzinfo=UTC)
    today_end = today_start + timedelta(days=1)

    is_today = (_effective_date >= today_start) & (_effective_date < today_end)

    result = await session.execute(
        select(
            func.count(NewsItem.id).label("total"),
            func.count(case((is_today, NewsItem.id))).label("items_today"),
            func.count(func.distinct(NewsItem.source)).label("sources"),
            func.count(func.distinct(case((NewsItem.topic.isnot(None), NewsItem.topic)))).label(
                "topics"
            ),
            func.count(case((NewsItem.trending.is_(True) & is_today, NewsItem.id))).label(
                "trending"
            ),
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
    _user: UserClaims = Depends(require_auth),
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
    _user: UserClaims = Depends(require_auth),
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
    _user: UserClaims = Depends(require_auth),
) -> list[StatsDateResponse]:
    """Get item count grouped by date for the last N days."""
    since_date = datetime.now(tz=UTC).date() - timedelta(days=days)
    since_dt = datetime.combine(since_date, time.min, tzinfo=UTC)
    effective_date = func.date(_effective_date)
    result = await session.execute(
        select(
            effective_date.label("date"),
            func.count(NewsItem.id).label("count"),
        )
        .where(_effective_date >= since_dt)
        .group_by(effective_date)
        .order_by(effective_date.desc())
    )
    return [StatsDateResponse(date=row.date, count=row.count) for row in result.all()]


@router.get(
    "/by-topic-date",
    response_model=list[StatsGroupDateResponse],
    responses={401: {"model": ErrorWrapper}},
)
@limiter.limit("30/minute")
async def stats_by_topic_date(
    request: Request,
    days: int = Query(30, ge=1, le=365, description="Number of days to include"),
    session: AsyncSession = Depends(get_session),
    _user: UserClaims = Depends(require_auth),
) -> list[StatsGroupDateResponse]:
    """Get item count grouped by topic and date for the last N days."""
    since_dt = datetime.combine(
        (datetime.now(tz=UTC) - timedelta(days=days)).date(), time.min, tzinfo=UTC
    )
    effective_date = func.date(_effective_date)
    result = await session.execute(
        select(
            effective_date.label("date"),
            NewsItem.topic.label("group"),
            func.count(NewsItem.id).label("count"),
        )
        .where((_effective_date >= since_dt) & NewsItem.topic.isnot(None))
        .group_by(effective_date, NewsItem.topic)
        .order_by(effective_date.asc(), NewsItem.topic.asc())
    )
    return [
        StatsGroupDateResponse(date=row.date, group=row.group, count=row.count)
        for row in result.all()
    ]


@router.get(
    "/by-source-date",
    response_model=list[StatsGroupDateResponse],
    responses={401: {"model": ErrorWrapper}},
)
@limiter.limit("30/minute")
async def stats_by_source_date(
    request: Request,
    days: int = Query(30, ge=1, le=365, description="Number of days to include"),
    session: AsyncSession = Depends(get_session),
    _user: UserClaims = Depends(require_auth),
) -> list[StatsGroupDateResponse]:
    """Get item count grouped by source and date for the last N days."""
    since_dt = datetime.combine(
        (datetime.now(tz=UTC) - timedelta(days=days)).date(), time.min, tzinfo=UTC
    )
    effective_date = func.date(_effective_date)
    result = await session.execute(
        select(
            effective_date.label("date"),
            NewsItem.source.label("group"),
            func.count(NewsItem.id).label("count"),
        )
        .where(_effective_date >= since_dt)
        .group_by(effective_date, NewsItem.source)
        .order_by(effective_date.asc(), NewsItem.source.asc())
    )
    return [
        StatsGroupDateResponse(date=row.date, group=row.group, count=row.count)
        for row in result.all()
    ]


@router.get(
    "/trending-timeline",
    response_model=list[StatsDateResponse],
    responses={401: {"model": ErrorWrapper}},
)
@limiter.limit("30/minute")
async def stats_trending_timeline(
    request: Request,
    days: int = Query(30, ge=1, le=365, description="Number of days to include"),
    session: AsyncSession = Depends(get_session),
    _user: UserClaims = Depends(require_auth),
) -> list[StatsDateResponse]:
    """Get trending item count by date for the last N days."""
    since_dt = datetime.combine(
        (datetime.now(tz=UTC) - timedelta(days=days)).date(), time.min, tzinfo=UTC
    )
    effective_date = func.date(_effective_date)
    result = await session.execute(
        select(
            effective_date.label("date"),
            func.count(NewsItem.id).label("count"),
        )
        .where((_effective_date >= since_dt) & NewsItem.trending.is_(True))
        .group_by(effective_date)
        .order_by(effective_date.asc())
    )
    return [StatsDateResponse(date=row.date, count=row.count) for row in result.all()]


_SCORE_BUCKETS = [
    ("0-10", 0, 10),
    ("11-50", 11, 50),
    ("51-100", 51, 100),
    ("101-250", 101, 250),
    ("251-500", 251, 500),
    ("501+", 501, None),
]


@router.get(
    "/score-distribution",
    response_model=list[ScoreDistributionResponse],
    responses={401: {"model": ErrorWrapper}},
)
@limiter.limit("30/minute")
async def stats_score_distribution(
    request: Request,
    days: int = Query(30, ge=1, le=365, description="Number of days to include"),
    source: str | None = Query(None, description="Filter by source"),
    topic: str | None = Query(None, description="Filter by topic"),
    session: AsyncSession = Depends(get_session),
    _user: UserClaims = Depends(require_auth),
) -> list[ScoreDistributionResponse]:
    """Get score distribution as histogram buckets."""
    since_dt = datetime.combine(
        (datetime.now(tz=UTC) - timedelta(days=days)).date(), time.min, tzinfo=UTC
    )
    results: list[ScoreDistributionResponse] = []

    for label, min_score, max_score in _SCORE_BUCKETS:
        query = select(func.count(NewsItem.id)).where(
            (_effective_date >= since_dt) & NewsItem.score.isnot(None)
        )
        query = query.where(NewsItem.score >= min_score)
        if max_score is not None:
            query = query.where(NewsItem.score <= max_score)
        if source:
            query = query.where(NewsItem.source == source)
        if topic:
            query = query.where(NewsItem.topic == topic)

        count = (await session.execute(query)).scalar_one()
        results.append(
            ScoreDistributionResponse(
                range=label,
                min_score=min_score,
                max_score=max_score or 999999,
                count=count,
            )
        )

    return results
