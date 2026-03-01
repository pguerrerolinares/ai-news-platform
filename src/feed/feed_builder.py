"""Feed construction pipeline: candidates -> collapse -> MMR -> paginate."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import get_settings
from src.core.logging import get_logger
from src.core.models import NewsItem
from src.core.queries import effective_date
from src.feed.mmr_ranker import mmr_rank
from src.feed.variant_collapse import collapse_variants

log = get_logger(__name__)


class FeedBuilder:
    """Builds a diversified feed from the news items table."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        settings = get_settings()
        self._default_lambda = settings.feed_mmr_lambda
        self._candidate_multiplier = settings.feed_candidate_multiplier

    async def build(
        self,
        *,
        topic: str | None = None,
        source: str | None = None,
        limit: int = 20,
        offset: int = 0,
        diversity: float | None = None,
    ) -> tuple[list[NewsItem], int]:
        """Build a diversified feed.

        Returns (items, total_count).
        """
        lambda_ = diversity if diversity is not None else self._default_lambda
        pool_size = limit * self._candidate_multiplier

        # Fetch candidate pool (only items with composite_score)
        query = select(NewsItem).where(NewsItem.composite_score.isnot(None))
        if topic:
            query = query.where(NewsItem.topic == topic)
        if source:
            query = query.where(NewsItem.source == source)

        query = query.order_by(
            NewsItem.composite_score.desc().nulls_last(),
            effective_date.desc(),
        )

        # For offset > 0, need larger pool to account for previous pages
        fetch_size = pool_size + offset
        result = await self._session.execute(query.limit(fetch_size))
        all_candidates = list(result.scalars().all())

        # Collapse HF model variants (GGUF/GPTQ dedup)
        collapsed = collapse_variants(all_candidates)

        # Apply MMR diversification
        ranked = mmr_rank(collapsed, lambda_=lambda_, limit=offset + limit)

        # Paginate
        page = ranked[offset : offset + limit]
        total = len(collapsed)

        log.info(
            "feed_built",
            candidates=len(all_candidates),
            after_collapse=len(collapsed),
            returned=len(page),
            total=total,
        )

        return page, total
