# Ideas Backlog — Future Features

> Ideas discussed during milestone planning. Not committed to any specific milestone.
> Add new ideas freely. Move to a milestone plan when ready to implement.

---

## Done

- [x] **Trending page/section** — Done (React Trending.tsx with `/api/items/trending` + `/api/items/top`)
- [x] **Theme simplification** — Done (React ThemeToggle, dark/light only, no "system" option)
- [x] ~~**Design fixes (2026-02-19 plan)**~~ — Obsolete (Angular-specific, React frontend is fresh)
- [x] ~~**Mobile bottom nav redesign**~~ — Obsolete (React uses top nav + Sheet drawer)
- [x] **Wire React to real API** — Done (2026-02-24). Login, JWT auth, API client, 4 pages wired, SSE chat
- [x] **Pipeline scheduling + live feeds** — Done (2026-02-25). APScheduler 3-tier jobs, pipeline sources filter, Reddit OAuth, RSS ETags, HF daily_papers, circuit breaker
- [x] **Multi-user auth** — Done (2026-02-25). Passwordless email OTP via Resend API, users + otp_codes tables, UserClaims + require_admin, React two-step login, OTP cleanup scheduler, shared password backward compatible

## In Progress

(nothing currently in progress)

## Frontend — Charts & Analytics

- [ ] **Analytics page**: Use stats endpoints (`by-topic-date`, `by-source-date`,
  `trending-timeline`, `score-distribution`) to build chart visualizations
  - Stacked area chart: topics over time
  - Stacked bar chart: sources over time
  - Sparkline: trending items over time
  - Histogram: score distribution
  - Leaderboard: top items by score

- [ ] **Mini charts in Dashboard**: Sparkline of items per day (last 7 days), topic breakdown
  pie chart for the current day

- [ ] **Chat with inline charts**: LLM returns structured data alongside text, frontend
  detects chart payloads and renders charts inline in the conversation

## Frontend — UX Improvements

- [x] **Pagination UI controls** — Done. Infinite scroll / pagination implemented in
  Dashboard and Trending pages.

- [ ] **"Related news" sidebar**: Use `/api/items/{id}/similar` to show related items
  when clicking on a news card

- [ ] **Source-based browse view**: Use `/api/sources` + `/api/items?source=X` to let
  users browse by source (HackerNews, arXiv, Reddit, etc.)

- [ ] **Archive page**: Historical briefings by date (was in Angular, not yet in React)

- [ ] **Auto-hide nav on scroll**: Top navigation hides when scrolling down,
  reappears when scrolling up. Saves mobile viewport space.

- [ ] **Error states & empty states** — Production-grade UI for:
  - API down / network error (retry button, offline indicator)
  - No results for search query (helpful message, suggestions)
  - Empty dashboard when pipeline hasn't run yet (first-run experience)
  - Chat errors (SSE connection lost, rate limit hit)

- [x] **Loading skeletons** — Done. Shadcn `Skeleton` used in Dashboard, Trending, Timeline,
  and calendar-heatmap components.

- [ ] **Mobile responsiveness audit** — Verify all 5 pages render well on 360px-428px
  viewports. Key areas: news card layout, chat input, search filters, nav Sheet
  drawer. Fix any overflow, truncation, or touch target issues.

## Frontend — Future Pages

- [x] **Timeline section** — Calendar heatmap + topic-grouped items per date. Browse by date
  with full history navigation. See `2026-03-02-timeline-section-design.md`. Done (2026-03-02).

- [ ] **Daily Briefing page** — Backend already generates LLM briefings (`/briefings/{date}`).
  Surface them in a dedicated page with date navigation. Low effort — data already exists.

- [ ] **Analytics Dashboard** — 8 stats endpoints are unused in the frontend. Visualize:
  topic trends over time, source breakdown, trending timeline, score distribution histogram.

- [ ] **Discovery / Similar** — "More like this" recommendations using pgvector similarity
  (`/items/{id}/similar`). Cross-topic connections, emerging patterns.

- [ ] **Settings page** — User preferences: default topic filter, preferred sources,
  notification preferences. Stored in localStorage initially, backend later.

## Architecture — Pipeline & Infrastructure (from 2026-03-02 retrospective)

### Tier 1 — High Impact (Pipeline Performance)

- [x] **Separate Dockerfiles: API vs Pipeline** — Done (2026-03-03). Two images: `Dockerfile.api`
  (core + api deps only) and `Dockerfile.pipeline` (core + pipeline deps). API image ~300MB.

- [x] **Replace Crawl4AI with httpx + readability** — Done (2026-03-03). Chromium removed,
  WebScraperExtractor now uses httpx + readability-lxml at ~0 overhead.

- [x] **Break pipeline.py into composable stages** — Done (2026-03-03). Five stage modules in
  `src/pipeline/stages/`: extract, classify, score, store, notify. Thin orchestrator in
  `pipeline.py`.

### Tier 1.5 — High Impact (Pipeline Efficiency, from 2026-03-17 analysis)

> Post-deploy analysis: seen filter + GitHub fixes reduced LLM calls ~80%, Tier 2
> pipeline from 100s→23.5s. These are the next wave of optimizations.

- [x] **Drop duplicate HNSW index** — Done (2026-03-17). Migration 012 drops
  `ix_item_embeddings_hnsw` (duplicate of ORM-declared `idx_embeddings_hnsw`).
  Saves 56MB RAM/disk.

- [x] **Increase HN poll interval 15min→30min** — Done (2026-03-17). Config change only.
  Halves Algolia requests with no coverage loss (seen filter catches repeats).

- [x] **Event dedup without LLM (fuzzy matching)** — Done (2026-03-17). Replaced LLM
  grouping with `difflib.SequenceMatcher` (stdlib, threshold 0.80). Union-find groups
  similar titles per topic. Saves 1-2 Kimi calls/cycle, zero new dependencies.

- [x] **Tune GitHub extractor** — Done (2026-03-17). min_stars 500→200, age 90→180 days,
  sort stars→updated. Remaining idea: add `GitHubTrendingExtractor` scraping
  `github.com/trending?since=daily` (HTML is server-rendered, no browserless needed).
  Captures what's actually popular TODAY. Hybrid: keep Search for new repos,
  add Trending for signal. Medium effort.

- [x] **Two-phase classification (keyword pre-filter → LLM)** — Done (2026-03-17).
  ≥3 keyword matches → auto-accept (no LLM). 0 matches → reject. 1-2 → LLM.
  Saves ~1 LLM batch/cycle. Auto-accepted items have no summary (trade-off).

- [x] **Reduce embedding dimensions 1536→512** — Done (2026-03-17). Migration 013 drops
  old embeddings, alters column to vector(512), recreates HNSW index. Embedding service
  passes dimensions=512 to API. ~3x storage savings, ~1% precision loss. Embeddings
  auto-regenerate on next pipeline runs (~7K items, ~$0.01).

### Tier 2 — Medium Impact (Tech Debt)

- [ ] **Move refresh tokens to PostgreSQL** — `_refresh_tokens` dict in `auth.py` is lost on
  every container restart, forcing all users to re-login. Add `refresh_token_hash` +
  `refresh_expires_at` to `users` table (or dedicated table). One migration, one code change.

- [ ] **Replace python-jose with PyJWT** — python-jose last release 2022, unmaintained.
  PyJWT is actively maintained, near drop-in replacement. Security-critical dependency.

- [x] ~~**Multi-stage Dockerfile**~~ — Obsolete (separate `Dockerfile.api` + `Dockerfile.pipeline`
  already exist, see Tier 1 Done above).

### Tier 3 — Low Impact (Nice to Have)

- [ ] **Split Settings into sub-configs** — `PipelineSettings`, `AuthSettings`, `FeedSettings`,
  `ScraperSettings`. 50 settings in one flat class with 13 `*_list` properties is unwieldy.

- [x] ~~**Clean up dead code**~~ — `web/` (Angular) already removed. Unused imports cleaned.

- [ ] **psycopg2-binary → psycopg3** — Modern driver supporting both async and sync in one
  package. Eliminates need for asyncpg + psycopg2-binary dual dependency.

## Backend — Improvements

- [x] **HF daily_papers: fetch abstract text** — Done (2026-03-17). Batch fetch abstracts
  from arXiv API (`export.arxiv.org/api/query?id_list=...`). Text field now contains
  title + abstract for richer classification and embeddings.

- [x] **Cross-source event grouping** — Done (2026-03-17). `seen_filter.py` now has
  two passes: URL hash (exact) + title similarity (SequenceMatcher ≥0.80 against recent
  DB titles). If HN and RSS bring the same news in different tiers, the second one is
  filtered out. No new dependencies.

- [x] **Content freshness indicator** — Done (2026-03-17). `GET /api/admin/freshness`
  returns per-source last_item_at, hours_ago, and status (ok/stale/dead).
  TODO: surface in frontend as "last updated" badges.

- [ ] **LLM fallback visibility** — When LLM API is down, classifier falls back to
  keyword-based. No user-visible indicator. Add a flag to news items or briefing
  metadata showing which classifier was used. Frontend could show a subtle badge
  "AI-classified" vs "auto-classified".

## Backend — Future Endpoints

- [ ] **Semantic search**: Expose vector similarity search as an API endpoint
  (currently only used internally by RAG chat). Different from full-text search —
  finds conceptually similar items even without exact keyword matches.

- [ ] **Item detail endpoint**: `GET /api/items/{id}` — currently no way to fetch a
  single item by ID (only lists). Needed for deep-linking and "related news" flow.

- [ ] **Chat history**: Store and retrieve past chat conversations per session/user.

- [ ] **Alerts/subscriptions**: Let users subscribe to topics or keywords and get
  notified (Telegram/email) when matching items appear.

## Infrastructure & Ops

- [x] **Migrate local DB to production** — Done (2026-02-27). Restored 6,374 news items,
  6,374 embeddings, and 21,526 raw extractions via `pg_dump -Fc` + `pg_restore --data-only`.
  See `docs/plans/2026-02-27-data-migration-design.md` for full procedure and lessons learned.

- [ ] **Reddit extractor** — Disabled via `ENABLED_SOURCES` env var (Reddit changed API terms,
  requires paid API key). Keep the code in place, re-enable when API access is resolved.

- [x] **WebScraper extractor** — Done (2026-03-17). Enabled with TechCrunch AI + Ars Technica AI
  (both server-rendered, readability works). GNE tested but unnecessary — readability extracts
  cleanly. The Verge/VentureBeat are SPAs (JS-required), skipped. ~80 articles/day potential,
  filtered by seen filter + keyword pre-filter.

- [ ] **Database retention policy** — `news_items` grows indefinitely (~100-200 items/day).
  After 6 months = ~30K rows + embeddings. Options:
  - Soft archive: move items older than N days to `news_items_archive` table (cheaper queries)
  - Hard delete: purge items older than N days (saves disk, simpler)
  - Tiered: keep 90 days hot, archive to cold storage
  Needs: Alembic migration for archive table (if soft), APScheduler cleanup job, config setting.

- [ ] **Health check page** — Extend `/health` to return per-component status:
  DB connectivity, scheduler running, last pipeline run per source, circuit breaker
  state, LLM API reachable. Frontend admin page or just JSON endpoint.

- [ ] **Backup verification** — `scripts/backup.sh` runs pg_dump to Backblaze B2 but
  no automated restore test. Add a periodic restore-and-verify job or at least
  a script that validates backup integrity.

## Observability & Monitoring (from 2026-03-17 production audit)

> Two layers: (A) project-specific audit queries for domain knowledge,
> (B) generic traceability using existing tooling. Telegram alerts to be removed.

### Layer A — Project-Specific Audit (custom, lives in ai-news-platform)

- [x] **Admin audit endpoint** (`GET /api/admin/audit`) — Done (2026-03-17). JSON endpoint returning:
  items/day/source (14 days), duplicate count, source gaps (0-item sources),
  pipeline health (runs, avg duration, error rate), seen filter stats, LLM
  fallback rate (keyword vs LLM classification). Replaces the manual
  SSH→docker→psql queries done during the 2026-03-17 audit. Admin-only.

- [x] **Pipeline run log table** — Done (2026-03-17). `PipelineRun` model + migration 014.
  Persists every run: started_at, duration, status, sources, items at each stage
  (extracted, dedup, seen_filtered, classified, validated, stored), error_message,
  correlation_id. Saved at success/empty/error paths in pipeline.py.
  TODO: add `GET /api/admin/pipeline-runs` endpoint + frontend page.

- [ ] **Frontend admin page** — Charts + stats consuming the audit and pipeline-runs
  endpoints. Items/day/source stacked bar, pipeline duration trend, error timeline,
  source health indicators. Admin-only route in React.

- [ ] **Remove Telegram alerts** — Delete `src/notifiers/alerts.py`, `AlertService`,
  and all call sites in pipeline.py, scheduler.py, stages/notify.py. Remove
  `telegram_bot_token`, `telegram_chat_id`, `telegram_alerts_enabled` config.
  Pipeline run log table + admin page replaces this entirely.

### Layer B — Generic Traceability (external tooling, reusable across projects)

- [ ] **Grafana Cloud free tier** — Ship structlog JSON + Prometheus metrics to
  Grafana Cloud (free: 50GB logs/month, 10K metrics series). Covers log search,
  dashboards, and alerting without local RAM cost. Already have structlog JSON
  output and `/metrics` Prometheus endpoint — just needs a shipper.

- [ ] **Grafana Alloy log shipper** (~30MB RAM) — Lightweight agent that reads
  Docker stdout logs and ships to Grafana Cloud Loki. Also scrapes `/metrics`
  and remote_writes to Grafana Cloud Prometheus. Single binary, replaces need
  for full Grafana+Loki+Prometheus stack locally.

- [ ] **Request logging middleware** (inspired by a11y-crawler-v2) — FastAPI
  middleware that persists every API request to a `request_logs` table: method,
  path, status, duration, IP, user-agent, request/response body (truncated,
  sanitized). Endpoint `GET /api/admin/logs` with filters. Useful for debugging
  API issues, rate limit analysis, and usage patterns. Can coexist with or be
  replaced by Grafana Cloud log search.

- [ ] **OpenTelemetry integration** (future, optional) — Replace custom
  correlation_id + Prometheus metrics with OTEL SDK. Auto-instruments FastAPI,
  httpx, SQLAlchemy. Sends traces to any OTEL-compatible backend (Grafana Tempo,
  Jaeger, Datadog). Higher effort but industry standard. Evaluate after Grafana
  Cloud is running — may not be needed if Loki+Prometheus suffice.

## Security

- [x] ~~**Multi-user auth**~~ — Done (see Done section above)

- [x] **Per-user rate limiting** — Done (2026-03-04). Rate limiting now JWT-based:
  guest tokens keyed by `jti`, authenticated users by `sub`, fallback to IP.
  See `src/api/ratelimit.py:get_rate_limit_key()`.

- [x] **Public access with guest tokens** — Done (2026-03-04). `POST /api/auth/guest`
  issues 24h read-only JWTs. Public endpoints use `require_auth_or_guest`. Chat
  requires full auth. See `docs/plans/2026-03-04-public-access-design.md`.

- [x] **Remove legacy shared-password auth** — Done (2026-03-04). `POST /api/auth/token`
  and `shared_password` config removed. Only OTP and passkey login remain.

---

*Last updated: 17 de marzo de 2026*
