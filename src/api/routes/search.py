"""API routes for full-text and semantic (vector) search."""

from datetime import date

from fastapi import APIRouter, Depends, Query, Request, Response
from slowapi import Limiter
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.auth import UserClaims, require_auth_or_guest
from src.api.pagination import set_total_count_header
from src.api.ratelimit import get_client_ip
from src.api.schemas import ErrorWrapper, NewsItemResponse
from src.core.database import get_session
from src.core.models import NewsItem
from src.core.queries import effective_date
from src.rag.retriever import Retriever

router = APIRouter(prefix="/api/search", tags=["search"])
limiter = Limiter(key_func=get_client_ip)


@router.get(
    "",
    response_model=list[NewsItemResponse],
    responses={401: {"model": ErrorWrapper}},
)
@limiter.limit("20/minute")
async def search_items(
    request: Request,
    response: Response,
    q: str = Query(..., min_length=1, description="Search text"),
    topic: str | None = Query(None, description="Filter by topic"),
    date_from: date | None = Query(None, description="Start date (inclusive)"),
    date_to: date | None = Query(None, description="End date (inclusive)"),
    sort_by: str = Query("relevance", pattern="^(relevance|date|score)$", description="Sort order"),
    limit: int = Query(50, ge=1, le=200, description="Max results to return"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    session: AsyncSession = Depends(get_session),
    _user: UserClaims = Depends(require_auth_or_guest),
) -> list[NewsItemResponse]:
    """Search news items using PostgreSQL full-text search.

    Searches across title and full_text columns. Results are ranked by
    relevance and can be filtered by topic and date range.
    """
    ts_query = func.plainto_tsquery("simple", q)
    ts_vector = func.to_tsvector(
        "simple",
        func.coalesce(NewsItem.title, "")
        + " "
        + func.coalesce(NewsItem.full_text, "")
        + " "
        + func.coalesce(NewsItem.source, ""),
    )

    fts_match = ts_vector.bool_op("@@")(ts_query)
    like_pattern = f"%{q}%"
    ilike_match = or_(
        NewsItem.title.ilike(like_pattern),
        NewsItem.source.ilike(like_pattern),
        NewsItem.summary.ilike(like_pattern),
    )

    query = select(NewsItem).where(or_(fts_match, ilike_match))

    if topic:
        query = query.where(NewsItem.topic == topic)
    if date_from:
        query = query.where(func.date(effective_date) >= date_from)
    if date_to:
        query = query.where(func.date(effective_date) <= date_to)

    # Count total matching results (before limit/offset)
    count_query = select(func.count()).select_from(query.with_only_columns(NewsItem.id).subquery())
    total = (await session.execute(count_query)).scalar_one()
    set_total_count_header(response, total)

    # Apply sorting
    if sort_by == "date":
        query = query.order_by(effective_date.desc())
    elif sort_by == "score":
        query = query.order_by(NewsItem.score.desc().nulls_last())
    else:  # relevance (default)
        query = query.order_by(func.ts_rank(ts_vector, ts_query).desc())

    query = query.offset(offset).limit(limit)

    result = await session.execute(query)
    items = result.scalars().all()

    return [NewsItemResponse.model_validate(item) for item in items]


@router.get(
    "/semantic",
    response_model=list[NewsItemResponse],
    responses={401: {"model": ErrorWrapper}},
)
@limiter.limit("20/minute")
async def semantic_search_items(
    request: Request,
    q: str = Query(..., min_length=1, description="Free-text search query to embed"),
    limit: int = Query(20, ge=1, le=50, description="Max results to return"),
    session: AsyncSession = Depends(get_session),
    _user: UserClaims = Depends(require_auth_or_guest),
) -> list[NewsItemResponse]:
    """Search news items by semantic (vector) similarity.

    Embeds the query string and returns the top-N most similar news items
    ranked by cosine distance. Returns an empty list when the embedding
    service is unavailable (e.g. ``embedding_api_key`` not configured).
    """
    retriever = Retriever()
    items = await retriever.retrieve(session, q, limit=limit)
    return [NewsItemResponse.model_validate(item) for item in items]
