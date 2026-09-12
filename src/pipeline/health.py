"""Scheduler liveness derived from pipeline_runs.

Single source of truth for "is the scheduler stuck": both the Docker
healthcheck (``scripts/pipeline_healthcheck.py``) and the future
admin-salud panel consume ``SCHEDULER_STALE_AFTER`` and
``last_run_started_at`` so the two never disagree on the threshold.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.models import PipelineRun

# Trade-off (accepted): the container healthcheck now depends on the DB. If
# the DB is down, pipeline-cron restart-loops — acceptable, the API would be
# down too in that scenario.
SCHEDULER_STALE_AFTER = timedelta(minutes=45)


async def last_run_started_at(session: AsyncSession) -> datetime | None:
    """Return the most recent ``pipeline_runs.started_at``, or None if empty."""
    result = await session.execute(select(func.max(PipelineRun.started_at)))
    return result.scalar_one_or_none()
