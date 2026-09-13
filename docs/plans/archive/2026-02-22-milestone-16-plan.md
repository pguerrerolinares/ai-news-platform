# M16: API Endpoint Expansion — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add 9 new backend endpoints and make briefings resilient, preparing the API layer for richer frontend analytics without touching the frontend.

**Architecture:** All endpoints follow the existing FastAPI patterns: route function with `request: Request`, `session: AsyncSession = Depends(get_session)`, `_user: str = Depends(require_auth)`, rate-limited via `@limiter.limit()`, `responses={401: {"model": ErrorWrapper}}` for OpenAPI docs. New schemas in `schemas.py`, tests mirror `test_stats_api.py` pattern (mock session, httpx `AsyncClient`).

**Tech Stack:** FastAPI, SQLAlchemy async, pgvector (cosine distance), Pydantic v2, pytest + httpx

---

### Task 1: New schemas for M16 endpoints

**Files:**
- Modify: `src/api/schemas.py`
- Test: `tests/unit/test_schemas.py` (create)

**Step 1: Write the failing test**

Create `tests/unit/test_schemas.py`:

```python
"""Unit tests for M16 Pydantic schemas."""
from __future__ import annotations

from datetime import date, datetime, timezone

from src.api.schemas import (
    BriefingResponse,
    ScoreDistributionResponse,
    SourceInfo,
    SourcesResponse,
    StatsGroupDateResponse,
)


class TestSourceSchemas:
    def test_source_info_fields(self):
        s = SourceInfo(name="hackernews", count=42)
        assert s.name == "hackernews"
        assert s.count == 42

    def test_sources_response_wraps_list(self):
        r = SourcesResponse(sources=[SourceInfo(name="arxiv", count=10)])
        assert len(r.sources) == 1


class TestStatsGroupDateResponse:
    def test_fields(self):
        r = StatsGroupDateResponse(date=date(2026, 2, 22), group="modelos", count=5)
        assert r.group == "modelos"
        assert r.count == 5


class TestScoreDistributionResponse:
    def test_fields(self):
        r = ScoreDistributionResponse(range="0-10", min_score=0, max_score=10, count=45)
        assert r.range == "0-10"
        assert r.count == 45


class TestBriefingResponseOptionalGeneratedAt:
    def test_generated_at_optional(self):
        b = BriefingResponse(date=date(2026, 2, 22), generated_at=None)
        assert b.generated_at is None

    def test_generated_at_with_value(self):
        dt = datetime(2026, 2, 22, 12, 0, tzinfo=timezone.utc)
        b = BriefingResponse(date=date(2026, 2, 22), generated_at=dt)
        assert b.generated_at == dt
```

**Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/unit/test_schemas.py -v`
Expected: FAIL (import errors — schemas don't exist yet)

**Step 3: Write minimal implementation**

Add to `src/api/schemas.py`:

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
    min_score: int
    max_score: int
    count: int
```

Also change `BriefingResponse.generated_at` from `datetime` to `datetime | None = None` so the resilient briefing can set it to `None`.

**Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/unit/test_schemas.py -v`
Expected: PASS

**Step 5: Ruff check**

Run: `.venv/bin/ruff check src/api/schemas.py tests/unit/test_schemas.py`
Expected: All checks passed

**Step 6: Commit**

```bash
git add src/api/schemas.py tests/unit/test_schemas.py
git commit -m "feat: M16 add new schemas — SourceInfo, StatsGroupDate, ScoreDistribution [Track A]"
```

---

### Task 2: GET `/api/items/by-date/{date}` — Items by date

**Files:**
- Modify: `src/api/routes/items.py`
- Test: `tests/unit/test_api_routes.py`

**Step 1: Write the failing tests**

Add to `tests/unit/test_api_routes.py`:

```python
class TestItemsByDate:
    async def test_by_date_returns_200(self, api_client: AsyncClient):
        resp = await api_client.get("/api/items/by-date/2026-02-22")
        assert resp.status_code == 200

    async def test_by_date_returns_list(self, api_client: AsyncClient):
        resp = await api_client.get("/api/items/by-date/2026-02-22")
        assert isinstance(resp.json(), list)

    async def test_by_date_has_total_count_header(self, api_client: AsyncClient):
        resp = await api_client.get("/api/items/by-date/2026-02-22")
        assert "X-Total-Count" in resp.headers

    async def test_by_date_accepts_filters(self, api_client: AsyncClient):
        resp = await api_client.get(
            "/api/items/by-date/2026-02-22",
            params={"topic": "modelos", "source": "hackernews", "limit": 10, "offset": 5},
        )
        assert resp.status_code == 200

    async def test_by_date_invalid_date_returns_422(self, api_client: AsyncClient):
        resp = await api_client.get("/api/items/by-date/not-a-date")
        assert resp.status_code == 422

    async def test_by_date_requires_auth(self, api_client: AsyncClient):
        app.dependency_overrides.pop(require_auth, None)
        resp = await api_client.get("/api/items/by-date/2026-02-22")
        assert resp.status_code == 403
```

**Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/unit/test_api_routes.py::TestItemsByDate -v`
Expected: FAIL (404 — route doesn't exist)

**Step 3: Write minimal implementation**

Add to `src/api/routes/items.py`:

```python
@router.get(
    "/by-date/{item_date}",
    response_model=list[NewsItemResponse],
    responses={401: {"model": ErrorWrapper}},
)
@limiter.limit("30/minute")
async def list_items_by_date(
    request: Request,
    response: Response,
    item_date: date,
    topic: str | None = Query(None, description="Filter by topic"),
    source: str | None = Query(None, description="Filter by source"),
    limit: int = Query(50, ge=1, le=200, description="Max items to return"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    session: AsyncSession = Depends(get_session),
    _user: str = Depends(require_auth),
) -> list[NewsItemResponse]:
    """List news items for a specific date, sorted by score."""
    day_start = datetime.combine(item_date, time.min, tzinfo=UTC)
    day_end = day_start + timedelta(days=1)
    query = select(NewsItem).where(
        (NewsItem.created_at >= day_start) & (NewsItem.created_at < day_end)
    )
    if topic:
        query = query.where(NewsItem.topic == topic)
    if source:
        query = query.where(NewsItem.source == source)

    count_query = select(func.count()).select_from(query.with_only_columns(NewsItem.id).subquery())
    total = (await session.execute(count_query)).scalar_one()
    set_total_count_header(response, total)

    query = query.order_by(NewsItem.score.desc().nulls_last()).offset(offset).limit(limit)
    result = await session.execute(query)
    items = result.scalars().all()
    return [NewsItemResponse.model_validate(item) for item in items]
```

**Important:** This endpoint must be registered BEFORE the existing `""` route in the file, because FastAPI evaluates routes in order. Place it after `/count` and before `/today`, or ensure the path `/by-date/{item_date}` is unique enough not to conflict.

**Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/unit/test_api_routes.py::TestItemsByDate -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/api/routes/items.py tests/unit/test_api_routes.py
git commit -m "feat: M16 GET /api/items/by-date/{date} — items without briefing dependency [Track A]"
```

---

### Task 3: Make GET `/api/briefings/{date}` resilient

**Files:**
- Modify: `src/api/routes/briefings.py`
- Modify: `src/api/schemas.py` (already done in Task 1 — `generated_at` now optional)
- Test: `tests/unit/test_api_routes.py`

**Step 1: Write the failing tests**

Add to `tests/unit/test_api_routes.py`:

```python
class TestResilientBriefing:
    """Briefing endpoint should return synthesized response when no DailyBriefing exists."""

    async def test_briefing_no_record_returns_200_when_items_exist(self, api_client: AsyncClient):
        """When no DailyBriefing but items exist for that date, return 200."""
        # Default mock: scalar_one_or_none=None (no briefing), scalar_one=5 (items exist)
        # Need to override to return count > 0
        mock_session = _make_mock_session()
        # First execute call: briefing lookup (scalar_one_or_none=None)
        # Second: count query (scalar_one=5)
        # Third: items query (scalars().all()=[])
        call_count = 0
        original_execute = mock_session.execute

        async def _side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            result = MagicMock()
            mock_scalars = MagicMock()
            mock_scalars.all.return_value = []
            result.scalars.return_value = mock_scalars
            if call_count == 1:
                result.scalar_one_or_none.return_value = None  # no briefing
            elif call_count == 2:
                result.scalar_one.return_value = 5  # items exist
            else:
                pass  # items query
            return result

        mock_session.execute = AsyncMock(side_effect=_side_effect)

        async def _session_override():
            yield mock_session

        app.dependency_overrides[get_session] = _session_override
        resp = await api_client.get("/api/briefings/2026-02-22")
        assert resp.status_code == 200
        data = resp.json()
        assert data["date"] == "2026-02-22"
        assert data["generated_at"] is None
        assert data["total_items"] is None

    async def test_briefing_no_record_no_items_returns_404(self, api_client: AsyncClient):
        """When no DailyBriefing and no items, return 404."""
        resp = await api_client.get("/api/briefings/2026-02-22")
        assert resp.status_code == 404
```

**Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/unit/test_api_routes.py::TestResilientBriefing -v`
Expected: FAIL (current code always returns 404 when no briefing)

**Step 3: Write minimal implementation**

Replace the `get_briefing` function in `src/api/routes/briefings.py`:

```python
async def get_briefing(
    request: Request,
    response: Response,
    briefing_date: date,
    limit: int = Query(100, ge=1, le=500, description="Max items to return"),
    offset: int = Query(0, ge=0, description="Items offset"),
    session: AsyncSession = Depends(get_session),
    _user: str = Depends(require_auth),
) -> BriefingResponse:
    """Get the daily briefing for a specific date, including paginated items."""
    result = await session.execute(select(DailyBriefing).where(DailyBriefing.date == briefing_date))
    briefing = result.scalar_one_or_none()

    # Use timestamp range for index-friendly queries
    day_start = datetime.combine(briefing_date, time.min, tzinfo=UTC)
    day_end = day_start + timedelta(days=1)
    date_filter = (NewsItem.created_at >= day_start) & (NewsItem.created_at < day_end)

    # Count total items for this date
    items_count = (
        await session.execute(
            select(func.count(NewsItem.id)).where(date_filter)
        )
    ).scalar_one()

    # If no briefing AND no items, truly nothing exists
    if not briefing and items_count == 0:
        raise APIError(404, "BRIEFING_NOT_FOUND", f"No data found for {briefing_date}")

    set_total_count_header(response, items_count)

    # Fetch paginated items
    items_result = await session.execute(
        select(NewsItem)
        .where(date_filter)
        .order_by(NewsItem.score.desc().nulls_last())
        .offset(offset)
        .limit(limit)
    )
    items = items_result.scalars().all()

    if briefing:
        return BriefingResponse(
            date=briefing.date,
            total_items=briefing.total_items,
            items_extracted=briefing.items_extracted,
            items_after_dedup=briefing.items_after_dedup,
            items_filtered=briefing.items_filtered,
            trending_count=briefing.trending_count,
            duration_seconds=briefing.duration_seconds,
            sources_used=briefing.sources_used,
            generated_at=briefing.generated_at,
            items=[NewsItemResponse.model_validate(item) for item in items],
        )

    # Synthesize minimal response from items only
    return BriefingResponse(
        date=briefing_date,
        generated_at=None,
        items=[NewsItemResponse.model_validate(item) for item in items],
    )
```

**Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/unit/test_api_routes.py::TestResilientBriefing -v`
Expected: PASS

**Step 5: Run full existing briefing tests to verify no regression**

Run: `.venv/bin/pytest tests/unit/test_api_routes.py -v -k briefing`
Expected: PASS

**Step 6: Commit**

```bash
git add src/api/routes/briefings.py tests/unit/test_api_routes.py
git commit -m "feat: M16 resilient briefings — synthesize response when no DailyBriefing [Track A]"
```

---

### Task 4: GET `/api/items/trending` — Dedicated trending endpoint

**Files:**
- Modify: `src/api/routes/items.py`
- Test: `tests/unit/test_api_routes.py`

**Step 1: Write the failing tests**

Add to `tests/unit/test_api_routes.py`:

```python
class TestTrendingItems:
    async def test_trending_returns_200(self, api_client: AsyncClient):
        resp = await api_client.get("/api/items/trending")
        assert resp.status_code == 200

    async def test_trending_returns_list(self, api_client: AsyncClient):
        resp = await api_client.get("/api/items/trending")
        assert isinstance(resp.json(), list)

    async def test_trending_has_total_count(self, api_client: AsyncClient):
        resp = await api_client.get("/api/items/trending")
        assert "X-Total-Count" in resp.headers

    async def test_trending_accepts_filters(self, api_client: AsyncClient):
        resp = await api_client.get(
            "/api/items/trending",
            params={"topic": "modelos", "source": "hackernews", "days": 14, "limit": 5},
        )
        assert resp.status_code == 200

    async def test_trending_rejects_excessive_days(self, api_client: AsyncClient):
        resp = await api_client.get("/api/items/trending", params={"days": 999})
        assert resp.status_code == 422

    async def test_trending_requires_auth(self, api_client: AsyncClient):
        app.dependency_overrides.pop(require_auth, None)
        resp = await api_client.get("/api/items/trending")
        assert resp.status_code == 403
```

**Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/unit/test_api_routes.py::TestTrendingItems -v`
Expected: FAIL (404)

**Step 3: Write minimal implementation**

Add to `src/api/routes/items.py`:

```python
@router.get(
    "/trending",
    response_model=list[NewsItemResponse],
    responses={401: {"model": ErrorWrapper}},
)
@limiter.limit("30/minute")
async def list_trending_items(
    request: Request,
    response: Response,
    topic: str | None = Query(None, description="Filter by topic"),
    source: str | None = Query(None, description="Filter by source"),
    days: int = Query(7, ge=1, le=90, description="Look back N days"),
    limit: int = Query(20, ge=1, le=100, description="Max items to return"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    session: AsyncSession = Depends(get_session),
    _user: str = Depends(require_auth),
) -> list[NewsItemResponse]:
    """List trending items from the last N days, sorted by score."""
    since = datetime.combine(
        (datetime.now(tz=UTC) - timedelta(days=days)).date(), time.min, tzinfo=UTC
    )
    query = select(NewsItem).where(
        NewsItem.trending.is_(True) & (NewsItem.created_at >= since)
    )
    if topic:
        query = query.where(NewsItem.topic == topic)
    if source:
        query = query.where(NewsItem.source == source)

    count_query = select(func.count()).select_from(query.with_only_columns(NewsItem.id).subquery())
    total = (await session.execute(count_query)).scalar_one()
    set_total_count_header(response, total)

    query = query.order_by(NewsItem.score.desc().nulls_last(), NewsItem.created_at.desc()).offset(offset).limit(limit)
    result = await session.execute(query)
    items = result.scalars().all()
    return [NewsItemResponse.model_validate(item) for item in items]
```

**Important:** Register `/trending` BEFORE `/today` in the file so FastAPI doesn't interpret `trending` as a value for a path parameter.

**Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/unit/test_api_routes.py::TestTrendingItems -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/api/routes/items.py tests/unit/test_api_routes.py
git commit -m "feat: M16 GET /api/items/trending — dedicated trending endpoint [Track A]"
```

---

### Task 5: GET `/api/items/{item_id}/similar` — Similar items via embeddings

**Files:**
- Modify: `src/api/routes/items.py`
- Test: `tests/unit/test_api_routes.py`

**Step 1: Write the failing tests**

Add to `tests/unit/test_api_routes.py`:

```python
import uuid


class TestSimilarItems:
    async def test_similar_returns_404_when_no_embedding(self, api_client: AsyncClient):
        """Default mock returns None for scalar_one_or_none — no embedding."""
        item_id = str(uuid.uuid4())
        resp = await api_client.get(f"/api/items/{item_id}/similar")
        assert resp.status_code == 404

    async def test_similar_accepts_limit_param(self, api_client: AsyncClient):
        item_id = str(uuid.uuid4())
        resp = await api_client.get(f"/api/items/{item_id}/similar", params={"limit": 3})
        # 404 because no embedding, but param is accepted (not 422)
        assert resp.status_code == 404

    async def test_similar_rejects_excessive_limit(self, api_client: AsyncClient):
        item_id = str(uuid.uuid4())
        resp = await api_client.get(f"/api/items/{item_id}/similar", params={"limit": 999})
        assert resp.status_code == 422

    async def test_similar_requires_auth(self, api_client: AsyncClient):
        app.dependency_overrides.pop(require_auth, None)
        item_id = str(uuid.uuid4())
        resp = await api_client.get(f"/api/items/{item_id}/similar")
        assert resp.status_code == 403

    async def test_similar_invalid_uuid_returns_422(self, api_client: AsyncClient):
        resp = await api_client.get("/api/items/not-a-uuid/similar")
        assert resp.status_code == 422
```

**Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/unit/test_api_routes.py::TestSimilarItems -v`
Expected: FAIL (404 for wrong reason or route not found)

**Step 3: Write minimal implementation**

Add imports to `src/api/routes/items.py`:

```python
import uuid as uuid_mod
from src.core.models import ItemEmbedding, NewsItem
```

Add the endpoint (place it AFTER the existing endpoints, since the path `/{item_id}/similar` won't conflict with `/by-date/`, `/trending/`, `/today`, `/count`):

```python
@router.get(
    "/{item_id}/similar",
    response_model=list[NewsItemResponse],
    responses={
        401: {"model": ErrorWrapper},
        404: {"model": ErrorWrapper},
    },
)
@limiter.limit("20/minute")
async def get_similar_items(
    request: Request,
    item_id: uuid_mod.UUID,
    limit: int = Query(5, ge=1, le=20, description="Number of similar items"),
    session: AsyncSession = Depends(get_session),
    _user: str = Depends(require_auth),
) -> list[NewsItemResponse]:
    """Find similar items using pgvector cosine distance."""
    # Get embedding for the source item
    result = await session.execute(
        select(ItemEmbedding).where(ItemEmbedding.item_id == item_id).limit(1)
    )
    embedding_row = result.scalar_one_or_none()

    if not embedding_row:
        raise APIError(404, "EMBEDDING_NOT_FOUND", f"No embedding found for item {item_id}")

    # Find nearest neighbors (exclude the source item)
    similar_query = (
        select(NewsItem)
        .join(ItemEmbedding, NewsItem.id == ItemEmbedding.item_id)
        .where(ItemEmbedding.item_id != item_id)
        .order_by(ItemEmbedding.embedding.cosine_distance(embedding_row.embedding))
        .limit(limit)
    )
    similar_result = await session.execute(similar_query)
    items = similar_result.scalars().all()
    return [NewsItemResponse.model_validate(item) for item in items]
```

Add `APIError` and `ItemEmbedding` imports at the top of `items.py`:

```python
from src.api.errors import APIError
from src.core.models import ItemEmbedding, NewsItem
```

**Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/unit/test_api_routes.py::TestSimilarItems -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/api/routes/items.py tests/unit/test_api_routes.py
git commit -m "feat: M16 GET /api/items/{id}/similar — pgvector similarity search [Track B]"
```

---

### Task 6: GET `/api/sources` — Sources list with counts

**Files:**
- Create: `src/api/routes/sources.py`
- Modify: `src/api/app.py` (register router)
- Test: Create `tests/unit/test_sources_api.py`

**Step 1: Write the failing tests**

Create `tests/unit/test_sources_api.py`:

```python
"""Unit tests for GET /api/sources endpoint."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from src.api.app import app
from src.api.auth import require_auth
from src.core.database import get_session


def _make_mock_session():
    mock_result = MagicMock()
    mock_result.all.return_value = []
    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(return_value=mock_result)
    return mock_session


async def _mock_get_session():
    yield _make_mock_session()


@pytest.fixture(autouse=True)
def _override_dependencies():
    app.dependency_overrides[get_session] = _mock_get_session
    yield
    app.dependency_overrides.pop(get_session, None)
    app.dependency_overrides.pop(require_auth, None)


@pytest.fixture()
async def api_client() -> AsyncClient:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac  # type: ignore[misc]


class TestSourcesList:
    async def test_returns_200(self, api_client: AsyncClient):
        resp = await api_client.get("/api/sources")
        assert resp.status_code == 200

    async def test_returns_sources_key(self, api_client: AsyncClient):
        resp = await api_client.get("/api/sources")
        assert "sources" in resp.json()
        assert isinstance(resp.json()["sources"], list)

    async def test_no_auth_required(self, api_client: AsyncClient):
        """Sources endpoint is public, like /api/topics."""
        app.dependency_overrides.pop(require_auth, None)
        resp = await api_client.get("/api/sources")
        assert resp.status_code == 200
```

**Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/unit/test_sources_api.py -v`
Expected: FAIL (404 — route doesn't exist)

**Step 3: Write minimal implementation**

Create `src/api/routes/sources.py`:

```python
"""API route for listing active sources."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.schemas import SourceInfo, SourcesResponse
from src.core.database import get_session
from src.core.models import NewsItem

router = APIRouter(prefix="/api/sources", tags=["sources"])
limiter = Limiter(key_func=get_remote_address)


@router.get("", response_model=SourcesResponse)
@limiter.limit("30/minute")
async def list_sources(
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> SourcesResponse:
    """List all sources with item count, sorted by count descending."""
    result = await session.execute(
        select(NewsItem.source, func.count(NewsItem.id).label("count"))
        .group_by(NewsItem.source)
        .order_by(func.count(NewsItem.id).desc())
    )
    sources = [SourceInfo(name=row.source, count=row.count) for row in result.all()]
    return SourcesResponse(sources=sources)
```

Register in `src/api/app.py` — add import and `app.include_router(sources_router)`:

```python
from src.api.routes.sources import router as sources_router
# ...
app.include_router(sources_router)
```

**Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/unit/test_sources_api.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/api/routes/sources.py src/api/app.py tests/unit/test_sources_api.py
git commit -m "feat: M16 GET /api/sources — public sources list with counts [Track A]"
```

---

### Task 7: Chart-ready stats endpoints (by-topic-date, by-source-date, trending-timeline)

**Files:**
- Modify: `src/api/routes/stats.py`
- Modify: `src/api/schemas.py` (StatsGroupDateResponse already added in Task 1)
- Test: `tests/unit/test_stats_api.py`

**Step 1: Write the failing tests**

Add to `tests/unit/test_stats_api.py`:

```python
class TestStatsByTopicDate:
    async def test_returns_200(self, api_client: AsyncClient):
        resp = await api_client.get("/api/stats/by-topic-date")
        assert resp.status_code == 200

    async def test_returns_list(self, api_client: AsyncClient):
        resp = await api_client.get("/api/stats/by-topic-date")
        assert isinstance(resp.json(), list)

    async def test_accepts_days_param(self, api_client: AsyncClient):
        resp = await api_client.get("/api/stats/by-topic-date", params={"days": 7})
        assert resp.status_code == 200

    async def test_rejects_excessive_days(self, api_client: AsyncClient):
        resp = await api_client.get("/api/stats/by-topic-date", params={"days": 999})
        assert resp.status_code == 422


class TestStatsBySourceDate:
    async def test_returns_200(self, api_client: AsyncClient):
        resp = await api_client.get("/api/stats/by-source-date")
        assert resp.status_code == 200

    async def test_returns_list(self, api_client: AsyncClient):
        resp = await api_client.get("/api/stats/by-source-date")
        assert isinstance(resp.json(), list)

    async def test_accepts_days_param(self, api_client: AsyncClient):
        resp = await api_client.get("/api/stats/by-source-date", params={"days": 14})
        assert resp.status_code == 200


class TestTrendingTimeline:
    async def test_returns_200(self, api_client: AsyncClient):
        resp = await api_client.get("/api/stats/trending-timeline")
        assert resp.status_code == 200

    async def test_returns_list(self, api_client: AsyncClient):
        resp = await api_client.get("/api/stats/trending-timeline")
        assert isinstance(resp.json(), list)

    async def test_accepts_days_param(self, api_client: AsyncClient):
        resp = await api_client.get("/api/stats/trending-timeline", params={"days": 60})
        assert resp.status_code == 200
```

**Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/unit/test_stats_api.py -k "TopicDate or SourceDate or TrendingTimeline" -v`
Expected: FAIL (404)

**Step 3: Write minimal implementation**

Add import to `src/api/routes/stats.py`:

```python
from src.api.schemas import (
    ErrorWrapper,
    StatsDateResponse,
    StatsGroupDateResponse,
    StatsGroupResponse,
    StatsSummaryResponse,
)
```

Add endpoints:

```python
@router.get(
    "/by-topic-date",
    response_model=list[StatsGroupDateResponse],
    responses={401: {"model": ErrorWrapper}},
)
@limiter.limit("30/minute")
async def stats_by_topic_date(
    request: Request,
    days: int = Query(30, ge=1, le=365, description="Number of days to include"),
    session: AsyncSession = Depends(get_session),
    _user: str = Depends(require_auth),
) -> list[StatsGroupDateResponse]:
    """Get item count grouped by topic and date for the last N days."""
    since_dt = datetime.combine(
        (datetime.now(tz=UTC) - timedelta(days=days)).date(), time.min, tzinfo=UTC
    )
    created_date = func.date(NewsItem.created_at)
    result = await session.execute(
        select(
            created_date.label("date"),
            NewsItem.topic.label("group"),
            func.count(NewsItem.id).label("count"),
        )
        .where((NewsItem.created_at >= since_dt) & NewsItem.topic.isnot(None))
        .group_by(created_date, NewsItem.topic)
        .order_by(created_date.asc(), NewsItem.topic.asc())
    )
    return [
        StatsGroupDateResponse(date=row.date, group=row.group, count=row.count)
        for row in result.all()
    ]


@router.get(
    "/by-source-date",
    response_model=list[StatsGroupDateResponse],
    responses={401: {"model": ErrorWrapper}},
)
@limiter.limit("30/minute")
async def stats_by_source_date(
    request: Request,
    days: int = Query(30, ge=1, le=365, description="Number of days to include"),
    session: AsyncSession = Depends(get_session),
    _user: str = Depends(require_auth),
) -> list[StatsGroupDateResponse]:
    """Get item count grouped by source and date for the last N days."""
    since_dt = datetime.combine(
        (datetime.now(tz=UTC) - timedelta(days=days)).date(), time.min, tzinfo=UTC
    )
    created_date = func.date(NewsItem.created_at)
    result = await session.execute(
        select(
            created_date.label("date"),
            NewsItem.source.label("group"),
            func.count(NewsItem.id).label("count"),
        )
        .where(NewsItem.created_at >= since_dt)
        .group_by(created_date, NewsItem.source)
        .order_by(created_date.asc(), NewsItem.source.asc())
    )
    return [
        StatsGroupDateResponse(date=row.date, group=row.group, count=row.count)
        for row in result.all()
    ]


@router.get(
    "/trending-timeline",
    response_model=list[StatsDateResponse],
    responses={401: {"model": ErrorWrapper}},
)
@limiter.limit("30/minute")
async def stats_trending_timeline(
    request: Request,
    days: int = Query(30, ge=1, le=365, description="Number of days to include"),
    session: AsyncSession = Depends(get_session),
    _user: str = Depends(require_auth),
) -> list[StatsDateResponse]:
    """Get trending item count by date for the last N days."""
    since_dt = datetime.combine(
        (datetime.now(tz=UTC) - timedelta(days=days)).date(), time.min, tzinfo=UTC
    )
    created_date = func.date(NewsItem.created_at)
    result = await session.execute(
        select(
            created_date.label("date"),
            func.count(NewsItem.id).label("count"),
        )
        .where((NewsItem.created_at >= since_dt) & NewsItem.trending.is_(True))
        .group_by(created_date)
        .order_by(created_date.asc())
    )
    return [StatsDateResponse(date=row.date, count=row.count) for row in result.all()]
```

**Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/unit/test_stats_api.py -k "TopicDate or SourceDate or TrendingTimeline" -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/api/routes/stats.py tests/unit/test_stats_api.py
git commit -m "feat: M16 stats by-topic-date, by-source-date, trending-timeline [Track A]"
```

---

### Task 8: Score distribution + Top items endpoints

**Files:**
- Modify: `src/api/routes/stats.py` (score distribution)
- Modify: `src/api/routes/items.py` (top items)
- Test: `tests/unit/test_stats_api.py`, `tests/unit/test_api_routes.py`

**Step 1: Write the failing tests**

Add to `tests/unit/test_stats_api.py`:

```python
class TestScoreDistribution:
    async def test_returns_200(self, api_client: AsyncClient):
        resp = await api_client.get("/api/stats/score-distribution")
        assert resp.status_code == 200

    async def test_returns_list(self, api_client: AsyncClient):
        resp = await api_client.get("/api/stats/score-distribution")
        assert isinstance(resp.json(), list)

    async def test_accepts_filters(self, api_client: AsyncClient):
        resp = await api_client.get(
            "/api/stats/score-distribution",
            params={"days": 7, "source": "hackernews", "topic": "modelos"},
        )
        assert resp.status_code == 200
```

Add to `tests/unit/test_api_routes.py`:

```python
class TestTopItems:
    async def test_returns_200(self, api_client: AsyncClient):
        resp = await api_client.get("/api/items/top")
        assert resp.status_code == 200

    async def test_returns_list(self, api_client: AsyncClient):
        resp = await api_client.get("/api/items/top")
        assert isinstance(resp.json(), list)

    async def test_accepts_filters(self, api_client: AsyncClient):
        resp = await api_client.get(
            "/api/items/top",
            params={"days": 14, "limit": 5, "topic": "papers", "source": "arxiv"},
        )
        assert resp.status_code == 200

    async def test_rejects_excessive_days(self, api_client: AsyncClient):
        resp = await api_client.get("/api/items/top", params={"days": 999})
        assert resp.status_code == 422

    async def test_requires_auth(self, api_client: AsyncClient):
        app.dependency_overrides.pop(require_auth, None)
        resp = await api_client.get("/api/items/top")
        assert resp.status_code == 403
```

**Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/unit/test_stats_api.py::TestScoreDistribution tests/unit/test_api_routes.py::TestTopItems -v`
Expected: FAIL (404)

**Step 3: Write implementation**

Add score distribution to `src/api/routes/stats.py`:

```python
from src.api.schemas import (
    ErrorWrapper,
    ScoreDistributionResponse,
    StatsDateResponse,
    StatsGroupDateResponse,
    StatsGroupResponse,
    StatsSummaryResponse,
)

# ... existing code ...

_SCORE_BUCKETS = [
    ("0-10", 0, 10),
    ("11-50", 11, 50),
    ("51-100", 51, 100),
    ("101-250", 101, 250),
    ("251-500", 251, 500),
    ("501+", 501, None),
]


@router.get(
    "/score-distribution",
    response_model=list[ScoreDistributionResponse],
    responses={401: {"model": ErrorWrapper}},
)
@limiter.limit("30/minute")
async def stats_score_distribution(
    request: Request,
    days: int = Query(30, ge=1, le=365, description="Number of days to include"),
    source: str | None = Query(None, description="Filter by source"),
    topic: str | None = Query(None, description="Filter by topic"),
    session: AsyncSession = Depends(get_session),
    _user: str = Depends(require_auth),
) -> list[ScoreDistributionResponse]:
    """Get score distribution as histogram buckets."""
    since_dt = datetime.combine(
        (datetime.now(tz=UTC) - timedelta(days=days)).date(), time.min, tzinfo=UTC
    )
    results: list[ScoreDistributionResponse] = []

    for label, min_score, max_score in _SCORE_BUCKETS:
        query = select(func.count(NewsItem.id)).where(
            (NewsItem.created_at >= since_dt) & NewsItem.score.isnot(None)
        )
        query = query.where(NewsItem.score >= min_score)
        if max_score is not None:
            query = query.where(NewsItem.score <= max_score)
        if source:
            query = query.where(NewsItem.source == source)
        if topic:
            query = query.where(NewsItem.topic == topic)

        count = (await session.execute(query)).scalar_one()
        results.append(ScoreDistributionResponse(
            range=label, min_score=min_score, max_score=max_score or 999999, count=count
        ))

    return results
```

Add top items to `src/api/routes/items.py`:

```python
@router.get(
    "/top",
    response_model=list[NewsItemResponse],
    responses={401: {"model": ErrorWrapper}},
)
@limiter.limit("30/minute")
async def list_top_items(
    request: Request,
    days: int = Query(7, ge=1, le=90, description="Look back N days"),
    limit: int = Query(10, ge=1, le=50, description="Max items to return"),
    topic: str | None = Query(None, description="Filter by topic"),
    source: str | None = Query(None, description="Filter by source"),
    session: AsyncSession = Depends(get_session),
    _user: str = Depends(require_auth),
) -> list[NewsItemResponse]:
    """Top items by score in the last N days."""
    since = datetime.combine(
        (datetime.now(tz=UTC) - timedelta(days=days)).date(), time.min, tzinfo=UTC
    )
    query = select(NewsItem).where(
        (NewsItem.created_at >= since) & NewsItem.score.isnot(None)
    )
    if topic:
        query = query.where(NewsItem.topic == topic)
    if source:
        query = query.where(NewsItem.source == source)

    query = query.order_by(NewsItem.score.desc().nulls_last()).limit(limit)
    result = await session.execute(query)
    items = result.scalars().all()
    return [NewsItemResponse.model_validate(item) for item in items]
```

**Important:** Register `/top` BEFORE `/{item_id}/similar` in `items.py` so FastAPI doesn't interpret `top` as a UUID path parameter.

**Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/unit/test_stats_api.py::TestScoreDistribution tests/unit/test_api_routes.py::TestTopItems -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/api/routes/stats.py src/api/routes/items.py tests/unit/test_stats_api.py tests/unit/test_api_routes.py
git commit -m "feat: M16 score distribution + top items endpoints [Track A]"
```

---

### Task 9: Full verification — lint, tests, type check

**Step 1: Run ruff on all modified files**

```bash
.venv/bin/ruff check src/api/routes/items.py src/api/routes/stats.py src/api/routes/briefings.py src/api/routes/sources.py src/api/schemas.py src/api/app.py
```
Expected: All checks passed

**Step 2: Run full unit test suite**

```bash
.venv/bin/pytest tests/unit/ -x --timeout=30 -q
```
Expected: All pass (756 + new tests)

**Step 3: Run pyright on modified files**

```bash
.venv/bin/pyright src/api/routes/items.py src/api/routes/stats.py src/api/routes/briefings.py src/api/routes/sources.py src/api/schemas.py
```
Expected: No new errors

**Step 4: Verify Angular build still works (no frontend changes, sanity check)**

```bash
cd web && npx tsc --noEmit
```
Expected: 0 errors

---

### Task 10: Update AGENTS.md

**Files:**
- Modify: `AGENTS.md`

Update:
- Header: milestone 16, update test count
- Add new file descriptions (`sources.py`, `test_schemas.py`, `test_sources_api.py`)
- Add M16 milestone section with checklist of all 10 endpoints
- Update endpoint documentation section with new endpoints
- Update development history
- Add `ideas-backlog.md` to docs listing

**Commit:**

```bash
git add AGENTS.md
git commit -m "docs: update AGENTS.md for M16 — API Endpoint Expansion complete"
```

---

## Route Registration Order in `items.py`

**Critical:** FastAPI matches routes in order. The final order in `items.py` should be:

1. `GET /api/items` (existing — catch-all list)
2. `GET /api/items/count` (existing)
3. `GET /api/items/by-date/{item_date}` (new — Task 2)
4. `GET /api/items/trending` (new — Task 4)
5. `GET /api/items/top` (new — Task 8)
6. `GET /api/items/today` (existing)
7. `GET /api/items/{item_id}/similar` (new — Task 5, last because `{item_id}` is a catch-all)

Ensure `/{item_id}/similar` is the LAST route to avoid it matching `/by-date/`, `/trending/`, `/top/`, `/today`, or `/count`.

---

## Task Summary

| Task | Description | Risk | Files |
|------|-------------|------|-------|
| 1 | New Pydantic schemas | Low | schemas.py, test_schemas.py |
| 2 | GET /items/by-date/{date} | Low | items.py, test_api_routes.py |
| 3 | Resilient briefings | Medium | briefings.py, test_api_routes.py |
| 4 | GET /items/trending | Low | items.py, test_api_routes.py |
| 5 | GET /items/{id}/similar | Medium | items.py, test_api_routes.py |
| 6 | GET /sources | Low | sources.py, app.py, test_sources_api.py |
| 7 | Stats: topic-date, source-date, trending-timeline | Low | stats.py, test_stats_api.py |
| 8 | Score distribution + top items | Low | stats.py, items.py, tests |
| 9 | Full verification | Low | — |
| 10 | AGENTS.md update | Low | AGENTS.md |
