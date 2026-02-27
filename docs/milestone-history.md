# Milestone History Archive

> Archived from AGENTS.md on 2026-02-27 to reduce context window consumption. This file is NOT auto-loaded. Read it when you need historical context about completed milestones or design decisions.

## Current State

**Milestone 0 — Foundation**: Complete
- [x] Project structure + git init
- [x] pyproject.toml with dependencies
- [x] Dockerfile + docker-compose.yml
- [x] Core modules (config, database, models, logging, metrics)
- [x] Alembic initial migration
- [x] FastAPI app with /health and /metrics
- [x] Base interfaces (BaseExtractor, BaseClassifier, BaseValidator, BaseNotifier)
- [x] AlertService (Telegram)
- [x] GitHub Actions CI/CD
- [x] Scripts (backup, health check)
- [x] Pre-push hooks
- [x] AGENTS.md, CLAUDE.md, ADRs, runbooks
- [x] Tests (98 unit tests)

**Milestone 1 — First Vertical Slice**: Complete
- [x] HackerNews extractor (async httpx, Algolia API, BaseExtractor)
- [x] Hash deduplication service (2-pass: content_hash + url_hash)
- [x] Basic pipeline: extract -> dedup -> store in PostgreSQL
- [x] FastAPI endpoints: items (list, count, today), briefings (get, list)
- [x] Angular 21 app: single page showing today's items (signals, responsive)
- [x] Nginx config: serve Angular + proxy API
- [x] Data quality alert: Telegram if extractor returns 0 items
- [x] Tests (61 new tests, 159 total)

**Milestone 2 — Full Pipeline**: Complete
- [x] ArXiv, Reddit, RSS extractors
- [x] Keyword + LLM classifiers, event deduplication
- [x] Credibility validator
- [x] Telegram notifier (daily briefing)
- [x] Full pipeline: extract→dedup→classify→event-dedup→validate→filter→store→briefing→notify
- [x] JWT authentication + protected API routes
- [x] Full-text search endpoint (PostgreSQL FTS)
- [x] Angular: router, login, dashboard, archive, search pages
- [x] Playwright E2E tests
- [x] Tests (353 new, 512 total, 92% coverage)

**Milestone 3 — New Sources + MCP**: Complete
- [x] GitHub extractor (GitHub Search API, star filter, async httpx)
- [x] HuggingFace extractor (HF API, download filter, trending detection)
- [x] MCP server (news tools: search, trending, topics, briefing)
- [x] MCP client (connect, call tools)
- [x] Pipeline registration (6 extractors total)
- [x] Tests (64 new, 576 total)

**Milestone 4 — RAG + Q&A Chat**: Complete
- [x] EmbeddingService (OpenAI-compatible, batch embed, text preparation)
- [x] Retriever (pgvector cosine similarity, topic filter)
- [x] ChatService (SSE streaming, context-aware RAG, Kimi LLM)
- [x] POST /api/chat endpoint (rate-limited 10/min, JWT auth)
- [x] Pipeline embedding step (auto-embed new items)
- [x] Angular chat page (SSE streaming, markdown rendering)
- [x] Angular analytics page (source/topic dashboard)
- [x] E2E tests for chat + analytics
- [x] Tests (90 new, 666 total)

**Milestone 5 — Production Hardening**: Complete
- [x] Health endpoint returns 503 when DB unreachable
- [x] Nginx: SSE streaming (proxy_buffering off), security headers, metrics restriction
- [x] Docker entrypoint with auto-migration (alembic upgrade head)
- [x] Pipeline-cron service (sleep loop scheduler)
- [x] .env.example updated with M3/M4 variables
- [x] AGENTS.md updated to reflect M0-M5
- [ ] HTTPS configuration ready (needs domain)
- [ ] Deploy to VPS and verify

**Milestone 6 — Frontend Polish (CSS v1)**: Complete
- [x] Extract `NewsItemCard` reusable component
- [x] Add `GET /api/topics` endpoint for dynamic topic loading
- [x] Render markdown in chat with `marked` + `DOMPurify`
- [x] Topic filter chips on dashboard (toggleable, computed)
- [x] Widen layout from 800px to 1024px
- [x] Dark editorial design (Space Grotesk + Inter + JetBrains Mono)
- [x] E2E test for dashboard topic chip filtering
- [x] Tests: 35 E2E total

**Milestone 7 — Frontend Redesign (Angular Material M3)**: Complete
- [x] Install `@angular/material` 21, `@angular/cdk`, `@angular/animations`
- [x] Convert `styles.css` → `styles.scss` with M3 theming (`mat.$violet-palette`)
- [x] Dark/light theme via `mat.theme()` + `mat.theme-overrides()` for editorial palette
- [x] Navbar: `MatToolbar` + `mat-button` + `mat-icon-button` (Material Icons)
- [x] Login: `MatCard` + `MatFormField`/`MatInput` + `mat-flat-button` (inverted colors)
- [x] News cards: `MatCard` + `MatChip` (topic badge); source badges remain plain `<span>`s with `[data-source]`
- [x] Dashboard: `MatChipListbox` for topic filter + `MatProgressBar` for loading
- [x] Archive: `MatFormField` with native `<input type="date">` + `MatSelect` for topic
- [x] Search: `MatFormField` + native `<select matNativeControl>` for `#topic-select` (Playwright compat)
- [x] Analytics: `MatCard` wrappers for Highcharts
- [x] Chat: `MatChip` suggestion chips + `MatFormField`/`MatSelect` + `mat-flat-button`
- [x] Budget adjusted: 1MB warning / 1.5MB error (Material adds ~400kB)
- [x] All 35 E2E tests pass, 637 unit tests pass
- [x] Zero TS logic changes — signals, computed, subscriptions, handlers all preserved
- [x] Files NOT touched: `app.routes.ts`, services, guards, interceptors, models, tests

**Key design decisions (M7)**:
- Source badges = plain `<span>` (NOT MatChip) — 6 per-source colors + `[data-source]` E2E selectors
- Date inputs = native `type="date"` inside MatFormField — E2E needs `#archive-date[type="date"][max]`
- Search `#topic-select` = native `<select matNativeControl>` — Playwright `select_option()` requires native `<select>`
- Message bubbles = plain divs — no Material equivalent, E2E depends on `.message.user`/`.message.assistant`
- Stats bar = custom CSS inside MatCard — no Material stats grid component
- Inverted buttons = `mat-flat-button` with `.submit-btn` class overriding `--mdc-filled-button-container-color`

**Milestone 8 — Design Overhaul (Minimal Luxury)**: Complete
- [x] Design System First: 5 SCSS partials (`_tokens`, `_typography`, `_animations`, `_surfaces`, `_layout`)
- [x] New entry stylesheet: `web/src/styles/styles.scss` imports all partials + M3 theme
- [x] Font change: Plus Jakarta Sans (heading + body), JetBrains Mono (mono)
- [x] Color palette: Electric Indigo accent (#6366F1 dark / #4F46E5 light)
- [x] Token system: CSS custom properties for runtime dark/light switching
- [x] Route transitions: View Transitions API via `withViewTransitions()`
- [x] Navbar: Glass blur (`backdrop-filter`), animated underlines on hover/active
- [x] Login: Gradient mesh orbs, `scale-in` animation, larger card
- [x] News cards: Accent border glow on hover, animated underline titles, 3-line clamp
- [x] Dashboard: Accent-colored selected chips, staggered stat animations
- [x] Chat: Accent-colored user bubbles (both themes), 2x2 suggestion grid, fade-in messages
- [x] Analytics: Indigo accent charts, Plus Jakarta Sans in Highcharts
- [x] All 35 E2E tests pass — zero selector regressions
- [x] Zero TS logic changes — styles-only modifications across all components

**Key design decisions (M8)**:
- Design System First: Tokens as CSS custom properties, not SCSS variables (enables runtime theme switching)
- Single font family: Plus Jakarta Sans for both heading and body (was Space Grotesk + Inter)
- Accent color: Electric Indigo (#6366F1/#4F46E5) replacing Iris (#5b5bd6)
- User chat bubbles: `var(--accent)` + white text (same in both themes, replacing inverted black/white)
- Token renames: `--bg-surface-hover` → `--bg-hover`, `--text-tertiary` → `--text-muted`, `--accent-subtle` → `--accent-glow`
- New tokens: `--bg-elevated`, `--accent-dim`, `--border-accent`, `--shadow-sm/md/lg/glow`
- Stats bar animation: Staggered `fade-in` with SCSS `@for` loop delays
- View Transitions: `::view-transition-old/new(root)` for route fade+slide

**Milestone 14 — DB + Backend API Polish**: Complete
- [x] Alembic migration: 4 performance indexes (score, source+date, topic+date, created_at)
- [x] Pagination helper (`set_total_count_header`) + new schemas (stats, auth v2, errors)
- [x] Search pagination: `offset`, `sort_by` (relevance|date|score), `X-Total-Count`
- [x] Items pagination: `offset` on `/today`, `X-Total-Count` on all item endpoints
- [x] Briefings pagination: `limit`+`offset` on `/{date}`, `offset` on list, `X-Total-Count`
- [x] Aggregate stats endpoints: `/api/stats/summary`, `by-source`, `by-topic`, `by-date`
- [x] Error standardization: `APIError` class, `{"error": {"code", "message"}}` format
- [x] Refresh tokens: access (30min) + refresh (7d) with rotation, `POST /api/auth/refresh`
- [x] Pipeline pre-storage validation: reject items without title or URL
- [x] Pipeline robustness: embedding error metrics, chat SSE 30s timeout
- [x] Full lint + test pass: 749 unit tests green, ruff clean
- [x] AGENTS.md updated

**Key design decisions (M14)**:
- `X-Total-Count` header convention for all paginated endpoints (lightweight, frontend-friendly)
- `model_validate()` with `from_attributes=True` replaces manual ORM→schema conversion
- `from __future__ import annotations` removed from route files (breaks FastAPI runtime type resolution)
- Refresh token rotation with `jti` (UUID4) for uniqueness, in-memory hash set for revocation
- `APIError(HTTPException)` with status-to-code mapping for consistent error format
- Pre-storage validation before classification (fail fast, not silently dropped)

**Milestone 15 — API Contract Polish**: Complete
- [x] Chat SSE: OpenAI-style events (`event: message/error/done`) with message ID correlation
- [x] Chat SSE: structured JSON payloads (`type: token/sources`, `error: {code, message}`)
- [x] Frontend auth: `TokenResponseV2` support (refresh_token, expires_in, expiry tracking)
- [x] Frontend auth: `refreshToken()` method with `firstValueFrom`, `storeTokens()`, `isAuthenticated()` expiry check
- [x] Auth interceptor: auto-refresh on 401, retry original request, skip for `/api/auth/*`
- [x] Chat page: 401 retry with token refresh (raw fetch bypass)
- [x] Chat frontend: OpenAI-style SSE parser (`event:` + `data:` pairs)
- [x] News service: `PaginatedResponse<T>` pattern, `observe: 'response'`, `X-Total-Count` header
- [x] News service: `offset`, `sort_by` params, 4 stats methods
- [x] Models: `PaginatedResponse<T>`, `StatsSummary`, `StatsGroup`, `StatsDate` interfaces
- [x] Pages updated: dashboard, search, analytics use `PaginatedResponse`
- [x] Schema cleanup: deleted dead `TokenResponse`, added `CountResponse`, moved `ChatRequest` to schemas.py
- [x] OpenAPI: `responses={401: ErrorWrapper}` on all protected endpoints, 404 on briefings `/{date}`
- [x] Full verification: 756 unit tests, ruff clean, Angular build green

**Key design decisions (M15)**:
- Chat SSE follows OpenAI convention: `event: <type>` + `data: <json>` (not raw `data:` lines)
- Message ID (`msg_<uuid4.hex[:12]>`) shared across all events in a stream for correlation
- Frontend `PaginatedResponse<T>` reads `X-Total-Count` via `observe: 'response'` + `res.headers.get()`
- Auth interceptor wraps `refreshToken()` Promise in `from()` for RxJS compatibility
- Chat uses raw `fetch()` for SSE (Angular HttpClient doesn't support streaming), so 401 retry is manual
- `ChatRequest` moved to `schemas.py` for consistency (all Pydantic models in one file)

**Milestone 16 — API Endpoint Expansion**: Complete
- [x] New Pydantic schemas for M16 endpoints (SourceCount, ItemsByDate, SimilarItem, StatsTopicDate, StatsSourceDate, StatsTrendingTimeline, ScoreDistribution)
- [x] GET /api/items/by-date/{date} — items for a specific date without briefing dependency
- [x] GET /api/items/trending — dedicated trending items endpoint
- [x] GET /api/items/top — top items by score
- [x] GET /api/items/{id}/similar — similar items via pgvector cosine distance
- [x] GET /api/sources — active sources list with item counts
- [x] GET /api/stats/by-topic-date — item count grouped by topic and date
- [x] GET /api/stats/by-source-date — item count grouped by source and date
- [x] GET /api/stats/trending-timeline — trending item count by date
- [x] GET /api/stats/score-distribution — score distribution histogram
- [x] GET /api/briefings/{date} (modified) — resilient, synthesizes response when no DailyBriefing exists
- [x] Unit tests: test_schemas.py + test_sources_api.py
- [x] Full verification: 767 unit tests green, ruff clean, pyright clean
- [x] AGENTS.md updated

**Key design decisions (M16)**:
- `/api/items/by-date/{date}` queries news_items directly (no briefing dependency) — more resilient
- `/api/items/{id}/similar` uses pgvector cosine distance (`<=>`) on item_embeddings; returns 404 if item has no embedding
- `/api/briefings/{date}` now synthesizes a response from news_items when no DailyBriefing row exists
- Score distribution uses fixed buckets (0.0-0.2, 0.2-0.4, ..., 0.8-1.0) for chart-ready output
- All new endpoints require JWT auth, follow existing pagination + error conventions
- `sources.py` added as a separate route module (SRP) rather than extending items.py

**Pipeline Scheduling + Live Feeds**: Complete
- [x] APScheduler AsyncIOScheduler in FastAPI lifespan (3-tier jobs)
- [x] Pipeline refactor: `run_pipeline(session, sources=None)` for per-tier runs
- [x] Reddit OAuth client_credentials flow with fallback to unauthenticated
- [x] RSS ETags (If-None-Match / If-Modified-Since, 304 skip)
- [x] HuggingFace daily_papers endpoint integration
- [x] Circuit breaker: 3 consecutive failures → 1h cooldown per source
- [x] Scheduler config settings (per-source intervals, Reddit OAuth creds)
- [x] `get_async_session()` standalone context manager for scheduler jobs
- [x] Tests: 61 new (828 unit total), all green

**Scheduling tiers**:

| Tier | Interval | Sources | Job |
|------|----------|---------|-----|
| 1 | Every 15 min | HackerNews, Reddit | `run_scheduled_pipeline(["hackernews", "reddit"])` |
| 2 | Every 60 min | RSS, GitHub, HuggingFace | `run_scheduled_pipeline(["rss", "github", "huggingface"])` |
| 3 | Daily 01:30 UTC | arXiv | `run_scheduled_pipeline(["arxiv"])` |

**Key design decisions (Pipeline Scheduling)**:
- APScheduler runs in-process (no external broker) — suitable for single-instance VPS
- Pipeline `sources` filter is backward compatible: `None` runs all enabled sources
- Reddit OAuth uses httpx (no asyncpraw dependency), caches token in memory, refreshes on expiry
- RSS ETags stored in per-instance dict, resets on restart (first poll always fetches)
- HF daily_papers shares `seen_urls` set with trending models to avoid duplicates
- Circuit breaker uses `time.monotonic()` for cooldown tracking, auto-resets after cooldown
- Docker `pipeline-cron` service kept but deprecated (scheduler runs in API process)

## Frontend Migration

The Angular 21 frontend (`web/`) was replaced by a React 19 frontend (`frontend/`) in Feb 2026.
The Angular code is preserved on disk but removed from git tracking (see `.gitignore`).

**React frontend stack**: Vite 7, React 19, TypeScript, Tailwind CSS 4, Shadcn UI, Motion (Framer Motion), React Router 7.

**Key features**:
- 5 pages: Login, Latest (dashboard), Trending, Buscar (search), Chat
- All pages wired to real FastAPI backend (no mock data)
- JWT auth with auto-refresh on 401, protected routes via RequireAuth
- Chat uses SSE streaming (POST /api/chat) with token-by-token rendering
- Dark/light theme with circular reveal animation (View Transitions API + flushSync)
- Page transitions (AnimatePresence fade + slide)
- Staggered card grids, chat message animations, card hover/tap micro-interactions
- Nav active indicator with Motion layoutId spring animation
- All animations respect `prefers-reduced-motion`
- ~165 kB gzip bundle

**Multi-User Auth (Passwordless Email OTP)**: Complete
- [x] Auth config settings: ADMIN_EMAIL, RESEND_API_KEY, OTP_FROM_EMAIL, OTP_EXPIRE_MINUTES
- [x] Alembic migration 005: users + otp_codes tables
- [x] User + OtpCode ORM models with check constraints and indexes
- [x] OTP service: generate 6-digit codes (secrets.randbelow), send via Resend API (httpx)
- [x] Auth refactor: UserClaims dataclass, require_auth returns UserClaims, require_admin dependency
- [x] OTP endpoints: POST /api/auth/otp/request (3/min), POST /api/auth/otp/verify (5/min), GET /api/auth/me
- [x] Auto user registration on first OTP verify, ADMIN_EMAIL auto-promotes to admin
- [x] OTP cleanup scheduler job (daily at 02:00 UTC, purge expired codes)
- [x] Shared password backward compatibility: subject="legacy", role="reader"
- [x] React frontend: two-step Login (email → OTP code) + legacy password fallback
- [x] Tests: 44 new (872 unit total), all green

**Key design decisions (Multi-User Auth)**:
- Passwordless email OTP (no passwords to store/manage), Resend API for email delivery
- Open registration: any email auto-creates user on first OTP verify
- ADMIN_EMAIL env var auto-promotes matching user to admin role
- `hmac.compare_digest()` for timing-safe OTP comparison
- `from __future__ import annotations` removed from route files (breaks FastAPI + slowapi type resolution)
- Shared password login kept as fallback (subject="legacy", role="reader")
- OTP codes invalidated on verify or when new code requested for same email

## Next Tasks

1. Deploy to VPS and configure HTTPS (requires domain)
2. Monitor APScheduler pipeline in production
3. Analytics page with charts (stats endpoints ready)
4. Pagination UI controls (infinite scroll or pagination buttons)
5. Consider: user preferences, saved searches, email digest

## Development History

| Date | Milestone | Changes |
|------|-----------|---------|
| 2026-02-17 | 0 | Project created. Foundation infrastructure. 98 tests. |
| 2026-02-17 | 1 | HN extractor, pipeline, dedup, API routes, Angular 21 UI. 159 tests. |
| 2026-02-17 | 2 | 4 extractors, LLM classifiers, credibility validator, Telegram notifier, JWT auth, search, Angular multi-page, Playwright E2E. 512 tests. |
| 2026-02-18 | 3 | GitHub + HuggingFace extractors, MCP server/client. 576 tests. |
| 2026-02-18 | 4 | RAG embeddings, retriever, chat service, SSE streaming, analytics page. 666 tests. |
| 2026-02-18 | 5 | Health 503, Nginx hardening, auto-migration, pipeline-cron, docs. 667 tests. |
| 2026-02-18 | 6 | Frontend polish: NewsItemCard component, topic filters, markdown chat, dark editorial design. 35 E2E. |
| 2026-02-18 | 7 | Angular Material M3 migration: MatToolbar, MatCard, MatChipListbox, MatProgressBar, MatFormField, SCSS theming. 35 E2E green. |
| 2026-02-19 | 8 | Design overhaul: SCSS design system (5 partials), Plus Jakarta Sans, Electric Indigo accent, View Transitions, glass navbar, gradient login, accent chat bubbles, indigo charts. 35 E2E green. |
| 2026-02-21 | 14 | DB + Backend API Polish: 4 performance indexes, pagination on all endpoints (X-Total-Count), 4 aggregate stats endpoints, search sort_by, standardized errors (APIError), refresh tokens (30min/7d), pipeline validation, chat 30s timeout. 749 unit tests. |
| 2026-02-21 | 15 | API Contract Polish: Chat SSE OpenAI-style events (event types + message ID), frontend auth refresh tokens + interceptor auto-refresh, news service pagination + stats, schema cleanup, OpenAPI error docs. 756 unit tests. |
| 2026-02-22 | 16 | API Endpoint Expansion: 9 new endpoints + 1 modified, resilient briefings, chart-ready stats (by-topic-date, by-source-date, trending-timeline, score-distribution), pgvector similarity search, sources list. 767 unit tests. |
| 2026-02-25 | Sched | Pipeline Scheduling + Live Feeds: APScheduler 3-tier jobs, pipeline sources filter, Reddit OAuth, RSS ETags, HF daily_papers, circuit breaker. 828 unit tests. |
| 2026-02-25 | Auth | Multi-User Auth: Passwordless email OTP, users + otp_codes tables, UserClaims + require_admin, Resend API, React two-step login, OTP cleanup scheduler. 872 unit tests. |
