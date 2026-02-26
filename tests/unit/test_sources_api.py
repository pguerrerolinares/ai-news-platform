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
