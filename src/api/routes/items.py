"""API routes for news items."""

from datetime import UTC, date, datetime, time, timedelta

from fastapi import APIRouter, Depends, Query, Request, Response
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.auth import require_auth
from src.api.pagination import set_total_count_header
from src.api.schemas import CountResponse, NewsItemResponse
from src.core.database import get_session
from src.core.models import NewsItem

router = APIRouter(prefix="/api/items", tags=["items"])
limiter = Limiter(key_func=get_remote_address)


@router.get("", response_model=list[NewsItemResponse])
@limiter.limit("30/minute")
async def list_items(
    request: Request,
    response: Response,
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

    # Count before pagination
    count_query = select(func.count()).select_from(query.with_only_columns(NewsItem.id).subquery())
    total = (await session.execute(count_query)).scalar_one()
    set_total_count_header(response, total)

    query = query.order_by(NewsItem.published_at.desc()).offset(offset).limit(limit)

    result = await session.execute(query)
    items = result.scalars().all()

    return [NewsItemResponse.model_validate(item) for item in items]


@router.get("/count", response_model=CountResponse)
@limiter.limit("30/minute")
async def count_items(
    request: Request,
    source: str | None = Query(None),
    topic: str | None = Query(None),
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    session: AsyncSession = Depends(get_session),
    _user: str = Depends(require_auth),
) -> CountResponse:
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

    return CountResponse(count=count)


@router.get("/today", response_model=list[NewsItemResponse])
@limiter.limit("30/minute")
async def list_today_items(
    request: Request,
    response: Response,
    topic: str | None = Query(None, description="Filter by topic"),
    limit: int = Query(100, ge=1, le=200),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    session: AsyncSession = Depends(get_session),
    _user: str = Depends(require_auth),
) -> list[NewsItemResponse]:
    """List today's news items, sorted by score descending."""
    today_start = datetime.combine(datetime.now(tz=UTC).date(), time.min, tzinfo=UTC)
    today_end = today_start + timedelta(days=1)
    query = select(NewsItem).where(
        (NewsItem.created_at >= today_start) & (NewsItem.created_at < today_end)
    )
    if topic:
        query = query.where(NewsItem.topic == topic)

    # Count before pagination
    count_query = select(func.count()).select_from(query.with_only_columns(NewsItem.id).subquery())
    total = (await session.execute(count_query)).scalar_one()
    set_total_count_header(response, total)

    query = query.order_by(NewsItem.score.desc().nulls_last()).offset(offset).limit(limit)
    result = await session.execute(query)
    items = result.scalars().all()
    return [NewsItemResponse.model_validate(item) for item in items]
