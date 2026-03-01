"""API routes for news items."""

import uuid as uuid_mod
from datetime import UTC, date, datetime, time, timedelta

from fastapi import APIRouter, Depends, Query, Request, Response
from slowapi import Limiter
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.auth import UserClaims, require_auth
from src.api.errors import APIError
from src.api.pagination import set_total_count_header
from src.api.ratelimit import get_client_ip
from src.api.schemas import CountResponse, ErrorWrapper, NewsItemResponse
from src.core.database import get_session
from src.core.models import ItemEmbedding, NewsItem
from src.core.queries import effective_date

router = APIRouter(prefix="/api/items", tags=["items"])
limiter = Limiter(key_func=get_client_ip)

_DEFAULT_EMBEDDING_MODEL = "text-embedding-3-small"


@router.get(
    "",
    response_model=list[NewsItemResponse],
    responses={401: {"model": ErrorWrapper}},
)
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
    _user: UserClaims = Depends(require_auth),
) -> list[NewsItemResponse]:
    """List news items with optional filters."""
    query = select(NewsItem)

    if source:
        query = query.where(NewsItem.source == source)
    if topic:
        query = query.where(NewsItem.topic == topic)
    if date_from:
        query = query.where(func.date(effective_date) >= date_from)
    if date_to:
        query = query.where(func.date(effective_date) <= date_to)
    if trending is not None:
        query = query.where(NewsItem.trending == trending)

    # Count before pagination
    count_query = select(func.count()).select_from(query.with_only_columns(NewsItem.id).subquery())
    total = (await session.execute(count_query)).scalar_one()
    set_total_count_header(response, total)

    query = query.order_by(effective_date.desc()).offset(offset).limit(limit)

    result = await session.execute(query)
    items = result.scalars().all()

    return [NewsItemResponse.model_validate(item) for item in items]


@router.get(
    "/count",
    response_model=CountResponse,
    responses={401: {"model": ErrorWrapper}},
)
@limiter.limit("30/minute")
async def count_items(
    request: Request,
    source: str | None = Query(None),
    topic: str | None = Query(None),
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    session: AsyncSession = Depends(get_session),
    _user: UserClaims = Depends(require_auth),
) -> CountResponse:
    """Count items matching filters."""
    query = select(func.count(NewsItem.id))

    if source:
        query = query.where(NewsItem.source == source)
    if topic:
        query = query.where(NewsItem.topic == topic)
    if date_from:
        query = query.where(func.date(effective_date) >= date_from)
    if date_to:
        query = query.where(func.date(effective_date) <= date_to)

    result = await session.execute(query)
    count = result.scalar_one()

    return CountResponse(count=count)


@router.get(
    "/by-date/{item_date}",
    response_model=list[NewsItemResponse],
    responses={401: {"model": ErrorWrapper}},
)
@limiter.limit("30/minute")
async def list_items_by_date(
    request: Request,
    response: Response,
    item_date: date,
    topic: str | None = Query(None, description="Filter by topic"),
    source: str | None = Query(None, description="Filter by source"),
    limit: int = Query(50, ge=1, le=200, description="Max items to return"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    session: AsyncSession = Depends(get_session),
    _user: UserClaims = Depends(require_auth),
) -> list[NewsItemResponse]:
    """List news items for a specific date, sorted by score."""
    day_start = datetime.combine(item_date, time.min, tzinfo=UTC)
    day_end = day_start + timedelta(days=1)
    query = select(NewsItem).where((effective_date >= day_start) & (effective_date < day_end))
    if topic:
        query = query.where(NewsItem.topic == topic)
    if source:
        query = query.where(NewsItem.source == source)

    count_query = select(func.count()).select_from(query.with_only_columns(NewsItem.id).subquery())
    total = (await session.execute(count_query)).scalar_one()
    set_total_count_header(response, total)

    query = (
        query.order_by(NewsItem.score.desc().nulls_last(), effective_date.desc())
        .offset(offset)
        .limit(limit)
    )
    result = await session.execute(query)
    items = result.scalars().all()
    return [NewsItemResponse.model_validate(item) for item in items]


@router.get(
    "/trending",
    response_model=list[NewsItemResponse],
    responses={401: {"model": ErrorWrapper}},
)
@limiter.limit("30/minute")
async def list_trending_items(
    request: Request,
    response: Response,
    topic: str | None = Query(None, description="Filter by topic"),
    source: str | None = Query(None, description="Filter by source"),
    days: int = Query(7, ge=1, le=90, description="Look back N days"),
    limit: int = Query(20, ge=1, le=100, description="Max items to return"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    session: AsyncSession = Depends(get_session),
    _user: UserClaims = Depends(require_auth),
) -> list[NewsItemResponse]:
    """List trending items from the last N days, sorted by score."""
    since = datetime.combine(
        (datetime.now(tz=UTC) - timedelta(days=days)).date(), time.min, tzinfo=UTC
    )
    query = select(NewsItem).where(NewsItem.trending.is_(True) & (effective_date >= since))
    if topic:
        query = query.where(NewsItem.topic == topic)
    if source:
        query = query.where(NewsItem.source == source)

    count_query = select(func.count()).select_from(query.with_only_columns(NewsItem.id).subquery())
    total = (await session.execute(count_query)).scalar_one()
    set_total_count_header(response, total)

    query = (
        query.order_by(NewsItem.score.desc().nulls_last(), effective_date.desc())
        .offset(offset)
        .limit(limit)
    )
    result = await session.execute(query)
    items = result.scalars().all()
    return [NewsItemResponse.model_validate(item) for item in items]


@router.get(
    "/today",
    response_model=list[NewsItemResponse],
    responses={401: {"model": ErrorWrapper}},
)
@limiter.limit("30/minute")
async def list_today_items(
    request: Request,
    response: Response,
    topic: str | None = Query(None, description="Filter by topic"),
    limit: int = Query(100, ge=1, le=200),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    session: AsyncSession = Depends(get_session),
    _user: UserClaims = Depends(require_auth),
) -> list[NewsItemResponse]:
    """List today's news items, sorted chronologically (newest first)."""
    today_start = datetime.combine(datetime.now(tz=UTC).date(), time.min, tzinfo=UTC)
    today_end = today_start + timedelta(days=1)
    query = select(NewsItem).where(
        (effective_date >= today_start) & (effective_date < today_end)
    )
    if topic:
        query = query.where(NewsItem.topic == topic)

    # Count before pagination
    count_query = select(func.count()).select_from(query.with_only_columns(NewsItem.id).subquery())
    total = (await session.execute(count_query)).scalar_one()
    set_total_count_header(response, total)

    query = query.order_by(effective_date.desc()).offset(offset).limit(limit)
    result = await session.execute(query)
    items = result.scalars().all()
    return [NewsItemResponse.model_validate(item) for item in items]


@router.get(
    "/top",
    response_model=list[NewsItemResponse],
    responses={401: {"model": ErrorWrapper}},
)
@limiter.limit("30/minute")
async def list_top_items(
    request: Request,
    response: Response,
    days: int = Query(7, ge=1, le=90, description="Look back N days"),
    limit: int = Query(10, ge=1, le=50, description="Max items to return"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    topic: str | None = Query(None, description="Filter by topic"),
    source: str | None = Query(None, description="Filter by source"),
    session: AsyncSession = Depends(get_session),
    _user: UserClaims = Depends(require_auth),
) -> list[NewsItemResponse]:
    """Top items by score in the last N days."""
    since = datetime.combine(
        (datetime.now(tz=UTC) - timedelta(days=days)).date(), time.min, tzinfo=UTC
    )
    query = select(NewsItem).where((effective_date >= since) & NewsItem.score.isnot(None))
    if topic:
        query = query.where(NewsItem.topic == topic)
    if source:
        query = query.where(NewsItem.source == source)

    count_query = select(func.count()).select_from(query.with_only_columns(NewsItem.id).subquery())
    total = (await session.execute(count_query)).scalar_one()
    set_total_count_header(response, total)

    query = query.order_by(NewsItem.score.desc().nulls_last()).offset(offset).limit(limit)
    result = await session.execute(query)
    items = result.scalars().all()
    return [NewsItemResponse.model_validate(item) for item in items]


@router.get(
    "/latest",
    response_model=list[NewsItemResponse],
    responses={401: {"model": ErrorWrapper}},
)
@limiter.limit("30/minute")
async def list_latest_items(
    request: Request,
    response: Response,
    topic: str | None = Query(None, description="Filter by topic"),
    source: str | None = Query(None, description="Filter by source"),
    limit: int = Query(50, ge=1, le=200, description="Max items to return"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    session: AsyncSession = Depends(get_session),
    _user: UserClaims = Depends(require_auth),
) -> list[NewsItemResponse]:
    """Latest items across all dates, sorted by effective date descending."""
    query = select(NewsItem)

    if topic:
        query = query.where(NewsItem.topic == topic)
    if source:
        query = query.where(NewsItem.source == source)

    count_query = select(func.count()).select_from(query.with_only_columns(NewsItem.id).subquery())
    total = (await session.execute(count_query)).scalar_one()
    set_total_count_header(response, total)

    query = query.order_by(effective_date.desc()).offset(offset).limit(limit)

    result = await session.execute(query)
    items = result.scalars().all()
    return [NewsItemResponse.model_validate(item) for item in items]


# IMPORTANT: This route MUST be last — {item_id} is a catch-all path parameter.
@router.get(
    "/{item_id}/similar",
    response_model=list[NewsItemResponse],
    responses={
        401: {"model": ErrorWrapper},
        404: {"model": ErrorWrapper},
    },
)
@limiter.limit("20/minute")
async def get_similar_items(
    request: Request,
    item_id: uuid_mod.UUID,
    limit: int = Query(5, ge=1, le=20, description="Number of similar items"),
    session: AsyncSession = Depends(get_session),
    _user: UserClaims = Depends(require_auth),
) -> list[NewsItemResponse]:
    """Find similar items using pgvector cosine distance."""
    # Get embedding for the source item
    result = await session.execute(
        select(ItemEmbedding)
        .where(ItemEmbedding.item_id == item_id)
        .where(ItemEmbedding.model == _DEFAULT_EMBEDDING_MODEL)
        .limit(1)
    )
    embedding_row = result.scalar_one_or_none()

    if not embedding_row:
        raise APIError(404, "EMBEDDING_NOT_FOUND", f"No embedding found for item {item_id}")

    # Find nearest neighbors (exclude the source item)
    similar_query = (
        select(NewsItem)
        .join(ItemEmbedding, NewsItem.id == ItemEmbedding.item_id)
        .where(ItemEmbedding.item_id != item_id)
        .where(ItemEmbedding.model == _DEFAULT_EMBEDDING_MODEL)
        .order_by(ItemEmbedding.embedding.cosine_distance(embedding_row.embedding))
        .limit(limit)
    )
    similar_result = await session.execute(similar_query)
    items = similar_result.scalars().all()
    return [NewsItemResponse.model_validate(item) for item in items]
