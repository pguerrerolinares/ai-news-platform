"""Tests for src.pipeline.scheduler -- APScheduler integration."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest


class TestCreateScheduler:
    """Verify scheduler creation and job configuration."""

    def test_creates_scheduler_with_jobs(self):
        from src.core.config import Settings
        from src.pipeline.scheduler import create_scheduler

        settings = Settings(
            scheduler_enabled=True,
        )
        with patch("src.pipeline.scheduler.get_settings", return_value=settings):
            scheduler = create_scheduler()

        jobs = scheduler.get_jobs()
        assert len(jobs) == 6
        job_ids = {j.id for j in jobs}
        assert "tier1_hn" in job_ids
        assert "tier1b_hn_leading" in job_ids
        assert "tier2_rss_gh_hf_ws" in job_ids
        assert "tier2b_github_search" in job_ids
        assert "tier3_arxiv" in job_ids
        assert "otp_cleanup" in job_ids

    def test_scheduler_not_created_when_disabled(self):
        from src.core.config import Settings
        from src.pipeline.scheduler import create_scheduler

        settings = Settings(
            scheduler_enabled=False,
        )
        with patch("src.pipeline.scheduler.get_settings", return_value=settings):
            scheduler = create_scheduler()

        assert scheduler is None


class TestOtpCleanupJob:
    """Verify OTP cleanup job is registered and works."""

    def test_scheduler_includes_otp_cleanup_job(self):
        from src.core.config import Settings
        from src.pipeline.scheduler import create_scheduler

        settings = Settings(
            scheduler_enabled=True,
        )
        with patch("src.pipeline.scheduler.get_settings", return_value=settings):
            scheduler = create_scheduler()

        assert scheduler is not None
        job_ids = [j.id for j in scheduler.get_jobs()]
        assert "otp_cleanup" in job_ids

    @pytest.mark.asyncio
    async def test_cleanup_expired_otps_executes(self):
        from src.pipeline.scheduler import cleanup_expired_otps

        mock_result = AsyncMock()
        mock_result.rowcount = 5

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.commit = AsyncMock()

        from contextlib import asynccontextmanager

        @asynccontextmanager
        async def mock_get_session():
            yield mock_session

        with patch("src.pipeline.scheduler.get_async_session", mock_get_session):
            await cleanup_expired_otps()

        mock_session.execute.assert_called_once()
        mock_session.commit.assert_called_once()


class TestRunScheduledPipeline:
    """Verify run_scheduled_pipeline creates session and runs pipeline."""

    @pytest.mark.asyncio
    async def test_creates_session_and_runs_pipeline(self):
        from src.pipeline.scheduler import run_scheduled_pipeline

        mock_session = AsyncMock()
        mock_session_cm = AsyncMock()
        mock_session_cm.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_cm.__aexit__ = AsyncMock(return_value=False)

        with (
            patch("src.pipeline.scheduler.get_async_session", return_value=mock_session_cm),
            patch("src.pipeline.scheduler.run_pipeline", new_callable=AsyncMock) as mock_run,
        ):
            await run_scheduled_pipeline(sources=["hackernews", "reddit"])

        mock_run.assert_called_once_with(
            mock_session, sources=["hackernews", "reddit"], since_hours=None
        )

    @pytest.mark.asyncio
    async def test_catches_exceptions_and_logs(self):
        from src.pipeline.scheduler import run_scheduled_pipeline

        mock_session = AsyncMock()
        mock_session_cm = AsyncMock()
        mock_session_cm.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_cm.__aexit__ = AsyncMock(return_value=False)

        with (
            patch("src.pipeline.scheduler.get_async_session", return_value=mock_session_cm),
            patch(
                "src.pipeline.scheduler.run_pipeline",
                new_callable=AsyncMock,
                side_effect=RuntimeError("DB down"),
            ),
        ):
            # Should NOT raise
            await run_scheduled_pipeline(sources=["hackernews"])


class TestSchedulerSinceHours:
    """Verify scheduler passes per-tier since_hours to run_pipeline."""

    @pytest.mark.asyncio
    async def test_run_scheduled_pipeline_passes_since_hours(self):
        from src.pipeline.scheduler import run_scheduled_pipeline

        mock_session = AsyncMock()
        mock_session_cm = AsyncMock()
        mock_session_cm.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_cm.__aexit__ = AsyncMock(return_value=False)

        with (
            patch("src.pipeline.scheduler.get_async_session", return_value=mock_session_cm),
            patch("src.pipeline.scheduler.run_pipeline", new_callable=AsyncMock) as mock_run,
        ):
            await run_scheduled_pipeline(sources=["hackernews", "reddit"], since_hours=1)

        mock_run.assert_called_once_with(
            mock_session, sources=["hackernews", "reddit"], since_hours=1
        )
