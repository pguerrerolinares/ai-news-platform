"""Tests for src.pipeline.stages.extract — extraction stage."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from src.extractors.base import ExtractedItem
from src.pipeline.stages.extract import get_extractors, run_extraction


def _mock_settings(**overrides):
    from src.core.config import Settings

    defaults = {
        "enabled_sources": "hackernews",
        "telegram_bot_token": "",
        "telegram_chat_id": "",
        "telegram_alerts_enabled": False,
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
