#!/usr/bin/env python3
"""CLI for recovering news items lost during the LLM classifier outage.

See src/pipeline/backfill/recovery.py for the recovery logic, scope, and
rationale (which sources are covered and why).

Usage:
    python scripts/recover_outage.py --dry-run
    python scripts/recover_outage.py --max-cost 2.0 2>&1 | tee <log outside the repo>

--max-cost gates the pre-flight cost estimate only: the run aborts before any LLM
call if the estimate exceeds it. Real spend is not metered during the run.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.core.config import Settings, get_settings
from src.core.database import get_session_factory
from src.extractors.base import ExtractedItem
from src.pipeline.backfill import recovery
from src.pipeline.dedup import deduplicate_items
from src.pipeline.stages.classify import run_classification
from src.pipeline.stages.score import run_scoring
from src.pipeline.stages.store import embed_new_items, store_classified_items
from src.pipeline.validation import validate_extracted_item
from src.validators.credibility import CredibilityValidator

FETCHERS = {
    "hackernews": recovery.fetch_hackernews,
    "github_search": recovery.fetch_github_search,
}


async def run(args: argparse.Namespace) -> None:
    settings: Settings = get_settings()
    factory = get_session_factory()

    print(
        f"Recovery window: {recovery.WINDOW_START.isoformat()} -> "
        f"{recovery.WINDOW_END.isoformat()}"
    )
    print(f"Sources: {args.sources}\n")

    per_source_extracted: dict[str, list[ExtractedItem]] = {}
    for source in args.sources:
        if source not in FETCHERS:
            raise SystemExit(f"Unsupported source for recovery: {source!r}")
        print(f"-- Fetching {source} --")
        per_source_extracted[source] = await FETCHERS[source](settings)
        print(f"  Raw items in window: {len(per_source_extracted[source])}")

    titles_since = recovery.WINDOW_START - timedelta(days=settings.seen_window_days)
    async with factory() as session:
        existing_content, existing_url = await recovery.load_existing_hashes(session)
        stored_titles = await recovery.load_recent_titles(session, titles_since)
    print(
        f"\nExisting news_items hashes loaded: {len(existing_content)} content, "
        f"{len(existing_url)} url; {len(stored_titles)} titles since {titles_since.isoformat()}"
    )

    all_new: list[ExtractedItem] = []
    print(
        f"\n{'source':<15}{'extracted':>10}{'existing':>10}{'similar':>9}{'new':>8}"
        f"{'reject':>8}{'to_llm':>8}{'auto_acc':>9}"
    )
    total_to_llm = 0
    for source, items in per_source_extracted.items():
        new_items, already = recovery.filter_new(items, existing_content, existing_url)
        new_items = deduplicate_items(new_items)
        new_items, similar = recovery.filter_similar_titles(new_items, stored_titles)
        valid_items = [
            i for i in new_items if not validate_extracted_item({"title": i.title, "url": i.url})
        ]
        auto_reject, to_llm, auto_accept = recovery.keyword_buckets(valid_items)
        total_to_llm += to_llm
        print(
            f"{source:<15}{len(items):>10}{already:>10}{similar:>9}{len(valid_items):>8}"
            f"{auto_reject:>8}{to_llm:>8}{auto_accept:>9}"
        )
        all_new.extend(valid_items)

    est_cost = recovery.estimate_llm_cost_usd(total_to_llm)
    print(f"\nTotal items to send to LLM (ambiguous, 1-2 keyword matches): {total_to_llm}")
    print(
        f"Estimated LLM cost (kimi-k2.6, ${recovery.INPUT_PRICE_PER_M}/"
        f"${recovery.OUTPUT_PRICE_PER_M} per 1M in/out tokens): ${est_cost:.4f} "
        "(pre-flight estimate; spend is not metered during the run)"
    )

    if args.dry_run:
        print("\nDRY RUN -- no data was written. Re-run without --dry-run to execute.")
        return

    if est_cost > args.max_cost:
        raise SystemExit(
            f"Estimated cost ${est_cost:.4f} exceeds --max-cost ${args.max_cost:.2f}; aborting."
        )

    print(
        f"\nProceeding: classifying {len(all_new)} candidate items via the live pipeline "
        f"stages (classify -> score -> credibility validate -> store)..."
    )

    classified = await run_classification(all_new)
    scored = run_scoring(classified)
    validator = CredibilityValidator()
    validated = await validator.validate(scored)

    async with factory() as session:
        stored = await store_classified_items(session, validated)
        if settings.embedding_api_key:
            embedded = await embed_new_items(session)
            print(f"Embedded {embedded} items")

    print(f"\nClassified: {len(classified)} | Validated: {len(validated)} | Stored: {stored}")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Recover news items lost during the LLM outage")
    p.add_argument(
        "--sources",
        default="hackernews,github_search",
        help="Comma-separated sources to recover (default: hackernews,github_search)",
    )
    p.add_argument("--dry-run", action="store_true", help="Estimate only, no LLM calls, no writes")
    p.add_argument(
        "--max-cost",
        type=float,
        default=2.0,
        help=(
            "Abort if the pre-flight cost estimate exceeds this (USD). "
            "Real spend is not metered during the run."
        ),
    )
    args = p.parse_args()
    args.sources = [s.strip() for s in args.sources.split(",") if s.strip()]
    return args


if __name__ == "__main__":
    asyncio.run(run(parse_args()))
