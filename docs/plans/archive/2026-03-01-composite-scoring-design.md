# Composite Scoring System — Design Document

**Date:** 2026-03-01
**Status:** Approved
**Branch:** feat/feed-redesign

## Problem

The feed has no meaningful ranking differentiation:
- `relevance_score` clusters at 0.80-0.85 (LLM doesn't use the full range)
- `credibility_score` is flat at 0.65 for all items
- `dev_value_score` is always null
- `priority` is always 1 (engagement thresholds too low)
- Feed sorts by raw `score` (engagement), so GitHub repos with 240K lifetime stars dominate over genuinely trending items

## Solution

A composite score combining 4 signals: **engagement velocity**, **LLM relevance**, **recency**, and **topic weight**. Computed at pipeline time and stored in a new DB column.

Inspired by Twitter/X's ranking approach: engagement velocity (how fast something gains traction) matters more than raw cumulative engagement.

## Design

### 1. Data Capture — Fix Extractors

Some extractors discard the actual content creation date, which is needed for velocity.

| Extractor | `published_at` today | Change |
|-----------|---------------------|--------|
| **GitHub** | `pushed_at` (last commit) | Capture `created_at` from API into metadata |
| **HuggingFace models** | `lastModified` | Investigate and capture model creation date |
| **HN, Reddit, Arxiv, RSS, HF papers** | Already correct | None |

New field in `ExtractedItem`: `source_created_at: datetime | None` — the actual creation date on the source platform. GitHub extractor sets this from the repo's `created_at` field (already in API response, currently discarded).

### 2. Velocity Calculation

Velocity = engagement / age, normalized per source.

| Source | Score meaning | Age denominator | Velocity formula |
|--------|--------------|-----------------|------------------|
| **GitHub** | stars | days since repo creation | `stars / days_alive` |
| **HN** | points | hours since submission | `points / hours_alive` |
| **Reddit** | upvotes | hours since post creation | `score / hours_alive` |
| **HF models** | downloads (24h) | Already a velocity | `downloads` as-is |
| **HF papers** | upvotes | hours since publication | `upvotes / hours_alive` |
| **Arxiv** | none (0) | N/A | `null` — no velocity |
| **RSS** | none (0) | N/A | `null` — no velocity |

**Normalization to 0-1 with per-source saturation thresholds:**

```python
VELOCITY_THRESHOLDS = {
    "github": 500,           # 500+ stars/day = 1.0
    "hackernews": 200,       # 200+ points/hour = 1.0
    "reddit": 150,           # 150+ upvotes/hour = 1.0
    "huggingface": 100_000,  # 100K+ downloads/day = 1.0 (models)
    "huggingface_paper": 50, # 50+ upvotes/hour = 1.0
}

def normalize_velocity(velocity: float, source: str) -> float:
    threshold = VELOCITY_THRESHOLDS[source]
    return min(1.0, velocity / threshold)
```

### 3. Fix LLM Relevance Scoring

The current LLM prompt says "use the full range" but the model clusters at 0.80-0.85. Fix with few-shot anchoring and forced distribution.

**Improved prompt:**

```
RELEVANCE SCORING — you MUST use the full range. Each item gets ONE score.
Score by comparing against these real-world anchors:

1.0  = "OpenAI releases GPT-5 with 2x performance on all benchmarks"
0.95 = "Meta open-sources Llama 4 405B model weights"
0.90 = "Google DeepMind publishes new SOTA on protein folding"
0.85 = "New framework reaches #1 on GitHub trending with 10K stars in a day"
0.80 = "Incremental update to an existing popular tool"
0.75 = "Niche library or minor paper with limited audience"

FORCED DISTRIBUTION: In a batch of 10 items, you MUST NOT give more than
3 items the same score. Spread your scores across the range.
```

Key changes:
1. Concrete example anchors instead of abstract descriptions
2. Forced distribution constraint prevents clustering
3. Comparison-based framing

### 4. Composite Score Formula

```python
# When velocity is available (GitHub, HN, Reddit, HuggingFace)
composite = (
    0.35 * velocity_norm +      # engagement velocity (normalized 0-1)
    0.30 * relevance_norm +     # LLM relevance (0.75-1.0 mapped to 0-1)
    0.20 * recency_score +      # time decay (1.0 = just published, 0 = 48h+ old)
    0.15 * topic_weight         # content family weight (0-1)
)

# When velocity is NOT available (Arxiv, RSS)
composite = (
    0.45 * relevance_norm +     # relevance becomes primary signal
    0.30 * recency_score +      # recency matters more for curated sources
    0.25 * topic_weight         # topic weight fills the gap
)
```

**Relevance normalization** (map 0.75-1.0 to 0-1):
```python
relevance_norm = (relevance_score - 0.75) / 0.25
# 0.75 -> 0.0, 0.85 -> 0.4, 1.0 -> 1.0
```

**Recency score** (computed at pipeline time):
```python
age_hours = (now - published_at).total_seconds() / 3600
recency_score = max(0.0, 1.0 - (age_hours / 48))
# 0h -> 1.0, 12h -> 0.75, 24h -> 0.5, 48h+ -> 0.0
```

**Topic weights** (from feed redesign content families):
```python
TOPIC_WEIGHTS = {
    "models": 1.0,
    "products": 1.0,
    "regulation": 1.0,
    "agents": 0.95,
    "tools": 0.85,
    "open_source": 0.85,
    "papers": 0.70,
}
```

**Example differentiation with real data:**

| Item | velocity_norm | relevance_norm | recency | topic_w | **composite** |
|------|--------------|----------------|---------|---------|--------------|
| sim (26K stars, agents) | 0.9 | 0.40 | 0.97 | 0.95 | **0.70** |
| zeroclaw (21K stars, tools) | 0.8 | 0.40 | 0.98 | 0.85 | **0.65** |
| langgraph (25K stars, agents) | 0.85 | 0.20 | 0.93 | 0.95 | **0.64** |
| openclaw (240K stars, products) | 0.26 | 0.20 | 0.96 | 1.0 | **0.40** |
| LMCache (7K stars, tools) | 0.3 | 0.20 | 0.95 | 0.85 | **0.39** |

openclaw (240K lifetime stars, low velocity) now ranks **below** sim and zeroclaw (high velocity).

### 5. Storage & Query Changes

**New DB column:**
```python
composite_score: Mapped[float | None]  # 0.0-1.0, computed at pipeline time
```

New Alembic migration with index for sorting performance.

**Pipeline integration** — new step after classification:
```
extract -> dedup -> classify -> COMPUTE_COMPOSITE -> validate -> embed -> store -> notify
```

New `CompositeScorer` component computes the score using velocity + relevance + recency + topic weight.

**Query changes in items endpoint:**
```python
# /api/items/latest with sort=relevance (default)
ORDER BY composite_score DESC NULLS LAST, effective_date DESC

# /api/items/latest with sort=recent
ORDER BY effective_date DESC
```

**Backfill:** Existing items get `composite_score = null`, sort after new items via `NULLS LAST`.

**Configuration via env vars:**
```
COMPOSITE_W_VELOCITY=0.35
COMPOSITE_W_RELEVANCE=0.30
COMPOSITE_W_RECENCY=0.20
COMPOSITE_W_TOPIC=0.15
VELOCITY_THRESHOLD_GITHUB=500
VELOCITY_THRESHOLD_HACKERNEWS=200
VELOCITY_THRESHOLD_REDDIT=150
VELOCITY_THRESHOLD_HUGGINGFACE=100000
VELOCITY_THRESHOLD_HUGGINGFACE_PAPER=50
```

## Components Affected

1. `src/extractors/github.py` — capture `created_at`
2. `src/extractors/huggingface.py` — capture model creation date
3. `src/classifiers/llm.py` — improved prompt with anchors
4. New: `src/pipeline/composite_scorer.py` — velocity + composite calculation
5. `src/pipeline/pipeline.py` — integrate CompositeScorer step
6. `src/core/models.py` — add `composite_score` column
7. `src/core/config.py` — add weight/threshold settings
8. `src/api/routes/items.py` — sort by `composite_score`
9. New Alembic migration
10. Tests for all changes
