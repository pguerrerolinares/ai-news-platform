"""Feed construction pipeline: candidates -> collapse -> rescore -> MMR -> paginate."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import get_settings
from src.core.logging import get_logger
from src.core.models import NewsItem
from src.core.queries import effective_date
from src.feed.mmr_ranker import mmr_rank
from src.feed.variant_collapse import collapse_variants
from src.pipeline.composite_scorer import CompositeScorer

log = get_logger(__name__)

_EXPANSION_WINDOWS = [48.0, 72.0, 168.0]


class FeedBuilder:
    """Builds a diversified feed from the news items table."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        settings = get_settings()
        self._default_lambda = settings.feed_mmr_lambda
        self._candidate_multiplier = settings.feed_candidate_multiplier
        self._default_max_age = settings.feed_latest_max_age_hours
        self._min_items = settings.feed_latest_min_items

    async def build(
        self,
        *,
        topic: str | None = None,
        source: str | None = None,
        limit: int = 20,
        offset: int = 0,
        diversity: float | None = None,
        max_age_hours: float | None = None,
    ) -> tuple[list[NewsItem], int]:
        """Build a diversified feed.

        Returns (items, total_count).
        """
        lambda_ = diversity if diversity is not None else self._default_lambda
        pool_size = limit * self._candidate_multiplier
        age_limit = max_age_hours if max_age_hours is not None else self._default_max_age

        # Fetch candidates with progressive time window expansion
        all_candidates = await self._fetch_candidates(
            topic=topic,
            source=source,
            pool_size=pool_size + offset,
            max_age_hours=age_limit,
        )

        # Live rescore with current time
        if all_candidates:
            scorer = CompositeScorer()
            now = datetime.now(UTC)
            for item in all_candidates:
                item.composite_score = scorer.score_newsitem(item, now=now)

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

    async def _fetch_candidates(
        self,
        *,
        topic: str | None,
        source: str | None,
        pool_size: int,
        max_age_hours: float,
    ) -> list[NewsItem]:
        """Fetch candidate items, expanding time window if too few results."""
        windows = [max_age_hours] + [w for w in _EXPANSION_WINDOWS if w > max_age_hours]

        candidates: list[NewsItem] = []
        for window in windows:
            cutoff = datetime.now(UTC) - timedelta(hours=window)
            query = select(NewsItem).where(
                NewsItem.composite_score.isnot(None),
                effective_date >= cutoff,
            )
            if topic:
                query = query.where(NewsItem.topic == topic)
            if source:
                query = query.where(NewsItem.source == source)

            query = query.order_by(
                NewsItem.composite_score.desc().nulls_last(),
                effective_date.desc(),
            )

            result = await self._session.execute(query.limit(pool_size))
            candidates = list(result.scalars().all())

            if len(candidates) >= self._min_items:
                log.info(
                    "feed_window_selected",
                    window_hours=window,
                    candidates=len(candidates),
                )
                return candidates

        log.info(
            "feed_window_exhausted",
            final_window=windows[-1],
            candidates=len(candidates),
        )
        return candidates
