"""Tests for event deduplication (fuzzy title matching)."""

from __future__ import annotations

from src.classifiers.event_dedup import (
    _group_by_similarity,
    _pick_winner,
    deduplicate_events,
)
from src.core.text_utils import title_similarity
from tests.factories import make_classified_item, make_extracted_item


# ---------------------------------------------------------------------------
# _title_similarity
# ---------------------------------------------------------------------------
class TestTitleSimilarity:
    def test_identical_titles(self):
        assert title_similarity("GPT-5 Released", "GPT-5 Released") == 1.0

    def test_case_insensitive(self):
        assert title_similarity("GPT-5 Released", "gpt-5 released") == 1.0

    def test_similar_titles(self):
        ratio = title_similarity("GPT-5 Released by OpenAI", "OpenAI Releases GPT-5")
        assert 0.4 <= ratio < 1.0  # Similar but reworded

    def test_different_titles(self):
        ratio = title_similarity("GPT-5 Released", "EU AI Act Regulation Update")
        assert ratio < 0.5


# ---------------------------------------------------------------------------
# _group_by_similarity
# ---------------------------------------------------------------------------
class TestGroupBySimilarity:
    def test_groups_similar_titles(self):
        items = [
            make_classified_item(
                title="GPT-5 Released by OpenAI",
                topic="models",
                item=make_extracted_item(title="GPT-5 Released by OpenAI", score=300),
            ),
            make_classified_item(
                title="GPT-5 Released by OpenAI today",
                topic="models",
                item=make_extracted_item(
                    title="GPT-5 Released by OpenAI today",
                    score=100,
                    url="https://example.com/2",
                ),
            ),
        ]
        groups = _group_by_similarity(items)
        assert len(groups) == 1
        assert sorted(groups[0]) == [0, 1]

    def test_keeps_different_titles_separate(self):
        items = [
            make_classified_item(
                title="GPT-5 Released",
                topic="models",
                item=make_extracted_item(title="GPT-5 Released", score=300),
            ),
            make_classified_item(
                title="Llama 4 Open Source Launch",
                topic="models",
                item=make_extracted_item(
                    title="Llama 4 Open Source Launch",
                    score=200,
                    url="https://example.com/llama",
                ),
            ),
        ]
        groups = _group_by_similarity(items)
        assert len(groups) == 2

    def test_transitive_grouping(self):
        """A~B and B~C should put A, B, C in same group."""
        items = [
            make_classified_item(
                title="OpenAI releases GPT-5 model weights",
                topic="models",
                item=make_extracted_item(title="OpenAI releases GPT-5 model weights", score=100),
            ),
            make_classified_item(
                title="OpenAI releases GPT-5 model weights today",
                topic="models",
                item=make_extracted_item(
                    title="OpenAI releases GPT-5 model weights today",
                    score=200,
                    url="https://example.com/2",
                ),
            ),
            make_classified_item(
                title="OpenAI releases GPT-5 model weights open source",
                topic="models",
                item=make_extracted_item(
                    title="OpenAI releases GPT-5 model weights open source",
                    score=50,
                    url="https://example.com/3",
                ),
            ),
        ]
        groups = _group_by_similarity(items)
        assert len(groups) == 1
        assert sorted(groups[0]) == [0, 1, 2]


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
    def test_empty_list(self):
        results = deduplicate_events([])
        assert results == []

    def test_single_item_no_dedup(self):
        item = make_classified_item(topic="models")
        results = deduplicate_events([item])
        assert len(results) == 1

    def test_dedup_same_event(self):
        """Two items with very similar titles should be deduped to one."""
        items = [
            make_classified_item(
                title="GPT-5 Released by OpenAI",
                topic="models",
                relevance_score=0.9,
                priority=2,
                item=make_extracted_item(title="GPT-5 Released by OpenAI", score=300),
            ),
            make_classified_item(
                title="GPT-5 Released by OpenAI today",
                topic="models",
                relevance_score=0.85,
                priority=3,
                item=make_extracted_item(
                    title="GPT-5 Released by OpenAI today",
                    score=100,
                    url="https://example.com/2",
                ),
            ),
        ]
        results = deduplicate_events(items)
        assert len(results) == 1
        assert results[0].item.title == "GPT-5 Released by OpenAI"
        assert results[0].trending is True
        assert results[0].source_count == 2

    def test_dedup_different_events(self):
        """Items about different events should remain separate."""
        items = [
            make_classified_item(
                title="GPT-5 Released",
                topic="models",
                relevance_score=0.9,
                item=make_extracted_item(title="GPT-5 Released", score=300),
            ),
            make_classified_item(
                title="Llama 4 Released",
                topic="models",
                relevance_score=0.85,
                item=make_extracted_item(
                    title="Llama 4 Released",
                    score=200,
                    url="https://example.com/llama",
                ),
            ),
        ]
        results = deduplicate_events(items)
        assert len(results) == 2

    def test_dedup_multiple_topics(self):
        """Each topic is deduped independently."""
        items = [
            make_classified_item(
                title="GPT-5 Released by OpenAI",
                topic="models",
                relevance_score=0.9,
                item=make_extracted_item(title="GPT-5 Released by OpenAI", score=300),
            ),
            make_classified_item(
                title="GPT-5 Released by OpenAI today",
                topic="models",
                relevance_score=0.85,
                item=make_extracted_item(
                    title="GPT-5 Released by OpenAI today",
                    score=100,
                    url="https://example.com/2",
                ),
            ),
            make_classified_item(
                title="EU AI Act Update",
                topic="regulation",
                relevance_score=0.8,
                item=make_extracted_item(
                    title="EU AI Act Update",
                    score=50,
                    url="https://example.com/eu",
                ),
            ),
        ]
        results = deduplicate_events(items)
        assert len(results) == 2
        topics = {r.topic for r in results}
        assert topics == {"models", "regulation"}

    def test_all_items_same_event(self):
        """All 5 items similar -> 1 winner with trending and source_count=5."""
        items = [
            make_classified_item(
                title=f"GPT-5 major breakthrough in AI announced #{i}",
                topic="models",
                relevance_score=0.85 + i * 0.02,
                priority=3,
                item=make_extracted_item(
                    title=f"GPT-5 major breakthrough in AI announced #{i}",
                    score=50 + i * 50,
                    url=f"https://example.com/{i}",
                ),
            )
            for i in range(5)
        ]
        results = deduplicate_events(items)
        assert len(results) == 1
        assert results[0].trending is True
        assert results[0].source_count == 5
