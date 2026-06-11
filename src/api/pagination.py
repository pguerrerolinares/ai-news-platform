"""Pagination utilities for API endpoints."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import InstrumentedAttribute
from starlette.responses import Response

from src.core.models import NewsItem


def set_total_count_header(response: Response, count: int) -> None:
    """Set X-Total-Count header on a response."""
    response.headers["X-Total-Count"] = str(count)


async def count_query(
    session: AsyncSession,
    query: select,  # type: ignore[type-arg]
    pk: InstrumentedAttribute = NewsItem.id,
) -> int:
    """Count rows matching *query* via a subquery on *pk*.

    Uses ``with_only_columns`` so the original query's WHERE/JOIN clauses are
    preserved while the SELECT list is reduced to the primary-key column before
    wrapping in a COUNT subquery.
    """
    cq = select(func.count()).select_from(query.with_only_columns(pk).subquery())
    return (await session.execute(cq)).scalar_one()
