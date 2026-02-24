# AGENTS.md — AI News Platform

> **Last updated**: 2026-02-22 | **Current milestone**: 16 (API Endpoint Expansion) | **Status**: Complete

## Project Overview

**AI News Platform** is a web-based AI news aggregation, classification, and search platform. It extracts news from multiple sources (HackerNews, arXiv, Reddit, RSS, GitHub Trending, HuggingFace), classifies them using LLM (Kimi/Moonshot), stores in PostgreSQL with pgvector embeddings, and serves via a FastAPI REST API + React frontend. Includes RAG-based Q&A chat.

**Evolved from**: `x-news-summarizer` (Telegram-only pipeline). This project adds a web UI, database, full-text search, RAG chat, and MCP integration.

**Key facts**:
- **Audience**: Semi-public (5-10 people), shared password auth -> JWT
- **Development**: 100% by AI agents. Zero human coding.
- **Infrastructure**: Hetzner VPS (4GB RAM, ~5 EUR/month)
- **LLM**: Kimi/Moonshot API (OpenAI-compatible, cheapest option)
- **Tests**: 802 (767 unit + 35 E2E), 92% coverage

## Architecture

```
Docker Compose on Hetzner VPS
┌──────────────────────────────────────────────────────────┐
│                                                          │
│  ┌──────────┐  ┌──────────┐  ┌─────────────────────┐    │
│  │  Nginx   │  │ Pipeline │  │  PostgreSQL 16       │    │
│  │  (TLS +  │  │ (cron)   │──│  + pgvector          │    │
│  │  proxy + │  └──────────┘  │                      │    │
│  │  static) │  ┌──────────┐  │  Tables:             │    │
│  └────┬─────┘  │ FastAPI  │──│  - news_items        │    │
│       └────────│ (REST)   │  │  - daily_briefings   │    │
│                └──────────┘  │  - item_embeddings   │    │
│                              └─────────────────────┘    │
└──────────────────────────────────────────────────────────┘
```

### Data Flow

```
Sources -> Extract -> Dedup -> Classify (LLM) -> Validate -> Store (PostgreSQL)
                                                                 |
                                                    FastAPI API <-+-> React UI
                                                                 |
                                                    Telegram     <-+
                                                                 |
                                                    Embed -> RAG Chat (SSE)
```

## How to Run

### Development
```bash
# Setup
git clone <repo> && cd ai-news-platform
cp .env.example .env  # Fill in secrets
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
git config core.hooksPath .githooks

# Database (requires Docker for PostgreSQL)
docker compose up db -d
alembic upgrade head

# Run API
uvicorn src.api.app:app --reload --port 8000

# Run tests
pytest tests/ -v
```

### Production (Docker)
```bash
docker compose up -d                                          # Core services (db, api, nginx)
docker compose --profile pipeline run --rm pipeline           # One-off pipeline run
docker compose --profile cron up -d pipeline-cron             # Scheduled pipeline (daily)
```

### Pipeline (manual run)
```bash
python -m src.main
```

## File Map

```
ai-news-platform/
├── AGENTS.md                      # THIS FILE — agent guide (updated on every change)
├── CLAUDE.md                      # Coding conventions + 8 engineering principles
├── .env.example                   # Environment variable template
├── .gitignore
├── .dockerignore
├── pyproject.toml                 # Dependencies, tool config (ruff, pyright, pytest)
├── Dockerfile                     # Python 3.12-slim, non-root, healthcheck, auto-migration entrypoint
├── docker-entrypoint.sh           # alembic upgrade head + exec uvicorn (auto-migration)
├── docker-compose.yml             # PostgreSQL + API + Pipeline + Pipeline-Cron + Nginx + Certbot
├── nginx.conf                     # Reverse proxy + SSE streaming + security headers + rate limiting
├── alembic.ini                    # Alembic configuration
├── .githooks/
│   └── pre-push                   # ruff + pyright + pytest --fast
├── alembic/
│   ├── env.py                     # Async-compatible Alembic environment
│   ├── script.py.mako             # Migration template
│   └── versions/
│       ├── 001_initial_schema.py  # news_items, daily_briefings, item_embeddings
│       ├── 002_add_vector_column.py # pgvector embedding column
│       ├── 003_raw_extractions.py # raw_extractions staging table
│       └── 004_add_performance_indexes.py # score, source+date, topic+date, created_at
├── src/                           # (every package has __init__.py)
│   ├── main.py                    # CLI entry point for pipeline
│   ├── core/
│   │   ├── config.py              # Pydantic Settings (all env vars)
│   │   ├── database.py            # Async SQLAlchemy engine + session factory
│   │   ├── models.py              # ORM: NewsItem, DailyBriefing, ItemEmbedding
│   │   ├── logging.py             # structlog + correlation IDs
│   │   └── metrics.py             # Prometheus counters + histograms
│   ├── extractors/
│   │   ├── base.py                # BaseExtractor ABC + ExtractedItem dataclass
│   │   ├── hackernews.py          # HackerNewsExtractor (Algolia API, async httpx)
│   │   ├── arxiv.py               # ArxivExtractor (RSS feeds, feedparser, keyword filter)
│   │   ├── reddit.py              # RedditExtractor (JSON API, skip stickied, dedup by ID)
│   │   ├── rss.py                 # RSSExtractor (curated feeds, 48h lookback, HTML cleanup)
│   │   ├── github.py              # GitHubExtractor (GitHub Search API, async httpx, star filter)
│   │   └── huggingface.py         # HuggingFaceExtractor (HF API, download filter, trending)
│   ├── classifiers/
│   │   ├── base.py                # BaseClassifier ABC + ClassifiedItem dataclass
│   │   ├── keyword.py             # KeywordClassifier (7 topics, word-boundary regex, fallback)
│   │   ├── llm.py                 # LLMClassifier (Kimi/Moonshot, batched, Spanish prompts)
│   │   └── event_dedup.py         # Event deduplication (LLM grouping, trending detection)
│   ├── validators/
│   │   ├── base.py                # BaseValidator ABC
│   │   └── credibility.py         # CredibilityValidator (domain trust, SSRF-safe, Jaccard dedup)
│   ├── notifiers/
│   │   ├── base.py                # BaseNotifier ABC
│   │   ├── alerts.py              # AlertService (Telegram alerts for ops)
│   │   └── telegram.py            # TelegramNotifier (daily briefing, topic blocks, HTML)
│   ├── api/
│   │   ├── app.py                 # FastAPI app, /health (200/503), /metrics, middleware, error handlers
│   │   ├── auth.py                # JWT access+refresh tokens, require_auth, token rotation
│   │   ├── errors.py              # APIError class, standardized error handlers
│   │   ├── pagination.py          # set_total_count_header() helper
│   │   ├── schemas.py             # Pydantic response models (incl. stats, auth v2, errors)
│   │   └── routes/
│   │       ├── auth.py            # POST /api/auth/token + POST /api/auth/refresh
│   │       ├── items.py           # GET /api/items, /count, /today (paginated, X-Total-Count)
│   │       ├── briefings.py       # GET /api/briefings/{date}, /briefings (paginated, X-Total-Count)
│   │       ├── search.py          # GET /api/search (FTS, sort_by, offset, X-Total-Count)
│   │       ├── stats.py           # GET /api/stats/* (summary, by-source, by-topic, by-date)
│   │       ├── chat.py            # POST /api/chat (SSE streaming, RAG, rate-limited, JWT)
│   │       └── sources.py         # GET /api/sources — active sources list with item counts
│   ├── pipeline/
│   │   ├── dedup.py               # 2-pass dedup (content_hash + url_hash)
│   │   ├── validation.py          # Pre-storage validation (title, URL required)
│   │   └── pipeline.py            # Full flow: extract→dedup→classify→validate→embed→store→notify
│   ├── rag/
│   │   ├── embeddings.py          # EmbeddingService (OpenAI-compatible, batch embed, text prep)
│   │   ├── retriever.py           # Retriever (pgvector cosine similarity, topic filter)
│   │   └── chat.py                # ChatService (SSE streaming, context-aware, Kimi LLM)
│   └── mcp/
│       ├── server.py              # MCP server (news tools: search, trending, topics, briefing)
│       └── client.py              # MCP client (connect to server, call tools)
├── frontend/                      # React 19 app (Vite + Shadcn UI + Tailwind CSS 4)
│   ├── package.json               # React 19 + Vite 7 + Shadcn + Motion dependencies
│   ├── vite.config.ts             # Vite config
│   ├── tsconfig.json              # TypeScript config
│   ├── components.json            # Shadcn UI config
│   ├── src/
│   │   ├── main.tsx               # React bootstrap (ThemeProvider + BrowserRouter)
│   │   ├── App.tsx                # Route definitions (/, /trending, /buscar, /chat)
│   │   ├── index.css              # Tailwind + Shadcn theme tokens + View Transition CSS
│   │   ├── lib/
│   │   │   ├── constants.ts       # SOURCE_COLORS, TOPIC_LABELS, formatTime, safeUrl, mock data
│   │   │   ├── types.ts           # NewsItem interface
│   │   │   └── utils.ts           # cn() utility (clsx + tailwind-merge)
│   │   ├── hooks/
│   │   │   ├── use-theme.tsx      # ThemeProvider context + circular reveal (View Transitions API + flushSync)
│   │   │   ├── use-mobile.tsx     # useIsMobile() responsive hook
│   │   │   └── use-reduced-motion.ts # Re-exports Motion's useReducedMotion
│   │   ├── components/
│   │   │   ├── layout.tsx         # Root layout (AppNav + AnimatedOutlet)
│   │   │   ├── app-nav.tsx        # Nav bar (desktop: layoutId animated pill, mobile: Sheet drawer)
│   │   │   ├── theme-toggle.tsx   # Dark/light toggle (AnimatePresence icon morph)
│   │   │   ├── news-card.tsx      # News card (hover lift + tap scale)
│   │   │   ├── featured-card.tsx  # Featured card with gradient border
│   │   │   ├── animated-outlet.tsx # Page transitions (AnimatePresence fade + slide)
│   │   │   ├── animated-card-grid.tsx # Staggered card grid wrapper
│   │   │   └── ui/               # Shadcn UI primitives (badge, button, card, etc.)
│   │   └── pages/
│   │       ├── Dashboard.tsx      # Latest news (topic filter, featured card, staggered grid)
│   │       ├── Trending.tsx       # Trending + top scored items
│   │       ├── Buscar.tsx         # Full-text search with filters
│   │       └── Chat.tsx           # Mock AI chat (animated messages, typing dots)
│   └── dist/                      # Built React app (served by Nginx)
├── tests/                         # (every package has __init__.py)
│   ├── conftest.py                # Shared fixtures (DB, client, factories)
│   ├── factories.py               # Test data factories
│   ├── unit/                      # 767 tests
│   │   ├── test_config.py         # Settings defaults + env overrides (27 tests)
│   │   ├── test_config_embedding.py # Embedding config settings (5 tests)
│   │   ├── test_models.py         # ORM model structure (20 tests)
│   │   ├── test_logging.py        # structlog + correlation IDs (8 tests)
│   │   ├── test_extractors_base.py # ExtractedItem + BaseExtractor ABC (17 tests)
│   │   ├── test_hackernews_extractor.py # HN extractor with respx (13 tests)
│   │   ├── test_arxiv_extractor.py # ArXiv extractor with respx (22 tests)
│   │   ├── test_reddit_extractor.py # Reddit extractor with respx (15 tests)
│   │   ├── test_rss_extractor.py  # RSS extractor with respx (18 tests)
│   │   ├── test_github_extractor.py # GitHub extractor with respx (18 tests)
│   │   ├── test_huggingface_extractor.py # HuggingFace extractor with respx (14 tests)
│   │   ├── test_keyword_classifier.py # Keyword classifier (42 tests)
│   │   ├── test_llm_classifier.py # LLM classifier with mocked OpenAI (25 tests)
│   │   ├── test_event_dedup.py    # Event deduplication (22 tests)
│   │   ├── test_credibility_validator.py # Credibility validator (68 tests)
│   │   ├── test_telegram_notifier.py # Telegram notifier with respx (85 tests)
│   │   ├── test_alerts.py         # AlertService enabled/disabled (16 tests)
│   │   ├── test_dedup.py          # Dedup service (18 tests)
│   │   ├── test_pipeline.py       # Pipeline orchestration (32 tests)
│   │   ├── test_pipeline_embedding.py # Pipeline embedding step (5 tests)
│   │   ├── test_api.py            # /health (200+503) + /metrics endpoints (11 tests)
│   │   ├── test_api_routes.py     # Items + briefings API routes + pagination (30 tests)
│   │   ├── test_auth.py           # JWT auth + access/refresh tokens (20 tests)
│   │   ├── test_search_api.py     # Search API with FTS + pagination + sort (20 tests)
│   │   ├── test_stats_api.py      # Stats endpoints: summary, by-source/topic/date (11 tests)
│   │   ├── test_error_responses.py # Standardized error format (2 tests)
│   │   ├── test_pagination.py     # Pagination helper (2 tests)
│   │   ├── test_pipeline_validation.py # Pre-storage item validation (6 tests)
│   │   ├── test_chat_route.py     # POST /api/chat SSE streaming (10 tests)
│   │   ├── test_chat_service.py   # ChatService unit tests (15 tests)
│   │   ├── test_embeddings.py     # EmbeddingService unit tests (15 tests)
│   │   ├── test_retriever.py      # Retriever pgvector tests (10 tests)
│   │   ├── test_mcp_server.py     # MCP server tools (18 tests)
│   │   ├── test_mcp_client.py     # MCP client (14 tests)
│   │   ├── test_schemas.py        # Unit tests for M16 Pydantic schemas
│   │   └── test_sources_api.py    # Unit tests for GET /api/sources endpoint
│   ├── e2e/                       # 35 Playwright tests
│   │   ├── conftest.py            # Static server, API mocks, auth fixtures
│   │   ├── test_login.py          # Login flow (correct, incorrect, redirect)
│   │   ├── test_dashboard.py      # Dashboard with mocked data
│   │   ├── test_archive.py        # Archive date picker
│   │   ├── test_search.py         # Search with filters
│   │   ├── test_chat.py           # Chat SSE streaming
│   │   ├── test_analytics.py      # Analytics dashboard
│   │   └── test_navigation.py     # Nav bar, logout, protected routes
│   └── integration/               # (empty, for future DB integration tests)
├── scripts/
│   ├── backup.sh                  # pg_dump -> gzip -> Backblaze B2
│   ├── health_check.sh            # Post-deploy health verification
│   └── pipeline-scheduler.sh      # Sleep loop scheduler for pipeline-cron service
├── docs/
│   ├── architecture/
│   │   ├── overview.md            # Architecture details
│   │   └── decisions/             # ADRs
│   │       ├── 001-postgresql-over-sqlite.md
│   │       ├── 002-httpx-over-requests.md
│   │       ├── 003-structlog-over-stdlib.md
│   │       ├── 004-kimi-as-primary-llm.md
│   │       └── 005-risk-based-autonomy.md
│   ├── plans/
│   │   ├── milestone-0-foundation.md
│   │   ├── milestone-1-first-slice.md
│   │   ├── milestone-2-full-pipeline.md
│   │   ├── milestone-3-new-sources.md
│   │   ├── milestone-4-rag.md
│   │   ├── 2026-02-18-milestone-5-design.md
│   │   ├── 2026-02-18-milestone-5-plan.md
│   │   ├── 2026-02-21-milestone-14-design.md
│   │   ├── 2026-02-21-milestone-14-plan.md
│   │   ├── 2026-02-21-milestone-15-design.md
│   │   ├── 2026-02-21-milestone-15-plan.md
│   │   └── ideas-backlog.md               # Future feature ideas and backlog
│   └── runbooks/
│       ├── deployment.md
│       ├── add-new-extractor.md
│       ├── backup-restore.md
│       └── troubleshooting.md
└── .github/
    ├── PULL_REQUEST_TEMPLATE.md   # Track C PR template
    └── workflows/
        ├── ci.yml                 # ruff + pyright + pytest + bandit + alembic
        └── deploy.yml             # SSH deploy + health check + rollback
```

## Database Schema

### news_items
| Column | Type | Notes |
|--------|------|-------|
| id | UUID | PK, gen_random_uuid() |
| title | TEXT | NOT NULL |
| summary | TEXT | LLM Spanish summary |
| url | TEXT | Source URL |
| source | VARCHAR(50) | hackernews, arxiv, reddit, rss, github, huggingface |
| topic | VARCHAR(50) | CHECK constraint: modelos, papers, agentes, productos, herramientas, open_source, regulacion |
| relevance_score | FLOAT | 0.0-1.0 |
| dev_value_score | FLOAT | 0.0-1.0, utility for development |
| credibility_score | FLOAT | 0.0-1.0 |
| priority | INTEGER | 1 (highest) - 5 (lowest) |
| trending | BOOLEAN | Default false |
| published_at | TIMESTAMPTZ | Source publication date |
| created_at | TIMESTAMPTZ | Default NOW() |
| content_hash | TEXT | UNIQUE, dedup by title+url |
| url_hash | TEXT | Dedup by URL only |
| full_text | TEXT | Full article text if available |
| author | TEXT | |
| score | INTEGER | Engagement (upvotes, stars) |
| metadata | JSONB | Source-specific extra data |

**Indexes**: published_at DESC, topic, source, content_hash, url_hash, FTS (title + summary + full_text), score DESC NULLS LAST, (source, published_at DESC), (topic, published_at DESC), created_at DESC

### raw_extractions (staging)
| Column | Type | Notes |
|--------|------|-------|
| id | SERIAL | PK |
| title | TEXT | NOT NULL |
| url | TEXT | |
| source | VARCHAR(50) | |
| extracted_at | TIMESTAMPTZ | Default NOW() |
| data | JSONB | Raw extraction payload |

**Note**: Staging table for pipeline. Kept as-is per design decision (no cleanup needed).

### daily_briefings
| Column | Type | Notes |
|--------|------|-------|
| date | DATE | PK |
| total_items | INTEGER | |
| items_extracted | INTEGER | |
| items_after_dedup | INTEGER | |
| items_filtered | INTEGER | |
| trending_count | INTEGER | |
| duration_seconds | FLOAT | |
| sources_used | JSONB | |
| generated_at | TIMESTAMPTZ | |

### item_embeddings
| Column | Type | Notes |
|--------|------|-------|
| item_id | UUID | FK -> news_items.id, PK |
| model | TEXT | Embedding model name, PK |
| embedding | vector(1536) | pgvector (OpenAI text-embedding-3-small) |
| created_at | TIMESTAMPTZ | |

## API Endpoints

| Method | Path | Auth | Description | Milestone | Status |
|--------|------|------|-------------|-----------|--------|
| GET | /health | No | Health check + DB connectivity (200/503) | 0 | Done |
| GET | /metrics | No | Prometheus metrics (localhost only via Nginx) | 0 | Done |
| POST | /api/auth/token | No | Login with shared password -> access+refresh JWT | 2,14 | Done |
| POST | /api/auth/refresh | No | Refresh access token (rotation, rate-limited 10/min) | 14 | Done |
| GET | /api/items | JWT | List items (filters: source, topic, date, limit, offset) + X-Total-Count | 1,14 | Done |
| GET | /api/items/count | JWT | Count items matching filters | 1 | Done |
| GET | /api/items/today | JWT | Today's items sorted by score (offset) + X-Total-Count | 1,14 | Done |
| GET | /api/briefings/{date} | JWT | Daily briefing (limit, offset) + X-Total-Count | 1,14 | Done |
| GET | /api/briefings | JWT | List recent briefings (offset) | 1,14 | Done |
| GET | /api/search | JWT | Full-text search (FTS, sort_by, offset) + X-Total-Count | 2,14 | Done |
| GET | /api/stats/summary | JWT | Aggregate stats: total items, today, sources, topics, trending | 14 | Done |
| GET | /api/stats/by-source | JWT | Item count per source (GROUP BY) | 14 | Done |
| GET | /api/stats/by-topic | JWT | Item count per topic (GROUP BY) | 14 | Done |
| GET | /api/stats/by-date | JWT | Items per day (days param, max 365) | 14 | Done |
| POST | /api/chat | JWT | RAG Q&A (SSE streaming, OpenAI-style events, rate-limited 10/min) | 4,14,15 | Done |
| GET | /api/items/by-date/{date} | JWT | Items for a specific date (no briefing dependency) | 16 | Done |
| GET | /api/items/trending | JWT | Dedicated trending items endpoint | 16 | Done |
| GET | /api/items/top | JWT | Top items by score | 16 | Done |
| GET | /api/items/{id}/similar | JWT | Similar items via pgvector cosine distance | 16 | Done |
| GET | /api/sources | JWT | Active sources list with item counts | 16 | Done |
| GET | /api/stats/by-topic-date | JWT | Item count grouped by topic and date | 16 | Done |
| GET | /api/stats/by-source-date | JWT | Item count grouped by source and date | 16 | Done |
| GET | /api/stats/trending-timeline | JWT | Trending item count by date | 16 | Done |
| GET | /api/stats/score-distribution | JWT | Score distribution histogram | 16 | Done |
| GET | /api/briefings/{date} | JWT | (modified) Resilient — synthesizes response when no DailyBriefing exists | 1,14,16 | Done |

**Pagination convention**: All paginated endpoints return `X-Total-Count` header with total matching results.

**Error format**: All endpoints return `{"error": {"code": "UPPER_SNAKE_CASE", "message": "..."}}` on error. All protected endpoints document 401 errors in OpenAPI spec.

**Auth tokens**: Access token (30min) + refresh token (7d with rotation). Access token in `Authorization: Bearer`. Refresh via `POST /api/auth/refresh`.

**Chat SSE contract** (OpenAI-style events):
```
event: message\ndata: {"id":"msg_<hex12>","type":"token","content":"..."}\n\n
event: message\ndata: {"id":"msg_<hex12>","type":"sources","content":[...]}\n\n
event: error\ndata: {"id":"msg_<hex12>","error":{"code":"...","message":"..."}}\n\n
event: done\ndata: {"id":"msg_<hex12>"}
```

## Configuration

All config via environment variables. See `.env.example` for full list.

**Required for Docker Compose** (not validated by Python app):
- `POSTGRES_PASSWORD`: Database password (Docker Compose fails without it)

**Required for full functionality** (app starts without them but features are disabled):
- `OPENAI_API_KEY`: Kimi/Moonshot API key (needed for LLM classification)
- `TELEGRAM_BOT_TOKEN` + `TELEGRAM_CHAT_ID`: For Telegram alerts (alerts silently disabled if missing)
- `EMBEDDING_API_KEY`: OpenAI API key (needed for RAG chat embeddings)

**Key defaults**:
- `OPENAI_BASE_URL`: `https://api.moonshot.cn/v1`
- `OPENAI_MODEL`: `kimi-latest`
- `EMBEDDING_BASE_URL`: `https://api.openai.com/v1`
- `EMBEDDING_MODEL`: `text-embedding-3-small`
- `ENABLED_SOURCES`: `hackernews,arxiv,reddit,rss,github,huggingface`
- `MIN_RELEVANCE_SCORE`: `0.8`
- `LOG_FORMAT`: `json`
- `CORS_ORIGINS`: `http://localhost:5173`

## Testing

```bash
# All tests
pytest tests/ -v

# Unit tests only
pytest tests/unit/ -v

# E2E tests (requires React build in frontend/dist)
pytest tests/e2e/ -v

# With coverage
coverage run -m pytest tests/ && coverage report

# Fast subset (pre-push)
pytest tests/ -x --timeout=30 -q
```

**Coverage target**: 80% minimum (enforced in CI, unit tests only)
**Current coverage**: 92% (767 unit + 35 E2E = 802 total)
**E2E tests**: Playwright — login, dashboard, archive, search, chat, analytics, navigation flows

## CI/CD Pipeline

### CI (on push/PR to main)
1. `ruff check .` — Linting
2. `ruff format --check .` — Format check
3. `pyright .` — Type checking
4. `bandit -r src/` — Security scan
5. `alembic upgrade head && alembic check` — Migration validity
6. `coverage run -m pytest && coverage report --fail-under=80` — Tests + coverage

### CD (on CI success, main branch only)
1. SSH to VPS
2. `git pull origin main`
3. `docker compose build --no-cache api`
4. `docker compose up -d api`
5. Auto-migration via `docker-entrypoint.sh` (alembic upgrade head)
6. Health check (60s timeout)
7. On failure: automatic rollback to previous version
8. Telegram notification (success or failure)

## Risk-Based Autonomy

| Track | Risk | Examples | Gate |
|-------|------|----------|------|
| **A** | Low | Docs, tests, config | CI passes -> auto-deploy |
| **B** | Medium | New extractor, API changes | CI + integration tests -> auto-deploy |
| **C** | High | DB migrations, security, pipeline core | CI + **human review** (PR required) |

## Engineering Principles

1. **KISS**: Direct logic, no meta-programming
2. **YAGNI**: No features without concrete use case
3. **DRY + Rule of Three**: Extract after 3 stable repetitions
4. **SRP + ISP**: One responsibility per module, extend via interfaces
5. **Fail Fast**: Never silence errors
6. **Secure by Default**: Deny-by-default
7. **Determinism**: Reproducible for reliable CI
8. **Reversibility**: Every change easy to revert

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

## Frontend Migration

The Angular 21 frontend (`web/`) was replaced by a React 19 frontend (`frontend/`) in Feb 2026.
The Angular code is preserved on disk but removed from git tracking (see `.gitignore`).

**React frontend stack**: Vite 7, React 19, TypeScript, Tailwind CSS 4, Shadcn UI, Motion (Framer Motion), React Router 7.

**Key features**:
- 4 pages: Latest (dashboard), Trending, Buscar (search), Chat (mock)
- Dark/light theme with circular reveal animation (View Transitions API + flushSync)
- Page transitions (AnimatePresence fade + slide)
- Staggered card grids, chat message animations, card hover/tap micro-interactions
- Nav active indicator with Motion layoutId spring animation
- All animations respect `prefers-reduced-motion`
- ~167 kB gzip bundle

## Next Tasks

1. Deploy to VPS and configure HTTPS (requires domain)
2. Monitor pipeline-cron in production
3. Frontend: wire React app to real API endpoints (replace mock data)
4. Consider: user preferences, saved searches, email digest

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
