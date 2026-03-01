"""One-time script to compute composite_score for items where it's NULL.

Uses existing DB data (source, score, relevance_score, topic, published_at, metadata)
to compute composite_score via the same formula used in the pipeline.
No external API calls — pure math on existing data.

Usage:
    python scripts/rescore_composite.py [--dry-run] [--batch-size 500]
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from datetime import UTC, datetime

from sqlalchemy import func, select, update

from src.classifiers.base import ClassifiedItem
from src.core.database import get_async_session
from src.core.models import NewsItem
from src.extractors.base import ExtractedItem
from src.pipeline.composite_scorer import CompositeScorer


def _newsitem_to_classified(item: NewsItem) -> ClassifiedItem:
    """Reconstruct a ClassifiedItem from a NewsItem for scoring."""
    ei = ExtractedItem(
        title=item.title or "",
        source=item.source or "",
        url=item.url,
        text=item.full_text,
        author=item.author,
        published_at=item.published_at,
        score=item.score,
        metadata=item.metadata_ or {},
    )
    return ClassifiedItem(
        item=ei,
        topic=item.topic or "",
        relevance_score=item.relevance_score or 0.0,
        dev_value_score=item.dev_value_score,
        credibility_score=item.credibility_score,
        summary=item.summary,
        priority=item.priority or 3,
        trending=item.trending or False,
    )


async def rescore(dry_run: bool = False, batch_size: int = 500) -> int:
    """Compute composite_score for all items where it's NULL."""
    scorer = CompositeScorer()
    now = datetime.now(UTC)
    updated = 0

    async with get_async_session() as session:
        # Count nulls
        count_result = await session.execute(
            select(func.count(NewsItem.id)).where(NewsItem.composite_score.is_(None))
        )
        total = count_result.scalar_one()
        print(f"Found {total} items with NULL composite_score")

        if total == 0:
            print("Nothing to do.")
            return 0

        # Process in batches
        offset = 0
        while offset < total:
            result = await session.execute(
                select(NewsItem)
                .where(NewsItem.composite_score.is_(None))
                .order_by(NewsItem.created_at)
                .limit(batch_size)
                .offset(0)  # Always 0 because we update as we go
            )
            items = result.scalars().all()

            if not items:
                break

            for item in items:
                ci = _newsitem_to_classified(item)
                score = scorer.score(ci, now=now)

                if not dry_run:
                    await session.execute(
                        update(NewsItem).where(NewsItem.id == item.id).values(composite_score=score)
                    )

            if not dry_run:
                await session.commit()

            updated += len(items)
            print(f"  [{updated}/{total}] processed", flush=True)

            if dry_run:
                # In dry-run, show a sample
                for item in items[:3]:
                    ci = _newsitem_to_classified(item)
                    score = scorer.score(ci, now=now)
                    print(f"    {item.source:15s} | {score:.4f} | {item.title[:60]}")
                break  # Only show first batch in dry-run

    print(f"Done. {'Would update' if dry_run else 'Updated'} {updated} items.")
    return updated


def main() -> None:
    parser = argparse.ArgumentParser(description="Re-score items with NULL composite_score")
    parser.add_argument("--dry-run", action="store_true", help="Compute but don't write")
    parser.add_argument("--batch-size", type=int, default=500, help="Batch size (default: 500)")
    args = parser.parse_args()

    asyncio.run(rescore(dry_run=args.dry_run, batch_size=args.batch_size))


if __name__ == "__main__":
    main()
