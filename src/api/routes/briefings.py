"""API routes for daily briefings."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.auth import require_auth
from src.api.schemas import BriefingResponse, NewsItemResponse
from src.core.database import get_session
from src.core.models import DailyBriefing, NewsItem

router = APIRouter(prefix="/api/briefings", tags=["briefings"])
limiter = Limiter(key_func=get_remote_address)


@router.get("/{briefing_date}", response_model=BriefingResponse)
@limiter.limit("30/minute")
async def get_briefing(
    request: Request,
    briefing_date: date,
    session: AsyncSession = Depends(get_session),
    _user: str = Depends(require_auth),
) -> BriefingResponse:
    """Get the daily briefing for a specific date, including all items."""
    # Fetch briefing record
    result = await session.execute(select(DailyBriefing).where(DailyBriefing.date == briefing_date))
    briefing = result.scalar_one_or_none()

    if not briefing:
        raise HTTPException(status_code=404, detail=f"No briefing for {briefing_date}")

    # Fetch items for that date
    items_result = await session.execute(
        select(NewsItem)
        .where(func.date(NewsItem.created_at) == briefing_date)
        .order_by(NewsItem.score.desc().nulls_last())
    )
    items = items_result.scalars().all()

    return BriefingResponse(
        date=briefing.date,
        total_items=briefing.total_items,
        items_extracted=briefing.items_extracted,
        items_after_dedup=briefing.items_after_dedup,
        items_filtered=briefing.items_filtered,
        trending_count=briefing.trending_count,
        duration_seconds=briefing.duration_seconds,
        sources_used=briefing.sources_used,
        generated_at=briefing.generated_at,
        items=[
            NewsItemResponse(
                id=item.id,
                title=item.title,
                summary=item.summary,
                url=item.url,
                source=item.source,
                topic=item.topic,
                relevance_score=item.relevance_score,
                dev_value_score=item.dev_value_score,
                credibility_score=item.credibility_score,
                priority=item.priority,
                trending=item.trending,
                published_at=item.published_at,
                created_at=item.created_at,
                author=item.author,
                score=item.score,
            )
            for item in items
        ],
    )


@router.get("", response_model=list[BriefingResponse])
@limiter.limit("30/minute")
async def list_briefings(
    request: Request,
    limit: int = Query(30, ge=1, le=90, description="Max briefings to return"),
    session: AsyncSession = Depends(get_session),
    _user: str = Depends(require_auth),
) -> list[BriefingResponse]:
    """List recent daily briefings (without items)."""
    result = await session.execute(
        select(DailyBriefing).order_by(DailyBriefing.date.desc()).limit(limit)
    )
    briefings = result.scalars().all()

    return [
        BriefingResponse(
            date=b.date,
            total_items=b.total_items,
            items_extracted=b.items_extracted,
            items_after_dedup=b.items_after_dedup,
            items_filtered=b.items_filtered,
            trending_count=b.trending_count,
            duration_seconds=b.duration_seconds,
            sources_used=b.sources_used,
            generated_at=b.generated_at,
            items=[],
        )
        for b in briefings
    ]
