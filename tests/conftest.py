"""Shared test fixtures for the AI News Platform test suite."""

from __future__ import annotations

import os
from collections.abc import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from tests.factories import make_classified_item, make_extracted_item

# ---------------------------------------------------------------------------
# Environment setup -- force test mode BEFORE importing application code
# that calls get_settings() at module level.
# ---------------------------------------------------------------------------
os.environ["TESTING"] = "1"
os.environ["TELEGRAM_BOT_TOKEN"] = ""
os.environ["TELEGRAM_CHAT_ID"] = ""
os.environ["TELEGRAM_ALERTS_ENABLED"] = "false"


# ---------------------------------------------------------------------------
# Settings fixture
# ---------------------------------------------------------------------------
@pytest.fixture()
def settings():
    """Return a Settings instance tuned for testing.

    Overrides the database URL to point at a dedicated test database and
    disables external integrations so unit tests never touch real services.
    """
    from src.core.config import Settings

    return Settings(
        database_url="postgresql+asyncpg://ainews:ainews@localhost:5432/ainews_test",
        database_url_sync="postgresql://ainews:ainews@localhost:5432/ainews_test",
        debug=True,
        telegram_bot_token="",
        telegram_chat_id="",
        telegram_alerts_enabled=False,
        log_format="console",
    )


# ---------------------------------------------------------------------------
# Database fixtures
# ---------------------------------------------------------------------------
@pytest.fixture()
async def db_engine(settings) -> AsyncGenerator[AsyncEngine, None]:
    """Create an async engine pointed at the test database.

    The engine is disposed after the test.
    """
    engine = create_async_engine(
        settings.database_url,
        echo=True,
        pool_size=2,
        max_overflow=0,
    )
    yield engine
    await engine.dispose()


@pytest.fixture()
async def db_session(db_engine: AsyncEngine) -> AsyncGenerator[AsyncSession, None]:
    """Yield a test session wrapped in a transaction that is always rolled back.

    This ensures that every test starts with a clean database state without
    needing to recreate tables each time.
    """
    session_factory = async_sessionmaker(
        bind=db_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    async with session_factory() as session, session.begin():
        yield session
        # Roll back so nothing persists between tests
        await session.rollback()


# ---------------------------------------------------------------------------
# FastAPI / httpx test client
# ---------------------------------------------------------------------------
@pytest.fixture()
async def client() -> AsyncGenerator[AsyncClient, None]:
    """Provide an async httpx client wired to the FastAPI app.

    Uses ASGITransport so no real HTTP server is started.
    """
    from src.api.app import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac


# ---------------------------------------------------------------------------
# Data-factory fixtures (thin wrappers for convenience in tests)
# ---------------------------------------------------------------------------
@pytest.fixture()
def extracted_item_factory():
    """Return the ``make_extracted_item`` factory function.

    Usage inside a test::

        item = extracted_item_factory(title="Custom title", source="arxiv")
    """
    return make_extracted_item


@pytest.fixture()
def classified_item_factory():
    """Return the ``make_classified_item`` factory function.

    Usage inside a test::

        item = classified_item_factory(topic="papers", relevance_score=0.95)
    """
    return make_classified_item
