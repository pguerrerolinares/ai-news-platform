"""Tests for src.pipeline.stages.score — composite scoring stage."""

from __future__ import annotations

from src.classifiers.base import ClassifiedItem
from src.core.metrics import scoring_duration_seconds
from src.extractors.base import ExtractedItem
from src.pipeline.stages.score import run_scoring


def _histogram_sample_count(histogram) -> float:
    for family in histogram.collect():
        for sample in family.samples:
            if sample.name.endswith("_count"):
                return sample.value
    raise AssertionError("no _count sample found")


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

    def test_records_scoring_duration_metric(self):
        """#31: score.py had no metric before this; scoring_duration_seconds
        must observe a sample per non-empty run_scoring call."""
        before = _histogram_sample_count(scoring_duration_seconds)
        run_scoring([_make_classified()])
        after = _histogram_sample_count(scoring_duration_seconds)

        assert after == before + 1
