"""API routes for daily briefings."""

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.auth import require_auth
from src.api.pagination import set_total_count_header
from src.api.schemas import BriefingResponse, NewsItemResponse
from src.core.database import get_session
from src.core.models import DailyBriefing, NewsItem

router = APIRouter(prefix="/api/briefings", tags=["briefings"])
limiter = Limiter(key_func=get_remote_address)


@router.get("/{briefing_date}", response_model=BriefingResponse)
@limiter.limit("30/minute")
async def get_briefing(
    request: Request,
    response: Response,
    briefing_date: date,
    limit: int = Query(100, ge=1, le=500, description="Max items to return"),
    offset: int = Query(0, ge=0, description="Items offset"),
    session: AsyncSession = Depends(get_session),
    _user: str = Depends(require_auth),
) -> BriefingResponse:
    """Get the daily briefing for a specific date, including paginated items."""
    result = await session.execute(select(DailyBriefing).where(DailyBriefing.date == briefing_date))
    briefing = result.scalar_one_or_none()

    if not briefing:
        raise HTTPException(status_code=404, detail=f"No briefing for {briefing_date}")

    # Count total items for this date
    items_count = (
        await session.execute(
            select(func.count(NewsItem.id)).where(func.date(NewsItem.created_at) == briefing_date)
        )
    ).scalar_one()
    set_total_count_header(response, items_count)

    # Fetch paginated items
    items_result = await session.execute(
        select(NewsItem)
        .where(func.date(NewsItem.created_at) == briefing_date)
        .order_by(NewsItem.score.desc().nulls_last())
        .offset(offset)
        .limit(limit)
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
        items=[NewsItemResponse.model_validate(item) for item in items],
    )


@router.get("", response_model=list[BriefingResponse])
@limiter.limit("30/minute")
async def list_briefings(
    request: Request,
    limit: int = Query(30, ge=1, le=90, description="Max briefings to return"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    session: AsyncSession = Depends(get_session),
    _user: str = Depends(require_auth),
) -> list[BriefingResponse]:
    """List recent daily briefings (without items)."""
    result = await session.execute(
        select(DailyBriefing).order_by(DailyBriefing.date.desc()).offset(offset).limit(limit)
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
