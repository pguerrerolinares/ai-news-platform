"""Unit tests for admin API routes (audit, pipeline-runs, freshness).

These endpoints are publicly readable (require_auth_or_guest, no admin needed).
error_message is sanitized (None) in pipeline-runs responses.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from src.api.app import app
from src.api.auth import require_auth_or_guest
from src.core.database import get_session


def _make_base_session() -> AsyncMock:
    """Return a minimal mock session for admin endpoints."""
    mock_result = MagicMock()
    mock_result.scalars.return_value = MagicMock(all=MagicMock(return_value=[]))
    mock_result.all.return_value = []
    mock_result.one.return_value = (0, None, None)
    mock_result.scalar_one_or_none.return_value = None

    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(return_value=mock_result)
    return mock_session


async def _mock_get_session():
    yield _make_base_session()


@pytest.fixture(autouse=True)
def _override_dependencies():
    app.dependency_overrides[require_auth_or_guest] = lambda: "guest"
    app.dependency_overrides[get_session] = _mock_get_session
    yield
    app.dependency_overrides.pop(require_auth_or_guest, None)
    app.dependency_overrides.pop(get_session, None)


@pytest.fixture()
async def api_client() -> AsyncClient:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac  # type: ignore[misc]


# ---------------------------------------------------------------------------
# /api/admin/audit
# ---------------------------------------------------------------------------
class TestAdminAudit:
    """GET /api/admin/audit is publicly readable (no admin required)."""

    async def test_audit_returns_200_for_guest(self, api_client: AsyncClient):
        """Guest (no login) can read the audit endpoint."""

        def _session():
            mock_result = MagicMock()
            # Handles: (count, min, max), (dup_groups, extra_items) via one()
            mock_result.one.side_effect = [
                (0, None, None),  # total items + date range
                (0, 0),  # duplicate subquery
            ]
            mock_result.all.return_value = []
            mock_session = AsyncMock()
            mock_session.execute = AsyncMock(return_value=mock_result)
            return mock_session

        async def _get():
            yield _session()

        app.dependency_overrides[get_session] = _get
        try:
            resp = await api_client.get("/api/admin/audit")
        finally:
            app.dependency_overrides[get_session] = _mock_get_session

        assert resp.status_code == 200
        data = resp.json()
        assert "total_items" in data
        assert "sources" in data
        assert "duplicates" in data

    async def test_audit_does_not_require_admin_token(self, api_client: AsyncClient):
        """Endpoint accessible without any auth override hacks for admin role."""
        # The autouse fixture already overrides to a plain guest — 200 proves no admin check.

        def _session():
            mock_result = MagicMock()
            mock_result.one.side_effect = [(0, None, None), (0, 0)]
            mock_result.all.return_value = []
            mock_session = AsyncMock()
            mock_session.execute = AsyncMock(return_value=mock_result)
            return mock_session

        async def _get():
            yield _session()

        app.dependency_overrides[get_session] = _get
        try:
            resp = await api_client.get("/api/admin/audit")
        finally:
            app.dependency_overrides[get_session] = _mock_get_session

        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# /api/admin/pipeline-runs
# ---------------------------------------------------------------------------


def _make_pipeline_run(
    *,
    error_message: str | None = None,
    status: str = "success",
) -> MagicMock:
    """Create a MagicMock resembling a PipelineRun ORM row."""
    run = MagicMock()
    run.id = uuid.uuid4()
    run.started_at = datetime(2024, 1, 1, tzinfo=UTC)
    run.duration_seconds = 1.5
    run.status = status
    run.sources = ["hackernews"]
    run.items_extracted = 10
    run.items_after_dedup = 8
    run.items_seen_filtered = 2
    run.items_classified = 7
    run.items_validated = 6
    run.items_stored = 5
    run.error_message = error_message
    run.correlation_id = "abc123"
    return run


class TestAdminPipelineRuns:
    """GET /api/admin/pipeline-runs is publicly readable; error_message is sanitized."""

    def _session_with_runs(self, runs: list) -> AsyncMock:
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = runs
        mock_result = MagicMock()
        mock_result.scalars.return_value = mock_scalars
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)
        return mock_session

    async def test_pipeline_runs_returns_200_for_guest(self, api_client: AsyncClient):
        """Guest can read pipeline-runs without admin login."""
        session = self._session_with_runs([])

        async def _get():
            yield session

        app.dependency_overrides[get_session] = _get
        try:
            resp = await api_client.get("/api/admin/pipeline-runs")
        finally:
            app.dependency_overrides[get_session] = _mock_get_session

        assert resp.status_code == 200
        assert resp.json() == []

    async def test_error_message_sanitized_to_none(self, api_client: AsyncClient):
        """A run with a raw error_message in the DB must return error_message=None in JSON."""
        run = _make_pipeline_run(
            error_message="could not connect to server: Connection refused\n"
            "\tIs the server running on host 'db.internal' (192.168.1.5) and port 5432?",
            status="error",
        )
        session = self._session_with_runs([run])

        async def _get():
            yield session

        app.dependency_overrides[get_session] = _get
        try:
            resp = await api_client.get("/api/admin/pipeline-runs")
        finally:
            app.dependency_overrides[get_session] = _mock_get_session

        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["error_message"] is None, "Raw error must not be exposed publicly"
        assert data[0]["status"] == "error", "Status must still reflect the failure"

    async def test_null_error_message_stays_none(self, api_client: AsyncClient):
        """A successful run with error_message=None in DB stays None in response."""
        run = _make_pipeline_run(error_message=None, status="success")
        session = self._session_with_runs([run])

        async def _get():
            yield session

        app.dependency_overrides[get_session] = _get
        try:
            resp = await api_client.get("/api/admin/pipeline-runs")
        finally:
            app.dependency_overrides[get_session] = _mock_get_session

        assert resp.status_code == 200
        data = resp.json()
        assert data[0]["error_message"] is None

    async def test_status_filter_passed_through(self, api_client: AsyncClient):
        """Query param ?status=error is forwarded to the DB query (returns 200)."""
        session = self._session_with_runs([])

        async def _get():
            yield session

        app.dependency_overrides[get_session] = _get
        try:
            resp = await api_client.get("/api/admin/pipeline-runs?status=error")
        finally:
            app.dependency_overrides[get_session] = _mock_get_session

        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# /api/admin/freshness
# ---------------------------------------------------------------------------
class TestAdminFreshness:
    """GET /api/admin/freshness is publicly readable."""

    async def test_freshness_returns_200_for_guest(self, api_client: AsyncClient):
        """Guest can read freshness without admin login."""
        mock_result = MagicMock()
        mock_result.all.return_value = []
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)

        async def _get():
            yield mock_session

        app.dependency_overrides[get_session] = _get
        try:
            resp = await api_client.get("/api/admin/freshness")
        finally:
            app.dependency_overrides[get_session] = _mock_get_session

        assert resp.status_code == 200
        assert resp.json() == []

    async def test_freshness_response_shape(self, api_client: AsyncClient):
        """Each freshness entry has source, last_item_at, hours_ago, status fields."""
        row = MagicMock()
        row.source = "hackernews"
        row.last_item_at = datetime(2024, 1, 1, 0, 0, 0, tzinfo=UTC)

        mock_result = MagicMock()
        mock_result.all.return_value = [row]
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)

        async def _get():
            yield mock_session

        app.dependency_overrides[get_session] = _get
        try:
            resp = await api_client.get("/api/admin/freshness")
        finally:
            app.dependency_overrides[get_session] = _mock_get_session

        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        entry = data[0]
        assert entry["source"] == "hackernews"
        assert "last_item_at" in entry
        assert "hours_ago" in entry
        assert entry["status"] in ("ok", "stale", "dead")
