"""Unit tests for M16 Pydantic schemas."""

from __future__ import annotations

from datetime import UTC, date, datetime

from src.api.schemas import (
    BriefingResponse,
    ScoreDistributionResponse,
    SourceInfo,
    SourcesResponse,
    StatsGroupDateResponse,
)


class TestSourceSchemas:
    def test_source_info_fields(self):
        s = SourceInfo(name="hackernews", count=42)
        assert s.name == "hackernews"
        assert s.count == 42

    def test_sources_response_wraps_list(self):
        r = SourcesResponse(sources=[SourceInfo(name="arxiv", count=10)])
        assert len(r.sources) == 1


class TestStatsGroupDateResponse:
    def test_fields(self):
        r = StatsGroupDateResponse(date=date(2026, 2, 22), group="modelos", count=5)
        assert r.group == "modelos"
        assert r.count == 5


class TestScoreDistributionResponse:
    def test_fields(self):
        r = ScoreDistributionResponse(range="0-10", min_score=0, max_score=10, count=45)
        assert r.range == "0-10"
        assert r.count == 45


class TestBriefingResponseOptionalGeneratedAt:
    def test_generated_at_optional(self):
        b = BriefingResponse(date=date(2026, 2, 22), generated_at=None)
        assert b.generated_at is None

    def test_generated_at_with_value(self):
        dt = datetime(2026, 2, 22, 12, 0, tzinfo=UTC)
        b = BriefingResponse(date=date(2026, 2, 22), generated_at=dt)
        assert b.generated_at == dt
