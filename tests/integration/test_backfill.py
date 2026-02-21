"""Integration test for backfill pipeline with mocked APIs."""

from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.models import RawExtraction

pytestmark = [pytest.mark.integration, pytest.mark.asyncio(loop_scope="session")]


class TestBackfillRawStorage:
    async def test_raw_extraction_idempotent(self, db_session: AsyncSession) -> None:
        """Inserting same source+source_id twice should not duplicate."""
        for _ in range(2):
            stmt = (
                insert(RawExtraction)
                .values(
                    source="hackernews",
                    source_id="test-123",
                    raw_json={"title": "Test", "points": 100},
                )
                .on_conflict_do_nothing(constraint="uq_raw_source_id")
            )
            await db_session.execute(stmt)
        await db_session.commit()

        result = await db_session.execute(
            select(RawExtraction).where(RawExtraction.source_id == "test-123")
        )
        items = result.scalars().all()
        assert len(items) == 1

    async def test_raw_json_queryable(self, db_session: AsyncSession) -> None:
        """JSONB fields should be queryable."""
        stmt = (
            insert(RawExtraction)
            .values(
                source="github",
                source_id="test/repo",
                raw_json={"stargazers_count": 500, "language": "Python"},
            )
            .on_conflict_do_nothing(constraint="uq_raw_source_id")
        )
        await db_session.execute(stmt)
        await db_session.commit()

        result = await db_session.execute(
            select(RawExtraction).where(
                RawExtraction.raw_json["stargazers_count"].as_integer() > 100
            )
        )
        items = result.scalars().all()
        assert len(items) >= 1
