# Source Diversity Cap — Design Document

**Date**: 2026-03-01
**Status**: Approved

## Problem

High-volume sources (HuggingFace, GitHub) dominate the `/items/latest` feed because they publish far more items than other sources. Even with per-source velocity normalization in `composite_score`, the sheer volume means 90%+ of results can come from a single source.

## Solution

Add a `max_per_source` query parameter to `GET /api/items/latest` that caps how many items from each source appear in results, using SQL window functions.

## API Contract

New query parameter on `GET /api/items/latest`:

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `max_per_source` | `int \| None` | `None` | Max items per source. `None` = no cap (backward compatible) |

- `X-Total-Count` header reflects the filtered total when cap is active.
- Existing filters (`topic`, `source`, `sort`) work unchanged alongside `max_per_source`.
- When `source` filter is set, `max_per_source` has no practical effect (single source).

## SQL Query (with diversity)

```sql
WITH ranked AS (
  SELECT *, ROW_NUMBER() OVER (
    PARTITION BY source
    ORDER BY composite_score DESC NULLS LAST, effective_date DESC
  ) as source_rank
  FROM news_items
  WHERE ... (topic, source filters)
)
SELECT * FROM ranked
WHERE source_rank <= :max_per_source
ORDER BY composite_score DESC NULLS LAST, effective_date DESC
OFFSET :offset LIMIT :limit
```

When `max_per_source` is `None`, the query uses the current simple `SELECT` without CTE.

## Changes Required

### Backend (1 file)

**`src/api/routes/items.py`** — `list_latest_items()`:
- Add parameter: `max_per_source: int | None = Query(None, ge=1, le=100)`
- When `None`: current query, no changes (backward compatible)
- When set: wrap query in CTE with `ROW_NUMBER() OVER (PARTITION BY source)`
- Update count query to use same CTE for accurate `X-Total-Count`

### Frontend (1 file)

Pass `max_per_source` as query param when calling `/api/items/latest`. The value should be based on page size (e.g., `max_per_source=5` for a page of 20).

## What Does NOT Change

- Scoring pipeline (`composite_score`, `relevance_score`, `credibility_score`) — untouched
- Other endpoints (`/items/top`, `/trending`, `/by-date`, `/today`) — untouched
- Database schema — no migrations needed
- `CompositeScorer`, classifiers, validators — untouched

## Scope

- Only `GET /api/items/latest` endpoint affected
- Only when `sort=relevance` (default) — `sort=recent` doesn't need diversity since it's chronological
- Backward compatible: no `max_per_source` param = current behavior
