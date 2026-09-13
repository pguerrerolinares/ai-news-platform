# Pipeline Quality Fix: GitHub + HuggingFace

**Date**: 2026-03-04
**Status**: Approved

## Problem

Two data quality issues in the pipeline:

1. **GitHub extractor returns 0 items always** — `pushed:>` (strictly greater) with today's date matches nothing because GitHub interprets it as "after end of day"
2. **HuggingFace injects model repo pages as news** — 59 model page URLs in DB (24 Qwen3.5 variants alone). Re-uploads, quantizations, and format conversions stored as "news"

## Root Causes

### GitHub
- `src/extractors/github.py:86`: `pushed:>{since_date}` should be `pushed:>={since_date}`

### HuggingFace
- Extractor treats all 50 trending models as news with `title=text=modelId` (no real content)
- No distinction between original model releases and re-uploads/quantizations
- Classifier LLM prompt accepts "model launches" — every trending model qualifies
- Variant collapse only works within a single pipeline run and misses many suffixes

## Design

### Fix 1: GitHub `pushed:>=` (one character)

Change `pushed:>` to `pushed:>=` in `github.py:86`.

### Fix 2: HuggingFace tag-based filtering

Use HuggingFace API metadata to filter deterministically — no blocklists needed.

The HF API provides tags like `base_model:quantized:Qwen/Qwen3.5-35B-A3B` on re-uploads. This is the definitive signal.

**Filter rules in `huggingface.py`** (applied during extraction):

1. **Skip quantizations**: If tags contain any `base_model:quantized:*` tag → skip
2. **Skip re-uploads without library**: If `library_name is None` → skip (quantized wrappers have null library)
3. **Filter by `createdAt`**: Only models created within `since_hours`. Trending old models are not new launches.
4. **Improve `text` field**: Use `pipeline_tag` + description tags instead of repeating `modelId`

### Fix 3: Expand variant collapse (safety net)

In `src/feed/variant_collapse.py`:

- Add suffixes: `-FP8`, `-FP16`, `-NVFP4`, `-abliterated`, `-censored`
- Normalize parameter size in `normalize_model_name`: strip `-0.8B`, `-27B`, `-397B-A17B`, etc.

### Fix 4: Clean existing data

```sql
-- Verify scope first
SELECT COUNT(*) FROM news_items
WHERE source = 'huggingface'
  AND url LIKE 'https://huggingface.co/%'
  AND url NOT LIKE '%arxiv%';

-- Delete embeddings first (FK)
DELETE FROM item_embeddings WHERE item_id IN (
  SELECT id FROM news_items
  WHERE source = 'huggingface'
    AND url LIKE 'https://huggingface.co/%'
    AND url NOT LIKE '%arxiv%'
);

-- Delete items
DELETE FROM news_items
WHERE source = 'huggingface'
  AND url LIKE 'https://huggingface.co/%'
  AND url NOT LIKE '%arxiv%';
```

## Trade-offs

- **`base_model:quantized` tag**: Relies on HF metadata being correct. If an original model mistakenly has this tag, it gets filtered. Risk is low — HF auto-generates these tags.
- **`library_name is None` filter**: Some legitimate models might not specify a library. Mitigated by the `createdAt` filter being the primary gate.
- **`createdAt` filter**: A model could be created months ago but only become newsworthy now (e.g., goes viral). Acceptable trade-off — daily papers cover these cases.

## Files Changed

- `src/extractors/github.py` — one-char fix
- `src/extractors/huggingface.py` — tag-based filtering logic
- `src/feed/variant_collapse.py` — expanded suffixes + size normalization
- `tests/unit/extractors/test_huggingface.py` — new filter tests
- `tests/unit/feed/test_variant_collapse.py` — expanded tests
- Production DB — DELETE stale model page entries
