# Efficiency & Optimization Findings — 2026-06-10

Scope: read-only analysis of the full `src/` tree. Every claim is cited with
file:line. Impact estimates are reasoned from code; anything requiring
production data to confirm is flagged explicitly.

---

## Implementation status — 2026-06-11 (sprint)

Verified the speculative findings against the local dev DB (5718 items) before
touching anything, then actioned the rest via parent-orchestrator + Sonnet
children (commits `f98d4f0`..`6e6945e`, local only — not pushed).

| Finding | Outcome |
|---------|---------|
| F-1 | ✅ Done — title-similarity loop moved off the event loop (`asyncio.to_thread`). |
| F-4 | ✅ Done — `NOT IN` → `outerjoin + IS NULL + LIMIT 500`. (Note: at 5718 rows the old query ran in 3ms; value is bounded RAM at scale, not speed now.) |
| F-5 | ✅ Done — 6 sequential COUNTs → one `case()` aggregate. |
| F-8 | ✅ Done — LLM batches now concurrent, bounded by `Semaphore(3)`; order + fallback preserved. |
| F-11 | ✅ Done — `Retriever` reused as a module singleton in `/api/search`. |
| F-12 | ✅ Done — `CompositeScorer` constructed once in `FeedBuilder.__init__`. |
| F-16 | ✅ Done — **the doc's NULL guess was wrong**: `search_vector` was 5718/5718 populated by trigger `trg_news_items_search`, but using `to_tsvector('english', title+summary)` while `search.py` ran `to_tsvector('simple', title+full_text+source)` at query time — the GIN index was dead weight nothing read. Migration 017 realigns the trigger to `'simple', title+full_text+source` + backfills; `search.py` now matches/ranks against the column (Bitmap Index Scan confirmed). Config stays `'simple'` (no semantic change). |
| F-17 | ✅ Done — `AsyncOpenAI` client cached on the classifier. |
| F-3 | ✅ Removed entirely (owner decision) — per-item HEAD request + `+0.1` URL bonus deleted; shared SSRF helper untouched. |
| F-6 | ❌ Dismissed — `EXPLAIN ANALYZE` on the topic+effective_date query already uses `idx_news_items_effective_date` in **0.05ms**. Composite indexes would be over-engineering at this scale. |
| F-2, F-13 | Deferred — need production duplicate-counts / pool-wait data to justify. |
| F-7, F-10 | Noted only (HNSW tuning low-priority at scale; F-10 is a documented behavior, no code change). |
| F-9, F-14, F-15 | Already optimal — see "NOT Worth It" section. |

Follow-up (separate, data-driven): F-16 leaves search on `'simple'` (no stemming);
switching to `'english'` stemming over the same columns is a search-QUALITY change to
A/B with real queries, deliberately kept out of this sprint.

---

## Bottom-Line Summary — Top 5 Opportunities

| # | Finding | Impact | Effort | Confidence |
|---|---------|--------|--------|------------|
| 1 | **Seen-filter title similarity is O(N×M) Python loop** — up to ~100 candidates × 2000 DB titles = 200 000 `rapidfuzz` calls per pipeline run, synchronously blocking the async loop | High — pipeline latency | S | High (code-verified) |
| 2 | **`embed_new_items` uses a NOT IN subquery** that scans the full `news_items` table, and all un-embedded items are loaded into Python memory in one shot | Med — DB load + RAM | S | High (code-verified) |
| 3 | **`stats_score_distribution` fires 6 sequential DB queries** for a single endpoint hit (one per score bucket) | Med — DB round-trips | S | High (code-verified) |
| 4 | **`Retriever()` and `CompositeScorer()` are reconstructed on every request/pipeline-step** — cheap but reads `get_settings()` (LRU-cached) and allocates objects unnecessarily | Low–Med — CPU/RAM at scale | S | High (code-verified) |
| 5 | **Credibility validator fires HEAD HTTP requests per item** (up to `_SEMAPHORE_LIMIT=5` concurrent), adding real network latency to every pipeline run | Med — pipeline latency | S | High (code-verified) |

---

## Dimension 1 — Pipeline Efficiency

### F-1: O(N×M) title-similarity loop in seen_filter blocks the async loop

**File:line:** `src/pipeline/stages/seen_filter.py:83–92`

**What's inefficient:**
The filter fetches up to 2000 recent titles from DB (line 77), then for each
incoming candidate runs `any(title_similarity(item_title, rt) >= 0.80 for rt in
recent_titles)`. `title_similarity` itself has a cheap pre-filter (line 13–17 of
`text_utils.py`), but worst-case this is 100 candidates × 2000 stored titles =
200 000 `rapidfuzz` calls executed **synchronously in the async event loop**
(there is no `asyncio.to_thread` or similar). This stalls all other coroutines
for the duration.

The comment in the code acknowledges the O(N×M) concern and the 2000-title cap
is already a mitigation, but the inner loop remains pure-Python CPU work on the
event loop.

**Estimated impact:** High on pipeline latency. At 100 candidates and 2000
stored titles with the early-exit `any()`, average case is better, but bursts
(HN poll with many new items, week-old `seen_window_days=7`) can still mean
tens of thousands of calls. Blocks the event loop, meaning API requests queue
up during pipeline runs.

**Effort:** S  
**Risk:** Low — pure logic change, easy to revert  
**Fix:** Wrap the inner loop in `asyncio.to_thread`:
```python
def _title_filter_sync(candidates, recent_titles, threshold):
    ...  # existing loop
    return after_title

after_title = await asyncio.to_thread(_title_filter_sync, candidates, recent_titles, THRESHOLD)
```
This moves 100% of CPU work off the event loop with zero logic change.
Alternative: use PostgreSQL trigram similarity (`pg_trgm`) to push the fuzzy
match into the DB entirely — but that's a larger change and requires the
`pg_trgm` extension.

**Needs production data:** Query `EXPLAIN ANALYZE` on the title fetch query to
confirm the 2000 row limit is the real bottleneck vs. the Python loop itself.
Prometheus pipeline duration histogram would show if this stage is a meaningful
fraction of total pipeline time.

---

### F-2: Seen-filter also double-counts work with event_dedup

**File:line:** `src/pipeline/stages/seen_filter.py` (title pass) vs
`src/classifiers/event_dedup.py:52–62`

**What's inefficient:**
There are now three separate fuzzy-title-similarity passes in the pipeline:
1. `seen_filter` pass 2 — title similarity vs. DB (cross-run dedup)
2. `credibility._is_duplicate_or_similar` — Jaccard on title+text within-batch
3. `event_dedup._group_by_similarity` — union-find within-batch per topic

Passes 2 and 3 both operate on the same within-batch set, meaning any item that
survives pass 2 is re-compared in pass 3. They use different metrics (Jaccard
vs. rapidfuzz ratio) so they can't be trivially merged, but the overlap means
some work is genuinely redundant.

**Estimated impact:** Low on its own (passes 2 and 3 operate on the much
smaller post-classification set, typically <50 items). Noted for completeness.

**Effort:** M (requires careful re-evaluation of what each pass does)  
**Risk:** Med — dedup logic is correctness-sensitive  
**Recommendation:** Defer until production data confirms duplicate counts from
each pass.

---

### F-3: `CredibilityValidator` fires HEAD HTTP requests per item in the pipeline

**File:line:** `src/validators/credibility.py:303–319`, `367–384`

**What's inefficient:**
Every classified item with a URL goes through `_verify_url_content` which does
a live `httpx.HEAD` request (timeout 5s, semaphore 5, no redirect follow). On
a batch of 30 items with URLs this is up to 30 network round-trips adding up
to `30/5 * 5s = 30s` worst-case latency to pipeline runs (if all URLs time
out). The value returned is a flat +0.1 bonus — a binary accessible/not signal.

The `_is_safe_url` SSRF check (line 414) is async and adds a DNS lookup per
item before the HEAD.

**Estimated impact:** Med pipeline latency, especially for slow external hosts
(webscraper URLs, arxiv). At best adds 2–5 seconds on a healthy run; at worst
30+ seconds if URLs are unreachable.

**Effort:** S  
**Risk:** Low  
**Fix options (pick one, ordered by pragmatism):**
- a) Remove URL verification entirely — the +0.1 bonus is marginal vs. the
  source/domain/engagement scores that already do the heavy lifting.
- b) Make URL verification opt-in via a config flag
  (`enable_url_verification: bool = False`).
- c) Cap concurrency at 3 and use a shorter timeout (1.5s) — already SSRF-safe.

---

## Dimension 2 — Database

### F-4: `embed_new_items` uses `NOT IN` subquery — full table scan risk + full result load

**File:line:** `src/pipeline/stages/store.py:151–154`

```python
subquery = select(ItemEmbedding.item_id).where(ItemEmbedding.model == model_name)
stmt = select(NewsItem).where(~NewsItem.id.in_(subquery))
result = await session.execute(stmt)
items = list(result.scalars().all())
```

**What's inefficient:**
1. `NOT IN (subquery)` over all `news_items` is a full scan of `news_items`
   (the planner can't use the PK index efficiently with NOT IN on large sets).
   A `LEFT JOIN ... WHERE item_embeddings.item_id IS NULL` or `NOT EXISTS`
   subquery is generally faster and handles NULLs correctly.
2. All un-embedded items are loaded into Python memory in one call. Early in the
   project this is fine; at 10 000+ items (90-day retention) this could be
   several MB of ORM objects before `embed_batch` is called.

**Estimated impact:** Med DB load (grows with table size), Low RAM at current
scale but degrades over time. The embedding batch is already chunked at 100
(line 57 of `embeddings.py`) but the SELECT loads everything first.

**Effort:** S  
**Risk:** Low — pure SQL rewrite, same semantics  
**Fix:**
```python
stmt = (
    select(NewsItem)
    .outerjoin(
        ItemEmbedding,
        (NewsItem.id == ItemEmbedding.item_id) & (ItemEmbedding.model == model_name),
    )
    .where(ItemEmbedding.item_id.is_(None))
    .limit(500)  # process in chunks across pipeline runs
)
```
Adding a `.limit(500)` means embeddings catch up incrementally; the seen-filter
already prevents re-processing stored items so there's no correctness risk.

**Needs production data:** `EXPLAIN ANALYZE` on the `NOT IN` query to confirm
seq scan vs. index scan. At <5000 rows the planner may choose well anyway.

---

### F-5: `stats_score_distribution` fires 6 sequential round-trips

**File:line:** `src/api/routes/stats.py:293–313`

**What's inefficient:**
The `for label, min_score, max_score in _SCORE_BUCKETS` loop sends 6 separate
`COUNT` queries to Postgres, sequentially (`await` inside the loop). This is a
classic N-query anti-pattern — a single `CASE WHEN` aggregation does the same
work in one round-trip.

**Estimated impact:** Med — 6× DB round-trip overhead on every
`/api/stats/score-distribution` call. On a VPS with local Postgres this is ~5ms
per round-trip × 6 = ~30ms of pure latency overhead vs. <5ms for a single
aggregate query. Wasted connection time from the small pool (size=5).

**Effort:** S (straightforward SQL rewrite)  
**Risk:** Low  
**Fix:**
```python
result = await session.execute(
    select(
        func.count(case((NewsItem.score.between(0, 10), NewsItem.id))).label("b0"),
        func.count(case((NewsItem.score.between(11, 50), NewsItem.id))).label("b1"),
        ...
    ).where(effective_date >= since_dt)
)
```

---

### F-6: `effective_date` computed column used in ORDER BY — index coverage uncertain

**File:line:** `src/core/queries.py:9`, used in `items.py`, `stats.py`, etc.

`effective_date = func.coalesce(NewsItem.published_at, NewsItem.created_at)`

**What's inefficient:**
This expression is used extensively in `WHERE` and `ORDER BY` clauses. There is
a functional index `idx_news_items_effective_date` on the same coalesce
expression (models.py line 110–113), which should be used by the planner for
range filters. However:
- The index sorts `.desc()` — queries that filter by `>= cutoff` and then sort
  `DESC` should hit it, but queries that add additional `WHERE` clauses on
  `topic` or `source` may do an index scan + filter rather than an index-only
  scan.
- The `idx_news_items_topic_date` and `idx_news_items_source_date` composite
  indexes use the raw `published_at` column, not the coalesce expression (lines
  105–106). These indexes are therefore useless for queries that filter on
  `effective_date >= cutoff AND topic = ?` — the planner must choose between the
  topic-date index (wrong expression) or the effective_date index (right
  expression, no topic column).

**Estimated impact:** Speculative — depends on query plans. Could cause full or
partial table scans on topic-filtered date queries at scale.

**Effort:** S–M (add composite functional indexes)  
**Risk:** Low (additive change)  
**Fix:** Add composite functional indexes:
```sql
CREATE INDEX idx_news_items_topic_eff_date ON news_items
    (topic, (COALESCE(published_at, created_at)) DESC);
CREATE INDEX idx_news_items_source_eff_date ON news_items
    (source, (COALESCE(published_at, created_at)) DESC);
```
**Needs production data:** `EXPLAIN (ANALYZE, BUFFERS)` on `GET /api/items?topic=models`
and `GET /api/items/trending` to confirm whether index is used.

---

### F-7: HNSW index has no `ef_construction`/`m` tuning parameters set

**File:line:** `src/core/models.py:181–188`

```python
Index(
    "idx_embeddings_hnsw",
    "embedding",
    postgresql_using="hnsw",
    postgresql_ops={"embedding": "vector_cosine_ops"},
),
```

**What's inefficient:**
No `m` or `ef_construction` parameters are set, so pgvector defaults apply
(`m=16, ef_construction=64`). These defaults are reasonable for small datasets
but sub-optimal for recall at scale. More critically, `ef_search` (query-time
parameter) is never set in the retriever — it defaults to 40, which may trade
recall for speed unnecessarily.

This is low priority on a 4GB VPS with a small dataset but worth knowing.

**Estimated impact:** Low at current scale. If the embedding table grows to
50k+ rows, recall quality may degrade without tuning.

**Effort:** S  
**Risk:** Low  
**Fix:** Set `SET hnsw.ef_search = 100` per connection in the retriever, or as
a session-level default if recall is important.

---

## Dimension 3 — Embeddings & LLM Cost

### F-8: LLM batches are processed sequentially, not concurrently

**File:line:** `src/classifiers/llm.py:235–251`

```python
for batch_start in range(0, len(items), BATCH_SIZE):
    batch = items[batch_start : batch_start + BATCH_SIZE]
    batch_results = await self._classify_batch(...)
```

**What's inefficient:**
Batches of 10 are sent to Kimi/Moonshot one at a time. If there are 50
ambiguous items (5 batches), each ~2s LLM call adds up to ~10s sequentially.
Since each batch is fully independent, they could run concurrently with a
semaphore to respect rate limits.

**Estimated impact:** Med — pipeline latency proportional to number of LLM
batches. With the two-phase classifier, only the "ambiguous" (1–2 keyword
matches) items reach LLM, so the real batch count is lower than it looks.
But on a busy run with many ambiguous items this is the single biggest pipeline
latency item after URL verification.

**Effort:** S  
**Risk:** Low–Med — concurrent batches increase rate-limit risk; a semaphore of
2–3 concurrent batches is the conservative fix.  
**Fix:**
```python
sem = asyncio.Semaphore(3)
async def _bounded_batch(start):
    async with sem:
        return await self._classify_batch(...)
results = await asyncio.gather(*[_bounded_batch(s) for s in range(0, len(items), BATCH_SIZE)])
```

---

### F-9: Keyword classifier re-compiles regex patterns on every call

**File:line:** `src/classifiers/keyword.py:228–238`

```python
for keyword in keywords:
    pattern = r"\b" + re.escape(keyword.lower()) + r"\b"
    if re.search(pattern, text):  # compiled implicitly, cached by re module
```

**What's inefficient:**
Python's `re` module has an internal LRU cache (default 512 entries) for
compiled patterns, so this is less bad than it looks. However, with 7 topics ×
~20 keywords = ~140 patterns, called once per item, the LRU cache should absorb
the cost after the first pass. This is **not worth fixing** — Python's `re`
cache handles it adequately.

**Verdict:** Already effectively cached via `re` module internals. Not a real
issue.

---

### F-10: `embed_new_items` re-embeds items on model name change

**File:line:** `src/pipeline/stages/store.py:150–153`

When `embedding_model` is changed in config, the `NOT IN` subquery filters by
`model == model_name`, so all existing items (embedded under the old model name)
appear as "not embedded" and get re-embedded. This is correct behavior but could
be expensive ($) if accidentally triggered.

**Estimated impact:** Low probability, high one-time $ cost if it happens.  
**Fix:** Document the behavior explicitly in config.py near `embedding_model`.
No code change needed.

---

## Dimension 4 — Memory Footprint

### F-11: `Retriever()` constructed per HTTP request for semantic search

**File:line:** `src/api/routes/search.py:114`

```python
retriever = Retriever()
items = await retriever.retrieve(session, q, limit=limit)
```

And `Retriever.__init__` always constructs a new `EmbeddingService()` which
constructs a new `openai.AsyncOpenAI()` client (line 27 of `embeddings.py`).
The `openai.AsyncOpenAI` client creates an internal `httpx.AsyncClient` with
connection pool. This means every semantic search request allocates a new HTTP
client and its connection pool, which is then discarded.

The `ChatService` in `chat.py` does it correctly — it takes an optional injected
client — but the default path in the search route always creates fresh.

**Estimated impact:** Med — connection pool thrash. Each discarded
`httpx.AsyncClient` wastes connection establishment overhead (TLS handshake to
OpenAI) and slightly inflates memory during the request. On a 4GB VPS with
concurrent users this adds up.

**Effort:** S  
**Risk:** Low  
**Fix:** Create a module-level `_retriever_singleton: Retriever | None = None`
in `search.py` and reuse it, or inject via FastAPI dependency.

---

### F-12: `CompositeScorer()` constructed per feed request

**File:line:** `src/feed/feed_builder.py:62`

```python
scorer = CompositeScorer()
for item in all_candidates:
    item.composite_score = scorer.score_newsitem(item, now=now)
```

`CompositeScorer.__init__` calls `get_settings()` (LRU cached, free) and copies
~12 float attributes. This runs on every `/api/items/latest` request that uses
the FeedBuilder. It's cheap (microseconds) but unnecessary.

**Estimated impact:** Low — CPU is negligible. Noted because it's a one-line fix.  
**Fix:** Store scorer as a `FeedBuilder` instance attribute set in `__init__`.

---

### F-13: Connection pool sizing may be too small for concurrent pipeline + API

**File:line:** `src/core/database.py:27–30`

```python
pool_size=5,
max_overflow=5,
```

Total max connections: 10. The scheduler runs multiple concurrent pipeline
jobs (HN every 30min, RSS/GH/HF/WS every 60min, HN-leading every 15min) each
creating its own session. If a slow pipeline run overlaps with a burst of API
requests, the pool will exhaust and requests will queue waiting for a
connection.

**Estimated impact:** Low at low traffic. On a VPS with <10 concurrent users
this is fine. Worth monitoring as traffic grows.

**Needs production data:** Check `pg_stat_activity` or SQLAlchemy pool events
for wait times during pipeline execution.

---

## Dimension 5 — Feed Algorithm

### F-14: MMR is O(K × selected) — fine at current scale

**File:line:** `src/feed/mmr_ranker.py:67–83`

The MMR loop is O(remaining × selected) for each selection step, giving
O(limit × pool_size) total. With `feed_candidate_multiplier=5` and
`limit=50`, that's `250 × 50 / 2 ≈ 6250` `item_similarity` calls per feed
request. Each call does two `set` operations on tokenized titles (Jaccard).
This is ~milliseconds and well within acceptable range.

**Verdict:** Already fine for the current pool sizes. Would only matter at
`pool_size > 1000`.

---

### F-15: Feed candidate pool fetched up to 3 times (progressive window expansion)

**File:line:** `src/feed/feed_builder.py:96–131`

The `_fetch_candidates` method tries up to 3 time windows sequentially. If the
first two windows return fewer than `feed_latest_min_items=5` items, it fires 3
DB queries before returning. In a cold DB (new deployment) or low-traffic
period this means 3 queries where 1 would suffice.

**Estimated impact:** Low — 3 queries, each lightweight (indexed, LIMIT'd). The
window expansion is the right UX behavior.

**Verdict:** Acceptable trade-off. Not worth changing.

---

## Dimension 6 — Redundancy & Dead Paths

### F-16: `search.py` FTS query computes `ts_vector` on-the-fly instead of using stored column

**File:line:** `src/api/routes/search.py:50–65`

```python
ts_vector = func.to_tsvector(
    "simple",
    func.coalesce(NewsItem.title, "") + " " + func.coalesce(NewsItem.full_text, "") + ...
)
```

The `news_items` table has a pre-computed `search_vector` TSVECTOR column
(models.py line 87) with a GIN index (`idx_news_items_search`, line 113). But
the search route re-computes the tsvector at query time from raw text instead of
using the stored column. This means:
- The GIN index on `search_vector` is unused for the FTS part
- `to_tsvector` is called on every matching row (O(n) computation)
- The `ilike` OR fallback adds a sequential scan component anyway

**Estimated impact:** Med — the stored `search_vector` + GIN index path is
substantially faster than the runtime `to_tsvector` path, especially as the
table grows. The GIN index exists but is never used.

**Effort:** S  
**Risk:** Low  
**Fix:**
```python
fts_match = NewsItem.search_vector.bool_op("@@")(func.plainto_tsquery("simple", q))
rank_col = func.ts_rank(NewsItem.search_vector, func.plainto_tsquery("simple", q))
```
Note: `search_vector` must be populated (via trigger or pipeline update step)
for this to work correctly. **Needs confirmation that `search_vector` is
actually being populated** — the column exists in the model but no trigger or
pipeline code was found that updates it. If it's always NULL, the GIN index and
stored column are currently dead weight.

**Needs production data / code verification:** Check if any migration or
trigger populates `search_vector`. A quick `SELECT COUNT(*) FROM news_items WHERE
search_vector IS NOT NULL` would confirm.

---

### F-17: `LLMClassifier._get_client()` creates a new `AsyncOpenAI` client on every `classify()` call

**File:line:** `src/classifiers/llm.py:204–212`

```python
def _get_client(self) -> openai.AsyncOpenAI:
    if self._client is not None:
        return self._client
    settings = get_settings()
    return openai.AsyncOpenAI(...)
```

When `self._client` is None (the default path in production), this creates a
**new** `AsyncOpenAI` client on every call to `_get_client()`, which happens
once per `classify()` invocation. Since `LLMClassifier` is also created fresh
in `run_classification` (line 71 of `classify.py`): `classifier =
LLMClassifier()`, a new client is built every pipeline run. This abandons the
previous client's connection pool.

The same pattern exists for `ChatService` (chat.py line 40–44) but there the
service is injected as a FastAPI dependency so it's scoped per-request anyway.

**Estimated impact:** Low — one new client per pipeline run (~hourly). Slightly
wasteful but not a real bottleneck.  
**Fix:** Cache the client as a class-level or module-level singleton, or make
`LLMClassifier` a singleton passed in via the pipeline.

---

## Section: Needs Production Data to Confirm

| ID | What to measure | How to check |
|----|----------------|--------------|
| F-1 | Fraction of pipeline time spent in title similarity loop | Prometheus `pipeline_duration_seconds` histogram broken down by stage |
| F-4 | Whether `NOT IN` causes seq scan | `EXPLAIN ANALYZE SELECT * FROM news_items WHERE id NOT IN (SELECT item_id FROM item_embeddings WHERE model = '...')` |
| F-6 | Whether topic+date queries use the effective_date index | `EXPLAIN (ANALYZE, BUFFERS) SELECT * FROM news_items WHERE topic='models' AND COALESCE(published_at, created_at) > now() - interval '48h'` |
| F-13 | Connection pool exhaustion during concurrent pipeline runs | `pg_stat_activity` during a pipeline run, or SQLAlchemy pool event logging |
| F-16 | Whether `search_vector` is populated | `SELECT COUNT(*) FROM news_items WHERE search_vector IS NOT NULL` |
| F-3 | Actual latency of `_verify_url_content` calls | Pipeline trace logs — check time between `classification_complete` and `validation_complete` |

---

## Section: NOT Worth It / Already Optimal

| Area | Finding | Reason it's fine |
|------|---------|-----------------|
| Title similarity pre-filter | `text_utils.py:13–17` — length ratio check before rapidfuzz | Already eliminates many comparisons cheaply |
| Embedding batch size | `_BATCH_SIZE=100` in `embeddings.py` | Matches OpenAI's recommended batch size for `text-embedding-3-small` |
| Keyword regex caching | `keyword.py` regex patterns | Python `re` module LRU cache absorbs repeated patterns |
| MMR complexity | `mmr_ranker.py` O(K×selected) | At `pool_size≤250`, cost is microseconds |
| Extraction concurrency | `asyncio.gather` over all extractors | Already fully parallel — correct |
| URL hash dedup (pass 1) | Indexed lookup on `url_hash` with `IN` clause | Single round-trip, uses `uix_news_items_url_hash` partial unique index |
| Feed window expansion | 3 sequential queries with LIMIT | Cheap, correct UX behavior for cold DB |
| HNSW index presence | Single HNSW index on `item_embeddings` | Correct; prior duplicate removal is already done |
| DB pool pre-ping | `pool_pre_ping=True` | Correct for long-lived connections on VPS |
| Circuit breaker | `CircuitBreaker` in scheduler | Well-placed, correct granularity |
| `seen_window_days=7` | DB cutoff in both seen_filter passes | Keeps comparison set bounded |
| `dedup.py` hash pass | In-memory dict dedup before DB | Zero DB cost for cross-source URL duplicates within one extraction run |
