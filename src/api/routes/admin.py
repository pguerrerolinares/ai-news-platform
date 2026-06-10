"""Admin API routes — pipeline audit, runs, and source freshness.

NOTE: No `from __future__ import annotations` — slowapi @limiter.limit
breaks with PEP 563 deferred evaluation. See src/api/routes/otp.py.
"""

from datetime import UTC, datetime, timedelta
from typing import Literal

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel
from slowapi import Limiter
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.auth import UserClaims, require_auth_or_guest
from src.api.ratelimit import get_client_ip
from src.core.database import get_session
from src.core.models import NewsItem, PipelineRun

router = APIRouter(prefix="/api/admin", tags=["admin"])
limiter = Limiter(key_func=get_client_ip)


# --- Schemas ---


class SourceStats(BaseModel):
    source: str
    count: int
    last_item_at: datetime | None


class DailySourceCount(BaseModel):
    date: str
    source: str
    count: int


class DuplicateInfo(BaseModel):
    duplicate_groups: int
    extra_items: int


class AuditResponse(BaseModel):
    total_items: int
    date_range: dict[str, str | None]
    sources: list[SourceStats]
    daily_breakdown: list[DailySourceCount]
    duplicates: DuplicateInfo


class PipelineRunResponse(BaseModel):
    id: str
    started_at: datetime
    duration_seconds: float
    status: str
    sources: list[str]
    items_extracted: int
    items_after_dedup: int
    items_seen_filtered: int
    items_classified: int
    items_validated: int
    items_stored: int
    error_message: str | None
    correlation_id: str | None


class FreshnessResponse(BaseModel):
    source: str
    last_item_at: datetime | None
    hours_ago: float | None
    status: str  # ok, stale, dead


# --- Endpoints ---


@router.get("/audit", response_model=AuditResponse)
@limiter.limit("10/minute")
async def admin_audit(
    request: Request,
    days: int = Query(14, ge=1, le=365),
    session: AsyncSession = Depends(get_session),
    _user: UserClaims = Depends(require_auth_or_guest),
) -> AuditResponse:
    """Full audit snapshot: items, sources, daily breakdown, duplicates."""
    now = datetime.now(tz=UTC)
    cutoff = now - timedelta(days=days)

    # Total items + date range
    result = await session.execute(
        select(
            func.count(NewsItem.id),
            func.min(NewsItem.created_at),
            func.max(NewsItem.created_at),
        )
    )
    total, oldest, newest = result.one()

    # Per-source stats
    result = await session.execute(
        select(
            NewsItem.source,
            func.count(NewsItem.id).label("count"),
            func.max(NewsItem.created_at).label("last_item_at"),
        )
        .group_by(NewsItem.source)
        .order_by(func.count(NewsItem.id).desc())
    )
    sources = [
        SourceStats(source=r.source, count=r.count, last_item_at=r.last_item_at)
        for r in result.all()
    ]

    # Daily breakdown by source
    result = await session.execute(
        select(
            func.date(NewsItem.created_at).label("day"),
            NewsItem.source,
            func.count(NewsItem.id).label("count"),
        )
        .where(NewsItem.created_at >= cutoff)
        .group_by(func.date(NewsItem.created_at), NewsItem.source)
        .order_by(func.date(NewsItem.created_at).desc(), func.count(NewsItem.id).desc())
    )
    daily = [
        DailySourceCount(date=str(r.day), source=r.source, count=r.count) for r in result.all()
    ]

    # Duplicate check (by URL) — compute per-URL counts in a subquery,
    # then aggregate over that subquery to avoid nested aggregate functions.
    dup_counts = (
        select(func.count(NewsItem.id).label("cnt"))
        .where(NewsItem.url.isnot(None))
        .group_by(NewsItem.url)
        .having(func.count(NewsItem.id) > 1)
        .subquery()
    )
    result = await session.execute(
        select(
            func.count(),
            func.coalesce(func.sum(dup_counts.c.cnt - 1), 0),
        ).select_from(dup_counts)
    )
    dup_groups, extra_items = result.one()

    return AuditResponse(
        total_items=total or 0,
        date_range={
            "oldest": str(oldest) if oldest else None,
            "newest": str(newest) if newest else None,
        },
        sources=sources,
        daily_breakdown=daily,
        duplicates=DuplicateInfo(duplicate_groups=dup_groups or 0, extra_items=extra_items or 0),
    )


@router.get("/pipeline-runs", response_model=list[PipelineRunResponse])
@limiter.limit("10/minute")
async def admin_pipeline_runs(
    request: Request,
    limit: int = Query(50, ge=1, le=500),
    status: Literal["success", "empty", "error"] | None = Query(None),
    session: AsyncSession = Depends(get_session),
    _user: UserClaims = Depends(require_auth_or_guest),
) -> list[PipelineRunResponse]:
    """List recent pipeline runs with per-stage stats."""
    stmt = select(PipelineRun).order_by(PipelineRun.started_at.desc()).limit(limit)
    if status:
        stmt = stmt.where(PipelineRun.status == status)

    result = await session.execute(stmt)
    runs = result.scalars().all()

    return [
        PipelineRunResponse(
            id=str(r.id),
            started_at=r.started_at,
            duration_seconds=r.duration_seconds,
            status=r.status,
            sources=r.sources if isinstance(r.sources, list) else [],
            items_extracted=r.items_extracted or 0,
            items_after_dedup=r.items_after_dedup or 0,
            items_seen_filtered=r.items_seen_filtered or 0,
            items_classified=r.items_classified or 0,
            items_validated=r.items_validated or 0,
            items_stored=r.items_stored or 0,
            error_message=r.error_message,
            correlation_id=r.correlation_id,
        )
        for r in runs
    ]


@router.get("/freshness", response_model=list[FreshnessResponse])
@limiter.limit("10/minute")
async def admin_freshness(
    request: Request,
    session: AsyncSession = Depends(get_session),
    _user: UserClaims = Depends(require_auth_or_guest),
) -> list[FreshnessResponse]:
    """Per-source content freshness: when was the last item stored?"""
    now = datetime.now(tz=UTC)

    result = await session.execute(
        select(
            NewsItem.source,
            func.max(NewsItem.created_at).label("last_item_at"),
        )
        .group_by(NewsItem.source)
        .order_by(NewsItem.source)
    )

    responses: list[FreshnessResponse] = []
    for r in result.all():
        last = r.last_item_at
        if last is None:
            hours_ago = None
            status = "dead"
        else:
            hours_ago = round((now - last).total_seconds() / 3600, 1)
            if hours_ago <= 2:
                status = "ok"
            elif hours_ago <= 24:
                status = "stale"
            else:
                status = "dead"

        responses.append(
            FreshnessResponse(
                source=r.source,
                last_item_at=last,
                hours_ago=hours_ago,
                status=status,
            )
        )

    return responses
