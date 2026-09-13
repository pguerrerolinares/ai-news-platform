"""Pipeline orchestrator — chains composable stages.

extract -> dedup -> seen_filter -> validate -> classify -> score -> validate -> store -> embed
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import get_settings
from src.core.database import get_session_factory
from src.core.logging import get_correlation_id, get_logger, set_correlation_id
from src.core.metrics import (
    items_validated_total,
    items_validation_failed_total,
    pipeline_duration_seconds,
    pipeline_runs_total,
    validation_duration_seconds,
)
from src.core.models import PipelineRun
from src.pipeline.circuit_breaker import CircuitBreaker
from src.pipeline.dedup import deduplicate_items
from src.pipeline.stages.classify import run_classification
from src.pipeline.stages.extract import get_extractors, run_extraction
from src.pipeline.stages.score import run_scoring
from src.pipeline.stages.seen_filter import filter_already_seen
from src.pipeline.stages.store import embed_new_items, save_briefing, store_classified_items
from src.pipeline.validation import validate_extracted_item
from src.validators.credibility import CredibilityValidator

logger = get_logger(__name__)

# Cap on how long the CancelledError handler waits to persist the
# `interrupted` PipelineRun on its own short-lived session (see
# _persist_interrupted_run) before giving up and re-raising anyway.
_INTERRUPTED_RUN_SAVE_TIMEOUT_SECONDS = 5.0


async def _persist_interrupted_run(
    *,
    started_at: datetime,
    duration_seconds: float,
    sources_used: list[str],
    correlation_id: str | None,
) -> None:
    """Persist an ``interrupted`` PipelineRun on a new, independent session.

    Called from run_pipeline's ``CancelledError`` handler, where the
    session passed into run_pipeline may be mid-query when cancelled and is
    unsafe to reuse (#7) -- a fresh session from the factory is used instead.
    """
    factory = get_session_factory()
    async with factory() as new_session:
        new_session.add(
            PipelineRun(
                started_at=started_at,
                duration_seconds=duration_seconds,
                status="interrupted",
                sources=sources_used,
                correlation_id=correlation_id,
            )
        )
        await new_session.commit()


async def run_pipeline(
    session: AsyncSession,
    sources: list[str] | None = None,
    since_hours: int | None = None,
    circuit_breaker: CircuitBreaker | None = None,
) -> bool:
    """Execute the full news pipeline.

    Steps:
    1. Extract from enabled sources (parallel)
    2. Deduplicate by hash (content + URL)
    2.5. Filter already seen (persistent DB dedup)
    3. Pre-validate (reject items without title/URL)
    4. Classify (keyword pre-filter + LLM) + event dedup + variant collapse
    5. Composite scoring
    6. Credibility validation
    7. Store in PostgreSQL
    8. Save daily briefing stats
    9. Generate embeddings

    ``circuit_breaker``, if given, is passed through to the extract stage so
    each source's success/failure is tracked independently (see
    ``src.pipeline.stages.extract.run_extraction``).
    """
    cid = set_correlation_id()
    start = datetime.now(tz=UTC)
    settings = get_settings()

    sources_used: list[str] = []
    logger.info("pipeline_start", correlation_id=cid)

    try:
        # 1. Extract
        extractors = get_extractors(sources=sources)
        sources_used = [e.source_name for e in extractors]
        logger.info("pipeline_extract", sources=sources_used)

        effective_since = (
            since_hours if since_hours is not None else settings.extraction_since_hours
        )
        all_items = await run_extraction(
            extractors, effective_since, circuit_breaker=circuit_breaker
        )
        items_extracted = len(all_items)

        if not all_items:
            logger.warning("pipeline_no_items")
            pipeline_runs_total.labels(status="empty").inc()
            duration = (datetime.now(tz=UTC) - start).total_seconds()
            session.add(
                PipelineRun(
                    started_at=start,
                    duration_seconds=duration,
                    status="empty",
                    sources=sources_used,
                    correlation_id=get_correlation_id(),
                )
            )
            await session.commit()
            return False

        # 2. Dedup
        logger.info("pipeline_dedup", input_count=items_extracted)
        unique_items = deduplicate_items(all_items)
        items_after_dedup = len(unique_items)

        # 2.5. Filter already seen (persistent DB dedup)
        before_seen = len(unique_items)
        unique_items = await filter_already_seen(session, unique_items)
        logger.info("pipeline_seen_filter", count=len(unique_items))

        # 3. Pre-validate
        valid_items = []
        for item in unique_items:
            errors = validate_extracted_item({"title": item.title, "url": item.url})
            if errors:
                for reason in errors:
                    items_validation_failed_total.labels(reason=reason).inc()
                logger.warning(
                    "item_validation_failed",
                    errors=errors,
                    title=item.title[:80] if item.title else None,
                )
            else:
                valid_items.append(item)

        if valid_items != unique_items:
            logger.info(
                "pipeline_validation",
                valid=len(valid_items),
                rejected=len(unique_items) - len(valid_items),
            )

        # 4. Classify + event dedup + variant collapse
        classified = await run_classification(valid_items)
        logger.info("pipeline_classified", count=len(classified))

        # 5. Composite scoring
        scored = run_scoring(classified)
        logger.info("pipeline_scoring", count=len(scored))

        # 6. Credibility validation
        with validation_duration_seconds.time():
            validator = CredibilityValidator()
            validated = await validator.validate(scored)
        items_validated_total.inc(len(validated))
        logger.info("pipeline_validated", count=len(validated))

        # 7. Store
        items_stored = await store_classified_items(session, validated)

        # 8. Briefing
        trending_count = sum(1 for i in validated if i.trending)
        duration = (datetime.now(tz=UTC) - start).total_seconds()
        await save_briefing(
            session,
            items_extracted=items_extracted,
            items_after_dedup=items_after_dedup,
            items_stored=items_stored,
            sources_used=sources_used,
            duration_seconds=duration,
            trending_count=trending_count,
        )

        # 9. Embeddings
        if settings.embedding_api_key:
            embedded_count = await embed_new_items(session)
            logger.info("pipeline_embeddings", count=embedded_count)

        pipeline_runs_total.labels(status="success").inc()
        pipeline_duration_seconds.observe(duration)

        logger.info(
            "pipeline_complete",
            items_extracted=items_extracted,
            items_classified=len(classified),
            items_validated=len(validated),
            items_stored=items_stored,
            duration_seconds=round(duration, 1),
            sources=sources_used,
        )

        # Persist pipeline run stats
        items_seen_filtered = before_seen - len(unique_items)
        session.add(
            PipelineRun(
                started_at=start,
                duration_seconds=duration,
                status="success",
                sources=sources_used,
                items_extracted=items_extracted,
                items_after_dedup=items_after_dedup,
                items_seen_filtered=items_seen_filtered,
                items_classified=len(classified),
                items_validated=len(validated),
                items_stored=items_stored,
                correlation_id=get_correlation_id(),
            )
        )
        await session.commit()

        return True

    except asyncio.CancelledError:
        # BaseException, not Exception -- deliberately not merged with the
        # handler below. A SIGTERM during deploy lands here mid-await; the
        # session passed into run_pipeline may be mid-query, so persistence
        # uses its own short-lived session (#7) and this always re-raises:
        # cancellation must never look like a successful run.
        duration = (datetime.now(tz=UTC) - start).total_seconds()
        pipeline_runs_total.labels(status="interrupted").inc()
        logger.warning("pipeline_interrupted", duration_seconds=round(duration, 1))
        try:
            await asyncio.wait_for(
                _persist_interrupted_run(
                    started_at=start,
                    duration_seconds=duration,
                    sources_used=sources_used,
                    correlation_id=get_correlation_id(),
                ),
                timeout=_INTERRUPTED_RUN_SAVE_TIMEOUT_SECONDS,
            )
        except Exception:
            logger.warning("pipeline_interrupted_run_save_failed", exc_info=True)
        raise

    except Exception as exc:
        duration = (datetime.now(tz=UTC) - start).total_seconds()
        pipeline_runs_total.labels(status="error").inc()
        logger.error("pipeline_failed", error=str(exc), duration_seconds=round(duration, 1))
        try:
            # The exception may have come from a DB constraint violation,
            # which leaves the session's transaction aborted -- Postgres
            # refuses any further statement (including this commit) until
            # it's rolled back. Without this, the error PipelineRun below
            # silently fails to save too, and the run vanishes entirely (#4).
            await session.rollback()
            session.add(
                PipelineRun(
                    started_at=start,
                    duration_seconds=duration,
                    status="error",
                    sources=sources_used,
                    error_message=str(exc)[:500],
                    correlation_id=get_correlation_id(),
                )
            )
            await session.commit()
        except Exception:
            logger.warning("pipeline_run_save_failed", exc_info=True)
        raise
