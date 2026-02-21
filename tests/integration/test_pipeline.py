"""Integration tests for the pipeline -> DB interaction."""

from __future__ import annotations

import pytest
from sqlalchemy import func, select

from src.core.models import NewsItem

pytestmark = [pytest.mark.integration, pytest.mark.asyncio(loop_scope="session")]


class TestSmoke:
    async def test_db_connection_works(self, db_session):
        """Verify we can connect to the test database."""
        result = await db_session.execute(select(func.count(NewsItem.id)))
        assert result.scalar_one() == 0  # empty after rollback
