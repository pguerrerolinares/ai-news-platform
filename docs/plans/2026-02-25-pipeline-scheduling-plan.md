# Pipeline Scheduling + Live Feeds — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace daily cron with per-source APScheduler intervals inside FastAPI, add Reddit OAuth, RSS ETags, and HuggingFace daily_papers.

**Architecture:** APScheduler `AsyncIOScheduler` starts in FastAPI lifespan. Pipeline refactored to accept optional `sources` filter. Each scheduler tier calls `run_pipeline(session, sources=[...])` at its configured interval. Reddit migrates to OAuth client_credentials flow. RSS adds conditional requests (ETag/If-Modified-Since). HuggingFace adds daily_papers endpoint alongside trending models.

**Tech Stack:** APScheduler 3.10, httpx (existing), FastAPI lifespan (existing), feedparser (existing)

---

## Task 1: Add APScheduler dependency

**Files:**
- Modify: `pyproject.toml:10-40`

**Step 1: Add apscheduler to dependencies**

In `pyproject.toml`, add `apscheduler` to the `dependencies` list, after the existing entries:

```toml
    # Scheduling
    "apscheduler~=3.10",
```

Add it right after the `"slowapi~=0.1.0",` line (before MCP).

**Step 2: Install the new dependency**

Run: `cd /home/paul/Documentos/proyectos/backend/ai-news-platform && pip install -e ".[dev]"`
Expected: Successfully installed apscheduler-3.10.x

**Step 3: Verify import works**

Run: `python -c "from apscheduler.schedulers.asyncio import AsyncIOScheduler; print('OK')"`
Expected: `OK`

**Step 4: Commit**

```bash
git add pyproject.toml
git commit -m "feat: add apscheduler~=3.10 dependency for pipeline scheduling"
```

---

## Task 2: Add scheduler config settings

**Files:**
- Modify: `src/core/config.py:108-114`
- Modify: `.env:64-67`
- Test: `tests/unit/test_config.py` (add new tests)

**Step 1: Write the failing tests**

Add to `tests/unit/test_config.py`:

```python
class TestSchedulerConfig:
    """Scheduler-related settings."""

    def test_scheduler_enabled_default(self):
        """scheduler_enabled defaults to True."""
        from src.core.config import Settings
        s = Settings(telegram_bot_token="", telegram_chat_id="", telegram_alerts_enabled=False)
        assert s.scheduler_enabled is True

    def test_poll_interval_defaults(self):
        """Poll intervals have sensible defaults."""
        from src.core.config import Settings
        s = Settings(telegram_bot_token="", telegram_chat_id="", telegram_alerts_enabled=False)
        assert s.hn_poll_interval_minutes == 15
        assert s.reddit_poll_interval_minutes == 15
        assert s.rss_poll_interval_minutes == 60
        assert s.github_poll_interval_minutes == 60
        assert s.hf_poll_interval_minutes == 60
        assert s.arxiv_cron_hour == 1
        assert s.arxiv_cron_minute == 30

    def test_reddit_oauth_defaults_empty(self):
        """Reddit OAuth credentials default to empty strings."""
        from src.core.config import Settings
        s = Settings(telegram_bot_token="", telegram_chat_id="", telegram_alerts_enabled=False)
        assert s.reddit_client_id == ""
        assert s.reddit_client_secret == ""
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/test_config.py::TestSchedulerConfig -v`
Expected: FAIL (attributes do not exist yet)

**Step 3: Add settings to config.py**

In `src/core/config.py`, add a new section after the `# --- Pipeline ---` block (after line 111):

```python
    # --- Scheduler ---
    scheduler_enabled: bool = True
    hn_poll_interval_minutes: int = 15
    reddit_poll_interval_minutes: int = 15
    rss_poll_interval_minutes: int = 60
    github_poll_interval_minutes: int = 60
    hf_poll_interval_minutes: int = 60
    arxiv_cron_hour: int = 1
    arxiv_cron_minute: int = 30

    # --- Reddit OAuth ---
    reddit_client_id: str = ""
    reddit_client_secret: str = ""
```

**Step 4: Update .env with new settings**

Add to `.env` after the `TIMEZONE=Europe/Madrid` line:

```
# --- Scheduler ---
SCHEDULER_ENABLED=true
HN_POLL_INTERVAL_MINUTES=15
REDDIT_POLL_INTERVAL_MINUTES=15
RSS_POLL_INTERVAL_MINUTES=60
GITHUB_POLL_INTERVAL_MINUTES=60
HF_POLL_INTERVAL_MINUTES=60
ARXIV_CRON_HOUR=1
ARXIV_CRON_MINUTE=30

# --- Reddit OAuth (optional, for higher rate limits) ---
REDDIT_CLIENT_ID=
REDDIT_CLIENT_SECRET=
```

**Step 5: Run tests to verify they pass**

Run: `pytest tests/unit/test_config.py::TestSchedulerConfig -v`
Expected: PASS (3 tests)

**Step 6: Commit**

```bash
git add src/core/config.py .env tests/unit/test_config.py
git commit -m "feat: add scheduler + Reddit OAuth config settings"
```

---

## Task 3: Pipeline refactor — accept `sources` filter

**Files:**
- Modify: `src/pipeline/pipeline.py:54-78` (`_get_extractors`)
- Modify: `src/pipeline/pipeline.py:265` (`run_pipeline` signature)
- Test: `tests/unit/test_pipeline.py` (add new tests)

**Step 1: Write the failing tests**

Add to `tests/unit/test_pipeline.py`:

```python
class TestGetExtractorsWithFilter:
    """_get_extractors with sources filter parameter."""

    def test_filter_to_single_source(self):
        """When sources=['hackernews'], only HackerNewsExtractor is returned."""
        settings = _mock_settings(enabled_sources="hackernews,arxiv,reddit,rss")
        with patch("src.pipeline.pipeline.get_settings", return_value=settings):
            extractors = _get_extractors(sources=["hackernews"])
        assert len(extractors) == 1
        assert extractors[0].source_name == "hackernews"

    def test_filter_to_multiple_sources(self):
        """When sources=['hackernews','reddit'], only those two are returned."""
        settings = _mock_settings(enabled_sources="hackernews,arxiv,reddit,rss")
        with patch("src.pipeline.pipeline.get_settings", return_value=settings):
            extractors = _get_extractors(sources=["hackernews", "reddit"])
        assert len(extractors) == 2
        names = [e.source_name for e in extractors]
        assert "hackernews" in names
        assert "reddit" in names

    def test_filter_none_returns_all_enabled(self):
        """When sources=None, all enabled sources are returned (backward compat)."""
        settings = _mock_settings(enabled_sources="hackernews,arxiv,reddit,rss")
        with patch("src.pipeline.pipeline.get_settings", return_value=settings):
            extractors = _get_extractors(sources=None)
        assert len(extractors) == 4

    def test_filter_source_not_enabled_returns_empty(self):
        """When filtering for a source not in ENABLED_SOURCES, returns empty."""
        settings = _mock_settings(enabled_sources="hackernews")
        with patch("src.pipeline.pipeline.get_settings", return_value=settings):
            extractors = _get_extractors(sources=["reddit"])
        assert extractors == []


class TestRunPipelineWithSources:
    """run_pipeline with sources parameter."""

    @pytest.mark.asyncio
    async def test_pipeline_passes_sources_to_get_extractors(self):
        """run_pipeline(session, sources=['hackernews']) filters extractors."""
        settings = _mock_settings(
            enabled_sources="hackernews,reddit",
            openai_api_key="",
            enable_news_validation=False,
            embedding_api_key="",
        )
        session = _mock_session()
        items = [_make_extracted_item()]
        classified = [_make_classified_item()]

        with (
            patch("src.pipeline.pipeline.get_settings", return_value=settings),
            patch("src.pipeline.pipeline._get_extractors") as mock_get_ext,
            patch(
                "src.pipeline.pipeline._extract_all",
                new_callable=AsyncMock,
                return_value=items,
            ),
            patch("src.pipeline.pipeline.deduplicate_items", return_value=items),
            patch("src.pipeline.pipeline.KeywordClassifier") as mock_kw_cls,
            patch("src.pipeline.pipeline.CredibilityValidator") as mock_val_cls,
            patch("src.pipeline.pipeline.AlertService") as mock_alerts_cls,
        ):
            mock_ext = MagicMock()
            mock_ext.source_name = "hackernews"
            mock_get_ext.return_value = [mock_ext]

            mock_classifier = AsyncMock()
            mock_classifier.classify.return_value = classified
            mock_kw_cls.return_value = mock_classifier

            mock_validator = AsyncMock()
            mock_validator.validate.return_value = classified
            mock_val_cls.return_value = mock_validator

            mock_alerts = AsyncMock()
            mock_alerts_cls.return_value = mock_alerts

            result = await run_pipeline(session, sources=["hackernews"])

        assert result is True
        mock_get_ext.assert_called_once_with(sources=["hackernews"])
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/test_pipeline.py::TestGetExtractorsWithFilter -v`
Expected: FAIL (TypeError: _get_extractors() got unexpected keyword argument 'sources')

Run: `pytest tests/unit/test_pipeline.py::TestRunPipelineWithSources -v`
Expected: FAIL (TypeError: run_pipeline() got unexpected keyword argument 'sources')

**Step 3: Modify `_get_extractors` to accept `sources` parameter**

Change the function signature in `src/pipeline/pipeline.py:54`:

```python
def _get_extractors(sources: list[str] | None = None) -> list[BaseExtractor]:
    """Build list of enabled extractors, optionally filtered by source names."""
    settings = get_settings()
    enabled = settings.enabled_sources_list

    # If sources filter is provided, intersect with enabled sources
    if sources is not None:
        enabled = [s for s in enabled if s in sources]

    extractors: list[BaseExtractor] = []
    # ... rest unchanged ...
```

**Step 4: Modify `run_pipeline` to accept `sources` parameter**

Change the function signature in `src/pipeline/pipeline.py:265`:

```python
async def run_pipeline(session: AsyncSession, sources: list[str] | None = None) -> bool:
```

And update the call to `_get_extractors()` at line ~287:

```python
        extractors = _get_extractors(sources=sources)
```

**Step 5: Run all pipeline tests to verify**

Run: `pytest tests/unit/test_pipeline.py -v`
Expected: ALL PASS (existing tests still work because `sources=None` is backward compatible)

**Step 6: Commit**

```bash
git add src/pipeline/pipeline.py tests/unit/test_pipeline.py
git commit -m "feat: pipeline accepts sources filter for per-tier scheduling"
```

---

## Task 4: APScheduler integration in FastAPI lifespan

**Files:**
- Create: `src/pipeline/scheduler.py`
- Modify: `src/api/app.py:100-117` (lifespan)
- Test: `tests/unit/test_scheduler.py`

**Step 1: Write the failing tests**

Create `tests/unit/test_scheduler.py`:

```python
"""Tests for src.pipeline.scheduler -- APScheduler integration."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.pipeline.scheduler import create_scheduler, run_scheduled_pipeline


class TestCreateScheduler:
    """Verify scheduler creation and job configuration."""

    def test_creates_scheduler_with_jobs(self):
        """create_scheduler() returns a scheduler with 3 tier jobs."""
        from src.core.config import Settings

        settings = Settings(
            scheduler_enabled=True,
            telegram_bot_token="",
            telegram_chat_id="",
            telegram_alerts_enabled=False,
        )
        with patch("src.pipeline.scheduler.get_settings", return_value=settings):
            scheduler = create_scheduler()

        jobs = scheduler.get_jobs()
        assert len(jobs) == 3  # tier1, tier2, tier3
        job_ids = {j.id for j in jobs}
        assert "tier1_hn_reddit" in job_ids
        assert "tier2_rss_gh_hf" in job_ids
        assert "tier3_arxiv" in job_ids

    def test_scheduler_not_created_when_disabled(self):
        """create_scheduler() returns None when scheduler_enabled=False."""
        from src.core.config import Settings

        settings = Settings(
            scheduler_enabled=False,
            telegram_bot_token="",
            telegram_chat_id="",
            telegram_alerts_enabled=False,
        )
        with patch("src.pipeline.scheduler.get_settings", return_value=settings):
            scheduler = create_scheduler()

        assert scheduler is None


class TestRunScheduledPipeline:
    """Verify run_scheduled_pipeline creates session and runs pipeline."""

    @pytest.mark.asyncio
    async def test_creates_session_and_runs_pipeline(self):
        """run_scheduled_pipeline gets a DB session and calls run_pipeline."""
        mock_session = AsyncMock()
        mock_session_factory = AsyncMock()
        mock_session_factory.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_factory.__aexit__ = AsyncMock(return_value=False)

        with (
            patch("src.pipeline.scheduler.get_async_session", return_value=mock_session_factory),
            patch("src.pipeline.scheduler.run_pipeline", new_callable=AsyncMock) as mock_run,
        ):
            await run_scheduled_pipeline(sources=["hackernews", "reddit"])

        mock_run.assert_called_once_with(mock_session, sources=["hackernews", "reddit"])

    @pytest.mark.asyncio
    async def test_catches_exceptions_and_logs(self):
        """run_scheduled_pipeline does not propagate exceptions."""
        mock_session = AsyncMock()
        mock_session_factory = AsyncMock()
        mock_session_factory.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_factory.__aexit__ = AsyncMock(return_value=False)

        with (
            patch("src.pipeline.scheduler.get_async_session", return_value=mock_session_factory),
            patch(
                "src.pipeline.scheduler.run_pipeline",
                new_callable=AsyncMock,
                side_effect=RuntimeError("DB down"),
            ),
        ):
            # Should NOT raise
            await run_scheduled_pipeline(sources=["hackernews"])
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/test_scheduler.py -v`
Expected: FAIL (ModuleNotFoundError: No module named 'src.pipeline.scheduler')

**Step 3: Create `src/pipeline/scheduler.py`**

```python
"""APScheduler integration for per-source pipeline scheduling."""

from __future__ import annotations

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from src.core.config import get_settings
from src.core.database import get_async_session
from src.core.logging import get_logger
from src.pipeline.pipeline import run_pipeline

logger = get_logger(__name__)


async def run_scheduled_pipeline(sources: list[str]) -> None:
    """Run the pipeline for a specific set of sources.

    Creates its own DB session and catches all exceptions
    so that one failed job does not crash the scheduler.
    """
    logger.info("scheduled_pipeline_start", sources=sources)
    try:
        async with get_async_session() as session:
            await run_pipeline(session, sources=sources)
    except Exception as exc:
        logger.error("scheduled_pipeline_failed", sources=sources, error=str(exc))


def create_scheduler() -> AsyncIOScheduler | None:
    """Create and configure the APScheduler instance.

    Returns None if scheduler_enabled is False.
    """
    settings = get_settings()

    if not settings.scheduler_enabled:
        logger.info("scheduler_disabled")
        return None

    scheduler = AsyncIOScheduler()

    # Tier 1: HackerNews + Reddit (every 15 min)
    scheduler.add_job(
        run_scheduled_pipeline,
        IntervalTrigger(minutes=settings.hn_poll_interval_minutes),
        id="tier1_hn_reddit",
        kwargs={"sources": ["hackernews", "reddit"]},
        replace_existing=True,
    )

    # Tier 2: RSS + GitHub + HuggingFace (every 60 min)
    scheduler.add_job(
        run_scheduled_pipeline,
        IntervalTrigger(minutes=settings.rss_poll_interval_minutes),
        id="tier2_rss_gh_hf",
        kwargs={"sources": ["rss", "github", "huggingface"]},
        replace_existing=True,
    )

    # Tier 3: arXiv (daily at configured hour)
    scheduler.add_job(
        run_scheduled_pipeline,
        CronTrigger(hour=settings.arxiv_cron_hour, minute=settings.arxiv_cron_minute),
        id="tier3_arxiv",
        kwargs={"sources": ["arxiv"]},
        replace_existing=True,
    )

    logger.info(
        "scheduler_configured",
        tier1_interval=settings.hn_poll_interval_minutes,
        tier2_interval=settings.rss_poll_interval_minutes,
        tier3_cron=f"{settings.arxiv_cron_hour}:{settings.arxiv_cron_minute:02d}",
    )

    return scheduler
```

**Step 4: Verify `get_async_session` exists in database module**

Check that `src/core/database.py` exposes `get_async_session` as an async context manager. If it doesn't exist, check what session helper is available and adapt `run_scheduled_pipeline` accordingly. The function needs an `AsyncSession` to pass to `run_pipeline`.

Likely the existing code uses `get_session()` as a FastAPI dependency. For the scheduler, we need a standalone session factory. If `get_async_session` doesn't exist, create it:

```python
# In src/core/database.py, add:
from contextlib import asynccontextmanager

@asynccontextmanager
async def get_async_session():
    """Standalone async session context manager (for non-FastAPI use)."""
    async with async_session_factory() as session:
        yield session
```

**Step 5: Run tests to verify they pass**

Run: `pytest tests/unit/test_scheduler.py -v`
Expected: PASS (all 4 tests)

**Step 6: Integrate scheduler into FastAPI lifespan**

Modify `src/api/app.py` lifespan function (lines 100-117):

```python
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan: setup and teardown."""
    setup_logging()

    # Block startup with insecure defaults in production
    settings = get_settings()
    if not settings.debug:
        if settings.jwt_secret == "change-me-in-production":
            raise RuntimeError("JWT_SECRET must be set in production (DEBUG=false)")
        if settings.shared_password == "change-me-in-production":
            raise RuntimeError("SHARED_PASSWORD must be set in production (DEBUG=false)")

    logger.info("starting_application")
    await init_db()

    # Start scheduler if enabled
    from src.pipeline.scheduler import create_scheduler

    scheduler = create_scheduler()
    if scheduler is not None:
        scheduler.start()
        logger.info("scheduler_started")

    yield

    # Shutdown scheduler
    if scheduler is not None:
        scheduler.shutdown(wait=False)
        logger.info("scheduler_stopped")

    logger.info("shutting_down_application")
    await close_db()
```

**Step 7: Run full test suite to verify no regressions**

Run: `pytest tests/unit/ -v --timeout=30`
Expected: ALL PASS

**Step 8: Commit**

```bash
git add src/pipeline/scheduler.py src/api/app.py src/core/database.py tests/unit/test_scheduler.py
git commit -m "feat: APScheduler integration in FastAPI lifespan with 3-tier jobs"
```

---

## Task 5: Reddit OAuth (client_credentials flow)

**Files:**
- Modify: `src/extractors/reddit.py`
- Test: `tests/unit/test_reddit_extractor.py` (add OAuth tests)

**Step 1: Write the failing tests**

Add to `tests/unit/test_reddit_extractor.py`:

```python
class TestRedditOAuth:
    """RedditExtractor with OAuth client_credentials flow."""

    @respx.mock
    async def test_uses_oauth_when_credentials_set(self):
        """When reddit_client_id and reddit_client_secret are set, uses OAuth."""
        # Mock token endpoint
        respx.post("https://www.reddit.com/api/v1/access_token").mock(
            return_value=httpx.Response(200, json={
                "access_token": "test-bearer-token",
                "token_type": "bearer",
                "expires_in": 7200,
            }),
        )
        # Mock OAuth API endpoint
        respx.get("https://oauth.reddit.com/r/MachineLearning/top/.json").mock(
            return_value=httpx.Response(200, json=_reddit_response([
                _make_post("oauth1", "OAuth Post", score=100),
            ])),
        )

        settings = _mock_settings(
            reddit_client_id="test-client-id",
            reddit_client_secret="test-client-secret",
        )
        with patch("src.extractors.reddit.get_settings", return_value=settings):
            extractor = RedditExtractor()
            result = await extractor.extract()

        assert len(result) == 1
        assert result[0].title == "OAuth Post"

    @respx.mock
    async def test_falls_back_to_unauthenticated_when_no_credentials(self):
        """When reddit_client_id is empty, uses unauthenticated API."""
        posts = [_make_post("noauth1", "NoAuth Post", score=50)]
        respx.get(f"{BASE_URL}/r/MachineLearning/top/.json").mock(
            return_value=httpx.Response(200, json=_reddit_response(posts)),
        )

        settings = _mock_settings(reddit_client_id="", reddit_client_secret="")
        with patch("src.extractors.reddit.get_settings", return_value=settings):
            extractor = RedditExtractor()
            result = await extractor.extract()

        assert len(result) == 1

    @respx.mock
    async def test_oauth_token_failure_falls_back(self):
        """When OAuth token request fails, falls back to unauthenticated."""
        respx.post("https://www.reddit.com/api/v1/access_token").mock(
            return_value=httpx.Response(401, text="Unauthorized"),
        )
        # Fallback: unauthenticated endpoint
        posts = [_make_post("fb1", "Fallback Post", score=75)]
        respx.get(f"{BASE_URL}/r/MachineLearning/top/.json").mock(
            return_value=httpx.Response(200, json=_reddit_response(posts)),
        )

        settings = _mock_settings(
            reddit_client_id="bad-id",
            reddit_client_secret="bad-secret",
        )
        with patch("src.extractors.reddit.get_settings", return_value=settings):
            extractor = RedditExtractor()
            result = await extractor.extract()

        assert len(result) == 1
        assert result[0].title == "Fallback Post"
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/test_reddit_extractor.py::TestRedditOAuth -v`
Expected: FAIL (no reddit_client_id attribute on settings / wrong URL being called)

**Step 3: Implement Reddit OAuth in `src/extractors/reddit.py`**

Replace the entire file with the updated version. Key changes:

1. Add `OAUTH_TOKEN_URL` and `OAUTH_BASE_URL` constants
2. Add `_get_oauth_token` method that does `POST /api/v1/access_token` with `client_credentials` grant
3. Modify `extract` to try OAuth first, fall back to unauthenticated
4. Modify `_fetch_subreddit` to accept a `base_url` and optional `auth_headers`

```python
"""Reddit extractor with optional OAuth client_credentials flow.

When REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET are set, uses OAuth for
10x higher rate limits (100 req/min vs 10 req/min).

Falls back to unauthenticated API if OAuth credentials are missing or
token request fails.
"""

from __future__ import annotations

from datetime import UTC, datetime

import httpx

from src.core.config import get_settings
from src.core.logging import get_logger
from src.core.metrics import (
    extractor_duration_seconds,
    extractor_errors_total,
    items_extracted_total,
)
from src.extractors.base import BaseExtractor, ExtractedItem

logger = get_logger(__name__)

BASE_URL = "https://www.reddit.com"
OAUTH_BASE_URL = "https://oauth.reddit.com"
OAUTH_TOKEN_URL = "https://www.reddit.com/api/v1/access_token"


class RedditExtractor(BaseExtractor):
    """Extracts AI-related posts from Reddit subreddits."""

    @property
    def source_name(self) -> str:
        return "reddit"

    async def _get_oauth_token(self, client: httpx.AsyncClient) -> str | None:
        """Request OAuth bearer token using client_credentials grant.

        Returns the access token string, or None on failure.
        """
        settings = get_settings()
        if not settings.reddit_client_id or not settings.reddit_client_secret:
            return None

        try:
            resp = await client.post(
                OAUTH_TOKEN_URL,
                data={"grant_type": "client_credentials"},
                auth=(settings.reddit_client_id, settings.reddit_client_secret),
                headers={"User-Agent": "AI-News-Platform/1.0"},
            )
            resp.raise_for_status()
            token_data = resp.json()
            token = token_data.get("access_token")
            if token:
                logger.info("reddit_oauth_token_acquired")
            return token
        except Exception as exc:
            logger.warning("reddit_oauth_token_failed", error=str(exc))
            return None

    async def extract(self, since_hours: int = 24) -> list[ExtractedItem]:
        """Extract top posts from configured subreddits."""
        settings = get_settings()
        subreddits = settings.reddit_subreddits_list
        limit = settings.reddit_top_limit
        max_items = settings.max_items_per_source

        seen_ids: set[str] = set()
        items: list[ExtractedItem] = []

        with extractor_duration_seconds.labels(source=self.source_name).time():
            async with httpx.AsyncClient(
                timeout=30,
                headers={"User-Agent": "AI-News-Platform/1.0"},
            ) as client:
                # Try OAuth first
                token = await self._get_oauth_token(client)
                if token:
                    api_base = OAUTH_BASE_URL
                    auth_headers = {"Authorization": f"Bearer {token}"}
                else:
                    api_base = BASE_URL
                    auth_headers = {}

                for subreddit in subreddits:
                    try:
                        new_items = await self._fetch_subreddit(
                            client, subreddit, limit, seen_ids,
                            base_url=api_base, extra_headers=auth_headers,
                        )
                        items.extend(new_items)
                    except Exception as exc:
                        logger.warning(
                            "reddit_fetch_failed",
                            subreddit=subreddit,
                            error=str(exc),
                        )
                        continue

        items.sort(key=lambda x: x.score or 0, reverse=True)
        items = items[:max_items]

        items_extracted_total.labels(source=self.source_name).inc(len(items))
        logger.info(
            "extraction_complete",
            source=self.source_name,
            count=len(items),
            subreddits=len(subreddits),
        )

        if not items:
            extractor_errors_total.labels(source=self.source_name).inc()

        return items

    async def _fetch_subreddit(
        self,
        client: httpx.AsyncClient,
        subreddit: str,
        limit: int,
        seen_ids: set[str],
        *,
        base_url: str = BASE_URL,
        extra_headers: dict[str, str] | None = None,
    ) -> list[ExtractedItem]:
        """Fetch top posts from a single subreddit."""
        url = f"{base_url}/r/{subreddit}/top/.json"
        params = {"t": "day", "limit": limit}

        resp = await client.get(url, params=params, headers=extra_headers or {})
        resp.raise_for_status()
        data = resp.json()

        items: list[ExtractedItem] = []
        children = data.get("data", {}).get("children", [])

        for child in children:
            post = child.get("data", {})

            if post.get("stickied", False):
                continue

            post_id = post.get("id", "")
            if not post_id:
                continue

            if post_id in seen_ids:
                continue
            seen_ids.add(post_id)

            is_self = post.get("is_self", False)
            permalink = f"https://www.reddit.com{post.get('permalink', '')}"
            if is_self:
                url = permalink
                text = post.get("selftext", "") or post.get("title", "")
            else:
                url = post.get("url", permalink)
                text = post.get("title", "")

            created_utc = post.get("created_utc", 0)
            try:
                published = datetime.fromtimestamp(created_utc, tz=UTC)
            except (ValueError, OSError):
                published = datetime.now(tz=UTC)

            flair = post.get("link_flair_text", "") or ""
            domain = post.get("domain", "") or ""

            items.append(
                ExtractedItem(
                    title=post.get("title", ""),
                    source=self.source_name,
                    url=url,
                    text=text,
                    author=post.get("author", "unknown"),
                    published_at=published,
                    score=post.get("score", 0),
                    metadata={
                        "subreddit": subreddit,
                        "post_id": post_id,
                        "num_comments": post.get("num_comments", 0),
                        "upvote_ratio": post.get("upvote_ratio", 0.0),
                        "is_self": is_self,
                        "flair": flair,
                        "domain": domain,
                    },
                )
            )

        return items
```

**Step 4: Run all Reddit tests**

Run: `pytest tests/unit/test_reddit_extractor.py -v`
Expected: ALL PASS (existing tests use empty credentials, so they use unauthenticated path)

**Step 5: Commit**

```bash
git add src/extractors/reddit.py tests/unit/test_reddit_extractor.py
git commit -m "feat: Reddit OAuth client_credentials flow with fallback"
```

---

## Task 6: RSS ETags (conditional requests)

**Files:**
- Modify: `src/extractors/rss.py`
- Test: `tests/unit/test_rss_extractor.py` (add ETag tests)

**Step 1: Write the failing tests**

Add to `tests/unit/test_rss_extractor.py`:

```python
class TestRSSETags:
    """RSSExtractor conditional request behavior with ETags."""

    @respx.mock
    async def test_sends_etag_on_second_request(self):
        """After a response with ETag header, next request sends If-None-Match."""
        from src.extractors.rss import RSSExtractor

        entries = [_make_entry("Post A", "https://openai.com/blog/a")]
        feed_xml = _make_feed(entries)

        # First request: returns ETag in response
        respx.get(FEED_URL_OPENAI).mock(
            return_value=httpx.Response(
                200, text=feed_xml, headers={"ETag": '"abc123"'}
            ),
        )

        settings = _mock_settings()
        with patch("src.extractors.rss.get_settings", return_value=settings):
            extractor = RSSExtractor()
            result1 = await extractor.extract(since_hours=48)

        assert len(result1) == 1

        # Second request: should send If-None-Match, server returns 304
        route = respx.get(FEED_URL_OPENAI).mock(
            return_value=httpx.Response(304),
        )

        with patch("src.extractors.rss.get_settings", return_value=settings):
            result2 = await extractor.extract(since_hours=48)

        assert result2 == []
        # Verify If-None-Match was sent
        request = route.calls.last.request
        assert request.headers.get("if-none-match") == '"abc123"'

    @respx.mock
    async def test_304_response_returns_empty(self):
        """HTTP 304 Not Modified returns empty list (feed unchanged)."""
        from src.extractors.rss import RSSExtractor

        # Pre-seed the cache with an ETag for this feed
        extractor = RSSExtractor()
        extractor._etag_cache[FEED_URL_OPENAI] = {"etag": '"cached"'}

        respx.get(FEED_URL_OPENAI).mock(
            return_value=httpx.Response(304),
        )

        settings = _mock_settings()
        with patch("src.extractors.rss.get_settings", return_value=settings):
            result = await extractor.extract(since_hours=48)

        assert result == []
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/test_rss_extractor.py::TestRSSETags -v`
Expected: FAIL (no _etag_cache attribute, no conditional request logic)

**Step 3: Add ETag support to `src/extractors/rss.py`**

Key changes to `RSSExtractor`:

1. Add `_etag_cache: dict[str, dict[str, str]]` as instance variable in `__init__`
2. In `_fetch_feed`, add `If-None-Match` / `If-Modified-Since` headers from cache
3. On 304 response, return empty list
4. On 200 response, store `ETag` / `Last-Modified` headers in cache

Add `__init__` to the class:

```python
def __init__(self) -> None:
    self._etag_cache: dict[str, dict[str, str]] = {}
```

Modify `_fetch_feed`:

```python
async def _fetch_feed(
    self,
    client: httpx.AsyncClient,
    feed_url: str,
    cutoff: datetime,
    seen_urls: set[str],
) -> list[ExtractedItem]:
    """Fetch and parse a single RSS/Atom feed with conditional request support."""
    # Build conditional request headers from cache
    headers: dict[str, str] = {}
    cached = self._etag_cache.get(feed_url, {})
    if cached.get("etag"):
        headers["If-None-Match"] = cached["etag"]
    if cached.get("last_modified"):
        headers["If-Modified-Since"] = cached["last_modified"]

    resp = await client.get(feed_url, headers=headers)

    # 304 Not Modified: feed unchanged since last fetch
    if resp.status_code == 304:
        logger.info("rss_feed_unchanged", feed_url=feed_url)
        return []

    resp.raise_for_status()

    # Store conditional request headers for next fetch
    new_cache: dict[str, str] = {}
    if resp.headers.get("etag"):
        new_cache["etag"] = resp.headers["etag"]
    if resp.headers.get("last-modified"):
        new_cache["last_modified"] = resp.headers["last-modified"]
    if new_cache:
        self._etag_cache[feed_url] = new_cache

    feed = feedparser.parse(resp.text)
    # ... rest of parsing unchanged ...
```

**Step 4: Run all RSS tests**

Run: `pytest tests/unit/test_rss_extractor.py -v`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add src/extractors/rss.py tests/unit/test_rss_extractor.py
git commit -m "feat: RSS ETags — conditional requests skip unchanged feeds"
```

---

## Task 7: HuggingFace daily_papers endpoint

**Files:**
- Modify: `src/extractors/huggingface.py`
- Test: `tests/unit/test_huggingface_extractor.py` (add daily_papers tests)

**Step 1: Write the failing tests**

Add to `tests/unit/test_huggingface_extractor.py`:

```python
DAILY_PAPERS_URL = "https://huggingface.co/api/daily_papers"


def _make_daily_paper(
    title: str = "Attention Is All You Need v2",
    paper_id: str = "2401.12345",
    authors: list[str] | None = None,
    upvotes: int = 42,
    published_at: str | None = None,
) -> dict:
    if authors is None:
        authors = ["Author A", "Author B"]
    if published_at is None:
        published_at = _recent_iso()
    return {
        "paper": {
            "id": paper_id,
            "title": title,
            "authors": [{"name": a} for a in authors],
            "publishedAt": published_at,
            "upvotes": upvotes,
        },
    }


class TestDailyPapers:
    """HuggingFaceExtractor fetches daily_papers alongside trending models."""

    @respx.mock
    async def test_daily_papers_included_in_results(self):
        """daily_papers items appear in extraction results."""
        # Mock trending models (empty)
        respx.get(API_URL).mock(return_value=httpx.Response(200, json=[]))
        # Mock daily_papers
        papers = [_make_daily_paper("Cool Paper", "2401.00001", upvotes=50)]
        respx.get(DAILY_PAPERS_URL).mock(
            return_value=httpx.Response(200, json=papers),
        )

        with patch("src.extractors.huggingface.get_settings", return_value=_mock_settings()):
            result = await HuggingFaceExtractor().extract()

        assert len(result) == 1
        assert result[0].title == "Cool Paper"
        assert result[0].url == "https://arxiv.org/abs/2401.00001"
        assert result[0].source == "huggingface"

    @respx.mock
    async def test_daily_papers_deduped_with_models(self):
        """Papers with same URL as a trending model are deduplicated."""
        # Model with URL that matches a paper
        models = [_make_model("org/model-a", downloads=5000)]
        respx.get(API_URL).mock(return_value=httpx.Response(200, json=models))

        papers = [_make_daily_paper("Same URL Paper", "2401.00001")]
        respx.get(DAILY_PAPERS_URL).mock(
            return_value=httpx.Response(200, json=papers),
        )

        with patch("src.extractors.huggingface.get_settings", return_value=_mock_settings()):
            result = await HuggingFaceExtractor().extract()

        # Should have model + paper (different URLs, no dedup)
        urls = {item.url for item in result}
        assert "https://huggingface.co/org/model-a" in urls
        assert "https://arxiv.org/abs/2401.00001" in urls

    @respx.mock
    async def test_daily_papers_api_failure_still_returns_models(self):
        """If daily_papers API fails, trending models are still returned."""
        models = [_make_model("org/model-b", downloads=3000)]
        respx.get(API_URL).mock(return_value=httpx.Response(200, json=models))
        respx.get(DAILY_PAPERS_URL).mock(
            return_value=httpx.Response(500, text="Server Error"),
        )

        with patch("src.extractors.huggingface.get_settings", return_value=_mock_settings()):
            result = await HuggingFaceExtractor().extract()

        assert len(result) == 1
        assert result[0].title == "org/model-b"

    @respx.mock
    async def test_daily_papers_author_from_first_author(self):
        """Paper author should come from the first author in the list."""
        papers = [_make_daily_paper(
            "Multi Author Paper", "2401.99999",
            authors=["Alice", "Bob", "Charlie"],
        )]
        respx.get(API_URL).mock(return_value=httpx.Response(200, json=[]))
        respx.get(DAILY_PAPERS_URL).mock(
            return_value=httpx.Response(200, json=papers),
        )

        with patch("src.extractors.huggingface.get_settings", return_value=_mock_settings()):
            result = await HuggingFaceExtractor().extract()

        assert result[0].author == "Alice"
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/test_huggingface_extractor.py::TestDailyPapers -v`
Expected: FAIL (no DAILY_PAPERS_URL endpoint being fetched)

**Step 3: Add daily_papers to HuggingFaceExtractor**

Add a constant at the top of `src/extractors/huggingface.py`:

```python
DAILY_PAPERS_URL = "https://huggingface.co/api/daily_papers"
```

Add a new method `_fetch_daily_papers` and call it from `extract()`:

```python
async def _fetch_daily_papers(
    self, client: httpx.AsyncClient, seen_urls: set[str]
) -> list[ExtractedItem]:
    """Fetch curated daily papers from HuggingFace."""
    items: list[ExtractedItem] = []
    try:
        resp = await client.get(DAILY_PAPERS_URL)
        resp.raise_for_status()
        papers = resp.json()

        for entry in papers:
            paper = entry.get("paper", {})
            paper_id = paper.get("id", "")
            if not paper_id:
                continue

            url = f"https://arxiv.org/abs/{paper_id}"
            if url in seen_urls:
                continue
            seen_urls.add(url)

            authors = paper.get("authors", [])
            author = authors[0].get("name", "unknown") if authors else "unknown"

            published_str = paper.get("publishedAt", "")
            try:
                published = datetime.fromisoformat(
                    published_str.replace("Z", "+00:00")
                )
            except (ValueError, AttributeError):
                published = datetime.now(tz=UTC)

            items.append(
                ExtractedItem(
                    title=paper.get("title", paper_id),
                    source=self.source_name,
                    url=url,
                    text=paper.get("title", ""),
                    author=author,
                    published_at=published,
                    score=paper.get("upvotes", 0),
                    metadata={
                        "paper_id": paper_id,
                        "upvotes": paper.get("upvotes", 0),
                        "type": "daily_paper",
                    },
                )
            )
    except Exception as exc:
        logger.warning("huggingface_daily_papers_failed", error=str(exc))

    return items
```

In `extract()`, after the trending models fetch, call `_fetch_daily_papers`:

```python
# After the existing try block for trending models:
                    # Also fetch daily papers
                    daily_items = await self._fetch_daily_papers(client, seen_urls)
                    items.extend(daily_items)
```

The `seen_urls` set ensures dedup between trending models and daily papers.

**Step 4: Run all HuggingFace tests**

Run: `pytest tests/unit/test_huggingface_extractor.py -v`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add src/extractors/huggingface.py tests/unit/test_huggingface_extractor.py
git commit -m "feat: HuggingFace daily_papers endpoint integration"
```

---

## Task 8: Error handling with circuit breaker (metrics + structured logging)

**Files:**
- Modify: `src/pipeline/scheduler.py` (add per-job error tracking)
- Create: `src/pipeline/circuit_breaker.py`
- Test: `tests/unit/test_circuit_breaker.py`

**Step 1: Write the failing tests**

Create `tests/unit/test_circuit_breaker.py`:

```python
"""Tests for src.pipeline.circuit_breaker."""

from __future__ import annotations

import time
from unittest.mock import patch

from src.pipeline.circuit_breaker import CircuitBreaker


class TestCircuitBreaker:
    """CircuitBreaker tracks failures and disables sources."""

    def test_initial_state_is_closed(self):
        """New circuit breaker starts in closed (healthy) state."""
        cb = CircuitBreaker(threshold=3, cooldown_seconds=60)
        assert cb.is_open("hackernews") is False

    def test_opens_after_threshold_failures(self):
        """After threshold consecutive failures, circuit opens."""
        cb = CircuitBreaker(threshold=3, cooldown_seconds=60)
        cb.record_failure("hackernews")
        cb.record_failure("hackernews")
        assert cb.is_open("hackernews") is False
        cb.record_failure("hackernews")
        assert cb.is_open("hackernews") is True

    def test_success_resets_failure_count(self):
        """A success resets the consecutive failure counter."""
        cb = CircuitBreaker(threshold=3, cooldown_seconds=60)
        cb.record_failure("hackernews")
        cb.record_failure("hackernews")
        cb.record_success("hackernews")
        cb.record_failure("hackernews")
        assert cb.is_open("hackernews") is False  # only 1 failure after reset

    def test_circuit_closes_after_cooldown(self):
        """After cooldown period, circuit transitions back to closed."""
        cb = CircuitBreaker(threshold=3, cooldown_seconds=1)
        cb.record_failure("reddit")
        cb.record_failure("reddit")
        cb.record_failure("reddit")
        assert cb.is_open("reddit") is True

        # Wait for cooldown
        time.sleep(1.1)
        assert cb.is_open("reddit") is False

    def test_independent_per_source(self):
        """Each source has independent failure tracking."""
        cb = CircuitBreaker(threshold=2, cooldown_seconds=60)
        cb.record_failure("hackernews")
        cb.record_failure("hackernews")
        assert cb.is_open("hackernews") is True
        assert cb.is_open("reddit") is False
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/test_circuit_breaker.py -v`
Expected: FAIL (ModuleNotFoundError)

**Step 3: Create `src/pipeline/circuit_breaker.py`**

```python
"""Simple in-memory circuit breaker for pipeline sources."""

from __future__ import annotations

import time

from src.core.logging import get_logger

logger = get_logger(__name__)


class CircuitBreaker:
    """Tracks consecutive failures per source and disables after threshold.

    After ``threshold`` consecutive failures, the circuit opens (source
    disabled) for ``cooldown_seconds``. After the cooldown, the circuit
    closes and the source is retried.

    State resets on process restart (acceptable for this use case).
    """

    def __init__(self, threshold: int = 3, cooldown_seconds: int = 3600) -> None:
        self._threshold = threshold
        self._cooldown = cooldown_seconds
        self._failures: dict[str, int] = {}
        self._opened_at: dict[str, float] = {}

    def record_failure(self, source: str) -> None:
        """Record a failure for a source."""
        self._failures[source] = self._failures.get(source, 0) + 1
        if self._failures[source] >= self._threshold:
            self._opened_at[source] = time.monotonic()
            logger.warning(
                "circuit_breaker_opened",
                source=source,
                failures=self._failures[source],
                cooldown_seconds=self._cooldown,
            )

    def record_success(self, source: str) -> None:
        """Record a success, resetting the failure counter."""
        self._failures.pop(source, None)
        self._opened_at.pop(source, None)

    def is_open(self, source: str) -> bool:
        """Check if the circuit is open (source should be skipped)."""
        if self._failures.get(source, 0) < self._threshold:
            return False

        opened_at = self._opened_at.get(source)
        if opened_at is None:
            return False

        # Check if cooldown has elapsed
        if time.monotonic() - opened_at >= self._cooldown:
            # Reset — allow retry
            self._failures.pop(source, None)
            self._opened_at.pop(source, None)
            logger.info("circuit_breaker_reset", source=source)
            return False

        return True
```

**Step 4: Run tests**

Run: `pytest tests/unit/test_circuit_breaker.py -v`
Expected: ALL PASS (5 tests)

**Step 5: Integrate circuit breaker into scheduler**

Update `src/pipeline/scheduler.py` to use the circuit breaker. Add a module-level instance and check before running each source group:

```python
from src.pipeline.circuit_breaker import CircuitBreaker

_circuit_breaker = CircuitBreaker(threshold=3, cooldown_seconds=3600)


async def run_scheduled_pipeline(sources: list[str]) -> None:
    """Run the pipeline for a specific set of sources."""
    # Filter out sources with open circuits
    active_sources = [s for s in sources if not _circuit_breaker.is_open(s)]
    if not active_sources:
        logger.info("scheduled_pipeline_all_sources_circuit_open", sources=sources)
        return

    logger.info("scheduled_pipeline_start", sources=active_sources)
    try:
        async with get_async_session() as session:
            result = await run_pipeline(session, sources=active_sources)
            # Record success for all active sources
            if result:
                for source in active_sources:
                    _circuit_breaker.record_success(source)
    except Exception as exc:
        logger.error("scheduled_pipeline_failed", sources=active_sources, error=str(exc))
        for source in active_sources:
            _circuit_breaker.record_failure(source)
```

**Step 6: Run all tests**

Run: `pytest tests/unit/test_scheduler.py tests/unit/test_circuit_breaker.py -v`
Expected: ALL PASS

**Step 7: Commit**

```bash
git add src/pipeline/circuit_breaker.py src/pipeline/scheduler.py tests/unit/test_circuit_breaker.py
git commit -m "feat: circuit breaker — disable sources after 3 consecutive failures"
```

---

## Task 9: Update docs and final verification

**Files:**
- Modify: `AGENTS.md` (update architecture, file map, scheduler section)
- Modify: `docs/plans/ideas-backlog.md` (mark item done)
- Modify: `.env` (ensure all new settings present — already done in Task 2)

**Step 1: Update AGENTS.md**

Add to the architecture section:

- New file: `src/pipeline/scheduler.py` — APScheduler integration, 3-tier job configuration
- New file: `src/pipeline/circuit_breaker.py` — Per-source circuit breaker (3 failures → 1h cooldown)
- Modified: `src/pipeline/pipeline.py` — `run_pipeline(session, sources=None)` accepts optional source filter
- Modified: `src/extractors/reddit.py` — OAuth client_credentials flow with fallback
- Modified: `src/extractors/rss.py` — ETag/If-Modified-Since conditional requests
- Modified: `src/extractors/huggingface.py` — daily_papers endpoint alongside trending models
- Modified: `src/api/app.py` — Scheduler starts/stops in lifespan
- Modified: `src/core/config.py` — Scheduler intervals, Reddit OAuth settings

Add scheduler tiers table:

| Tier | Interval | Sources |
|------|----------|---------|
| 1 | 15 min | HackerNews, Reddit |
| 2 | 60 min | RSS, GitHub, HuggingFace |
| 3 | Daily 01:30 UTC | arXiv |

**Step 2: Update backlog**

In `docs/plans/ideas-backlog.md`, move the pipeline scheduling item from "In Progress" to "Done":

```markdown
- [x] **Pipeline scheduling + live feeds** — Done (APScheduler in FastAPI, per-source intervals, Reddit OAuth, RSS ETags, HF daily_papers)
```

**Step 3: Run full test suite**

Run: `pytest tests/unit/ -v --timeout=30`
Expected: ALL PASS

**Step 4: Commit**

```bash
git add AGENTS.md docs/plans/ideas-backlog.md
git commit -m "docs: update AGENTS.md and backlog for pipeline scheduling milestone"
```

---

## Summary of All Tasks

| # | Task | New/Modified Files | Tests |
|---|------|--------------------|-------|
| 1 | APScheduler dependency | `pyproject.toml` | import check |
| 2 | Scheduler config settings | `config.py`, `.env`, `test_config.py` | 3 tests |
| 3 | Pipeline sources filter | `pipeline.py`, `test_pipeline.py` | 5 tests |
| 4 | APScheduler in lifespan | `scheduler.py`, `app.py`, `database.py`, `test_scheduler.py` | 4 tests |
| 5 | Reddit OAuth | `reddit.py`, `test_reddit_extractor.py` | 3 tests |
| 6 | RSS ETags | `rss.py`, `test_rss_extractor.py` | 2 tests |
| 7 | HF daily_papers | `huggingface.py`, `test_huggingface_extractor.py` | 4 tests |
| 8 | Circuit breaker | `circuit_breaker.py`, `scheduler.py`, `test_circuit_breaker.py` | 5 tests |
| 9 | Docs + final verification | `AGENTS.md`, `ideas-backlog.md` | full suite |
