# Feed Freshness & Pipeline Fix — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix /latest and /top endpoints to show fresh, diverse news, and fix pipeline so HN/Reddit/arXiv actually produce items.

**Architecture:** Add time-window filter + live rescore to FeedBuilder, fix /top sort, fix docker-entrypoint.sh to respect CMD overrides, separate scheduler to pipeline-cron only, increase HN extraction window.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy async, APScheduler, Docker

---

### Task 1: Add config settings for feed freshness

**Files:**
- Modify: `src/core/config.py:117` (after feed_candidate_multiplier)
- Test: `tests/unit/test_composite_scorer.py` (existing, no changes needed)

**Step 1: Add two new settings**

In `src/core/config.py`, after line 120 (`feed_candidate_multiplier`), add:

```python
    feed_latest_max_age_hours: float = 48.0
    feed_latest_min_items: int = 5
```

**Step 2: Verify no breakage**

Run: `pytest tests/unit/test_composite_scorer.py -v --timeout=30`
Expected: All existing tests PASS

**Step 3: Commit**

```bash
git add src/core/config.py
git commit -m "feat: add feed_latest_max_age_hours and feed_latest_min_items settings"
```

---

### Task 2: Add `score_newsitem()` to CompositeScorer

**Files:**
- Modify: `src/pipeline/composite_scorer.py:155` (after `score()` method)
- Test: `tests/unit/test_composite_scorer.py` (add new test class)

**Step 1: Write the failing tests**

Add to `tests/unit/test_composite_scorer.py`:

```python
from src.core.models import NewsItem


class TestScoreNewsitem:
    """Test live rescoring of persisted NewsItem objects."""

    def _make_newsitem(
        self,
        source: str = "github",
        score: int = 10000,
        relevance_score: float = 0.85,
        topic: str = "tools",
        published_at: datetime | None = None,
        source_created_at: datetime | None = None,
        metadata_: dict | None = None,
    ) -> NewsItem:
        item = NewsItem.__new__(NewsItem)
        item.source = source
        item.score = score
        item.relevance_score = relevance_score
        item.topic = topic
        item.published_at = published_at if published_at else datetime.now(UTC)
        item.source_created_at = source_created_at
        item.metadata_ = metadata_ or {}
        return item

    def test_score_newsitem_returns_float_in_range(self):
        scorer = CompositeScorer()
        item = self._make_newsitem()
        result = scorer.score_newsitem(item)
        assert isinstance(result, float)
        assert 0.0 <= result <= 1.0

    def test_score_newsitem_fresh_item_higher_than_old(self):
        scorer = CompositeScorer()
        now = datetime(2026, 3, 1, 12, 0, tzinfo=UTC)
        fresh = self._make_newsitem(published_at=now - timedelta(hours=1))
        old = self._make_newsitem(published_at=now - timedelta(hours=40))
        assert scorer.score_newsitem(fresh, now=now) > scorer.score_newsitem(old, now=now)

    def test_score_newsitem_none_relevance_treated_as_zero(self):
        scorer = CompositeScorer()
        item = self._make_newsitem(relevance_score=None)
        result = scorer.score_newsitem(item)
        assert 0.0 <= result <= 1.0

    def test_score_newsitem_arxiv_uses_no_velocity_weights(self):
        scorer = CompositeScorer()
        now = datetime(2026, 3, 1, 12, 0, tzinfo=UTC)
        item = self._make_newsitem(
            source="arxiv", score=0, topic="papers",
            relevance_score=0.90, published_at=now,
        )
        result = scorer.score_newsitem(item, now=now)
        assert 0.0 <= result <= 1.0
        # Same as ClassifiedItem version: ~0.745
        assert result == pytest.approx(0.745, abs=0.05)
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/test_composite_scorer.py::TestScoreNewsitem -v --timeout=30`
Expected: FAIL with `AttributeError: 'CompositeScorer' object has no attribute 'score_newsitem'`

**Step 3: Implement `score_newsitem()`**

In `src/pipeline/composite_scorer.py`, add after the `score()` method (after line 155):

```python
    def score_newsitem(self, item: object, now: datetime | None = None) -> float:
        """Rescore a persisted NewsItem with current time.

        Accepts any object with source, score, relevance_score, topic,
        published_at, source_created_at, and metadata_ attributes.
        """
        if now is None:
            now = datetime.now(UTC)

        relevance_norm = self._normalize_relevance(
            getattr(item, "relevance_score", None) or 0.0
        )
        recency = self._compute_recency(getattr(item, "published_at", None), now)
        topic_weight = TOPIC_WEIGHTS.get(
            getattr(item, "topic", None) or "", DEFAULT_TOPIC_WEIGHT
        )

        velocity = compute_velocity(
            source=getattr(item, "source", ""),
            score=getattr(item, "score", None),
            source_created_at=getattr(item, "source_created_at", None),
            published_at=getattr(item, "published_at", None),
            metadata=getattr(item, "metadata_", None),
            now=now,
        )

        if velocity is None:
            return (
                self._nv_w_rel * relevance_norm
                + self._nv_w_rec * recency
                + self._nv_w_top * topic_weight
            )

        velocity_norm = self._normalize_velocity(
            velocity, getattr(item, "source", ""), getattr(item, "metadata_", None)
        )
        return (
            self._w_vel * velocity_norm
            + self._w_rel * relevance_norm
            + self._w_rec * recency
            + self._w_top * topic_weight
        )
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/unit/test_composite_scorer.py -v --timeout=30`
Expected: ALL tests PASS

**Step 5: Commit**

```bash
git add src/pipeline/composite_scorer.py tests/unit/test_composite_scorer.py
git commit -m "feat: add score_newsitem() for live rescoring persisted items"
```

---

### Task 3: Add time filter + live rescore to FeedBuilder

**Files:**
- Modify: `src/feed/feed_builder.py` (full rework of `build()`)
- Test: `tests/unit/test_feed_builder.py` (add new tests)

**Step 1: Write failing tests**

Add to `tests/unit/test_feed_builder.py`:

```python
from datetime import UTC, datetime, timedelta


def _make_item_with_dates(
    *,
    title: str = "Test Item",
    source: str = "hackernews",
    topic: str = "models",
    composite_score: float = 0.8,
    score: int = 100,
    author: str | None = None,
    published_at: datetime | None = None,
    created_at: datetime | None = None,
    relevance_score: float = 0.85,
    source_created_at: datetime | None = None,
    metadata_: dict | None = None,
) -> SimpleNamespace:
    """Create a mock NewsItem with date fields for time-filtered builds."""
    now = datetime.now(UTC)
    return SimpleNamespace(
        title=title,
        source=source,
        topic=topic,
        composite_score=composite_score,
        score=score,
        author=author,
        published_at=published_at or now,
        created_at=created_at or now,
        relevance_score=relevance_score,
        source_created_at=source_created_at,
        metadata_=metadata_ or {},
    )


@pytest.mark.asyncio
@patch("src.feed.feed_builder.get_settings")
async def test_build_accepts_max_age_hours(mock_get_settings: MagicMock) -> None:
    """build() accepts max_age_hours parameter without error."""
    mock_get_settings.return_value = _make_settings(
        feed_latest_max_age_hours=48.0,
        feed_latest_min_items=5,
    )
    items = [_make_item(composite_score=0.9)]
    session = _make_mock_session(items)

    builder = FeedBuilder(session)
    result, total = await builder.build(limit=10, max_age_hours=48.0)

    assert len(result) == 1
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_feed_builder.py::test_build_accepts_max_age_hours -v --timeout=30`
Expected: FAIL with `TypeError: build() got an unexpected keyword argument 'max_age_hours'`

**Step 3: Implement time filter + expansion + live rescore**

Replace `src/feed/feed_builder.py` entirely:

```python
"""Feed construction pipeline: candidates -> collapse -> rescore -> MMR -> paginate."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import get_settings
from src.core.logging import get_logger
from src.core.models import NewsItem
from src.core.queries import effective_date
from src.feed.mmr_ranker import mmr_rank
from src.feed.variant_collapse import collapse_variants
from src.pipeline.composite_scorer import CompositeScorer

log = get_logger(__name__)

_EXPANSION_WINDOWS = [48.0, 72.0, 168.0]


class FeedBuilder:
    """Builds a diversified feed from the news items table."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        settings = get_settings()
        self._default_lambda = settings.feed_mmr_lambda
        self._candidate_multiplier = settings.feed_candidate_multiplier
        self._default_max_age = settings.feed_latest_max_age_hours
        self._min_items = settings.feed_latest_min_items

    async def build(
        self,
        *,
        topic: str | None = None,
        source: str | None = None,
        limit: int = 20,
        offset: int = 0,
        diversity: float | None = None,
        max_age_hours: float | None = None,
    ) -> tuple[list[NewsItem], int]:
        """Build a diversified feed.

        Returns (items, total_count).
        """
        lambda_ = diversity if diversity is not None else self._default_lambda
        pool_size = limit * self._candidate_multiplier
        age_limit = max_age_hours if max_age_hours is not None else self._default_max_age

        # Fetch candidates with progressive time window expansion
        all_candidates = await self._fetch_candidates(
            topic=topic,
            source=source,
            pool_size=pool_size + offset,
            max_age_hours=age_limit,
        )

        # Live rescore with current time
        if all_candidates:
            scorer = CompositeScorer()
            now = datetime.now(UTC)
            for item in all_candidates:
                item.composite_score = scorer.score_newsitem(item, now=now)

        # Collapse HF model variants (GGUF/GPTQ dedup)
        collapsed = collapse_variants(all_candidates)

        # Apply MMR diversification
        ranked = mmr_rank(collapsed, lambda_=lambda_, limit=offset + limit)

        # Paginate
        page = ranked[offset : offset + limit]
        total = len(collapsed)

        log.info(
            "feed_built",
            candidates=len(all_candidates),
            after_collapse=len(collapsed),
            returned=len(page),
            total=total,
        )

        return page, total

    async def _fetch_candidates(
        self,
        *,
        topic: str | None,
        source: str | None,
        pool_size: int,
        max_age_hours: float,
    ) -> list[NewsItem]:
        """Fetch candidate items, expanding time window if too few results."""
        windows = [max_age_hours] + [w for w in _EXPANSION_WINDOWS if w > max_age_hours]

        for window in windows:
            cutoff = datetime.now(UTC) - timedelta(hours=window)
            query = select(NewsItem).where(
                NewsItem.composite_score.isnot(None),
                effective_date >= cutoff,
            )
            if topic:
                query = query.where(NewsItem.topic == topic)
            if source:
                query = query.where(NewsItem.source == source)

            query = query.order_by(
                NewsItem.composite_score.desc().nulls_last(),
                effective_date.desc(),
            )

            result = await self._session.execute(query.limit(pool_size))
            candidates = list(result.scalars().all())

            if len(candidates) >= self._min_items:
                log.info(
                    "feed_window_selected",
                    window_hours=window,
                    candidates=len(candidates),
                )
                return candidates

        log.info(
            "feed_window_exhausted",
            final_window=windows[-1],
            candidates=len(candidates),
        )
        return candidates
```

**Step 4: Update `_make_settings` in test file**

In `tests/unit/test_feed_builder.py`, update `_make_settings` to include new fields:

```python
def _make_settings(**overrides: object) -> SimpleNamespace:
    """Create a mock Settings object with feed defaults."""
    defaults = {
        "feed_mmr_lambda": 0.7,
        "feed_candidate_multiplier": 5,
        "feed_latest_max_age_hours": 48.0,
        "feed_latest_min_items": 5,
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)
```

**Step 5: Run all feed builder tests**

Run: `pytest tests/unit/test_feed_builder.py -v --timeout=30`
Expected: ALL tests PASS

**Step 6: Commit**

```bash
git add src/feed/feed_builder.py tests/unit/test_feed_builder.py
git commit -m "feat: add time filter + progressive expansion + live rescore to FeedBuilder"
```

---

### Task 4: Fix `/latest` and `/top` endpoints

**Files:**
- Modify: `src/api/routes/items.py:241-305`
- Test: `tests/unit/test_items_api.py` (add tests)

**Step 1: Write failing test for /top sort**

Add to `tests/unit/test_items_api.py`:

```python
class TestTopEndpoint:
    async def test_top_returns_200(self, api_client: AsyncClient):
        resp = await api_client.get("/api/items/top")
        assert resp.status_code == 200

    async def test_top_returns_list(self, api_client: AsyncClient):
        resp = await api_client.get("/api/items/top")
        assert isinstance(resp.json(), list)
```

**Step 2: Fix `/top` sort — change score to composite_score**

In `src/api/routes/items.py`, line 241, change:

```python
    query = select(NewsItem).where((effective_date >= since) & NewsItem.score.isnot(None))
```
to:
```python
    query = select(NewsItem).where(
        (effective_date >= since) & NewsItem.composite_score.isnot(None)
    )
```

And line 251, change:

```python
    query = query.order_by(NewsItem.score.desc().nulls_last()).offset(offset).limit(limit)
```
to:
```python
    query = query.order_by(
        NewsItem.composite_score.desc().nulls_last()
    ).offset(offset).limit(limit)
```

**Step 3: Fix `/latest` sort=recent — add time filter**

In `src/api/routes/items.py`, in the `sort=recent` branch (lines 291-305), add time filter after line 292:

```python
    # Chronological (sort=recent) — with time window
    cutoff = datetime.now(tz=UTC) - timedelta(hours=48)
    query = select(NewsItem).where(effective_date >= cutoff)
```

**Step 4: Run tests**

Run: `pytest tests/unit/test_items_api.py -v --timeout=30`
Expected: ALL tests PASS

**Step 5: Commit**

```bash
git add src/api/routes/items.py tests/unit/test_items_api.py
git commit -m "fix: sort /top by composite_score, add time filter to /latest sort=recent"
```

---

### Task 5: Fix docker-entrypoint.sh to respect CMD override

**Files:**
- Modify: `docker-entrypoint.sh`

**Step 1: Update entrypoint to pass `$@`**

Replace `docker-entrypoint.sh`:

```bash
#!/usr/bin/env bash
set -e

echo "Running database migrations..."
alembic upgrade head

# If a custom command is passed (e.g. pipeline-scheduler.sh), run it
if [ $# -gt 0 ]; then
    echo "Running custom command: $*"
    exec "$@"
fi

echo "Starting API server..."
exec uvicorn src.api.app:app \
    --host "${API_HOST:-0.0.0.0}" \
    --port "${API_PORT:-8000}" \
    --workers "${API_WORKERS:-2}"
```

**Step 2: Verify locally**

Run: `bash -n docker-entrypoint.sh` (syntax check)
Expected: No output (valid syntax)

**Step 3: Commit**

```bash
git add docker-entrypoint.sh
git commit -m "fix: pass CMD args in docker-entrypoint.sh so pipeline-scheduler.sh runs"
```

---

### Task 6: Separate scheduler — only pipeline-cron runs it

**Files:**
- Modify: `docker-compose.coolify.yml:31` (add SCHEDULER_ENABLED=false to api)

**Step 1: Add SCHEDULER_ENABLED=false to api service**

In `docker-compose.coolify.yml`, in the `api` service `environment` block (after line 32), add:

```yaml
      SCHEDULER_ENABLED: 'false'
```

The `pipeline-cron` service inherits `SCHEDULER_ENABLED=true` from `.env` (already set).

**Step 2: Commit**

```bash
git add docker-compose.coolify.yml
git commit -m "fix: disable scheduler in api container, only pipeline-cron runs it"
```

---

### Task 7: Increase HN extraction window from 1h to 6h

**Files:**
- Modify: `src/pipeline/scheduler.py:74`

**Step 1: Change since_hours**

In `src/pipeline/scheduler.py`, line 74, change:

```python
        kwargs={"sources": ["hackernews", "reddit"], "since_hours": 1},
```
to:
```python
        kwargs={"sources": ["hackernews", "reddit"], "since_hours": 6},
```

**Step 2: Run existing tests**

Run: `pytest tests/ -x --timeout=30 -q`
Expected: ALL tests PASS

**Step 3: Commit**

```bash
git add src/pipeline/scheduler.py
git commit -m "fix: increase HN/Reddit extraction window from 1h to 6h for reliable polling"
```

---

### Task 8: Update AGENTS.md and run full quality gate

**Files:**
- Modify: `AGENTS.md` (update feed algorithm section if it exists)

**Step 1: Run full quality gate**

Run: `ruff check . && ruff format --check . && pyright . && pytest tests/ -x --timeout=30`
Expected: ALL pass

**Step 2: Fix any lint/type issues found**

**Step 3: Commit**

```bash
git add -A
git commit -m "docs: update AGENTS.md with feed freshness changes"
```

---

### Task 9: Deploy and verify on production

**NOT code — manual/operational steps:**

1. Push to main, Coolify auto-deploys
2. SSH to server, verify pipeline-cron runs pipeline-scheduler.sh (not uvicorn)
3. Add `reddit` to `ENABLED_SOURCES` env var in Coolify (if Reddit credentials available)
4. Wait 15 min, check logs for HN extraction
5. Test endpoints:
   - `GET /api/items/latest` — should show only last 48h items
   - `GET /api/items/top?days=7` — should show diverse sources, not just HF
   - `GET /api/items/latest?sort=recent` — should show only recent items
