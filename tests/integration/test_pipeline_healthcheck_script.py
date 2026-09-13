"""Integration tests for scripts/pipeline_healthcheck.py -- the actual Docker
HEALTHCHECK entrypoint for pipeline-cron.

Runs the script as a real subprocess (as Docker would) against a scratch
database, so exit codes are verified end-to-end rather than just the
underlying query helper. Uses its own scratch DB, created and dropped here
(not ainews_test, which the
`db_session` fixture in this package's conftest creates/drops tables on)
because a subprocess needs *committed* rows -- the savepoint-rollback
isolation the shared fixture relies on is invisible across connections.
"""

from __future__ import annotations

import os
import subprocess
import sys
import uuid
from collections.abc import AsyncGenerator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import asyncpg
import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from src.core.models import Base

pytestmark = [pytest.mark.integration, pytest.mark.asyncio(loop_scope="session")]

_SCRATCH_DB = "ainews_healthcheck_test"
# Credentials/host come from the integration env (tests/integration/conftest.py
# sets DATABASE_URL_SYNC by default; CI overrides it), only the DB name changes.
_BASE_URL = make_url(os.environ["DATABASE_URL_SYNC"])
_MAINTENANCE_DSN = _BASE_URL.set(database="postgres").render_as_string(hide_password=False)
_SCRATCH_DATABASE_URL_SYNC = _BASE_URL.set(database=_SCRATCH_DB).render_as_string(
    hide_password=False
)
_SCRATCH_DATABASE_URL = _BASE_URL.set(
    drivername="postgresql+asyncpg", database=_SCRATCH_DB
).render_as_string(hide_password=False)
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent


async def _admin_execute(*statements: str) -> None:
    conn = await asyncpg.connect(_MAINTENANCE_DSN)
    try:
        await conn.execute(
            "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
            "WHERE datname = $1 AND pid <> pg_backend_pid()",
            _SCRATCH_DB,
        )
        for statement in statements:
            await conn.execute(statement)
    finally:
        await conn.close()


@pytest_asyncio.fixture(loop_scope="session")
async def scratch_engine() -> AsyncGenerator[AsyncEngine, None]:
    """Engine on a scratch DB created (with the ORM schema) and dropped per test."""
    # _SCRATCH_DB is a module-level constant; DDL identifiers can't be bound anyway.
    await _admin_execute(
        f'DROP DATABASE IF EXISTS "{_SCRATCH_DB}"', f'CREATE DATABASE "{_SCRATCH_DB}"'
    )
    engine = create_async_engine(_SCRATCH_DATABASE_URL, pool_size=2, max_overflow=0)
    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()
    await _admin_execute(f'DROP DATABASE IF EXISTS "{_SCRATCH_DB}"')


async def _insert_run(engine: AsyncEngine, started_at: datetime) -> None:
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO pipeline_runs "
                "(id, started_at, duration_seconds, status, sources) "
                "VALUES (:id, :started_at, 1.0, 'success', '[]'::jsonb)"
            ),
            {"id": str(uuid.uuid4()), "started_at": started_at},
        )


def _run_healthcheck() -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env["DATABASE_URL"] = _SCRATCH_DATABASE_URL
    env["DATABASE_URL_SYNC"] = _SCRATCH_DATABASE_URL_SYNC
    return subprocess.run(  # noqa: S603
        [sys.executable, "-m", "scripts.pipeline_healthcheck"],
        cwd=_REPO_ROOT,
        env=env,
        capture_output=True,
        timeout=15,
    )


class TestPipelineHealthcheckScript:
    async def test_fresh_run_exits_zero(self, scratch_engine: AsyncEngine):
        await _insert_run(scratch_engine, datetime.now(tz=UTC))

        result = _run_healthcheck()

        assert result.returncode == 0, result.stderr

    async def test_empty_table_exits_one(self, scratch_engine: AsyncEngine):
        result = _run_healthcheck()

        # stderr must be empty: exit 1 here means "no run within threshold",
        # not a crash (a crash also exits 1 but prints to stderr -- see main()).
        assert result.stderr == b"", result.stderr
        assert result.returncode == 1

    async def test_stale_run_exits_one(self, scratch_engine: AsyncEngine):
        stale = datetime.now(tz=UTC) - timedelta(minutes=46)
        await _insert_run(scratch_engine, stale)

        result = _run_healthcheck()

        assert result.stderr == b"", result.stderr
        assert result.returncode == 1
