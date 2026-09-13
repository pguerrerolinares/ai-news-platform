# Milestone 2 — Full Pipeline

**Objective**: Feature parity with x-news-summarizer + web UI.

## Tasks

### Extractors
- [ ] arXiv extractor (async, httpx, BaseExtractor)
- [ ] Reddit extractor (async, httpx, BaseExtractor)
- [ ] RSS extractor (async, httpx + feedparser, BaseExtractor)

### Classification
- [ ] LLM Classifier (Kimi/Moonshot, batched, prompts + dev_value_score)
- [ ] Keyword fallback classifier
- [ ] LLM event deduplication

### Validation
- [ ] Credibility validator (SSRF protection, domain trust, Jaccard dedup)
- [ ] Noise filter

### Notification
- [ ] Telegram notifier (daily briefing, implements BaseNotifier)

### Pipeline
- [ ] Full pipeline: extract -> dedup -> classify -> validate -> store -> notify
- [ ] Prometheus metrics per step

### API
- [ ] Search endpoint (topic, date range, keyword FTS)
- [ ] Briefing stats endpoint
- [ ] JWT auth (shared password)

### Frontend
- [ ] Dashboard page (today's briefing)
- [ ] Archive page (calendar)
- [ ] Search page (filters)
- [ ] Login page

### E2E Tests (Playwright)
- [ ] Add `playwright` to dev dependencies in `pyproject.toml`
- [ ] Add `pytest-playwright` for pytest integration
- [ ] Create `tests/e2e/` directory with conftest (base URL, browser setup)
- [ ] E2E: Login flow (enter password -> redirect to dashboard)
- [ ] E2E: Dashboard shows today's news items (titles, source badges, scores)
- [ ] E2E: Navigate to Archive page, select a date, see items
- [ ] E2E: Search page — type query, apply filters, verify results
- [ ] E2E: Responsive check (mobile viewport shows correct layout)
- [ ] Add Playwright to CI workflow (install browsers, run e2e tests)

### Quality
- [ ] Unit tests for all new modules
- [ ] Data quality dashboard: items/day per source
- [ ] Update AGENTS.md, ADRs

## Verification

1. Pipeline runs daily with 4 sources, classification, validation, dedup
2. Telegram briefing matches x-news-summarizer content
3. Web: Dashboard + Archive + Search work with auth
4. Prometheus metrics at /metrics
5. Unit tests pass, CI green
6. Playwright E2E tests pass: login, dashboard, archive, search flows
