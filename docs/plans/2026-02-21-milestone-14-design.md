# M14: DB + Backend API Polish — Design Doc

**Goal:** Optimize the database layer, fix all API pagination gaps, add aggregate stats
endpoints, standardize errors, add refresh tokens, and improve pipeline robustness —
preparing the backend for a future frontend redesign.

**Context:** With 6,374 real news items in the database (M13 backfill), several API
endpoints reveal pagination gaps, missing indexes, and incomplete features that were
invisible with 20 mock items. This milestone fixes everything backend before the
frontend redesign (M15).

---

## 1. Database Indexes

**Problem:** Several critical queries do full table scans because indexes are missing.

**Changes (single Alembic migration):**

| Index | Column(s) | Reason |
|-------|-----------|--------|
| `idx_news_items_score` | `score DESC NULLS LAST` | `/api/items/today` and briefings ORDER BY score |
| `idx_news_items_source_date` | `(source, published_at DESC)` | Filter by source + sort by date |
| `idx_news_items_topic_date` | `(topic, published_at DESC)` | Filter by topic + sort by date |
| `idx_news_items_created_at` | `created_at DESC` | Briefing generation filters by created_at date |

**No changes to:** `raw_extractions` table (kept as-is per user decision).

---

## 2. API Pagination Fixes

**Problem:** 3 endpoints cannot paginate beyond their first page of results.

### 2a. `GET /api/search` — Add `offset`

```python
# Before:
async def search_items(q: str, limit: int = 50) -> list[NewsItem]:
# After:
async def search_items(q: str, limit: int = 50, offset: int = 0) -> list[NewsItem]:
```

Add `X-Total-Count` response header with total matching results.

### 2b. `GET /api/items/today` — Add `offset`

```python
# Before:
async def list_today_items(topic: str | None, limit: int = 100):
# After:
async def list_today_items(topic: str | None, limit: int = 100, offset: int = 0):
```

Add `X-Total-Count` response header.

### 2c. `GET /api/briefings/{date}` — Add `limit` and `offset`

Currently returns ALL items for a date unbounded. Add:
- `limit: int = Query(100, ge=1, le=500)`
- `offset: int = Query(0, ge=0)`
- `X-Total-Count` header

### 2d. `GET /api/briefings` — Add `offset`

Currently only has `limit` (max 90). Add `offset` to allow navigating older briefings.

### Response Header Convention

All paginated endpoints return:
- `X-Total-Count: <int>` — total number of matching results (before limit/offset)

This is lightweight, standards-aligned, and gives the frontend everything it needs
to build pagination UI.

---

## 3. Aggregate Stats Endpoints

**Problem:** Analytics page uses a 100-item sample to compute charts — completely
inaccurate with 6,374 items. Need server-side aggregation.

### New routes in `src/api/routes/stats.py`:

| Endpoint | Response | Description |
|----------|----------|-------------|
| `GET /api/stats/summary` | `{total_items, items_today, sources_count, topics_count, trending_today}` | Overview numbers |
| `GET /api/stats/by-source` | `[{source, count}]` | Item count per source |
| `GET /api/stats/by-topic` | `[{topic, count}]` | Item count per topic |
| `GET /api/stats/by-date` | `[{date, count}]` | Items per day, param `days` (default 30, max 365) |

All endpoints:
- Require auth (`Depends(require_auth)`)
- Rate limited: 30/minute
- Use PostgreSQL `GROUP BY` aggregation (efficient, no full scan)

---

## 4. Search Sorting

**Problem:** Search always returns results by relevance (`ts_rank`). Users may want
to sort by date or popularity.

Add `sort_by` parameter to `GET /api/search`:

| Value | Ordering | Description |
|-------|----------|-------------|
| `relevance` (default) | `ts_rank DESC` | Current behavior |
| `date` | `published_at DESC` | Most recent first |
| `score` | `score DESC NULLS LAST` | Most popular first |

Implementation: `sort_by: str = Query("relevance", pattern="^(relevance|date|score)$")`

---

## 5. Error Response Standardization

**Problem:** Errors return different formats: `{"detail": "..."}` (FastAPI default)
vs `{"error": "..."}` (chat SSE).

### Standard error format:

```json
{
  "error": {
    "code": "INVALID_TOKEN",
    "message": "Invalid or expired token"
  }
}
```

### Implementation:

- Custom exception handler for `HTTPException` that wraps responses
- Error codes are UPPER_SNAKE_CASE constants
- Chat SSE errors use same format in the `{"error": {...}}` event

### Error code mapping:

| HTTP Status | Code | Message |
|-------------|------|---------|
| 401 | `INVALID_PASSWORD` | Invalid password |
| 401 | `INVALID_TOKEN` | Invalid or expired token |
| 404 | `BRIEFING_NOT_FOUND` | No briefing found for this date |
| 413 | `BODY_TOO_LARGE` | Request body exceeds 1MB limit |
| 422 | `VALIDATION_ERROR` | (FastAPI validation detail preserved) |
| 429 | `RATE_LIMITED` | Too many requests, try again later |

---

## 6. Refresh Tokens

**Problem:** JWT expires after 24h, forcing re-login. No way to extend session
without re-entering password.

### Design:

- **Access token**: Short-lived (30 minutes instead of 24h)
- **Refresh token**: Long-lived (7 days), stored in HttpOnly cookie or returned in body
- **New endpoint**: `POST /api/auth/refresh`

### Token flow:

```
1. POST /api/auth/token {password} → {access_token, refresh_token, expires_in}
2. GET /api/items (Authorization: Bearer <access_token>)
3. ... 30 min later, access_token expires ...
4. POST /api/auth/refresh {refresh_token} → {access_token, refresh_token, expires_in}
```

### Implementation details:

- Refresh token is a separate JWT with `type: "refresh"` claim
- Access token gets `type: "access"` claim
- `require_auth` validates only access tokens (`type == "access"`)
- Refresh endpoint validates only refresh tokens (`type == "refresh"`)
- Refresh token rotation: each refresh returns a NEW refresh token (old one invalidated)
- Store refresh token hash in memory (dict) for rotation/revocation
  - For this scale (single user), in-memory is fine
  - If scaling needed later, move to Redis

### Config changes:

```python
jwt_access_expire_minutes: int = 30      # was jwt_expire_minutes = 1440
jwt_refresh_expire_days: int = 7         # new
```

---

## 7. Pipeline Robustness

### 7a. Pre-storage validation

Before classification, validate that each extracted item has:
- Non-empty title (required)
- Non-empty URL (required)
- Valid `published_at` date if present

Items failing validation are logged and skipped (not silently dropped).
Add metric: `items_validation_failed_total{reason}`.

### 7b. Embedding failure logging

Current: silently returns 0 on failure.
Fix: Log at ERROR level (not WARNING) with item count that failed.
Add metric: `embedding_failures_total`.

### 7c. Chat SSE timeout

Add 30-second timeout to LLM streaming. If no token received in 30s,
close SSE with error event:

```json
{"error": {"code": "LLM_TIMEOUT", "message": "AI response timed out"}}
```

---

## Scope Summary

| Section | Tasks (est.) | Risk |
|---------|-------------|------|
| 1. DB Indexes | 2 | Track A (low) |
| 2. Pagination Fixes | 5 | Track A (low) |
| 3. Stats Endpoints | 3 | Track A (low) |
| 4. Search Sorting | 2 | Track A (low) |
| 5. Error Standardization | 3 | Track B (medium) |
| 6. Refresh Tokens | 4 | Track B (medium) |
| 7. Pipeline Robustness | 3 | Track A (low) |
| **Total** | **~22 tasks** | |

## Out of Scope

- Frontend changes (M15 with Pencil)
- `raw_extractions` cleanup (kept as-is)
- API versioning (not needed yet, single consumer)
- Redis/external cache (in-memory sufficient at this scale)
- Semantic search endpoint (future milestone, uses pgvector)

---

*Design approved: 21 de febrero de 2026*
