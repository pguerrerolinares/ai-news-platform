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

- [ ] **Pagination UI controls**: Infinite scroll or pagination buttons for:
  - Dashboard news list
  - Search results
  - Trending lists

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

- [ ] **Loading skeletons** — Replace blank loading states with animated skeleton
  placeholders for: news cards, trending list, search results, chat messages.
  Use Shadcn `Skeleton` component for consistency.

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

### Tier 2 — Medium Impact (Tech Debt)

- [ ] **Move refresh tokens to PostgreSQL** — `_refresh_tokens` dict in `auth.py` is lost on
  every container restart, forcing all users to re-login. Add `refresh_token_hash` +
  `refresh_expires_at` to `users` table (or dedicated table). One migration, one code change.

- [ ] **Replace python-jose with PyJWT** — python-jose last release 2022, unmaintained.
  PyJWT is actively maintained, near drop-in replacement. Security-critical dependency.

- [ ] **Multi-stage Dockerfile** (if not doing separate Dockerfiles) — At minimum, builder
  stage to reduce final image size.

### Tier 3 — Low Impact (Nice to Have)

- [ ] **Split Settings into sub-configs** — `PipelineSettings`, `AuthSettings`, `FeedSettings`,
  `ScraperSettings`. 50 settings in one flat class with 13 `*_list` properties is unwieldy.

- [ ] **Clean up dead code** — Remove `web/` (Angular) if still tracked. Remove unused imports.

- [ ] **psycopg2-binary → psycopg3** — Modern driver supporting both async and sync in one
  package. Eliminates need for asyncpg + psycopg2-binary dual dependency.

## Backend — Improvements

- [ ] **HF daily_papers: fetch abstract text** — Currently `text` field for daily papers is
  just the title (HF `/api/daily_papers` doesn't return abstracts). Could fetch abstract from
  arXiv API (`arxiv.org/abs/{id}`) as a second pass, giving the LLM classifier and embeddings
  richer content. Low priority: pipeline dedup may already have the arXiv version with abstract.

- [ ] **Cross-source event grouping** — Same news covered by multiple sources (e.g., an
  OpenAI announcement on HN + Reddit + RSS + arXiv) should be grouped as one "event"
  with multiple source links. Currently `event_dedup.py` groups within a single pipeline
  run using LLM, but doesn't detect cross-source duplicates from different tiers/times.
  Approaches: pgvector cosine similarity on embeddings (threshold ~0.92), or
  title similarity (Jaccard/fuzzy). Would improve dashboard by reducing noise.

- [ ] **Content freshness indicator** — Expose when the pipeline last ran successfully
  per source. New endpoint `GET /api/pipeline/status` returning last-run timestamps,
  items extracted, circuit breaker state. Frontend shows a "last updated X min ago"
  badge. Users know if data is stale.

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

- [ ] **WebScraper extractor** — Not in `ENABLED_SOURCES`. Two issues: (1) add `webscraper` to
  env var, (2) the 3 configured URLs (Anthropic/research, DeepMind, Meta AI blog) are JS-heavy
  SPAs that won't work with readability-lxml. Options: replace URLs with static-HTML blogs,
  or integrate the `browserless` container already running in production to render JS before
  extraction. Since these blogs are already covered by RSS, most value would come from scraping
  sites WITHOUT RSS feeds (TechCrunch AI, The Verge AI, VentureBeat AI).

- [ ] **Database retention policy** — `news_items` grows indefinitely (~100-200 items/day).
  After 6 months = ~30K rows + embeddings. Options:
  - Soft archive: move items older than N days to `news_items_archive` table (cheaper queries)
  - Hard delete: purge items older than N days (saves disk, simpler)
  - Tiered: keep 90 days hot, archive to cold storage
  Needs: Alembic migration for archive table (if soft), APScheduler cleanup job, config setting.

- [ ] **Monitoring dashboard** — Prometheus metrics exist (extractor duration, items stored,
  pipeline runs, API request latency) but no visualization. Options:
  - Grafana (full-featured, needs separate container, ~100MB RAM)
  - Simple `/api/admin/dashboard` endpoint returning JSON stats (lightweight, custom UI)
  - Prometheus built-in expression browser (zero extra infra, ugly)
  Constraint: 4GB VPS, already running PostgreSQL + API + Nginx.

- [ ] **Health check page** — Extend `/health` to return per-component status:
  DB connectivity, scheduler running, last pipeline run per source, circuit breaker
  state, LLM API reachable. Frontend admin page or just JSON endpoint.

- [ ] **Backup verification** — `scripts/backup.sh` runs pg_dump to Backblaze B2 but
  no automated restore test. Add a periodic restore-and-verify job or at least
  a script that validates backup integrity.

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

*Last updated: 4 de marzo de 2026*
