"""Tests for the trend bucket calendar and response assembly."""

from __future__ import annotations

from datetime import date

from src.api.trend import TREND_DISTANCE_EDGES, bucket_starts, build_buckets


class TestBucketStarts:
    def test_weeks_start_on_iso_monday(self):
        # 2026-09-03 is a Thursday; 2026-09-15 is a Tuesday.
        assert bucket_starts(date(2026, 9, 3), date(2026, 9, 15), "week") == [
            date(2026, 8, 31),
            date(2026, 9, 7),
            date(2026, 9, 14),
        ]

    def test_months_cross_year_boundary(self):
        assert bucket_starts(date(2025, 11, 20), date(2026, 2, 2), "month") == [
            date(2025, 11, 1),
            date(2025, 12, 1),
            date(2026, 1, 1),
            date(2026, 2, 1),
        ]


class TestBuildBuckets:
    def test_keyword_has_no_by_distance(self):
        """Without a bands dict (keyword), by_distance is None throughout."""
        starts = [date(2026, 8, 31), date(2026, 9, 7)]
        counts = {(date(2026, 9, 7), "github"): 1, (date(2026, 9, 7), "arxiv"): 2}
        totals = {date(2026, 9, 7): 9}

        buckets = build_buckets(starts, counts, totals)

        assert [b.model_dump() for b in buckets] == [
            {
                "bucket": date(2026, 8, 31),
                "count": 0,
                "total_in_bucket": 0,
                "share": 0.0,
                "by_source": {},
                "by_distance": None,
            },
            {
                "bucket": date(2026, 9, 7),
                "count": 3,
                "total_in_bucket": 9,
                "share": 0.3333,
                "by_source": {"arxiv": 2, "github": 1},
                "by_distance": None,
            },
        ]

    def test_semantic_by_distance_is_cumulative_with_all_edges_present(self):
        """3 items at cosine distance 0.10 / 0.38 / 0.47 from the query (decision's
        worked example): by_distance accumulates band counts at each fixed edge, and
        all 5 edges are present even for a bucket with zero bands.
        """
        assert TREND_DISTANCE_EDGES == (0.30, 0.35, 0.40, 0.45, 0.50)
        starts = [date(2026, 8, 31), date(2026, 9, 7)]
        counts = {
            (date(2026, 9, 7), "arxiv"): 2
        }  # within max_distance=0.40: the 0.10 and 0.38 items
        totals = {date(2026, 9, 7): 3}
        # width_bucket index: 0 = dist < 0.30 (the 0.10 item); 2 = 0.35 <= dist < 0.40
        # (the 0.38 item); 4 = 0.45 <= dist < 0.50 (the 0.47 item, a different source).
        bands = {
            (date(2026, 9, 7), "arxiv", 0): 1,
            (date(2026, 9, 7), "arxiv", 2): 1,
            (date(2026, 9, 7), "github", 4): 1,
        }

        buckets = build_buckets(starts, counts, totals, bands=bands)

        empty, week = buckets
        assert empty.by_distance == {"0.30": 0, "0.35": 0, "0.40": 0, "0.45": 0, "0.50": 0}
        assert week.by_distance == {"0.30": 1, "0.35": 1, "0.40": 2, "0.45": 2, "0.50": 3}
        assert (
            week.count == 2
        )  # count is independent of by_distance: at max_distance, from `counts`
