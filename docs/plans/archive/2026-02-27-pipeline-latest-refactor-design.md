# Pipeline + Latest Endpoint Refactor — Design

**Date:** 2026-02-27
**Status:** Approved

## Problem

Two confirmed bugs plus related inconsistencies in the pipeline/API integration:

1. **Sort orders swapped**: `/api/items/today` (the Dashboard "Latest" feed) sorts by
   `score.desc()` instead of chronologically. `/api/items/top` sorts by `published_at.desc()`
   instead of by score.
2. **DailyBriefing stats inflated**: Each 15-min pipeline run re-extracts 24h of data and
   _accumulates_ `items_extracted`/`items_after_dedup` onto the daily record. With ~96
   runs/day, these numbers become ~96x the real value.
3. **Extraction window waste**: Every tier re-extracts 24h regardless of poll frequency.
4. **`created_at` vs `published_at` inconsistency**: Some endpoints filter/sort on
   `created_at`, others on `published_at`, with no clear rationale.
5. **No date-unbounded "latest" endpoint**: The Dashboard calls `/api/items/today` which
   shows nothing around UTC midnight or when few items exist for the current day.

## Design

### Section 1: Fix sort orders (items.py)

| Endpoint | Current sort | Correct sort |
|---|---|---|
| `GET /api/items/today` | `score.desc().nulls_last()` | `published_at.desc().nulls_last()` |
| `GET /api/items/top` | `published_at.desc()` | `score.desc().nulls_last()` |

### Section 2: Fix DailyBriefing accumulation (pipeline.py)

Change `_save_briefing` behavior for existing daily records:

| Field | Current | New |
|---|---|---|
| `items_stored` (= `total_items`) | Accumulate | Accumulate (correct) |
| `items_extracted` | Accumulate | **Replace** with latest run |
| `items_after_dedup` | Accumulate | **Replace** with latest run |
| `items_filtered` | Accumulate | **Replace** with latest run |
| `trending_count` | Accumulate | **Replace** with latest run |
| `duration_seconds` | Accumulate | **Replace** with latest run |
| `sources_used` | Replace | Replace (no change) |

### Section 3: Per-tier extraction windows (scheduler.py + pipeline.py)

Pass `since_hours` from scheduler to `run_pipeline` and through to extractors:

| Tier | Sources | Interval | New `since_hours` | Buffer ratio |
|---|---|---|---|---|
| Tier 1 | HN + Reddit | 15 min | 1h | 4x |
| Tier 2 | RSS + GH + HF | 60 min | 3h | 3x |
| Tier 3 | arXiv | daily | 24h | 1x (unchanged) |

Dedup on `content_hash` catches any overlap from generous buffers.

Changes:
- `run_pipeline(session, sources, since_hours)` — add optional `since_hours` param
- `run_scheduled_pipeline(sources, since_hours)` — pass through from scheduler
- `_extract_all` overrides `settings.extraction_since_hours` when `since_hours` is provided

### Section 4: Standardize dates (items.py + stats.py)

Define a reusable effective date expression:

```python
_effective_date = func.coalesce(NewsItem.published_at, NewsItem.created_at)
```

Use `_effective_date` consistently in all date-filtered and date-sorted endpoints:
- `GET /api/items` — filter and sort
- `GET /api/items/today` — filter and sort
- `GET /api/items/by-date/{date}` — filter and sort
- `GET /api/items/trending` — filter and sort
- `GET /api/items/top` — filter and sort
- `GET /api/stats/*` — all date groupings

### Section 5: New `/api/items/latest` endpoint + frontend update

**New endpoint: `GET /api/items/latest`**
- No date boundary — returns the N most recent items
- Sorted by `_effective_date.desc()`
- Supports: `topic`, `source`, `limit` (default 50), `offset`
- Paginated with `X-Total-Count` header

**Frontend (`Dashboard.tsx`):**
- Change API call from `/api/items/today` to `/api/items/latest`
- Change query key from `items-today` to `items-latest`
- No other frontend changes needed

**Keep `/api/items/today`** — still useful for date-specific views.

## Files Affected

- `src/api/routes/items.py` — Sections 1, 4, 5
- `src/api/routes/stats.py` — Section 4
- `src/pipeline/pipeline.py` — Sections 2, 3
- `src/pipeline/scheduler.py` — Section 3
- `frontend/src/pages/Dashboard.tsx` — Section 5

## Risks

- **Section 4 (COALESCE)**: Items with `published_at=NULL` will now use `created_at` for
  sorting/filtering. This is better than the current inconsistency but could change the
  order of some items in existing views. Low risk — `published_at` is populated for most
  sources.
- **Section 3 (extraction windows)**: If a tier's run fails and the next run uses a short
  window, items from the gap period could be missed. Mitigated by generous buffer ratios
  (3-4x) and the circuit breaker pausing after 3 consecutive failures.

## Testing

- Unit tests for each section (sort order, briefing accumulation, extraction windows)
- Verify `_effective_date` COALESCE works with NULL `published_at`
- Frontend smoke test: Dashboard loads with `/api/items/latest`
