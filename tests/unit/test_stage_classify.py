"""Tests for src.pipeline.stages.classify — classification stage."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from src.classifiers.base import ClassifiedItem
from src.extractors.base import ExtractedItem
from src.pipeline.stages.classify import run_classification


def _mock_settings(**overrides):
    from src.core.config import Settings

    defaults = {
        "enabled_sources": "hackernews",
        "openai_api_key": "",
        "telegram_bot_token": "",
        "telegram_chat_id": "",
        "telegram_alerts_enabled": False,
    }
    defaults.update(overrides)
    return Settings(**defaults)


def _make_item(title="Test", source="hackernews", url="https://example.com"):
    return ExtractedItem(title=title, source=source, url=url, score=100)


def _make_classified(item, topic="models"):
    return ClassifiedItem(
        item=item,
        topic=topic,
        relevance_score=0.9,
        summary="Test summary",
    )


class TestRunClassification:
    async def test_uses_keyword_classifier_when_no_api_key(self):
        settings = _mock_settings(openai_api_key="")
        items = [_make_item()]

        with (
            patch("src.pipeline.stages.classify.get_settings", return_value=settings),
            patch("src.pipeline.stages.classify.KeywordClassifier") as mock_cls,
        ):
            mock_instance = AsyncMock()
            mock_instance.classify = AsyncMock(return_value=[_make_classified(items[0])])
            mock_cls.return_value = mock_instance
            result = await run_classification(items)

        assert len(result) == 1
        mock_cls.assert_called_once()

    async def test_uses_llm_classifier_when_api_key_present(self):
        settings = _mock_settings(openai_api_key="sk-test")
        items = [_make_item()]

        with (
            patch("src.pipeline.stages.classify.get_settings", return_value=settings),
            patch("src.pipeline.stages.classify.LLMClassifier") as mock_cls,
            patch(
                "src.pipeline.stages.classify.deduplicate_events",
                new_callable=AsyncMock,
                return_value=[_make_classified(items[0])],
            ),
        ):
            mock_instance = AsyncMock()
            mock_instance.classify = AsyncMock(return_value=[_make_classified(items[0])])
            mock_cls.return_value = mock_instance
            result = await run_classification(items)

        assert len(result) == 1

    async def test_returns_empty_for_empty_input(self):
        settings = _mock_settings()
        with patch("src.pipeline.stages.classify.get_settings", return_value=settings):
            result = await run_classification([])
        assert result == []
