"""RAG retriever — vector similarity search over news items."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.logging import get_logger
from src.core.models import ItemEmbedding, NewsItem
from src.rag.embeddings import EmbeddingService

logger = get_logger(__name__)


class Retriever:
    """Retrieve relevant news items via pgvector cosine similarity."""

    def __init__(self, embedding_service: EmbeddingService | None = None) -> None:
        self._embed = embedding_service or EmbeddingService()

    async def retrieve(
        self,
        session: AsyncSession,
        query: str,
        *,
        limit: int = 5,
        topic: str | None = None,
    ) -> list[NewsItem]:
        """Find the top-K most similar news items to the query."""
        if not query.strip():
            return []

        try:
            query_vec = await self._embed.embed_text(query)
        except Exception:
            logger.error("retriever_embed_failed", exc_info=True)
            return []

        stmt = (
            select(NewsItem)
            .join(ItemEmbedding, NewsItem.id == ItemEmbedding.item_id)
            .order_by(ItemEmbedding.embedding.cosine_distance(query_vec))
            .limit(limit)
        )

        if topic:
            stmt = stmt.where(NewsItem.topic == topic)

        result = await session.execute(stmt)
        return list(result.scalars().all())
