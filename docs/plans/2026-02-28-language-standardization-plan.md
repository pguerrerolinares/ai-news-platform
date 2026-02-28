# Language Standardization Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Standardize the entire platform to English, fix data bugs, optimize schema, and make the frontend i18n-ready.

**Architecture:** Clean slate rebuild — fix code first, apply schema migration on empty tables, then re-classify all raw_extractions in English with correct dates. Frontend moves to react-i18next with locale files.

**Tech Stack:** Python 3.12+, FastAPI, SQLAlchemy async, PostgreSQL/pgvector, Alembic, React 19, react-i18next, Vite

**Design doc:** `docs/plans/2026-02-28-language-standardization-design.md`

---

## Task 1: Fix search.py effective_date bug

**Files:**
- Modify: `src/api/routes/search.py:1-79`
- Test: `tests/unit/test_search_route.py` (existing)

**Step 1: Fix the import and date filtering**

In `src/api/routes/search.py`, add the `effective_date` import and replace `NewsItem.published_at` with `effective_date` in date filters and sort:

```python
# Add to imports (after line 15):
from src.core.queries import effective_date

# Replace lines 67-70:
    if date_from:
        query = query.where(func.date(effective_date) >= date_from)
    if date_to:
        query = query.where(func.date(effective_date) <= date_to)

# Replace line 79 (sort by date):
        query = query.order_by(effective_date.desc())
```

**Step 2: Run tests**

Run: `pytest tests/ -x -k "search" --timeout=30`
Expected: All search tests PASS

**Step 3: Commit**

```bash
git add src/api/routes/search.py
git commit -m "fix: use effective_date in search route for consistent date filtering"
```

---

## Task 2: Fix retriever.py effective_date bug

**Files:**
- Modify: `src/rag/retriever.py:1-92`
- Test: `tests/unit/test_retriever.py` (existing)

**Step 1: Fix the import and date filtering**

In `src/rag/retriever.py`, add the import and replace `NewsItem.published_at`:

```python
# Add to imports (after line 11):
from src.core.queries import effective_date

# Replace line 88:
            stmt = stmt.where(effective_date >= since)
```

**Step 2: Run tests**

Run: `pytest tests/ -x -k "retriever" --timeout=30`
Expected: All retriever tests PASS

**Step 3: Commit**

```bash
git add src/rag/retriever.py
git commit -m "fix: use effective_date in RAG retriever for consistent date filtering"
```

---

## Task 3: Fix extractor date fallbacks

**Files:**
- Modify: `src/extractors/hackernews.py:117-120`
- Modify: `src/extractors/github.py:103-106`
- Modify: `src/extractors/huggingface.py:54-57,116-121`
- Test: existing extractor tests

**Step 1: Fix all datetime.now() fallbacks to None**

In each extractor, replace the `except` block's `datetime.now(tz=UTC)` with `None`:

`src/extractors/hackernews.py`:
```python
            try:
                created_at = datetime.fromtimestamp(hit.get("created_at_i", 0), tz=UTC)
            except (ValueError, OSError):
                created_at = None
```

`src/extractors/github.py`:
```python
            try:
                pushed = datetime.fromisoformat(repo.get("pushed_at", "").replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                pushed = None
```

`src/extractors/huggingface.py` (both locations — daily papers ~line 57 and models ~line 121):
```python
            except (ValueError, AttributeError):
                published = None  # or last_mod = None for the models extractor
```

**Step 2: Run tests**

Run: `pytest tests/ -x -k "extractor" --timeout=30`
Expected: PASS (may need test updates if tests assert on datetime.now behavior)

**Step 3: Commit**

```bash
git add src/extractors/hackernews.py src/extractors/github.py src/extractors/huggingface.py
git commit -m "fix: use None instead of datetime.now() for unparseable dates in extractors"
```

---

## Task 4: Add HTML entity decoding to extractors

**Files:**
- Modify: `src/extractors/hackernews.py`
- Modify: `src/extractors/github.py`
- Modify: `src/extractors/rss.py`
- Modify: `src/extractors/huggingface.py`
- Modify: `src/extractors/arxiv.py`
- Modify: `src/extractors/reddit.py`
- Test: write a targeted unit test

**Step 1: Write a test for HTML entity decoding**

Create or add to `tests/unit/test_html_decoding.py`:

```python
"""Test that extractors decode HTML entities in titles."""
import html


def test_html_unescape_smart_quotes():
    raw = "We don&#8217;t have to have unsupervised killer robots"
    assert html.unescape(raw) == "We don\u2019t have to have unsupervised killer robots"


def test_html_unescape_amp():
    raw = "ML &amp; AI"
    assert html.unescape(raw) == "ML & AI"


def test_html_unescape_noop():
    raw = "Normal title without entities"
    assert html.unescape(raw) == raw
```

**Step 2: Run test to verify it passes**

Run: `pytest tests/unit/test_html_decoding.py -v`
Expected: PASS (stdlib html.unescape works correctly)

**Step 3: Add html.unescape() to each extractor**

In each extractor, add `import html` at the top and wrap title/text with `html.unescape()`:

`src/extractors/hackernews.py`:
```python
import html
# ...
title=html.unescape(hit.get("title") or ""),
text=html.unescape(hit.get("title") or ""),
```

`src/extractors/github.py`:
```python
import html
# ...
name = html.unescape(repo.get("name", ""))
description = html.unescape(repo.get("description") or "")
```

`src/extractors/rss.py`:
```python
import html
# ...
title = html.unescape(entry.get("title", ""))
```

Apply same pattern to `arxiv.py`, `reddit.py`, `huggingface.py` — add `html.unescape()` on title and text/description fields.

**Step 4: Run all extractor tests**

Run: `pytest tests/ -x -k "extractor" --timeout=30`
Expected: PASS

**Step 5: Commit**

```bash
git add src/extractors/ tests/unit/test_html_decoding.py
git commit -m "fix: decode HTML entities in extractor titles and text"
```

---

## Task 5: Update ORM model — topics + new columns

**Files:**
- Modify: `src/core/models.py:35-43,82-101`
- Test: existing model tests

**Step 1: Update VALID_TOPICS and add new columns**

In `src/core/models.py`:

```python
# Replace VALID_TOPICS (lines 35-43):
VALID_TOPICS = (
    "models",
    "papers",
    "agents",
    "products",
    "tools",
    "open_source",
    "regulation",
)

# Add new columns to NewsItem class (after line 80):
    language: Mapped[str] = mapped_column(String(5), server_default=text("'en'"))
    search_vector: Mapped[str | None] = mapped_column(
        TSVECTOR, deferred=True
    )
```

Note: Import `TSVECTOR` from `sqlalchemy.dialects.postgresql`:
```python
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR, UUID
```

Also remove `idx_news_items_content_hash` from `__table_args__` (line 90) since we're dropping it.

**Step 2: Run tests**

Run: `pytest tests/ -x --timeout=30 -q`
Expected: Some tests may fail due to topic changes — update test fixtures in next tasks

**Step 3: Commit**

```bash
git add src/core/models.py
git commit -m "feat: update topics to English, add language and search_vector columns"
```

---

## Task 6: Create Alembic migration 008

**Files:**
- Create: `alembic/versions/008_language_and_optimization.py`

**Step 1: Write the migration**

```python
"""Language standardization, search vector, and index optimization.

Revision ID: 008
Revises: 007
Create Date: 2026-02-28
"""

from alembic import op

revision = "008"
down_revision = "007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. New columns
    op.execute("ALTER TABLE news_items ADD COLUMN IF NOT EXISTS language VARCHAR(5) NOT NULL DEFAULT 'en'")
    op.execute("ALTER TABLE news_items ADD COLUMN IF NOT EXISTS search_vector tsvector")

    # 2. search_vector auto-update trigger
    op.execute("""
        CREATE OR REPLACE FUNCTION news_items_search_trigger() RETURNS trigger AS $$
        BEGIN
          NEW.search_vector := to_tsvector('english',
            coalesce(NEW.title, '') || ' ' || coalesce(NEW.summary, ''));
          RETURN NEW;
        END $$ LANGUAGE plpgsql
    """)
    op.execute("""
        CREATE TRIGGER trg_news_items_search
          BEFORE INSERT OR UPDATE OF title, summary ON news_items
          FOR EACH ROW EXECUTE FUNCTION news_items_search_trigger()
    """)

    # 3. GIN index on search_vector
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_news_items_search "
        "ON news_items USING gin(search_vector)"
    )

    # 4. HNSW index on embeddings
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_embeddings_hnsw "
        "ON item_embeddings USING hnsw (embedding vector_cosine_ops)"
    )

    # 5. Partial index for trending
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_news_items_trending_date "
        "ON news_items (COALESCE(published_at, created_at) DESC) "
        "WHERE trending = true"
    )

    # 6. Drop duplicate index (unique constraint already covers this)
    op.execute("DROP INDEX IF EXISTS idx_news_items_content_hash")


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_news_items_search ON news_items")
    op.execute("DROP FUNCTION IF EXISTS news_items_search_trigger()")
    op.execute("DROP INDEX IF EXISTS idx_news_items_search")
    op.execute("DROP INDEX IF EXISTS idx_embeddings_hnsw")
    op.execute("DROP INDEX IF EXISTS idx_news_items_trending_date")
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_news_items_content_hash "
        "ON news_items (content_hash)"
    )
    op.execute("ALTER TABLE news_items DROP COLUMN IF EXISTS search_vector")
    op.execute("ALTER TABLE news_items DROP COLUMN IF EXISTS language")
```

**Step 2: Test migration locally**

Run:
```bash
# Truncate first (empty tables = instant migration)
docker exec ai-news-platform-db-1 psql -U ainews -d ainews -c "TRUNCATE item_embeddings, news_items CASCADE;"
alembic upgrade head
```
Expected: Migration completes without errors

**Step 3: Verify schema**

```bash
docker exec ai-news-platform-db-1 psql -U ainews -d ainews -c "\d news_items"
```
Expected: `language` and `search_vector` columns present

**Step 4: Commit**

```bash
git add alembic/versions/008_language_and_optimization.py
git commit -m "feat: migration 008 — language column, search_vector, HNSW, index optimization"
```

---

## Task 7: Update LLM classifier to English

**Files:**
- Modify: `src/classifiers/llm.py:31-34,135-182`
- Test: `tests/unit/test_llm_classifier.py` (existing)

**Step 1: Update SYSTEM_MESSAGE**

```python
SYSTEM_MESSAGE = (
    "You are an AI news classifier. "
    "Respond ONLY with a valid JSON array, no additional text."
)
```

**Step 2: Update classification prompt**

Replace the entire `_build_prompt` return string (lines 135-182) with the English version. Maintain the same structure:

```python
    return f"""Classify these {len(batch)} items. BE STRICT with is_news.

REJECT (is_news=false):
- Opinions, rants, personal stories, career/job discussions
- Generic tips, basic tutorials, beginner questions
- Content unrelated to AI/ML/LLM (child safety, photography, etc.)
- Memes, spam, trivial content without technical substance

ACCEPT (is_news=true):
- Model launches, AI tools, AI products
- Papers with clear technical contribution
- AI company news (OpenAI, Google, Meta, Anthropic, etc.)
- Technical advances, benchmarks, open source releases

RELEVANCE SCALE (use the full range, do NOT put 0.9 on everything):
- 1.0: Major launch from top company or breakthrough with massive impact
- 0.95: Important release with verifiable metrics surpassing SOTA
- 0.9: Significant news with clear industry impact
- 0.85: Interesting paper or release but incremental
- 0.8: Relevant but routine content
- 0.75: Minimally relevant, niche
- <0.75: Reject (is_news=false)

DISAMBIGUATION RULES:
- arXiv preprint without code/weights release -> "papers" (NOT "models")
- Model with published weights on HuggingFace/GitHub -> "models"
- Paper about agents/tool-use -> "agents" (NOT "papers")
- Consumer product (ChatGPT feature, Claude update) -> "products" (NOT "models")

Topics:
{topics_info}

Items:{items_text}

SUMMARY - MAX 25 words in English:
- Do NOT repeat the title: add context
- If paper: mention main result
- If release: mention key improvement
GOOD: "New MoE 397B params, 17B active; surpasses Llama 3.1 on MMLU and code"
BAD: "New model release" (too vague)

JSON array. relevance: 0.75-1.0 per scale above.
[
  {{"idx": 0, "is_news": true, "topic": "models",
    "relevance": 0.85, "summary": "Short phrase in English max 25 words"}},
  {{"idx": 1, "is_news": false}},
  ...
]"""
```

**Step 3: Run tests**

Run: `pytest tests/ -x -k "classifier or llm" --timeout=30`
Expected: PASS (update test fixtures if they assert on Spanish text)

**Step 4: Commit**

```bash
git add src/classifiers/llm.py
git commit -m "feat: switch LLM classifier prompts to English"
```

---

## Task 8: Update keyword classifier topics to English

**Files:**
- Modify: `src/classifiers/keyword.py`
- Test: `tests/unit/test_keyword_classifier.py` (existing)

**Step 1: Rename all topic keys**

Find and replace throughout the file:
- `"modelos"` → `"models"`
- `"herramientas"` → `"tools"`
- `"productos"` → `"products"`
- `"agentes"` → `"agents"`
- `"regulacion"` → `"regulation"`

Also translate the `"description"` values from Spanish to English.

**Step 2: Run tests**

Run: `pytest tests/ -x -k "keyword" --timeout=30`
Expected: FAIL (tests assert on old Spanish topic names) — update test fixtures

**Step 3: Update test fixtures**

In test files, replace Spanish topic names with English equivalents.

**Step 4: Run tests again**

Run: `pytest tests/ -x -k "keyword" --timeout=30`
Expected: PASS

**Step 5: Commit**

```bash
git add src/classifiers/keyword.py tests/
git commit -m "feat: rename keyword classifier topics to English"
```

---

## Task 9: Update RAG chat to English

**Files:**
- Modify: `src/rag/chat.py:20-26,58-78,61,105,176`
- Test: `tests/unit/test_chat.py` (existing)

**Step 1: Update SYSTEM_PROMPT**

```python
SYSTEM_PROMPT = (
    "You are an expert AI and technology news assistant. "
    "Respond based ONLY on the news provided as context. "
    "If there is no relevant information, say so clearly. "
    "Include sources (titles and URLs) in your response. "
    "Respond in English."
)
```

**Step 2: Update _build_context labels**

```python
    def _build_context(self, items: list[NewsItem]) -> str:
        if not items:
            return "No relevant news found in the database."

        lines: list[str] = []
        for i, item in enumerate(items, 1):
            parts = [f"[{i}] {item.title}"]
            if item.summary:
                parts.append(f"   Summary: {item.summary}")
            if item.url:
                parts.append(f"   URL: {item.url}")
            if item.source:
                parts.append(f"   Source: {item.source}")
            if item.topic:
                parts.append(f"   Topic: {item.topic}")
            if item.published_at:
                parts.append(f"   Date: {item.published_at.strftime('%Y-%m-%d')}")
            lines.append("\n".join(parts))

        return "\n\n".join(lines)
```

**Step 3: Update error messages**

Search for all Spanish error strings and translate:
- `"La pregunta no puede estar vacia"` → `"Question cannot be empty"`
- `"Error al generar la respuesta"` → `"Error generating response"`

**Step 4: Run tests**

Run: `pytest tests/ -x -k "chat" --timeout=30`
Expected: PASS (update test fixtures if needed)

**Step 5: Commit**

```bash
git add src/rag/chat.py
git commit -m "feat: switch RAG chat prompts and labels to English"
```

---

## Task 10: Update Telegram notifier to English

**Files:**
- Modify: `src/notifiers/telegram.py`
- Test: `tests/unit/test_telegram.py` (existing)

**Step 1: Update all Spanish strings**

Find and replace all user-facing Spanish strings:
- `"📭 No hay noticias relevantes hoy."` → `"📭 No relevant news today."`
- `"📊 {len(items)} noticias  · {source_str}"` → `"📊 {len(items)} news  · {source_str}"`
- `"⭐ <b>TOP 3 DEL DIA</b>"` → `"⭐ <b>TOP 3 TODAY</b>"`
- `"{len(items)} analizados"` → `"{len(items)} analyzed"`

Update topic emoji mapping keys:
- `"modelos"` → `"models"`
- `"herramientas"` → `"tools"`
- `"productos"` → `"products"`
- `"agentes"` → `"agents"`
- `"regulacion"` → `"regulation"`

**Step 2: Run tests**

Run: `pytest tests/ -x -k "telegram" --timeout=30`
Expected: PASS (update test fixtures for English strings)

**Step 3: Commit**

```bash
git add src/notifiers/telegram.py
git commit -m "feat: switch Telegram notifier to English"
```

---

## Task 11: Update event_dedup topic references

**Files:**
- Modify: `src/classifiers/event_dedup.py` (if it references topic names)
- Modify: any other file referencing old Spanish topic names

**Step 1: Search for remaining Spanish topic references**

```bash
rg "modelos|herramientas|productos|agentes|regulacion" src/ --glob "*.py" -l
```

Fix any remaining references. Check:
- `src/classifiers/event_dedup.py`
- `src/pipeline/pipeline.py`
- `src/api/routes/*.py`
- `src/api/schemas.py`

**Step 2: Run full test suite**

Run: `pytest tests/ -x --timeout=30 -q`
Expected: ALL PASS

**Step 3: Commit**

```bash
git add -u
git commit -m "refactor: update remaining Spanish topic references to English"
```

---

## Task 12: Fix backfill script — dates + HTML decoding

**Files:**
- Modify: `scripts/backfill.py:364-408`
- Test: `tests/unit/test_backfill_extractors.py` (existing)

**Step 1: Fix `_raw_to_extracted()` to parse actual dates**

```python
import html

def _raw_to_extracted(raw: RawExtraction) -> ExtractedItem:
    """Convert a RawExtraction record to an ExtractedItem."""
    j = raw.raw_json
    if raw.source == "hackernews":
        url = j.get("url") or f"https://news.ycombinator.com/item?id={raw.source_id}"
        # Parse actual publication date from raw JSON
        try:
            published_at = datetime.fromtimestamp(j.get("created_at_i", 0), tz=UTC)
        except (ValueError, OSError):
            published_at = raw.extracted_at
        return ExtractedItem(
            title=html.unescape(j.get("title", "")),
            source="hackernews",
            url=url,
            text=html.unescape(j.get("title", "")),
            author=j.get("author", "unknown"),
            published_at=published_at,
            score=j.get("points", 0),
            metadata={
                "story_id": raw.source_id,
                "num_comments": j.get("num_comments", 0),
            },
        )
    if raw.source == "github":
        desc = html.unescape(j.get("description") or "")
        name = html.unescape(j.get("name", ""))
        # Parse actual push date from raw JSON
        try:
            published_at = datetime.fromisoformat(
                j.get("pushed_at", "").replace("Z", "+00:00")
            )
        except (ValueError, AttributeError):
            published_at = raw.extracted_at
        return ExtractedItem(
            title=f"{name}: {desc}" if desc else name,
            source="github",
            url=j.get("html_url", ""),
            text=desc,
            author=j.get("owner", {}).get("login", "unknown"),
            published_at=published_at,
            score=j.get("stargazers_count", 0),
            metadata={
                "stars": j.get("stargazers_count", 0),
                "full_name": j.get("full_name", ""),
            },
        )
    # huggingface
    try:
        published_at = datetime.fromisoformat(
            j.get("lastModified", "").replace("Z", "+00:00")
        )
    except (ValueError, AttributeError):
        published_at = raw.extracted_at
    return ExtractedItem(
        title=html.unescape(raw.source_id),
        source="huggingface",
        url=f"https://huggingface.co/{raw.source_id}",
        text=raw.source_id,
        author=raw.source_id.split("/")[0] if "/" in raw.source_id else "unknown",
        published_at=published_at,
        score=j.get("downloads", 0),
        metadata={"downloads": j.get("downloads", 0), "likes": j.get("likes", 0)},
    )
```

**Step 2: Run backfill tests**

Run: `pytest tests/ -x -k "backfill" --timeout=30`
Expected: PASS

**Step 3: Commit**

```bash
git add scripts/backfill.py
git commit -m "fix: parse actual publication dates from raw_json, add HTML entity decoding"
```

---

## Task 13: Setup react-i18next in frontend

**Files:**
- Create: `frontend/src/i18n/config.ts`
- Create: `frontend/src/i18n/locales/en.json`
- Modify: `frontend/src/main.tsx` (import i18n config)
- Modify: `frontend/package.json` (add dependencies)

**Step 1: Install dependencies**

```bash
cd frontend && npm install react-i18next i18next
```

**Step 2: Create i18n config**

Create `frontend/src/i18n/config.ts`:
```typescript
import i18n from 'i18next'
import { initReactI18next } from 'react-i18next'

import en from './locales/en.json'

i18n.use(initReactI18next).init({
  resources: { en: { translation: en } },
  lng: 'en',
  fallbackLng: 'en',
  interpolation: { escapeValue: false },
})

export default i18n
```

**Step 3: Create en.json locale file**

Create `frontend/src/i18n/locales/en.json`:
```json
{
  "common": {
    "retry": "Retry",
    "loading": "Loading...",
    "send": "Send",
    "all": "All"
  },
  "nav": {
    "trending": "Trending",
    "search": "Search",
    "chat": "Chat",
    "logout": "Log out"
  },
  "dashboard": {
    "loading": "Loading news...",
    "errorLoading": "Error loading news",
    "newsCount": "{{count}} news, {{trending}} trending",
    "filterByTopic": "Filter by topic",
    "allTopics": "All topics",
    "noNewsForTopic": "No news for this topic",
    "errorLoadingMore": "Error loading more news"
  },
  "trending": {
    "loading": "Loading trending...",
    "gainingTraction": "{{count}} news gaining traction now",
    "noTrending": "No trending news",
    "highestScoring": "Highest scoring news"
  },
  "search": {
    "title": "Search",
    "subtitle": "Search through AI news",
    "placeholder": "Search news...",
    "searchButton": "Search",
    "hint": "Type and press Enter or Search"
  },
  "chat": {
    "title": "AI Chat",
    "subtitle": "Ask about today's AI news",
    "placeholder": "Type your question...",
    "suggestion1": "What LLM news is there?",
    "suggestion2": "Summarize today's trending",
    "suggestion3": "What new tools are available?"
  },
  "login": {
    "sendCode": "Send code",
    "sending": "Sending...",
    "verify": "Verify",
    "verifying": "Verifying..."
  },
  "topics": {
    "models": "Models",
    "tools": "Tools",
    "papers": "Papers",
    "products": "Products",
    "open_source": "Open Source",
    "agents": "Agents",
    "regulation": "Regulation"
  }
}
```

**Step 4: Import i18n in main.tsx**

Add at the top of `frontend/src/main.tsx`:
```typescript
import './i18n/config'
```

**Step 5: Build to verify**

Run: `cd frontend && npm run build`
Expected: Build succeeds

**Step 6: Commit**

```bash
cd frontend
git add src/i18n/ src/main.tsx package.json package-lock.json
git commit -m "feat: setup react-i18next with English locale"
```

---

## Task 14: Update frontend constants and date formatting

**Files:**
- Modify: `frontend/src/lib/constants.ts`

**Step 1: Update topic labels and date locale**

```typescript
export const TOPIC_LABELS: Record<string, string> = {
  models: 'Models',
  tools: 'Tools',
  papers: 'Papers',
  products: 'Products',
  open_source: 'Open Source',
  agents: 'Agents',
  regulation: 'Regulation',
}

export function formatTime(dateStr: string | null) {
  if (!dateStr) return ''
  const d = new Date(dateStr)
  return d.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' })
}
```

**Step 2: Commit**

```bash
git add frontend/src/lib/constants.ts
git commit -m "feat: update topic labels to English and date format to en-GB"
```

---

## Task 15: Update frontend pages to use i18n

**Files:**
- Modify: `frontend/src/pages/Dashboard.tsx`
- Modify: `frontend/src/pages/Trending.tsx`
- Modify: `frontend/src/pages/Buscar.tsx` → rename to `Search.tsx`
- Modify: `frontend/src/pages/Chat.tsx`
- Modify: `frontend/src/pages/Login.tsx`
- Modify: `frontend/src/components/app-nav.tsx`
- Modify: `frontend/src/App.tsx`

**Step 1: Add `useTranslation` to each page**

In every page/component with Spanish strings, add:
```typescript
import { useTranslation } from 'react-i18next'
// Inside component:
const { t } = useTranslation()
```

Then replace every hardcoded Spanish string with `t('section.key')`. For example in `Dashboard.tsx`:
- `"Cargando noticias..."` → `{t('dashboard.loading')}`
- `"Reintentar"` → `{t('common.retry')}`
- `"Filtrar por topic"` → `{t('dashboard.filterByTopic')}`
- `"Todos los topics"` → `{t('dashboard.allTopics')}`
- `"No hay noticias para este topic"` → `{t('dashboard.noNewsForTopic')}`

Apply same pattern to all pages.

**Step 2: Rename Buscar.tsx to Search.tsx**

```bash
cd frontend
git mv src/pages/Buscar.tsx src/pages/Search.tsx
```

Update the component name from `Buscar` to `Search` inside the file.

**Step 3: Update App.tsx routes**

```typescript
import Search from '@/pages/Search'
// ...
<Route path="search" element={<Search />} />
```

**Step 4: Update nav links**

In `app-nav.tsx`:
```typescript
{ to: '/search', label: t('nav.search') },
```

**Step 5: Build and verify**

Run: `cd frontend && npm run build`
Expected: Build succeeds

**Step 6: Commit**

```bash
git add frontend/src/
git commit -m "feat: migrate all frontend strings to react-i18next English locale"
```

---

## Task 16: Update existing tests for English output

**Files:**
- Modify: various test files that assert on Spanish strings

**Step 1: Find all tests asserting on Spanish strings**

```bash
rg "espanol|Resumen|Fuente|Tema|modelos|herramientas|productos|agentes|regulacion|noticias" tests/ --glob "*.py" -l
```

**Step 2: Update test assertions**

Replace Spanish topic names and strings with English equivalents in all test files. Key changes:
- `"modelos"` → `"models"` in test fixtures and assertions
- `"herramientas"` → `"tools"`
- `"productos"` → `"products"`
- `"agentes"` → `"agents"`
- `"regulacion"` → `"regulation"`
- Any assertions on Spanish summary text or error messages

**Step 3: Run full test suite**

Run: `ruff check . && ruff format --check . && pyright . && pytest tests/ -x --timeout=30`
Expected: ALL PASS

**Step 4: Commit**

```bash
git add tests/
git commit -m "test: update all test fixtures for English topics and strings"
```

---

## Task 17: Local data rebuild and verification

**Files:** None (operational task)

**Step 1: Truncate local DB**

```bash
docker exec ai-news-platform-db-1 psql -U ainews -d ainews -c "TRUNCATE item_embeddings, news_items CASCADE;"
```

**Step 2: Run migration**

```bash
alembic upgrade head
```
Expected: Migration 008 applies cleanly

**Step 3: Re-classify from raw data**

```bash
python scripts/backfill.py --phase classify --max-cost 5
```
Expected: Items classified with English summaries and correct dates

**Step 4: Re-generate embeddings**

```bash
python scripts/backfill.py --phase embed
```
Expected: Embeddings generated

**Step 5: Verify data**

```bash
# Check English summaries
docker exec ai-news-platform-db-1 psql -U ainews -d ainews -c "SELECT title, summary, topic, published_at FROM news_items ORDER BY published_at DESC LIMIT 5;"

# Check topics are English
docker exec ai-news-platform-db-1 psql -U ainews -d ainews -c "SELECT topic, count(*) FROM news_items GROUP BY topic ORDER BY count DESC;"

# Check dates are correct (should span 2023-2026, NOT all same day)
docker exec ai-news-platform-db-1 psql -U ainews -d ainews -c "SELECT min(published_at)::date, max(published_at)::date FROM news_items;"

# Check search_vector is populated
docker exec ai-news-platform-db-1 psql -U ainews -d ainews -c "SELECT count(*) FROM news_items WHERE search_vector IS NOT NULL;"

# Check HNSW index exists
docker exec ai-news-platform-db-1 psql -U ainews -d ainews -c "SELECT indexname FROM pg_indexes WHERE indexname = 'idx_embeddings_hnsw';"
```

**Step 6: Run full test suite one final time**

Run: `ruff check . && ruff format --check . && pyright . && pytest tests/ -x --timeout=30`
Expected: ALL PASS

**Step 7: Final commit**

```bash
git commit --allow-empty -m "docs: language standardization complete — verified locally"
```

---

## Summary

| Task | Description | Risk |
|------|------------|------|
| 1 | Fix search.py effective_date | Low |
| 2 | Fix retriever.py effective_date | Low |
| 3 | Fix extractor date fallbacks | Low |
| 4 | Add HTML entity decoding | Low |
| 5 | Update ORM model topics + columns | Medium |
| 6 | Alembic migration 008 | Medium |
| 7 | LLM classifier → English | Low |
| 8 | Keyword classifier → English | Low |
| 9 | RAG chat → English | Low |
| 10 | Telegram notifier → English | Low |
| 11 | Clean up remaining topic refs | Low |
| 12 | Fix backfill dates + HTML | Medium |
| 13 | Setup react-i18next | Low |
| 14 | Frontend constants → English | Low |
| 15 | Frontend pages → i18n | Medium |
| 16 | Update tests | Medium |
| 17 | Local data rebuild + verify | Low |

**Total estimated time:** Tasks 1-16 are code changes. Task 17 is verification.
**Production deploy:** Follow Section 5.2 of the design doc after local verification.
