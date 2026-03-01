# Feed Algorithm Redesign — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace the simple `ORDER BY composite_score` with a multi-step feed pipeline: variant collapse, percentile-based scoring, and MMR diversification for a Twitter-like feed.

**Architecture:** New `src/feed/` module with three components (variant_collapse, mmr_ranker, feed_builder). Modified composite_scorer for percentile velocity. One-time re-score script. Backfill fix.

**Tech Stack:** SQLAlchemy async, Python stdlib (no new deps), existing Jaccard from credibility validator.

---

### Task 1: Variant Collapse Module

**Files:**
- Create: `src/feed/__init__.py`
- Create: `src/feed/variant_collapse.py`
- Create: `tests/unit/test_variant_collapse.py`

**Step 1: Write failing tests**

```python
"""Tests for HuggingFace model variant collapse."""

import pytest

from src.feed.variant_collapse import normalize_model_name, collapse_variants


class TestNormalizeModelName:
    def test_strips_gguf_suffix(self):
        assert normalize_model_name("unsloth/Qwen3.5-27B-GGUF") == "qwen3.5-27b"

    def test_strips_gptq_suffix(self):
        assert normalize_model_name("TheBloke/Llama-3-70B-GPTQ") == "llama-3-70b"

    def test_strips_awq_suffix(self):
        assert normalize_model_name("bartowski/Phi-4-AWQ") == "phi-4"

    def test_strips_exl2_suffix(self):
        assert normalize_model_name("turboderp/Qwen2.5-72B-EXL2") == "qwen2.5-72b"

    def test_strips_onnx_suffix(self):
        assert normalize_model_name("someone/Model-ONNX") == "model"

    def test_preserves_original_model(self):
        assert normalize_model_name("Qwen/Qwen3.5-27B") == "qwen3.5-27b"

    def test_non_huggingface_returns_none(self):
        assert normalize_model_name("some-github-repo") is None

    def test_handles_nested_org_name(self):
        assert normalize_model_name("meta-llama/Llama-3.1-8B") == "llama-3.1-8b"


class TestCollapseVariants:
    def test_keeps_original_drops_gguf(self):
        items = [
            _make_item("Qwen/Qwen3.5-27B", source="huggingface", score=200000),
            _make_item("unsloth/Qwen3.5-27B-GGUF", source="huggingface", score=180000),
        ]
        result = collapse_variants(items)
        assert len(result) == 1
        assert result[0].title == "Qwen/Qwen3.5-27B"

    def test_keeps_highest_score_variant(self):
        items = [
            _make_item("unsloth/Model-GGUF", source="huggingface", score=500000),
            _make_item("Author/Model", source="huggingface", score=100),
        ]
        result = collapse_variants(items)
        assert len(result) == 1
        assert result[0].score == 500000

    def test_non_huggingface_items_untouched(self):
        items = [
            _make_item("Some HN Post", source="hackernews", score=100),
            _make_item("Another Post", source="hackernews", score=50),
        ]
        result = collapse_variants(items)
        assert len(result) == 2

    def test_mixed_sources(self):
        items = [
            _make_item("Qwen/Qwen3.5-27B", source="huggingface", score=200000),
            _make_item("unsloth/Qwen3.5-27B-GGUF", source="huggingface", score=180000),
            _make_item("Cool HN Post", source="hackernews", score=500),
        ]
        result = collapse_variants(items)
        assert len(result) == 2

    def test_different_models_not_collapsed(self):
        items = [
            _make_item("Qwen/Qwen3.5-27B", source="huggingface", score=200000),
            _make_item("Qwen/Qwen3.5-122B-A10B", source="huggingface", score=100000),
        ]
        result = collapse_variants(items)
        assert len(result) == 2
```

Helper `_make_item` creates a simple dataclass or namedtuple with `title`, `source`, `score` fields. Use the `NewsItem` model or a lightweight stand-in matching the interface `collapse_variants` expects.

**Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/unit/test_variant_collapse.py -v`
Expected: ImportError (module doesn't exist yet)

**Step 3: Implement variant_collapse.py**

```python
"""Collapse HuggingFace model variants (GGUF, GPTQ, AWQ, etc.)."""

from __future__ import annotations

import re

from src.core.logging import get_logger

log = get_logger(__name__)

# Known quantization/format suffixes to strip
_SUFFIXES = re.compile(r"-(GGUF|GPTQ|AWQ|ONNX|EXL2|MLX)$", re.IGNORECASE)

# Known re-upload publishers (strip these to find base model name)
_QUANT_PUBLISHERS = frozenset({
    "unsloth", "thebloke", "bartowski", "turboderp", "mradermacher",
})


def normalize_model_name(title: str) -> str | None:
    """Extract normalized base model name from a HuggingFace title.

    Returns None if title doesn't match org/model pattern.
    """
    # Expect "org/model-name" format
    if "/" not in title:
        return None

    org, model = title.split("/", 1)

    # Strip quantization suffix
    model = _SUFFIXES.sub("", model)

    # If org is a known quant publisher, drop it (base model name is enough)
    # The original publisher's version will have a different org
    if org.lower() in _QUANT_PUBLISHERS:
        pass  # We still use just the model name for grouping

    return model.lower()


def collapse_variants(items: list) -> list:
    """Collapse HuggingFace model variants, keeping highest-score per base model.

    Non-HuggingFace items pass through unchanged.
    """
    non_hf = []
    hf_groups: dict[str, list] = {}

    for item in items:
        source = getattr(item, "source", None)
        title = getattr(item, "title", "") or ""

        if source != "huggingface":
            non_hf.append(item)
            continue

        base_name = normalize_model_name(title)
        if base_name is None:
            non_hf.append(item)
            continue

        hf_groups.setdefault(base_name, []).append(item)

    # Keep highest-score item per group
    kept_hf = []
    collapsed_count = 0
    for base_name, group in hf_groups.items():
        best = max(group, key=lambda x: getattr(x, "score", 0) or 0)
        kept_hf.append(best)
        collapsed_count += len(group) - 1

    if collapsed_count > 0:
        log.info("variants_collapsed", collapsed=collapsed_count, groups=len(hf_groups))

    return non_hf + kept_hf
```

**Step 4: Run tests**

Run: `.venv/bin/python -m pytest tests/unit/test_variant_collapse.py -v`
Expected: ALL PASS

**Step 5: Lint and commit**

```bash
ruff check src/feed/ tests/unit/test_variant_collapse.py && ruff format --check src/feed/ tests/unit/test_variant_collapse.py
git add src/feed/ tests/unit/test_variant_collapse.py
git commit -m "feat: add variant collapse module for HuggingFace model dedup"
```

---

### Task 2: MMR Ranker Module

**Files:**
- Create: `src/feed/mmr_ranker.py`
- Create: `tests/unit/test_mmr_ranker.py`

**Step 1: Write failing tests**

```python
"""Tests for MMR diversification ranker."""

import pytest

from src.feed.mmr_ranker import mmr_rank, item_similarity


class TestItemSimilarity:
    def test_same_source_adds_similarity(self):
        a = _make_item(source="hackernews", topic="models", author="alice", title="GPT-5")
        b = _make_item(source="hackernews", topic="tools", author="bob", title="LangChain")
        sim = item_similarity(a, b)
        assert sim >= 0.3  # same source

    def test_same_topic_adds_similarity(self):
        a = _make_item(source="hackernews", topic="models", author="alice", title="GPT-5")
        b = _make_item(source="github", topic="models", author="bob", title="Llama-3")
        sim = item_similarity(a, b)
        assert sim >= 0.3  # same topic

    def test_same_author_adds_similarity(self):
        a = _make_item(source="hackernews", topic="models", author="Qwen", title="Qwen3")
        b = _make_item(source="huggingface", topic="models", author="Qwen", title="Qwen3-TTS")
        sim = item_similarity(a, b)
        assert sim >= 0.2  # same author

    def test_completely_different_items_low_similarity(self):
        a = _make_item(source="hackernews", topic="models", author="alice", title="GPT-5 released")
        b = _make_item(source="github", topic="tools", author="bob", title="New testing framework")
        sim = item_similarity(a, b)
        assert sim < 0.2

    def test_identical_items_high_similarity(self):
        a = _make_item(source="hackernews", topic="models", author="alice", title="GPT-5 released")
        b = _make_item(source="hackernews", topic="models", author="alice", title="GPT-5 released")
        sim = item_similarity(a, b)
        assert sim >= 0.9


class TestMMRRank:
    def test_basic_reranking(self):
        items = [
            _make_item(source="huggingface", topic="models", composite_score=0.9),
            _make_item(source="huggingface", topic="models", composite_score=0.85),
            _make_item(source="hackernews", topic="tools", composite_score=0.7),
        ]
        result = mmr_rank(items, lambda_=0.7, limit=3)
        # First item should be highest score
        assert result[0].composite_score == 0.9
        # Third should promote diversity (HN item) over 2nd HF item
        # because similarity penalty reduces HF #2's effective score

    def test_pure_quality_mode(self):
        items = [
            _make_item(source="huggingface", topic="models", composite_score=0.9),
            _make_item(source="huggingface", topic="models", composite_score=0.85),
            _make_item(source="hackernews", topic="tools", composite_score=0.7),
        ]
        result = mmr_rank(items, lambda_=1.0, limit=3)
        # lambda=1.0 = pure score, no diversity penalty
        assert result[0].composite_score == 0.9
        assert result[1].composite_score == 0.85
        assert result[2].composite_score == 0.7

    def test_limit_respected(self):
        items = [_make_item(composite_score=0.5 + i * 0.1) for i in range(10)]
        result = mmr_rank(items, lambda_=0.7, limit=5)
        assert len(result) == 5

    def test_empty_input(self):
        assert mmr_rank([], lambda_=0.7, limit=10) == []

    def test_fewer_items_than_limit(self):
        items = [_make_item(composite_score=0.8)]
        result = mmr_rank(items, lambda_=0.7, limit=10)
        assert len(result) == 1
```

**Step 2: Run tests, verify fail**

Run: `.venv/bin/python -m pytest tests/unit/test_mmr_ranker.py -v`

**Step 3: Implement mmr_ranker.py**

```python
"""Maximal Marginal Relevance (MMR) diversification for feed ranking."""

from __future__ import annotations

import re

from src.core.logging import get_logger

log = get_logger(__name__)

_WORD_RE = re.compile(r"[a-zA-Z0-9]+")


def _jaccard(text_a: str, text_b: str) -> float:
    """Jaccard similarity on word tokens."""
    tokens_a = set(_WORD_RE.findall(text_a.lower()))
    tokens_b = set(_WORD_RE.findall(text_b.lower()))
    if not tokens_a or not tokens_b:
        return 0.0
    return len(tokens_a & tokens_b) / len(tokens_a | tokens_b)


def item_similarity(a: object, b: object) -> float:
    """Compute similarity between two feed items.

    Based on source, topic, author, and title overlap.
    """
    score = 0.0
    if getattr(a, "source", None) == getattr(b, "source", None):
        score += 0.3
    if getattr(a, "topic", None) == getattr(b, "topic", None):
        score += 0.3
    if (
        getattr(a, "author", None)
        and getattr(b, "author", None)
        and getattr(a, "author", "") == getattr(b, "author", "")
    ):
        score += 0.2
    title_a = getattr(a, "title", "") or ""
    title_b = getattr(b, "title", "") or ""
    if title_a and title_b:
        score += _jaccard(title_a, title_b) * 0.2
    return score


def mmr_rank(
    candidates: list,
    lambda_: float = 0.7,
    limit: int = 20,
) -> list:
    """Rank items using Maximal Marginal Relevance.

    Balances quality (composite_score) with diversity (low similarity to
    already-selected items).

    Args:
        candidates: Items with composite_score attribute.
        lambda_: 0.0=max diversity, 1.0=pure quality. Default 0.7.
        limit: Max items to return.
    """
    if not candidates:
        return []

    remaining = list(candidates)
    selected: list = []

    for _ in range(min(limit, len(candidates))):
        best_score = float("-inf")
        best_idx = 0

        for i, item in enumerate(remaining):
            quality = getattr(item, "composite_score", 0.0) or 0.0

            # Max similarity to any already-selected item
            if selected:
                max_sim = max(item_similarity(item, s) for s in selected)
            else:
                max_sim = 0.0

            mmr_score = lambda_ * quality - (1 - lambda_) * max_sim

            if mmr_score > best_score:
                best_score = mmr_score
                best_idx = i

        selected.append(remaining.pop(best_idx))

    log.info("mmr_ranking_complete", candidates=len(candidates), selected=len(selected))
    return selected
```

**Step 4: Run tests, lint, commit**

```bash
.venv/bin/python -m pytest tests/unit/test_mmr_ranker.py -v
ruff check src/feed/mmr_ranker.py && ruff format --check src/feed/mmr_ranker.py
git add src/feed/mmr_ranker.py tests/unit/test_mmr_ranker.py
git commit -m "feat: add MMR diversification ranker for feed"
```

---

### Task 3: Feed Builder (orchestrator)

**Files:**
- Create: `src/feed/feed_builder.py`
- Create: `tests/unit/test_feed_builder.py`

**Step 1: Write failing tests**

Test that FeedBuilder:
- Fetches candidates from DB
- Applies variant collapse
- Applies MMR
- Returns paginated results
- Handles `sort=recent` (bypasses MMR)
- Returns correct total count

Use mock DB session returning fixture items from multiple sources.

**Step 2: Implement feed_builder.py**

```python
"""Feed construction pipeline: candidates -> collapse -> MMR -> paginate."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import get_settings
from src.core.logging import get_logger
from src.core.models import NewsItem
from src.core.queries import effective_date
from src.feed.mmr_ranker import mmr_rank
from src.feed.variant_collapse import collapse_variants

log = get_logger(__name__)


class FeedBuilder:
    """Builds a diversified feed from the news items table."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        settings = get_settings()
        self._default_lambda = settings.feed_mmr_lambda
        self._candidate_multiplier = settings.feed_candidate_multiplier

    async def build(
        self,
        *,
        topic: str | None = None,
        source: str | None = None,
        limit: int = 20,
        offset: int = 0,
        diversity: float | None = None,
    ) -> tuple[list[NewsItem], int]:
        """Build a diversified feed.

        Returns (items, total_count).
        """
        lambda_ = diversity if diversity is not None else self._default_lambda
        pool_size = limit * self._candidate_multiplier

        # Fetch candidate pool (larger than needed for MMR selection)
        query = (
            select(NewsItem)
            .where(NewsItem.composite_score.isnot(None))
        )
        if topic:
            query = query.where(NewsItem.topic == topic)
        if source:
            query = query.where(NewsItem.source == source)

        query = query.order_by(
            NewsItem.composite_score.desc().nulls_last(),
            effective_date.desc(),
        )

        # For offset > 0, we need a larger pool to account for items
        # already "consumed" by previous pages
        fetch_size = pool_size + offset
        result = await self._session.execute(query.limit(fetch_size))
        all_candidates = list(result.scalars().all())

        # Collapse variants (HF GGUF/GPTQ dedup)
        collapsed = collapse_variants(all_candidates)

        # Apply MMR on the full collapsed set
        ranked = mmr_rank(collapsed, lambda_=lambda_, limit=offset + limit)

        # Paginate: skip offset, take limit
        page = ranked[offset : offset + limit]
        total = len(collapsed)  # Total after collapse but before pagination

        log.info(
            "feed_built",
            candidates=len(all_candidates),
            after_collapse=len(collapsed),
            returned=len(page),
            total=total,
        )

        return page, total
```

**Step 3: Run tests, lint, commit**

```bash
.venv/bin/python -m pytest tests/unit/test_feed_builder.py -v
ruff check src/feed/ && ruff format --check src/feed/
git add src/feed/feed_builder.py tests/unit/test_feed_builder.py
git commit -m "feat: add FeedBuilder orchestrator for diversified feed"
```

---

### Task 4: Config Settings

**Files:**
- Modify: `src/core/config.py` (add new settings after composite scoring section)

**Step 1: Add settings**

Add after the velocity threshold settings (around line 108):

```python
    # --- Feed Algorithm ---
    feed_mmr_lambda: float = 0.7  # MMR quality vs diversity (0=diverse, 1=quality)
    feed_candidate_multiplier: int = 5  # Candidate pool = limit * multiplier
```

**Step 2: Lint and commit**

```bash
ruff check src/core/config.py && ruff format --check src/core/config.py
git add src/core/config.py
git commit -m "feat: add feed algorithm config settings (MMR lambda, candidate multiplier)"
```

---

### Task 5: Integrate FeedBuilder into API Endpoint

**Files:**
- Modify: `src/api/routes/items.py` — `list_latest_items` function

**Step 1: Write/update tests**

Update `tests/unit/test_items_api.py` TestLatestEndpoint:
- Remove `test_latest_accepts_max_per_source` and `test_latest_rejects_invalid_max_per_source` (param removed)
- Add `test_latest_accepts_diversity_param`
- Add `test_latest_rejects_invalid_diversity`
- Keep backward compat tests

**Step 2: Modify endpoint**

Replace `list_latest_items` to:
- Remove `max_per_source` param
- Add `diversity: float = Query(0.7, ge=0.0, le=1.0, description="Feed diversity (0=quality, 1=diverse)")`
- When `sort=relevance`: use `FeedBuilder.build()`
- When `sort=recent`: keep current chronological query

**Step 3: Run all tests, lint, commit**

```bash
.venv/bin/python -m pytest tests/unit/test_items_api.py -v
ruff check src/api/routes/items.py && ruff format --check src/api/routes/items.py
git add src/api/routes/items.py tests/unit/test_items_api.py
git commit -m "feat: integrate FeedBuilder into /items/latest endpoint"
```

---

### Task 6: Frontend — Replace max_per_source with diversity

**Files:**
- Modify: `frontend/src/pages/Dashboard.tsx`

**Step 1: Update params**

```typescript
const PAGE_SIZE = 20
// Remove MAX_PER_SOURCE constant

// In queryFn params:
const params: Record<string, string> = {
    limit: String(PAGE_SIZE),
    offset: String(pageParam),
    sort: 'relevance',
    // max_per_source removed — diversity is server default (0.7)
}
```

**Step 2: Build and commit**

```bash
cd frontend && npm run build
git add frontend/src/pages/Dashboard.tsx
git commit -m "feat: remove max_per_source, use server-side feed diversity"
```

---

### Task 7: Re-score Existing Items Script

**Files:**
- Create: `scripts/rescore_composite.py`

**Step 1: Implement script**

Script that:
1. Queries all items with `composite_score IS NULL`
2. For each, reconstructs velocity from `source`, `score`, `published_at`, `metadata_`
3. Computes composite score using `CompositeScorer` logic
4. Batch UPDATEs the DB
5. Reports progress

Use direct SQL UPDATE with computed values (no need to load full ORM objects). Batch in groups of 500.

**Step 2: Test locally (dry-run)**

Add `--dry-run` flag that computes but doesn't write.

**Step 3: Commit**

```bash
git add scripts/rescore_composite.py
git commit -m "feat: add one-time rescore script for null composite_scores"
```

---

### Task 8: Fix Backfill Script

**Files:**
- Modify: `scripts/backfill.py` — `phase_classify` function (around line 380)

**Step 1: Add composite scoring**

After LLM classification and before storage, add:

```python
from src.pipeline.composite_scorer import CompositeScorer

# After classified_items is populated:
scorer = CompositeScorer()
classified_items = scorer.score_batch(classified_items)
```

And in the `.values()` dict (around line 395), add:

```python
composite_score=ci.composite_score,
```

**Step 2: Commit**

```bash
git add scripts/backfill.py
git commit -m "fix: add composite scoring to backfill pipeline"
```

---

### Task 9: Add Variant Collapse to Pipeline

**Files:**
- Modify: `src/pipeline/pipeline.py` — after event dedup, before composite scoring

**Step 1: Add variant collapse step**

After event deduplication (around line 365) and before composite scoring (line 368):

```python
from src.feed.variant_collapse import collapse_variants

# After event dedup:
classified = collapse_variants(classified)
logger.info("pipeline_variant_collapse", count=len(classified))
```

**Step 2: Run full test suite**

```bash
.venv/bin/python -m pytest tests/ -x --timeout=30
```

**Step 3: Commit**

```bash
git add src/pipeline/pipeline.py
git commit -m "feat: add variant collapse step to pipeline"
```
