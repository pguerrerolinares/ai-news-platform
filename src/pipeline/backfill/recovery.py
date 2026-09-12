"""Recovery logic for the 2026-08-22 -> 2026-09-12 LLM classifier outage.

See docs/adr/003-llm-kimi-k26-fail-loud.md for the outage root cause: the LLM
classifier silently degraded to KeywordClassifier (whose relevance never clears
MIN_RELEVANCE_SCORE), so almost nothing was stored for three weeks.

Only sources with a queryable historical window are re-extracted here:

- hackernews: HN Algolia Search API (created_at_i range) -- HistoricalHNExtractor.
- github_search: GitHub Search API (pushed:<date range>) -- HistoricalGitHubExtractor.
  Relabeled "github_search" (not "github"): the historical extractor's raw_json
  matches prod's search-based extractor (src/extractors/github.py, source_name
  "github_search"); prod's plain "github" source is github_trending.py, a
  trending-page scrape with no historical API.

NOT covered (see the recovery report for evidence):
- arxiv: a real historical API exists (export.arxiv.org/api/query, submittedDate
  range) but it started 429-ing during manual testing in this session; not
  implemented here given the time/budget box. Follow-up candidate.
- rss, github (trending), huggingface (trending), webscraper: snapshot-only
  sources with no queryable archive -- confirmed by reading each extractor.

Re-extracted items are meant to be run through the *live* pipeline stages
(dedup -> validate -> classify -> score -> credibility validate -> store) so
behavior matches the normal pipeline exactly. store_classified_items() is an
insert-or-upsert keyed on content_hash/url_hash -- no manual DELETE/UPDATE is
ever issued by callers of this module.
"""

from __future__ import annotations

from datetime import UTC, datetime

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.classifiers.keyword import classify_by_keywords
from src.core.config import Settings
from src.core.dates import parse_iso_z
from src.core.models import NewsItem
from src.extractors.base import ExtractedItem
from src.pipeline.backfill.extractors import (
    HistoricalGitHubExtractor,
    HistoricalHNExtractor,
    RawItem,
    generate_month_ranges,
)

# Outage window per ADR-003 / incident timeline.
WINDOW_START = datetime(2026, 8, 22, 4, 40, tzinfo=UTC)
WINDOW_END = datetime(2026, 9, 12, 22, 55, tzinfo=UTC)

# Keyword pre-filter bucket boundary, mirrors src/pipeline/stages/classify.py
# run_classification() exactly (0 matches -> reject, 1-2 -> LLM, >=3 -> auto-accept).
HIGH_CONFIDENCE_THRESHOLD = 3

# kimi-k2.6 pricing per docs/adr/003-llm-kimi-k26-fail-loud.md (USD / 1M tokens).
# NOTE: src/pipeline/backfill/cost_tracker.py still has the old kimi-latest-8k
# pricing ($0.20/$2.00) hardcoded -- do not reuse it for cost estimates here.
INPUT_PRICE_PER_M = 0.95
OUTPUT_PRICE_PER_M = 4.00

# Same per-item token estimate documented in scripts/backfill.py: ~900-token fixed
# prompt overhead amortized over a batch of 10 + ~80 tokens/item in, ~45 tokens/item out.
EST_INPUT_TOKENS_PER_ITEM = 170
EST_OUTPUT_TOKENS_PER_ITEM = 45


def in_window(dt: datetime | None) -> bool:
    """True if dt falls inside the outage recovery window."""
    if dt is None:
        return False
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return WINDOW_START <= dt <= WINDOW_END


def raw_hn_to_extracted(raw: RawItem) -> ExtractedItem:
    """Convert a HackerNews RawItem to an ExtractedItem (mirrors scripts/backfill.py)."""
    j = raw.raw_json
    return ExtractedItem(
        title=raw.title,
        source="hackernews",
        url=j.get("url") or f"https://news.ycombinator.com/item?id={raw.source_id}",
        text=raw.title,
        author=j.get("author", "unknown"),
        published_at=raw.published_at,
        score=raw.score,
        metadata={"story_id": raw.source_id, "num_comments": j.get("num_comments", 0)},
    )


def raw_github_to_extracted(raw: RawItem) -> ExtractedItem:
    """Convert a GitHub search RawItem to an ExtractedItem tagged as github_search."""
    j = raw.raw_json
    desc = j.get("description") or ""
    name = j.get("name", "")
    title = f"{name}: {desc}" if desc else name
    return ExtractedItem(
        title=title,
        source="github_search",
        url=j.get("html_url", ""),
        text=desc,
        author=j.get("owner", {}).get("login", "unknown"),
        published_at=raw.published_at,
        score=raw.score,
        source_created_at=raw.published_at,
        metadata={
            "stars": j.get("stargazers_count", 0),
            "full_name": j.get("full_name", ""),
            "recovered_from_outage": True,
        },
    )


async def fetch_hackernews(settings: Settings) -> list[ExtractedItem]:
    """Fetch HN stories for the outage window via the Algolia search API."""
    extractor = HistoricalHNExtractor(min_points=50, queries=settings.hn_search_queries_list)
    months = generate_month_ranges("2026-08", "2026-09")
    raw_items: list[RawItem] = []
    async with httpx.AsyncClient(
        timeout=30, headers={"User-Agent": "AI-News-Platform-Recovery/1.0"}
    ) as client:
        for start, end in months:
            raw_items.extend(await extractor.fetch_month(client, start, end))
    return [raw_hn_to_extracted(r) for r in raw_items if in_window(r.published_at)]


def is_recent_repo(raw: RawItem, max_age_days: int) -> bool:
    """Mirror prod github_search's repo-age filter (src/extractors/github.py).

    Prod skips repos created more than ``max_age_days`` before the poll. During the
    outage a poll saw each repo around its push, so age is measured against the push
    date. Without this, long-lived repos that merely got a push in the window leak in.
    """
    created_at = parse_iso_z(raw.raw_json.get("created_at", ""))
    if created_at is None or raw.published_at is None or max_age_days <= 0:
        return True
    return (raw.published_at - created_at).days <= max_age_days


async def fetch_github_search(settings: Settings) -> list[ExtractedItem]:
    """Fetch repos pushed during the outage window via the GitHub search API."""
    extractor = HistoricalGitHubExtractor(
        min_stars=settings.github_min_stars,
        queries=settings.github_search_queries_list,
        token=settings.github_token or "",
    )
    months = generate_month_ranges("2026-08", "2026-09")
    raw_items: list[RawItem] = []
    headers = {
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "AI-News-Platform-Recovery/1.0",
    }
    if settings.github_token:
        headers["Authorization"] = f"Bearer {settings.github_token}"
    async with httpx.AsyncClient(timeout=30, headers=headers) as client:
        for start, end in months:
            raw_items.extend(await extractor.fetch_month(client, start, end))
    max_age_days = settings.github_max_repo_age_days
    return [
        raw_github_to_extracted(r)
        for r in raw_items
        if in_window(r.published_at) and is_recent_repo(r, max_age_days)
    ]


async def load_existing_hashes(session: AsyncSession) -> tuple[set[str], set[str]]:
    """Load every stored content_hash / url_hash for dedup against recovered items."""
    result = await session.execute(
        select(NewsItem.content_hash, NewsItem.url_hash).where(
            NewsItem.content_hash.isnot(None) | NewsItem.url_hash.isnot(None)
        )
    )
    content_hashes: set[str] = set()
    url_hashes: set[str] = set()
    for content_hash, url_hash in result.all():
        if content_hash:
            content_hashes.add(content_hash)
        if url_hash:
            url_hashes.add(url_hash)
    return content_hashes, url_hashes


def filter_new(
    items: list[ExtractedItem],
    existing_content: set[str],
    existing_url: set[str],
) -> tuple[list[ExtractedItem], int]:
    """Split out items already present in news_items by content_hash or url_hash."""
    new_items: list[ExtractedItem] = []
    already = 0
    for item in items:
        if item.content_hash in existing_content or (
            item.url_hash is not None and item.url_hash in existing_url
        ):
            already += 1
        else:
            new_items.append(item)
    return new_items, already


def keyword_buckets(items: list[ExtractedItem]) -> tuple[int, int, int]:
    """Bucket items exactly like run_classification(): (auto_reject, to_llm, auto_accept)."""
    auto_reject = to_llm = auto_accept = 0
    for item in items:
        _topic, _relevance, match_count = classify_by_keywords(item)
        if match_count >= HIGH_CONFIDENCE_THRESHOLD:
            auto_accept += 1
        elif match_count >= 1:
            to_llm += 1
        else:
            auto_reject += 1
    return auto_reject, to_llm, auto_accept


def estimate_llm_cost_usd(to_llm_count: int) -> float:
    """Estimate kimi-k2.6 cost for classifying `to_llm_count` ambiguous items."""
    input_tokens = to_llm_count * EST_INPUT_TOKENS_PER_ITEM
    output_tokens = to_llm_count * EST_OUTPUT_TOKENS_PER_ITEM
    return (
        input_tokens * INPUT_PRICE_PER_M / 1_000_000
        + output_tokens * OUTPUT_PRICE_PER_M / 1_000_000
    )
