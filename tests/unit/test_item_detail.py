"""Tests for the item detail rules (engagement kind, discussion link)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest

from src.api.item_detail import discussion_url_for, engagement_for, to_item_detail
from src.core.models import NewsItem


class TestEngagementFor:
    @pytest.mark.parametrize(
        ("source", "score", "metadata", "expected"),
        [
            ("hackernews", 120, {}, ("points", 120)),
            ("github", 5400, {}, ("stars", 5400)),
            ("github_search", 800, {}, ("stars", 800)),
            ("huggingface", 1992040, {"type": "model"}, ("downloads", 1992040)),
            ("huggingface", 37, {"type": "daily_paper"}, ("upvotes", 37)),
        ],
    )
    def test_kind_by_source_and_type(self, source, score, metadata, expected):
        engagement = engagement_for(source, score, metadata)
        assert engagement is not None
        assert (engagement.kind, engagement.value) == expected

    @pytest.mark.parametrize(
        ("source", "score", "metadata"),
        [
            ("arxiv", 0, {}),
            ("rss", 0, {}),
            ("webscraper", 0, None),
            ("huggingface", 10, {}),
            ("hackernews", None, {}),
        ],
    )
    def test_null_when_no_engagement_signal(self, source, score, metadata):
        assert engagement_for(source, score, metadata) is None


class TestDiscussionUrl:
    def test_hn_url_is_the_discussion(self):
        meta = {"hn_url": "https://news.ycombinator.com/item?id=1"}
        assert discussion_url_for(meta) == "https://news.ycombinator.com/item?id=1"

    def test_missing_metadata(self):
        assert discussion_url_for(None) is None
        assert discussion_url_for({"lane": "leading"}) is None


class TestToItemDetail:
    def test_builds_detail_from_orm_item(self):
        item = NewsItem(
            id=uuid.uuid4(),
            title="Show HN: tiny agent memory",
            source="hackernews",
            topic="agents",
            score=42,
            trending=False,
            full_text="Full body, not truncated.",
            metadata_={"hn_url": "https://news.ycombinator.com/item?id=9"},
            created_at=datetime(2026, 9, 1, tzinfo=UTC),
        )
        detail = to_item_detail(item)
        assert detail.full_text == "Full body, not truncated."
        assert detail.discussion_url == "https://news.ycombinator.com/item?id=9"
        assert detail.engagement is not None
        assert detail.engagement.model_dump() == {"kind": "points", "value": 42}
        assert detail.title == "Show HN: tiny agent memory"
