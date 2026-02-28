#!/usr/bin/env python3
"""Historical backfill CLI — extract AI news from 2023-now.

Usage:
    python scripts/backfill.py --dry-run                 # estimate costs
    python scripts/backfill.py --max-cost 10             # run with $10 budget
    python scripts/backfill.py --resume                  # resume from checkpoint
"""

from __future__ import annotations

import argparse
import asyncio
import html
import sys
from datetime import UTC, datetime
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx
import openai
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from src.classifiers.keyword import classify_by_keywords
from src.core.config import Settings, get_settings
from src.core.database import get_session_factory
from src.core.logging import get_logger
from src.core.models import NewsItem, RawExtraction
from src.extractors.base import ExtractedItem
from src.pipeline.backfill.checkpoint import BackfillCheckpoint
from src.pipeline.backfill.cost_tracker import CostTracker
from src.pipeline.backfill.extractors import (
    HistoricalGitHubExtractor,
    HistoricalHFExtractor,
    HistoricalHNExtractor,
    RawItem,
    generate_month_ranges,
)

logger = get_logger(__name__)

CHECKPOINT_PATH = Path("data/backfill-checkpoint.json")
_STORE_BATCH_SIZE = 500  # commit every N items in _store_raw_items

# Estimated tokens per item for LLM classification cost tracking.
# Prompt is ~900 tokens fixed overhead + ~80 tokens per item in a batch of 10.
# Output is ~45 tokens per item (JSON entry + English summary for accepted items).
EST_INPUT_TOKENS_PER_ITEM = 170
EST_OUTPUT_TOKENS_PER_ITEM = 45


# -- Phase 1: Extract raw -----------------------------------------------------


async def phase_extract(
    args: argparse.Namespace,
    checkpoint: BackfillCheckpoint,
) -> int:
    """Extract raw items from all sources, store in raw_extractions."""
    settings = get_settings()
    total_stored = 0
    batch_id = f"backfill-{datetime.now(tz=UTC).strftime('%Y%m%d-%H%M')}"

    async with httpx.AsyncClient(
        timeout=30, headers={"User-Agent": "AI-News-Platform-Backfill/1.0"}
    ) as client:
        if "hackernews" in args.sources and total_stored < args.max_items:
            total_stored += await _extract_hn(
                client, args, checkpoint, settings, batch_id, args.max_items - total_stored
            )

        if "github" in args.sources and total_stored < args.max_items:
            total_stored += await _extract_github(
                args, checkpoint, settings, batch_id, args.max_items - total_stored
            )

        if "huggingface" in args.sources and total_stored < args.max_items:
            total_stored += await _extract_hf(
                client, args, checkpoint, batch_id, args.max_items - total_stored
            )

    return total_stored


async def _extract_hn(
    client: httpx.AsyncClient,
    args: argparse.Namespace,
    checkpoint: BackfillCheckpoint,
    settings: Settings,
    batch_id: str,
    remaining: int,
) -> int:
    extractor = HistoricalHNExtractor(
        min_points=args.min_points,
        queries=settings.hn_search_queries_list,
    )
    months = generate_month_ranges(args.from_month, args.to_month)
    stored = 0

    cp_data = checkpoint.sources.get("hackernews", {})
    last_month = cp_data.get("last_month")

    for start, end in months:
        if stored >= remaining:
            logger.info("max_items_reached", source="hackernews", stored=stored)
            break
        if last_month and start <= last_month:
            continue

        items = await extractor.fetch_month(client, start, end)
        stored += await _store_raw_items(items, batch_id)

        checkpoint.update_source("hackernews", last_month=start, items_stored=stored)
        checkpoint.save()
        logger.info("hn_progress", month=start, stored=stored)

    return stored


async def _extract_github(
    args: argparse.Namespace,
    checkpoint: BackfillCheckpoint,
    settings: Settings,
    batch_id: str,
    remaining: int,
) -> int:
    token = settings.github_token
    gh_headers: dict[str, str] = {
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "AI-News-Platform-Backfill/1.0",
    }
    if token:
        gh_headers["Authorization"] = f"Bearer {token}"

    async with httpx.AsyncClient(timeout=30, headers=gh_headers) as gh_client:
        extractor = HistoricalGitHubExtractor(min_stars=args.min_stars)
        months = generate_month_ranges(args.from_month, args.to_month)
        stored = 0

        cp_data = checkpoint.sources.get("github", {})
        last_month = cp_data.get("last_month")

        for start, end in months:
            if stored >= remaining:
                logger.info("max_items_reached", source="github", stored=stored)
                break
            if last_month and start <= last_month:
                continue

            items = await extractor.fetch_month(gh_client, start, end)
            stored += await _store_raw_items(items, batch_id)

            checkpoint.update_source("github", last_month=start, items_stored=stored)
            checkpoint.save()
            logger.info("github_progress", month=start, stored=stored)

    return stored


async def _extract_hf(
    client: httpx.AsyncClient,
    args: argparse.Namespace,
    checkpoint: BackfillCheckpoint,
    batch_id: str,
    remaining: int,
) -> int:
    extractor = HistoricalHFExtractor(min_downloads=100, since_date=args.from_month)
    items = await extractor.fetch_all(client, max_items=min(2000, remaining))
    stored = await _store_raw_items(items, batch_id)

    checkpoint.update_source("huggingface", items_stored=stored)
    checkpoint.save()
    return stored


async def _store_raw_items(items: list[RawItem], batch_id: str = "") -> int:
    """Insert raw items into raw_extractions, skip duplicates. Commits in batches."""
    if not items:
        return 0
    stored = 0
    factory = get_session_factory()
    async with factory() as session:
        for i, item in enumerate(items):
            stmt = (
                insert(RawExtraction)
                .values(
                    source=item.source,
                    source_id=item.source_id,
                    raw_json=item.raw_json,
                    backfill_batch=batch_id or None,
                )
                .on_conflict_do_nothing(constraint="uq_raw_source_id")
            )
            result = await session.execute(stmt)
            if result.rowcount and result.rowcount > 0:
                stored += 1
            if (i + 1) % _STORE_BATCH_SIZE == 0:
                await session.commit()
        await session.commit()
    return stored


# -- Phase 2: Filter + Classify -----------------------------------------------


async def phase_classify(
    args: argparse.Namespace,
    checkpoint: BackfillCheckpoint,
    cost_tracker: CostTracker,
) -> int:
    """Load raw items, pre-filter, classify with LLM, store as NewsItem."""
    from src.classifiers.llm import LLMClassifier

    llm_clf = LLMClassifier()
    stored = 0
    factory = get_session_factory()

    async with factory() as session:
        # Load existing content hashes to avoid reprocessing
        result = await session.execute(
            select(NewsItem.content_hash).where(NewsItem.content_hash.isnot(None))
        )
        existing_hashes = {row[0] for row in result.all()}

        # Load raw items not yet classified
        raw_result = await session.execute(
            select(RawExtraction).order_by(RawExtraction.extracted_at)
        )
        raw_items = raw_result.scalars().all()

    logger.info("classify_start", raw_count=len(raw_items), existing_hashes=len(existing_hashes))

    # Convert raw -> ExtractedItem for classification pipeline
    extracted: list[ExtractedItem] = []
    for raw in raw_items:
        ei = _raw_to_extracted(raw)
        if ei.content_hash in existing_hashes:
            continue
        extracted.append(ei)

    logger.info("classify_after_dedup", count=len(extracted))

    # Keyword pre-filter (lenient, 0.3 threshold)
    filtered: list[ExtractedItem] = []
    for ei in extracted:
        topic, relevance = classify_by_keywords(ei)
        if topic is not None and relevance >= 0.15:
            filtered.append(ei)

    # Enforce --max-items on items sent to LLM
    if len(filtered) > args.max_items:
        logger.info("max_items_cap", original=len(filtered), capped=args.max_items)
        filtered = filtered[: args.max_items]

    logger.info(
        "classify_after_keyword",
        count=len(filtered),
        dropped=len(extracted) - len(filtered),
    )

    if args.dry_run:
        _print_dry_run_summary(raw_items, extracted, filtered)
        return 0

    # LLM classification in concurrent batches
    batch_size = 10
    concurrency = 5
    all_batches = [filtered[i : i + batch_size] for i in range(0, len(filtered), batch_size)]
    total_batches = len(all_batches)
    classified_items: list = []
    completed = 0
    stopped = False

    print(
        f"  Classifying {len(filtered)} items in {total_batches} batches "
        f"(concurrency={concurrency})...",
        flush=True,
    )

    sem = asyncio.Semaphore(concurrency)

    async def _classify_one(batch_num: int, batch: list) -> list:
        nonlocal completed, stopped
        if stopped:
            return []
        async with sem:
            if cost_tracker.budget_exceeded or stopped:
                return []
            try:
                results = await llm_clf.classify(batch)
                cost_tracker.add_tokens(
                    input_tokens=len(batch) * EST_INPUT_TOKENS_PER_ITEM,
                    output_tokens=len(batch) * EST_OUTPUT_TOKENS_PER_ITEM,
                )
                completed += 1
                if completed % 25 == 0 or completed == 1:
                    print(
                        f"  [{completed}/{total_batches}] "
                        f"cost=${cost_tracker.estimated_cost_usd:.3f}",
                        flush=True,
                    )
                return results
            except (httpx.HTTPStatusError, openai.APIError) as exc:
                status = getattr(exc, "status_code", None) or getattr(
                    getattr(exc, "response", None), "status_code", 0
                )
                logger.warning("classify_batch_failed", error=str(exc), batch=batch_num)
                if status in (402, 429):
                    stopped = True
                return []
            except Exception as exc:
                logger.warning("classify_batch_unexpected", error=str(exc), batch=batch_num)
                return []

    tasks = [_classify_one(i, batch) for i, batch in enumerate(all_batches)]
    batch_results = await asyncio.gather(*tasks)
    for br in batch_results:
        classified_items.extend(br)

    checkpoint.cost_usd = cost_tracker.estimated_cost_usd
    checkpoint.save()

    # Store classified items
    async with factory() as session:
        for ci in classified_items:
            ei = ci.item
            stmt = (
                insert(NewsItem)
                .values(
                    title=ei.title,
                    url=ei.url,
                    source=ei.source,
                    published_at=ei.published_at,
                    content_hash=ei.content_hash,
                    url_hash=ei.url_hash,
                    full_text=ei.text,
                    author=ei.author,
                    score=ei.score,
                    metadata_=ei.metadata,
                    topic=ci.topic,
                    relevance_score=ci.relevance_score,
                    summary=ci.summary,
                    priority=ci.priority,
                    trending=ci.trending,
                    dev_value_score=ci.dev_value_score,
                    credibility_score=ci.credibility_score,
                )
                .on_conflict_do_nothing(index_elements=["content_hash"])
            )
            result = await session.execute(stmt)
            if result.rowcount and result.rowcount > 0:
                stored += 1
        await session.commit()

    checkpoint.items_classified = stored
    checkpoint.cost_usd = cost_tracker.estimated_cost_usd
    checkpoint.save()
    logger.info("classify_complete", stored=stored, cost=f"${cost_tracker.estimated_cost_usd:.2f}")
    return stored


def _parse_iso_date(value: str | None) -> datetime | None:
    """Parse an ISO-8601 date string, returning None on failure."""
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return dt if dt.tzinfo else dt.replace(tzinfo=UTC)
    except (ValueError, TypeError):
        return None


def _raw_to_extracted(raw: RawExtraction) -> ExtractedItem:
    """Convert a RawExtraction record to an ExtractedItem."""
    j = raw.raw_json
    if raw.source == "hackernews":
        url = j.get("url") or f"https://news.ycombinator.com/item?id={raw.source_id}"
        title = html.unescape(j.get("title", ""))
        return ExtractedItem(
            title=title,
            source="hackernews",
            url=url,
            text=title,
            author=j.get("author", "unknown"),
            published_at=_parse_iso_date(j.get("created_at")) or raw.extracted_at,
            score=j.get("points", 0),
            metadata={
                "story_id": raw.source_id,
                "num_comments": j.get("num_comments", 0),
            },
        )
    if raw.source == "github":
        desc = html.unescape(j.get("description") or "")
        name = html.unescape(j.get("name", ""))
        title = f"{name}: {desc}" if desc else name
        return ExtractedItem(
            title=title,
            source="github",
            url=j.get("html_url", ""),
            text=desc,
            author=j.get("owner", {}).get("login", "unknown"),
            published_at=_parse_iso_date(j.get("pushed_at") or j.get("created_at"))
            or raw.extracted_at,
            score=j.get("stargazers_count", 0),
            metadata={
                "stars": j.get("stargazers_count", 0),
                "full_name": j.get("full_name", ""),
            },
        )
    # huggingface
    return ExtractedItem(
        title=html.unescape(raw.source_id),
        source="huggingface",
        url=f"https://huggingface.co/{raw.source_id}",
        text=html.unescape(raw.source_id),
        author=raw.source_id.split("/")[0] if "/" in raw.source_id else "unknown",
        published_at=_parse_iso_date(j.get("lastModified")) or raw.extracted_at,
        score=j.get("downloads", 0),
        metadata={"downloads": j.get("downloads", 0), "likes": j.get("likes", 0)},
    )


def _print_dry_run_summary(
    raw_items: list[RawExtraction],
    extracted: list[ExtractedItem],
    filtered: list[ExtractedItem],
) -> None:
    """Print dry-run summary with cost estimate."""
    from src.pipeline.backfill.cost_tracker import _INPUT_PRICE_PER_M, _OUTPUT_PRICE_PER_M

    est_llm_cost = len(filtered) * (
        EST_INPUT_TOKENS_PER_ITEM * _INPUT_PRICE_PER_M / 1_000_000
        + EST_OUTPUT_TOKENS_PER_ITEM * _OUTPUT_PRICE_PER_M / 1_000_000
    )
    est_embed_cost = len(filtered) * 0.000001
    print("\n" + "=" * 60)
    print("DRY RUN SUMMARY")
    print("=" * 60)
    print(f"  Raw extractions:       {len(raw_items):>8,}")
    print(f"  After DB dedup:        {len(extracted):>8,}")
    print(f"  After keyword filter:  {len(filtered):>8,}")
    print(f"  Estimated LLM cost:     ${est_llm_cost:>7.2f}")
    print(f"  Estimated embed cost:   ${est_embed_cost:>7.4f}")
    print(f"  Total estimated cost:   ${est_llm_cost + est_embed_cost:>7.2f}")
    print("=" * 60)
    print("Run without --dry-run to proceed.\n")


# -- Phase 3: Embeddings ------------------------------------------------------


async def phase_embed() -> int:
    """Generate embeddings for items that don't have them yet."""
    from src.pipeline.pipeline import _embed_new_items as embed_new_items
    from src.rag.embeddings import EmbeddingService

    settings = get_settings()
    if not settings.embedding_api_key:
        logger.warning("no_embedding_key")
        return 0

    embed_service = EmbeddingService()
    factory = get_session_factory()
    async with factory() as session:
        count = await embed_new_items(session, embed_service)
    logger.info("embed_complete", count=count)
    return count


# -- CLI -----------------------------------------------------------------------


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Historical backfill for AI News Platform")
    p.add_argument(
        "--sources",
        default="hackernews,github,huggingface",
        help="Comma-separated sources",
    )
    p.add_argument(
        "--from",
        dest="from_month",
        default="2023-01",
        help="Start month (YYYY-MM)",
    )
    p.add_argument(
        "--to",
        dest="to_month",
        default=datetime.now(tz=UTC).strftime("%Y-%m"),
        help="End month (YYYY-MM)",
    )
    p.add_argument("--max-items", type=int, default=20_000, help="Max items to process")
    p.add_argument("--max-cost", type=float, default=10.0, help="Max LLM cost in USD")
    p.add_argument("--min-points", type=int, default=50, help="HN min points")
    p.add_argument("--min-stars", type=int, default=200, help="GitHub min stars")
    p.add_argument(
        "--dry-run", action="store_true", help="Extract + filter only, show cost estimate"
    )
    p.add_argument("--resume", action="store_true", help="Resume from checkpoint")
    p.add_argument("--skip-embeddings", action="store_true", help="Skip embedding generation")
    p.add_argument(
        "--phase",
        choices=["extract", "classify", "embed", "all"],
        default="all",
        help="Run specific phase",
    )
    args = p.parse_args()
    args.sources = [s.strip() for s in args.sources.split(",")]
    return args


async def main() -> None:
    args = parse_args()
    checkpoint = (
        BackfillCheckpoint.load(CHECKPOINT_PATH)
        if args.resume
        else BackfillCheckpoint(CHECKPOINT_PATH)
    )
    # Resume accumulated cost from previous runs so budget protection works across restarts
    initial_cost = checkpoint.cost_usd if args.resume else 0.0
    cost_tracker = CostTracker(max_cost_usd=args.max_cost, initial_cost_usd=initial_cost)

    print(f"Backfill: {args.sources} | {args.from_month} -> {args.to_month}")
    print(f"Budget: ${args.max_cost} | Max items: {args.max_items}")
    if args.dry_run:
        print("MODE: DRY RUN (no LLM calls)\n")

    if args.phase in ("extract", "all"):
        print("\n-- Phase 1: Extract Raw --")
        raw_count = await phase_extract(args, checkpoint)
        print(f"  Stored {raw_count} raw items")

    if args.phase in ("classify", "all"):
        print("\n-- Phase 2: Filter + Classify --")
        classified = await phase_classify(args, checkpoint, cost_tracker)
        print(f"  Classified and stored {classified} items")
        print(f"  Cost: ${cost_tracker.estimated_cost_usd:.2f}")

    if args.phase in ("embed", "all") and not args.skip_embeddings and not args.dry_run:
        print("\n-- Phase 3: Embeddings --")
        embedded = await phase_embed()
        print(f"  Generated {embedded} embeddings")

    print("\nDone!")


if __name__ == "__main__":
    asyncio.run(main())
