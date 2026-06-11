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

- [x] **Daily Briefing page** — Done (2026-06-10). `/briefing` route: pipeline-summary
  stats header + news items for the date, prev/next day nav, default today, graceful
  404 empty state. Reuses NewsCard/Timeline patterns. Verified end-to-end with
  Playwright + local backend. Final prod-data/mobile sign-off pending Paul.

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

- [x] **Efficiency sprint (2026-06-11)** — actioned F-1/F-4/F-5/F-8/F-11/F-12/F-16/F-17
  and removed F-3 (URL HEAD check) from `docs/plans/efficiency-findings-2026-06-10.md`;
  F-6 dismissed via EXPLAIN. Highlights: seen-filter loop off the event loop, single-query
  score distribution, concurrent LLM batches, search now uses the GIN-indexed `search_vector`
  (migration 017). See that doc's "Implementation status" table. Local commits, not yet deployed.

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

- [ ] **Move refresh tokens (+ WebAuthn challenges) to PostgreSQL** — `_refresh_tokens` dict in
  `auth.py` is lost on every container restart, forcing all users to re-login, and is per-worker
  under `api_workers: 2`. See the [HIGH] security finding (Track 5) for the full analysis and
  options (Postgres-with-TTL vs `api_workers: 1` stopgap).

- [x] **Replace python-jose with PyJWT** — Done (2026-06-09, commit 739dd84). `pyjwt[crypto]~=2.10`.

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

- [x] **LLM fallback visibility** — Done (2026-03-17). `classifier` field added to
  `ClassifiedItem` ("llm" or "keyword"). Stored in news_items metadata JSONB.
  Frontend can show badge based on `metadata.classifier`.

## Backend — Future Endpoints

- [x] **Semantic search**: Done (2026-06-10). `GET /api/search/semantic?q=...&limit=`
  embeds the query and ranks items by cosine similarity via the existing Retriever
  (no duplicated SQL). require_auth_or_guest, returns [] when embeddings unavailable.
  Implemented via parent-orchestrator → Sonnet executor child.

- [x] **Item detail endpoint**: `GET /api/items/{id}` — Done (2026-06-10). Single item by
  UUID, reuses NewsItemResponse, require_auth_or_guest, 404 on miss. Unlocks deep-linking +
  "related news" / discovery. Implemented via parent-orchestrator → executor child.

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

- [x] **Frontend admin page** — Done (2026-06-10). `/admin` route (public — the 3
  endpoints were relaxed to guest-readable): source-health strip, pipeline-runs table
  with status filter + compact funnel, stacked ingestion chart (recharts), totals/
  duplicates footer. Building it surfaced + fixed a latent audit-endpoint 500.
  Verified end-to-end with Playwright + local backend.

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

### Security Audit Findings (2026-06-09)

> Full backend security review. Verdict: **MEDIUM risk, 0 critical**. Code is security-aware
> (algorithm allowlist on every `jwt.decode`, `secrets.randbelow` + `hmac.compare_digest` for OTP,
> SSRF helper blocking private/reserved IPs, parameterized ORM throughout, 1MB body cap, startup
> guard against default JWT secret, no committed secrets). Findings below are verified against the
> code; ordered by severity. Bandit is already wired (`ci.yml:39` + `[tool.bandit]`) — not a gap.

- [x] **[HIGH] Upgrade `python-jose 3.3.0`** — Done (2026-06-09, commit 739dd84). Replaced with
  `pyjwt[crypto]~=2.10`. Near drop-in (`JWTError` → `jwt.PyJWTError`); behavior verified unchanged
  by the auth + JWT-manipulation suites. Closes CVE-2024-33663/33664.

- [ ] **[HIGH] Move refresh-token + WebAuthn-challenge stores out of per-worker memory** —
  `auth.py:22` (`_refresh_tokens`), `webauthn.py` (`_challenges`); runs under `api_workers: 2`.
  **This is the remaining "security sprint" item (Track 5), deferred 2026-06-09 for a dedicated
  session.** Two distinct faults:
  - **Multi-worker:** with 2 workers, refresh/rotation hits the wrong worker ~50% of the time;
    revocation is illusory (a rotated token stays valid on the other worker until JWT expiry, up
    to 7 days); WebAuthn login fails intermittently. Caps (100/200) evict valid tokens.
  - **Restart/deploy:** the in-memory store clears on every container restart. Because deploys run
    on each push via Coolify webhook, **every deploy logs all users out**.
  - **Options weighed:** (a) `api_workers: 1` stopgap — one config line, fixes the multi-worker
    fault + passkey flakiness instantly, but does NOT fix deploy-logout. (b) Postgres-backed store
    with TTL for both refresh tokens and WebAuthn challenges — migration + rewrite both stores +
    tests (~half day); fixes BOTH faults. Recommended given frequent deploys. Extends the Tier 2
    "Move refresh tokens to PostgreSQL" item to also cover the WebAuthn challenge store.

- [x] **[MEDIUM] SSRF: redirects not re-validated in webscraper/rss** — Done (2026-06-09, commit
  cb7b7c6). Added `ssrf.safe_get()` (validates every hop against `assert_safe_url`,
  `follow_redirects=False`); wired into RSS + WebScraper.

- [x] **[MEDIUM] No response-size cap on external fetches** — Done (2026-06-09, commit cb7b7c6).
  `safe_get()` streams the body with a 5 MB ceiling, raising past the cap.

- [x] **[MEDIUM] OTP: no per-code lockout** — Done (2026-06-09, commit 09f0e74). Added `attempts`
  column (migration 016); each wrong guess increments it and the code is burned after 5 failures.

- [x] **[MEDIUM] Unauthenticated `/api/sources` + `/api/topics`** — Done (2026-06-09, commit
  35f49d7). Both now require `require_auth_or_guest`; the frontend already sends a guest token.

- [ ] **[MEDIUM] Prompt injection from feed content into LLM** — `chat.py:58-78,126`. Retrieved
  titles/summaries are interpolated raw into the prompt; the "respond only on context" system prompt
  is a weak guardrail. No tool-calling, so impact is bounded to steering Spanish summaries shown to
  users / Telegram and possible system-prompt leak (no RCE). Fix: fence each item in
  `<news_item>…</news_item>` and instruct the model to treat it as untrusted data, not instructions.

- [ ] **[LOW] `/health` leaks DB exception string** — `app.py:222`. The 503 returns raw `str(exc)`
  (can reveal hostname/port/driver). Return a generic message; log detail server-side only.

- [ ] **[LOW] `/metrics` relies solely on nginx ACL** — `app.py:226`, `nginx.conf:84-87`. The app
  serves `/metrics` unauthenticated; the `allow 127.0.0.1; deny all` lives in nginx, but the prod
  stack is Coolify+Traefik and may not route through it. Confirm Traefik doesn't expose it, or bind
  to an internal port / require admin.

- [ ] **[LOW] No minimum length enforced for `jwt_secret`** — `config.py:36`, `app.py:111`. The guard
  blocks the literal default but accepts any other value, including a short/weak one. Add a
  `len >= 32` check in the production guard.

- [ ] **[LOW] `require_auth` accepts tokens with no `type` claim** — `auth.py:153`
  (`not in ("access", None)`). Legacy concession, not exploitable (refresh path rejects them).
  Tighten to `!= "access"` once legacy tokens age out.

---

*Last updated: 9 de junio de 2026*
