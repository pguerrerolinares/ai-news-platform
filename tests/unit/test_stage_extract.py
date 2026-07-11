"""Tests for src.pipeline.stages.extract — extraction stage."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from src.core.metrics import extractor_errors_total
from src.extractors.base import ExtractedItem
from src.pipeline.circuit_breaker import CircuitBreaker
from src.pipeline.stages.extract import get_extractors, run_extraction


def _mock_settings(**overrides):
    from src.core.config import Settings

    defaults = {
        "enabled_sources": "hackernews",
    }
    defaults.update(overrides)
    return Settings(**defaults)


def _make_item(title="Test", source="hackernews", url="https://example.com"):
    return ExtractedItem(title=title, source=source, url=url, score=100)


class TestGetExtractors:
    def test_returns_enabled_extractors(self):
        settings = _mock_settings(enabled_sources="hackernews,arxiv")
        with patch("src.pipeline.stages.extract.get_settings", return_value=settings):
            extractors = get_extractors()
        names = [e.source_name for e in extractors]
        assert "hackernews" in names
        assert "arxiv" in names

    def test_filters_by_sources_param(self):
        settings = _mock_settings(enabled_sources="hackernews,arxiv,rss")
        with patch("src.pipeline.stages.extract.get_settings", return_value=settings):
            extractors = get_extractors(sources=["hackernews"])
        names = [e.source_name for e in extractors]
        assert names == ["hackernews"]

    def test_webscraper_included_when_enabled(self):
        settings = _mock_settings(enabled_sources="webscraper")
        with patch("src.pipeline.stages.extract.get_settings", return_value=settings):
            extractors = get_extractors()
        assert any(e.source_name == "webscraper" for e in extractors)

    def test_hackernews_leading_included_when_enabled(self):
        settings = _mock_settings(enabled_sources="hackernews_leading")
        with patch("src.pipeline.stages.extract.get_settings", return_value=settings):
            extractors = get_extractors()
        assert any(e.source_name == "hackernews_leading" for e in extractors)


class TestRunExtraction:
    async def test_returns_items_from_all_extractors(self):
        mock_extractor = AsyncMock()
        mock_extractor.source_name = "hackernews"
        mock_extractor.extract = AsyncMock(return_value=[_make_item()])

        settings = _mock_settings()
        with patch("src.pipeline.stages.extract.get_settings", return_value=settings):
            result = await run_extraction(extractors=[mock_extractor], since_hours=24)

        assert len(result) == 1

    async def test_handles_extractor_failure(self):
        mock_extractor = AsyncMock()
        mock_extractor.source_name = "hackernews"
        mock_extractor.extract = AsyncMock(side_effect=RuntimeError("API down"))

        settings = _mock_settings()
        with patch("src.pipeline.stages.extract.get_settings", return_value=settings):
            result = await run_extraction(extractors=[mock_extractor], since_hours=24)

        assert result == []

    async def test_returns_empty_when_no_extractors(self):
        settings = _mock_settings()
        with patch("src.pipeline.stages.extract.get_settings", return_value=settings):
            result = await run_extraction(extractors=[], since_hours=24)
        assert result == []


class TestRunExtractionCircuitBreaker:
    """run_extraction feeds per-source outcomes into the circuit breaker."""

    async def test_failure_recorded_for_the_failing_source_only(self):
        breaker = CircuitBreaker(threshold=3, cooldown_seconds=60)

        ext_bad = AsyncMock()
        ext_bad.source_name = "arxiv"
        ext_bad.extract = AsyncMock(side_effect=RuntimeError("selector changed"))

        ext_good = AsyncMock()
        ext_good.source_name = "hackernews"
        ext_good.extract = AsyncMock(return_value=[_make_item(source="hackernews")])

        result = await run_extraction(
            extractors=[ext_bad, ext_good], since_hours=24, circuit_breaker=breaker
        )

        assert len(result) == 1
        assert breaker._failures.get("arxiv") == 1
        assert "hackernews" not in breaker._failures

    async def test_success_resets_failure_count(self):
        breaker = CircuitBreaker(threshold=3, cooldown_seconds=60)
        breaker.record_failure("hackernews")

        ext = AsyncMock()
        ext.source_name = "hackernews"
        ext.extract = AsyncMock(return_value=[_make_item()])

        await run_extraction(extractors=[ext], since_hours=24, circuit_breaker=breaker)

        assert "hackernews" not in breaker._failures

    async def test_three_consecutive_failures_open_the_circuit(self):
        breaker = CircuitBreaker(threshold=3, cooldown_seconds=60)

        ext = AsyncMock()
        ext.source_name = "arxiv"
        ext.extract = AsyncMock(side_effect=RuntimeError("down"))

        for _ in range(3):
            await run_extraction(extractors=[ext], since_hours=24, circuit_breaker=breaker)

        assert breaker.is_open("arxiv") is True

    async def test_open_circuit_skips_extraction_without_calling_it(self):
        breaker = CircuitBreaker(threshold=1, cooldown_seconds=3600)
        breaker.record_failure("arxiv")
        assert breaker.is_open("arxiv") is True

        ext = AsyncMock()
        ext.source_name = "arxiv"
        ext.extract = AsyncMock(return_value=[_make_item(source="arxiv")])

        result = await run_extraction(extractors=[ext], since_hours=24, circuit_breaker=breaker)

        assert result == []
        ext.extract.assert_not_called()

    async def test_no_breaker_passed_behaves_as_before(self):
        ext = AsyncMock()
        ext.source_name = "hackernews"
        ext.extract = AsyncMock(side_effect=RuntimeError("boom"))

        result = await run_extraction(extractors=[ext], since_hours=24)

        assert result == []

    async def test_failure_increments_extractor_errors_metric(self):
        breaker = CircuitBreaker(threshold=3, cooldown_seconds=60)

        ext = AsyncMock()
        ext.source_name = "github"
        ext.extract = AsyncMock(side_effect=RuntimeError("rate limited"))

        before = extractor_errors_total.labels(source="github")._value.get()
        await run_extraction(extractors=[ext], since_hours=24, circuit_breaker=breaker)
        after = extractor_errors_total.labels(source="github")._value.get()

        assert after == before + 1
