"""Security test fixtures — adversarial testing infrastructure."""

from __future__ import annotations

import os
from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

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

from src.core.config import get_settings

get_settings.cache_clear()


# ---------------------------------------------------------------------------
# Lightweight client (no real DB — mocked session)
# ---------------------------------------------------------------------------
@pytest_asyncio.fixture(loop_scope="session")
async def security_client() -> AsyncGenerator[AsyncClient, None]:
    """ASGI client with a mocked DB session for non-DB security tests."""
    from src.api.app import app
    from src.core.database import get_session

    mock_session = AsyncMock(spec=AsyncSession)

    async def _override() -> AsyncGenerator[AsyncSession, None]:
        yield mock_session

    app.dependency_overrides[get_session] = _override

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac

    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------
@pytest.fixture()
def valid_token() -> str:
    """Create a valid JWT token for comparison/baseline tests."""
    from src.api.auth import create_access_token

    return create_access_token(subject="test-user")


@pytest.fixture()
def auth_headers(valid_token: str) -> dict[str, str]:
    """Valid Authorization headers."""
    return {"Authorization": f"Bearer {valid_token}"}
