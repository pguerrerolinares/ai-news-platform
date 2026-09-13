"""Docker healthcheck for pipeline-cron — replaces the old `os.kill(1, 0)` no-op.

Liveness is derived from `pipeline_runs` (src.pipeline.health), the same
criterion the admin-salud panel will use: a scheduler that stopped firing
jobs (hung event loop, crashed process still holding PID 1) is unhealthy
even though the process itself is alive.

Semantics: exit 0 only if a run started within SCHEDULER_STALE_AFTER; exit 1
for an empty table, a stale run, or any error (DB down, timeout) — fail
closed. Kept fast (<5s total) and quiet: no structlog, this runs on every
HEALTHCHECK interval.
"""

from __future__ import annotations

import asyncio
import sys
from datetime import UTC, datetime

from src.core.database import get_async_session
from src.pipeline.health import SCHEDULER_STALE_AFTER, last_run_started_at

_TOTAL_TIMEOUT_SECONDS = 5.0


async def _is_healthy() -> bool:
    async with get_async_session() as session:
        started_at = await last_run_started_at(session)
    if started_at is None:
        return False
    return (datetime.now(tz=UTC) - started_at) <= SCHEDULER_STALE_AFTER


def main() -> int:
    try:
        healthy = asyncio.run(asyncio.wait_for(_is_healthy(), timeout=_TOTAL_TIMEOUT_SECONDS))
    except Exception as exc:
        # Fail closed: DB down, timeout, or any unexpected error -> unhealthy.
        print(f"pipeline_healthcheck: {exc}", file=sys.stderr)
        return 1
    return 0 if healthy else 1


if __name__ == "__main__":
    sys.exit(main())
