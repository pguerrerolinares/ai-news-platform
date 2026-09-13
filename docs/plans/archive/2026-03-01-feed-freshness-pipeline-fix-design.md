# Feed Freshness & Pipeline Fix Design

**Date**: 2026-03-01
**Status**: Approved

## Problem

The `/latest` endpoint returns items from months ago (Jan 2025, Sep 2025, etc.) with
composite_scores ~0.74, alongside fresh items. The `/top` endpoint is dominated by
HuggingFace models due to sorting by raw `score` (downloads in millions). The pipeline
is barely producing new items because of multiple configuration and infrastructure issues.

## Root Causes

### Endpoints
1. **`/latest`**: No time filter — queries all items by `composite_score DESC`
2. **`/top`**: Sorts by raw `score` (not normalized across sources)
3. **composite_score stale**: Calculated once at ingest, never recalculated

### Pipeline
4. **`docker-entrypoint.sh`**: Uses `exec uvicorn` without `$@`, ignoring CMD override —
   `pipeline-scheduler.sh` never executes
5. **Two schedulers**: Both `api` and `pipeline-cron` containers start APScheduler
6. **HN `since_hours=1`**: With `min_points=10`, stories rarely have 10 pts in 1 hour
7. **Reddit missing**: Not in `ENABLED_SOURCES` env var
8. **arXiv**: Cron at 01:30 UTC, hasn't fired yet since container restart

### Data
- 5,963 total items; 5,905 backfilled on 2026-02-28
- Only 17 items in last 48h, 38 in last 7d
- 63% of items are >90 days old (from backfill)

## Solution

### A. Pipeline Fixes

**A1. `docker-entrypoint.sh`** — Pass `$@` so CMD overrides work:
```bash
if [ $# -gt 0 ]; then exec "$@"; fi
exec uvicorn ...
```

**A2. Single scheduler** — Set `SCHEDULER_ENABLED=false` on `api` container,
`SCHEDULER_ENABLED=true` on `pipeline-cron`. Both still serve HTTP for healthchecks.

**A3. HN `since_hours`** — Change tier1 from `since_hours=1` to `since_hours=6`.
Stories accumulate 10+ points in 6 hours reliably.

**A4. Reddit** — Add `reddit` to `ENABLED_SOURCES` env var in Coolify.
Requires `REDDIT_CLIENT_ID` and `REDDIT_CLIENT_SECRET`.

### B. Endpoint Fixes

**B1. `/latest` — Time filter + live rescore**
- FeedBuilder filters `WHERE effective_date >= NOW() - 48h`
- Progressive expansion: 48h -> 72h -> 168h if <5 items
- Live rescore via `CompositeScorer.score_newsitem()` with current `now`
- Same filter for `sort=recent` path

**B2. `/top` — Sort by composite_score**
- Change `ORDER BY score DESC` to `ORDER BY composite_score DESC`

### C. CompositeScorer

**C1. New `score_newsitem()` method**
- Accepts `NewsItem` (persisted model) instead of `ClassifiedItem`
- Recalculates all components with current time

### D. Config

```python
feed_latest_max_age_hours: float = 48.0
feed_latest_min_items: int = 5
```

## Files to Modify

| File | Change |
|------|--------|
| `docker-entrypoint.sh` | Pass `$@` for CMD override |
| `docker-compose.coolify.yml` | `SCHEDULER_ENABLED=false` for api |
| `src/pipeline/scheduler.py` | tier1 `since_hours=1` -> `6` |
| `src/feed/feed_builder.py` | Time filter + expansion + live rescore |
| `src/pipeline/composite_scorer.py` | `score_newsitem()` method |
| `src/api/routes/items.py` | Time filter in `/latest`, sort fix in `/top` |
| `src/core/config.py` | 2 new settings |

## Testing

- Unit tests for `score_newsitem()` with various ages
- Unit tests for FeedBuilder time filter + expansion
- Unit test for `/top` sort order
- Manual verification on production after deploy
