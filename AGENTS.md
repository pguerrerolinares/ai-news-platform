# AGENTS.md — AI News Platform

> **Last updated**: 2026-02-18 | **Current milestone**: 5 (Production Hardening) | **Status**: In progress

## Project Overview

**AI News Platform** is a web-based AI news aggregation, classification, and search platform. It extracts news from multiple sources (HackerNews, arXiv, Reddit, RSS, GitHub Trending, HuggingFace), classifies them using LLM (Kimi/Moonshot), stores in PostgreSQL with pgvector embeddings, and serves via a FastAPI REST API + Angular frontend. Includes RAG-based Q&A chat.

**Evolved from**: `x-news-summarizer` (Telegram-only pipeline). This project adds a web UI, database, full-text search, RAG chat, and MCP integration.

**Key facts**:
- **Audience**: Semi-public (5-10 people), shared password auth -> JWT
- **Development**: 100% by AI agents. Zero human coding.
- **Infrastructure**: Hetzner VPS (4GB RAM, ~5 EUR/month)
- **LLM**: Kimi/Moonshot API (OpenAI-compatible, cheapest option)
- **Tests**: 667 (633 unit + 34 E2E), 92% coverage

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
                                                    FastAPI API <-+-> Angular UI
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
│       └── 001_initial_schema.py  # news_items, daily_briefings, item_embeddings
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
│   │   ├── app.py                 # FastAPI app, /health (200/503), /metrics, middleware
│   │   ├── auth.py                # JWT creation/verification, require_auth dependency
│   │   ├── schemas.py             # Pydantic response models
│   │   └── routes/
│   │       ├── auth.py            # POST /api/auth/token (shared password -> JWT)
│   │       ├── items.py           # GET /api/items, /api/items/count, /api/items/today (JWT)
│   │       ├── briefings.py       # GET /api/briefings/{date}, /api/briefings (JWT)
│   │       ├── search.py          # GET /api/search (PostgreSQL FTS, JWT)
│   │       └── chat.py            # POST /api/chat (SSE streaming, RAG, rate-limited, JWT)
│   ├── pipeline/
│   │   ├── dedup.py               # 2-pass dedup (content_hash + url_hash)
│   │   └── pipeline.py            # Full flow: extract→dedup→classify→validate→embed→store→notify
│   ├── rag/
│   │   ├── embeddings.py          # EmbeddingService (OpenAI-compatible, batch embed, text prep)
│   │   ├── retriever.py           # Retriever (pgvector cosine similarity, topic filter)
│   │   └── chat.py                # ChatService (SSE streaming, context-aware, Kimi LLM)
│   └── mcp/
│       ├── server.py              # MCP server (news tools: search, trending, topics, briefing)
│       └── client.py              # MCP client (connect to server, call tools)
├── web/                           # Angular 21 app
│   ├── package.json               # Angular 21 dependencies
│   ├── angular.json               # Angular CLI config
│   ├── tsconfig.json              # TypeScript config
│   ├── tsconfig.app.json          # App-specific TS config
│   ├── src/
│   │   ├── main.ts                # Angular bootstrap
│   │   ├── index.html             # HTML shell
│   │   ├── styles.css             # Global styles
│   │   └── app/
│   │       ├── app.ts             # Root component (nav bar + router-outlet)
│   │       ├── app.config.ts      # provideRouter, provideHttpClient, withInterceptors
│   │       ├── app.routes.ts      # Route definitions (login, dashboard, archive, search, chat, analytics)
│   │       ├── models/
│   │       │   └── news-item.ts   # NewsItem + Briefing interfaces
│   │       ├── services/
│   │       │   ├── news.service.ts # HTTP service (items, briefings, search)
│   │       │   └── auth.service.ts # JWT auth (login, logout, token management)
│   │       ├── guards/
│   │       │   └── auth.guard.ts  # Route guard (redirects to login if unauthenticated)
│   │       ├── interceptors/
│   │       │   └── auth.interceptor.ts # Adds JWT to requests, handles 401/403
│   │       └── pages/
│   │           ├── login.ts       # Password login page
│   │           ├── dashboard.ts   # Today's news + topic distribution + stats
│   │           ├── archive.ts     # Historical briefings by date
│   │           ├── search.ts      # Full-text search with filters
│   │           ├── chat.ts        # RAG Q&A chat (SSE streaming, markdown)
│   │           └── analytics.ts   # Source/topic analytics dashboard
│   └── dist/                      # Built Angular (served by Nginx)
├── tests/                         # (every package has __init__.py)
│   ├── conftest.py                # Shared fixtures (DB, client, factories)
│   ├── factories.py               # Test data factories
│   ├── unit/                      # 633 tests
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
│   │   ├── test_api_routes.py     # Items + briefings API routes (22 tests)
│   │   ├── test_auth.py           # JWT auth + token endpoint (15 tests)
│   │   ├── test_search_api.py     # Search API with FTS (16 tests)
│   │   ├── test_chat_route.py     # POST /api/chat SSE streaming (10 tests)
│   │   ├── test_chat_service.py   # ChatService unit tests (12 tests)
│   │   ├── test_embeddings.py     # EmbeddingService unit tests (15 tests)
│   │   ├── test_retriever.py      # Retriever pgvector tests (10 tests)
│   │   ├── test_mcp_server.py     # MCP server tools (18 tests)
│   │   └── test_mcp_client.py     # MCP client (14 tests)
│   ├── e2e/                       # 34 Playwright tests
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
│   │   └── 2026-02-18-milestone-5-plan.md
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

**Indexes**: published_at DESC, topic, source, content_hash, url_hash, FTS (title + summary + full_text)

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
| POST | /api/auth/token | No | Login with shared password -> JWT | 2 | Done |
| GET | /api/items | JWT | List items (filters: source, topic, date, limit, offset) | 1 | Done |
| GET | /api/items/count | JWT | Count items matching filters | 1 | Done |
| GET | /api/items/today | JWT | Today's items sorted by score | 1 | Done |
| GET | /api/briefings/{date} | JWT | Daily briefing with all items | 1 | Done |
| GET | /api/briefings | JWT | List recent briefings | 1 | Done |
| GET | /api/search | JWT | Full-text search (PostgreSQL FTS, ts_rank) | 2 | Done |
| POST | /api/chat | JWT | RAG Q&A (SSE streaming, rate-limited 10/min) | 4 | Done |

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
- `CORS_ORIGINS`: `http://localhost:4200`

## Testing

```bash
# All tests
pytest tests/ -v

# Unit tests only
pytest tests/unit/ -v

# E2E tests (requires Angular build in web/dist/browser)
pytest tests/e2e/ -v

# With coverage
coverage run -m pytest tests/ && coverage report

# Fast subset (pre-push)
pytest tests/ -x --timeout=30 -q
```

**Coverage target**: 80% minimum (enforced in CI, unit tests only)
**Current coverage**: 92%
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

**Milestone 5 — Production Hardening**: In progress
- [x] Health endpoint returns 503 when DB unreachable
- [x] Nginx: SSE streaming (proxy_buffering off), security headers, metrics restriction
- [x] Docker entrypoint with auto-migration (alembic upgrade head)
- [x] Pipeline-cron service (sleep loop scheduler)
- [x] .env.example updated with M3/M4 variables
- [x] AGENTS.md updated to reflect M0-M5
- [ ] HTTPS configuration ready (needs domain)
- [ ] Deploy to VPS and verify

## Next Tasks

1. Deploy to VPS and configure HTTPS (requires domain)
2. Monitor pipeline-cron in production
3. Consider: user preferences, content enrichment, historical import

## Development History

| Date | Milestone | Changes |
|------|-----------|---------|
| 2026-02-17 | 0 | Project created. Foundation infrastructure. 98 tests. |
| 2026-02-17 | 1 | HN extractor, pipeline, dedup, API routes, Angular 21 UI. 159 tests. |
| 2026-02-17 | 2 | 4 extractors, LLM classifiers, credibility validator, Telegram notifier, JWT auth, search, Angular multi-page, Playwright E2E. 512 tests. |
| 2026-02-18 | 3 | GitHub + HuggingFace extractors, MCP server/client. 576 tests. |
| 2026-02-18 | 4 | RAG embeddings, retriever, chat service, SSE streaming, analytics page. 666 tests. |
| 2026-02-18 | 5 | Health 503, Nginx hardening, auto-migration, pipeline-cron, docs. 667 tests. |
