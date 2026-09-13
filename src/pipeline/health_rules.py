"""Pure health-evaluation rules for `GET /api/admin/health`.

No DB session, no settings, no I/O: every rule is a plain function over
in-memory data (see `src/api/routes/admin.py::admin_health` for the caller
that fetches those inputs). Kept separate from `src/pipeline/health.py`
(scheduler-liveness threshold shared with the Docker healthcheck) per SRP.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timedelta
from typing import Literal

from pydantic import BaseModel

from src.core.models import PipelineRun
from src.pipeline.health import SCHEDULER_STALE_AFTER

# --- Constants -------------------------------------------------------------

RUN_WINDOW = timedelta(hours=24)
RUNS_FAILING_STREAK = 3
RUNS_DEGRADED_STREAK = 3
RUNS_STORING_NOTHING_MIN = 10
FAILING_STATUSES = frozenset({"error"})
NEUTRAL_STATUSES = frozenset({"empty", "interrupted"})  # excluded from the informative sequence
STORING_STATUSES = frozenset({"success", "degraded"})

_SCHEDULER_STALE_MINUTES = int(SCHEDULER_STALE_AFTER.total_seconds() // 60)

_MSG_RUNS_FAILING = "The last 3 pipeline runs failed."
_MSG_RUNS_STORING_NOTHING = (
    "Pipeline runs have completed for 24 h without storing any item; "
    "the classifier or the filters may be rejecting everything."
)
_MSG_RUNS_DEGRADED = (
    "The last 3 pipeline runs stored items but failed to generate embeddings; "
    "semantic search is falling behind."
)
_MSG_CLASSIFIER_KEYWORD_ONLY = (
    "LLM classifier is not configured; the keyword fallback is active and "
    "almost nothing will pass the relevance threshold."
)

# --- Schema ------------------------------------------------------------

HealthSeverity = Literal["critical", "warning"]
HealthCode = Literal[
    "scheduler_silent",
    "runs_failing",
    "runs_storing_nothing",
    "runs_degraded",
    "classifier_keyword_only",
    "sources_dead",
]


class HealthAlert(BaseModel):
    severity: HealthSeverity
    code: HealthCode
    message: str
    since: datetime | None


# --- Helpers -----------------------------------------------------------


def _streak(seq: Sequence[PipelineRun], statuses: frozenset[str]) -> list[PipelineRun]:
    """Return the leading run of consecutive elements whose status is in `statuses`.

    `seq` must already be ordered by `started_at` descending (most recent first).
    """
    out: list[PipelineRun] = []
    for run in seq:
        if run.status not in statuses:
            break
        out.append(run)
    return out


# --- Rules (one per HealthCode, in fixed a->f order) ------------------------


def _rule_scheduler_silent(*, now: datetime, last_run_at: datetime | None) -> HealthAlert | None:
    if last_run_at is not None and now - last_run_at <= SCHEDULER_STALE_AFTER:
        return None
    return HealthAlert(
        severity="critical",
        code="scheduler_silent",
        message=(
            f"No pipeline run has started in the last {_SCHEDULER_STALE_MINUTES} minutes. "
            "The scheduler may be down."
        ),
        since=last_run_at,
    )


def _rule_runs_failing(informative_runs: Sequence[PipelineRun]) -> HealthAlert | None:
    streak = _streak(informative_runs, FAILING_STATUSES)
    if len(streak) < RUNS_FAILING_STREAK:
        return None
    return HealthAlert(
        severity="critical",
        code="runs_failing",
        message=_MSG_RUNS_FAILING,
        since=streak[-1].started_at,
    )


def _rule_runs_storing_nothing(runs: Sequence[PipelineRun]) -> HealthAlert | None:
    storing = [r for r in runs if r.status in STORING_STATUSES and r.items_extracted > 0]
    if len(storing) < RUNS_STORING_NOTHING_MIN:
        return None
    if not all(r.items_stored == 0 for r in storing):
        return None
    return HealthAlert(
        severity="critical",
        code="runs_storing_nothing",
        message=_MSG_RUNS_STORING_NOTHING,
        since=min(r.started_at for r in storing),
    )


def _rule_runs_degraded(informative_runs: Sequence[PipelineRun]) -> HealthAlert | None:
    streak = _streak(informative_runs, frozenset({"degraded"}))
    if len(streak) < RUNS_DEGRADED_STREAK:
        return None
    return HealthAlert(
        severity="warning",
        code="runs_degraded",
        message=_MSG_RUNS_DEGRADED,
        since=streak[-1].started_at,
    )


def _rule_classifier_keyword_only(*, has_llm_key: bool) -> HealthAlert | None:
    if has_llm_key:
        return None
    return HealthAlert(
        severity="warning",
        code="classifier_keyword_only",
        message=_MSG_CLASSIFIER_KEYWORD_ONLY,
        since=None,
    )


def _rule_sources_dead(dead_sources: Sequence[str]) -> HealthAlert | None:
    if not dead_sources:
        return None
    names = ", ".join(sorted(dead_sources))
    return HealthAlert(
        severity="warning",
        code="sources_dead",
        message=f"No new items in over 24 h from: {names}.",
        since=None,
    )


# --- Entry point ---------------------------------------------------------


def evaluate_health(
    *,
    now: datetime,
    last_run_at: datetime | None,
    runs: Sequence[PipelineRun],
    dead_sources: Sequence[str],
    has_llm_key: bool,
) -> list[HealthAlert]:
    """Evaluate rules a-f and return the resulting alerts, most severe first.

    `runs` is expected to already be scoped to `RUN_WINDOW` by the caller
    (see the route's query); this function sorts it but does not re-filter
    by time. `empty` and `interrupted` runs are excluded from the
    failing/degraded streaks (`NEUTRAL_STATUSES`): `empty` returns before
    classify/store and says nothing about either; `interrupted` is a
    cancellation (deploy restarts pipeline-cron and cancels every in-flight
    tier at once, per verdict `2026-09-13-pipeline-runs-interrupted`), so it
    neither counts as a failure nor breaks a real failure streak. Neither is
    filtered out of `runs` itself since `runs_storing_nothing` already
    excludes them via `STORING_STATUSES`.
    """
    ordered_runs = sorted(runs, key=lambda r: r.started_at, reverse=True)
    informative_runs = [r for r in ordered_runs if r.status not in NEUTRAL_STATUSES]

    rules = (
        _rule_scheduler_silent(now=now, last_run_at=last_run_at),
        _rule_runs_failing(informative_runs),
        _rule_runs_storing_nothing(ordered_runs),
        _rule_runs_degraded(informative_runs),
        _rule_classifier_keyword_only(has_llm_key=has_llm_key),
        _rule_sources_dead(dead_sources),
    )
    return [alert for alert in rules if alert is not None]
