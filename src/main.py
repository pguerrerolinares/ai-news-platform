"""CLI entry point for running the pipeline."""

from __future__ import annotations

import asyncio
import sys

from src.core.database import close_db, get_session_factory, init_db
from src.core.logging import get_logger, setup_logging
from src.pipeline.pipeline import run_pipeline

logger = get_logger(__name__)


async def main() -> int:
    """Run the daily news pipeline."""
    setup_logging()
    logger.info("pipeline_cli_start")

    await init_db()
    try:
        factory = get_session_factory()
        async with factory() as session:
            success = await run_pipeline(session)
            return 0 if success else 1
    except Exception as exc:
        logger.error("pipeline_cli_failed", error=str(exc))
        return 1
    finally:
        await close_db()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
