"""Re-score ALL items with current CompositeScorer thresholds.

Usage:
    python scripts/rescore_all.py [--dry-run] [--batch-size 500]
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from datetime import UTC, datetime

from sqlalchemy import func, select, text, update

from src.classifiers.base import ClassifiedItem
from src.core.database import get_async_session
from src.core.models import NewsItem
from src.extractors.base import ExtractedItem
from src.pipeline.composite_scorer import CompositeScorer


def _newsitem_to_classified(item: NewsItem) -> ClassifiedItem:
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


async def rescore_all(dry_run: bool = False, batch_size: int = 500) -> int:
    scorer = CompositeScorer()
    now = datetime.now(UTC)
    thresholds = scorer._velocity_thresholds
    print(f"Thresholds: gh={thresholds['github']}, hn={thresholds['hackernews']}, hf={thresholds['huggingface']}")

    async with get_async_session() as session:
        count_result = await session.execute(select(func.count(NewsItem.id)))
        total = count_result.scalar_one()
        print(f"Re-scoring {total} items...")

        offset = 0
        updated = 0
        while offset < total:
            result = await session.execute(
                select(NewsItem).order_by(NewsItem.created_at).limit(batch_size).offset(offset)
            )
            items = result.scalars().all()
            if not items:
                break

            for item in items:
                ci = _newsitem_to_classified(item)
                new_score = scorer.score(ci, now=now)
                if not dry_run:
                    await session.execute(
                        update(NewsItem).where(NewsItem.id == item.id).values(composite_score=new_score)
                    )

            if not dry_run:
                await session.commit()

            updated += len(items)
            offset += batch_size
            print(f"  [{updated}/{total}] processed", flush=True)

            if dry_run and updated >= batch_size:
                for item in items[:3]:
                    ci = _newsitem_to_classified(item)
                    score = scorer.score(ci, now=now)
                    print(f"    {item.source:15s} | old={item.composite_score:.4f} -> new={score:.4f} | {item.title[:60]}")
                break

        print(f"\nDone. {'Would update' if dry_run else 'Updated'} {updated} items.")

        if not dry_run:
            r = await session.execute(text(
                "SELECT source, count(*), avg(composite_score), min(composite_score), max(composite_score) "
                "FROM news_items WHERE composite_score IS NOT NULL "
                "GROUP BY source ORDER BY avg(composite_score) DESC"
            ))
            print("\nNew distribution:")
            for row in r.all():
                print(f"  {row[0]:15s} count={row[1]:5d} avg={row[2]:.4f} min={row[3]:.4f} max={row[4]:.4f}")

    return updated


def main() -> None:
    parser = argparse.ArgumentParser(description="Re-score ALL items with current thresholds")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--batch-size", type=int, default=500)
    args = parser.parse_args()
    asyncio.run(rescore_all(dry_run=args.dry_run, batch_size=args.batch_size))


if __name__ == "__main__":
    main()
