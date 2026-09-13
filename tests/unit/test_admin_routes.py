"""Unit tests for admin API routes (audit, pipeline-runs, freshness).

These endpoints are publicly readable (require_auth_or_guest, no admin needed).
error_message is sanitized before being served: the DB keeps the raw exception
string for internal debugging, but the response only exposes a short, path-free
first line (see `_sanitize_error_message` in src/api/routes/admin.py).
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from pydantic import TypeAdapter

from src.api.app import app
from src.api.auth import require_auth_or_guest
from src.core.config import Settings
from src.core.database import get_session
from src.pipeline.health_rules import HealthAlert

_FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"


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
    """GET /api/admin/pipeline-runs is publicly readable; error_message is exposed for debugging."""

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

    async def test_error_message_is_sanitized_for_public_response(self, api_client: AsyncClient):
        """A raw multi-line error_message with an internal path must be sanitized before serving."""
        raw_error = (
            "could not connect to server: Connection refused at /home/deploy/app/db/pool.py:42\n"
            "\tIs the server running on host 'db.internal' (192.168.1.5) and port 5432?\n"
            "\tTraceback (most recent call last): ..."
        )
        run = _make_pipeline_run(error_message=raw_error, status="error")
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
        sanitized = data[0]["error_message"]
        assert sanitized is not None
        assert "/home/deploy/app/db/pool.py" not in sanitized, "must not leak absolute paths"
        assert "\n" not in sanitized, "must not leak multi-line tracebacks"
        assert len(sanitized) <= 120, "must be capped to a short length"
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


# ---------------------------------------------------------------------------
# /api/admin/health
# ---------------------------------------------------------------------------
class TestAdminHealth:
    """GET /api/admin/health: derived, no new tables, public (guest token)."""

    @staticmethod
    def _session(*, last_run_at, runs, freshness_rows) -> AsyncMock:
        """3 queries in order: last_run_started_at, pipeline_runs window, freshness."""
        result_last_run = MagicMock()
        result_last_run.scalar_one_or_none.return_value = last_run_at

        result_runs = MagicMock()
        result_runs.scalars.return_value = MagicMock(all=MagicMock(return_value=runs))

        result_freshness = MagicMock()
        result_freshness.all.return_value = freshness_rows

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(
            side_effect=[result_last_run, result_runs, result_freshness]
        )
        return mock_session

    async def _get(self, api_client: AsyncClient, mock_session: AsyncMock, settings: Settings):
        async def _override():
            yield mock_session

        app.dependency_overrides[get_session] = _override
        try:
            with patch("src.api.routes.admin.get_settings", return_value=settings):
                return await api_client.get("/api/admin/health")
        finally:
            app.dependency_overrides[get_session] = _mock_get_session

    async def test_returns_200_empty_list_for_healthy_db(self, api_client: AsyncClient):
        now = datetime.now(tz=UTC)
        run = MagicMock()
        run.started_at = now - timedelta(minutes=5)
        run.status = "success"
        run.items_extracted = 10
        run.items_stored = 10

        mock_session = self._session(last_run_at=now, runs=[run], freshness_rows=[])
        resp = await self._get(api_client, mock_session, Settings(openai_api_key="sk-test"))

        assert resp.status_code == 200
        assert resp.json() == []

    async def test_empty_table_reports_scheduler_silent_with_since_null(
        self, api_client: AsyncClient
    ):
        mock_session = self._session(last_run_at=None, runs=[], freshness_rows=[])
        resp = await self._get(api_client, mock_session, Settings(openai_api_key="sk-test"))

        assert resp.status_code == 200
        alert = next(a for a in resp.json() if a["code"] == "scheduler_silent")
        assert alert["since"] is None
        assert alert["severity"] == "critical"

    async def test_no_setting_value_leaks_in_response(self, api_client: AsyncClient):
        """Falsable: interpolating any setting into a message would break this."""
        sentinel_settings = Settings(
            openai_api_key="",
            openai_model="SENTINEL-MODEL-9f3",
            openai_base_url="https://sentinel-9f3.invalid",
            database_url="postgresql+asyncpg://u:SENTINEL-PW-9f3@h/d",
            jwt_secret="SENTINEL-JWT-9f3",
            enabled_sources="hackernews,rss",
        )
        now = datetime.now(tz=UTC)
        mock_session = self._session(last_run_at=now, runs=[], freshness_rows=[])
        resp = await self._get(api_client, mock_session, sentinel_settings)

        assert resp.status_code == 200
        assert "9f3" not in resp.text
        codes = [a["code"] for a in resp.json()]
        assert "classifier_keyword_only" in codes

    async def test_no_cache_control_header(self, api_client: AsyncClient):
        now = datetime.now(tz=UTC)
        mock_session = self._session(last_run_at=now, runs=[], freshness_rows=[])
        resp = await self._get(api_client, mock_session, Settings(openai_api_key="sk-test"))

        assert "cache-control" not in resp.headers

    def test_fixture_matches_schema(self):
        """tests/fixtures/admin_health_sample.json is the same file the capture script uses."""
        raw = json.loads((_FIXTURES_DIR / "admin_health_sample.json").read_text())
        alerts = TypeAdapter(list[HealthAlert]).validate_python(raw)
        assert [a.code for a in alerts] == ["runs_storing_nothing", "classifier_keyword_only"]
        assert alerts[0].severity == "critical"
        assert alerts[1].severity == "warning"
        assert alerts[1].since is None
