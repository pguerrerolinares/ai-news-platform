"""Tests for the CompositeScorer and velocity calculation."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from src.classifiers.base import ClassifiedItem
from src.extractors.base import ExtractedItem
from src.pipeline.composite_scorer import CompositeScorer, compute_velocity


class TestComputeVelocity:
    """Test velocity calculation per source."""

    def test_github_velocity_stars_per_day(self):
        """GitHub velocity = stars / days_since_creation."""
        now = datetime(2026, 3, 1, tzinfo=UTC)
        created = datetime(2026, 2, 1, tzinfo=UTC)  # 28 days ago
        velocity = compute_velocity(
            source="github", score=14000, source_created_at=created, now=now
        )
        assert velocity == pytest.approx(500.0, rel=0.01)  # 14000/28

    def test_hackernews_velocity_points_per_hour(self):
        """HN velocity = points / hours_since_submission."""
        now = datetime(2026, 3, 1, 12, 0, tzinfo=UTC)
        published = datetime(2026, 3, 1, 6, 0, tzinfo=UTC)  # 6 hours ago
        velocity = compute_velocity(source="hackernews", score=600, published_at=published, now=now)
        assert velocity == pytest.approx(100.0, rel=0.01)  # 600/6

    def test_reddit_velocity_upvotes_per_hour(self):
        """Reddit velocity = upvotes / hours_since_post."""
        now = datetime(2026, 3, 1, 12, 0, tzinfo=UTC)
        published = datetime(2026, 3, 1, 9, 0, tzinfo=UTC)  # 3 hours ago
        velocity = compute_velocity(source="reddit", score=450, published_at=published, now=now)
        assert velocity == pytest.approx(150.0, rel=0.01)  # 450/3

    def test_huggingface_model_velocity_is_downloads(self):
        """HF model downloads are already a 24h velocity."""
        velocity = compute_velocity(
            source="huggingface",
            score=50000,
            metadata={"type": "model"},
        )
        assert velocity == 50000

    def test_huggingface_paper_velocity_upvotes_per_hour(self):
        """HF paper velocity = upvotes / hours_since_publication."""
        now = datetime(2026, 3, 1, 12, 0, tzinfo=UTC)
        published = datetime(2026, 3, 1, 2, 0, tzinfo=UTC)  # 10 hours ago
        velocity = compute_velocity(
            source="huggingface",
            score=100,
            published_at=published,
            metadata={"type": "daily_paper"},
            now=now,
        )
        assert velocity == pytest.approx(10.0, rel=0.01)  # 100/10

    def test_arxiv_returns_none(self):
        """Arxiv has no engagement data — velocity is None."""
        velocity = compute_velocity(source="arxiv", score=0)
        assert velocity is None

    def test_rss_returns_none(self):
        """RSS has no engagement data — velocity is None."""
        velocity = compute_velocity(source="rss", score=0)
        assert velocity is None

    def test_zero_age_uses_minimum_1_hour(self):
        """Avoid division by zero: items with age < 1h use 1h floor."""
        now = datetime(2026, 3, 1, 12, 0, tzinfo=UTC)
        published = datetime(2026, 3, 1, 11, 50, tzinfo=UTC)  # 10 min ago
        velocity = compute_velocity(source="hackernews", score=100, published_at=published, now=now)
        # Floor at 1 hour: 100/1 = 100
        assert velocity == pytest.approx(100.0, rel=0.01)

    def test_github_no_created_at_uses_published_at(self):
        """If source_created_at missing, fall back to published_at."""
        now = datetime(2026, 3, 1, tzinfo=UTC)
        published = datetime(2026, 2, 15, tzinfo=UTC)  # 14 days ago
        velocity = compute_velocity(
            source="github",
            score=7000,
            source_created_at=None,
            published_at=published,
            now=now,
        )
        assert velocity == pytest.approx(500.0, rel=0.01)  # 7000/14


class TestCompositeScorer:
    """Test the full composite score calculation."""

    def _make_item(
        self,
        source: str = "github",
        score: int = 10000,
        relevance: float = 0.85,
        topic: str = "tools",
        published_at: datetime | None = None,
        source_created_at: datetime | None = None,
        metadata: dict | None = None,
    ) -> ClassifiedItem:
        if published_at is None:
            published_at = datetime.now(UTC)
        return ClassifiedItem(
            item=ExtractedItem(
                title="Test item",
                source=source,
                url="https://example.com",
                score=score,
                published_at=published_at,
                source_created_at=source_created_at,
                metadata=metadata or {},
            ),
            topic=topic,
            relevance_score=relevance,
        )

    def test_score_between_0_and_1(self):
        """Composite score must always be in [0, 1]."""
        scorer = CompositeScorer()
        item = self._make_item()
        score = scorer.score(item)
        assert 0.0 <= score <= 1.0

    def test_high_velocity_ranks_above_low_velocity(self):
        """Item with high velocity should score higher than low velocity."""
        scorer = CompositeScorer()
        now = datetime.now(UTC)
        high_vel = self._make_item(
            score=5000,
            source_created_at=now - timedelta(days=7),  # 714 stars/day
            published_at=now,
        )
        low_vel = self._make_item(
            score=240000,
            source_created_at=now - timedelta(days=1825),  # 131 stars/day
            published_at=now,
        )
        assert scorer.score(high_vel) > scorer.score(low_vel)

    def test_higher_relevance_boosts_score(self):
        """Higher relevance should produce higher composite score."""
        scorer = CompositeScorer()
        now = datetime.now(UTC)
        high_rel = self._make_item(relevance=0.95, published_at=now)
        low_rel = self._make_item(relevance=0.75, published_at=now)
        assert scorer.score(high_rel) > scorer.score(low_rel)

    def test_news_topic_ranks_above_papers(self):
        """News topic (models) should rank above papers, all else equal."""
        scorer = CompositeScorer()
        now = datetime.now(UTC)
        news = self._make_item(topic="models", published_at=now)
        paper = self._make_item(topic="papers", published_at=now)
        assert scorer.score(news) > scorer.score(paper)

    def test_fresh_item_ranks_above_old(self):
        """Recent item should score higher than 24h+ old item."""
        scorer = CompositeScorer()
        now = datetime.now(UTC)
        fresh = self._make_item(published_at=now)
        old = self._make_item(published_at=now - timedelta(hours=36))
        assert scorer.score(fresh) > scorer.score(old)

    def test_arxiv_uses_no_velocity_weights(self):
        """Arxiv items (no velocity) use alternative weight distribution."""
        scorer = CompositeScorer()
        now = datetime.now(UTC)
        arxiv_item = self._make_item(
            source="arxiv",
            score=0,
            topic="papers",
            relevance=0.90,
            published_at=now,
        )
        score = scorer.score(arxiv_item)
        assert 0.0 <= score <= 1.0
        # With relevance=0.90 -> norm=0.6, recency=1.0, topic=0.7
        # 0.45*0.6 + 0.30*1.0 + 0.25*0.7 = 0.27 + 0.30 + 0.175 = 0.745
        assert score == pytest.approx(0.745, abs=0.05)

    def test_score_batch(self):
        """score_batch processes multiple items and sets composite_score."""
        scorer = CompositeScorer()
        items = [self._make_item() for _ in range(5)]
        scored = scorer.score_batch(items)
        assert len(scored) == 5
        for item in scored:
            assert item.composite_score is not None
            assert 0.0 <= item.composite_score <= 1.0

    def test_unknown_topic_uses_default_weight(self):
        """Unknown topic should use a default weight (0.5)."""
        scorer = CompositeScorer()
        item = self._make_item(topic="unknown_topic")
        score = scorer.score(item)
        assert 0.0 <= score <= 1.0


class TestScoreNewsitem:
    """Test live rescoring of persisted NewsItem objects."""

    def _make_newsitem(
        self,
        source: str = "github",
        score: int = 10000,
        relevance_score: float = 0.85,
        topic: str = "tools",
        published_at: datetime | None = None,
        source_created_at: datetime | None = None,
        metadata_: dict | None = None,
    ) -> object:
        from types import SimpleNamespace

        return SimpleNamespace(
            source=source,
            score=score,
            relevance_score=relevance_score,
            topic=topic,
            published_at=published_at if published_at else datetime.now(UTC),
            source_created_at=source_created_at,
            metadata_=metadata_ or {},
        )

    def test_score_newsitem_returns_float_in_range(self):
        scorer = CompositeScorer()
        item = self._make_newsitem()
        result = scorer.score_newsitem(item)
        assert isinstance(result, float)
        assert 0.0 <= result <= 1.0

    def test_score_newsitem_fresh_item_higher_than_old(self):
        scorer = CompositeScorer()
        now = datetime(2026, 3, 1, 12, 0, tzinfo=UTC)
        fresh = self._make_newsitem(published_at=now - timedelta(hours=1))
        old = self._make_newsitem(published_at=now - timedelta(hours=40))
        assert scorer.score_newsitem(fresh, now=now) > scorer.score_newsitem(old, now=now)

    def test_score_newsitem_none_relevance_treated_as_zero(self):
        scorer = CompositeScorer()
        item = self._make_newsitem(relevance_score=None)
        result = scorer.score_newsitem(item)
        assert 0.0 <= result <= 1.0

    def test_score_newsitem_arxiv_uses_no_velocity_weights(self):
        scorer = CompositeScorer()
        now = datetime(2026, 3, 1, 12, 0, tzinfo=UTC)
        item = self._make_newsitem(
            source="arxiv",
            score=0,
            topic="papers",
            relevance_score=0.90,
            published_at=now,
        )
        result = scorer.score_newsitem(item, now=now)
        assert 0.0 <= result <= 1.0
        assert result == pytest.approx(0.745, abs=0.05)
