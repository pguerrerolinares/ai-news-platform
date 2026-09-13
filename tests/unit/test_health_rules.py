"""Unit tests for the pure health-evaluation rules (src/pipeline/health_rules.py).

Pure module, no DB, no settings: every rule is exercised through
`evaluate_health` with a fixed `now` and synthetic `PipelineRun` instances
(never persisted, never flushed to a session).
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime, timedelta

from src.core.models import PipelineRun
from src.pipeline.health_rules import evaluate_health

NOW = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)


def _run(minutes_ago: float, status: str, extracted: int = 1, stored: int = 1) -> PipelineRun:
    return PipelineRun(
        started_at=NOW - timedelta(minutes=minutes_ago),
        duration_seconds=1.0,
        status=status,
        sources=[],
        items_extracted=extracted,
        items_stored=stored,
    )


def _evaluate(
    runs: Sequence[PipelineRun],
    *,
    last_run_at: datetime | None = NOW,
    has_llm_key: bool = True,
    dead_sources: Sequence[str] = (),
):
    return evaluate_health(
        now=NOW,
        last_run_at=last_run_at,
        runs=runs,
        dead_sources=dead_sources,
        has_llm_key=has_llm_key,
    )


def _codes(alerts) -> list[str]:
    return [a.code for a in alerts]


# ---------------------------------------------------------------------------
# (a) scheduler_silent
# ---------------------------------------------------------------------------
class TestSchedulerSilent:
    def test_exactly_45_minutes_does_not_fire(self):
        alerts = _evaluate([], last_run_at=NOW - timedelta(minutes=45))
        assert "scheduler_silent" not in _codes(alerts)

    def test_45_minutes_and_1_second_fires(self):
        last_run_at = NOW - timedelta(minutes=45, seconds=1)
        alerts = _evaluate([], last_run_at=last_run_at)
        alert = next(a for a in alerts if a.code == "scheduler_silent")
        assert alert.severity == "critical"
        assert alert.since == last_run_at

    def test_no_runs_ever_fires_with_since_none(self):
        alerts = _evaluate([], last_run_at=None)
        alert = next(a for a in alerts if a.code == "scheduler_silent")
        assert alert.since is None


# ---------------------------------------------------------------------------
# (b) runs_failing
# ---------------------------------------------------------------------------
class TestRunsFailing:
    def test_two_errors_does_not_fire(self):
        runs = [_run(5, "error"), _run(10, "error")]
        assert "runs_failing" not in _codes(_evaluate(runs))

    def test_three_errors_fires(self):
        runs = [_run(5, "error"), _run(10, "error"), _run(15, "error")]
        alert = next(a for a in _evaluate(runs) if a.code == "runs_failing")
        assert alert.severity == "critical"

    def test_empty_ignored_since_is_oldest_of_streak(self):
        # Sequence (most recent first): error, empty, interrupted, empty, error
        runs = [
            _run(5, "error"),
            _run(10, "empty"),
            _run(15, "interrupted"),
            _run(20, "empty"),
            _run(25, "error"),
        ]
        alert = next(a for a in _evaluate(runs) if a.code == "runs_failing")
        assert alert.since == NOW - timedelta(minutes=25)

    def test_recent_success_blocks_streak(self):
        runs = [
            _run(5, "success"),
            _run(10, "error"),
            _run(15, "error"),
            _run(20, "error"),
        ]
        assert "runs_failing" not in _codes(_evaluate(runs))


# ---------------------------------------------------------------------------
# (c) runs_storing_nothing
# ---------------------------------------------------------------------------
class TestRunsStoringNothing:
    def test_ten_success_stored_zero_fires(self):
        runs = [_run(10 * i, "success", extracted=1, stored=0) for i in range(1, 11)]
        alert = next(a for a in _evaluate(runs) if a.code == "runs_storing_nothing")
        assert alert.severity == "critical"
        assert alert.since == NOW - timedelta(minutes=100)

    def test_nine_does_not_fire(self):
        runs = [_run(10 * i, "success", extracted=1, stored=0) for i in range(1, 10)]
        assert "runs_storing_nothing" not in _codes(_evaluate(runs))

    def test_ten_with_one_stored_does_not_fire(self):
        runs = [_run(10 * i, "success", extracted=1, stored=0) for i in range(1, 10)]
        runs.append(_run(100, "success", extracted=1, stored=1))
        assert "runs_storing_nothing" not in _codes(_evaluate(runs))

    def test_ten_stored_zero_plus_degraded_stored_nonzero_does_not_fire(self):
        runs = [_run(10 * i, "success", extracted=1, stored=0) for i in range(1, 11)]
        runs.append(_run(200, "degraded", extracted=1, stored=5))
        assert "runs_storing_nothing" not in _codes(_evaluate(runs))

    def test_ten_success_stored_zero_extracted_zero_does_not_fire(self):
        runs = [_run(10 * i, "success", extracted=0, stored=0) for i in range(1, 11)]
        assert "runs_storing_nothing" not in _codes(_evaluate(runs))


# ---------------------------------------------------------------------------
# (d) runs_degraded
# ---------------------------------------------------------------------------
class TestRunsDegraded:
    def test_three_degraded_fires_as_warning(self):
        runs = [_run(5, "degraded"), _run(10, "degraded"), _run(15, "degraded")]
        alert = next(a for a in _evaluate(runs) if a.code == "runs_degraded")
        assert alert.severity == "warning"

    def test_two_degraded_does_not_fire(self):
        runs = [_run(5, "degraded"), _run(10, "degraded")]
        assert "runs_degraded" not in _codes(_evaluate(runs))

    def test_error_breaks_streak(self):
        runs = [
            _run(5, "degraded"),
            _run(10, "error"),
            _run(15, "degraded"),
            _run(20, "degraded"),
        ]
        assert "runs_degraded" not in _codes(_evaluate(runs))


# ---------------------------------------------------------------------------
# (e) classifier_keyword_only
# ---------------------------------------------------------------------------
class TestClassifierKeywordOnly:
    def test_no_llm_key_fires_with_since_none(self):
        alert = next(
            a for a in _evaluate([], has_llm_key=False) if a.code == "classifier_keyword_only"
        )
        assert alert.severity == "warning"
        assert alert.since is None

    def test_llm_key_present_does_not_fire(self):
        assert "classifier_keyword_only" not in _codes(_evaluate([], has_llm_key=True))


# ---------------------------------------------------------------------------
# (f) sources_dead
# ---------------------------------------------------------------------------
class TestSourcesDead:
    def test_no_dead_sources_does_not_fire(self):
        assert "sources_dead" not in _codes(_evaluate([], dead_sources=[]))

    def test_dead_sources_fire_sorted_in_message(self):
        alert = next(
            a for a in _evaluate([], dead_sources=["rss", "arxiv"]) if a.code == "sources_dead"
        )
        assert alert.severity == "warning"
        assert "arxiv, rss" in alert.message


# ---------------------------------------------------------------------------
# Ordering: critical before warning, fixed a->f order within severity
# ---------------------------------------------------------------------------
class TestOrdering:
    def test_scenario_one(self):
        runs = [_run(10 * i, "success", extracted=1, stored=0) for i in range(1, 11)]
        alerts = _evaluate(runs, last_run_at=None, has_llm_key=False, dead_sources=["rss"])
        assert _codes(alerts) == [
            "scheduler_silent",
            "runs_storing_nothing",
            "classifier_keyword_only",
            "sources_dead",
        ]

    def test_scenario_two(self):
        old_storing = [_run(60 * i, "success", extracted=1, stored=0) for i in range(2, 12)]
        recent_errors = [_run(5, "error"), _run(10, "error"), _run(15, "error")]
        alerts = _evaluate(old_storing + recent_errors)
        assert _codes(alerts) == ["runs_failing", "runs_storing_nothing"]

    def test_no_triggers_returns_empty_list(self):
        assert _evaluate([]) == []
