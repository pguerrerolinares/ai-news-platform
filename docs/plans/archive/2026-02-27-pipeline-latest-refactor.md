# Pipeline + Latest Endpoint Refactor — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix sort order bugs, briefing stat inflation, extraction waste, date inconsistencies, and add a date-unbounded `/api/items/latest` endpoint.

**Architecture:** Targeted fixes across 5 backend files + 1 frontend file. Each task is independent after Task 1. TDD throughout — write the failing test, implement, verify, commit.

**Tech Stack:** FastAPI, SQLAlchemy async, APScheduler, React + TanStack Query

---

### Task 1: Fix sort orders in items.py

**Files:**
- Modify: `src/api/routes/items.py:216` (today endpoint sort)
- Modify: `src/api/routes/items.py:253` (top endpoint sort)
- Create: `tests/unit/test_items_api.py`

**Step 1: Write failing tests for sort order**

Create `tests/unit/test_items_api.py` with test infrastructure matching `test_stats_api.py` pattern:

```python
"""Unit tests for items API endpoints — sort order verification."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from src.api.app import app
from src.api.auth import require_auth
from src.core.database import get_session


def _make_mock_session():
    mock_result = MagicMock()
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = []
    mock_result.scalars.return_value = mock_scalars
    mock_result.scalar_one.return_value = 0
    mock_result.scalar_one_or_none.return_value = None
    mock_result.all.return_value = []

    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(return_value=mock_result)
    return mock_session


async def _mock_get_session():
    yield _make_mock_session()


@pytest.fixture(autouse=True)
def _override_dependencies():
    app.dependency_overrides[require_auth] = lambda: "test-user"
    app.dependency_overrides[get_session] = _mock_get_session
    yield
    app.dependency_overrides.pop(require_auth, None)
    app.dependency_overrides.pop(get_session, None)


@pytest.fixture()
async def api_client() -> AsyncClient:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac  # type: ignore[misc]


class TestTodayEndpoint:
    async def test_today_returns_200(self, api_client: AsyncClient):
        resp = await api_client.get("/api/items/today")
        assert resp.status_code == 200

    async def test_today_accepts_topic_filter(self, api_client: AsyncClient):
        resp = await api_client.get("/api/items/today", params={"topic": "modelos"})
        assert resp.status_code == 200


class TestTopEndpoint:
    async def test_top_returns_200(self, api_client: AsyncClient):
        resp = await api_client.get("/api/items/top")
        assert resp.status_code == 200

    async def test_top_accepts_filters(self, api_client: AsyncClient):
        resp = await api_client.get(
            "/api/items/top", params={"days": 7, "source": "hackernews"}
        )
        assert resp.status_code == 200
```

**Step 2: Run tests to verify they pass (baseline)**

Run: `pytest tests/unit/test_items_api.py -v`
Expected: PASS (these verify endpoints work, not sort order directly)

**Step 3: Fix the sort orders**

In `src/api/routes/items.py`, line 216 — change `/today` sort:

```python
# BEFORE:
query = query.order_by(NewsItem.score.desc().nulls_last()).offset(offset).limit(limit)

# AFTER:
query = query.order_by(NewsItem.published_at.desc().nulls_last()).offset(offset).limit(limit)
```

In `src/api/routes/items.py`, line 253 — change `/top` sort:

```python
# BEFORE:
query = query.order_by(NewsItem.published_at.desc()).offset(offset).limit(limit)

# AFTER:
query = query.order_by(NewsItem.score.desc().nulls_last()).offset(offset).limit(limit)
```

**Step 4: Run tests to verify they still pass**

Run: `pytest tests/unit/test_items_api.py tests/unit/test_stats_api.py -v`
Expected: All PASS

**Step 5: Commit**

```bash
git add src/api/routes/items.py tests/unit/test_items_api.py
git commit -m "fix: swap sort orders in /today and /top endpoints

/today now sorts by published_at desc (chronological, was score).
/top now sorts by score desc (was published_at).
[Track A]"
```

---

### Task 2: Fix DailyBriefing accumulation in pipeline.py

**Files:**
- Modify: `src/pipeline/pipeline.py:194-201` (_save_briefing update block)
- Modify: `tests/unit/test_pipeline.py` (TestSaveBriefing class)

**Step 1: Write failing test for replace-not-accumulate**

Add to `tests/unit/test_pipeline.py` in the `TestSaveBriefing` class:

```python
@pytest.mark.asyncio
async def test_save_briefing_replaces_extraction_stats_on_existing(self):
    """When a briefing already exists, extraction stats are replaced, not accumulated."""
    from unittest.mock import MagicMock
    from src.pipeline.pipeline import _save_briefing

    # Simulate existing briefing with prior stats
    existing_briefing = MagicMock()
    existing_briefing.total_items = 50
    existing_briefing.items_extracted = 100  # old extraction count
    existing_briefing.items_after_dedup = 80
    existing_briefing.items_filtered = 50
    existing_briefing.trending_count = 5
    existing_briefing.duration_seconds = 30.0

    mock_select_result = MagicMock()
    mock_select_result.scalar_one_or_none.return_value = existing_briefing

    session = AsyncMock()
    session.execute = AsyncMock(return_value=mock_select_result)
    session.commit = AsyncMock()

    await _save_briefing(
        session,
        items_extracted=20,
        items_after_dedup=15,
        items_stored=5,
        sources_used=["hackernews"],
        duration_seconds=10.0,
        trending_count=2,
    )

    # total_items (= items_stored) should ACCUMULATE: 50 + 5 = 55
    assert existing_briefing.total_items == 55
    # Extraction stats should be REPLACED, not accumulated
    assert existing_briefing.items_extracted == 20
    assert existing_briefing.items_after_dedup == 15
    assert existing_briefing.items_filtered == 5
    assert existing_briefing.trending_count == 2
    assert existing_briefing.duration_seconds == 10.0
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_pipeline.py::TestSaveBriefing::test_save_briefing_replaces_extraction_stats_on_existing -v`
Expected: FAIL — current code accumulates so `items_extracted` would be 120, not 20

**Step 3: Fix _save_briefing**

In `src/pipeline/pipeline.py`, replace lines 194-202 (the `if briefing:` block):

```python
    if briefing:
        # Accumulate only items_stored (actual new DB inserts)
        briefing.total_items = (briefing.total_items or 0) + items_stored
        # Replace per-run stats (these reflect the latest run, not cumulative)
        briefing.items_extracted = items_extracted
        briefing.items_after_dedup = items_after_dedup
        briefing.items_filtered = items_stored
        briefing.trending_count = trending_count
        briefing.duration_seconds = duration_seconds
        briefing.sources_used = {"sources": sources_used}
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_pipeline.py::TestSaveBriefing -v`
Expected: All PASS

**Step 5: Commit**

```bash
git add src/pipeline/pipeline.py tests/unit/test_pipeline.py
git commit -m "fix: replace extraction stats in daily briefing instead of accumulating

Only items_stored (total_items) accumulates across pipeline runs.
items_extracted, items_after_dedup, trending_count, and duration_seconds
are replaced with the latest run's values to avoid 96x inflation.
[Track A]"
```

---

### Task 3: Per-tier extraction windows

**Files:**
- Modify: `src/pipeline/pipeline.py:86-98,274` (add since_hours param)
- Modify: `src/pipeline/scheduler.py:26-53,69-93` (pass since_hours per tier)
- Modify: `tests/unit/test_scheduler.py` (verify since_hours passed)
- Modify: `tests/unit/test_pipeline.py` (verify since_hours override)

**Step 1: Write failing test for pipeline since_hours param**

Add to `tests/unit/test_pipeline.py`:

```python
class TestPipelineSinceHoursOverride:
    """Verify run_pipeline passes since_hours to extractors."""

    @pytest.mark.asyncio
    async def test_extract_all_uses_custom_since_hours(self):
        """_extract_all should use the provided since_hours, not settings default."""
        mock_extractor = AsyncMock()
        mock_extractor.source_name = "hackernews"
        mock_extractor.extract = AsyncMock(return_value=[])

        settings = _mock_settings(extraction_since_hours=24)
        with patch("src.pipeline.pipeline.get_settings", return_value=settings):
            await _extract_all([mock_extractor], since_hours=1)

        mock_extractor.extract.assert_called_once_with(since_hours=1)
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_pipeline.py::TestPipelineSinceHoursOverride -v`
Expected: FAIL — `_extract_all` doesn't accept `since_hours` param yet

**Step 3: Implement since_hours in pipeline**

In `src/pipeline/pipeline.py`, modify `_extract_all` signature and body:

```python
async def _extract_all(
    extractors: list[BaseExtractor],
    alerts: AlertService | None = None,
    since_hours: int | None = None,
) -> list[ExtractedItem]:
    """Run all extractors concurrently and collect results."""
    settings = get_settings()
    if alerts is None:
        alerts = AlertService()
    effective_since = since_hours if since_hours is not None else settings.extraction_since_hours

    async def _run_one(extractor: BaseExtractor) -> list[ExtractedItem]:
        try:
            items = await extractor.extract(since_hours=effective_since)
            # ... rest unchanged
```

Modify `run_pipeline` signature to accept and pass `since_hours`:

```python
async def run_pipeline(
    session: AsyncSession,
    sources: list[str] | None = None,
    since_hours: int | None = None,
) -> bool:
    # ...
    all_items = await _extract_all(extractors, alerts=alerts, since_hours=since_hours)
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_pipeline.py::TestPipelineSinceHoursOverride -v`
Expected: PASS

**Step 5: Write failing test for scheduler passing since_hours**

Add to `tests/unit/test_scheduler.py`:

```python
class TestSchedulerSinceHours:
    """Verify scheduler passes per-tier since_hours to run_pipeline."""

    @pytest.mark.asyncio
    async def test_tier1_passes_since_hours(self):
        from src.pipeline.scheduler import run_scheduled_pipeline

        mock_session = AsyncMock()
        mock_session_cm = AsyncMock()
        mock_session_cm.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_cm.__aexit__ = AsyncMock(return_value=False)

        with (
            patch("src.pipeline.scheduler.get_async_session", return_value=mock_session_cm),
            patch("src.pipeline.scheduler.run_pipeline", new_callable=AsyncMock) as mock_run,
        ):
            await run_scheduled_pipeline(sources=["hackernews", "reddit"], since_hours=1)

        mock_run.assert_called_once_with(
            mock_session, sources=["hackernews", "reddit"], since_hours=1
        )
```

**Step 6: Run test to verify it fails**

Run: `pytest tests/unit/test_scheduler.py::TestSchedulerSinceHours -v`
Expected: FAIL — `run_scheduled_pipeline` doesn't accept `since_hours`

**Step 7: Implement since_hours in scheduler**

In `src/pipeline/scheduler.py`, modify `run_scheduled_pipeline`:

```python
async def run_scheduled_pipeline(sources: list[str], since_hours: int | None = None) -> None:
    # ... circuit breaker logic unchanged ...
    try:
        async with get_async_session() as session:
            result = await run_pipeline(session, sources=active_sources, since_hours=since_hours)
```

Update job registrations in `create_scheduler`:

```python
    # Tier 1: HackerNews + Reddit (every 15 min, extract last 1h)
    scheduler.add_job(
        run_scheduled_pipeline,
        IntervalTrigger(minutes=settings.hn_poll_interval_minutes),
        id="tier1_hn_reddit",
        kwargs={"sources": ["hackernews", "reddit"], "since_hours": 1},
        replace_existing=True,
    )

    # Tier 2: RSS + GitHub + HuggingFace (every 60 min, extract last 3h)
    scheduler.add_job(
        run_scheduled_pipeline,
        IntervalTrigger(minutes=settings.rss_poll_interval_minutes),
        id="tier2_rss_gh_hf",
        kwargs={"sources": ["rss", "github", "huggingface"], "since_hours": 3},
        replace_existing=True,
    )

    # Tier 3: arXiv (daily, extract last 24h)
    scheduler.add_job(
        run_scheduled_pipeline,
        CronTrigger(hour=settings.arxiv_cron_hour, minute=settings.arxiv_cron_minute),
        id="tier3_arxiv",
        kwargs={"sources": ["arxiv"], "since_hours": 24},
        replace_existing=True,
    )
```

**Step 8: Run all scheduler and pipeline tests**

Run: `pytest tests/unit/test_scheduler.py tests/unit/test_pipeline.py -v`
Expected: All PASS

Note: The existing test `test_creates_session_and_runs_pipeline` will need updating — its assertion checks `mock_run.assert_called_once_with(mock_session, sources=["hackernews", "reddit"])` which won't match now that `since_hours` is also passed. Update the assertion to:

```python
mock_run.assert_called_once_with(mock_session, sources=["hackernews", "reddit"], since_hours=None)
```

**Step 9: Commit**

```bash
git add src/pipeline/pipeline.py src/pipeline/scheduler.py tests/unit/test_scheduler.py tests/unit/test_pipeline.py
git commit -m "feat: per-tier extraction windows to reduce redundant API calls

Tier 1 (HN+Reddit, 15min): extracts last 1h (was 24h)
Tier 2 (RSS+GH+HF, 60min): extracts last 3h (was 24h)
Tier 3 (arXiv, daily): stays at 24h
Dedup on content_hash still catches any overlap.
[Track A]"
```

---

### Task 4: Standardize dates with COALESCE

**Files:**
- Modify: `src/api/routes/items.py` (add `_effective_date`, update all endpoints)
- Modify: `src/api/routes/stats.py` (update date groupings)
- Modify: `src/api/routes/briefings.py` (update date filter)
- Modify: `tests/unit/test_items_api.py` (add test for /latest endpoint, next task)
- Modify: `tests/unit/test_stats_api.py` (ensure tests still pass)

**Step 1: Add `_effective_date` expression and update items.py endpoints**

At the top of `src/api/routes/items.py`, after the imports, add:

```python
from sqlalchemy import func

# Effective date: prefer published_at, fall back to created_at
_effective_date = func.coalesce(NewsItem.published_at, NewsItem.created_at)
```

Note: `func` is already imported — just add the expression.

Then update each endpoint to use `_effective_date`:

**`list_items` (line 46-68):** Replace `published_at` references:

```python
    if date_from:
        query = query.where(func.date(_effective_date) >= date_from)
    if date_to:
        query = query.where(func.date(_effective_date) <= date_to)
    # ...
    query = query.order_by(_effective_date.desc()).offset(offset).limit(limit)
```

**`list_items_by_date` (line 110-143):** Replace `created_at` references:

```python
    query = select(NewsItem).where(
        (_effective_date >= day_start) & (_effective_date < day_end)
    )
    # ...count_query uses same filter...
    query = (
        query.order_by(NewsItem.score.desc().nulls_last(), _effective_date.desc())
        .offset(offset)
        .limit(limit)
    )
```

**`list_trending_items` (line 152-184):** Replace `created_at`:

```python
    query = select(NewsItem).where(
        NewsItem.trending.is_(True) & (_effective_date >= since)
    )
    # ...
    query = (
        query.order_by(NewsItem.score.desc().nulls_last(), _effective_date.desc())
        .offset(offset)
        .limit(limit)
    )
```

**`list_today_items` (line 193-219):** Replace `created_at`:

```python
    query = select(NewsItem).where(
        (_effective_date >= today_start) & (_effective_date < today_end)
    )
    # ...count uses same filter...
    query = query.order_by(_effective_date.desc().nulls_last()).offset(offset).limit(limit)
```

**`list_top_items` (line 228-256):** Replace `created_at`:

```python
    query = select(NewsItem).where(
        (_effective_date >= since) & NewsItem.score.isnot(None)
    )
    # ...
    query = query.order_by(NewsItem.score.desc().nulls_last()).offset(offset).limit(limit)
```

**Step 2: Update stats.py endpoints**

In `src/api/routes/stats.py`, add at the top after imports:

```python
_effective_date = func.coalesce(NewsItem.published_at, NewsItem.created_at)
```

Then replace all `NewsItem.created_at` references with `_effective_date` and `func.date(NewsItem.created_at)` with `func.date(_effective_date)` in:
- `stats_summary` (line 42)
- `stats_by_date` (line 124)
- `stats_by_topic_date` (line 153-154)
- `stats_by_source_date` (line 187-188)
- `stats_trending_timeline` (line 220-225)
- `stats_score_distribution` (line 263)

**Step 3: Update briefings.py**

In `src/api/routes/briefings.py`, add at the top:

```python
_effective_date = func.coalesce(NewsItem.published_at, NewsItem.created_at)
```

Replace `NewsItem.created_at` with `_effective_date` in `get_briefing` (line 47):

```python
    date_filter = (_effective_date >= day_start) & (_effective_date < day_end)
```

**Step 4: Run all existing tests**

Run: `pytest tests/unit/test_items_api.py tests/unit/test_stats_api.py -v`
Expected: All PASS

**Step 5: Commit**

```bash
git add src/api/routes/items.py src/api/routes/stats.py src/api/routes/briefings.py
git commit -m "refactor: standardize date filtering with COALESCE(published_at, created_at)

All date-filtered endpoints now use _effective_date which prefers
published_at but falls back to created_at for items without it.
Eliminates inconsistency between endpoints using different date fields.
[Track A]"
```

---

### Task 5: Add `/api/items/latest` endpoint

**Files:**
- Modify: `src/api/routes/items.py` (new endpoint, BEFORE the `/{item_id}` catch-all)
- Modify: `tests/unit/test_items_api.py` (new test class)

**Step 1: Write failing test**

Add to `tests/unit/test_items_api.py`:

```python
class TestLatestEndpoint:
    async def test_latest_returns_200(self, api_client: AsyncClient):
        resp = await api_client.get("/api/items/latest")
        assert resp.status_code == 200

    async def test_latest_returns_list(self, api_client: AsyncClient):
        resp = await api_client.get("/api/items/latest")
        assert isinstance(resp.json(), list)

    async def test_latest_accepts_filters(self, api_client: AsyncClient):
        resp = await api_client.get(
            "/api/items/latest",
            params={"topic": "modelos", "source": "hackernews", "limit": "10"},
        )
        assert resp.status_code == 200

    async def test_latest_has_total_count_header(self, api_client: AsyncClient):
        resp = await api_client.get("/api/items/latest")
        assert "X-Total-Count" in resp.headers
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_items_api.py::TestLatestEndpoint -v`
Expected: FAIL — 404 or 405 because endpoint doesn't exist

**Step 3: Implement the endpoint**

Add to `src/api/routes/items.py`, BEFORE the `/{item_id}/similar` route (which is the catch-all):

```python
@router.get(
    "/latest",
    response_model=list[NewsItemResponse],
    responses={401: {"model": ErrorWrapper}},
)
@limiter.limit("30/minute")
async def list_latest_items(
    request: Request,
    response: Response,
    topic: str | None = Query(None, description="Filter by topic"),
    source: str | None = Query(None, description="Filter by source"),
    limit: int = Query(50, ge=1, le=200, description="Max items to return"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    session: AsyncSession = Depends(get_session),
    _user: UserClaims = Depends(require_auth),
) -> list[NewsItemResponse]:
    """Latest items across all dates, sorted by effective date descending."""
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

    query = query.order_by(_effective_date.desc()).offset(offset).limit(limit)

    result = await session.execute(query)
    items = result.scalars().all()
    return [NewsItemResponse.model_validate(item) for item in items]
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/unit/test_items_api.py -v`
Expected: All PASS

**Step 5: Commit**

```bash
git add src/api/routes/items.py tests/unit/test_items_api.py
git commit -m "feat: add /api/items/latest endpoint for date-unbounded feed

Returns the most recent items regardless of date, sorted by
COALESCE(published_at, created_at). Supports topic, source,
limit, offset filters. Dashboard will use this instead of /today.
[Track A]"
```

---

### Task 6: Update frontend Dashboard to use /latest

**Files:**
- Modify: `frontend/src/pages/Dashboard.tsx:37,44`

**Step 1: Update the API call and query key**

In `frontend/src/pages/Dashboard.tsx`, line 37:

```typescript
// BEFORE:
queryKey: ['items-today', { topic: topicParam }],

// AFTER:
queryKey: ['items-latest', { topic: topicParam }],
```

Line 44:

```typescript
// BEFORE:
return apiGet<NewsItem[]>('/api/items/today', params, signal)

// AFTER:
return apiGet<NewsItem[]>('/api/items/latest', params, signal)
```

**Step 2: Verify frontend builds**

Run: `cd frontend && npm run build`
Expected: Build succeeds with no errors

**Step 3: Commit**

```bash
git add frontend/src/pages/Dashboard.tsx
git commit -m "feat: switch Dashboard from /today to /latest endpoint

Dashboard 'Latest' feed now uses the date-unbounded /api/items/latest
endpoint instead of /api/items/today, avoiding empty states around
UTC midnight.
[Track A]"
```

---

### Task 7: Run full test suite and verify

**Step 1: Run all backend tests**

Run: `pytest tests/unit/ -v --timeout=30`
Expected: All PASS

**Step 2: Run linting**

Run: `ruff check . && ruff format --check .`
Expected: No errors

**Step 3: Run type checking**

Run: `pyright .`
Expected: No new errors

**Step 4: Build frontend**

Run: `cd frontend && npm run build`
Expected: Build succeeds

---

### Task 8: Update AGENTS.md if needed

**Files:**
- Modify: `AGENTS.md` (if endpoint list or pipeline description changed)

**Step 1: Check if AGENTS.md documents the items endpoints or pipeline schedule**

If it does, update to reflect:
- New `/api/items/latest` endpoint
- Per-tier extraction windows
- Fixed sort orders

**Step 2: Commit**

```bash
git add AGENTS.md
git commit -m "docs: update AGENTS.md with /latest endpoint and per-tier extraction

[Track A]"
```
