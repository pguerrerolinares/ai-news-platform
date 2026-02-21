"""Unit tests for standardized error responses."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from src.api.app import app
from src.core.database import get_session


def _make_mock_session():
    mock_result = MagicMock()
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = []
    mock_result.scalars.return_value = mock_scalars
    mock_result.scalar_one.return_value = 0
    mock_result.scalar_one_or_none.return_value = None
    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(return_value=mock_result)
    return mock_session


async def _mock_get_session():
    yield _make_mock_session()


@pytest.fixture(autouse=True)
def _override_session():
    app.dependency_overrides[get_session] = _mock_get_session
    yield
    app.dependency_overrides.pop(get_session, None)


@pytest.fixture()
async def api_client() -> AsyncClient:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac  # type: ignore[misc]


class TestErrorFormat:
    async def test_401_returns_error_object(self, api_client: AsyncClient):
        """401 should return {"error": {"code": ..., "message": ...}}."""
        resp = await api_client.get("/api/items", headers={"Authorization": "Bearer invalid"})
        assert resp.status_code == 401
        data = resp.json()
        assert "error" in data
        assert "code" in data["error"]
        assert "message" in data["error"]
        assert data["error"]["code"] == "INVALID_TOKEN"

    async def test_404_returns_error_object(self, api_client: AsyncClient):
        """404 should return {"error": {"code": ..., "message": ...}}."""
        from src.api.auth import require_auth

        app.dependency_overrides[require_auth] = lambda: "test-user"
        try:
            resp = await api_client.get("/api/briefings/1999-01-01")
            assert resp.status_code == 404
            data = resp.json()
            assert "error" in data
            assert data["error"]["code"] == "BRIEFING_NOT_FOUND"
        finally:
            app.dependency_overrides.pop(require_auth, None)
