# Design: WebScraperExtractor with Crawl4AI

**Date:** 2026-03-02
**Status:** Approved
**Author:** Paul + Claude (brainstorming)

## Problem

The current pipeline has 6 extractors that rely on structured APIs (Algolia, Reddit OAuth,
GitHub API) and RSS/Atom feeds. This limits source coverage to platforms with APIs. Many valuable
AI content sources (research lab pages, company blogs, newsletters) lack APIs or RSS feeds.

Additionally, existing extractors only capture titles and short summaries. Full article content
would improve RAG/chat quality and LLM classification accuracy.

## Goals

1. **Primary:** Add new content sources that don't have APIs or RSS feeds
2. **Secondary:** Capture full article content (markdown) for better RAG and classification
3. **Constraint:** Fit within the CX22 VPS resource limits (2 vCPU, 4 GB RAM)

## Decision: Crawl4AI as In-Process Library

### Alternatives Considered

| Approach | Verdict |
|----------|---------|
| **A: Crawl4AI in-process** | **Selected.** Lightest option (~150 MB extra RAM), native async integration, Apache 2.0 license |
| B: Firecrawl sidecar | Rejected. 5 containers (~2-4 GB RAM) is infeasible on CX22. AGPL-3.0 license. |
| C: Crawl4AI Docker service | Rejected. Unnecessary isolation overhead. Can migrate to this later if needed. |

### Why Crawl4AI over Firecrawl

- **Resource footprint:** ~150 MB (1 Chromium instance) vs ~2-4 GB (5 containers)
- **Integration:** Native Python async (`await crawler.arun()`) vs HTTP REST calls
- **License:** Apache 2.0 vs AGPL-3.0
- **Equivalent output:** Both produce clean LLM-ready markdown

## Architecture

```
Pipeline extract stage (unchanged orchestration)
├── HackerNewsExtractor
├── RedditExtractor
├── ArXivExtractor
├── RSSExtractor
├── GitHubExtractor
├── HuggingFaceExtractor
└── WebScraperExtractor  ← NEW
    ├── reads target URLs from Settings (env var)
    ├── uses AsyncWebCrawler to fetch + render pages
    ├── two-phase: discover links → scrape new articles
    ├── maps content to ExtractedItem
    └── crawler lifecycle: create → scrape → close (per run)
```

### Registration

- Add `"webscraper"` to `VALID_SOURCES` in `src/core/models.py`
- Register `WebScraperExtractor` in `src/extractors/__init__.py`
- Add to `enabled_sources` default value in `src/core/config.py`

## Configuration

Simple URL list via environment variable (like `RSS_FEEDS`):

```python
# In src/core/config.py Settings
webscraper_urls: list[str] = []  # Empty by default, user adds URLs
webscraper_max_concurrent: int = 3
webscraper_page_timeout: int = 30  # seconds
```

Example:
```
WEBSCRAPER_URLS=https://www.anthropic.com/research,https://deepmind.google/research/publications/,https://ai.meta.com/blog/
WEBSCRAPER_MAX_CONCURRENT=3
WEBSCRAPER_PAGE_TIMEOUT=30
```

## Data Flow: Two-Phase Scraping

### Phase 1: Link Discovery

```
For each configured URL (index page):
  1. Crawl4AI renders the page with Chromium
  2. Extract all internal <a href="..."> links
  3. Filter: keep only links that look like articles (same domain, path depth > 1)
  4. Pre-check against DB: SELECT url_hash FROM news_items WHERE url_hash IN (...)
  5. Discard already-known URLs
  6. Result: list of new article URLs to scrape
```

### Phase 2: Article Scraping

```
For each new URL (max_items_per_source applies):
  1. Crawl4AI renders the full article page
  2. Extracts clean markdown (strips nav, footer, scripts)
  3. Maps to ExtractedItem:
     - title: from <h1> or <title>
     - source: "webscraper"
     - url: article URL
     - text: full markdown content
     - author: from domain/meta tags
     - published_at: from <time> element if available
     - score: 0 (no engagement metric)
     - metadata: {domain, scraper_source, word_count}
```

### Deduplication

- **Pre-scrape:** URL hash check against DB (optimization to avoid unnecessary scraping)
- **Post-scrape:** Pipeline's existing `content_hash` dedup handles any remaining duplicates

## Scheduling

**Tier 2** — every 60 minutes, alongside RSS/GitHub/HuggingFace:

```python
# In scheduler.py — Tier 2 updated to include webscraper
scheduler.add_job(
    run_scheduled_pipeline,
    IntervalTrigger(minutes=rss_poll_interval_minutes),
    id="tier2_rss_gh_hf_ws",
    kwargs={"sources": ["rss", "github", "huggingface", "webscraper"], "since_hours": 3}
)
```

Rationale: Blogs and research pages publish at most a few times per day. 60 min is fresh enough
without wasting resources.

## Resource Constraints

| Control | Value | Purpose |
|---------|-------|---------|
| Max concurrent pages | 3 (configurable) | Limit Chromium instances |
| Page timeout | 30 seconds | Don't hang on slow sites |
| Max items per source | 50 (existing) | Cap total articles per run |
| Browser lifecycle | Create → scrape → close | No persistent browser between runs |
| MemoryAdaptiveDispatcher | Built-in to Crawl4AI | Auto-reduces concurrency under memory pressure |

**Estimated peak impact:** ~400 MB extra RAM for ~2-3 minutes during scraping. 0 MB between runs.

## Error Handling

| Scenario | Behavior |
|----------|----------|
| Chromium fails to start | `extract()` raises → circuit breaker captures → Telegram alert |
| Page timeout (30s) | Skip URL, log warning, continue with remaining URLs |
| Site blocks scraping (403/captcha) | Skip, log, increment `extractor_errors_total{source="webscraper"}` |
| High memory pressure | `MemoryAdaptiveDispatcher` reduces concurrency automatically |
| 3 consecutive failures | Circuit breaker opens → webscraper disabled for 1 hour |
| Empty/useless HTML | Crawl4AI returns empty markdown → item discarded in validation (empty title) |

All covered by existing pipeline infrastructure. No new resilience code needed.

## Testing Strategy

- **Unit tests:** Mock `AsyncWebCrawler` to test URL filtering logic, ExtractedItem mapping,
  error handling paths
- **Integration test:** HTML fixture files (no real Chromium) to validate parsing
- **No E2E with Chromium in CI:** Too heavy for CI; tested manually

## New Dependency

```toml
# In pyproject.toml
crawl4ai = "~=0.8"
```

Justification: Enables web scraping of sites without APIs/RSS. Lightweight in-process library
with native async support. Apache 2.0 license. No alternative in stdlib.

## Files to Create/Modify

| File | Action |
|------|--------|
| `src/extractors/webscraper.py` | **Create** — WebScraperExtractor implementation |
| `src/extractors/__init__.py` | Modify — register WebScraperExtractor |
| `src/core/config.py` | Modify — add webscraper settings |
| `src/core/models.py` | Modify — add "webscraper" to VALID_SOURCES |
| `src/pipeline/scheduler.py` | Modify — add webscraper to Tier 2 |
| `tests/unit/test_webscraper.py` | **Create** — unit tests |
| `pyproject.toml` | Modify — add crawl4ai dependency |
| `AGENTS.md` | Modify — document new extractor |

## Risks

| Risk | Mitigation |
|------|------------|
| Crawl4AI has bus factor of ~1 (single maintainer) | Library is simple enough to fork if abandoned. Can migrate to Crawl4AI Docker service (Approach C) or Firecrawl later. |
| Chromium crashes take down FastAPI process | Circuit breaker + Chromium runs in subprocess (Playwright manages this). Investigate process isolation if it becomes an issue. |
| Sites change HTML structure | Crawl4AI's content extraction is generic (not selector-dependent). Degraded quality possible but not breakage. |
| CX22 RAM too tight | MemoryAdaptiveDispatcher + configurable concurrency. If insufficient, move to separate VPS or Approach C. |
