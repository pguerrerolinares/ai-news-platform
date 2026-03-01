# Feed Algorithm Redesign — Design Document

**Date**: 2026-03-01
**Status**: Approved

## Problem

The current `/items/latest` feed has several quality issues:

1. **Manual diversity**: Hard `max_per_source` cap is fragile — some days 5 per source is too many, other days too few
2. **Duplicate model variants**: HuggingFace items include GGUF/GPTQ re-uploads alongside originals (e.g., `Qwen/Qwen3.5-27B` + `unsloth/Qwen3.5-27B-GGUF`), inflating the feed with redundant items
3. **Fixed velocity thresholds**: 100K downloads for HF, 200 points for HN — these don't adapt to daily volume variations
4. **Null composite scores**: Items from backfill script have no composite_score, making relevance ranking meaningless for ~60% of items

## Solution

Replace the simple `ORDER BY composite_score` with a multi-step feed construction pipeline:

```
Candidate Pool → Score → Collapse Variants → Diversify (MMR) → Paginate
```

## Components

### 1. Variant Collapse (pipeline step)

Detect and merge HuggingFace model variants during pipeline processing.

**Logic:**
- Normalize model name: strip suffixes (`-GGUF`, `-GPTQ`, `-AWQ`, `-ONNX`, `-EXL2`)
- Strip known quantization publishers: `unsloth/`, `TheBloke/`, `bartowski/`
- Group items by normalized base model name
- Keep only the item with highest score (typically the original)
- Mark collapsed items with a reference to the kept item (for traceability)

**Location:** New pipeline step between classification and composite scoring.

**Impact:** ~50% reduction in HuggingFace noise.

### 2. Percentile-Based Velocity Normalization (composite_scorer change)

Replace fixed thresholds with dynamic percentile-based normalization.

**Current (fixed):**
```python
velocity_norm = min(1.0, velocity / 100_000)  # HF threshold
```

**Proposed (percentile):**
```python
velocity_norm = percentile_rank(velocity, source="huggingface")
# Uses p95 from last 7 days as dynamic reference
```

**How it works:**
- Periodically compute velocity percentiles per source from recent data (last 7 days)
- Store as simple config/cache: `{source: {p50: X, p75: Y, p90: Z, p95: W}}`
- Normalize velocity against source's own distribution
- An item at p90 of HN = same normalized value as p90 of HF = fair cross-source comparison

**Fallback:** If not enough data for percentiles (new source, cold start), use current fixed thresholds.

### 3. MMR Diversification (replaces max_per_source)

Maximal Marginal Relevance — industry standard for diverse feed ranking.

**Algorithm:**
```python
selected = []
candidates = fetch_top_N_by_composite_score(limit * 5)

for _ in range(limit):
    best = argmax over candidates:
        lambda_ * composite_score(item)
        - (1 - lambda_) * max_similarity(item, selected)
    selected.append(best)
    candidates.remove(best)
```

**Similarity function:**
```python
def similarity(item_a, item_b) -> float:
    score = 0.0
    if item_a.source == item_b.source: score += 0.3
    if item_a.topic == item_b.topic: score += 0.3
    if item_a.author == item_b.author: score += 0.2
    score += title_similarity(item_a.title, item_b.title) * 0.2
    return score
```

**Parameters:**
- `lambda_`: 0.7 (favor quality over diversity). Configurable via settings.
- Title similarity: Jaccard on word tokens (already used in credibility validator).
- Candidate pool: `limit * 5` items (e.g., 100 candidates for 20 results).

**Key property:** No hard caps. If HN genuinely has 10 great items, they appear. But mediocre HN items are penalized if the feed already has several HN items.

### 4. Re-score Existing Items

One-time script to compute composite_score for all items where it's NULL.

**Logic:**
- Query `WHERE composite_score IS NULL`
- For each item, compute velocity from source + score + timestamps
- Apply composite formula
- Batch UPDATE in DB

**Cost:** Zero external API calls. Pure math on existing data.

### 5. Fix Backfill Script

Add `CompositeScorer.score_batch()` call to `scripts/backfill.py` after classification, so future backfill runs produce complete items.

## Architecture

### New files

```
src/feed/
  __init__.py
  feed_builder.py      # FeedBuilder: orchestrates candidate -> score -> collapse -> MMR -> paginate
  variant_collapse.py   # CollapseVariants: normalize model names, group, keep best
  mmr_ranker.py         # MMRRanker: greedy MMR diversification
```

### Modified files

```
src/pipeline/composite_scorer.py   # Percentile-based velocity normalization
src/pipeline/pipeline.py           # Add variant collapse step
src/api/routes/items.py            # /items/latest uses FeedBuilder
src/core/config.py                 # New settings (mmr_lambda, percentile window)
scripts/backfill.py                # Add CompositeScorer call
```

### New script

```
scripts/rescore_composite.py       # One-time re-scoring of null composite_scores
```

## API Changes

### `GET /api/items/latest`

- **Remove**: `max_per_source` parameter (replaced by MMR)
- **Add**: `diversity: float = Query(0.7, ge=0.0, le=1.0)` — controls MMR lambda (0.0 = pure score, 1.0 = max diversity). Optional, default 0.7.
- Behavior: When `sort=relevance`, uses FeedBuilder. When `sort=recent`, chronological (unchanged).

## Config Settings

```python
# MMR
feed_mmr_lambda: float = 0.7           # Quality vs diversity tradeoff
feed_candidate_multiplier: int = 5     # Candidate pool = limit * multiplier

# Percentile velocity
velocity_percentile_window_days: int = 7  # Look-back for percentile computation
velocity_percentile_target: float = 0.95  # Normalize against this percentile
```

## What Does NOT Change

- Database schema (no migrations)
- Other endpoints (`/items/top`, `/trending`, `/by-date`, `/today`)
- Extractors (HN, Reddit, GitHub, HF, arXiv, RSS)
- LLM classifier
- Credibility validator
- Embeddings / RAG / chat
- Frontend (except removing `max_per_source` param)
