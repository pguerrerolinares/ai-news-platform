# Production Quality Fixes — Design Spec

> Audit date: 2026-03-16 | DB: 7,011 items since 2026-02-28

## Context

Production audit revealed three data quality issues affecting feed quality:
194 duplicate items by URL, GitHub repos dominating 64% of the feed, and
LLM classifier losing precision during OpenAI rate limits.

---

## Fix 1: Persistent URL Deduplication

### Problem

`content_hash = SHA256(title|url)` has a unique constraint and powers `ON CONFLICT DO NOTHING`.
But the same URL with a slightly different title (e.g., GitHub repo description changes between
runs, or same repo appears via HN with user-edited title vs GitHub API title) produces a
different `content_hash`, bypassing the constraint.

`url_hash = SHA256(url)` is computed and stored but has **no unique constraint**.

**Production impact**: 179 URL groups with 194 extra items. Breakdown:
- 144 cross-source (github ↔ hackernews): same repo URL, different titles
- 23 intra-GitHub: same repo re-extracted with description changes
- 40 intra-HackerNews: same URL reposted with different HN titles
- 5 intra-RSS: feeds republishing

### Design

1. **Alembic migration**: Add named partial unique index
   `uix_news_items_url_hash ON news_items (url_hash) WHERE url_hash IS NOT NULL`.
   Items without URLs (rare) keep using `content_hash` only.

2. **Clean existing duplicates**: Migration runs cleanup BEFORE creating the index:
   - For each group of items sharing the same `url_hash`, keep the one with highest
     `composite_score` (or most recent `created_at` as tiebreaker)
   - Delete the rest
   - **Side effect**: cascade-deletes associated `item_embeddings` rows (FK with
     `ondelete="CASCADE"`). The surviving items will get re-embedded on the next
     pipeline run. Cost: ~194 embedding API calls (< $0.01).

3. **Update store stage**: Split insert logic by URL presence:
   - **Items WITH a URL**: `INSERT ... ON CONFLICT (url_hash) WHERE url_hash IS NOT NULL
     DO UPDATE SET composite_score = GREATEST(excluded.composite_score, news_items.composite_score),
     score = GREATEST(excluded.score, news_items.score),
     relevance_score = GREATEST(excluded.relevance_score, news_items.relevance_score)`
     — upsert-on-better-score semantics. In SQLAlchemy, reference the named index via
     `on_conflict_do_update(index_elements=["url_hash"],
     index_where=text("url_hash IS NOT NULL"), set_={...})`.
   - **Title/summary are NOT updated** on upsert — intentional. The first-ingested version
     preserves the original title. Cross-source title differences (HN user title vs GitHub
     API description) are a feature, not a bug — the stored title reflects the source that
     found it first. Score updates are what matter for ranking.
   - **Items WITHOUT a URL** (`url_hash IS NULL`): keep current
     `on_conflict_do_nothing(index_elements=["content_hash"])`.
   - The `content_hash` unique constraint remains as a secondary safety net for all items.

### Files Changed

- `alembic/versions/XXX_add_url_hash_unique.py` — new migration (cleanup + partial unique index)
- `src/pipeline/stages/store.py` — split insert by URL presence, upsert logic

### Risks

- Migration must delete duplicates BEFORE adding unique constraint, or it fails
- Partial unique index requires named reference in SQLAlchemy `ON CONFLICT` clause
- CASCADE deletion of embeddings is acceptable (auto-regenerated, negligible cost)

---

## Fix 2: GitHub Feed Flooding

### Problem

GitHub extractor produces 4,462 / 7,011 items (64%). Causes:
- `github_min_stars = 50` captures thousands of mature repos
- No persistent tracking: same repos (spaCy 33k★, frigate 30k★) reappear every hour
- Broad queries ("AI", "LLM", "machine-learning", "generative-AI") match too many repos
- No "novelty" filter: old repos with any recent push appear alongside genuinely new projects

### Design

Three incremental changes:

**2a) Raise minimum stars threshold**
- Change `github_min_stars` default from 50 to 500 in `config.py`
- Override in production env: `GITHUB_MIN_STARS=500`

**2b) Persistent "already seen" filter using database**
- Add a new pipeline stage `filter_already_seen(session, items)` AFTER in-memory dedup
  in `pipeline.py`. This keeps the extract stage session-free, receives a deduplicated
  item list (smaller IN clause), and preserves existing `items_after_dedup` briefing stats.
- Compute `url_hash` for each extracted item, then query:
  `SELECT url_hash FROM news_items WHERE url_hash IN (:hashes)
  AND created_at >= NOW() - make_interval(days => :window)`
  where `:window` is `seen_window_days` from config. Leverages `idx_news_items_url_hash`.
- Filter out items whose `url_hash` already exists in the database.
- Configurable window via `seen_window_days: int = 7` in config.
- Applies to ALL sources (not just GitHub), also reducing HF/RSS re-ingestion.

**2c) Repo creation date filter**
- Add `github_max_repo_age_days: int = 90` to config
- In GitHub extractor `_search()` method, filter inside the `for repo in data.get("items", [])`
  loop, right after parsing `created_at_dt` (line ~110-117).
- If `created_at_dt` is older than N days → skip repo.
- If `created_at_dt` is `None` (unparseable) → **include** the repo (fail open — don't
  silently drop repos because of a missing API field).
- Repos older than 90 days can still appear if posted on HackerNews (different source,
  curated by community engagement).

### Files Changed

- `src/core/config.py` — new defaults: `github_min_stars=500`, `github_max_repo_age_days=90`,
  `seen_window_days=7`
- `src/extractors/github.py` — repo age filter in `_search()`
- `src/pipeline/pipeline.py` — call `filter_already_seen()` between extract and dedup
- `src/pipeline/stages/extract.py` — new `filter_already_seen(session, items)` function

### Risks

- Repo age filter might exclude genuinely interesting old repos that suddenly go viral.
  Mitigation: HN still captures these via community curation.
- DB query adds one query per pipeline run. With ~100 url_hashes per batch against an
  indexed column, this is trivial (~1ms).

---

## Fix 3: LLM Retry Backoff

### Problem

OpenAI 429 rate limits exhaust 3 retries in 7 seconds (1s + 2s + 4s). Items fall back
to `KeywordClassifier` (no data loss), but lose LLM summary and precise classification.

Production logs show clusters of 429s around 04:00 UTC (arXiv daily + tier2 overlap).

### Design

- Change `MAX_RETRIES` from 3 to 5
- Change `RETRY_BACKOFF` from `[1, 2, 4]` to `[2, 5, 15, 30]`
- The retry loop does `for attempt in range(MAX_RETRIES)` with waits on attempts 0-3
  (4 waits between 5 attempts). Total max wait: 2 + 5 + 15 + 30 = **52s base**, ~68s with jitter.
- Add jitter: `wait + random.uniform(0, wait * 0.3)` to avoid thundering herd

### Files Changed

- `src/classifiers/llm.py` — retry constants, backoff array, jitter

### Risks

- Longer waits extend pipeline duration. Worst case: 52s × N failed batches.
  Acceptable since pipeline already takes 90-120s and runs on a cron, not user-facing.

---

## Out of Scope

- **WebScraper extractor**: deferred to backlog (needs browserless integration or new URLs)
- **Reddit extractor**: user decision to not include for now
- **Semantic dedup** (pgvector cosine similarity): nice-to-have, much higher complexity
- **GitHub query refinement**: current 4 queries are fine, the filtering fixes address the noise

## Testing Strategy

- **Fix 1**: Unit test for upsert-on-better-score logic (items with/without URL).
  Migration test: verify duplicates cleaned and index created on test DB.
- **Fix 2**: Unit test for repo age filter (old repo, new repo, None created_at).
  Unit test for `filter_already_seen` with mocked session.
- **Fix 3**: Unit test for jitter calculation bounds. Mock test for retry exhaustion
  verifying fallback to KeywordClassifier.

## Rollback

All fixes are independently deployable and reversible:
- Fix 1: Drop the unique index (migration downgrade), revert store.py
- Fix 2: Revert config values, remove age filter, remove `filter_already_seen` call
- Fix 3: Revert retry constants
