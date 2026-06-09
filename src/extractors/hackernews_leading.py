"""HackerNews leading-indicator extractor.

Polls the HN newest-first firehose (Algolia `search_by_date`) and keeps only
submissions whose linked URL is on an allowlist of authoritative AI domains.
Such items are ingested at 0 points -- the domain is the quality gate, not the
points threshold -- so a launch URL posted to HN is captured within one poll
interval of submission, well before it accrues enough points to surface via the
keyword-search lane.

Emitted items use source="hackernews" (unified storage / scoring / frontend);
the leading lane is distinguished via source_name (metrics, scheduling) and
metadata["lane"] = "leading".

API: https://hn.algolia.com/api -- free, no auth. No native domain filter, so
the firehose is fetched and filtered client-side (volume is ~1.2k stories/day,
trivial; authoritative-domain hits are single digits/day).
"""

from __future__ import annotations

import html
from datetime import UTC, datetime, timedelta
from urllib.parse import urlparse

import httpx

from src.core.config import get_settings
from src.core.logging import get_logger
from src.core.metrics import (
    extractor_duration_seconds,
    extractor_errors_total,
    items_extracted_total,
)
from src.extractors.base import BaseExtractor, ExtractedItem

logger = get_logger(__name__)

BASE_URL = "https://hn.algolia.com/api/v1/search_by_date"
# Items are stored under the canonical HN source so downstream scoring,
# velocity thresholds, and the frontend treat them like any HN item.
_STORAGE_SOURCE = "hackernews"


def _host_matches(host: str, domain: str) -> bool:
    """True if host is `domain` or a subdomain of it (registrable-suffix match).

    Rejects lookalikes: "notanthropic.com" and "anthropic.com.evil.io" do NOT
    match "anthropic.com".
    """
    return host == domain or host.endswith(f".{domain}")


class HackerNewsLeadingExtractor(BaseExtractor):
    """Catches authoritative-AI-domain submissions from the HN firehose early."""

    @property
    def source_name(self) -> str:
        return "hackernews_leading"

    async def extract(self, since_hours: int = 24) -> list[ExtractedItem]:
        settings = get_settings()
        allowed = settings.hn_authoritative_domains_list
        max_items = settings.max_items_per_source

        if not allowed:
            logger.info("hn_leading_no_domains_configured")
            return []

        since_ts = int((datetime.now(tz=UTC) - timedelta(hours=since_hours)).timestamp())
        items: list[ExtractedItem] = []
        seen_ids: set[str] = set()

        with extractor_duration_seconds.labels(source=self.source_name).time():
            async with httpx.AsyncClient(
                timeout=30,
                headers={"User-Agent": "AI-News-Platform/1.0"},
            ) as client:
                # No server-side OR across domains, so query each domain
                # separately. Per-domain errors are isolated.
                domains_failed = 0
                for domain in allowed:
                    try:
                        domain_items = await self._fetch_domain(
                            client, domain, since_ts, allowed, seen_ids
                        )
                    except Exception as exc:
                        domains_failed += 1
                        logger.warning("hn_leading_domain_failed", domain=domain, error=str(exc))
                        continue
                    items.extend(domain_items)
                    if len(items) >= max_items:
                        items = items[:max_items]
                        break

        # An empty result is the normal happy path (authoritative-domain hits are
        # rare); only a total failure across every domain is alert-worthy.
        if domains_failed == len(allowed):
            extractor_errors_total.labels(source=self.source_name).inc()

        items_extracted_total.labels(source=self.source_name).inc(len(items))
        logger.info(
            "extraction_complete",
            source=self.source_name,
            count=len(items),
            domains=len(allowed),
        )
        return items

    async def _fetch_domain(
        self,
        client: httpx.AsyncClient,
        domain: str,
        since_ts: int,
        allowed: list[str],
        seen_ids: set[str],
    ) -> list[ExtractedItem]:
        """Fetch recent story submissions whose URL is on `domain`.

        Uses a URL-scoped Algolia query (`restrictSearchableAttributes=url`) so
        the lookback window is honored regardless of overall firehose volume.
        Every hit is re-verified host-side as a belt-and-suspenders check.
        """
        params = {
            "query": domain,
            "restrictSearchableAttributes": "url",
            "tags": "story",
            "numericFilters": f"created_at_i>{since_ts}",
            "hitsPerPage": 100,
        }
        resp = await client.get(BASE_URL, params=params)
        resp.raise_for_status()
        data = resp.json()

        items: list[ExtractedItem] = []
        for hit in data.get("hits", []):
            url = hit.get("url")
            if not url:
                continue

            host = urlparse(url).netloc.lower().split(":")[0].rstrip(".")
            if not any(_host_matches(host, d) for d in allowed):
                continue

            story_id = hit.get("objectID", "")
            if story_id in seen_ids:
                continue
            seen_ids.add(story_id)

            try:
                created_at = datetime.fromtimestamp(hit.get("created_at_i", 0), tz=UTC)
            except (ValueError, OSError, TypeError):
                created_at = None

            title = html.unescape(hit.get("title") or "")
            items.append(
                ExtractedItem(
                    title=title,
                    source=_STORAGE_SOURCE,
                    url=url,
                    text=title,
                    author=hit.get("author", "unknown"),
                    published_at=created_at,
                    score=hit.get("points", 0),
                    source_created_at=created_at,
                    metadata={
                        "lane": "leading",
                        "domain": host,
                        "story_id": story_id,
                        "hn_url": f"https://news.ycombinator.com/item?id={story_id}",
                        "num_comments": hit.get("num_comments", 0),
                    },
                )
            )

        return items
