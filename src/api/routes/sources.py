"""API route for listing active sources."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.schemas import SourceInfo, SourcesResponse
from src.core.database import get_session
from src.core.models import NewsItem

router = APIRouter(prefix="/api/sources", tags=["sources"])
limiter = Limiter(key_func=get_remote_address)


@router.get("", response_model=SourcesResponse)
@limiter.limit("30/minute")
async def list_sources(
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> SourcesResponse:
    """List all sources with item count, sorted by count descending."""
    result = await session.execute(
        select(NewsItem.source, func.count(NewsItem.id).label("count"))
        .group_by(NewsItem.source)
        .order_by(func.count(NewsItem.id).desc())
    )
    sources = [SourceInfo(name=row.source, count=row.count) for row in result.all()]
    return SourcesResponse(sources=sources)
