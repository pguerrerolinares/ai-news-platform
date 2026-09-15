"""API routes for aggregate statistics."""

from datetime import UTC, datetime, timedelta
from datetime import date as date_type
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from slowapi import Limiter
from sqlalchemy import ColumnElement, Date, case, cast, func, select
from sqlalchemy.dialects.postgresql import array as pg_array
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.auth import UserClaims, require_auth_or_guest
from src.api.caching import set_cache_header
from src.api.errors import APIError
from src.api.ratelimit import get_client_ip
from src.api.routes.search import _ts_query
from src.api.schemas import (
    ErrorWrapper,
    ScoreDistributionResponse,
    StatsDateResponse,
    StatsGroupDateResponse,
    StatsGroupResponse,
    StatsSummaryResponse,
    TrendResponse,
)
from src.api.trend import TREND_DISTANCE_EDGES, bucket_starts, build_buckets
from src.core.config import get_settings
from src.core.database import get_session
from src.core.logging import get_logger
from src.core.models import ItemEmbedding, NewsItem
from src.core.queries import (
    day_end_exclusive,
    day_start,
    effective_date,
    force_exact_scan,
    since_days,
)
from src.rag.embeddings import EmbeddingService

router = APIRouter(prefix="/api/stats", tags=["stats"])
limiter = Limiter(key_func=get_client_ip)
logger = get_logger(__name__)

_TREND_DEFAULT_DAYS = 182  # ~6 months
_TREND_MAX_DAYS = 730  # 24 months

# Module-level singleton, same pattern as search.py's retriever.
_embedding_service: EmbeddingService | None = None


def _get_embedding_service() -> EmbeddingService:
    global _embedding_service
    if _embedding_service is None:
        _embedding_service = EmbeddingService()
    return _embedding_service


def _build_date_filter(
    date_from: date_type | None,
    date_to: date_type | None,
    days: int,
) -> "ColumnElement[bool]":
    """Build a date filter from either a date range or a days lookback."""
    if (date_from is None) != (date_to is None):
        raise HTTPException(
            status_code=422,
            detail="date_from and date_to must both be provided or both omitted",
        )
    if date_from is not None and date_to is not None:
        if date_from > date_to:
            raise HTTPException(
                status_code=422,
                detail="date_from must not be after date_to",
            )
        return (effective_date >= day_start(date_from)) & (
            effective_date < day_end_exclusive(date_to)
        )
    return effective_date >= since_days(days)


@router.get(
    "/summary",
    response_model=StatsSummaryResponse,
    responses={401: {"model": ErrorWrapper}},
)
@limiter.limit("30/minute")
async def stats_summary(
    request: Request,
    response: Response,
    session: AsyncSession = Depends(get_session),
    _user: UserClaims = Depends(require_auth_or_guest),
) -> StatsSummaryResponse:
    """Get summary statistics for the platform in a single query."""

    today = datetime.now(tz=UTC).date()
    is_today = (effective_date >= day_start(today)) & (effective_date < day_end_exclusive(today))

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

    set_cache_header(response)
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
    response: Response,
    session: AsyncSession = Depends(get_session),
    _user: UserClaims = Depends(require_auth_or_guest),
) -> list[StatsGroupResponse]:
    """Get item count grouped by source."""
    result = await session.execute(
        select(NewsItem.source, func.count(NewsItem.id).label("count"))
        .group_by(NewsItem.source)
        .order_by(func.count(NewsItem.id).desc())
    )
    set_cache_header(response)
    return [StatsGroupResponse(name=row.source, count=row.count) for row in result.all()]


@router.get(
    "/by-topic",
    response_model=list[StatsGroupResponse],
    responses={401: {"model": ErrorWrapper}},
)
@limiter.limit("30/minute")
async def stats_by_topic(
    request: Request,
    response: Response,
    session: AsyncSession = Depends(get_session),
    _user: UserClaims = Depends(require_auth_or_guest),
) -> list[StatsGroupResponse]:
    """Get item count grouped by topic."""
    result = await session.execute(
        select(NewsItem.topic, func.count(NewsItem.id).label("count"))
        .where(NewsItem.topic.isnot(None))
        .group_by(NewsItem.topic)
        .order_by(func.count(NewsItem.id).desc())
    )
    set_cache_header(response)
    return [StatsGroupResponse(name=row.topic, count=row.count) for row in result.all()]


@router.get(
    "/by-date",
    response_model=list[StatsDateResponse],
    responses={401: {"model": ErrorWrapper}},
)
@limiter.limit("30/minute")
async def stats_by_date(
    request: Request,
    response: Response,
    days: int = Query(30, ge=1, le=365, description="Number of days to include"),
    date_from: date_type | None = Query(default=None, description="Start date (inclusive)"),
    date_to: date_type | None = Query(default=None, description="End date (inclusive)"),
    session: AsyncSession = Depends(get_session),
    _user: UserClaims = Depends(require_auth_or_guest),
) -> list[StatsDateResponse]:
    """Get item count grouped by date for the last N days, or a custom date range."""
    date_filter = _build_date_filter(date_from, date_to, days)
    eff_date = func.date(effective_date)

    result = await session.execute(
        select(
            eff_date.label("date"),
            func.count(NewsItem.id).label("count"),
        )
        .where(date_filter)
        .group_by(eff_date)
        .order_by(eff_date.desc())
    )
    set_cache_header(response)
    return [StatsDateResponse(date=row.date, count=row.count) for row in result.all()]


@router.get(
    "/by-topic-date",
    response_model=list[StatsGroupDateResponse],
    responses={401: {"model": ErrorWrapper}},
)
@limiter.limit("30/minute")
async def stats_by_topic_date(
    request: Request,
    response: Response,
    days: int = Query(30, ge=1, le=365, description="Number of days to include"),
    date_from: date_type | None = Query(default=None, description="Start date (inclusive)"),
    date_to: date_type | None = Query(default=None, description="End date (inclusive)"),
    session: AsyncSession = Depends(get_session),
    _user: UserClaims = Depends(require_auth_or_guest),
) -> list[StatsGroupDateResponse]:
    """Get item count grouped by topic and date for the last N days, or a custom range."""
    date_filter = _build_date_filter(date_from, date_to, days)
    eff_date = func.date(effective_date)

    result = await session.execute(
        select(
            eff_date.label("date"),
            NewsItem.topic.label("group"),
            func.count(NewsItem.id).label("count"),
        )
        .where(date_filter & NewsItem.topic.isnot(None))
        .group_by(eff_date, NewsItem.topic)
        .order_by(eff_date.asc(), NewsItem.topic.asc())
    )
    set_cache_header(response)
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
    response: Response,
    days: int = Query(30, ge=1, le=365, description="Number of days to include"),
    session: AsyncSession = Depends(get_session),
    _user: UserClaims = Depends(require_auth_or_guest),
) -> list[StatsGroupDateResponse]:
    """Get item count grouped by source and date for the last N days."""
    eff_date = func.date(effective_date)
    result = await session.execute(
        select(
            eff_date.label("date"),
            NewsItem.source.label("group"),
            func.count(NewsItem.id).label("count"),
        )
        .where(effective_date >= since_days(days))
        .group_by(eff_date, NewsItem.source)
        .order_by(eff_date.asc(), NewsItem.source.asc())
    )
    set_cache_header(response)
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
    response: Response,
    days: int = Query(30, ge=1, le=365, description="Number of days to include"),
    session: AsyncSession = Depends(get_session),
    _user: UserClaims = Depends(require_auth_or_guest),
) -> list[StatsDateResponse]:
    """Get trending item count by date for the last N days."""
    eff_date = func.date(effective_date)
    result = await session.execute(
        select(
            eff_date.label("date"),
            func.count(NewsItem.id).label("count"),
        )
        .where((effective_date >= since_days(days)) & NewsItem.trending.is_(True))
        .group_by(eff_date)
        .order_by(eff_date.asc())
    )
    set_cache_header(response)
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
    response: Response,
    days: int = Query(30, ge=1, le=365, description="Number of days to include"),
    source: str | None = Query(None, description="Filter by source"),
    topic: str | None = Query(None, description="Filter by topic"),
    session: AsyncSession = Depends(get_session),
    _user: UserClaims = Depends(require_auth_or_guest),
) -> list[ScoreDistributionResponse]:
    """Get score distribution as histogram buckets."""
    # Build base filter (date + non-null score + optional source/topic)
    base_filter = (effective_date >= since_days(days)) & NewsItem.score.isnot(None)
    if source:
        base_filter = base_filter & (NewsItem.source == source)
    if topic:
        base_filter = base_filter & (NewsItem.topic == topic)

    # Single query: one COUNT per bucket using CASE expressions
    bucket_exprs = []
    for label, min_score, max_score in _SCORE_BUCKETS:
        cond = NewsItem.score >= min_score
        if max_score is not None:
            cond = cond & (NewsItem.score <= max_score)
        bucket_exprs.append(func.count(case((cond, NewsItem.id))).label(label))

    query = select(*bucket_exprs).where(base_filter)
    row = (await session.execute(query)).one()

    set_cache_header(response)
    return [
        ScoreDistributionResponse(
            range=label,
            min_score=min_score,
            max_score=max_score or 999999,
            count=getattr(row, label),
        )
        for label, min_score, max_score in _SCORE_BUCKETS
    ]


@router.get(
    "/trend",
    response_model=TrendResponse,
    responses={
        401: {"model": ErrorWrapper},
        422: {"model": ErrorWrapper},
        503: {"model": ErrorWrapper},
    },
)
@limiter.limit("20/minute")
async def stats_trend(
    request: Request,
    q: str = Query(..., min_length=1, max_length=200, description="Topic to measure"),
    method: Literal["keyword", "semantic"] = Query(
        "keyword",
        description="keyword = full-text match; semantic = distance bands below max_distance",
    ),
    granularity: Literal["week", "month"] = Query(
        "month", description="ISO weeks or calendar months (UTC)"
    ),
    since: date_type | None = Query(
        None, description="Start date (inclusive); default 182 days ago, at most 730 days ago"
    ),
    max_distance: float = Query(
        0.40,
        ge=0.20,
        le=0.60,
        description="Cosine-distance cutoff for method=semantic (ignored in keyword)",
    ),
    session: AsyncSession = Depends(get_session),
    _user: UserClaims = Depends(require_auth_or_guest),
) -> TrendResponse:
    """Count items about a topic per time bucket, with each bucket's total for normalization.

    Empty buckets are included (count 0). ``share`` = count / total_in_bucket; for
    ``semantic`` the total only counts items with an embedding of the active model.
    ``semantic`` has no calibrated threshold (pre-check (a) found no single cosine-distance
    cutoff separates relevant from irrelevant items across queries): ``max_distance`` is an
    explicit cutoff and ``by_distance`` gives the cumulative count at 5 fixed bands
    (0.30-0.50) so the caller can read the shape instead of trusting one number.
    """
    today = datetime.now(tz=UTC).date()
    start = since or (today - timedelta(days=_TREND_DEFAULT_DAYS))
    if start > today:
        raise APIError(422, "VALIDATION_ERROR", "since must not be in the future")
    if (today - start).days > _TREND_MAX_DAYS:
        raise APIError(
            422,
            "VALIDATION_ERROR",
            f"since must be within the last {_TREND_MAX_DAYS} days (24 months)",
        )

    starts = bucket_starts(start, today, granularity)
    bucket = cast(func.date_trunc(granularity, func.timezone("UTC", effective_date)), Date).label(
        "bucket"
    )
    in_window = effective_date >= day_start(starts[0])

    if method == "keyword":
        match = NewsItem.search_vector.bool_op("@@")(_ts_query(q))
        count_stmt = (
            select(bucket, NewsItem.source, func.count(NewsItem.id))
            .where(in_window & match)
            .group_by(bucket, NewsItem.source)
        )
        total_stmt = select(bucket, func.count(NewsItem.id)).where(in_window).group_by(bucket)

        counts = {(row[0], row[1]): row[2] for row in (await session.execute(count_stmt)).all()}
        totals = {row[0]: row[1] for row in (await session.execute(total_stmt)).all()}

        return TrendResponse(
            query=q,
            method=method,
            granularity=granularity,
            since=start,
            max_distance=None,
            distance_edges=None,
            buckets=build_buckets(starts, counts, totals),
        )

    settings = get_settings()
    try:
        query_vec = await _get_embedding_service().embed_text(q)
    except Exception as exc:
        logger.error("trend_embed_failed", exc_info=True)
        raise APIError(
            503,
            "EMBEDDING_UNAVAILABLE",
            "Semantic trend unavailable: the query could not be embedded",
        ) from exc

    has_embedding = (ItemEmbedding.item_id == NewsItem.id) & (
        ItemEmbedding.model == settings.embedding_model
    )
    distance = ItemEmbedding.embedding.cosine_distance(query_vec)
    band = func.width_bucket(distance, pg_array(TREND_DISTANCE_EDGES)).label("band")
    within_max = (distance < max_distance).label("within_max")
    # Widest edge we still need rows for: TREND_DISTANCE_EDGES[-1] (0.50) unless the
    # caller asked for a wider max_distance (up to 0.60).
    edge_cutoff = max(max_distance, TREND_DISTANCE_EDGES[-1])

    # No-op for this query shape: pgvector's HNSW index only supports ORDER BY
    # <-> LIMIT n (nearest-neighbor) scans, never a plain WHERE distance filter like
    # this grouped query's, so there is no HNSW-capped subset to guard against here
    # (pg_amop: hnsw vector_cosine_ops only registers an ORDER BY operator,
    # amoppurpose = 'o'; EXPLAIN agrees). Kept as a guard if the query
    # shape changes to add an ORDER BY distance LIMIT.
    await force_exact_scan(session)

    # Single grouped query: (bucket, source, band, within_max) -> count. `counts` (by
    # source, at max_distance) and `bands` (cumulative histogram) are both derived from
    # these rows in Python — see build_buckets.
    band_stmt = (
        select(bucket, NewsItem.source, band, within_max, func.count(NewsItem.id))
        .join(ItemEmbedding, has_embedding)
        .where(in_window & (distance < edge_cutoff))
        .group_by(bucket, NewsItem.source, band, within_max)
    )
    total_stmt = (
        select(bucket, func.count(NewsItem.id))
        .join(ItemEmbedding, has_embedding)
        .where(in_window)
        .group_by(bucket)
    )

    counts: dict[tuple[date_type, str], int] = {}
    bands: dict[tuple[date_type, str, int], int] = {}
    for bucket_start, source, band_idx, is_within_max, n in (
        await session.execute(band_stmt)
    ).all():
        key = (bucket_start, source, band_idx)
        bands[key] = bands.get(key, 0) + n
        if is_within_max:
            counts[(bucket_start, source)] = counts.get((bucket_start, source), 0) + n
    totals = {row[0]: row[1] for row in (await session.execute(total_stmt)).all()}

    return TrendResponse(
        query=q,
        method=method,
        granularity=granularity,
        since=start,
        max_distance=max_distance,
        distance_edges=list(TREND_DISTANCE_EDGES),
        buckets=build_buckets(starts, counts, totals, bands=bands),
    )
