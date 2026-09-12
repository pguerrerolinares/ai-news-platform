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
    LLMParseError,
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


_CALL_OPTS: dict = {"temperature": 0.6, "extra_body": None}


def _quota_error() -> openai.RateLimitError:
    """Moonshot's 429 when the account is suspended for insufficient balance."""
    return openai.RateLimitError(
        message="Your account is suspended due to insufficient balance",
        response=MagicMock(status_code=429),
        body={"message": "insufficient balance", "type": "exceeded_current_quota_error"},
    )


def _config_errors() -> list[openai.APIStatusError]:
    """Errors that neither retries nor the keyword fallback can fix."""
    return [
        openai.NotFoundError(
            message="Not found the model kimi-latest or Permission denied",
            response=MagicMock(status_code=404),
            body=None,
        ),
        openai.BadRequestError(
            message="invalid temperature: only 1 is allowed for this model",
            response=MagicMock(status_code=400),
            body=None,
        ),
        openai.AuthenticationError(
            message="invalid api key", response=MagicMock(status_code=401), body=None
        ),
        _quota_error(),
    ]


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

    def test_invalid_json_raises_parse_error(self):
        """Garbage text with no array must not be silently swallowed as []."""
        with pytest.raises(LLMParseError):
            _parse_llm_json("not valid json at all")

    def test_json_object_not_array_raises_parse_error(self):
        """A valid JSON value that isn't an array is still a parse failure."""
        with pytest.raises(LLMParseError):
            _parse_llm_json('{"idx": 0}')

    def test_empty_array(self):
        """Only a literal, valid JSON array -- including "[]" -- is success."""
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
        assert "RELEVANCE SCORING" in prompt

    def test_prompt_contains_anchor_examples(self):
        """Prompt should use concrete anchor examples for relevance scoring."""
        items = [make_extracted_item(title="Test", source="github")]
        prompt = _build_prompt(items, "models: AI models")
        assert "OpenAI releases GPT-5" in prompt
        assert "FORCED DISTRIBUTION" in prompt
        assert "MUST NOT give more than" in prompt

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
        result = await llm_call(client, "model", "system", "prompt", **_CALL_OPTS)
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
            result = await llm_call(client, "model", "system", "prompt", **_CALL_OPTS)
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
            result = await llm_call(client, "model", "system", "prompt", **_CALL_OPTS)
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
            result = await llm_call(client, "model", "system", "prompt", **_CALL_OPTS)
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
            await llm_call(client, "model", "system", "prompt", **_CALL_OPTS)
        assert client.chat.completions.create.call_count == 5

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
            await llm_call(client, "model", "system", "prompt", **_CALL_OPTS)
        assert client.chat.completions.create.call_count == 1

    async def test_passes_temperature_and_extra_body(self):
        client = _make_mock_client("ok")
        await llm_call(
            client,
            "kimi-k2.6",
            "system",
            "prompt",
            temperature=0.6,
            extra_body={"thinking": {"type": "disabled"}},
        )
        kwargs = client.chat.completions.create.call_args.kwargs
        assert kwargs["model"] == "kimi-k2.6"
        assert kwargs["temperature"] == pytest.approx(0.6)
        assert kwargs["extra_body"] == {"thinking": {"type": "disabled"}}

    async def test_no_retry_on_insufficient_balance(self):
        """A suspended account is not a transient rate limit: retrying only burns time."""
        client = _make_mock_client("")
        client.chat.completions.create = AsyncMock(side_effect=_quota_error())
        with (
            patch("src.classifiers.llm.asyncio.sleep", new_callable=AsyncMock),
            pytest.raises(openai.RateLimitError),
        ):
            await llm_call(client, "model", "system", "prompt", **_CALL_OPTS)
        assert client.chat.completions.create.call_count == 1


# ---------------------------------------------------------------------------
# Retry backoff
# ---------------------------------------------------------------------------
class TestRetryBackoff:
    """Tests for retry constants and jitter."""

    def test_max_retries_is_five(self):
        from src.classifiers.llm import MAX_RETRIES

        assert MAX_RETRIES == 5

    def test_retry_backoff_has_four_elements(self):
        from src.classifiers.llm import RETRY_BACKOFF

        assert len(RETRY_BACKOFF) == 4
        assert RETRY_BACKOFF == [2, 5, 15, 30]

    async def test_jitter_applied_to_sleep(self):
        """Verify sleep duration includes jitter (>= base wait)."""
        mock_client = _make_mock_client("test")
        mock_client.chat.completions.create = AsyncMock(
            side_effect=[
                openai.RateLimitError(
                    message="rate limited",
                    response=MagicMock(status_code=429, headers={}),
                    body=None,
                ),
                openai.RateLimitError(
                    message="rate limited",
                    response=MagicMock(status_code=429, headers={}),
                    body=None,
                ),
                openai.RateLimitError(
                    message="rate limited",
                    response=MagicMock(status_code=429, headers={}),
                    body=None,
                ),
                openai.RateLimitError(
                    message="rate limited",
                    response=MagicMock(status_code=429, headers={}),
                    body=None,
                ),
                SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="ok"))]),
            ]
        )
        with patch("src.classifiers.llm.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            result = await llm_call(mock_client, "model", "system", "prompt", **_CALL_OPTS)
        assert result == "ok"
        assert mock_sleep.await_count == 4
        for i, call in enumerate(mock_sleep.await_args_list):
            base = [2, 5, 15, 30][i]
            assert call.args[0] >= base

    async def test_five_failures_exhausts_retries(self):
        """After 5 failures, retries are exhausted and exception is raised."""
        mock_client = _make_mock_client("test")
        mock_client.chat.completions.create = AsyncMock(
            side_effect=openai.RateLimitError(
                message="rate limited",
                response=MagicMock(status_code=429, headers={}),
                body=None,
            )
        )
        with (
            patch("src.classifiers.llm.asyncio.sleep", new_callable=AsyncMock),
            pytest.raises(openai.RateLimitError),
        ):
            await llm_call(mock_client, "model", "system", "prompt", **_CALL_OPTS)
        assert mock_client.chat.completions.create.await_count == 5


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

    @pytest.mark.parametrize("error", _config_errors(), ids=lambda e: type(e).__name__)
    async def test_config_or_account_error_raises_instead_of_fallback(self, error):
        """Retired model, bad params, bad key or no balance must fail the run, not degrade it."""
        client = _make_mock_client("")
        client.chat.completions.create = AsyncMock(side_effect=error)
        classifier = LLMClassifier(client=client)
        items = [make_extracted_item(title="GPT-5 LLM achieves SOTA on MMLU benchmark")]
        with (
            patch("src.classifiers.llm.asyncio.sleep", new_callable=AsyncMock),
            pytest.raises(type(error)),
        ):
            await classifier.classify(items)

    async def test_classify_sends_model_options_from_settings(self):
        settings = _make_settings(
            openai_temperature=0.6, openai_extra_body={"thinking": {"type": "disabled"}}
        )
        classifier, client = self._make_classifier(_make_llm_response([]))
        with patch("src.classifiers.llm.get_settings", return_value=settings):
            await classifier.classify([make_extracted_item()])
        kwargs = client.chat.completions.create.call_args.kwargs
        assert kwargs["model"] == "test-model"
        assert kwargs["temperature"] == pytest.approx(0.6)
        assert kwargs["extra_body"] == {"thinking": {"type": "disabled"}}

    async def test_fallback_to_keyword_on_server_error(self):
        client = _make_mock_client("")
        client.chat.completions.create = AsyncMock(
            side_effect=openai.InternalServerError(
                message="internal error",
                response=MagicMock(status_code=500),
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
        """Malformed (non-parseable) JSON must NOT be silently dropped as 0 results.

        It must raise LLMParseError internally, which activates the existing
        KeywordClassifier fallback for that batch (#5) -- not silently lose it.
        """
        client = _make_mock_client("This is not valid JSON at all!!!")
        classifier = LLMClassifier(client=client)
        items = [
            make_extracted_item(
                title="GPT-5 LLM achieves SOTA on MMLU benchmark with transformer architecture",
                text="New model training fine-tuning attention weights parameters",
                score=100,
            ),
        ]
        with patch("src.classifiers.llm.logger") as mock_logger:
            results = await classifier.classify(items)

        # Keyword fallback picks up the strong AI-keyword title -> not lost in silence.
        assert len(results) >= 1
        assert results[0].topic == "models"
        # A parse-failure-specific error log was emitted (distinct from the generic
        # "llm_batch_failed_using_fallback" warning already logged for other errors).
        error_events = [call.args[0] for call in mock_logger.error.call_args_list]
        assert "llm_response_not_parseable" in error_events

    async def test_classify_malformed_response_increments_parse_failure_metric(self):
        """A non-parseable LLM response increments the parse-failure metric (#5)."""
        from src.core.metrics import llm_parse_failures_total

        before = llm_parse_failures_total._value.get()
        client = _make_mock_client("This is not valid JSON at all!!!")
        classifier = LLMClassifier(client=client)
        items = [make_extracted_item(title="GPT-5 model release", score=100)]

        await classifier.classify(items)

        assert llm_parse_failures_total._value.get() == before + 1

    async def test_classify_legitimate_empty_array_does_not_fall_back(self):
        """A literal "[]" response is success (no news in the batch), not a failure."""
        client = _make_mock_client("[]")
        classifier = LLMClassifier(client=client)
        items = [make_extracted_item(title="GPT-5 model release", score=100)]

        with patch("src.classifiers.llm.logger") as mock_logger:
            results = await classifier.classify(items)

        assert results == []
        error_events = [call.args[0] for call in mock_logger.error.call_args_list]
        assert "llm_response_not_parseable" not in error_events

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
    def test_truncated_json_raises_parse_error(self):
        """Truncated JSON (e.g. response cut off mid-array) is a parse failure."""
        with pytest.raises(LLMParseError):
            _parse_llm_json('[{"topic": "models"')

    def test_empty_string_raises_parse_error(self):
        """Empty response -- the LLM returned nothing -- is a parse failure."""
        with pytest.raises(LLMParseError):
            _parse_llm_json("")

    def test_whitespace_only_raises_parse_error(self):
        """Whitespace-only response is a parse failure, not a legitimate []."""
        with pytest.raises(LLMParseError):
            _parse_llm_json("\n\n")

    def test_text_without_array_raises_parse_error(self):
        """Prose with no JSON array anywhere in it is a parse failure."""
        with pytest.raises(LLMParseError):
            _parse_llm_json("I cannot classify these items right now.")

    def test_legitimate_empty_array_is_not_a_parse_error(self):
        """A literal "[]" is a valid, successful response (no items to classify)."""
        assert _parse_llm_json("[]") == []


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
                openai.InternalServerError(
                    message="internal error",
                    response=MagicMock(status_code=500),
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
        """AuthenticationError is NOT retryable and NOT hidden by the fallback: 1 call, raises."""
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
        with pytest.raises(openai.AuthenticationError):
            await classifier.classify(items)
        assert client.chat.completions.create.call_count == 1
