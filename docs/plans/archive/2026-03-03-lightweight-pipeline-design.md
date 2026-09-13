# Design: Lightweight Pipeline — Replace Crawl4AI, Split Stages, Split Dockerfiles

**Date:** 2026-03-03
**Status:** Approved
**Author:** Paul + Claude (brainstorming)

## Problem

The pipeline carries unnecessary weight on a 4GB VPS:

1. **Crawl4AI + Chromium** consumes ~500MB-1GB RAM for scraping static HTML blogs that don't need JS rendering
2. **Monolithic pipeline.py** (469 LOC) is hard to test, profile, or parallelize
3. **Single Dockerfile** forces the API container to carry pipeline-only dependencies (~1.2GB image)

## Goals

1. Drop Chromium dependency — replace Crawl4AI with httpx + readability-lxml (~0 RAM overhead)
2. Break pipeline.py into 5 composable, independently testable stage modules
3. Separate Docker images — lightweight API (~300MB) and full pipeline (~500MB)

## Constraints

- CX22 VPS: 2 vCPU, 4GB RAM
- Personal tool for 5-10 users
- Must not break existing pipeline behavior (extract -> dedup -> classify -> score -> store -> notify)

---

## Change 1: Replace Crawl4AI with httpx + readability-lxml

### Approach

The `WebScraperExtractor` two-phase architecture stays identical (discover links -> scrape articles).
Only the engine changes:

- **httpx** (already a dependency) for async HTTP fetching
- **readability-lxml** (new, ~200KB) for extracting article content from raw HTML
- **lxml** (transitive dep) for parsing `<a>` tags during link discovery

### Key Differences from Crawl4AI

| Aspect | Crawl4AI | httpx + readability |
|--------|----------|---------------------|
| Link discovery | `result.links["internal"]` | Parse `<a>` tags from HTML with lxml |
| Content extraction | Returns markdown | Returns clean HTML → strip to plain text |
| JS rendering | Full Chromium | None (not needed for configured URLs) |
| RAM overhead | ~500MB-1GB | ~0 |
| Output format | Markdown | Plain text (fine for classification + embeddings) |

### Dependencies

- **Remove:** `crawl4ai~=0.8` (and transitive Chromium/Playwright)
- **Add:** `readability-lxml~=0.8`
- **Keep:** `httpx~=0.28.0` (already present)

### Files Changed

| File | Action |
|------|--------|
| `src/extractors/webscraper.py` | Rewrite engine (httpx + readability), keep two-phase structure |
| `tests/unit/test_webscraper_extractor.py` | Update mocks (httpx instead of AsyncWebCrawler) |
| `pyproject.toml` | Remove crawl4ai, add readability-lxml |

---

## Change 2: Split pipeline.py into 5 composable stages

### Proposed Structure

```
src/pipeline/
  stages/
    __init__.py
    extract.py       # run_extraction() — extractor orchestration
    classify.py      # run_classification() — LLM/keyword + event dedup + variant collapse
    score.py         # run_scoring() — composite scoring
    store.py         # run_storage() — DB insert + briefing + embeddings
    notify.py        # run_notification() — Telegram alerts
  pipeline.py        # thin orchestrator (~100 LOC): chains stages
  dedup.py           # (unchanged)
  composite_scorer.py # (unchanged)
  validation.py      # (unchanged)
```

### Stage Interfaces

| Module | Function | Input | Output |
|--------|----------|-------|--------|
| `extract.py` | `run_extraction(sources, since_hours, alerts)` | source filter | `list[ExtractedItem]` |
| `classify.py` | `run_classification(items)` | validated items | `list[ClassifiedItem]` |
| `score.py` | `run_scoring(items)` | classified items | `list[ClassifiedItem]` (with composite scores) |
| `store.py` | `run_storage(session, items, stats)` | scored items + DB session | `int` (stored count) |
| `notify.py` | `run_notification(items, duration)` | final items | `None` |

### Design Decisions

- Dedup + pre-validation stays inline in the orchestrator (~20 lines, not worth a module)
- Credibility validation stays inline (single call)
- `composite_scorer.py`, `dedup.py`, `validation.py` are NOT moved
- Each stage function is independently importable and testable
- Existing pipeline tests become orchestrator tests; new per-stage tests added

### Orchestrator (~100 LOC)

```python
async def run_pipeline(session, sources=None, since_hours=None):
    all_items = await run_extraction(sources, since_hours, alerts)
    unique_items = deduplicate_items(all_items)
    valid_items = validate_items(unique_items)
    classified = await run_classification(valid_items)
    scored = run_scoring(classified)
    validated = await validator.validate(scored)
    stored = await run_storage(session, validated, stats)
    await run_notification(validated, duration)
```

---

## Change 3: Split Dockerfiles

### Two Images

**`Dockerfile.api`** (~300MB) — only API dependencies:
- fastapi, uvicorn, sqlalchemy, asyncpg, httpx, openai, structlog, prometheus
- python-jose, passlib, webauthn, slowapi, mcp
- Entrypoint: `docker-entrypoint.sh` (runs Alembic + uvicorn)

**`Dockerfile.pipeline`** (~500MB, down from ~1.2GB) — all dependencies:
- Everything in core + feedparser, readability-lxml, python-telegram-bot, apscheduler
- Entrypoint: `docker-entrypoint-pipeline.sh` (runs Alembic + scheduler)

### pyproject.toml — Optional Dependency Groups

```toml
[project]
dependencies = [
    # Core: fastapi, sqlalchemy, httpx, openai, structlog, prometheus, etc.
]

[project.optional-dependencies]
api = ["slowapi~=0.1.0", "webauthn~=2.5.0"]
pipeline = [
    "feedparser~=6.0.0", "readability-lxml~=0.8",
    "python-telegram-bot~=21.9", "apscheduler~=3.10",
]
```

- `Dockerfile.api`: `pip install ".[api]"`
- `Dockerfile.pipeline`: `pip install ".[pipeline]"`

### docker-compose.coolify.yml Changes

```yaml
api:
  build:
    context: .
    dockerfile: Dockerfile.api

pipeline-cron:
  build:
    context: .
    dockerfile: Dockerfile.pipeline
```

### New File: docker-entrypoint-pipeline.sh

- Runs Alembic migrations
- Starts scheduler: `python -m src.pipeline.scheduler`
- No uvicorn

---

## Risk Analysis

| Risk | Mitigation |
|------|------------|
| readability-lxml can't parse some sites well | Configured URLs are static blogs; test with actual target URLs before deploy |
| Import boundary violations (API importing pipeline-only deps) | Verify no cross-boundary imports; pipeline stages split helps |
| Pipeline behavior regression | Existing tests + new per-stage tests ensure same output |
| docker-compose change breaks Coolify deploy | Test locally with `docker compose up` before pushing |

## Execution Plan

Single branch, sequential commits:

1. **Replace Crawl4AI** — swap engine, update tests, change deps
2. **Split pipeline stages** — extract 5 modules, thin orchestrator, new tests
3. **Split Dockerfiles** — two Dockerfiles, optional dep groups, separate entrypoints, update compose

---

*Generated from brainstorming session, 2026-03-03*
