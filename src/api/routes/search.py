"""API routes for full-text and semantic (vector) search.

NOTE: No `from __future__ import annotations` — slowapi @limiter.limit
breaks with PEP 563 deferred evaluation for non-builtin Query types (date).
See src/api/routes/admin.py / auth.py. Verified: adding it here makes
TestSearchFilters::test_date_from_filter_accepted (and 3 siblings) fail with
`PydanticUserError: ... ForwardRef('date | None') ... is not fully defined`
(str/int Query params are unaffected — they resolve via __builtins__ even
though slowapi's wrapper.__globals__, not this module's, is what FastAPI
resolves the ForwardRef against).
"""

from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, Query, Request, Response
from slowapi import Limiter
from sqlalchemy import Select, Text, cast, func, select
from sqlalchemy.dialects.postgresql import TSQUERY
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import defer

from src.api.auth import UserClaims, require_auth_or_guest
from src.api.pagination import count_query, set_total_count_header
from src.api.ratelimit import get_client_ip
from src.api.schemas import ErrorWrapper, NewsItemResponse
from src.core.database import get_session
from src.core.models import NewsItem
from src.core.queries import day_end_exclusive, day_start, effective_date
from src.rag.retriever import Retriever

router = APIRouter(prefix="/api/search", tags=["search"])
limiter = Limiter(key_func=get_client_ip)

# F-11: module-level singleton — avoids rebuilding the OpenAI/httpx client per request.
_retriever: Retriever | None = None


def _get_retriever() -> Retriever:
    global _retriever
    if _retriever is None:
        _retriever = Retriever()
    return _retriever


# Lexemes of 3+ chars become prefix matches ('agent' -> 'agent':*, so "AI Agents"
# matches); 1-2 char lexemes stay exact ('ai', 'c') to avoid degenerate prefixes
# (ADR-005). The rewrite operates on plainto_tsquery's text form so user input
# never reaches the tsquery parser as operators. Cast (not to_tsquery) keeps
# compound lexemes (e.g. 'gpt-4o', 'mixture-of-experts') intact.
_PREFIX_PATTERN = r"(^| )'([^']{3,})'"
_PREFIX_REPLACEMENT = r"\1'\2':*"


def _ts_query(q: str) -> Any:
    """Build a prefix-aware tsquery from free text (see ADR-005)."""
    plain = cast(func.plainto_tsquery("simple", q), Text)
    return cast(func.regexp_replace(plain, _PREFIX_PATTERN, _PREFIX_REPLACEMENT, "g"), TSQUERY)


def _build_search_query(
    q: str,
    topic: str | None,
    date_from: date | None,
    date_to: date | None,
) -> Select:
    """Build the FTS-only search query (no ILIKE — see migration 019).

    ``search_vector`` (GIN-indexed) now covers title+full_text+summary+source,
    so the ILIKE fallback previously OR'd in is no longer needed and was
    forcing a sequential scan (revision-2026-09-13.md #1). Terms of 3+
    characters match as prefixes (ADR-005); shorter terms match exactly.
    """
    # F-16: use the stored, GIN-indexed search_vector column instead of
    # recomputing to_tsvector at query time.
    fts_match = NewsItem.search_vector.bool_op("@@")(_ts_query(q))

    query = select(NewsItem).where(fts_match).options(defer(NewsItem.full_text))

    if topic:
        query = query.where(NewsItem.topic == topic)
    if date_from:
        query = query.where(effective_date >= day_start(date_from))
    if date_to:
        query = query.where(effective_date < day_end_exclusive(date_to))

    return query


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

    Searches across title, full_text, summary and source columns (all
    covered by the search_vector GIN index). Terms of 3+ characters match as
    prefixes (e.g. "agent" finds "agents"); shorter terms match exactly
    (ADR-005). Results are ranked by relevance and can be filtered by topic
    and date range.
    """
    query = _build_search_query(q, topic, date_from, date_to)

    # Count total matching results (before limit/offset)
    total = await count_query(session, query)
    set_total_count_header(response, total)

    # Apply sorting
    if sort_by == "date":
        query = query.order_by(effective_date.desc())
    elif sort_by == "score":
        query = query.order_by(NewsItem.score.desc().nulls_last())
    else:  # relevance (default)
        query = query.order_by(func.ts_rank(NewsItem.search_vector, _ts_query(q)).desc())

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
    items = await _get_retriever().retrieve(session, q, limit=limit)
    return [NewsItemResponse.model_validate(item) for item in items]
