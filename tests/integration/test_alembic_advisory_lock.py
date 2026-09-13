"""Integration test for the Alembic advisory lock in alembic/env.py.

Two concurrent redeploys both running `alembic upgrade head` against a fresh
(unmigrated) database used to race on DDL (finding #11). The lock in
run_migrations_online() should serialize them: one applies all migrations
while the other blocks on pg_advisory_lock, then finds the DB already at
head and exits cleanly -- both processes exit 0, neither errors out from a
DDL race.

Uses its own scratch database (created and dropped by this test), not
the shared test databases, since it needs to start from zero (no
alembic_version table) to exercise the race.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import asyncpg
import pytest
from sqlalchemy.engine import make_url

pytestmark = [pytest.mark.integration, pytest.mark.asyncio(loop_scope="session")]

_SCRATCH_DB = "ainews_alembic_lock_test"
# Credentials/host come from the integration env (tests/integration/conftest.py
# sets DATABASE_URL_SYNC by default; CI overrides it), only the DB name changes.
_BASE_URL = make_url(os.environ["DATABASE_URL_SYNC"])
_MAINTENANCE_DSN = _BASE_URL.set(database="postgres").render_as_string(hide_password=False)
_SCRATCH_URL_SYNC = _BASE_URL.set(database=_SCRATCH_DB).render_as_string(hide_password=False)
_SCRATCH_URL_ASYNC = (
    _BASE_URL.set(drivername="postgresql+asyncpg", database=_SCRATCH_DB)
).render_as_string(hide_password=False)
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent


async def _terminate_scratch_db_connections(conn: asyncpg.Connection) -> None:
    await conn.execute(
        "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
        "WHERE datname = $1 AND pid <> pg_backend_pid()",
        _SCRATCH_DB,
    )


async def _recreate_scratch_db() -> None:
    conn = await asyncpg.connect(_MAINTENANCE_DSN)
    try:
        await _terminate_scratch_db_connections(conn)
        # _SCRATCH_DB is a module-level constant, not user input; DDL
        # identifiers can't be bound as query parameters either way.
        await conn.execute(f'DROP DATABASE IF EXISTS "{_SCRATCH_DB}"')
        await conn.execute(f'CREATE DATABASE "{_SCRATCH_DB}"')
    finally:
        await conn.close()

    conn = await asyncpg.connect(_SCRATCH_URL_SYNC)
    try:
        await conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
    finally:
        await conn.close()


async def _drop_scratch_db() -> None:
    conn = await asyncpg.connect(_MAINTENANCE_DSN)
    try:
        await _terminate_scratch_db_connections(conn)
        await conn.execute(f'DROP DATABASE IF EXISTS "{_SCRATCH_DB}"')
    finally:
        await conn.close()


def _alembic_upgrade_env() -> dict[str, str]:
    env = dict(os.environ)
    env["DATABASE_URL_SYNC"] = _SCRATCH_URL_SYNC
    env["DATABASE_URL"] = _SCRATCH_URL_ASYNC
    return env


class TestConcurrentAlembicUpgrade:
    async def test_two_concurrent_upgrades_both_succeed(self):
        await _recreate_scratch_db()
        try:
            env = _alembic_upgrade_env()
            cmd = [sys.executable, "-m", "alembic", "upgrade", "head"]
            proc_a = subprocess.Popen(  # noqa: S603
                cmd, cwd=_REPO_ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE
            )
            proc_b = subprocess.Popen(  # noqa: S603
                cmd, cwd=_REPO_ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE
            )

            out_a, err_a = proc_a.communicate(timeout=60)
            out_b, err_b = proc_b.communicate(timeout=60)

            assert proc_a.returncode == 0, err_a.decode()
            assert proc_b.returncode == 0, err_b.decode()

            # Sanity: migrations actually landed (pipeline_runs is from the
            # last-but-one migration at the time of writing).
            conn = await asyncpg.connect(_SCRATCH_URL_SYNC)
            try:
                exists = await conn.fetchval(
                    "SELECT EXISTS (SELECT 1 FROM information_schema.tables "
                    "WHERE table_name = 'pipeline_runs')"
                )
            finally:
                await conn.close()
            assert exists is True
        finally:
            await _drop_scratch_db()
