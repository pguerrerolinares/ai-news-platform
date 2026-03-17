"""Pipeline orchestrator — chains composable stages.

extract -> dedup -> validate -> classify -> score -> validate -> store -> notify -> embed
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import get_settings
from src.core.logging import get_correlation_id, get_logger, set_correlation_id
from src.core.metrics import (
    items_validated_total,
    items_validation_failed_total,
    pipeline_duration_seconds,
    pipeline_runs_total,
    validation_duration_seconds,
)
from src.core.models import PipelineRun
from src.notifiers.alerts import AlertService
from src.pipeline.dedup import deduplicate_items
from src.pipeline.stages.classify import run_classification
from src.pipeline.stages.extract import get_extractors, run_extraction
from src.pipeline.stages.notify import run_notification
from src.pipeline.stages.score import run_scoring
from src.pipeline.stages.seen_filter import filter_already_seen
from src.pipeline.stages.store import embed_new_items, save_briefing, store_classified_items
from src.pipeline.validation import validate_extracted_item
from src.validators.credibility import CredibilityValidator

logger = get_logger(__name__)


async def run_pipeline(
    session: AsyncSession,
    sources: list[str] | None = None,
    since_hours: int | None = None,
) -> bool:
    """Execute the full news pipeline.

    Steps:
    1. Extract from enabled sources (parallel)
    2. Deduplicate by hash (content + URL)
    3. Pre-validate (reject items without title/URL)
    4. Classify (LLM or keyword) + event dedup + variant collapse
    5. Composite scoring
    6. Credibility validation
    7. Store in PostgreSQL
    8. Save daily briefing stats
    9. Notify via Telegram
    10. Generate embeddings
    """
    cid = set_correlation_id()
    start = datetime.now(tz=UTC)
    alerts = AlertService()
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
        all_items = await run_extraction(extractors, effective_since, alerts=alerts)
        items_extracted = len(all_items)

        if not all_items:
            logger.warning("pipeline_no_items")
            await alerts.pipeline_failure("No items extracted from any source", stage="extraction")
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

        # 9. Notify
        await run_notification(validated, duration_seconds=duration)

        # 10. Embeddings
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

        await alerts.pipeline_success(
            items_count=items_stored,
            duration_seconds=duration,
            sources=sources_used,
        )
        return True

    except Exception as exc:
        duration = (datetime.now(tz=UTC) - start).total_seconds()
        pipeline_runs_total.labels(status="error").inc()
        logger.error("pipeline_failed", error=str(exc), duration_seconds=round(duration, 1))
        try:
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
        await alerts.pipeline_failure(str(exc), stage="unknown")
        raise
