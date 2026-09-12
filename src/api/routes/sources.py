"""API route for listing active sources."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request, Response
from slowapi import Limiter
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.auth import UserClaims, require_auth_or_guest
from src.api.caching import set_cache_header
from src.api.ratelimit import get_client_ip
from src.api.schemas import SourceInfo, SourcesResponse
from src.core.database import get_session
from src.core.models import NewsItem

router = APIRouter(prefix="/api/sources", tags=["sources"])
limiter = Limiter(key_func=get_client_ip)


@router.get("", response_model=SourcesResponse)
@limiter.limit("30/minute")
async def list_sources(
    request: Request,
    response: Response,
    session: AsyncSession = Depends(get_session),
    _user: UserClaims = Depends(require_auth_or_guest),
) -> SourcesResponse:
    """List all sources with item count, sorted by count descending."""
    result = await session.execute(
        select(NewsItem.source, func.count(NewsItem.id).label("count"))
        .group_by(NewsItem.source)
        .order_by(func.count(NewsItem.id).desc())
    )
    sources = [SourceInfo(name=row.source, count=row.count) for row in result.all()]
    set_cache_header(response)
    return SourcesResponse(sources=sources)
