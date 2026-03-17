"""Tests for src.pipeline.stages.classify — two-phase classification stage."""

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


def _make_item(title="New GPT model release", source="hackernews", url="https://example.com"):
    """Item with 1-2 keyword matches (ambiguous → sent to LLM)."""
    return ExtractedItem(title=title, source=source, url=url, score=100)


def _make_high_confidence_item():
    """Item with >=3 keyword matches (auto-accepted by keyword pre-filter)."""
    return ExtractedItem(
        title="GPT-5 LLM achieves SOTA on MMLU benchmark with transformer architecture",
        source="hackernews",
        url="https://example.com/gpt5",
        score=300,
    )


def _make_no_match_item():
    """Item with 0 keyword matches (auto-rejected)."""
    return ExtractedItem(
        title="Best pizza recipe for dinner tonight",
        source="hackernews",
        url="https://example.com/pizza",
        score=10,
    )


def _make_classified(item, topic="models"):
    return ClassifiedItem(
        item=item,
        topic=topic,
        relevance_score=0.9,
        summary="Test summary",
    )


class TestRunClassification:
    async def test_high_confidence_auto_accepted(self):
        """Items with >=3 keyword matches skip LLM."""
        settings = _mock_settings(openai_api_key="sk-test")
        item = _make_high_confidence_item()

        with patch("src.pipeline.stages.classify.get_settings", return_value=settings):
            result = await run_classification([item])

        assert len(result) == 1
        assert result[0].topic == "models"
        assert result[0].summary is None  # No LLM = no summary

    async def test_no_match_auto_rejected(self):
        """Items with 0 keyword matches are rejected without LLM."""
        settings = _mock_settings(openai_api_key="sk-test")
        item = _make_no_match_item()

        with patch("src.pipeline.stages.classify.get_settings", return_value=settings):
            result = await run_classification([item])

        assert len(result) == 0

    async def test_ambiguous_sent_to_llm(self):
        """Items with 1-2 keyword matches go to LLM classifier."""
        settings = _mock_settings(openai_api_key="sk-test")
        item = _make_item()  # 1-2 matches

        with (
            patch("src.pipeline.stages.classify.get_settings", return_value=settings),
            patch("src.pipeline.stages.classify.LLMClassifier") as mock_cls,
        ):
            mock_instance = AsyncMock()
            mock_instance.classify = AsyncMock(return_value=[_make_classified(item)])
            mock_cls.return_value = mock_instance
            result = await run_classification([item])

        mock_cls.assert_called_once()
        assert len(result) >= 1

    async def test_ambiguous_uses_keyword_when_no_api_key(self):
        """Without API key, ambiguous items fall back to KeywordClassifier."""
        settings = _mock_settings(openai_api_key="")
        item = _make_item()

        with (
            patch("src.pipeline.stages.classify.get_settings", return_value=settings),
            patch("src.pipeline.stages.classify.KeywordClassifier") as mock_cls,
        ):
            mock_instance = AsyncMock()
            mock_instance.classify = AsyncMock(return_value=[_make_classified(item)])
            mock_cls.return_value = mock_instance
            result = await run_classification([item])

        mock_cls.assert_called_once()
        assert len(result) >= 1

    async def test_mixed_items_split_correctly(self):
        """Mix of high-confidence, ambiguous, and no-match items."""
        settings = _mock_settings(openai_api_key="sk-test")
        high = _make_high_confidence_item()
        ambiguous = _make_item(title="New AI agent tool", url="https://example.com/2")
        no_match = _make_no_match_item()

        with (
            patch("src.pipeline.stages.classify.get_settings", return_value=settings),
            patch("src.pipeline.stages.classify.LLMClassifier") as mock_cls,
        ):
            mock_instance = AsyncMock()
            mock_instance.classify = AsyncMock(
                return_value=[_make_classified(ambiguous, topic="agents")]
            )
            mock_cls.return_value = mock_instance
            result = await run_classification([high, ambiguous, no_match])

        # high → auto-accepted, ambiguous → LLM, no_match → rejected
        assert len(result) == 2
        topics = {r.topic for r in result}
        assert "models" in topics  # high confidence
        assert "agents" in topics  # from LLM

    async def test_returns_empty_for_empty_input(self):
        settings = _mock_settings()
        with patch("src.pipeline.stages.classify.get_settings", return_value=settings):
            result = await run_classification([])
        assert result == []
