"""Tests for src.pipeline.stages.score — composite scoring stage."""

from __future__ import annotations

from src.classifiers.base import ClassifiedItem
from src.extractors.base import ExtractedItem
from src.pipeline.stages.score import run_scoring


def _make_classified(title="Test", score=100):
    item = ExtractedItem(title=title, source="hackernews", url="https://example.com", score=score)
    return ClassifiedItem(item=item, topic="models", relevance_score=0.9, summary="Test")


class TestRunScoring:
    def test_scores_all_items(self):
        items = [_make_classified(), _make_classified(title="Second")]
        result = run_scoring(items)
        assert len(result) == 2

    def test_returns_empty_for_empty_input(self):
        result = run_scoring([])
        assert result == []
