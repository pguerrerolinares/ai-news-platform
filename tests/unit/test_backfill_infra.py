"""Unit tests for backfill infrastructure — checkpoint and cost tracker."""

from __future__ import annotations

from pathlib import Path

from src.pipeline.backfill.checkpoint import BackfillCheckpoint
from src.pipeline.backfill.cost_tracker import CostTracker


class TestCheckpoint:
    def test_save_and_load(self, tmp_path: Path) -> None:
        cp_file = tmp_path / "checkpoint.json"
        cp = BackfillCheckpoint(cp_file)
        cp.update_source("hackernews", last_month="2024-03", last_page=5, items_stored=250)
        cp.save()

        loaded = BackfillCheckpoint.load(cp_file)
        assert loaded.sources["hackernews"]["last_month"] == "2024-03"
        assert loaded.sources["hackernews"]["items_stored"] == 250

    def test_resume_empty_file(self, tmp_path: Path) -> None:
        cp_file = tmp_path / "nonexistent.json"
        cp = BackfillCheckpoint.load(cp_file)
        assert cp.sources == {}

    def test_update_accumulates(self, tmp_path: Path) -> None:
        cp_file = tmp_path / "checkpoint.json"
        cp = BackfillCheckpoint(cp_file)
        cp.update_source("hackernews", last_month="2024-01", items_stored=100)
        cp.update_source("hackernews", last_month="2024-02", items_stored=200)
        assert cp.sources["hackernews"]["items_stored"] == 200
        assert cp.sources["hackernews"]["last_month"] == "2024-02"


class TestCostTracker:
    def test_track_tokens(self) -> None:
        tracker = CostTracker(max_cost_usd=10.0)
        tracker.add_tokens(input_tokens=1000, output_tokens=600)
        assert tracker.total_input_tokens == 1000
        assert tracker.total_output_tokens == 600
        assert tracker.estimated_cost_usd > 0

    def test_budget_exceeded(self) -> None:
        tracker = CostTracker(max_cost_usd=0.001)
        tracker.add_tokens(input_tokens=100_000, output_tokens=100_000)
        assert tracker.budget_exceeded

    def test_warning_threshold(self) -> None:
        tracker = CostTracker(max_cost_usd=0.01)
        # Cost = (50000 * 0.20 + 20000 * 2.00) / 1_000_000 = 0.01 + 0.04 = 0.05
        # That's 500% of 0.01 budget — way past warning
        tracker.add_tokens(input_tokens=50_000, output_tokens=20_000)
        assert tracker.at_warning_threshold
