"""Tests for the LLM-based classifier."""

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import openai
import pytest

from src.classifiers.base import ClassifiedItem
from src.classifiers.llm import (
    BATCH_SIZE,
    LLMClassifier,
    _build_prompt,
    _parse_llm_json,
    llm_call,
)
from src.core.config import Settings
from tests.factories import make_extracted_item


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _make_settings(**overrides) -> Settings:
    defaults = {
        "topics": "models,tools,papers,products,open_source,agents,regulation",
        "min_relevance_score": 0.8,
        "openai_api_key": "test-key",
        "openai_base_url": "https://api.test.com/v1",
        "openai_model": "test-model",
    }
    defaults.update(overrides)
    return Settings(**defaults)


def _make_mock_client(response_content: str) -> MagicMock:
    """Create a mock AsyncOpenAI client that returns the given content."""
    mock_client = MagicMock(spec=openai.AsyncOpenAI)
    mock_message = SimpleNamespace(content=response_content)
    mock_choice = SimpleNamespace(message=mock_message)
    mock_response = SimpleNamespace(choices=[mock_choice])
    mock_client.chat = MagicMock()
    mock_client.chat.completions = MagicMock()
    mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
    return mock_client


def _make_llm_response(items: list[dict]) -> str:
    return json.dumps(items)


# ---------------------------------------------------------------------------
# _parse_llm_json
# ---------------------------------------------------------------------------
class TestParseLlmJson:
    def test_clean_json(self):
        raw = '[{"idx": 0, "is_news": true, "topic": "models", "relevance": 0.9}]'
        result = _parse_llm_json(raw)
        assert len(result) == 1
        assert result[0]["topic"] == "models"

    def test_json_with_code_fences(self):
        raw = '```json\n[{"idx": 0, "is_news": true}]\n```'
        result = _parse_llm_json(raw)
        assert len(result) == 1

    def test_json_with_bare_code_fences(self):
        raw = '```\n[{"idx": 0, "is_news": true}]\n```'
        result = _parse_llm_json(raw)
        assert len(result) == 1

    def test_json_with_surrounding_text(self):
        raw = 'Here is the result:\n[{"idx": 0, "is_news": true}]\nDone.'
        result = _parse_llm_json(raw)
        assert len(result) == 1

    def test_invalid_json_returns_empty(self):
        result = _parse_llm_json("not valid json at all")
        assert result == []

    def test_json_object_not_array_returns_empty(self):
        result = _parse_llm_json('{"idx": 0}')
        assert result == []

    def test_empty_array(self):
        result = _parse_llm_json("[]")
        assert result == []

    def test_multiline_json(self):
        raw = """[
  {"idx": 0, "is_news": true, "topic": "models", "relevance": 0.85},
  {"idx": 1, "is_news": false}
]"""
        result = _parse_llm_json(raw)
        assert len(result) == 2


# ---------------------------------------------------------------------------
# _build_prompt
# ---------------------------------------------------------------------------
class TestBuildPrompt:
    def test_prompt_contains_items(self):
        items = [
            make_extracted_item(title="GPT-5 Released", source="hackernews", score=100),
            make_extracted_item(title="New Paper on ArXiv", source="arxiv", score=0),
        ]
        prompt = _build_prompt(items, "- models: description")
        assert "GPT-5 Released" in prompt
        assert "New Paper on ArXiv" in prompt
        assert "[0]" in prompt
        assert "[1]" in prompt

    def test_prompt_contains_topics_info(self):
        prompt = _build_prompt(
            [make_extracted_item()],
            '- "models": New models\n- "papers": Academic papers',
        )
        assert "models" in prompt
        assert "papers" in prompt

    def test_prompt_contains_classification_rules(self):
        prompt = _build_prompt([make_extracted_item()], "topics")
        assert "is_news" in prompt
        assert "REJECT" in prompt
        assert "ACCEPT" in prompt
        assert "RELEVANCE SCALE" in prompt

    def test_prompt_batch_size_in_text(self):
        items = [make_extracted_item(title=f"Item {i}") for i in range(3)]
        prompt = _build_prompt(items, "topics")
        assert "Classify these 3 items" in prompt


# ---------------------------------------------------------------------------
# llm_call
# ---------------------------------------------------------------------------
class TestLlmCall:
    async def test_successful_call(self):
        client = _make_mock_client("test response")
        result = await llm_call(client, "model", "system", "prompt")
        assert result == "test response"
        client.chat.completions.create.assert_called_once()

    async def test_retries_on_rate_limit(self):
        client = _make_mock_client("")
        client.chat.completions.create = AsyncMock(
            side_effect=[
                openai.RateLimitError(
                    message="rate limited",
                    response=MagicMock(status_code=429),
                    body=None,
                ),
                SimpleNamespace(
                    choices=[SimpleNamespace(message=SimpleNamespace(content="success"))]
                ),
            ]
        )
        with patch("src.classifiers.llm.asyncio.sleep", new_callable=AsyncMock):
            result = await llm_call(client, "model", "system", "prompt")
        assert result == "success"
        assert client.chat.completions.create.call_count == 2

    async def test_retries_on_timeout(self):
        client = _make_mock_client("")
        client.chat.completions.create = AsyncMock(
            side_effect=[
                openai.APITimeoutError(request=MagicMock()),
                SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="ok"))]),
            ]
        )
        with patch("src.classifiers.llm.asyncio.sleep", new_callable=AsyncMock):
            result = await llm_call(client, "model", "system", "prompt")
        assert result == "ok"

    async def test_retries_on_connection_error(self):
        client = _make_mock_client("")
        client.chat.completions.create = AsyncMock(
            side_effect=[
                openai.APIConnectionError(request=MagicMock()),
                SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="ok"))]),
            ]
        )
        with patch("src.classifiers.llm.asyncio.sleep", new_callable=AsyncMock):
            result = await llm_call(client, "model", "system", "prompt")
        assert result == "ok"

    async def test_exhausts_retries_and_raises(self):
        client = _make_mock_client("")
        exc = openai.RateLimitError(
            message="rate limited",
            response=MagicMock(status_code=429),
            body=None,
        )
        client.chat.completions.create = AsyncMock(side_effect=exc)
        with (
            patch("src.classifiers.llm.asyncio.sleep", new_callable=AsyncMock),
            pytest.raises(openai.RateLimitError),
        ):
            await llm_call(client, "model", "system", "prompt")
        assert client.chat.completions.create.call_count == 3

    async def test_no_retry_on_other_api_error(self):
        client = _make_mock_client("")
        client.chat.completions.create = AsyncMock(
            side_effect=openai.BadRequestError(
                message="bad request",
                response=MagicMock(status_code=400),
                body=None,
            )
        )
        with pytest.raises(openai.BadRequestError):
            await llm_call(client, "model", "system", "prompt")
        assert client.chat.completions.create.call_count == 1


# ---------------------------------------------------------------------------
# LLMClassifier.classify()
# ---------------------------------------------------------------------------
class TestLLMClassifier:
    @pytest.fixture(autouse=True)
    def _patch_settings(self):
        with (
            patch(
                "src.classifiers.llm.get_settings",
                return_value=_make_settings(),
            ),
            patch(
                "src.classifiers.keyword.get_settings",
                return_value=_make_settings(),
            ),
        ):
            yield

    def _make_classifier(self, response_content: str) -> tuple[LLMClassifier, MagicMock]:
        client = _make_mock_client(response_content)
        classifier = LLMClassifier(client=client)
        return classifier, client

    async def test_classify_single_item(self):
        response = _make_llm_response(
            [
                {
                    "idx": 0,
                    "is_news": True,
                    "topic": "models",
                    "relevance": 0.9,
                    "summary": "Nuevo modelo GPT-5 con mejoras significativas",
                },
            ]
        )
        classifier, _ = self._make_classifier(response)
        items = [
            make_extracted_item(
                title="GPT-5 Released",
                text="OpenAI releases GPT-5 with major improvements",
                score=200,
            )
        ]
        results = await classifier.classify(items)
        assert len(results) == 1
        assert results[0].topic == "models"
        assert results[0].relevance_score == 0.9
        assert results[0].summary == "Nuevo modelo GPT-5 con mejoras significativas"
        assert isinstance(results[0], ClassifiedItem)

    async def test_classify_filters_not_news(self):
        response = _make_llm_response(
            [
                {"idx": 0, "is_news": False},
                {
                    "idx": 1,
                    "is_news": True,
                    "topic": "models",
                    "relevance": 0.85,
                    "summary": "Resumen de prueba",
                },
            ]
        )
        classifier, _ = self._make_classifier(response)
        items = [
            make_extracted_item(title="Just an opinion"),
            make_extracted_item(title="GPT-5 Released"),
        ]
        results = await classifier.classify(items)
        assert len(results) == 1
        assert results[0].item.title == "GPT-5 Released"

    async def test_classify_filters_below_min_relevance(self):
        response = _make_llm_response(
            [
                {
                    "idx": 0,
                    "is_news": True,
                    "topic": "models",
                    "relevance": 0.75,
                    "summary": "Resumen",
                },
            ]
        )
        classifier, _ = self._make_classifier(response)
        items = [make_extracted_item(title="Minor update")]
        results = await classifier.classify(items)
        assert len(results) == 0  # 0.75 < 0.8 threshold

    async def test_classify_filters_disabled_topics(self):
        with patch(
            "src.classifiers.llm.get_settings",
            return_value=_make_settings(topics="papers,agents"),
        ):
            response = _make_llm_response(
                [
                    {
                        "idx": 0,
                        "is_news": True,
                        "topic": "models",
                        "relevance": 0.9,
                        "summary": "Resumen",
                    },
                ]
            )
            classifier, _ = self._make_classifier(response)
            items = [make_extracted_item(title="GPT-5")]
            results = await classifier.classify(items)
            assert len(results) == 0  # models not in enabled topics

    async def test_classify_empty_list(self):
        classifier, _ = self._make_classifier("[]")
        results = await classifier.classify([])
        assert results == []

    async def test_classify_batching(self):
        """Items are processed in batches of BATCH_SIZE."""
        response = _make_llm_response(
            [
                {
                    "idx": i,
                    "is_news": True,
                    "topic": "models",
                    "relevance": 0.9,
                    "summary": f"Resumen {i}",
                }
                for i in range(BATCH_SIZE)
            ]
        )
        client = _make_mock_client(response)
        classifier = LLMClassifier(client=client)

        items = [
            make_extracted_item(
                title=f"GPT model {i} with LLM transformer architecture SOTA MMLU benchmark",
                url=f"https://example.com/{i}",
                score=100,
            )
            for i in range(BATCH_SIZE + 3)
        ]

        # The second batch returns results for indices 0-2
        response2 = _make_llm_response(
            [
                {
                    "idx": i,
                    "is_news": True,
                    "topic": "models",
                    "relevance": 0.9,
                    "summary": f"Resumen batch2 {i}",
                }
                for i in range(3)
            ]
        )
        client.chat.completions.create = AsyncMock(
            side_effect=[
                SimpleNamespace(
                    choices=[SimpleNamespace(message=SimpleNamespace(content=response))]
                ),
                SimpleNamespace(
                    choices=[SimpleNamespace(message=SimpleNamespace(content=response2))]
                ),
            ]
        )

        results = await classifier.classify(items)
        assert client.chat.completions.create.call_count == 2
        assert len(results) == BATCH_SIZE + 3

    async def test_fallback_to_keyword_on_api_error(self):
        client = _make_mock_client("")
        client.chat.completions.create = AsyncMock(
            side_effect=openai.BadRequestError(
                message="bad request",
                response=MagicMock(status_code=400),
                body=None,
            )
        )
        classifier = LLMClassifier(client=client)
        items = [
            make_extracted_item(
                title="GPT-5 LLM achieves SOTA on MMLU benchmark with transformer architecture",
                text="New model training fine-tuning attention weights parameters",
                score=100,
            ),
        ]
        results = await classifier.classify(items)
        # Should fall back to keyword classifier
        assert len(results) >= 1
        assert results[0].topic == "models"

    async def test_fallback_on_rate_limit_exhaustion(self):
        client = _make_mock_client("")
        exc = openai.RateLimitError(
            message="rate limited",
            response=MagicMock(status_code=429),
            body=None,
        )
        client.chat.completions.create = AsyncMock(side_effect=exc)
        classifier = LLMClassifier(client=client)
        items = [
            make_extracted_item(
                title="GPT-5 LLM achieves SOTA on MMLU benchmark with transformer architecture",
                text="New model training fine-tuning attention weights parameters",
                score=100,
            ),
        ]
        with patch("src.classifiers.llm.asyncio.sleep", new_callable=AsyncMock):
            results = await classifier.classify(items)
        # Should fall back to keyword classifier after retries exhausted
        assert len(results) >= 1

    async def test_classify_handles_invalid_idx(self):
        response = _make_llm_response(
            [
                {
                    "idx": 99,
                    "is_news": True,
                    "topic": "models",
                    "relevance": 0.9,
                    "summary": "Resumen",
                },
                {
                    "idx": -1,
                    "is_news": True,
                    "topic": "models",
                    "relevance": 0.9,
                    "summary": "Resumen",
                },
                {
                    "idx": 0,
                    "is_news": True,
                    "topic": "models",
                    "relevance": 0.9,
                    "summary": "Resumen valido",
                },
            ]
        )
        classifier, _ = self._make_classifier(response)
        items = [make_extracted_item(title="GPT-5", score=100)]
        results = await classifier.classify(items)
        assert len(results) == 1
        assert results[0].summary == "Resumen valido"

    async def test_classify_handles_malformed_llm_response(self):
        """Malformed JSON in response triggers fallback."""
        client = _make_mock_client("This is not valid JSON at all!!!")
        classifier = LLMClassifier(client=client)
        items = [
            make_extracted_item(
                title="GPT-5 LLM achieves SOTA on MMLU benchmark with transformer architecture",
                text="New model training fine-tuning attention weights parameters",
                score=100,
            ),
        ]
        # Malformed response -> empty parse -> no results from LLM
        # But this does NOT trigger fallback since the call itself succeeded
        # The LLM batch just returns 0 classified items
        results = await classifier.classify(items)
        # The parse returns empty list but no exception, so no fallback
        assert len(results) == 0

    async def test_classify_priority_calculation(self):
        response = _make_llm_response(
            [
                {
                    "idx": 0,
                    "is_news": True,
                    "topic": "models",
                    "relevance": 0.95,
                    "summary": "Resumen",
                },
            ]
        )
        classifier, _ = self._make_classifier(response)
        items = [make_extracted_item(title="GPT-5", score=600)]
        results = await classifier.classify(items)
        assert len(results) == 1
        # score 600 -> priority 1, relevance 0.95 -> -2, clamped to 1
        assert results[0].priority == 1

    async def test_classify_creates_client_from_settings(self):
        """When no client provided, creates one from settings."""
        settings = _make_settings()
        with patch("src.classifiers.llm.get_settings", return_value=settings):
            classifier = LLMClassifier()
            # We can't actually call classify without a real client,
            # but we can test that _get_client creates one
            mock_instance = MagicMock()
            with patch(
                "src.classifiers.llm.openai.AsyncOpenAI",
                return_value=mock_instance,
            ) as mock_cls:
                client = classifier._get_client()
                mock_cls.assert_called_once_with(
                    api_key="test-key",
                    base_url="https://api.test.com/v1",
                )
                assert client is mock_instance


# ---------------------------------------------------------------------------
# Edge-case tests: _parse_llm_json
# ---------------------------------------------------------------------------
class TestParseLlmJsonEdgeCases:
    def test_truncated_json(self):
        """Truncated JSON string returns empty list."""
        result = _parse_llm_json('[{"topic": "models"')
        assert result == []

    def test_empty_string_parse(self):
        """Empty string returns empty list."""
        result = _parse_llm_json("")
        assert result == []


# ---------------------------------------------------------------------------
# Edge-case tests: LLMClassifier
# ---------------------------------------------------------------------------
class TestLLMClassifierEdgeCases:
    @pytest.fixture(autouse=True)
    def _patch_settings(self):
        with (
            patch(
                "src.classifiers.llm.get_settings",
                return_value=_make_settings(),
            ),
            patch(
                "src.classifiers.keyword.get_settings",
                return_value=_make_settings(),
            ),
        ):
            yield

    async def test_batch_partial_failure(self):
        """First batch OK, second raises -> first batch results + fallback for second."""
        # Build a response for the first batch (BATCH_SIZE items, all classified)
        first_batch_response = _make_llm_response(
            [
                {
                    "idx": i,
                    "is_news": True,
                    "topic": "models",
                    "relevance": 0.9,
                    "summary": f"Resumen batch1 item {i}",
                }
                for i in range(BATCH_SIZE)
            ]
        )

        # Create enough items to trigger 2 batches
        items = [
            make_extracted_item(
                title=f"GPT model {i} LLM transformer SOTA MMLU benchmark architecture",
                text="New model training fine-tuning attention weights parameters",
                url=f"https://example.com/{i}",
                score=100,
            )
            for i in range(BATCH_SIZE + 2)
        ]

        client = _make_mock_client(first_batch_response)
        # First call succeeds, second raises
        client.chat.completions.create = AsyncMock(
            side_effect=[
                SimpleNamespace(
                    choices=[
                        SimpleNamespace(
                            message=SimpleNamespace(content=first_batch_response),
                        )
                    ]
                ),
                openai.BadRequestError(
                    message="bad request",
                    response=MagicMock(status_code=400),
                    body=None,
                ),
            ]
        )

        classifier = LLMClassifier(client=client)
        results = await classifier.classify(items)

        assert client.chat.completions.create.call_count == 2
        # First batch: BATCH_SIZE LLM results; second batch: 2 items via keyword fallback
        # Keyword fallback may or may not classify items depending on keyword matches
        # But we should have at least the BATCH_SIZE from the first batch
        assert len(results) >= BATCH_SIZE

    async def test_non_retryable_auth_error(self):
        """AuthenticationError is NOT retryable -> falls back immediately, only 1 call."""
        client = _make_mock_client("")
        client.chat.completions.create = AsyncMock(
            side_effect=openai.AuthenticationError(
                message="invalid api key",
                response=MagicMock(status_code=401),
                body=None,
            )
        )
        classifier = LLMClassifier(client=client)
        items = [
            make_extracted_item(
                title="GPT-5 LLM achieves SOTA on MMLU benchmark with transformer architecture",
                text="New model training fine-tuning attention weights parameters",
                score=100,
            ),
        ]
        results = await classifier.classify(items)
        # AuthenticationError is not retryable, so only 1 call
        assert client.chat.completions.create.call_count == 1
        # Falls back to keyword classifier, which should classify this item
        assert len(results) >= 1
        assert results[0].topic == "models"
