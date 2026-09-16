"""RAG retriever — vector similarity search over news items."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import get_settings
from src.core.logging import get_logger
from src.core.models import ItemEmbedding, NewsItem
from src.core.queries import day_end_exclusive, day_start, effective_date, force_exact_scan
from src.rag.embeddings import EmbeddingService

logger = get_logger(__name__)

_DEFAULT_RECENCY_DAYS = 30


class EmbeddingUnavailableError(RuntimeError):
    """The embedding provider call failed; the caller decides how to respond.

    Decision (Paul): fail loud everywhere, not just where a caller happens to
    check for it — /api/search/semantic maps this to 503 EMBEDDING_UNAVAILABLE
    instead of silently returning []. See finding 1 of the 2026-09-16 review.
    """


class Retriever:
    """Retrieve relevant news items by exact pgvector cosine distance.

    By default searches recent items first and falls back to the full range if
    there are not enough results; ``recency_days=None`` ranks the full range directly.
    """

    def __init__(self, embedding_service: EmbeddingService | None = None) -> None:
        self._embed = embedding_service or EmbeddingService()

    async def retrieve(
        self,
        session: AsyncSession,
        query: str,
        *,
        limit: int = 5,
        topic: str | None = None,
        source: str | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
        recency_days: int | None = _DEFAULT_RECENCY_DAYS,
    ) -> list[NewsItem]:
        """Find the top-K most similar news items to the query.

        Filters (topic, source, inclusive date range) always apply. With
        ``recency_days`` set, searches the last ``recency_days`` first and falls back
        to the full filtered range if fewer than ``limit`` results are found.
        """
        if not query.strip():
            return []

        try:
            query_vec = await self._embed.embed_text(query)
        except Exception as exc:
            logger.error("retriever_embed_failed", exc_info=True)
            raise EmbeddingUnavailableError(
                "Semantic search unavailable: the query could not be embedded"
            ) from exc

        await force_exact_scan(session)

        if recency_days is None:
            return await self._search(
                session,
                query_vec,
                limit,
                topic=topic,
                source=source,
                date_from=date_from,
                date_to=date_to,
                since=None,
            )

        since = datetime.now(tz=UTC) - timedelta(days=recency_days)
        items = await self._search(
            session,
            query_vec,
            limit,
            topic=topic,
            source=source,
            date_from=date_from,
            date_to=date_to,
            since=since,
        )

        # Fallback to full range if not enough recent results
        if len(items) < limit:
            logger.info(
                "retriever_recency_fallback",
                recent_count=len(items),
                limit=limit,
                recency_days=recency_days,
            )
            items = await self._search(
                session,
                query_vec,
                limit,
                topic=topic,
                source=source,
                date_from=date_from,
                date_to=date_to,
                since=None,
            )

        return items

    async def _search(
        self,
        session: AsyncSession,
        query_vec: list[float],
        limit: int,
        *,
        topic: str | None,
        source: str | None,
        date_from: date | None,
        date_to: date | None,
        since: datetime | None,
    ) -> list[NewsItem]:
        """Execute a similarity search with optional filters."""
        settings = get_settings()
        stmt = (
            select(NewsItem)
            .join(ItemEmbedding, NewsItem.id == ItemEmbedding.item_id)
            .where(ItemEmbedding.model == settings.embedding_model)
            .order_by(ItemEmbedding.embedding.cosine_distance(query_vec))
            .limit(limit)
        )

        if topic:
            stmt = stmt.where(NewsItem.topic == topic)
        if source:
            stmt = stmt.where(NewsItem.source == source)
        if date_from:
            stmt = stmt.where(effective_date >= day_start(date_from))
        if date_to:
            stmt = stmt.where(effective_date < day_end_exclusive(date_to))
        if since:
            stmt = stmt.where(effective_date >= since)

        result = await session.execute(stmt)
        return list(result.scalars().all())
