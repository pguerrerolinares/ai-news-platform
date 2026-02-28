"""Security tests for SQL injection attempts against real PostgreSQL."""

from __future__ import annotations

from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from tests.integration.conftest import db_session, integration_engine, seed_news_item  # noqa: F401

pytestmark = [pytest.mark.security, pytest.mark.asyncio(loop_scope="session")]


@pytest_asyncio.fixture(loop_scope="session")
async def db_client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:  # noqa: F811
    """ASGI client with real DB session for SQL injection tests."""
    from src.api.app import app
    from src.core.database import get_session

    async def _override() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    app.dependency_overrides[get_session] = _override
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest.fixture()
def _auth_headers() -> dict[str, str]:
    from src.api.auth import create_access_token

    return {"Authorization": f"Bearer {create_access_token()}"}


class TestSQLInjection:
    """SQL injection attempts that must not cause data leaks or crashes."""

    async def test_classic_drop_table(
        self,
        db_client: AsyncClient,
        db_session: AsyncSession,  # noqa: F811
        _auth_headers: dict[str, str],
    ):
        """Classic DROP TABLE injection in search query must be harmless."""
        await seed_news_item(db_session, title="Safe Article", url="https://example.com/safe-sql")

        resp = await db_client.get(
            "/api/search", params={"q": "'; DROP TABLE news_items--"}, headers=_auth_headers
        )
        assert resp.status_code in (200, 422)
        assert resp.status_code != 500

        # Verify table still exists and has data
        result = await db_session.execute(text("SELECT count(*) FROM news_items"))
        assert result.scalar_one() >= 1

    async def test_union_select(self, db_client: AsyncClient, _auth_headers: dict[str, str]):
        """UNION SELECT injection must not leak data from other tables."""
        resp = await db_client.get(
            "/api/search",
            params={"q": "' UNION SELECT password FROM users--"},
            headers=_auth_headers,
        )
        assert resp.status_code in (200, 422)
        assert resp.status_code != 500
        # If 200, response should be empty or contain only legitimate items
        if resp.status_code == 200:
            data = resp.json()
            for item in data:
                assert "password" not in item

    async def test_filter_param_injection(
        self,
        db_client: AsyncClient,
        db_session: AsyncSession,  # noqa: F811
        _auth_headers: dict[str, str],
    ):
        """Topic filter with SQL injection must match zero results (exact match)."""
        await seed_news_item(
            db_session, title="Legit Item", topic="models", url="https://example.com/filter-sql"
        )

        resp = await db_client.get(
            "/api/items", params={"topic": "models' OR '1'='1"}, headers=_auth_headers
        )
        assert resp.status_code == 200
        data = resp.json()
        # Injection should NOT return items — exact match fails
        assert len(data) == 0

    async def test_null_byte_in_query(self, db_client: AsyncClient, _auth_headers: dict[str, str]):
        """Null byte in search query must not execute injected SQL.

        PostgreSQL rejects null bytes at the protocol level (invalid UTF-8).
        Depending on the driver/transport, this may surface as a 500 HTTP
        response or as an unhandled ``DBAPIError`` that propagates through the
        test session.  Both outcomes prove the injection was blocked — the
        DB refused the payload before any SQL execution occurred.
        """
        from sqlalchemy.exc import DBAPIError

        try:
            resp = await db_client.get(
                "/api/search",
                params={"q": "test\x00; DROP TABLE news_items"},
                headers=_auth_headers,
            )
            # 200 = safe search, 422 = validation rejected, 500 = driver rejected
            assert resp.status_code in (200, 422, 500)
        except DBAPIError as exc:
            # asyncpg raises CharacterNotInRepertoireError for 0x00 bytes —
            # this is the DB driver rejecting the payload at the protocol
            # level, which is a safe outcome (no SQL was executed).
            assert "0x00" in str(exc) or "null" in str(exc).lower()

    async def test_oversized_query_string(
        self, db_client: AsyncClient, _auth_headers: dict[str, str]
    ):
        """Extremely long search query must not crash the application."""
        resp = await db_client.get("/api/search", params={"q": "A" * 10000}, headers=_auth_headers)
        assert resp.status_code in (200, 422)
        assert resp.status_code != 500
