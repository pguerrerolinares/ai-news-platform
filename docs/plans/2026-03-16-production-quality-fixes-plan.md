# Production Quality Fixes — Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix 3 production data quality issues: URL duplicates, GitHub feed flooding, and LLM retry exhaustion.

**Architecture:** Each fix is independent — separate commits, independently deployable. Fix 3 (retry) is trivial. Fix 2 (GitHub) is config + filter logic. Fix 1 (URL dedup) requires a migration + store stage rewrite.

**Tech Stack:** Python 3.12, SQLAlchemy async, Alembic, PostgreSQL, pytest, respx

**Spec:** `docs/plans/2026-03-16-production-quality-fixes-design.md`

---

## Task 1: LLM Retry Backoff (Fix 3)

Smallest fix first — change constants and add jitter.

**Files:**
- Modify: `src/classifiers/llm.py:28-29` (constants), `src/classifiers/llm.py:70-78` (sleep logic)
- Test: `tests/unit/test_llm_classifier.py`

- [ ] **Step 1: Write failing tests for new retry behavior**

Add to `tests/unit/test_llm_classifier.py`:

```python
class TestRetryBackoff:
    """Tests for retry constants and jitter."""

    def test_max_retries_is_five(self):
        from src.classifiers.llm import MAX_RETRIES
        assert MAX_RETRIES == 5

    def test_retry_backoff_has_four_elements(self):
        from src.classifiers.llm import RETRY_BACKOFF
        assert len(RETRY_BACKOFF) == 4
        assert RETRY_BACKOFF == [2, 5, 15, 30]

    async def test_jitter_applied_to_sleep(self):
        """Verify sleep duration includes jitter (> base wait)."""
        mock_client = _make_mock_client("test")
        # Make first 4 attempts fail, 5th succeed
        mock_client.chat.completions.create = AsyncMock(
            side_effect=[
                openai.RateLimitError(
                    "rate limited",
                    response=MagicMock(status_code=429, headers={}),
                    body=None,
                ),
                openai.RateLimitError(
                    "rate limited",
                    response=MagicMock(status_code=429, headers={}),
                    body=None,
                ),
                openai.RateLimitError(
                    "rate limited",
                    response=MagicMock(status_code=429, headers={}),
                    body=None,
                ),
                openai.RateLimitError(
                    "rate limited",
                    response=MagicMock(status_code=429, headers={}),
                    body=None,
                ),
                SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="ok"))]),
            ]
        )
        with patch("src.classifiers.llm.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            result = await llm_call(mock_client, "model", "system", "prompt")
        assert result == "ok"
        assert mock_sleep.await_count == 4
        # Each sleep should be >= base wait (jitter adds, never subtracts)
        for i, call in enumerate(mock_sleep.await_args_list):
            base = [2, 5, 15, 30][i]
            assert call.args[0] >= base

    async def test_five_failures_exhausts_retries(self):
        """After 5 failures, retries are exhausted and exception is raised."""
        mock_client = _make_mock_client("test")
        mock_client.chat.completions.create = AsyncMock(
            side_effect=openai.RateLimitError(
                "rate limited",
                response=MagicMock(status_code=429, headers={}),
                body=None,
            )
        )
        with (
            patch("src.classifiers.llm.asyncio.sleep", new_callable=AsyncMock),
            pytest.raises(openai.RateLimitError),
        ):
            await llm_call(mock_client, "model", "system", "prompt")
        assert mock_client.chat.completions.create.await_count == 5
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/test_llm_classifier.py::TestRetryBackoff -v`
Expected: FAIL (MAX_RETRIES is 3, RETRY_BACKOFF is [1, 2, 4], no jitter)

- [ ] **Step 3: Update retry constants and add jitter**

In `src/classifiers/llm.py`, change:

```python
# Line 28-29: update constants
MAX_RETRIES = 5
RETRY_BACKOFF = [2, 5, 15, 30]
```

Add `import random` at the top of the file (after `import asyncio`).

In the retry loop (line 70-78), change the sleep line:

```python
            if attempt < MAX_RETRIES - 1:
                wait = RETRY_BACKOFF[attempt]
                jitter = random.uniform(0, wait * 0.3)  # noqa: S311
                logger.warning(
                    "llm_call_retry",
                    attempt=attempt + 1,
                    error=str(exc),
                    wait_seconds=round(wait + jitter, 1),
                )
                await asyncio.sleep(wait + jitter)
```

Also update the docstring (line 49-53) to reflect new values.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/unit/test_llm_classifier.py::TestRetryBackoff -v`
Expected: PASS (all 4 tests)

- [ ] **Step 4b: Update existing retry exhaustion test**

In `tests/unit/test_llm_classifier.py`, find the existing `test_exhausts_retries_and_raises`
(around line 198-211). Change the assertion from `call_count == 3` to `call_count == 5`:

```python
        assert client.chat.completions.create.call_count == 5
```

- [ ] **Step 5: Run full test suite to check no regressions**

Run: `pytest tests/unit/test_llm_classifier.py -v`
Expected: All tests PASS

- [ ] **Step 6: Lint check**

Run: `ruff check src/classifiers/llm.py && ruff format --check src/classifiers/llm.py`
Expected: No errors

- [ ] **Step 7: Commit**

```bash
git add src/classifiers/llm.py tests/unit/test_llm_classifier.py
git commit -m "fix: increase LLM retry backoff and add jitter

MAX_RETRIES 3→5, RETRY_BACKOFF [1,2,4]→[2,5,15,30] with 30% jitter.
Total max wait 7s→52s base (~68s with jitter).
Items still fall back to KeywordClassifier on exhaustion."
```

---

## Task 2: GitHub Repo Age Filter (Fix 2c)

Filter out repos older than 90 days in the GitHub extractor.

**Files:**
- Modify: `src/core/config.py:86` (add `github_max_repo_age_days`)
- Modify: `src/extractors/github.py:94-139` (add age filter in `_search()`)
- Test: `tests/unit/test_github_extractor.py`

- [ ] **Step 1: Write failing tests for repo age filter**

Add to `tests/unit/test_github_extractor.py`:

```python
class TestRepoAgeFilter:
    """Tests for github_max_repo_age_days filtering."""

    @respx.mock
    async def test_old_repo_filtered_out(self):
        """Repos older than github_max_repo_age_days are excluded."""
        old_repo = _make_repo("old-repo", created_at="2020-01-01T00:00:00Z")
        respx.get(SEARCH_URL).mock(
            return_value=httpx.Response(200, json=_search_response([old_repo]))
        )
        with patch(
            "src.extractors.github.get_settings",
            return_value=_mock_settings(github_max_repo_age_days=90),
        ):
            result = await GitHubExtractor().extract()
        assert len(result) == 0

    @respx.mock
    async def test_new_repo_passes_filter(self):
        """Repos newer than github_max_repo_age_days are kept."""
        from datetime import UTC, datetime, timedelta

        recent_date = (datetime.now(tz=UTC) - timedelta(days=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
        new_repo = _make_repo("new-repo", created_at=recent_date)
        respx.get(SEARCH_URL).mock(
            return_value=httpx.Response(200, json=_search_response([new_repo]))
        )
        with patch(
            "src.extractors.github.get_settings",
            return_value=_mock_settings(github_max_repo_age_days=90),
        ):
            result = await GitHubExtractor().extract()
        assert len(result) == 1

    @respx.mock
    async def test_none_created_at_passes_filter(self):
        """Repos with unparseable created_at are included (fail open)."""
        repo = _make_repo("no-date-repo", created_at="not-a-date")
        respx.get(SEARCH_URL).mock(
            return_value=httpx.Response(200, json=_search_response([repo]))
        )
        with patch(
            "src.extractors.github.get_settings",
            return_value=_mock_settings(github_max_repo_age_days=90),
        ):
            result = await GitHubExtractor().extract()
        assert len(result) == 1

    @respx.mock
    async def test_zero_age_disables_filter(self):
        """github_max_repo_age_days=0 disables the filter."""
        old_repo = _make_repo("old-but-allowed", created_at="2020-01-01T00:00:00Z")
        respx.get(SEARCH_URL).mock(
            return_value=httpx.Response(200, json=_search_response([old_repo]))
        )
        with patch(
            "src.extractors.github.get_settings",
            return_value=_mock_settings(github_max_repo_age_days=0),
        ):
            result = await GitHubExtractor().extract()
        assert len(result) == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/test_github_extractor.py::TestRepoAgeFilter -v`
Expected: FAIL (no `github_max_repo_age_days` in Settings, no filter in extractor)

- [ ] **Step 3: Add config field**

In `src/core/config.py`, after line 86 (`github_min_stars: int = 50`), add:

```python
    github_max_repo_age_days: int = 90
```

- [ ] **Step 4: Add age filter to GitHub extractor**

In `src/extractors/github.py`, modify `_search()` method.

At the top of `_search()` (after line 86 `q = f"..."`), read settings:

```python
        max_age_days = get_settings().github_max_repo_age_days
```

After the `created_at_dt` parsing block (lines 109-117) and before the `items.append(...)` block, add the age filter:

```python
            # Repo age filter: skip repos older than configured threshold
            if created_at_dt is not None and max_age_days > 0:
                if (datetime.now(tz=UTC) - created_at_dt).days > max_age_days:
                    continue
```

No signature change needed — `get_settings()` is `@lru_cache` and already patched in all tests.

- [ ] **Step 5: Update `_mock_settings` defaults and fix existing test regression**

In `tests/unit/test_github_extractor.py`, add `github_max_repo_age_days` to the
`_mock_settings` defaults dict (around line 53):

```python
        "github_max_repo_age_days": 0,  # disabled by default in tests
```

Setting it to `0` (disabled) prevents the age filter from breaking existing tests that
use old `created_at` dates (e.g., `test_extract_captures_repo_created_at` uses 2024).

The new `TestRepoAgeFilter` tests explicitly pass `github_max_repo_age_days=90` to
enable the filter for those specific tests.

- [ ] **Step 6: Run tests to verify they pass**

Run: `pytest tests/unit/test_github_extractor.py::TestRepoAgeFilter -v`
Expected: PASS (all 4 tests)

- [ ] **Step 7: Run full GitHub extractor tests**

Run: `pytest tests/unit/test_github_extractor.py -v`
Expected: All tests PASS (age filter disabled by default in mock settings)

- [ ] **Step 8: Lint check**

Run: `ruff check src/extractors/github.py src/core/config.py && ruff format --check src/extractors/github.py src/core/config.py`
Expected: No errors

- [ ] **Step 9: Commit**

```bash
git add src/core/config.py src/extractors/github.py tests/unit/test_github_extractor.py
git commit -m "feat: add GitHub repo age filter (max 90 days)

Repos with created_at older than github_max_repo_age_days (default 90)
are skipped. Repos with unparseable dates are included (fail open).
Set to 0 to disable. Mature repos still appear via HN curation."
```

---

## Task 3: Raise GitHub Minimum Stars (Fix 2a)

Trivial config change — update default from 50 to 500.

**Files:**
- Modify: `src/core/config.py:86`
- Test: `tests/unit/test_github_extractor.py` (update `_mock_settings` default)

- [ ] **Step 1: Update default in config**

In `src/core/config.py` line 86, change:

```python
    github_min_stars: int = 500
```

- [ ] **Step 2: Update test helper default**

In `tests/unit/test_github_extractor.py`, update `_mock_settings()` defaults dict:

```python
        "github_min_stars": 500,
```

- [ ] **Step 3: Run tests**

Run: `pytest tests/unit/test_github_extractor.py -v`
Expected: All PASS

- [ ] **Step 4: Commit**

```bash
git add src/core/config.py tests/unit/test_github_extractor.py
git commit -m "fix: raise GitHub min stars 50→500 to reduce feed noise

4462/7011 items (64%) were GitHub repos. Higher threshold filters
mature repos with any recent push. Combined with repo age filter."
```

---

## Task 4: Persistent "Already Seen" Filter (Fix 2b)

New pipeline stage that queries the DB to filter items already stored in the last N days.

**Files:**
- Modify: `src/core/config.py` (add `seen_window_days`)
- Create: `src/pipeline/stages/seen_filter.py`
- Modify: `src/pipeline/pipeline.py:80` (insert stage after dedup)
- Test: `tests/unit/test_seen_filter.py`

- [ ] **Step 1: Add config field**

In `src/core/config.py`, after `github_max_repo_age_days`, add:

```python
    seen_window_days: int = 7
```

- [ ] **Step 2: Write failing tests**

Create `tests/unit/test_seen_filter.py`:

```python
"""Tests for src.pipeline.stages.seen_filter — persistent already-seen filter."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.extractors.base import ExtractedItem
from src.pipeline.stages.seen_filter import filter_already_seen


def _make_item(url: str | None = "https://example.com/test", title: str = "Test") -> ExtractedItem:
    return ExtractedItem(title=title, source="hackernews", url=url)


class TestFilterAlreadySeen:
    async def test_filters_out_items_with_known_url_hash(self):
        """Items whose url_hash exists in DB are filtered out."""
        item = _make_item("https://example.com/already-seen")

        mock_session = AsyncMock()
        # Simulate DB returning the url_hash as already existing
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [item.url_hash]
        mock_session.execute = AsyncMock(return_value=mock_result)

        with patch("src.pipeline.stages.seen_filter.get_settings") as mock_settings:
            mock_settings.return_value.seen_window_days = 7
            result = await filter_already_seen(mock_session, [item])

        assert len(result) == 0

    async def test_keeps_items_not_in_db(self):
        """Items whose url_hash is NOT in DB pass through."""
        item = _make_item("https://example.com/brand-new")

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []  # nothing in DB
        mock_session.execute = AsyncMock(return_value=mock_result)

        with patch("src.pipeline.stages.seen_filter.get_settings") as mock_settings:
            mock_settings.return_value.seen_window_days = 7
            result = await filter_already_seen(mock_session, [item])

        assert len(result) == 1

    async def test_items_without_url_always_pass(self):
        """Items with url=None (no url_hash) are never filtered."""
        item = _make_item(url=None, title="No URL item")

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute = AsyncMock(return_value=mock_result)

        with patch("src.pipeline.stages.seen_filter.get_settings") as mock_settings:
            mock_settings.return_value.seen_window_days = 7
            result = await filter_already_seen(mock_session, [item])

        assert len(result) == 1

    async def test_empty_input_returns_empty(self):
        """Empty list returns empty list without DB query."""
        mock_session = AsyncMock()

        result = await filter_already_seen(mock_session, [])

        assert result == []
        mock_session.execute.assert_not_awaited()

    async def test_mixed_seen_and_unseen(self):
        """Mix of seen and unseen items: only unseen pass."""
        seen = _make_item("https://example.com/old")
        unseen = _make_item("https://example.com/new")
        no_url = _make_item(url=None, title="No URL")

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [seen.url_hash]
        mock_session.execute = AsyncMock(return_value=mock_result)

        with patch("src.pipeline.stages.seen_filter.get_settings") as mock_settings:
            mock_settings.return_value.seen_window_days = 7
            result = await filter_already_seen(mock_session, [seen, unseen, no_url])

        assert len(result) == 2
        urls = [i.url for i in result]
        assert "https://example.com/new" in urls
        assert None in urls
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `pytest tests/unit/test_seen_filter.py -v`
Expected: FAIL (module `src.pipeline.stages.seen_filter` does not exist)

- [ ] **Step 4: Implement `filter_already_seen`**

Create `src/pipeline/stages/seen_filter.py`:

```python
"""Seen filter stage — skip items already stored in recent days."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import get_settings
from src.core.logging import get_logger
from src.core.models import NewsItem
from src.extractors.base import ExtractedItem

logger = get_logger(__name__)


async def filter_already_seen(
    session: AsyncSession,
    items: list[ExtractedItem],
) -> list[ExtractedItem]:
    """Filter out items whose url_hash already exists in news_items.

    Items without a URL (url_hash is None) always pass through.
    Only checks items stored within the configured seen_window_days.
    """
    if not items:
        return []

    settings = get_settings()
    window_days = settings.seen_window_days

    # Separate items with and without URLs
    items_with_url = [i for i in items if i.url_hash is not None]
    items_without_url = [i for i in items if i.url_hash is None]

    if not items_with_url:
        return items

    # Query DB for existing url_hashes (no f-string SQL — uses SQLAlchemy func)
    url_hashes = [i.url_hash for i in items_with_url]
    cutoff = func.now() - func.make_interval(0, 0, 0, window_days)
    stmt = select(NewsItem.url_hash).where(
        NewsItem.url_hash.in_(url_hashes),
        NewsItem.created_at >= cutoff,
    )
    result = await session.execute(stmt)
    existing_hashes = set(result.scalars().all())

    # Filter
    new_items = [i for i in items_with_url if i.url_hash not in existing_hashes]
    filtered_count = len(items_with_url) - len(new_items)

    if filtered_count > 0:
        logger.info(
            "seen_filter_applied",
            input_count=len(items),
            filtered=filtered_count,
            window_days=window_days,
        )

    return new_items + items_without_url
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/unit/test_seen_filter.py -v`
Expected: PASS (all 5 tests)

- [ ] **Step 6: Wire into pipeline**

In `src/pipeline/pipeline.py`, add import at line 23 area:

```python
from src.pipeline.stages.seen_filter import filter_already_seen
```

After the dedup block (after line 81 `items_after_dedup = len(unique_items)`), add:

```python
        # 2.5. Filter already seen (persistent DB dedup)
        unique_items = await filter_already_seen(session, unique_items)
        logger.info("pipeline_seen_filter", count=len(unique_items))
```

- [ ] **Step 7: Run pipeline unit tests**

Run: `pytest tests/unit/test_pipeline.py -v`
Expected: PASS (pipeline test mocks session)

- [ ] **Step 8: Lint check**

Run: `ruff check src/pipeline/stages/seen_filter.py src/pipeline/pipeline.py src/core/config.py && ruff format --check src/pipeline/stages/seen_filter.py src/pipeline/pipeline.py src/core/config.py`
Expected: No errors

- [ ] **Step 9: Commit**

```bash
git add src/core/config.py src/pipeline/stages/seen_filter.py src/pipeline/pipeline.py tests/unit/test_seen_filter.py
git commit -m "feat: add persistent 'already seen' filter for all sources

New pipeline stage after dedup queries news_items by url_hash to skip
items stored in the last seen_window_days (default 7). Applies to all
sources, reducing GitHub/HF/RSS re-ingestion."
```

---

## Task 5: URL Hash Unique Index Migration (Fix 1a)

Alembic migration to clean duplicates and add partial unique index on `url_hash`.

**Files:**
- Create: `alembic/versions/011_url_hash_unique.py`

- [ ] **Step 1: Create migration**

Create `alembic/versions/011_url_hash_unique.py`:

```python
"""Add partial unique index on url_hash after cleaning duplicates.

Revision ID: 011
Revises: 010
"""

from __future__ import annotations

from alembic import op

revision = "011"
down_revision = "010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Step 1: Delete duplicate url_hash rows, keeping the one with
    # highest composite_score (tiebreak: most recent created_at).
    op.execute("""
        DELETE FROM news_items
        WHERE id IN (
            SELECT id FROM (
                SELECT id,
                       ROW_NUMBER() OVER (
                           PARTITION BY url_hash
                           ORDER BY composite_score DESC NULLS LAST,
                                    created_at DESC
                       ) AS rn
                FROM news_items
                WHERE url_hash IS NOT NULL
            ) ranked
            WHERE rn > 1
        )
    """)

    # Step 2: Create partial unique index (NULLs excluded)
    op.create_index(
        "uix_news_items_url_hash",
        "news_items",
        ["url_hash"],
        unique=True,
        postgresql_where="url_hash IS NOT NULL",
    )


def downgrade() -> None:
    op.drop_index("uix_news_items_url_hash", table_name="news_items")
```

- [ ] **Step 2: Verify migration syntax**

Run: `cd /home/paul/Documentos/proyectos/backend/ai-news-platform && python -c "import alembic; print('OK')"`
Expected: OK (alembic importable)

- [ ] **Step 3: Commit migration**

```bash
git add alembic/versions/011_url_hash_unique.py
git commit -m "feat: add url_hash partial unique index migration

Cleans 194 duplicate URL items (keeps highest composite_score),
then creates uix_news_items_url_hash WHERE url_hash IS NOT NULL.
CASCADE deletes orphaned embeddings (~\$0.01 to regenerate)."
```

---

## Task 6: Store Stage Upsert Logic (Fix 1b)

Split insert logic: items with URL use `ON CONFLICT url_hash DO UPDATE`, items without URL keep `ON CONFLICT content_hash DO NOTHING`.

**Files:**
- Modify: `src/pipeline/stages/store.py:33-60`
- Test: `tests/unit/test_stage_store.py`

- [ ] **Step 1: Write failing tests for upsert behavior**

Add to `tests/unit/test_stage_store.py`:

```python
class TestUrlHashUpsert:
    """Tests for url_hash-based upsert-on-better-score."""

    async def test_item_with_url_uses_url_hash_conflict(self):
        """Items with URL use ON CONFLICT url_hash DO UPDATE."""
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.rowcount = 1
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.commit = AsyncMock()

        item = _make_classified(title="Test", url="https://example.com/repo")
        await store_classified_items(mock_session, [item])

        # Verify the SQL statement used url_hash conflict
        call_args = mock_session.execute.call_args_list[0]
        stmt = call_args.args[0]
        compiled = stmt.compile(
            dialect=__import__("sqlalchemy.dialects.postgresql", fromlist=["dialect"]).dialect()
        )
        sql = str(compiled)
        assert "ON CONFLICT" in sql
        assert "url_hash" in sql or "DO UPDATE" in sql

    async def test_item_without_url_uses_content_hash_conflict(self):
        """Items without URL use ON CONFLICT content_hash DO NOTHING."""
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.rowcount = 1
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.commit = AsyncMock()

        item = _make_classified(title="No URL Item", url=None)
        await store_classified_items(mock_session, [item])

        call_args = mock_session.execute.call_args_list[0]
        stmt = call_args.args[0]
        compiled = stmt.compile(
            dialect=__import__("sqlalchemy.dialects.postgresql", fromlist=["dialect"]).dialect()
        )
        sql = str(compiled)
        assert "DO NOTHING" in sql
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/test_stage_store.py::TestUrlHashUpsert -v`
Expected: FAIL (current code always uses `on_conflict_do_nothing` on `content_hash`)

- [ ] **Step 3: Implement split insert logic**

Rewrite `store_classified_items` in `src/pipeline/stages/store.py`:

```python
async def store_classified_items(session: AsyncSession, items: list[ClassifiedItem]) -> int:
    """Store classified items in PostgreSQL with batch commits.

    Items WITH a URL: upsert on url_hash — update scores if new values are higher.
    Items WITHOUT a URL: insert with on_conflict_do_nothing on content_hash.
    """
    if not items:
        return 0

    stored = 0
    for i, ci in enumerate(items):
        item = ci.item
        values = dict(
            title=item.title,
            url=item.url,
            source=item.source,
            published_at=item.published_at,
            content_hash=item.content_hash,
            url_hash=item.url_hash,
            full_text=item.text,
            author=item.author,
            score=item.score,
            source_created_at=item.source_created_at,
            metadata_=item.metadata,
            topic=ci.topic,
            relevance_score=ci.relevance_score,
            credibility_score=ci.credibility_score,
            summary=ci.summary,
            priority=ci.priority,
            trending=ci.trending,
            dev_value_score=ci.dev_value_score,
            composite_score=ci.composite_score,
        )

        base_stmt = insert(NewsItem).values(**values)

        if item.url_hash is not None:
            # Upsert: update scores if new values are higher
            stmt = base_stmt.on_conflict_do_update(
                index_elements=["url_hash"],
                index_where=text("url_hash IS NOT NULL"),
                set_={
                    "composite_score": func.greatest(
                        NewsItem.composite_score, base_stmt.excluded.composite_score
                    ),
                    "score": func.greatest(
                        NewsItem.score, base_stmt.excluded.score
                    ),
                    "relevance_score": func.greatest(
                        NewsItem.relevance_score, base_stmt.excluded.relevance_score
                    ),
                },
            )
        else:
            stmt = base_stmt.on_conflict_do_nothing(index_elements=["content_hash"])

        result = await session.execute(stmt)
        if result.rowcount and result.rowcount > 0:
            stored += 1

        if (i + 1) % _BATCH_COMMIT_SIZE == 0:
            await session.commit()

    await session.commit()
    items_stored_total.inc(stored)
    logger.info("items_stored", count=stored, skipped=len(items) - stored)
    return stored
```

Add `func` to the imports at the top:

```python
from sqlalchemy import func, select, text
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/unit/test_stage_store.py -v`
Expected: All PASS

- [ ] **Step 5: Run full test suite**

Run: `pytest tests/unit/ -x --timeout=30`
Expected: All PASS

- [ ] **Step 6: Lint check**

Run: `ruff check src/pipeline/stages/store.py && ruff format --check src/pipeline/stages/store.py`
Expected: No errors

- [ ] **Step 7: Commit**

```bash
git add src/pipeline/stages/store.py tests/unit/test_stage_store.py
git commit -m "feat: split store insert by URL presence for url_hash upsert

Items WITH URL: ON CONFLICT (url_hash) DO UPDATE scores via GREATEST.
Items WITHOUT URL: ON CONFLICT (content_hash) DO NOTHING (unchanged).
Title/summary preserved from first ingestion."
```

---

## Task 7: Full Verification & Docs

- [ ] **Step 1: Run complete test suite**

Run: `ruff check . && ruff format --check . && pytest tests/unit/ -x --timeout=30`
Expected: All PASS, no lint errors

- [ ] **Step 2: Update AGENTS.md**

Add to the pipeline section a note about the new `filter_already_seen` stage and the url_hash unique index.

- [ ] **Step 3: Mark spec tasks as done**

Update `docs/plans/2026-03-16-production-quality-fixes-design.md` header to note completion.

- [ ] **Step 4: Final commit**

```bash
git add docs/ AGENTS.md
git commit -m "docs: update architecture for production quality fixes"
```

---

## Post-Deploy Steps (manual, after merging)

These steps run on the production server AFTER deploying the new code:

1. **Run migration**: `docker exec -it pipeline-cron-... alembic upgrade head`
   - This cleans ~194 duplicate items and creates the `uix_news_items_url_hash` index
2. **Update env vars in Coolify**:
   - `GITHUB_MIN_STARS=500` (overrides new default)
   - Verify `SEEN_WINDOW_DAYS=7` (or leave default)
3. **Monitor pipeline logs** for 24h:
   - Check `seen_filter_applied` log entries
   - Check GitHub item count drops from ~300/day to reasonable levels
   - Check LLM retry logs show longer backoff times
4. **Verify embeddings regenerate** for surviving items (check `embed_items_stored` log)
