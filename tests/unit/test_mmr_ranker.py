"""Tests for the MMR diversification ranker."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from src.feed.mmr_ranker import _jaccard, item_similarity, mmr_rank


def _make_item(**kwargs: object) -> SimpleNamespace:
    defaults: dict = {
        "source": "hackernews",
        "topic": "models",
        "author": "anon",
        "title": "test",
        "composite_score": 0.5,
    }
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


# ---------- _jaccard helper ----------


class TestJaccard:
    def test_identical_texts(self) -> None:
        assert _jaccard("hello world", "hello world") == 1.0

    def test_disjoint_texts(self) -> None:
        assert _jaccard("hello world", "foo bar") == 0.0

    def test_partial_overlap(self) -> None:
        score = _jaccard("hello world foo", "hello world bar")
        # intersection={hello,world}, union={hello,world,foo,bar} -> 2/4=0.5
        assert score == pytest.approx(0.5)

    def test_empty_text(self) -> None:
        assert _jaccard("", "hello") == 0.0
        assert _jaccard("hello", "") == 0.0
        assert _jaccard("", "") == 0.0


# ---------- item_similarity ----------


class TestItemSimilarity:
    def test_same_source_adds_03(self) -> None:
        a = _make_item(source="hackernews", topic="x", author=None, title="")
        b = _make_item(source="hackernews", topic="y", author=None, title="")
        assert item_similarity(a, b) == pytest.approx(0.3)

    def test_same_topic_adds_03(self) -> None:
        a = _make_item(source="x", topic="models", author=None, title="")
        b = _make_item(source="y", topic="models", author=None, title="")
        assert item_similarity(a, b) == pytest.approx(0.3)

    def test_same_author_adds_02(self) -> None:
        a = _make_item(source="x", topic="y", author="alice", title="")
        b = _make_item(source="z", topic="w", author="alice", title="")
        assert item_similarity(a, b) == pytest.approx(0.2)

    def test_title_overlap_adds_up_to_02(self) -> None:
        # Identical titles -> jaccard=1.0 -> 0.2 * 1.0 = 0.2
        a = _make_item(source="x", topic="y", author=None, title="hello world")
        b = _make_item(source="z", topic="w", author=None, title="hello world")
        assert item_similarity(a, b) == pytest.approx(0.2)

    def test_completely_different_items_low_similarity(self) -> None:
        a = _make_item(source="hackernews", topic="models", author="alice", title="AI advances")
        b = _make_item(source="arxiv", topic="tools", author="bob", title="Database optimization")
        sim = item_similarity(a, b)
        assert sim < 0.2

    def test_identical_items_high_similarity(self) -> None:
        a = _make_item(
            source="hackernews",
            topic="models",
            author="alice",
            title="Large language models are great",
        )
        b = _make_item(
            source="hackernews",
            topic="models",
            author="alice",
            title="Large language models are great",
        )
        sim = item_similarity(a, b)
        assert sim >= 0.9

    def test_none_author_not_counted(self) -> None:
        a = _make_item(author=None)
        b = _make_item(author=None)
        # source + topic match = 0.6, but author should NOT add 0.2
        # (both are None, but the guard checks for truthiness)
        sim = item_similarity(a, b)
        # source(0.3) + topic(0.3) + title(jaccard("test","test")=1.0 * 0.2) = 0.8
        assert sim == pytest.approx(0.8)


# ---------- mmr_rank ----------


class TestMmrRank:
    def test_empty_input_returns_empty(self) -> None:
        assert mmr_rank([]) == []

    def test_first_item_is_highest_composite_score(self) -> None:
        items = [
            _make_item(composite_score=0.3, source="a", topic="a", title="a"),
            _make_item(composite_score=0.9, source="b", topic="b", title="b"),
            _make_item(composite_score=0.6, source="c", topic="c", title="c"),
        ]
        result = mmr_rank(items)
        assert result[0].composite_score == 0.9

    def test_lambda_1_pure_quality_order(self) -> None:
        items = [
            _make_item(composite_score=0.3, source="a", topic="a", title="aaa"),
            _make_item(composite_score=0.9, source="b", topic="b", title="bbb"),
            _make_item(composite_score=0.6, source="c", topic="c", title="ccc"),
        ]
        result = mmr_rank(items, lambda_=1.0)
        scores = [r.composite_score for r in result]
        assert scores == [0.9, 0.6, 0.3]

    def test_limit_respected(self) -> None:
        items = [_make_item(composite_score=i / 10, source=str(i), topic=str(i)) for i in range(10)]
        result = mmr_rank(items, limit=3)
        assert len(result) == 3

    def test_fewer_items_than_limit_returns_all(self) -> None:
        items = [_make_item(composite_score=0.5), _make_item(composite_score=0.3)]
        result = mmr_rank(items, limit=20)
        assert len(result) == 2

    def test_diversity_promotion(self) -> None:
        """When 2 HF/models items and 1 HN/tools item, MMR with lambda=0.5
        should place the diverse HN item at position 2 over the similar HF item."""
        hf_high = _make_item(
            source="huggingface", topic="models", composite_score=0.9, title="New model A"
        )
        hf_low = _make_item(
            source="huggingface", topic="models", composite_score=0.85, title="New model B"
        )
        hn_diverse = _make_item(
            source="hackernews", topic="tools", composite_score=0.7, title="Dev tool release"
        )
        result = mmr_rank([hf_high, hf_low, hn_diverse], lambda_=0.5, limit=3)
        # First should be highest quality
        assert result[0] is hf_high
        # Second should be the diverse HN item (diversity bonus beats HF #2's quality)
        assert result[1] is hn_diverse
        # Third is the remaining HF item
        assert result[2] is hf_low

    def test_does_not_mutate_input(self) -> None:
        items = [
            _make_item(composite_score=0.5, source="a"),
            _make_item(composite_score=0.3, source="b"),
        ]
        original_len = len(items)
        mmr_rank(items, limit=1)
        assert len(items) == original_len
