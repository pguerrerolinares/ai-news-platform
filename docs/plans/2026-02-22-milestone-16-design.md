# M16: API Endpoint Expansion — Design Doc

**Goal:** Add new backend endpoints to fix the briefings 404 problem, expose trending/similar
items, add a sources list, and create chart-ready stats endpoints for future frontend analytics.

**Context:** M15 polished the API contract and bridged M14 backend features to the frontend.
The frontend still can't browse items by date without a `DailyBriefing` record (404), and the
analytics page underutilizes the stats endpoints. M16 prepares the API layer for richer
frontend experiences without touching the frontend itself.

---

## 1. Briefings Fix — Items by Date + Resilient Briefings

**Problem:** `GET /api/briefings/{date}` returns 404 when no `DailyBriefing` record exists,
even though `news_items` for that date are available in the database.

### 1a. New endpoint: GET `/api/items/by-date/{date}`

Query `news_items` where `created_at` falls within the date range (00:00–23:59 UTC).

- **Params:** `topic?`, `source?`, `limit` (1–200, default 50), `offset` (default 0)
- **Sort:** `score DESC NULLS LAST`, then `created_at DESC`
- **Returns:** `list[NewsItemResponse]` with `X-Total-Count` header
- **Auth:** Required (JWT)
- **Rate limit:** 30/min

No dependency on `DailyBriefing` table. Pure `news_items` query.

### 1b. Make GET `/api/briefings/{date}` resilient

Current behavior: 404 if no `DailyBriefing` record exists.

New behavior:
- If `DailyBriefing` record exists → current behavior (return full briefing with metadata)
- If no record exists → synthesize a minimal response:
  - `date` from path param
  - `items` from `news_items` query (same logic as 1a)
  - Metadata fields (`total_items`, `items_extracted`, etc.) set to `null`
  - `generated_at` set to `null`
- Returns 200 as long as there are items for that date
- Returns 404 only if truly no data at all (no briefing AND no items)

**Files:** `src/api/routes/items.py`, `src/api/routes/briefings.py`

---

## 2. Trending Endpoint

**Problem:** Trending items are only accessible via `GET /api/items?trending=true`, mixed
with the generic items endpoint. No dedicated, optimized query.

### GET `/api/items/trending`

- **Query:** `news_items WHERE trending = true`
- **Params:** `topic?`, `source?`, `days?` (1–90, default 7), `limit` (1–100, default 20), `offset`
- **Sort:** `score DESC NULLS LAST`, then `created_at DESC`
- **Date filter:** Only items from the last N `days`
- **Returns:** `list[NewsItemResponse]` with `X-Total-Count`
- **Auth:** Required
- **Rate limit:** 30/min

**Files:** `src/api/routes/items.py`

---

## 3. Similar Items (Embeddings)

**Problem:** The platform has pgvector embeddings for all items (used by RAG chat), but
no API endpoint exposes "similar items" functionality.

### GET `/api/items/{item_id}/similar`

- **Uses:** `item_embeddings` table with pgvector cosine distance (`<=>` operator)
- **Flow:** Find embedding for `item_id` → query nearest neighbors → return items
- **Params:** `limit` (1–20, default 5)
- **Excludes:** The source item itself
- **Returns:** `list[NewsItemResponse]` ordered by similarity (closest first)
- **Errors:** 404 if item not found or no embedding exists for it
- **Auth:** Required
- **Rate limit:** 20/min (vector queries are heavier)

**Implementation notes:**
- Join `item_embeddings` with `news_items` to get full item data
- Use the default embedding model (filter by `model` column)
- pgvector index should already exist for efficient KNN queries

**Files:** `src/api/routes/items.py`

---

## 4. Sources Endpoint

**Problem:** `/api/topics` exists but there's no equivalent for sources. Frontend needs a
source list for filter dropdowns and future source-based views.

### GET `/api/sources`

- **Query:** `SELECT DISTINCT source, COUNT(*) FROM news_items GROUP BY source`
- **Returns:** `{sources: [{name: str, count: int}, ...]}`
- **Sort:** By count DESC
- **Auth:** Not required (same as `/api/topics`)
- **Rate limit:** 30/min

**Schema:**
```python
class SourceInfo(BaseModel):
    name: str
    count: int

class SourcesResponse(BaseModel):
    sources: list[SourceInfo]
```

**Files:** `src/api/routes/items.py` or new `src/api/routes/sources.py`, `src/api/schemas.py`

---

## 5. Chart-Ready Stats Endpoints

**Problem:** The analytics page only uses `GET /api/stats/by-date`. Richer chart data
(topic/source breakdowns over time, score distributions, trending timelines) requires
new endpoints.

### 5a. GET `/api/stats/by-topic-date`

- **Params:** `days` (1–365, default 30)
- **Returns:** `[{date: "2026-02-22", topic: "modelos", count: 12}, ...]`
- **Sort:** By date ASC, then topic ASC
- **Use case:** Stacked area/bar chart — topic distribution over time

### 5b. GET `/api/stats/by-source-date`

- **Params:** `days` (1–365, default 30)
- **Returns:** `[{date: "2026-02-22", source: "hackernews", count: 45}, ...]`
- **Sort:** By date ASC, then source ASC
- **Use case:** Stacked area/bar chart — source activity over time

### 5c. GET `/api/stats/trending-timeline`

- **Params:** `days` (1–365, default 30)
- **Returns:** `[{date: "2026-02-22", count: 8}, ...]`
- **Sort:** By date ASC
- **Use case:** Sparkline/area chart — trending items over time

### 5d. GET `/api/stats/score-distribution`

- **Params:** `days?` (1–365, default 30), `source?`, `topic?`
- **Returns:** `[{range: "0-10", min: 0, max: 10, count: 45}, ...]`
- **Buckets:** 0–10, 11–50, 51–100, 101–250, 251–500, 501+
- **Use case:** Histogram — score distribution

### 5e. GET `/api/items/top`

- **Params:** `days` (1–90, default 7), `limit` (1–50, default 10), `topic?`, `source?`
- **Returns:** `list[NewsItemResponse]`
- **Sort:** `score DESC NULLS LAST`
- **Use case:** Leaderboard — top items by score

All stats endpoints: Auth required, 30/min rate limit.

**Files:** `src/api/routes/stats.py`, `src/api/routes/items.py`, `src/api/schemas.py`

---

## New Schemas

```python
class SourceInfo(BaseModel):
    name: str
    count: int

class SourcesResponse(BaseModel):
    sources: list[SourceInfo]

class StatsGroupDateResponse(BaseModel):
    date: date
    group: str
    count: int

class ScoreDistributionResponse(BaseModel):
    range: str
    min: int
    max: int
    count: int
```

---

## Scope Summary

| # | Endpoint | Type | Risk |
|---|----------|------|------|
| 1a | GET `/api/items/by-date/{date}` | New | Low |
| 1b | GET `/api/briefings/{date}` resilient | Modify | Medium |
| 2 | GET `/api/items/trending` | New | Low |
| 3 | GET `/api/items/{id}/similar` | New | Medium |
| 4 | GET `/api/sources` | New | Low |
| 5a | GET `/api/stats/by-topic-date` | New | Low |
| 5b | GET `/api/stats/by-source-date` | New | Low |
| 5c | GET `/api/stats/trending-timeline` | New | Low |
| 5d | GET `/api/stats/score-distribution` | New | Low |
| 5e | GET `/api/items/top` | New | Low |
| **Total** | **10 endpoints** (9 new + 1 modified) | | |

## Out of Scope (Future)

- Frontend chart implementation (see `docs/plans/ideas-backlog.md`)
- Chat with inline charts
- Frontend pages consuming new endpoints
- Visual redesign

---

*Design approved: 22 de febrero de 2026*
