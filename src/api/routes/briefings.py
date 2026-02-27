"""API routes for daily briefings."""

from datetime import UTC, date, datetime, time, timedelta

from fastapi import APIRouter, Depends, Query, Request, Response
from slowapi import Limiter
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.auth import UserClaims, require_auth
from src.api.errors import APIError
from src.api.pagination import set_total_count_header
from src.api.ratelimit import get_client_ip
from src.api.schemas import BriefingResponse, ErrorWrapper, NewsItemResponse
from src.core.database import get_session
from src.core.models import DailyBriefing, NewsItem
from src.core.queries import effective_date

router = APIRouter(prefix="/api/briefings", tags=["briefings"])
limiter = Limiter(key_func=get_client_ip)


@router.get(
    "/{briefing_date}",
    response_model=BriefingResponse,
    responses={
        401: {"model": ErrorWrapper},
        404: {"model": ErrorWrapper},
    },
)
@limiter.limit("30/minute")
async def get_briefing(
    request: Request,
    response: Response,
    briefing_date: date,
    limit: int = Query(100, ge=1, le=500, description="Max items to return"),
    offset: int = Query(0, ge=0, description="Items offset"),
    session: AsyncSession = Depends(get_session),
    _user: UserClaims = Depends(require_auth),
) -> BriefingResponse:
    """Get the daily briefing for a specific date, including paginated items."""
    result = await session.execute(select(DailyBriefing).where(DailyBriefing.date == briefing_date))
    briefing = result.scalar_one_or_none()

    # Use timestamp range for index-friendly queries
    day_start = datetime.combine(briefing_date, time.min, tzinfo=UTC)
    day_end = day_start + timedelta(days=1)
    date_filter = (effective_date >= day_start) & (effective_date < day_end)

    # Count total items for this date
    items_count = (
        await session.execute(select(func.count(NewsItem.id)).where(date_filter))
    ).scalar_one()

    # If no briefing AND no items, truly nothing exists for this date
    if not briefing and items_count == 0:
        raise APIError(404, "BRIEFING_NOT_FOUND", f"No data found for {briefing_date}")

    set_total_count_header(response, items_count)

    # Fetch paginated items
    items_result = await session.execute(
        select(NewsItem)
        .where(date_filter)
        .order_by(NewsItem.score.desc().nulls_last())
        .offset(offset)
        .limit(limit)
    )
    items = items_result.scalars().all()

    if briefing:
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

    # Synthesize minimal response from items only (no DailyBriefing record exists)
    return BriefingResponse(
        date=briefing_date,
        generated_at=None,
        items=[NewsItemResponse.model_validate(item) for item in items],
    )


@router.get(
    "",
    response_model=list[BriefingResponse],
    responses={401: {"model": ErrorWrapper}},
)
@limiter.limit("30/minute")
async def list_briefings(
    request: Request,
    response: Response,
    limit: int = Query(30, ge=1, le=90, description="Max briefings to return"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    session: AsyncSession = Depends(get_session),
    _user: UserClaims = Depends(require_auth),
) -> list[BriefingResponse]:
    """List recent daily briefings (without items)."""
    total = (await session.execute(select(func.count(DailyBriefing.date)))).scalar_one()
    set_total_count_header(response, total)

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
