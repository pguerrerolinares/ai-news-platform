"""Integration test fixtures — real PostgreSQL with savepoint isolation."""

from __future__ import annotations

import os
from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import pytest
import pytest_asyncio
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

from src.core.config import get_settings  # must be after env setup

# Clear cached settings so they pick up test DB URL
get_settings.cache_clear()


# ---------------------------------------------------------------------------
# Session-scoped: engine + table creation (once per test session)
# ---------------------------------------------------------------------------
@pytest_asyncio.fixture(scope="session", loop_scope="session")
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
@pytest_asyncio.fixture(loop_scope="session")
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
    def _restart_savepoint(db_session, transaction):  # type: ignore[no-untyped-def]
        if conn.closed:
            return
        if not conn.in_nested_transaction() and conn.sync_connection:
            conn.sync_connection.begin_nested()

    yield session

    await session.close()
    await trans.rollback()
    await conn.close()


# ---------------------------------------------------------------------------
# FastAPI test client with session override
# ---------------------------------------------------------------------------
@pytest_asyncio.fixture(loop_scope="session")
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
async def seed_news_item(session: AsyncSession, **overrides: Any) -> NewsItem:
    """Insert a single NewsItem and flush. Returns the ORM instance."""
    defaults: dict = {
        "title": "Test AI Breakthrough",
        "source": "hackernews",
        "topic": "models",
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


async def seed_briefing(session: AsyncSession, **overrides: Any) -> DailyBriefing:
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
