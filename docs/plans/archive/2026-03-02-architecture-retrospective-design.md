# Architecture Retrospective — AI News Platform

> **Date**: 2026-03-02 | **Type**: Retrospective analysis | **Status**: Approved

## Context

The project has grown from a Telegram-only pipeline (`x-news-summarizer`) to a full-stack
platform with 7 extractors, React frontend, RAG chat, WebAuthn, and CI/CD auto-deploy.
437 commits, 8,600 LOC backend, 4,869 LOC frontend, 1,015+ tests at 92% coverage.

This retrospective evaluates architectural decisions made during the journey, identifies
tech debt, and proposes improvements prioritized by impact on the main pain point:
**pipeline performance and resource consumption on a 4GB VPS**.

The project remains a **personal tool for 5-10 users**. Improvements target maintainability
and resource efficiency, not scale.

---

## Good Decisions (Keep)

| # | Decision | Why it works |
|---|----------|-------------|
| 1 | **PostgreSQL + pgvector** | Single DB for relational + vector + FTS. Zero operational overhead. |
| 2 | **FastAPI + async** | Pipeline is I/O-bound (HTTP, LLM, DB). Python async is the right fit. |
| 3 | **Interface-based ABCs** | 7 extractors prove the pattern. New sources are copy-and-adapt. |
| 4 | **Angular → React pivot** | Modern stack, good DX, 6 pages in ~4,800 LOC. Clean break. |
| 5 | **Design-first workflow** | ~75 design + plan docs. Every feature is designed before coded. |
| 6 | **CI/CD quality gates** | ruff + pyright + bandit + pytest 92% + auto-deploy to Coolify. |
| 7 | **Kimi/Moonshot LLM** | Cheap, OpenAI-compatible. `openai_base_url` makes switching trivial. |
| 8 | **Pydantic Settings + structlog + Prometheus** | Typed config, structured logging, metrics from day 0. |

## Questionable Decisions (Review)

### HIGH IMPACT

**1. Crawl4AI as direct dependency**
- `crawl4ai~=0.8` brings Chromium into the Docker image (~500MB-1GB RAM at runtime)
- On a 4GB VPS (PostgreSQL ~200MB, API ~150MB, Nginx ~50MB), Crawl4AI alone consumes ~25% of total RAM
- Single Dockerfile means ALL containers pay the image size cost, even API which never uses it
- **Decision was deliberate** — wanted more extraction power — but the cost/benefit ratio is unfavorable for manually-configured URLs that are mostly static HTML blogs

**2. Monolithic pipeline.py (469 LOC)**
- One function `run_pipeline()` does 9 steps: extract → dedup → validate → classify → event_dedup → variant_collapse → score → store → briefing → notify → embed
- Hard to profile individual stages, test in isolation, or parallelize independent steps
- Inline variant collapse logic (lines 371-392) should be its own stage

**3. Single Dockerfile for API + Pipeline**
- Same image for `api`, `pipeline`, and `pipeline-cron` containers
- API doesn't need: crawl4ai, feedparser, python-telegram-bot, apscheduler
- Pipeline doesn't need: slowapi, fastapi (in one-shot mode)
- Result: bloated images, slower builds, unnecessary RAM consumption

### MEDIUM IMPACT

**4. In-memory refresh tokens**
- `_refresh_tokens: dict[str, float]` in `auth.py` — lost on every container restart
- Every deploy forces all users to re-login
- Simple fix: move to `users` table or dedicated `refresh_tokens` table

**5. python-jose (unmaintained)**
- Last release: 2022. No security patches since then
- PyJWT is the actively maintained standard, near drop-in replacement
- Security-critical dependency that should be current

### LOW IMPACT

**6. Flat Settings class (166 LOC, ~50 settings)**
- Every new feature adds more settings to one class
- 13 `*_list` properties doing the same `.split(",")` pattern
- Not urgent but increasingly hard to navigate

**7. APScheduler in-process singleton**
- Module-level `_circuit_breaker` state lost on restart
- Acceptable for single-instance VPS deployment, but fragile

---

## Proposed Improvements

### Tier 1 — Pipeline Performance (high impact)

#### 1.1 Separate Dockerfiles: API vs Pipeline

Two images: `Dockerfile.api` (lightweight, no crawl4ai/feedparser/telegram) and
`Dockerfile.pipeline` (full dependencies). API image drops from ~1.2GB to ~300MB.

#### 1.2 Replace Crawl4AI with httpx + readability

| Approach | Pro | Con |
|----------|-----|-----|
| A) Crawl4AI as separate service | Isolates RAM, runs only when needed | Another container to maintain |
| B) **httpx + readability (recommended)** | No Chromium, ~0 overhead, enough for static blogs | Can't scrape JS-rendered SPAs |
| C) Keep but lazy-load | No functionality change | Still bloats image, only saves runtime RAM |

**Recommendation**: Approach B. The `webscraper_urls` are manually configured, mostly static
HTML blogs/news sites. If JS rendering is needed later, add it as a separate optional service.

#### 1.3 Break pipeline.py into composable stages

```
src/pipeline/
  stages/
    extract.py      → extraction + per-source error handling
    classify.py     → LLM/keyword classify + event dedup + variant collapse
    score.py        → composite scoring
    store.py        → DB storage + briefing
    notify.py       → telegram + embeddings
  pipeline.py       → thin orchestrator that chains stages
```

Each stage independently testable, profilable, and potentially parallelizable.

### Tier 2 — Tech Debt (medium impact)

#### 2.1 Move refresh tokens to PostgreSQL

Add `refresh_token_hash` + `refresh_expires_at` columns to `users` table (or dedicated
`refresh_tokens` table). One Alembic migration, one change to `auth.py`.

#### 2.2 Replace python-jose with PyJWT

Drop-in replacement in `auth.py`. Same basic API (`jwt.encode`/`jwt.decode`).
Actively maintained, receives security patches.

#### 2.3 Multi-stage Dockerfile (if not doing 1.1)

At minimum, separate builder stage to reduce final image size.

### Tier 3 — Nice to Have (low impact)

#### 3.1 Split Settings into sub-configs

`PipelineSettings`, `AuthSettings`, `FeedSettings`, `ScraperSettings`. More navigable.

#### 3.2 Clean up dead code

Remove `web/` (Angular) if still present. Remove unused imports and dead branches.

#### 3.3 psycopg2-binary → psycopg3

Modern driver supporting both async and sync. Eliminates need for asyncpg + psycopg2-binary.

---

## Key Insight: Python Is Correct

The concern about "being all Python" is addressed: **Python is the right choice for this
project**. The bottleneck is not the language (I/O-bound work benefits from async, not from
Go/Rust). The bottleneck is:

1. **Heavy dependency** (Crawl4AI/Chromium) consuming VPS resources
2. **Monolithic structure** making it hard to optimize individual pipeline stages
3. **Single Docker image** forcing all services to carry all dependencies

Fixing these three issues with Python-native solutions (httpx, modular pipeline, split
Dockerfiles) will address the performance concerns without a language change.

---

*Generated from architecture retrospective session, 2026-03-02*
