"""Tests for event deduplication."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import openai
import pytest

from src.classifiers.event_dedup import (
    _build_dedup_prompt,
    _parse_groups,
    _pick_winner,
    deduplicate_events,
)
from src.core.config import Settings
from tests.factories import make_classified_item, make_extracted_item


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _make_settings(**overrides) -> Settings:
    defaults = {
        "topics": "modelos,herramientas,papers,productos,open_source,agentes,regulacion",
        "min_relevance_score": 0.8,
        "openai_api_key": "test-key",
        "openai_base_url": "https://api.test.com/v1",
        "openai_model": "test-model",
    }
    defaults.update(overrides)
    return Settings(**defaults)


def _make_mock_client(response_content: str) -> MagicMock:
    """Create a mock AsyncOpenAI client."""
    mock_client = MagicMock(spec=openai.AsyncOpenAI)
    mock_message = SimpleNamespace(content=response_content)
    mock_choice = SimpleNamespace(message=mock_message)
    mock_response = SimpleNamespace(choices=[mock_choice])
    mock_client.chat = MagicMock()
    mock_client.chat.completions = MagicMock()
    mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
    return mock_client


# ---------------------------------------------------------------------------
# _parse_groups
# ---------------------------------------------------------------------------
class TestParseGroups:
    def test_valid_groups(self):
        raw = "[[0, 3, 5], [1], [2, 4]]"
        result = _parse_groups(raw)
        assert result == [[0, 3, 5], [1], [2, 4]]

    def test_with_code_fences(self):
        raw = "```json\n[[0, 1], [2]]\n```"
        result = _parse_groups(raw)
        assert result == [[0, 1], [2]]

    def test_with_surrounding_text(self):
        raw = "Here are the groups:\n[[0, 1], [2]]\nDone."
        result = _parse_groups(raw)
        assert result == [[0, 1], [2]]

    def test_invalid_json(self):
        result = _parse_groups("not json")
        assert result is None

    def test_not_array_of_arrays(self):
        result = _parse_groups("[1, 2, 3]")
        assert result is None

    def test_empty_array(self):
        result = _parse_groups("[]")
        assert result == []

    def test_single_group(self):
        result = _parse_groups("[[0, 1, 2]]")
        assert result == [[0, 1, 2]]


# ---------------------------------------------------------------------------
# _build_dedup_prompt
# ---------------------------------------------------------------------------
class TestBuildDedupPrompt:
    def test_contains_item_info(self):
        items = [
            make_classified_item(title="GPT-5 Released", source="hackernews", relevance_score=0.9),
            make_classified_item(title="GPT-5 Launch", source="reddit", relevance_score=0.85),
        ]
        prompt = _build_dedup_prompt(items)
        assert "GPT-5 Released" in prompt
        assert "GPT-5 Launch" in prompt
        assert "[0]" in prompt
        assert "[1]" in prompt

    def test_contains_batch_size(self):
        items = [make_classified_item() for _ in range(3)]
        prompt = _build_dedup_prompt(items)
        assert "3 items" in prompt


# ---------------------------------------------------------------------------
# _pick_winner
# ---------------------------------------------------------------------------
class TestPickWinner:
    def test_picks_highest_combined_score(self):
        item1 = make_classified_item(
            title="Lower score",
            relevance_score=0.8,
            item=make_extracted_item(title="Lower score", score=50),
        )
        item2 = make_classified_item(
            title="Higher score",
            relevance_score=0.9,
            item=make_extracted_item(title="Higher score", score=300),
        )
        winner = _pick_winner([item1, item2])
        assert winner.item.title == "Higher score"

    def test_winner_is_trending(self):
        item1 = make_classified_item(
            item=make_extracted_item(score=10),
        )
        item2 = make_classified_item(
            item=make_extracted_item(score=100, url="https://example.com/2"),
        )
        winner = _pick_winner([item1, item2])
        assert winner.trending is True

    def test_winner_source_count(self):
        items = [
            make_classified_item(item=make_extracted_item(score=100)),
            make_classified_item(
                item=make_extracted_item(score=50, url="https://example.com/2"),
            ),
            make_classified_item(
                item=make_extracted_item(score=10, url="https://example.com/3"),
            ),
        ]
        winner = _pick_winner(items)
        assert winner.source_count == 3

    def test_winner_priority_boost(self):
        item = make_classified_item(
            priority=3,
            item=make_extracted_item(score=100),
        )
        winner = _pick_winner([item])
        assert winner.priority == 2  # 3 - 1 = 2

    def test_priority_clamped_to_1(self):
        item = make_classified_item(
            priority=1,
            item=make_extracted_item(score=100),
        )
        winner = _pick_winner([item])
        assert winner.priority == 1  # max(1, 1-1) = 1


# ---------------------------------------------------------------------------
# deduplicate_events
# ---------------------------------------------------------------------------
class TestDeduplicateEvents:
    @pytest.fixture(autouse=True)
    def _patch_settings(self):
        with patch(
            "src.classifiers.event_dedup.get_settings",
            return_value=_make_settings(),
        ):
            yield

    async def test_empty_list(self):
        results = await deduplicate_events([], client=_make_mock_client("[]"))
        assert results == []

    async def test_single_item_no_dedup(self):
        item = make_classified_item(topic="modelos")
        client = _make_mock_client("[[0]]")
        results = await deduplicate_events([item], client=client)
        assert len(results) == 1
        # Single item in topic: no LLM call needed
        client.chat.completions.create.assert_not_called()

    async def test_dedup_same_event(self):
        """Two items about the same event should be deduped to one."""
        items = [
            make_classified_item(
                title="GPT-5 Released by OpenAI",
                topic="modelos",
                relevance_score=0.9,
                priority=2,
                item=make_extracted_item(title="GPT-5 Released by OpenAI", score=300),
            ),
            make_classified_item(
                title="OpenAI Launches GPT-5",
                topic="modelos",
                relevance_score=0.85,
                priority=3,
                item=make_extracted_item(
                    title="OpenAI Launches GPT-5",
                    score=100,
                    url="https://example.com/2",
                ),
            ),
        ]
        client = _make_mock_client("[[0, 1]]")
        results = await deduplicate_events(items, client=client)
        assert len(results) == 1
        assert results[0].item.title == "GPT-5 Released by OpenAI"  # Higher score
        assert results[0].trending is True
        assert results[0].source_count == 2

    async def test_dedup_different_events(self):
        """Items about different events should remain separate."""
        items = [
            make_classified_item(
                title="GPT-5 Released",
                topic="modelos",
                relevance_score=0.9,
                item=make_extracted_item(title="GPT-5 Released", score=300),
            ),
            make_classified_item(
                title="Llama 4 Released",
                topic="modelos",
                relevance_score=0.85,
                item=make_extracted_item(
                    title="Llama 4 Released",
                    score=200,
                    url="https://example.com/llama",
                ),
            ),
        ]
        client = _make_mock_client("[[0], [1]]")
        results = await deduplicate_events(items, client=client)
        assert len(results) == 2

    async def test_dedup_multiple_topics(self):
        """Each topic is deduped independently."""
        items = [
            make_classified_item(
                title="GPT-5 Released",
                topic="modelos",
                relevance_score=0.9,
                item=make_extracted_item(title="GPT-5 Released", score=300),
            ),
            make_classified_item(
                title="GPT-5 also here",
                topic="modelos",
                relevance_score=0.85,
                item=make_extracted_item(
                    title="GPT-5 also here",
                    score=100,
                    url="https://example.com/2",
                ),
            ),
            make_classified_item(
                title="EU AI Act Update",
                topic="regulacion",
                relevance_score=0.8,
                item=make_extracted_item(
                    title="EU AI Act Update",
                    score=50,
                    url="https://example.com/eu",
                ),
            ),
        ]
        # For modelos: group [0,1]; for regulacion: single item, no LLM call
        client = _make_mock_client("[[0, 1]]")
        results = await deduplicate_events(items, client=client)
        assert len(results) == 2  # 1 from modelos dedup + 1 from regulacion
        topics = {r.topic for r in results}
        assert topics == {"modelos", "regulacion"}

    async def test_graceful_fallback_on_llm_failure(self):
        """On LLM failure, keep all items as-is."""
        items = [
            make_classified_item(
                title="GPT-5 Released",
                topic="modelos",
                relevance_score=0.9,
                item=make_extracted_item(title="GPT-5 Released", score=300),
            ),
            make_classified_item(
                title="GPT-5 Launch",
                topic="modelos",
                relevance_score=0.85,
                item=make_extracted_item(
                    title="GPT-5 Launch",
                    score=100,
                    url="https://example.com/2",
                ),
            ),
        ]
        client = _make_mock_client("")
        exc = openai.RateLimitError(
            message="rate limited",
            response=MagicMock(status_code=429),
            body=None,
        )
        client.chat.completions.create = AsyncMock(side_effect=exc)

        with patch("src.classifiers.llm.asyncio.sleep", new_callable=AsyncMock):
            results = await deduplicate_events(items, client=client)

        # All items kept on failure
        assert len(results) == 2

    async def test_graceful_fallback_on_parse_failure(self):
        """On parse failure, keep all items."""
        items = [
            make_classified_item(
                title="Item 1",
                topic="modelos",
                item=make_extracted_item(title="Item 1", score=100),
            ),
            make_classified_item(
                title="Item 2",
                topic="modelos",
                item=make_extracted_item(
                    title="Item 2",
                    score=50,
                    url="https://example.com/2",
                ),
            ),
        ]
        client = _make_mock_client("totally invalid json garbage!!!")
        results = await deduplicate_events(items, client=client)
        assert len(results) == 2

    async def test_orphaned_items_are_kept(self):
        """Items not mentioned in any group are kept."""
        items = [
            make_classified_item(
                title="Item 0",
                topic="modelos",
                item=make_extracted_item(title="Item 0", score=100),
            ),
            make_classified_item(
                title="Item 1",
                topic="modelos",
                item=make_extracted_item(
                    title="Item 1",
                    score=200,
                    url="https://example.com/1",
                ),
            ),
            make_classified_item(
                title="Item 2",
                topic="modelos",
                item=make_extracted_item(
                    title="Item 2",
                    score=50,
                    url="https://example.com/2",
                ),
            ),
        ]
        # Only groups items 0 and 1, item 2 is orphaned
        client = _make_mock_client("[[0, 1]]")
        results = await deduplicate_events(items, client=client)
        # Group [0,1] -> 1 winner + orphaned item 2 = 2 total
        assert len(results) == 2
        titles = {r.item.title for r in results}
        assert "Item 2" in titles

    async def test_handles_invalid_indices_in_groups(self):
        """Invalid indices in groups are filtered out."""
        items = [
            make_classified_item(
                title="Item 0",
                topic="modelos",
                item=make_extracted_item(title="Item 0", score=100),
            ),
            make_classified_item(
                title="Item 1",
                topic="modelos",
                item=make_extracted_item(
                    title="Item 1",
                    score=200,
                    url="https://example.com/1",
                ),
            ),
        ]
        # Index 99 is invalid
        client = _make_mock_client("[[0, 99], [1]]")
        results = await deduplicate_events(items, client=client)
        assert len(results) == 2
