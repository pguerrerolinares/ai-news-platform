"""Full news pipeline with classification, validation, and notification.

extract -> dedup -> classify -> event dedup -> validate -> store -> briefing -> notify

Milestone 1: HackerNews only, no classification/validation.
Milestone 2: Full pipeline with all sources + LLM classification.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.classifiers.base import ClassifiedItem
from src.classifiers.event_dedup import deduplicate_events
from src.classifiers.keyword import KeywordClassifier
from src.classifiers.llm import LLMClassifier
from src.core.config import get_settings
from src.core.logging import get_logger, set_correlation_id
from src.core.metrics import (
    classification_duration_seconds,
    items_classified_total,
    items_stored_total,
    items_validated_total,
    items_validation_failed_total,
    notification_duration_seconds,
    notification_errors_total,
    pipeline_duration_seconds,
    pipeline_runs_total,
    validation_duration_seconds,
)
from src.core.models import DailyBriefing, ItemEmbedding, NewsItem
from src.extractors.arxiv import ArxivExtractor
from src.extractors.base import BaseExtractor, ExtractedItem
from src.extractors.github import GitHubExtractor
from src.extractors.hackernews import HackerNewsExtractor
from src.extractors.huggingface import HuggingFaceExtractor
from src.extractors.reddit import RedditExtractor
from src.extractors.rss import RSSExtractor
from src.notifiers.alerts import AlertService
from src.notifiers.telegram import TelegramNotifier
from src.pipeline.dedup import deduplicate_items
from src.pipeline.validation import validate_extracted_item
from src.rag.embeddings import EmbeddingService
from src.validators.credibility import CredibilityValidator

logger = get_logger(__name__)


def _get_extractors(sources: list[str] | None = None) -> list[BaseExtractor]:
    """Build list of enabled extractors, optionally filtered by source names."""
    settings = get_settings()
    enabled = settings.enabled_sources_list

    # If sources filter is provided, intersect with enabled sources
    if sources is not None:
        enabled = [s for s in enabled if s in sources]

    extractors: list[BaseExtractor] = []

    if "hackernews" in enabled:
        extractors.append(HackerNewsExtractor())

    if "arxiv" in enabled:
        extractors.append(ArxivExtractor())

    if "reddit" in enabled:
        extractors.append(RedditExtractor())

    if "rss" in enabled:
        extractors.append(RSSExtractor())

    if "github" in enabled:
        extractors.append(GitHubExtractor())

    if "huggingface" in enabled:
        extractors.append(HuggingFaceExtractor())

    return extractors


async def _extract_all(
    extractors: list[BaseExtractor],
    alerts: AlertService | None = None,
) -> list[ExtractedItem]:
    """Run all extractors concurrently and collect results."""
    settings = get_settings()
    if alerts is None:
        alerts = AlertService()

    async def _run_one(extractor: BaseExtractor) -> list[ExtractedItem]:
        try:
            since = settings.extraction_since_hours
            items = await extractor.extract(since_hours=since)
            logger.info(
                "extractor_result",
                source=extractor.source_name,
                count=len(items),
            )
            if not items:
                await alerts.extractor_empty(extractor.source_name)
            return items
        except Exception as exc:
            logger.error(
                "extractor_failed",
                source=extractor.source_name,
                error=str(exc),
            )
            await alerts.extractor_empty(extractor.source_name)
            return []

    results = await asyncio.gather(*[_run_one(ext) for ext in extractors])

    all_items: list[ExtractedItem] = []
    for result in results:
        all_items.extend(result)

    return all_items


_BATCH_COMMIT_SIZE = 25


async def _store_classified_items(session: AsyncSession, items: list[ClassifiedItem]) -> int:
    """Store classified items in PostgreSQL with batch commits.

    Commits every ``_BATCH_COMMIT_SIZE`` items to avoid losing all work
    if a late commit fails.  Returns count of new items inserted.
    """
    if not items:
        return 0

    stored = 0
    for i, ci in enumerate(items):
        item = ci.item  # ExtractedItem
        stmt = (
            insert(NewsItem)
            .values(
                title=item.title,
                url=item.url,
                source=item.source,
                published_at=item.published_at,
                content_hash=item.content_hash,
                url_hash=item.url_hash,
                full_text=item.text,
                author=item.author,
                score=item.score,
                metadata_=item.metadata,
                # Classification fields
                topic=ci.topic,
                relevance_score=ci.relevance_score,
                credibility_score=ci.credibility_score,
                summary=ci.summary,
                priority=ci.priority,
                trending=ci.trending,
                dev_value_score=ci.dev_value_score,
            )
            .on_conflict_do_nothing(index_elements=["content_hash"])
        )
        result = await session.execute(stmt)
        if result.rowcount and result.rowcount > 0:
            stored += 1

        if (i + 1) % _BATCH_COMMIT_SIZE == 0:
            await session.commit()

    await session.commit()
    items_stored_total.inc(stored)
    logger.info("items_stored", count=stored, skipped=len(items) - stored)
    return stored


async def _save_briefing(
    session: AsyncSession,
    *,
    items_extracted: int,
    items_after_dedup: int,
    items_stored: int,
    sources_used: list[str],
    duration_seconds: float,
    trending_count: int = 0,
) -> None:
    """Upsert the daily briefing record."""
    today = datetime.now(tz=UTC).date()

    # Check if briefing already exists for today
    existing = await session.execute(select(DailyBriefing).where(DailyBriefing.date == today))
    briefing = existing.scalar_one_or_none()

    if briefing:
        # Accumulate totals across multiple pipeline runs per day
        briefing.total_items = (briefing.total_items or 0) + items_stored
        briefing.items_extracted = (briefing.items_extracted or 0) + items_extracted
        briefing.items_after_dedup = (briefing.items_after_dedup or 0) + items_after_dedup
        briefing.items_filtered = (briefing.items_filtered or 0) + items_stored
        briefing.trending_count = (briefing.trending_count or 0) + trending_count
        briefing.duration_seconds = (briefing.duration_seconds or 0) + duration_seconds
        briefing.sources_used = {"sources": sources_used}
    else:
        session.add(
            DailyBriefing(
                date=today,
                total_items=items_stored,
                items_extracted=items_extracted,
                items_after_dedup=items_after_dedup,
                items_filtered=items_stored,
                trending_count=trending_count,
                duration_seconds=duration_seconds,
                sources_used={"sources": sources_used},
            )
        )

    await session.commit()


async def _embed_new_items(
    session: AsyncSession,
    embed_service: EmbeddingService | None = None,
) -> int:
    """Generate embeddings for items that don't have one yet.

    Returns count of newly embedded items. Errors are logged but not raised.
    """
    settings = get_settings()

    if embed_service is None:
        embed_service = EmbeddingService()

    model_name = settings.embedding_model

    # Find items without embeddings for this model
    subquery = select(ItemEmbedding.item_id).where(ItemEmbedding.model == model_name)
    stmt = select(NewsItem).where(~NewsItem.id.in_(subquery))
    result = await session.execute(stmt)
    items = list(result.scalars().all())

    if not items:
        logger.info("embed_no_new_items")
        return 0

    try:
        texts = [embed_service.prepare_text(item.title, item.summary) for item in items]
        embeddings = await embed_service.embed_batch(texts)

        for item, embedding in zip(items, embeddings, strict=True):
            session.add(
                ItemEmbedding(
                    item_id=item.id,
                    model=model_name,
                    embedding=embedding,
                )
            )

        await session.commit()
        logger.info("embed_items_stored", count=len(items))
        return len(items)

    except Exception as exc:
        from src.core.metrics import embedding_failures_total
        embedding_failures_total.inc()
        logger.error("embed_items_failed", error=str(exc), item_count=len(items))
        await session.rollback()
        return 0


async def run_pipeline(session: AsyncSession, sources: list[str] | None = None) -> bool:
    """Execute the full news pipeline.

    Steps:
    1. Extract from enabled sources (parallel)
    2. Deduplicate by hash (content + URL)
    3. Classify (LLM or keyword fallback)
    4. Event dedup (only if LLM available)
    5. Validate (credibility, engagement, tone, similarity)
    6. Store classified items in PostgreSQL
    7. Save daily briefing stats
    8. Notify via Telegram (if configured)
    """
    cid = set_correlation_id()
    start = datetime.now(tz=UTC)
    alerts = AlertService()
    settings = get_settings()

    logger.info("pipeline_start", correlation_id=cid)

    try:
        # 1. Extract
        extractors = _get_extractors(sources=sources)
        sources_used = [e.source_name for e in extractors]
        logger.info("pipeline_extract", sources=sources_used)

        all_items = await _extract_all(extractors, alerts=alerts)
        items_extracted = len(all_items)

        if not all_items:
            logger.warning("pipeline_no_items")
            await alerts.pipeline_failure("No items extracted from any source", stage="extraction")
            pipeline_runs_total.labels(status="empty").inc()
            return False

        # 2. Dedup
        logger.info("pipeline_dedup", input_count=items_extracted)
        unique_items = deduplicate_items(all_items)
        items_after_dedup = len(unique_items)

        # 2b. Pre-storage validation (reject items without title/URL)
        valid_items: list[ExtractedItem] = []
        for item in unique_items:
            item_dict = {
                "title": item.title,
                "url": item.url,
            }
            errors = validate_extracted_item(item_dict)
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
        unique_items = valid_items

        # 3. Classify
        with classification_duration_seconds.time():
            classifier = LLMClassifier() if settings.openai_api_key else KeywordClassifier()
            classified = await classifier.classify(unique_items)
        items_classified_total.inc(len(classified))
        logger.info("pipeline_classified", count=len(classified))

        # 4. Event dedup (only if LLM available)
        if settings.openai_api_key and len(classified) > 1:
            classified = await deduplicate_events(classified)
            logger.info("pipeline_event_dedup", count=len(classified))

        # 5. Validate
        with validation_duration_seconds.time():
            validator = CredibilityValidator()
            validated = await validator.validate(classified)
        items_validated_total.inc(len(validated))
        logger.info("pipeline_validated", count=len(validated))

        # 6. Store classified items
        items_stored = await _store_classified_items(session, validated)

        # 7. Save briefing
        trending_count = sum(1 for i in validated if i.trending)
        duration = (datetime.now(tz=UTC) - start).total_seconds()
        await _save_briefing(
            session,
            items_extracted=items_extracted,
            items_after_dedup=items_after_dedup,
            items_stored=items_stored,
            sources_used=sources_used,
            duration_seconds=duration,
            trending_count=trending_count,
        )

        # 8. Notify via Telegram
        if settings.telegram_bot_token and settings.telegram_chat_id:
            try:
                with notification_duration_seconds.time():
                    notifier = TelegramNotifier()
                    await notifier.send_briefing(validated, duration_seconds=duration)
            except Exception as exc:
                notification_errors_total.inc()
                logger.warning("notification_failed", error=str(exc))

        # 9. Generate embeddings (if configured)
        if settings.embedding_api_key:
            try:
                embedded_count = await _embed_new_items(session)
                logger.info("pipeline_embeddings", count=embedded_count)
            except Exception as exc:
                from src.core.metrics import embedding_failures_total
                embedding_failures_total.inc()
                logger.error("pipeline_embedding_failed", error=str(exc))

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
        await alerts.pipeline_failure(str(exc), stage="unknown")
        raise
