"""RAG retriever — vector similarity search over news items."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.logging import get_logger
from src.core.models import ItemEmbedding, NewsItem
from src.core.queries import effective_date
from src.rag.embeddings import EmbeddingService

logger = get_logger(__name__)

_DEFAULT_RECENCY_DAYS = 30


class Retriever:
    """Retrieve relevant news items via pgvector cosine similarity.

    Uses a recency filter: searches recent items first, falls back to
    full range if not enough results.
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
        recency_days: int = _DEFAULT_RECENCY_DAYS,
    ) -> list[NewsItem]:
        """Find the top-K most similar news items to the query.

        Searches within the last ``recency_days`` first. If fewer than
        ``limit`` results are found, falls back to the full date range.
        """
        if not query.strip():
            return []

        try:
            query_vec = await self._embed.embed_text(query)
        except Exception:
            logger.error("retriever_embed_failed", exc_info=True)
            return []

        # Try recent items first
        since = datetime.now(tz=UTC) - timedelta(days=recency_days)
        items = await self._search(session, query_vec, limit, topic, since=since)

        # Fallback to full range if not enough recent results
        if len(items) < limit:
            logger.info(
                "retriever_recency_fallback",
                recent_count=len(items),
                limit=limit,
                recency_days=recency_days,
            )
            items = await self._search(session, query_vec, limit, topic, since=None)

        return items

    async def _search(
        self,
        session: AsyncSession,
        query_vec: list[float],
        limit: int,
        topic: str | None,
        *,
        since: datetime | None,
    ) -> list[NewsItem]:
        """Execute a similarity search with optional date filter."""
        stmt = (
            select(NewsItem)
            .join(ItemEmbedding, NewsItem.id == ItemEmbedding.item_id)
            .order_by(ItemEmbedding.embedding.cosine_distance(query_vec))
            .limit(limit)
        )

        if topic:
            stmt = stmt.where(NewsItem.topic == topic)
        if since:
            stmt = stmt.where(effective_date >= since)

        result = await session.execute(stmt)
        return list(result.scalars().all())
