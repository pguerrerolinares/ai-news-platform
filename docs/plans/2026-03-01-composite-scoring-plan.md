# Composite Scoring System — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace flat feed ranking with a composite score combining engagement velocity, LLM relevance, recency, and topic weight.

**Architecture:** New `CompositeScorer` component in the pipeline computes a 0-1 composite score per item after classification. Extractors are updated to capture real content creation dates for velocity calculation. Score is stored in a new `composite_score` column and used for feed sorting.

**Tech Stack:** Python 3.12+, SQLAlchemy async, Alembic, FastAPI, pytest

**Design doc:** `docs/plans/2026-03-01-composite-scoring-design.md`

---

### Task 1: Add `source_created_at` to ExtractedItem and `composite_score` to ClassifiedItem

**Files:**
- Modify: `src/extractors/base.py:12-23` (ExtractedItem dataclass)
- Modify: `src/classifiers/base.py:12-23` (ClassifiedItem dataclass)
- Test: `tests/unit/test_extractors.py` (verify existing tests pass)

**Step 1: Add `source_created_at` field to ExtractedItem**

In `src/extractors/base.py`, add after `published_at` (line ~21):

```python
source_created_at: datetime | None = None  # actual creation date on source platform
```

**Step 2: Add `composite_score` field to ClassifiedItem**

In `src/classifiers/base.py`, add after `source_count` (line ~23):

```python
composite_score: float | None = None  # 0.0-1.0, computed by CompositeScorer
```

**Step 3: Run existing tests to verify no regressions**

Run: `pytest tests/unit/ -x --timeout=30 -q`
Expected: All pass (new fields have defaults)

**Step 4: Commit**

```bash
git add src/extractors/base.py src/classifiers/base.py
git commit -m "feat: add source_created_at and composite_score to data models"
```

---

### Task 2: Add columns to NewsItem model + Alembic migration

**Files:**
- Modify: `src/core/models.py:55-108` (NewsItem)
- Create: `alembic/versions/010_composite_scoring.py`

**Step 1: Add columns to NewsItem model**

In `src/core/models.py`, after `score` field (line ~79), add:

```python
source_created_at: Mapped[datetime | None] = mapped_column(
    DateTime(timezone=True), default=None
)
composite_score: Mapped[float | None] = mapped_column(Float, default=None)
```

Import `Float` from sqlalchemy if not already imported.

**Step 2: Add index to `__table_args__`**

In the `__table_args__` tuple (line ~99), add:

```python
Index("idx_news_items_composite_score", "composite_score"),
```

**Step 3: Create Alembic migration**

Create `alembic/versions/010_composite_scoring.py`:

```python
"""Add source_created_at and composite_score columns to news_items.

Revision ID: 010
Revises: 009
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "010"
down_revision = "009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "news_items",
        sa.Column("source_created_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "news_items",
        sa.Column("composite_score", sa.Float(), nullable=True),
    )
    op.create_index(
        "idx_news_items_composite_score", "news_items", ["composite_score"]
    )


def downgrade() -> None:
    op.drop_index("idx_news_items_composite_score", table_name="news_items")
    op.drop_column("news_items", "composite_score")
    op.drop_column("news_items", "source_created_at")
```

**Step 4: Run existing tests to verify no regressions**

Run: `pytest tests/unit/ -x --timeout=30 -q`
Expected: All pass

**Step 5: Commit**

```bash
git add src/core/models.py alembic/versions/010_composite_scoring.py
git commit -m "feat: add source_created_at and composite_score columns with migration"
```

---

### Task 3: Add composite scoring settings to Config

**Files:**
- Modify: `src/core/config.py:98-99` (after min_relevance_score)
- Test: `tests/unit/test_config.py` or inline verification

**Step 1: Add settings fields**

In `src/core/config.py`, after `min_relevance_score` (line ~99), add:

```python
# --- Composite Scoring Weights (must sum to 1.0 for each mode) ---
composite_w_velocity: float = 0.35
composite_w_relevance: float = 0.30
composite_w_recency: float = 0.20
composite_w_topic: float = 0.15
# Weights when velocity is unavailable (Arxiv, RSS)
composite_no_velocity_w_relevance: float = 0.45
composite_no_velocity_w_recency: float = 0.30
composite_no_velocity_w_topic: float = 0.25
# Recency decay window in hours
composite_recency_window_hours: float = 48.0
# --- Velocity Thresholds (saturation point = 1.0) ---
velocity_threshold_github: float = 500.0        # stars/day
velocity_threshold_hackernews: float = 200.0     # points/hour
velocity_threshold_reddit: float = 150.0         # upvotes/hour
velocity_threshold_huggingface: float = 100_000.0  # downloads/day (models)
velocity_threshold_huggingface_paper: float = 50.0  # upvotes/hour
```

**Step 2: Run existing tests**

Run: `pytest tests/unit/ -x --timeout=30 -q`
Expected: All pass (new fields have defaults)

**Step 3: Commit**

```bash
git add src/core/config.py
git commit -m "feat: add composite scoring weight and velocity threshold settings"
```

---

### Task 4: GitHub extractor — capture `created_at`

**Files:**
- Modify: `src/extractors/github.py:104-127`
- Test: `tests/unit/test_github_extractor.py`

**Step 1: Write the failing test**

In the GitHub extractor test file, add a test that verifies `source_created_at` is set:

```python
async def test_extract_captures_repo_created_at(self):
    """source_created_at should be set from GitHub repo created_at field."""
    mock_repo = {
        "full_name": "org/repo",
        "name": "repo",
        "description": "Test repo",
        "html_url": "https://github.com/org/repo",
        "stargazers_count": 5000,
        "forks_count": 100,
        "language": "Python",
        "topics": ["ai"],
        "pushed_at": "2026-03-01T00:00:00Z",
        "created_at": "2024-06-15T10:30:00Z",
        "owner": {"login": "org"},
    }
    # Mock the API response to return this repo
    # (follow existing test patterns for mocking httpx)
    ...
    items = await extractor.extract(since=some_cutoff)
    assert items[0].source_created_at is not None
    assert items[0].source_created_at.year == 2024
    assert items[0].source_created_at.month == 6
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_github_extractor.py::TestGitHubExtractor::test_extract_captures_repo_created_at -v`
Expected: FAIL — `source_created_at` is None

**Step 3: Implement — parse `created_at` in GitHub extractor**

In `src/extractors/github.py`, around line 105 where `pushed_at` is parsed, add:

```python
created_str = repo.get("created_at", "")
created_at_dt = None
if created_str:
    created_at_dt = datetime.fromisoformat(created_str.replace("Z", "+00:00"))
```

Then in the `ExtractedItem()` constructor (around line 109), add:

```python
source_created_at=created_at_dt,
```

Also add `"created_at": repo.get("created_at")` to the metadata dict.

**Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_github_extractor.py::TestGitHubExtractor::test_extract_captures_repo_created_at -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/extractors/github.py tests/unit/test_github_extractor.py
git commit -m "feat: capture repo created_at in GitHub extractor for velocity"
```

---

### Task 5: HuggingFace extractor — capture model creation date

**Files:**
- Modify: `src/extractors/huggingface.py:105-146`
- Test: `tests/unit/test_huggingface_extractor.py`

**Step 1: Investigate HuggingFace API response**

Check if the HF API provides `createdAt` for models. The HF Hub API `/api/models` endpoint includes `createdAt` in its response. Add it similarly to GitHub.

**Step 2: Write the failing test**

```python
async def test_extract_models_captures_created_at(self):
    """source_created_at should be set from HF model createdAt field."""
    mock_model = {
        "modelId": "org/model",
        "lastModified": "2026-03-01T00:00:00Z",
        "createdAt": "2025-01-10T08:00:00Z",
        "downloads": 50000,
        "likes": 200,
        "pipeline_tag": "text-generation",
        "tags": ["transformers"],
    }
    ...
    items = await extractor.extract(since=some_cutoff)
    assert items[0].source_created_at is not None
    assert items[0].source_created_at.year == 2025
```

**Step 3: Run test to verify it fails**

Run: `pytest tests/unit/test_huggingface_extractor.py -k "created_at" -v`
Expected: FAIL

**Step 4: Implement — parse `createdAt` in HuggingFace extractor**

In `src/extractors/huggingface.py`, around where `lastModified` is parsed (line ~118), add:

```python
created_str = model.get("createdAt", "")
hf_created_at = None
if created_str:
    hf_created_at = datetime.fromisoformat(created_str.replace("Z", "+00:00"))
```

Set `source_created_at=hf_created_at` in the `ExtractedItem()` constructor.

**Step 5: Run test to verify it passes**

Run: `pytest tests/unit/test_huggingface_extractor.py -k "created_at" -v`
Expected: PASS

**Step 6: Commit**

```bash
git add src/extractors/huggingface.py tests/unit/test_huggingface_extractor.py
git commit -m "feat: capture model createdAt in HuggingFace extractor for velocity"
```

---

### Task 6: Create CompositeScorer — core logic (TDD)

This is the main new component. Full TDD.

**Files:**
- Create: `src/pipeline/composite_scorer.py`
- Create: `tests/unit/test_composite_scorer.py`

**Step 1: Write tests first**

Create `tests/unit/test_composite_scorer.py`:

```python
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
        velocity = compute_velocity(
            source="hackernews", score=600, published_at=published, now=now
        )
        assert velocity == pytest.approx(100.0, rel=0.01)  # 600/6

    def test_reddit_velocity_upvotes_per_hour(self):
        """Reddit velocity = upvotes / hours_since_post."""
        now = datetime(2026, 3, 1, 12, 0, tzinfo=UTC)
        published = datetime(2026, 3, 1, 9, 0, tzinfo=UTC)  # 3 hours ago
        velocity = compute_velocity(
            source="reddit", score=450, published_at=published, now=now
        )
        assert velocity == pytest.approx(150.0, rel=0.01)  # 450/3

    def test_huggingface_model_velocity_is_downloads(self):
        """HF model downloads are already a 24h velocity."""
        velocity = compute_velocity(
            source="huggingface", score=50000,
            metadata={"type": "model"},
        )
        assert velocity == 50000

    def test_huggingface_paper_velocity_upvotes_per_hour(self):
        """HF paper velocity = upvotes / hours_since_publication."""
        now = datetime(2026, 3, 1, 12, 0, tzinfo=UTC)
        published = datetime(2026, 3, 1, 2, 0, tzinfo=UTC)  # 10 hours ago
        velocity = compute_velocity(
            source="huggingface", score=100, published_at=published,
            metadata={"type": "daily_paper"}, now=now,
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
        velocity = compute_velocity(
            source="hackernews", score=100, published_at=published, now=now
        )
        # Floor at 1 hour: 100/1 = 100
        assert velocity == pytest.approx(100.0, rel=0.01)

    def test_github_no_created_at_uses_published_at(self):
        """If source_created_at missing, fall back to published_at."""
        now = datetime(2026, 3, 1, tzinfo=UTC)
        published = datetime(2026, 2, 15, tzinfo=UTC)  # 14 days ago
        velocity = compute_velocity(
            source="github", score=7000,
            source_created_at=None, published_at=published, now=now,
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
            source="arxiv", score=0, topic="papers",
            relevance=0.90, published_at=now,
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
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/test_composite_scorer.py -v`
Expected: FAIL — `src.pipeline.composite_scorer` does not exist

**Step 3: Implement CompositeScorer**

Create `src/pipeline/composite_scorer.py`:

```python
from __future__ import annotations

from datetime import UTC, datetime

from src.classifiers.base import ClassifiedItem
from src.core.config import get_settings
from src.core.logging import get_logger

log = get_logger(__name__)

TOPIC_WEIGHTS: dict[str, float] = {
    "models": 1.0,
    "products": 1.0,
    "regulation": 1.0,
    "agents": 0.95,
    "tools": 0.85,
    "open_source": 0.85,
    "papers": 0.70,
}

DEFAULT_TOPIC_WEIGHT = 0.5

# Sources that have no engagement data
_NO_VELOCITY_SOURCES = frozenset({"arxiv", "rss"})

# Minimum age floor to avoid division by zero
_MIN_AGE_HOURS = 1.0
_MIN_AGE_DAYS = _MIN_AGE_HOURS / 24.0


def compute_velocity(
    source: str,
    score: int | None,
    source_created_at: datetime | None = None,
    published_at: datetime | None = None,
    metadata: dict | None = None,
    now: datetime | None = None,
) -> float | None:
    """Compute engagement velocity for a source.

    Returns None for sources without engagement data (arxiv, rss).
    """
    if source in _NO_VELOCITY_SOURCES:
        return None

    if not score or score <= 0:
        return 0.0

    if now is None:
        now = datetime.now(UTC)

    metadata = metadata or {}

    if source == "github":
        # GitHub: stars / days since repo creation
        ref_date = source_created_at or published_at
        if ref_date is None:
            return 0.0
        age_days = max(_MIN_AGE_DAYS, (now - ref_date).total_seconds() / 86400)
        return score / age_days

    if source == "huggingface" and metadata.get("type") == "daily_paper":
        # HF papers: upvotes / hours since publication
        if published_at is None:
            return 0.0
        age_hours = max(_MIN_AGE_HOURS, (now - published_at).total_seconds() / 3600)
        return score / age_hours

    if source == "huggingface":
        # HF models: downloads field is already 24h velocity
        return float(score)

    # HN, Reddit: score / hours since publication
    if published_at is None:
        return 0.0
    age_hours = max(_MIN_AGE_HOURS, (now - published_at).total_seconds() / 3600)
    return score / age_hours


class CompositeScorer:
    """Computes composite ranking score from velocity, relevance, recency, topic."""

    def __init__(self) -> None:
        settings = get_settings()
        self._w_vel = settings.composite_w_velocity
        self._w_rel = settings.composite_w_relevance
        self._w_rec = settings.composite_w_recency
        self._w_top = settings.composite_w_topic
        self._nv_w_rel = settings.composite_no_velocity_w_relevance
        self._nv_w_rec = settings.composite_no_velocity_w_recency
        self._nv_w_top = settings.composite_no_velocity_w_topic
        self._recency_window = settings.composite_recency_window_hours
        self._velocity_thresholds = {
            "github": settings.velocity_threshold_github,
            "hackernews": settings.velocity_threshold_hackernews,
            "reddit": settings.velocity_threshold_reddit,
            "huggingface": settings.velocity_threshold_huggingface,
            "huggingface_paper": settings.velocity_threshold_huggingface_paper,
        }

    def _normalize_velocity(self, velocity: float, source: str, metadata: dict | None = None) -> float:
        metadata = metadata or {}
        key = source
        if source == "huggingface" and metadata.get("type") == "daily_paper":
            key = "huggingface_paper"
        threshold = self._velocity_thresholds.get(key, 500.0)
        return min(1.0, velocity / threshold)

    def _normalize_relevance(self, relevance: float) -> float:
        return max(0.0, min(1.0, (relevance - 0.75) / 0.25))

    def _compute_recency(self, published_at: datetime | None, now: datetime) -> float:
        if published_at is None:
            return 0.0
        age_hours = (now - published_at).total_seconds() / 3600
        return max(0.0, 1.0 - (age_hours / self._recency_window))

    def score(self, item: ClassifiedItem, now: datetime | None = None) -> float:
        """Compute composite score for a single classified item."""
        if now is None:
            now = datetime.now(UTC)

        ei = item.item  # ExtractedItem
        relevance_norm = self._normalize_relevance(item.relevance_score)
        recency = self._compute_recency(ei.published_at, now)
        topic_weight = TOPIC_WEIGHTS.get(item.topic, DEFAULT_TOPIC_WEIGHT)

        velocity = compute_velocity(
            source=ei.source,
            score=ei.score,
            source_created_at=ei.source_created_at,
            published_at=ei.published_at,
            metadata=ei.metadata,
            now=now,
        )

        if velocity is None:
            # No velocity: Arxiv, RSS
            return (
                self._nv_w_rel * relevance_norm
                + self._nv_w_rec * recency
                + self._nv_w_top * topic_weight
            )

        velocity_norm = self._normalize_velocity(velocity, ei.source, ei.metadata)
        return (
            self._w_vel * velocity_norm
            + self._w_rel * relevance_norm
            + self._w_rec * recency
            + self._w_top * topic_weight
        )

    def score_batch(self, items: list[ClassifiedItem]) -> list[ClassifiedItem]:
        """Compute composite scores for a batch, setting composite_score on each."""
        now = datetime.now(UTC)
        for item in items:
            item.composite_score = self.score(item, now=now)
        log.info("composite_scoring_complete", count=len(items))
        return items
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/unit/test_composite_scorer.py -v`
Expected: All PASS

**Step 5: Run full test suite for regressions**

Run: `pytest tests/unit/ -x --timeout=30 -q`
Expected: All pass

**Step 6: Commit**

```bash
git add src/pipeline/composite_scorer.py tests/unit/test_composite_scorer.py
git commit -m "feat: add CompositeScorer with velocity-based ranking (TDD)"
```

---

### Task 7: Fix LLM classifier prompt with anchored examples

**Files:**
- Modify: `src/classifiers/llm.py:148-155` (relevance scale in prompt)
- Test: `tests/unit/test_llm_classifier.py`

**Step 1: Write the failing test**

Add a test that verifies the prompt contains the new anchor examples:

```python
def test_prompt_contains_anchor_examples(self):
    """Prompt should use concrete anchor examples for relevance scoring."""
    from src.classifiers.llm import _build_prompt
    items = [ExtractedItem(title="Test", source="github")]
    prompt = _build_prompt(items, "models: AI models")
    assert "OpenAI releases GPT-5" in prompt
    assert "FORCED DISTRIBUTION" in prompt
    assert "MUST NOT give more than" in prompt
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_llm_classifier.py -k "anchor" -v`
Expected: FAIL — current prompt doesn't contain these strings

**Step 3: Replace relevance scale in prompt**

In `src/classifiers/llm.py`, replace lines 148-155 (the RELEVANCE SCALE block):

```python
# OLD (lines 148-155):
RELEVANCE SCALE (use the full range, do NOT put 0.9 on everything):
- 1.0: Major launch from top company or breakthrough with massive impact
- 0.95: Important release with verifiable metrics surpassing SOTA
- 0.9: Significant news with clear industry impact
- 0.85: Interesting paper or release but incremental
- 0.8: Relevant but routine content
- 0.75: Minimally relevant, niche
- <0.75: Reject (is_news=false)

# NEW:
RELEVANCE SCORING — you MUST use the full range. Each item gets ONE score.
Score by comparing against these real-world anchors:

1.0  = "OpenAI releases GPT-5 with 2x performance on all benchmarks"
0.95 = "Meta open-sources Llama 4 405B model weights"
0.90 = "Google DeepMind publishes new SOTA on protein folding"
0.85 = "New framework reaches #1 on GitHub trending with 10K stars in a day"
0.80 = "Incremental update to an existing popular tool"
0.75 = "Niche library or minor paper with limited audience"
<0.75: Reject (is_news=false)

FORCED DISTRIBUTION: In a batch of {len(batch)} items, you MUST NOT give more than
3 items the same score. Spread your scores across the range.
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_llm_classifier.py -k "anchor" -v`
Expected: PASS

**Step 5: Run full classifier tests**

Run: `pytest tests/unit/test_llm_classifier.py -v`
Expected: All pass

**Step 6: Commit**

```bash
git add src/classifiers/llm.py tests/unit/test_llm_classifier.py
git commit -m "feat: improve LLM relevance prompt with anchored examples and forced distribution"
```

---

### Task 8: Pipeline integration — store `source_created_at` and `composite_score`

**Files:**
- Modify: `src/pipeline/pipeline.py:129-175` (store function)
- Modify: `src/pipeline/pipeline.py:351-370` (pipeline flow — add scoring step)

**Step 1: Update `_store_classified_items` to persist new fields**

In `src/pipeline/pipeline.py`, in the `.values(...)` block of the insert statement (lines 143-162), add:

```python
source_created_at=item.source_created_at,  # after score (line 152)
composite_score=ci.composite_score,         # after dev_value_score (line 161)
```

**Step 2: Add CompositeScorer step to pipeline flow**

In `src/pipeline/pipeline.py`, after the classify step and before validate, add:

```python
from src.pipeline.composite_scorer import CompositeScorer

# After classification (after event dedup, before validate):
scorer = CompositeScorer()
classified = scorer.score_batch(classified)
log.info("composite_scoring_done", scored=len(classified))
```

**Step 3: Run existing pipeline tests**

Run: `pytest tests/unit/ -k "pipeline" -v --timeout=30`
Expected: All pass (or update mocks if needed)

**Step 4: Commit**

```bash
git add src/pipeline/pipeline.py
git commit -m "feat: integrate CompositeScorer into pipeline and persist scores"
```

---

### Task 9: Update items endpoint to sort by `composite_score`

**Files:**
- Modify: `src/api/routes/items.py:285-288` (sort logic in `list_latest_items`)

**Step 1: Write the failing test**

```python
async def test_latest_items_sort_by_composite_score(self, client, session):
    """Default sort=relevance should order by composite_score DESC."""
    # Insert items with different composite_score values
    ...
    response = await client.get("/api/items/latest", headers=auth_headers)
    items = response.json()
    scores = [i["composite_score"] for i in items if i["composite_score"] is not None]
    assert scores == sorted(scores, reverse=True)
```

**Step 2: Run test to verify it fails**

Expected: FAIL — currently sorts by `score` not `composite_score`

**Step 3: Update sort logic**

In `src/api/routes/items.py`, replace lines 285-288:

```python
# OLD:
if sort == "recent":
    query = query.order_by(effective_date.desc())
else:
    query = query.order_by(NewsItem.score.desc().nulls_last(), effective_date.desc())

# NEW:
if sort == "recent":
    query = query.order_by(effective_date.desc())
else:
    query = query.order_by(
        NewsItem.composite_score.desc().nulls_last(), effective_date.desc()
    )
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/unit/ -k "latest_items_sort" -v`
Expected: PASS

**Step 5: Also update `NewsItemResponse` schema if `composite_score` is not exposed**

Check if `NewsItemResponse` (in routes or schemas) needs `composite_score: float | None` added so the API returns it.

**Step 6: Commit**

```bash
git add src/api/routes/items.py tests/
git commit -m "feat: sort feed by composite_score instead of raw engagement"
```

---

### Task 10: Verify end-to-end and run full test suite

**Files:**
- All modified files

**Step 1: Run full lint and type checks**

Run: `ruff check . && ruff format --check . && pyright .`
Expected: All pass

**Step 2: Run full test suite**

Run: `pytest tests/unit/ -x --timeout=30`
Expected: All pass, 80%+ coverage on new code

**Step 3: Manual verification with sample data**

Test the composite scorer manually with the example data from the design doc to verify rankings match expected output.

**Step 4: Final commit if any fixes needed**

```bash
git commit -m "fix: address lint/type issues from composite scoring integration"
```
