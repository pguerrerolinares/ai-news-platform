"""APScheduler integration for per-source pipeline scheduling."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy import delete

from src.core.config import get_settings
from src.core.database import get_async_session
from src.core.logging import get_logger
from src.core.models import OtpCode
from src.pipeline.circuit_breaker import CircuitBreaker
from src.pipeline.pipeline import run_pipeline

logger = get_logger(__name__)

# Module-level singleton — state resets on process restart.
# Acceptable: scheduler runs in-process, single instance on VPS.
_circuit_breaker = CircuitBreaker(threshold=3, cooldown_seconds=3600)


async def run_scheduled_pipeline(sources: list[str], since_hours: int | None = None) -> None:
    """Run the pipeline for a specific set of sources.

    Creates its own DB session and catches all exceptions
    so that one failed job does not crash the scheduler.
    Sources with open circuits are skipped until cooldown expires.
    """
    # Filter out sources with open circuits
    active_sources = [s for s in sources if not _circuit_breaker.is_open(s)]
    if not active_sources:
        logger.info("scheduled_pipeline_all_sources_circuit_open", sources=sources)
        return

    logger.info("scheduled_pipeline_start", sources=active_sources)
    try:
        async with get_async_session() as session:
            result = await run_pipeline(session, sources=active_sources, since_hours=since_hours)
            # Record success for all active sources
            if result:
                for source in active_sources:
                    _circuit_breaker.record_success(source)
    except Exception as exc:
        # Pipeline catches per-extractor errors internally; exceptions here
        # are infrastructure-level (DB, network), so penalizing all sources
        # in the tier is correct — the failure is not source-specific.
        logger.error("scheduled_pipeline_failed", sources=active_sources, error=str(exc))
        for source in active_sources:
            _circuit_breaker.record_failure(source)


def create_scheduler() -> AsyncIOScheduler | None:
    """Create and configure the APScheduler instance.

    Returns None if scheduler_enabled is False.
    """
    settings = get_settings()

    if not settings.scheduler_enabled:
        logger.info("scheduler_disabled")
        return None

    scheduler = AsyncIOScheduler()

    # Tier 1: HackerNews + Reddit (every 15 min, extract last 1h)
    scheduler.add_job(
        run_scheduled_pipeline,
        IntervalTrigger(minutes=settings.hn_poll_interval_minutes),
        id="tier1_hn_reddit",
        kwargs={"sources": ["hackernews", "reddit"], "since_hours": 6},
        replace_existing=True,
    )

    # Tier 2: RSS + GitHub + HuggingFace + WebScraper (every 60 min, extract last 3h)
    scheduler.add_job(
        run_scheduled_pipeline,
        IntervalTrigger(minutes=settings.rss_poll_interval_minutes),
        id="tier2_rss_gh_hf_ws",
        kwargs={
            "sources": ["rss", "github", "huggingface", "webscraper"],
            "since_hours": 3,
        },
        replace_existing=True,
    )

    # Tier 3: arXiv (daily, extract last 24h)
    scheduler.add_job(
        run_scheduled_pipeline,
        CronTrigger(hour=settings.arxiv_cron_hour, minute=settings.arxiv_cron_minute),
        id="tier3_arxiv",
        kwargs={"sources": ["arxiv"], "since_hours": 24},
        replace_existing=True,
    )

    logger.info(
        "scheduler_configured",
        tier1_interval=settings.hn_poll_interval_minutes,
        tier2_interval=settings.rss_poll_interval_minutes,
        tier3_cron=f"{settings.arxiv_cron_hour}:{settings.arxiv_cron_minute:02d}",
    )

    # OTP cleanup: daily at 02:00 UTC
    scheduler.add_job(
        cleanup_expired_otps,
        CronTrigger(hour=2, minute=0),
        id="otp_cleanup",
        replace_existing=True,
    )

    return scheduler


async def cleanup_expired_otps() -> None:
    """Purge expired OTP codes older than 1 day."""
    async with get_async_session() as session:
        cutoff = datetime.now(tz=UTC) - timedelta(days=1)
        result = await session.execute(delete(OtpCode).where(OtpCode.expires_at < cutoff))
        await session.commit()
        if result.rowcount:
            logger.info("otp_cleanup_done", deleted=result.rowcount)
