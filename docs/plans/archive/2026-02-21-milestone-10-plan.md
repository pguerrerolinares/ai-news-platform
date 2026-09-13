# M10 Integration Testing Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add 27 integration tests that validate real DB interactions against PostgreSQL+pgvector.

**Architecture:** Tests use a real `ainews_test` PostgreSQL database with pgvector extension. Session-scoped engine creates tables once; function-scoped sessions use savepoint isolation (rollback after each test). External APIs (OpenAI, extractors, Telegram) are mocked at service level.

**Tech Stack:** pytest, pytest-asyncio, SQLAlchemy async, asyncpg, pgvector, httpx (ASGI), respx (not needed — service mocks only)

---

## Context for Implementer

### Project layout

```
src/
  core/config.py          # Settings (pydantic-settings, @lru_cache get_settings())
  core/models.py          # NewsItem, DailyBriefing, ItemEmbedding (pgvector Vector(1536))
  core/database.py        # get_session() async generator (used as Depends in routes)
  pipeline/pipeline.py    # run_pipeline(), _store_classified_items(), _save_briefing(), _embed_new_items()
  api/app.py              # FastAPI app (module-level get_settings() calls)
  api/auth.py             # create_access_token(), require_auth() (JWT via python-jose)
  api/routes/items.py     # GET /api/items, /api/items/count, /api/items/today
  api/routes/search.py    # GET /api/search (plainto_tsquery + ts_rank)
  api/routes/briefings.py # GET /api/briefings, /api/briefings/{date}
  api/routes/chat.py      # POST /api/chat (SSE stream)
  api/routes/auth.py      # POST /api/auth/token
  rag/embeddings.py       # EmbeddingService (OpenAI text-embedding-3-small)
  rag/retriever.py        # Retriever (pgvector cosine_distance)
  rag/chat.py             # ChatService (RAG + LLM stream)
tests/
  conftest.py             # Parent fixtures (settings, db_engine, db_session, client)
  factories.py            # make_extracted_item(), make_classified_item()
  integration/            # NEW — all integration tests go here
```

### Key patterns

- **Auth**: Shared password → JWT. Routes use `Depends(require_auth)`. Default jwt_secret = `"change-me-in-production"` (works in debug=True mode).
- **Session**: Routes use `Depends(get_session)` from `src.core.database`. Integration tests override this dependency to inject the test session.
- **Pipeline storage**: `_store_classified_items(session, items)` uses `insert().on_conflict_do_nothing(index_elements=["content_hash"])` and commits every 25 items.
- **Briefing upsert**: `_save_briefing()` checks for existing row, accumulates if found, creates if not.
- **Content hash**: `ExtractedItem.content_hash` is a SHA256 of `title + url` — different title/url = different hash.
- **Embedding**: `_embed_new_items(session, embed_service)` finds items without embeddings, calls `embed_service.embed_batch()`, stores in `item_embeddings`.
- **Retriever**: `Retriever(embedding_service).retrieve(session, query)` embeds query, does `ORDER BY cosine_distance(embedding, query_vec)`.

### Savepoint isolation pattern

Integration tests need code like `_store_classified_items` to call `session.commit()` normally, but the data must be rolled back after the test. The solution is SQLAlchemy's nested transaction pattern:

1. Open a connection and begin an outer transaction
2. Start a SAVEPOINT (nested transaction)
3. Give the session to the test
4. When test code calls `session.commit()`, it commits the SAVEPOINT
5. An event listener immediately starts a new SAVEPOINT
6. After the test, rollback the outer transaction → undoes everything

### Prerequisites

Local dev: the `ainews_test` database must exist:
```bash
docker exec -it $(docker ps -qf "ancestor=pgvector/pgvector:pg16") \
  psql -U ainews -c "CREATE DATABASE ainews_test" 2>/dev/null || true
```

CI: already configured (`POSTGRES_DB: ainews_test` in ci.yml).

---

## Task 1: Infrastructure — conftest & smoke test

**Files:**
- Create: `tests/integration/__init__.py`
- Create: `tests/integration/conftest.py`
- Create: `tests/integration/test_pipeline.py` (smoke test only — full tests in Task 2)

### Step 1: Create `tests/integration/__init__.py`

```python
```

(Empty file — just marks the directory as a Python package.)

### Step 2: Create `tests/integration/conftest.py`

```python
"""Integration test fixtures — real PostgreSQL with savepoint isolation."""

from __future__ import annotations

import os
from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine

from src.core.models import Base, DailyBriefing, ItemEmbedding, NewsItem

# ---------------------------------------------------------------------------
# Environment — must run BEFORE any application import that calls get_settings()
# ---------------------------------------------------------------------------
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://ainews:ainews@localhost:5432/ainews_test",
)
os.environ.setdefault(
    "DATABASE_URL_SYNC",
    "postgresql://ainews:ainews@localhost:5432/ainews_test",
)
os.environ["TESTING"] = "1"
os.environ["DEBUG"] = "true"
os.environ["TELEGRAM_BOT_TOKEN"] = ""
os.environ["TELEGRAM_CHAT_ID"] = ""
os.environ["TELEGRAM_ALERTS_ENABLED"] = "false"

from src.core.config import get_settings  # noqa: E402 — must be after env setup

# Clear cached settings so they pick up test DB URL
get_settings.cache_clear()


# ---------------------------------------------------------------------------
# Session-scoped: engine + table creation (once per test session)
# ---------------------------------------------------------------------------
@pytest.fixture(scope="session")
async def integration_engine() -> AsyncGenerator[AsyncEngine, None]:
    """Create engine, install pgvector extension, and create all tables."""
    settings = get_settings()
    engine = create_async_engine(settings.database_url, pool_size=5, max_overflow=0)

    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


# ---------------------------------------------------------------------------
# Function-scoped: savepoint-isolated session (rolled back after each test)
# ---------------------------------------------------------------------------
@pytest.fixture()
async def db_session(integration_engine: AsyncEngine) -> AsyncGenerator[AsyncSession, None]:
    """Yield a session inside a transaction that is always rolled back.

    Uses the nested-transaction (SAVEPOINT) pattern so that code under test
    can call ``session.commit()`` normally — each commit releases a savepoint,
    and the event listener immediately starts a new one.  After the test the
    outer transaction is rolled back, undoing all writes.
    """
    conn = await integration_engine.connect()
    trans = await conn.begin()
    await conn.begin_nested()

    session = AsyncSession(bind=conn, expire_on_commit=False)

    @event.listens_for(session.sync_session, "after_transaction_end")
    def _restart_savepoint(db_session, transaction):  # noqa: ANN001, ARG001
        if conn.closed:
            return
        if not conn.in_nested_transaction():
            if conn.sync_connection:
                conn.sync_connection.begin_nested()

    yield session

    await session.close()
    await trans.rollback()
    await conn.close()


# ---------------------------------------------------------------------------
# FastAPI test client with session override
# ---------------------------------------------------------------------------
@pytest.fixture()
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """ASGI client that injects the test session into all route handlers."""
    from src.api.app import app
    from src.core.database import get_session

    async def _override_session() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    app.dependency_overrides[get_session] = _override_session

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac

    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Auth helper
# ---------------------------------------------------------------------------
@pytest.fixture()
def auth_headers() -> dict[str, str]:
    """Return Authorization headers with a valid JWT."""
    from src.api.auth import create_access_token

    token = create_access_token(subject="test-user")
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# Seed helpers
# ---------------------------------------------------------------------------
async def seed_news_item(session: AsyncSession, **overrides) -> NewsItem:
    """Insert a single NewsItem and flush. Returns the ORM instance."""
    defaults: dict = {
        "title": "Test AI Breakthrough",
        "source": "hackernews",
        "topic": "modelos",
        "url": f"https://example.com/{uuid4().hex[:8]}",
        "content_hash": uuid4().hex,
        "full_text": "Article about AI and machine learning advances.",
        "author": "testuser",
        "published_at": datetime.now(tz=UTC),
        "score": 100,
        "relevance_score": 0.9,
        "priority": 2,
        "trending": False,
    }
    defaults.update(overrides)
    item = NewsItem(**defaults)
    session.add(item)
    await session.flush()
    return item


async def seed_briefing(session: AsyncSession, **overrides) -> DailyBriefing:
    """Insert a DailyBriefing and flush."""
    defaults: dict = {
        "date": datetime.now(tz=UTC).date(),
        "total_items": 10,
        "items_extracted": 20,
        "items_after_dedup": 15,
        "items_filtered": 10,
        "trending_count": 2,
        "duration_seconds": 5.5,
        "sources_used": {"sources": ["hackernews", "arxiv"]},
    }
    defaults.update(overrides)
    briefing = DailyBriefing(**defaults)
    session.add(briefing)
    await session.flush()
    return briefing


async def seed_embedding(
    session: AsyncSession,
    item: NewsItem,
    vector: list[float] | None = None,
    model: str = "text-embedding-3-small",
) -> ItemEmbedding:
    """Insert an ItemEmbedding for the given NewsItem."""
    emb = ItemEmbedding(
        item_id=item.id,
        model=model,
        embedding=vector or [0.1] * 1536,
    )
    session.add(emb)
    await session.flush()
    return emb
```

### Step 3: Write a smoke test

Add to `tests/integration/test_pipeline.py`:

```python
"""Integration tests for the pipeline → DB interaction."""

from __future__ import annotations

import pytest
from sqlalchemy import func, select

from src.core.models import NewsItem
from tests.integration.conftest import seed_news_item

pytestmark = pytest.mark.integration


class TestSmoke:
    async def test_db_connection_works(self, db_session):
        """Verify we can connect to the test database."""
        result = await db_session.execute(select(func.count(NewsItem.id)))
        assert result.scalar_one() == 0  # empty after rollback
```

### Step 4: Run the smoke test

```bash
.venv/bin/pytest tests/integration/test_pipeline.py -v --timeout=60
```

Expected: 1 passed.

### Step 5: Commit

```bash
git add tests/integration/
git commit -m "test: M10 integration test infrastructure — conftest + smoke test [M10]"
```

---

## Task 2: Pipeline Tests (7 tests)

**Files:**
- Modify: `tests/integration/test_pipeline.py`

### Step 1: Write all 7 pipeline tests

Replace the file contents with the full suite:

```python
"""Integration tests for the pipeline → DB interaction."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import func, select

from src.classifiers.base import ClassifiedItem
from src.core.models import DailyBriefing, ItemEmbedding, NewsItem
from src.pipeline.pipeline import (
    _embed_new_items,
    _save_briefing,
    _store_classified_items,
)
from src.rag.embeddings import EmbeddingService
from tests.factories import make_classified_item, make_extracted_item
from tests.integration.conftest import seed_news_item

pytestmark = pytest.mark.integration


class TestStoreClassifiedItems:
    """Tests for _store_classified_items against real PostgreSQL."""

    async def test_stores_items_in_db(self, db_session):
        """Classified items are written as NewsItem rows."""
        items = [
            make_classified_item(
                title=f"Article {i}",
                url=f"https://example.com/store-{i}",
            )
            for i in range(5)
        ]

        count = await _store_classified_items(db_session, items)

        assert count == 5
        result = await db_session.execute(select(func.count(NewsItem.id)))
        assert result.scalar_one() == 5

    async def test_dedup_by_content_hash(self, db_session):
        """Duplicate content_hash is silently skipped (ON CONFLICT DO NOTHING)."""
        item = make_classified_item(title="Same Title", url="https://example.com/same")
        # Insert twice — same content_hash both times
        await _store_classified_items(db_session, [item])
        count2 = await _store_classified_items(db_session, [item])

        assert count2 == 0
        result = await db_session.execute(select(func.count(NewsItem.id)))
        assert result.scalar_one() == 1

    async def test_batch_commit(self, db_session):
        """30 items (> BATCH_COMMIT_SIZE=25) are all stored across 2 batches."""
        items = [
            make_classified_item(
                title=f"Batch {i}",
                url=f"https://example.com/batch-{i}",
            )
            for i in range(30)
        ]

        count = await _store_classified_items(db_session, items)

        assert count == 30
        result = await db_session.execute(select(func.count(NewsItem.id)))
        assert result.scalar_one() == 30

    async def test_stores_correct_fields(self, db_session):
        """All ClassifiedItem fields map correctly to NewsItem columns."""
        item = make_classified_item(
            title="Field Test",
            url="https://example.com/fields",
            topic="herramientas",
        )
        item.relevance_score = 0.88
        item.priority = 3
        item.trending = True
        item.summary = "Test summary"
        item.dev_value_score = 0.77

        await _store_classified_items(db_session, [item])

        result = await db_session.execute(select(NewsItem))
        row = result.scalar_one()

        assert row.title == "Field Test"
        assert row.source == "hackernews"
        assert row.topic == "herramientas"
        assert row.relevance_score == pytest.approx(0.88)
        assert row.priority == 3
        assert row.trending is True
        assert row.summary == "Test summary"
        assert row.dev_value_score == pytest.approx(0.77)
        assert row.content_hash is not None
        assert row.url == "https://example.com/fields"


class TestSaveBriefing:
    """Tests for _save_briefing against real PostgreSQL."""

    async def test_briefing_created(self, db_session):
        """A new DailyBriefing row is created with correct stats."""
        await _save_briefing(
            db_session,
            items_extracted=20,
            items_after_dedup=15,
            items_stored=10,
            sources_used=["hackernews", "arxiv"],
            duration_seconds=3.5,
            trending_count=2,
        )

        today = datetime.now(tz=UTC).date()
        result = await db_session.execute(
            select(DailyBriefing).where(DailyBriefing.date == today)
        )
        briefing = result.scalar_one()

        assert briefing.items_extracted == 20
        assert briefing.items_after_dedup == 15
        assert briefing.total_items == 10
        assert briefing.trending_count == 2
        assert briefing.duration_seconds == pytest.approx(3.5)
        assert briefing.sources_used == {"sources": ["hackernews", "arxiv"]}

    async def test_briefing_accumulates(self, db_session):
        """Running twice in the same day accumulates stats, not replaces."""
        await _save_briefing(
            db_session,
            items_extracted=10,
            items_after_dedup=8,
            items_stored=5,
            sources_used=["hackernews"],
            duration_seconds=2.0,
            trending_count=1,
        )
        await _save_briefing(
            db_session,
            items_extracted=6,
            items_after_dedup=4,
            items_stored=3,
            sources_used=["arxiv"],
            duration_seconds=1.5,
            trending_count=0,
        )

        today = datetime.now(tz=UTC).date()
        result = await db_session.execute(
            select(DailyBriefing).where(DailyBriefing.date == today)
        )
        briefing = result.scalar_one()

        assert briefing.items_extracted == 16  # 10 + 6
        assert briefing.total_items == 8  # 5 + 3
        assert briefing.trending_count == 1  # 1 + 0
        assert briefing.duration_seconds == pytest.approx(3.5)  # 2.0 + 1.5

    async def test_empty_pipeline(self, db_session):
        """Briefing with 0 items stored is valid."""
        await _save_briefing(
            db_session,
            items_extracted=0,
            items_after_dedup=0,
            items_stored=0,
            sources_used=[],
            duration_seconds=0.1,
        )

        today = datetime.now(tz=UTC).date()
        result = await db_session.execute(
            select(DailyBriefing).where(DailyBriefing.date == today)
        )
        briefing = result.scalar_one()
        assert briefing.total_items == 0


class TestEmbedNewItems:
    """Test _embed_new_items writes embeddings to item_embeddings table."""

    async def test_embeds_items_without_embeddings(self, db_session):
        """Items without embeddings get new rows in item_embeddings."""
        # Seed 3 items
        items = []
        for i in range(3):
            item = await seed_news_item(
                db_session,
                title=f"Embed {i}",
                url=f"https://example.com/embed-{i}",
            )
            items.append(item)

        # Mock embedding service
        mock_embed = AsyncMock(spec=EmbeddingService)
        mock_embed.prepare_text = EmbeddingService.prepare_text
        mock_embed.embed_batch.return_value = [[0.5] * 1536] * 3

        with patch("src.pipeline.pipeline.get_settings") as mock_settings:
            mock_settings.return_value.embedding_model = "text-embedding-3-small"
            count = await _embed_new_items(db_session, embed_service=mock_embed)

        assert count == 3
        result = await db_session.execute(select(func.count(ItemEmbedding.item_id)))
        assert result.scalar_one() == 3
```

### Step 2: Run pipeline tests

```bash
.venv/bin/pytest tests/integration/test_pipeline.py -v --timeout=60
```

Expected: 7 passed.

### Step 3: Commit

```bash
git add tests/integration/test_pipeline.py
git commit -m "test: M10 pipeline integration tests — store, briefing, embed [M10]"
```

---

## Task 3: API Items Tests (7 tests)

**Files:**
- Create: `tests/integration/test_api_items.py`

### Step 1: Write API items tests

```python
"""Integration tests for GET /api/items endpoints against real PostgreSQL."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from tests.integration.conftest import seed_news_item

pytestmark = pytest.mark.integration


class TestListItems:
    async def test_returns_seeded_data(self, client, db_session, auth_headers):
        """Seeded items are returned by GET /api/items."""
        for i in range(5):
            await seed_news_item(db_session, title=f"Item {i}", url=f"https://x.com/{i}")

        resp = await client.get("/api/items", headers=auth_headers)

        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 5

    async def test_filter_by_topic(self, client, db_session, auth_headers):
        """?topic=modelos returns only items with that topic."""
        await seed_news_item(db_session, title="Modelos A", topic="modelos")
        await seed_news_item(db_session, title="Tools B", topic="herramientas")

        resp = await client.get("/api/items?topic=modelos", headers=auth_headers)

        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["topic"] == "modelos"

    async def test_filter_by_source(self, client, db_session, auth_headers):
        """?source=arxiv returns only items from that source."""
        await seed_news_item(db_session, title="HN Item", source="hackernews")
        await seed_news_item(db_session, title="Arxiv Item", source="arxiv")

        resp = await client.get("/api/items?source=arxiv", headers=auth_headers)

        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["source"] == "arxiv"

    async def test_filter_by_date_range(self, client, db_session, auth_headers):
        """?date_from=...&date_to=... returns items in that window."""
        today = datetime.now(tz=UTC)
        yesterday = today - timedelta(days=1)
        three_days_ago = today - timedelta(days=3)

        await seed_news_item(
            db_session, title="Recent", published_at=yesterday
        )
        await seed_news_item(
            db_session, title="Old", published_at=three_days_ago
        )

        date_from = (today - timedelta(days=2)).strftime("%Y-%m-%d")
        date_to = today.strftime("%Y-%m-%d")
        resp = await client.get(
            f"/api/items?date_from={date_from}&date_to={date_to}",
            headers=auth_headers,
        )

        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["title"] == "Recent"

    async def test_pagination(self, client, db_session, auth_headers):
        """limit and offset paginate correctly."""
        for i in range(10):
            await seed_news_item(
                db_session,
                title=f"Page {i}",
                url=f"https://x.com/page-{i}",
                score=100 - i,  # descending order
            )

        resp1 = await client.get("/api/items?limit=3&offset=0", headers=auth_headers)
        resp2 = await client.get("/api/items?limit=3&offset=3", headers=auth_headers)

        assert len(resp1.json()) == 3
        assert len(resp2.json()) == 3
        # No overlap between pages
        ids1 = {item["id"] for item in resp1.json()}
        ids2 = {item["id"] for item in resp2.json()}
        assert ids1.isdisjoint(ids2)


class TestItemsCount:
    async def test_count_matches(self, client, db_session, auth_headers):
        """GET /api/items/count returns correct count."""
        for i in range(4):
            await seed_news_item(db_session, title=f"Count {i}", url=f"https://x.com/c-{i}")

        resp = await client.get("/api/items/count", headers=auth_headers)

        assert resp.status_code == 200
        assert resp.json()["count"] == 4


class TestItemsToday:
    async def test_returns_only_today(self, client, db_session, auth_headers):
        """GET /api/items/today returns only items created today."""
        # created_at defaults to now() via server_default — these are "today"
        await seed_news_item(db_session, title="Today Item", url="https://x.com/today")

        resp = await client.get("/api/items/today", headers=auth_headers)

        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 1
        assert any(item["title"] == "Today Item" for item in data)
```

### Step 2: Run tests

```bash
.venv/bin/pytest tests/integration/test_api_items.py -v --timeout=60
```

Expected: 7 passed.

### Step 3: Commit

```bash
git add tests/integration/test_api_items.py
git commit -m "test: M10 API items integration tests — filters, pagination, count [M10]"
```

---

## Task 4: API Search Tests (3 tests)

**Files:**
- Create: `tests/integration/test_api_search.py`

### Step 1: Write search tests

```python
"""Integration tests for GET /api/search — PostgreSQL full-text search."""

from __future__ import annotations

import pytest

from tests.integration.conftest import seed_news_item

pytestmark = pytest.mark.integration


class TestSearch:
    async def test_finds_matching_items(self, client, db_session, auth_headers):
        """FTS with plainto_tsquery finds items by keyword in title/text."""
        await seed_news_item(
            db_session,
            title="Transformer Architecture Breakthrough",
            full_text="A new transformer model achieves state-of-the-art results.",
        )
        await seed_news_item(
            db_session,
            title="Python Web Framework",
            full_text="A guide to building REST APIs with FastAPI.",
        )

        resp = await client.get("/api/search?q=transformer", headers=auth_headers)

        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert "Transformer" in data[0]["title"]

    async def test_ranks_by_relevance(self, client, db_session, auth_headers):
        """Items with higher keyword density rank first (ts_rank)."""
        await seed_news_item(
            db_session,
            title="Machine Learning Overview",
            full_text="Brief mention of neural networks.",
            url="https://example.com/low-rank",
        )
        await seed_news_item(
            db_session,
            title="Neural Networks Deep Dive",
            full_text="Neural networks neural networks training neural networks.",
            url="https://example.com/high-rank",
        )

        resp = await client.get("/api/search?q=neural+networks", headers=auth_headers)

        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        # Higher density item should rank first
        assert "Deep Dive" in data[0]["title"]

    async def test_search_with_topic_filter(self, client, db_session, auth_headers):
        """Search + topic filter returns intersection."""
        await seed_news_item(
            db_session,
            title="LLM Training Techniques",
            topic="modelos",
            url="https://example.com/llm-modelos",
        )
        await seed_news_item(
            db_session,
            title="LLM Development Tools",
            topic="herramientas",
            url="https://example.com/llm-tools",
        )

        resp = await client.get(
            "/api/search?q=LLM&topic=modelos", headers=auth_headers
        )

        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["topic"] == "modelos"
```

### Step 2: Run tests

```bash
.venv/bin/pytest tests/integration/test_api_search.py -v --timeout=60
```

Expected: 3 passed.

### Step 3: Commit

```bash
git add tests/integration/test_api_search.py
git commit -m "test: M10 API search integration tests — FTS, ranking, filters [M10]"
```

---

## Task 5: API Briefings + Auth Tests (5 tests)

**Files:**
- Create: `tests/integration/test_api_briefings.py`
- Create: `tests/integration/test_api_auth.py`

### Step 1: Write briefing tests

```python
"""Integration tests for GET /api/briefings endpoints."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from tests.integration.conftest import seed_briefing, seed_news_item

pytestmark = pytest.mark.integration


class TestListBriefings:
    async def test_returns_seeded_briefings(self, client, db_session, auth_headers):
        """GET /api/briefings returns briefing summaries."""
        today = datetime.now(tz=UTC).date()
        yesterday = today - timedelta(days=1)

        await seed_briefing(db_session, date=today, total_items=10)
        await seed_briefing(db_session, date=yesterday, total_items=5)

        resp = await client.get("/api/briefings", headers=auth_headers)

        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2


class TestGetBriefingByDate:
    async def test_includes_items_for_date(self, client, db_session, auth_headers):
        """GET /api/briefings/{date} returns briefing with items."""
        today = datetime.now(tz=UTC).date()
        await seed_briefing(db_session, date=today, total_items=2)
        # Seed items with created_at = today (server_default handles this)
        await seed_news_item(db_session, title="Today A", url="https://x.com/ba")
        await seed_news_item(db_session, title="Today B", url="https://x.com/bb")

        resp = await client.get(
            f"/api/briefings/{today.isoformat()}", headers=auth_headers
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["total_items"] == 2
        assert len(data["items"]) == 2
```

### Step 2: Write auth tests

```python
"""Integration tests for authentication flow."""

from __future__ import annotations

import pytest

from src.core.config import get_settings

pytestmark = pytest.mark.integration


class TestAuthFlow:
    async def test_login_returns_jwt(self, client):
        """POST /api/auth/token with correct password returns JWT."""
        settings = get_settings()
        resp = await client.post(
            "/api/auth/token",
            json={"password": settings.shared_password},
        )

        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    async def test_protected_route_with_jwt(self, client):
        """Login, then use JWT to access protected route."""
        settings = get_settings()

        # Login
        login_resp = await client.post(
            "/api/auth/token",
            json={"password": settings.shared_password},
        )
        token = login_resp.json()["access_token"]

        # Access protected route
        resp = await client.get(
            "/api/items",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200

    async def test_protected_route_without_jwt(self, client):
        """Access protected route without token returns 403."""
        resp = await client.get("/api/items")
        assert resp.status_code == 403
```

### Step 3: Run tests

```bash
.venv/bin/pytest tests/integration/test_api_briefings.py tests/integration/test_api_auth.py -v --timeout=60
```

Expected: 5 passed.

### Step 4: Commit

```bash
git add tests/integration/test_api_briefings.py tests/integration/test_api_auth.py
git commit -m "test: M10 briefings + auth integration tests [M10]"
```

---

## Task 6: RAG Tests (5 tests)

**Files:**
- Create: `tests/integration/test_rag.py`

### Step 1: Write RAG tests

```python
"""Integration tests for RAG — embeddings, retrieval, and chat via pgvector."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import func, select

from src.core.models import ItemEmbedding, NewsItem
from src.rag.chat import ChatService
from src.rag.embeddings import EmbeddingService
from src.rag.retriever import Retriever
from tests.integration.conftest import seed_embedding, seed_news_item

pytestmark = pytest.mark.integration


class TestEmbeddingStorage:
    async def test_store_and_retrieve_by_similarity(self, db_session):
        """Items with embeddings can be retrieved by cosine similarity."""
        # Seed two items with distinct embeddings
        item_a = await seed_news_item(
            db_session, title="Close Match", url="https://x.com/close"
        )
        item_b = await seed_news_item(
            db_session, title="Far Match", url="https://x.com/far"
        )

        # item_a: vector pointing "right" — item_b: vector pointing "left"
        vec_a = [1.0] + [0.0] * 1535
        vec_b = [-1.0] + [0.0] * 1535
        await seed_embedding(db_session, item_a, vector=vec_a)
        await seed_embedding(db_session, item_b, vector=vec_b)

        # Query vector similar to item_a
        query_vec = [0.9] + [0.0] * 1535

        mock_embed = AsyncMock(spec=EmbeddingService)
        mock_embed.embed_text.return_value = query_vec

        retriever = Retriever(embedding_service=mock_embed)
        results = await retriever.retrieve(db_session, "test query", limit=2)

        assert len(results) == 2
        assert results[0].title == "Close Match"
        assert results[1].title == "Far Match"

    async def test_retrieve_with_topic_filter(self, db_session):
        """Retriever respects topic filter."""
        item_a = await seed_news_item(
            db_session,
            title="Modelos Item",
            topic="modelos",
            url="https://x.com/topic-a",
        )
        item_b = await seed_news_item(
            db_session,
            title="Tools Item",
            topic="herramientas",
            url="https://x.com/topic-b",
        )

        vec = [0.5] * 1536
        await seed_embedding(db_session, item_a, vector=vec)
        await seed_embedding(db_session, item_b, vector=vec)

        mock_embed = AsyncMock(spec=EmbeddingService)
        mock_embed.embed_text.return_value = vec

        retriever = Retriever(embedding_service=mock_embed)
        results = await retriever.retrieve(
            db_session, "test", limit=10, topic="modelos"
        )

        assert len(results) == 1
        assert results[0].topic == "modelos"

    async def test_retrieve_empty_table(self, db_session):
        """Retriever returns [] when no embeddings exist."""
        mock_embed = AsyncMock(spec=EmbeddingService)
        mock_embed.embed_text.return_value = [0.1] * 1536

        retriever = Retriever(embedding_service=mock_embed)
        results = await retriever.retrieve(db_session, "anything")

        assert results == []


class TestEmbedNewItems:
    async def test_new_items_get_embeddings(self, db_session):
        """_embed_new_items stores vectors for items without embeddings."""
        from unittest.mock import patch

        from src.pipeline.pipeline import _embed_new_items

        items = []
        for i in range(3):
            item = await seed_news_item(
                db_session,
                title=f"Embed Test {i}",
                url=f"https://x.com/embed-new-{i}",
            )
            items.append(item)

        mock_embed = AsyncMock(spec=EmbeddingService)
        mock_embed.prepare_text = EmbeddingService.prepare_text
        mock_embed.embed_batch.return_value = [[0.3] * 1536] * 3

        with patch("src.pipeline.pipeline.get_settings") as mock_settings:
            mock_settings.return_value.embedding_model = "text-embedding-3-small"
            count = await _embed_new_items(db_session, embed_service=mock_embed)

        assert count == 3
        result = await db_session.execute(select(func.count(ItemEmbedding.item_id)))
        assert result.scalar_one() == 3


class TestChatStream:
    async def test_returns_sse_events(self, db_session):
        """ChatService.chat_stream yields SSE token + sources + [DONE]."""
        # Seed item + embedding
        item = await seed_news_item(
            db_session, title="Chat Context Item", url="https://x.com/chat"
        )
        await seed_embedding(db_session, item, vector=[0.5] * 1536)

        # Mock embedding service (for retriever query embedding)
        mock_embed = AsyncMock(spec=EmbeddingService)
        mock_embed.embed_text.return_value = [0.5] * 1536

        # Mock LLM client
        mock_llm = AsyncMock()
        mock_chunk = AsyncMock()
        mock_chunk.choices = [AsyncMock()]
        mock_chunk.choices[0].delta.content = "Respuesta"
        mock_stream = AsyncMock()
        mock_stream.__aiter__ = lambda self: self
        mock_stream.__anext__ = AsyncMock(
            side_effect=[mock_chunk, StopAsyncIteration]
        )
        mock_llm.chat.completions.create.return_value = mock_stream

        retriever = Retriever(embedding_service=mock_embed)
        service = ChatService(retriever=retriever, llm_client=mock_llm)

        events = []
        async for event in service.chat_stream(db_session, "test question"):
            events.append(event)

        # Should have: token event(s) + sources + [DONE]
        assert len(events) >= 3
        # First event has a token
        first = json.loads(events[0].replace("data: ", "").strip())
        assert "token" in first
        # Second-to-last has sources
        sources_event = json.loads(events[-2].replace("data: ", "").strip())
        assert "sources" in sources_event
        assert len(sources_event["sources"]) == 1
        # Last is [DONE]
        assert events[-1].strip() == "data: [DONE]"
```

### Step 2: Run tests

```bash
.venv/bin/pytest tests/integration/test_rag.py -v --timeout=60
```

Expected: 5 passed.

### Step 3: Commit

```bash
git add tests/integration/test_rag.py
git commit -m "test: M10 RAG integration tests — embeddings, retrieval, chat [M10]"
```

---

## Task 7: CI Update + Final Verification

**Files:**
- Modify: `.github/workflows/ci.yml`
- Modify: `docs/plans/2026-02-21-milestone-10-design.md`

### Step 1: Update CI to run integration tests separately

In `.github/workflows/ci.yml`, replace the "Run tests" step with two steps:

```yaml
      - name: Run unit tests
        env:
          DATABASE_URL: postgresql+asyncpg://ainews:testpassword@localhost:5432/ainews_test
          DATABASE_URL_SYNC: postgresql://ainews:testpassword@localhost:5432/ainews_test
          TESTING: "1"
        run: |
          coverage run -m pytest tests/unit/ -v --timeout=30
          coverage report --fail-under=80

      - name: Run integration tests
        env:
          DATABASE_URL: postgresql+asyncpg://ainews:testpassword@localhost:5432/ainews_test
          DATABASE_URL_SYNC: postgresql://ainews:testpassword@localhost:5432/ainews_test
          TESTING: "1"
        run: |
          pytest tests/integration/ -v -m integration --timeout=60
```

### Step 2: Run full verification

```bash
# Unit tests (no regressions)
.venv/bin/pytest tests/unit/ -x --timeout=30

# Integration tests
.venv/bin/pytest tests/integration/ -v -m integration --timeout=60

# Lint
.venv/bin/ruff check . && .venv/bin/ruff format --check .
```

Expected:
- Unit: 702 passed
- Integration: 27 passed
- Ruff: clean

### Step 3: Update design doc success criteria

In `docs/plans/2026-02-21-milestone-10-design.md`, mark all criteria as `[x]`.

### Step 4: Commit

```bash
git add .github/workflows/ci.yml docs/plans/2026-02-21-milestone-10-design.md
git commit -m "test: M10 final — CI integration step + milestone complete [M10]"
```

---

## Summary

| Task | Tests | Files |
|---|---|---|
| 1. Infrastructure | 0 (+smoke) | conftest.py, __init__.py |
| 2. Pipeline | 7 | test_pipeline.py |
| 3. API Items | 7 | test_api_items.py |
| 4. API Search | 3 | test_api_search.py |
| 5. Briefings + Auth | 5 | test_api_briefings.py, test_api_auth.py |
| 6. RAG | 5 | test_rag.py |
| 7. CI + verification | 0 | ci.yml, design doc |
| **Total** | **27** | |
