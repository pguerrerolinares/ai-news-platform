# Language Standardization + Bug Fixes + Schema Optimization

**Date**: 2026-02-28
**Status**: Complete (deployed to production 2026-02-28)

## Goal

Standardize the entire platform to English, fix data bugs, optimize schema, and make the frontend i18n-ready.

## Success Criteria

- All stored data (titles, summaries) in English
- All UI (frontend, Telegram, RAG chat) in English
- Historical data re-classified from raw_extractions with correct dates
- Schema optimized with proper indexes (HNSW, GIN, partial)
- Frontend i18n-ready with react-i18next + `en.json`
- All known bugs fixed

## Current State

- **6,374 news_items** with Spanish summaries, all dated 2026-02-21 (wrong)
- **21,526 raw_extractions** (source of truth, preserved)
- **6,374 item_embeddings** built from Spanish text
- LLM prompts, Telegram, RAG chat, frontend all in Spanish
- Topic keys in Spanish: modelos, herramientas, productos, agentes, regulacion
- Multiple bugs: wrong dates, missing effective_date in search/RAG, HTML entities

## Approach

**Clean slate rebuild**: Truncate news_items + item_embeddings, apply schema changes on empty tables, re-classify all raw_extractions in English with correct dates.

---

## Section 1: Bug Fixes

### Bug #1 (CRITICAL) — Search uses wrong date field
- **File**: `src/api/routes/search.py:68-70`
- **Fix**: Replace `func.date(NewsItem.published_at)` with `func.date(effective_date)`

### Bug #2 (CRITICAL) — RAG retriever uses wrong date field
- **File**: `src/rag/retriever.py:88`
- **Fix**: Replace `NewsItem.published_at >= since` with `effective_date >= since`

### Bug #3 (HIGH) — Backfill uses extraction time instead of actual dates
- **File**: `scripts/backfill.py:364-408` (`_raw_to_extracted()`)
- **Fix**: Parse actual dates from `raw_json`:
  - HN: `datetime.fromtimestamp(j.get("created_at_i", 0), tz=UTC)`
  - GitHub: `datetime.fromisoformat(j.get("pushed_at", ""))`
  - HuggingFace: `datetime.fromisoformat(j.get("lastModified", ""))`
  - Fallback to `raw.extracted_at` only if parsing fails

### Bugs #5-8 (MEDIUM) — Extractors fall back to datetime.now() on parse failure
- **Files**: `hackernews.py:120`, `github.py:106`, `huggingface.py:57,121`
- **Fix**: Replace `datetime.now(tz=UTC)` fallback with `None` (let `effective_date` COALESCE handle it)

### Bug #12 (MEDIUM) — HTML entities not decoded
- **Files**: All extractors + `scripts/backfill.py:_raw_to_extracted()`
- **Fix**: Add `html.unescape()` on title and text fields (stdlib, no new dependency)

---

## Section 2: Schema Changes (Migration 008)

Single Alembic migration `008_language_and_optimization.py`. Runs on empty tables after TRUNCATE = instant.

### 2.1 New column: language
```sql
ALTER TABLE news_items ADD COLUMN language VARCHAR(5) NOT NULL DEFAULT 'en';
```

### 2.2 New column + trigger: search_vector (full-text search)
```sql
ALTER TABLE news_items ADD COLUMN search_vector tsvector;

CREATE FUNCTION news_items_search_trigger() RETURNS trigger AS $$
BEGIN
  NEW.search_vector := to_tsvector('english',
    coalesce(NEW.title, '') || ' ' || coalesce(NEW.summary, ''));
  RETURN NEW;
END $$ LANGUAGE plpgsql;

CREATE TRIGGER trg_news_items_search
  BEFORE INSERT OR UPDATE OF title, summary ON news_items
  FOR EACH ROW EXECUTE FUNCTION news_items_search_trigger();
```

### 2.3 New index: GIN on search_vector
```sql
CREATE INDEX idx_news_items_search ON news_items USING gin(search_vector);
```

### 2.4 New index: HNSW on embeddings
```sql
CREATE INDEX idx_embeddings_hnsw
  ON item_embeddings USING hnsw (embedding vector_cosine_ops);
```

### 2.5 New index: Partial index for trending
```sql
CREATE INDEX idx_news_items_trending_date
  ON news_items (COALESCE(published_at, created_at) DESC) WHERE trending = true;
```

### 2.6 Drop duplicate index
```sql
DROP INDEX idx_news_items_content_hash;
-- news_items_content_hash_key (unique constraint) already covers this
```

---

## Section 3: Backend Language Changes

### 3.1 LLM Classifier — `src/classifiers/llm.py`
- `SYSTEM_MESSAGE` → English
- Classification prompt → English (same structure, translated)
- Summary instruction: "SUMMARY - MAX 25 words in English"
- Topic keys: modelos→models, herramientas→tools, productos→products, agentes→agents, regulacion→regulation

### 3.2 RAG Chat — `src/rag/chat.py`
- System prompt → English ("You are an expert AI news assistant...")
- Context labels: Resumen→Summary, Fuente→Source, Tema→Topic, Fecha→Date
- Error messages → English

### 3.3 Telegram Notifier — `src/notifiers/telegram.py`
- All user-facing strings → English
- Topic emoji mapping: update keys to English
- Headers: "TOP 3 DEL DIA" → "TOP 3 TODAY"
- Empty: "No hay noticias relevantes hoy" → "No relevant news today"

### 3.4 Keyword Classifier — `src/classifiers/keyword.py`
- Topic keys: modelos→models, herramientas→tools, etc.
- Topic descriptions → English

### 3.5 Extractors (all 6) — `src/extractors/*.py`
- Add `html.unescape()` on title/text
- Replace `datetime.now(tz=UTC)` fallback with `None`

### 3.6 Backfill script — `scripts/backfill.py`
- `_raw_to_extracted()`: Parse actual dates from `raw_json`
- Add `html.unescape()` on titles

### 3.7 Topic key mapping (full)

| Current (ES) | New (EN) |
|---|---|
| modelos | models |
| herramientas | tools |
| papers | papers |
| productos | products |
| open_source | open_source |
| agentes | agents |
| regulacion | regulation |

---

## Section 4: Frontend Changes

### 4.1 Setup react-i18next
- Install `react-i18next` + `i18next`
- Create `frontend/src/i18n/config.ts`
- Create `frontend/src/i18n/locales/en.json` with all strings organized by page/component

### 4.2 Locale file structure (`en.json`)
```json
{
  "common": { "retry", "loading", "send", "all" },
  "nav": { "trending", "search", "chat", "logout" },
  "dashboard": { "loading", "errorLoading", "newsCount", "filterByTopic", "allTopics", "noNewsForTopic" },
  "trending": { "loading", "gainingTraction", "noTrending", "highestScoring" },
  "search": { "title", "subtitle", "placeholder", "hint" },
  "chat": { "title", "subtitle", "placeholder", "suggestions" },
  "login": { "sendCode", "sending", "verify", "verifying" },
  "topics": { "models", "tools", "papers", "products", "open_source", "agents", "regulation" }
}
```

### 4.3 Component updates
- Replace hardcoded Spanish strings with `t('key')` calls in all pages/components
- Rename `Buscar.tsx` → `Search.tsx`
- Route `/buscar` → `/search`

### 4.4 Date locale
- `en-GB` for DD/MM/YYYY European format

---

## Section 5: Data Rebuild & Deployment

### 5.1 Local testing
1. Apply all code changes
2. Run tests: `ruff check . && pyright . && pytest tests/ -x`
3. Frontend build: `cd frontend && npm install && npm run build`
4. Local DB rebuild:
   - `TRUNCATE item_embeddings, news_items;`
   - `alembic upgrade head`
   - `python scripts/backfill.py --phase classify --max-cost 5`
   - `python scripts/backfill.py --phase embed`
5. Verify English summaries, correct dates, English topics, search_vector, HNSW index

### 5.2 Production deployment
1. Stop cron (disable scheduler in Coolify)
2. `git push main` → Coolify auto-deploys, migration 008 runs
3. SSH into API container:
   - `TRUNCATE item_embeddings, news_items;` (via psql)
   - `python scripts/backfill.py --phase classify --max-cost 10`
   - `python scripts/backfill.py --phase embed`
4. Verify data
5. Re-enable cron
6. Monitor first cron run

### 5.3 Rollback plan
- `alembic downgrade 007` reverts schema changes
- `raw_extractions` is never touched (source of truth)
- Revert git commit + redeploy + re-run old backfill if needed

### 5.4 Estimated cost
- LLM re-classification: ~$2-5
- Embedding regeneration: ~$0.01
- Total: under $6

---

## What Does NOT Change

- Pipeline orchestration logic (`run_pipeline()`)
- Auth system (JWT, OTP)
- API route structure (except `/buscar` → `/search`)
- Database engine (PostgreSQL + pgvector)
- Ops alerts (already English)
- Dedup, validation, metrics, logging logic
