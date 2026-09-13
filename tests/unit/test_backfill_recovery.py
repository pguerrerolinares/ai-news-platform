"""Unit tests for outage recovery logic (src/pipeline/backfill/recovery.py)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from src.extractors.base import ExtractedItem
from src.pipeline.backfill import recovery
from src.pipeline.backfill.extractors import RawItem


class TestInWindow:
    def test_before_window_excluded(self) -> None:
        assert recovery.in_window(datetime(2026, 8, 21, tzinfo=UTC)) is False

    def test_after_window_excluded(self) -> None:
        assert recovery.in_window(datetime(2026, 9, 13, tzinfo=UTC)) is False

    def test_inside_window_included(self) -> None:
        assert recovery.in_window(datetime(2026, 9, 1, tzinfo=UTC)) is True

    def test_none_excluded(self) -> None:
        assert recovery.in_window(None) is False

    def test_naive_datetime_treated_as_utc(self) -> None:
        assert recovery.in_window(datetime(2026, 9, 1)) is True  # noqa: DTZ001


class TestRawToExtracted:
    def test_hackernews_conversion(self) -> None:
        raw = RawItem(
            source="hackernews",
            source_id="123",
            raw_json={"url": "http://a.com", "author": "u1", "num_comments": 4},
            title="AI story",
            score=50,
            published_at=datetime(2026, 9, 1, tzinfo=UTC),
        )
        item = recovery.raw_hn_to_extracted(raw)
        assert item.source == "hackernews"
        assert item.url == "http://a.com"
        assert item.metadata["story_id"] == "123"

    def test_hackernews_conversion_no_url_falls_back_to_hn_link(self) -> None:
        raw = RawItem(
            source="hackernews",
            source_id="123",
            raw_json={},
            title="Ask HN",
            score=10,
            published_at=datetime(2026, 9, 1, tzinfo=UTC),
        )
        item = recovery.raw_hn_to_extracted(raw)
        assert item.url == "https://news.ycombinator.com/item?id=123"

    def test_github_conversion_relabels_source_as_github_search(self) -> None:
        raw = RawItem(
            source="github",
            source_id="acme/repo",
            raw_json={
                "name": "repo",
                "description": "an AI repo",
                "html_url": "https://github.com/acme/repo",
                "owner": {"login": "acme"},
                "stargazers_count": 500,
                "full_name": "acme/repo",
            },
            title="acme/repo",
            score=500,
            published_at=datetime(2026, 9, 1, tzinfo=UTC),
        )
        item = recovery.raw_github_to_extracted(raw)
        assert item.source == "github_search"
        assert item.metadata["recovered_from_outage"] is True
        assert item.title == "repo: an AI repo"


class TestIsRecentRepo:
    """Mirrors prod github_search: skip repos older than github_max_repo_age_days."""

    def _raw(self, created_at: str | None) -> RawItem:
        raw_json = {"created_at": created_at} if created_at is not None else {}
        return RawItem(
            source="github",
            source_id="acme/repo",
            raw_json=raw_json,
            title="acme/repo",
            score=500,
            published_at=datetime(2026, 9, 1, tzinfo=UTC),
        )

    def test_repo_created_within_max_age_of_push_is_recent(self) -> None:
        assert recovery.is_recent_repo(self._raw("2026-06-01T00:00:00Z"), 180) is True

    def test_old_repo_pushed_in_window_is_excluded(self) -> None:
        assert recovery.is_recent_repo(self._raw("2019-01-01T00:00:00Z"), 180) is False

    def test_missing_created_at_is_kept_like_prod(self) -> None:
        assert recovery.is_recent_repo(self._raw(None), 180) is True

    def test_zero_max_age_disables_filter_like_prod(self) -> None:
        assert recovery.is_recent_repo(self._raw("2019-01-01T00:00:00Z"), 0) is True


class TestFilterNew:
    def test_splits_existing_by_content_hash(self) -> None:
        existing = ExtractedItem(title="dup", source="hackernews", url="http://x.com")
        new = ExtractedItem(title="new", source="hackernews", url="http://y.com")
        new_items, already = recovery.filter_new(
            [existing, new], existing_content={existing.content_hash}, existing_url=set()
        )
        assert new_items == [new]
        assert already == 1

    def test_splits_existing_by_url_hash(self) -> None:
        existing = ExtractedItem(title="different title now", source="rss", url="http://x.com")
        assert existing.url_hash is not None
        new_items, already = recovery.filter_new(
            [existing], existing_content=set(), existing_url={existing.url_hash}
        )
        assert new_items == []
        assert already == 1

    def test_item_without_url_only_checked_against_content_hash(self) -> None:
        item = ExtractedItem(title="no url item", source="hackernews", url=None)
        new_items, already = recovery.filter_new([item], existing_content=set(), existing_url=set())
        assert new_items == [item]
        assert already == 0


class TestKeywordBuckets:
    def test_buckets_match_classify_stage_thresholds(self) -> None:
        no_match = ExtractedItem(title="gardening tips", source="rss", url="http://a.com")
        ambiguous = ExtractedItem(title="new AI model released", source="rss", url="http://b.com")
        # "GPT", "LLM", "model" all belong to the same TOPIC_DEFINITIONS["models"]
        # keyword list, so this scores match_count=3 within one topic (auto-accept).
        high_conf = ExtractedItem(
            title="New GPT LLM foundation model released with benchmark results",
            source="rss",
            url="http://c.com",
        )
        auto_reject, to_llm, auto_accept = recovery.keyword_buckets(
            [no_match, ambiguous, high_conf]
        )
        assert auto_reject == 1
        assert to_llm == 1
        assert auto_accept == 1


class TestEstimateLlmCost:
    def test_zero_items_costs_nothing(self) -> None:
        assert recovery.estimate_llm_cost_usd(0) == 0.0

    def test_cost_scales_linearly_and_uses_k26_pricing(self) -> None:
        cost_100 = recovery.estimate_llm_cost_usd(100)
        cost_200 = recovery.estimate_llm_cost_usd(200)
        assert cost_200 == pytest.approx(cost_100 * 2)
        # 100 items * (170 input + 45 output tokens) at k2.6 pricing
        expected = (100 * 170 * 0.95 + 100 * 45 * 4.00) / 1_000_000
        assert cost_100 == pytest.approx(expected)


class TestFilterSimilarTitles:
    """Mirrors seen_filter Pass 2: cross-source dedup by title similarity."""

    def _item(self, title: str) -> ExtractedItem:
        return ExtractedItem(title=title, source="hackernews", url=f"https://x.com/{title}")

    def test_identical_title_is_dropped(self) -> None:
        kept, dropped = recovery.filter_similar_titles(
            [self._item("DeepSeek v4.1 Flash released")], ["deepseek v4.1 flash released"]
        )
        assert kept == []
        assert dropped == 1

    def test_different_title_is_kept(self) -> None:
        item = self._item("Cognition launches SWE-2 model")
        kept, dropped = recovery.filter_similar_titles([item], ["deepseek v4.1 flash released"])
        assert kept == [item]
        assert dropped == 0

    def test_empty_stored_titles_keeps_everything(self) -> None:
        items = [self._item("A new model"), self._item("Another tool")]
        kept, dropped = recovery.filter_similar_titles(items, [])
        assert kept == items
        assert dropped == 0

    def test_comparison_is_case_insensitive(self) -> None:
        kept, dropped = recovery.filter_similar_titles(
            [self._item("OPENAI RELEASES GPT-LIVE-1 IN THE API")],
            ["openai releases gpt-live-1 in the api"],
        )
        assert kept == []
        assert dropped == 1
