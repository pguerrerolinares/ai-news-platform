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

- [ ] **Settings page** — User preferences: default topic filter, preferred sources,
  notification preferences. Stored in localStorage initially, backend later.

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

- [ ] **Per-user rate limiting** — Rate limiting is IP-based (`slowapi` + `get_remote_address`).
  If users share a network (VPN, office), they share limits. Switch to JWT-based
  rate limiting using `jti` or user identifier from token.

---

*Last updated: 27 de febrero de 2026*
