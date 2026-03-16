"""Storage stage — persist classified items, briefing stats, and embeddings."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import func, select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.classifiers.base import ClassifiedItem
from src.core.config import get_settings
from src.core.logging import get_logger
from src.core.metrics import items_stored_total
from src.core.models import DailyBriefing, ItemEmbedding, NewsItem
from src.rag.embeddings import EmbeddingService

logger = get_logger(__name__)

_BATCH_COMMIT_SIZE = 25


async def store_classified_items(session: AsyncSession, items: list[ClassifiedItem]) -> int:
    """Store classified items in PostgreSQL with batch commits.

    Items WITH a URL: upsert on url_hash — update scores if new values are higher.
    Items WITHOUT a URL: insert with on_conflict_do_nothing on content_hash.
    """
    if not items:
        return 0

    stored = 0
    for i, ci in enumerate(items):
        item = ci.item
        base_stmt = insert(NewsItem).values(
            title=item.title,
            url=item.url,
            source=item.source,
            published_at=item.published_at,
            content_hash=item.content_hash,
            url_hash=item.url_hash,
            full_text=item.text,
            author=item.author,
            score=item.score,
            source_created_at=item.source_created_at,
            metadata_=item.metadata,
            topic=ci.topic,
            relevance_score=ci.relevance_score,
            credibility_score=ci.credibility_score,
            summary=ci.summary,
            priority=ci.priority,
            trending=ci.trending,
            dev_value_score=ci.dev_value_score,
            composite_score=ci.composite_score,
        )

        if item.url_hash is not None:
            # Upsert: update scores only when new values are strictly higher.
            # WHERE clause ensures rowcount=0 for exact duplicates (no-op update).
            stmt = base_stmt.on_conflict_do_update(
                index_elements=["url_hash"],
                index_where=text("url_hash IS NOT NULL"),
                set_={
                    "composite_score": func.greatest(
                        NewsItem.composite_score, base_stmt.excluded.composite_score
                    ),
                    "score": func.greatest(NewsItem.score, base_stmt.excluded.score),
                    "relevance_score": func.greatest(
                        NewsItem.relevance_score, base_stmt.excluded.relevance_score
                    ),
                },
                where=(
                    (base_stmt.excluded.composite_score > NewsItem.composite_score)
                    | (base_stmt.excluded.score > NewsItem.score)
                    | (base_stmt.excluded.relevance_score > NewsItem.relevance_score)
                ),
            )
        else:
            stmt = base_stmt.on_conflict_do_nothing(index_elements=["content_hash"])

        result = await session.execute(stmt)
        if result.rowcount and result.rowcount > 0:
            stored += 1

        if (i + 1) % _BATCH_COMMIT_SIZE == 0:
            await session.commit()

    await session.commit()
    items_stored_total.inc(stored)
    logger.info("items_stored", count=stored, skipped=len(items) - stored)
    return stored


async def save_briefing(
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

    existing = await session.execute(select(DailyBriefing).where(DailyBriefing.date == today))
    briefing = existing.scalar_one_or_none()

    if briefing:
        briefing.total_items = (briefing.total_items or 0) + items_stored
        briefing.items_extracted = items_extracted
        briefing.items_after_dedup = items_after_dedup
        briefing.items_filtered = items_stored
        briefing.trending_count = trending_count
        briefing.duration_seconds = duration_seconds
        existing_sources = set(
            briefing.sources_used.get("sources", []) if briefing.sources_used else []
        )
        existing_sources.update(sources_used)
        briefing.sources_used = {"sources": sorted(existing_sources)}
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


async def embed_new_items(
    session: AsyncSession,
    embed_service: EmbeddingService | None = None,
) -> int:
    """Generate embeddings for items that don't have one yet."""
    settings = get_settings()

    if embed_service is None:
        embed_service = EmbeddingService()

    model_name = settings.embedding_model

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

        rows = [
            {"item_id": item.id, "model": model_name, "embedding": embedding}
            for item, embedding in zip(items, embeddings, strict=True)
        ]
        stmt = (
            insert(ItemEmbedding)
            .values(rows)
            .on_conflict_do_nothing(index_elements=["item_id", "model"])
        )
        await session.execute(stmt)
        await session.commit()
        logger.info("embed_items_stored", count=len(items))
        return len(items)

    except Exception as exc:
        from src.core.metrics import embedding_failures_total

        embedding_failures_total.inc()
        logger.error("embed_items_failed", error=str(exc), item_count=len(items))
        await session.rollback()
        return 0
