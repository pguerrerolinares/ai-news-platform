# Source Diversity Cap — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add `max_per_source` query param to `GET /api/items/latest` that caps items per source using SQL window functions, preventing high-volume sources from dominating the feed.

**Architecture:** A subquery with `ROW_NUMBER() OVER (PARTITION BY source)` ranks items within each source. A filter keeps only the top N per source. The main query selects matching NewsItem rows, orders by composite_score, and paginates normally. When `max_per_source` is `None`, the current query runs unchanged.

**Tech Stack:** SQLAlchemy async (func.row_number, over, subquery), FastAPI Query params, React useInfiniteQuery

---

### Task 1: Backend — Write failing tests for max_per_source

**Files:**
- Modify: `tests/unit/test_items_api.py:78-97` (TestLatestEndpoint class)

**Step 1: Write failing tests**

Add these tests to the `TestLatestEndpoint` class in `tests/unit/test_items_api.py` (after line 97):

```python
    async def test_latest_accepts_max_per_source(self, api_client: AsyncClient):
        resp = await api_client.get(
            "/api/items/latest",
            params={"max_per_source": "5"},
        )
        assert resp.status_code == 200

    async def test_latest_rejects_invalid_max_per_source(self, api_client: AsyncClient):
        resp = await api_client.get(
            "/api/items/latest",
            params={"max_per_source": "0"},
        )
        assert resp.status_code == 422

    async def test_latest_without_max_per_source_still_works(self, api_client: AsyncClient):
        resp = await api_client.get("/api/items/latest")
        assert resp.status_code == 200
        assert "x-total-count" in resp.headers
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/test_items_api.py::TestLatestEndpoint -v`
Expected: `test_latest_accepts_max_per_source` FAILS (422 because param not recognized), others PASS.

---

### Task 2: Backend — Implement max_per_source in list_latest_items

**Files:**
- Modify: `src/api/routes/items.py:256-294` (list_latest_items function)

**Step 1: Add import**

No new imports needed — `func` and `select` are already imported (line 8). SQLAlchemy's `func.row_number().over()` uses existing imports.

**Step 2: Add max_per_source parameter and implement logic**

Replace the `list_latest_items` function (lines 262-294) with:

```python
async def list_latest_items(
    request: Request,
    response: Response,
    topic: str | None = Query(None, description="Filter by topic"),
    source: str | None = Query(None, description="Filter by source"),
    sort: str = Query("relevance", description="Sort: relevance or recent"),
    max_per_source: int | None = Query(
        None, ge=1, le=100, description="Max items per source (diversity cap)"
    ),
    limit: int = Query(50, ge=1, le=200, description="Max items to return"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    session: AsyncSession = Depends(get_session),
    _user: UserClaims = Depends(require_auth),
) -> list[NewsItemResponse]:
    """Latest items, sorted by relevance (default) or recency."""
    use_diversity = max_per_source is not None and sort != "recent"

    if use_diversity:
        # Subquery: rank items within each source by composite_score
        source_rank = func.row_number().over(
            partition_by=NewsItem.source,
            order_by=[
                NewsItem.composite_score.desc().nulls_last(),
                effective_date.desc(),
            ],
        ).label("source_rank")

        ranked = select(NewsItem.id, source_rank)
        if topic:
            ranked = ranked.where(NewsItem.topic == topic)
        if source:
            ranked = ranked.where(NewsItem.source == source)
        ranked_subq = ranked.subquery()

        # Filtered IDs: top N per source
        filtered_ids = select(ranked_subq.c.id).where(
            ranked_subq.c.source_rank <= max_per_source
        )

        # Count
        count_q = select(func.count()).select_from(filtered_ids.subquery())
        total = (await session.execute(count_q)).scalar_one()
        set_total_count_header(response, total)

        # Main query
        query = (
            select(NewsItem)
            .where(NewsItem.id.in_(filtered_ids))
            .order_by(
                NewsItem.composite_score.desc().nulls_last(),
                effective_date.desc(),
            )
            .offset(offset)
            .limit(limit)
        )
    else:
        # Original behavior (no diversity cap)
        query = select(NewsItem)
        if topic:
            query = query.where(NewsItem.topic == topic)
        if source:
            query = query.where(NewsItem.source == source)

        count_query = select(func.count()).select_from(
            query.with_only_columns(NewsItem.id).subquery()
        )
        total = (await session.execute(count_query)).scalar_one()
        set_total_count_header(response, total)

        if sort == "recent":
            query = query.order_by(effective_date.desc())
        else:
            query = query.order_by(
                NewsItem.composite_score.desc().nulls_last(),
                effective_date.desc(),
            )
        query = query.offset(offset).limit(limit)

    result = await session.execute(query)
    items = result.scalars().all()
    return [NewsItemResponse.model_validate(item) for item in items]
```

**Step 3: Run tests to verify they pass**

Run: `pytest tests/unit/test_items_api.py::TestLatestEndpoint -v`
Expected: ALL PASS

**Step 4: Run full test suite and linting**

Run: `ruff check src/api/routes/items.py && ruff format --check src/api/routes/items.py && pytest tests/unit/test_items_api.py -v`
Expected: No lint errors, all tests pass.

**Step 5: Commit**

```bash
git add src/api/routes/items.py tests/unit/test_items_api.py
git commit -m "feat: add max_per_source diversity cap to /items/latest endpoint"
```

---

### Task 3: Frontend — Pass max_per_source to API call

**Files:**
- Modify: `frontend/src/pages/Dashboard.tsx:31-37`

**Step 1: Add max_per_source param**

In `Dashboard.tsx`, update the params object (around line 31-36). `PAGE_SIZE` is 20 (line 11), so a good default cap is 5 items per source (25% of page):

```typescript
      const params: Record<string, string> = {
        limit: String(PAGE_SIZE),
        offset: String(pageParam),
        sort: 'relevance',
        max_per_source: '5',
      }
```

**Step 2: Verify frontend builds**

Run: `cd frontend && npm run build`
Expected: Build succeeds with no errors.

**Step 3: Commit**

```bash
git add frontend/src/pages/Dashboard.tsx
git commit -m "feat: pass max_per_source=5 to /items/latest for source diversity"
```
