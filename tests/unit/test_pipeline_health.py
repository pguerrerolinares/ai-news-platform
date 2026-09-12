"""Tests for src.pipeline.health -- scheduler liveness derived from pipeline_runs."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.pipeline.health import SCHEDULER_STALE_AFTER, last_run_started_at


def test_stale_after_is_45_minutes():
    """SCHEDULER_STALE_AFTER is the single threshold shared with admin-salud."""
    assert SCHEDULER_STALE_AFTER.total_seconds() == 45 * 60


class TestLastRunStartedAt:
    @pytest.mark.asyncio
    async def test_returns_max_started_at(self):
        expected = datetime(2026, 9, 13, 10, 0, tzinfo=UTC)
        result = MagicMock()
        result.scalar_one_or_none.return_value = expected
        session = AsyncMock()
        session.execute = AsyncMock(return_value=result)

        started_at = await last_run_started_at(session)

        assert started_at == expected

    @pytest.mark.asyncio
    async def test_returns_none_when_table_empty(self):
        result = MagicMock()
        result.scalar_one_or_none.return_value = None
        session = AsyncMock()
        session.execute = AsyncMock(return_value=result)

        started_at = await last_run_started_at(session)

        assert started_at is None
