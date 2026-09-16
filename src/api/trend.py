"""Pure helpers for GET /api/stats/trend: bucket calendar and response assembly.

No calibrated threshold: pre-check (a)
(docs/superpowers/specs/2026-09-15-mcp-descubrimiento-baseline/tau.md)
found that a single global cosine-distance cutoff does not separate relevant from
irrelevant items across queries (spread 0.19 > 0.10 between the best per-query cutoff).
The cutoff is instead an explicit request parameter (``max_distance``), and the response
also reports a cumulative histogram at 5 fixed bands so the caller (an LLM) can read the
shape of the distribution instead of trusting a single number.
"""

from __future__ import annotations

from datetime import date, timedelta

from src.api.schemas import TrendBucket

TREND_DISTANCE_EDGES: tuple[float, ...] = (0.30, 0.35, 0.40, 0.45, 0.50)


def _next_month(d: date) -> date:
    return date(d.year + 1, 1, 1) if d.month == 12 else date(d.year, d.month + 1, 1)


def bucket_starts(since: date, until: date, granularity: str) -> list[date]:
    """Start date of every bucket overlapping [since, until], oldest first.

    Weeks are ISO weeks (start Monday) and months start on day 1 — the same
    boundaries as Postgres ``date_trunc('week'|'month', ...)``, so SQL rows key
    straight into this calendar. Buckets with no rows are still present.
    """
    if granularity == "week":
        current = since - timedelta(days=since.weekday())
    else:
        current = since.replace(day=1)
    starts: list[date] = []
    while current <= until:
        starts.append(current)
        current = current + timedelta(days=7) if granularity == "week" else _next_month(current)
    return starts


def _cumulative_by_distance(band_counts: dict[int, int]) -> dict[str, int]:
    """Cumulative count at each fixed edge, from a histogram keyed by width_bucket index.

    ``width_bucket(dist, TREND_DISTANCE_EDGES)`` returns 0 for dist < edges[0], i for
    edges[i-1] <= dist < edges[i], and len(edges) for dist >= edges[-1]. The cumulative
    count "within edge i" (0-indexed) is the sum of bands 0..i.
    """
    cumulative: dict[str, int] = {}
    running = 0
    for i, edge in enumerate(TREND_DISTANCE_EDGES):
        running += band_counts.get(i, 0)
        cumulative[f"{edge:.2f}"] = running
    return cumulative


def build_buckets(
    starts: list[date],
    counts: dict[tuple[date, str], int],
    totals: dict[date, int],
    bands: dict[tuple[date, str, int], int] | None = None,
) -> list[TrendBucket]:
    """One TrendBucket per start; share = count / total_in_bucket (0.0 when empty).

    ``bands`` (bucket, source, width_bucket index) -> count is only passed for semantic
    trend and becomes each bucket's cumulative ``by_distance`` (all 5 edges present,
    0 where empty); ``None`` for keyword, where distance has no meaning.
    """
    buckets: list[TrendBucket] = []
    for start in starts:
        by_source = {source: n for (bucket, source), n in counts.items() if bucket == start}
        count = sum(by_source.values())
        total = totals.get(start, 0)
        by_distance = None
        if bands is not None:
            band_counts: dict[int, int] = {}
            for (bucket, _source, band), n in bands.items():
                if bucket == start:
                    band_counts[band] = band_counts.get(band, 0) + n
            by_distance = _cumulative_by_distance(band_counts)
        buckets.append(
            TrendBucket(
                bucket=start,
                count=count,
                total_in_bucket=total,
                share=round(count / total, 4) if total else 0.0,
                by_source=dict(sorted(by_source.items())),
                by_distance=by_distance,
            )
        )
    return buckets
