"""APScheduler integration for per-source pipeline scheduling."""

from __future__ import annotations

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from src.core.config import get_settings
from src.core.database import get_async_session
from src.core.logging import get_logger
from src.pipeline.pipeline import run_pipeline

logger = get_logger(__name__)


async def run_scheduled_pipeline(sources: list[str]) -> None:
    """Run the pipeline for a specific set of sources.

    Creates its own DB session and catches all exceptions
    so that one failed job does not crash the scheduler.
    """
    logger.info("scheduled_pipeline_start", sources=sources)
    try:
        async with get_async_session() as session:
            await run_pipeline(session, sources=sources)
    except Exception as exc:
        logger.error("scheduled_pipeline_failed", sources=sources, error=str(exc))


def create_scheduler() -> AsyncIOScheduler | None:
    """Create and configure the APScheduler instance.

    Returns None if scheduler_enabled is False.
    """
    settings = get_settings()

    if not settings.scheduler_enabled:
        logger.info("scheduler_disabled")
        return None

    scheduler = AsyncIOScheduler()

    # Tier 1: HackerNews + Reddit (every 15 min)
    scheduler.add_job(
        run_scheduled_pipeline,
        IntervalTrigger(minutes=settings.hn_poll_interval_minutes),
        id="tier1_hn_reddit",
        kwargs={"sources": ["hackernews", "reddit"]},
        replace_existing=True,
    )

    # Tier 2: RSS + GitHub + HuggingFace (every 60 min)
    scheduler.add_job(
        run_scheduled_pipeline,
        IntervalTrigger(minutes=settings.rss_poll_interval_minutes),
        id="tier2_rss_gh_hf",
        kwargs={"sources": ["rss", "github", "huggingface"]},
        replace_existing=True,
    )

    # Tier 3: arXiv (daily at configured hour)
    scheduler.add_job(
        run_scheduled_pipeline,
        CronTrigger(hour=settings.arxiv_cron_hour, minute=settings.arxiv_cron_minute),
        id="tier3_arxiv",
        kwargs={"sources": ["arxiv"]},
        replace_existing=True,
    )

    logger.info(
        "scheduler_configured",
        tier1_interval=settings.hn_poll_interval_minutes,
        tier2_interval=settings.rss_poll_interval_minutes,
        tier3_cron=f"{settings.arxiv_cron_hour}:{settings.arxiv_cron_minute:02d}",
    )

    return scheduler
