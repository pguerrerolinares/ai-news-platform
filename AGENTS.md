# AGENTS.md — AI News Platform

> **Last updated**: 2026-03-01 | **Current milestone**: CI/CD Auto-Deploy | **Status**: Complete

## Project Overview

**AI News Platform** is a web-based AI news aggregation, classification, and search platform. It extracts news from multiple sources (HackerNews, arXiv, Reddit, RSS, GitHub Trending, HuggingFace), classifies them using LLM (Kimi/Moonshot), stores in PostgreSQL with pgvector embeddings, and serves via a FastAPI REST API + React frontend. Includes RAG-based Q&A chat.

**Evolved from**: `x-news-summarizer` (Telegram-only pipeline). This project adds a web UI, database, full-text search, RAG chat, and MCP integration.

**Key facts**:
- **Audience**: Semi-public (5-10 people), passwordless email OTP auth + WebAuthn passkeys + JWT (shared password fallback)
- **Development**: 100% by AI agents. Zero human coding.
- **Infrastructure**: Hetzner VPS (4GB RAM, ~5 EUR/month)
- **LLM**: Kimi/Moonshot API (OpenAI-compatible, cheapest option)
- **Tests**: 1015+ passed, 92% coverage

## Architecture

```
Docker Compose on Hetzner VPS
┌──────────────────────────────────────────────────────────┐
│                                                          │
│  ┌──────────┐  ┌──────────┐  ┌─────────────────────┐    │
│  │  Nginx   │  │ Pipeline │  │  PostgreSQL 16       │    │
│  │  (TLS +  │  │ (sched)  │──│  + pgvector          │    │
│  │  proxy + │  └──────────┘  │                      │    │
│  │  static) │  ┌──────────┐  │  Tables:             │    │
│  └────┬─────┘  │ FastAPI  │──│  - news_items        │    │
│       └────────│ (REST)   │  │  - daily_briefings   │    │
│                └──────────┘  │  - item_embeddings   │    │
│                              │  - users             │    │
│                              │  - otp_codes         │    │
│                              │  - webauthn_creds    │    │
│                              └─────────────────────┘    │
└──────────────────────────────────────────────────────────┘
```

### Data Flow

```
Sources -> Extract -> Dedup -> Classify (LLM) -> Variant Collapse -> Validate -> Store (PostgreSQL)
                                                                                       |
                                                                          FastAPI API <-+-> React UI
                                                                                       |
                                                                          Telegram     <-+
                                                                                       |
                                                                          Embed -> RAG Chat (SSE)

Feed Pipeline (query-time):
  Time-window filter (48h→72h→168h expansion) -> Live rescore (CompositeScorer.score_newsitem)
  -> Variant Collapse -> MMR Diversification -> Paginate
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
├── AGENTS.md / CLAUDE.md            # Agent guide / coding conventions
├── pyproject.toml                    # Dependencies + tool config
├── Dockerfile / docker-compose.yml / nginx.conf
├── alembic/                          # DB migrations (9 versions)
├── src/
│   ├── main.py                       # CLI entry point
│   ├── core/
│   │   ├── config.py                 # Pydantic Settings (all env vars)
│   │   ├── database.py               # Async SQLAlchemy engine + get_async_session()
│   │   ├── models.py                 # ORM: NewsItem, DailyBriefing, ItemEmbedding, User, OtpCode, RawExtraction, WebAuthnCredential
│   │   ├── logging.py                # structlog + correlation IDs
│   │   └── metrics.py                # Prometheus counters + histograms
│   ├── extractors/                   # 6 extractors (HN, arXiv, Reddit, RSS, GitHub, HF)
│   ├── classifiers/                  # Keyword + LLM classifiers, event dedup
│   ├── validators/                   # CredibilityValidator
│   ├── notifiers/                    # Telegram notifier + AlertService
│   ├── api/
│   │   ├── app.py                    # FastAPI app, middleware, lifespan
│   │   ├── auth.py                   # JWT + refresh tokens, require_auth, require_admin
│   │   ├── otp.py                    # OTP generation + Resend API
│   │   ├── schemas.py                # Pydantic response models
│   │   ├── webauthn.py                # WebAuthn challenge store
│   │   └── routes/                   # auth, otp, webauthn, items, briefings, search, chat, stats, sources
│   ├── feed/                           # Feed algorithm (query-time ranking)
│   │   ├── variant_collapse.py       # Dedup HF model variants (GGUF/GPTQ/AWQ)
│   │   ├── mmr_ranker.py             # MMR diversification (quality vs source diversity)
│   │   └── feed_builder.py           # Orchestrator: candidates→collapse→MMR→paginate
│   ├── pipeline/
│   │   ├── pipeline.py               # extract→dedup→classify→variant_collapse→validate→embed→store→notify
│   │   ├── composite_scorer.py       # Composite scoring: velocity + relevance + recency + topic
│   │   ├── scheduler.py              # APScheduler 3-tier (15m/1h window, 60m/3h window, daily/24h)
│   │   └── circuit_breaker.py        # Per-source failure tracking
│   ├── rag/                          # embeddings, retriever, chat (SSE streaming)
│   └── mcp/                          # MCP server + client
├── frontend/                         # React 19 (Vite + Shadcn UI + Tailwind CSS 4)
│   └── src/
│       ├── lib/                      # api.ts, auth.ts, webauthn.ts, constants.ts, types.ts
│       ├── hooks/                    # use-auth, use-theme, use-mobile
│       ├── components/               # layout, app-nav, news-card, featured-card, ui/
│       └── pages/                    # Login, Dashboard, Trending, Search, Chat, Settings
├── tests/                            # 1015+ unit + 35 E2E (Playwright)
├── scripts/                          # backup, health check, rescore_composite, rescore_all
└── docs/                             # architecture, ADRs, plans, runbooks, milestone-history
```

## Database Schema

### Tables
- **news_items**: id(UUID PK), title, summary, url, source, topic, relevance_score, dev_value_score, credibility_score, composite_score, priority, trending, published_at, created_at, content_hash(UNIQUE), url_hash, full_text, author, score, metadata(JSONB), language(VARCHAR DEFAULT 'en'), search_vector(tsvector)
  Indexes: published_at DESC, topic, source, content_hash, url_hash, FTS(title+summary+full_text), score, created_at, GIN(search_vector), partial(trending+date)
  Constraint: valid_topic CHECK (models, papers, agents, products, tools, open_source, regulation)
- **raw_extractions**: id(SERIAL PK), title, url, source, extracted_at, data(JSONB) — staging table
- **daily_briefings**: date(DATE PK), total_items, items_extracted, items_after_dedup, items_filtered, trending_count, duration_seconds, sources_used(JSONB), generated_at
- **item_embeddings**: item_id(UUID FK→news_items PK), model(TEXT PK), embedding(vector(1536)), created_at
  Indexes: HNSW(embedding vector_cosine_ops)
- **users**: id(UUID PK), email(UNIQUE), name, role(admin|reader), created_at, last_login_at
- **otp_codes**: id(SERIAL PK), email, code(6-digit), expires_at, used, created_at — purged daily by scheduler
- **webauthn_credentials**: id(UUID PK), user_id(UUID FK→users CASCADE), credential_id(BYTEA UNIQUE), public_key(BYTEA), sign_count, device_name, transports(JSONB), backed_up, last_used_at, created_at
  Indexes: user_id

## API Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | /health | No | Health check (200/503) |
| GET | /metrics | No | Prometheus (localhost only) |
| POST | /api/auth/token | No | Login (shared password) → JWT |
| POST | /api/auth/refresh | No | Refresh access token (rotation, 10/min) |
| POST | /api/auth/otp/request | No | Send OTP email (3/min) |
| POST | /api/auth/otp/verify | No | Verify OTP → JWT (5/min) |
| POST | /api/auth/webauthn/register/options | JWT | Generate passkey registration options (3/min) |
| POST | /api/auth/webauthn/register/verify | JWT | Verify and store new passkey (3/min) |
| POST | /api/auth/webauthn/login/options | No | Generate passkey login options (5/min) |
| POST | /api/auth/webauthn/login/verify | No | Verify passkey login → JWT (5/min) |
| GET | /api/auth/webauthn/credentials | JWT | List user's passkeys (10/min) |
| DELETE | /api/auth/webauthn/credentials/{id} | JWT | Delete a passkey (3/min) |
| GET | /api/auth/me | JWT | Current user info |
| GET | /api/items | JWT | List items (filters: source, topic, date, limit, offset) |
| GET | /api/items/count | JWT | Count matching items |
| GET | /api/items/latest | JWT | Latest items (sort=relevance uses FeedBuilder with time filter + live rescore + MMR, sort=recent is chronological with 48h window) |
| GET | /api/items/today | JWT | Today's items by effective date |
| GET | /api/items/by-date/{date} | JWT | Items for specific date |
| GET | /api/items/trending | JWT | Trending items |
| GET | /api/items/top | JWT | Top items by composite_score (normalized across sources) |
| GET | /api/items/{id}/similar | JWT | Similar via pgvector cosine |
| GET | /api/briefings/{date} | JWT | Daily briefing (resilient — synthesizes if no row) |
| GET | /api/briefings | JWT | Recent briefings |
| GET | /api/search | JWT | Full-text search (FTS, sort_by) |
| GET | /api/sources | JWT | Sources with item counts |
| GET | /api/stats/* | JWT | summary, by-source, by-topic, by-date, by-topic-date, by-source-date, trending-timeline, score-distribution |
| POST | /api/chat | JWT | RAG Q&A (SSE streaming, 10/min) |

Pagination: all paginated endpoints return `X-Total-Count` header.
Errors: `{"error": {"code": "UPPER_SNAKE_CASE", "message": "..."}}`.
Auth: access token (30min) + refresh token (7d with rotation). `Authorization: Bearer`.
Chat SSE: OpenAI-style events (`event: message/error/done`, `data: {id, type, content}`).

## Configuration

All config via env vars. See `.env.example` for full list.

Key defaults: `OPENAI_BASE_URL=api.moonshot.cn/v1`, `OPENAI_MODEL=kimi-latest`, `EMBEDDING_MODEL=text-embedding-3-small`, `ENABLED_SOURCES=hackernews,arxiv,reddit,rss,github,huggingface`
Feed algorithm: `FEED_MMR_LAMBDA=0.7` (0=diverse, 1=quality), `FEED_CANDIDATE_MULTIPLIER=5` (pool size = limit × N)
Composite scoring weights: `COMPOSITE_W_VELOCITY=0.35`, `COMPOSITE_W_RELEVANCE=0.30`, `COMPOSITE_W_RECENCY=0.20`, `COMPOSITE_W_TOPIC=0.15`
Velocity thresholds (p95-calibrated): `VELOCITY_THRESHOLD_GITHUB=1000.0` (stars/day), `VELOCITY_THRESHOLD_HACKERNEWS=0.15` (points/hour), `VELOCITY_THRESHOLD_HUGGINGFACE=1000000.0` (downloads)
Scheduler: HN+Reddit every 15min, RSS+GitHub+HF every 60min, arXiv daily 01:30 UTC. Circuit breaker: 3 failures → 1h cooldown.
Auth: Passwordless OTP via Resend API + WebAuthn passkeys (biometric). `ADMIN_EMAIL` auto-promotes to admin. OTP expires in 10min. Shared password fallback (role=reader). WebAuthn config: `WEBAUTHN_RP_ID`, `WEBAUTHN_RP_NAME`, `WEBAUTHN_ORIGIN`.

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
**Current coverage**: 92% (1015+ passed)
**E2E tests**: Playwright — login, dashboard, archive, search, chat, analytics, navigation flows

## CI/CD Pipeline

### CI (on push/PR to main) — `.github/workflows/ci.yml`
1. **Lint** (parallel): `ruff check .`, `ruff format --check .`, `bandit -r src/`
2. **Type Check** (parallel): `pyright .`
3. **Unit Tests** (needs lint+typecheck): `alembic upgrade head && alembic check`, `coverage run -m pytest tests/unit/ --fail-under=80`
4. **Integration** (needs test): `pytest tests/integration/`, `pytest tests/security/`
5. **Deploy** (needs integration, main push only): Coolify webhook API

### CD (automated via Coolify webhook)
- **Trigger**: CI stage 5 calls `POST /api/v1/deploy?uuid=<service-uuid>` on Coolify API
- **Gate**: `vars.COOLIFY_DEPLOY_ENABLED == 'true'` (kill switch in GitHub Variables)
- **Secrets**: `COOLIFY_WEBHOOK` (deploy URL), `COOLIFY_TOKEN` (API bearer token)
- **What Coolify does**: pulls latest code, builds Docker images, restarts containers
- **Compose file**: `docker-compose.coolify.yml` (Traefik labels, 4 services)
- **Rollback**: via Coolify UI deployment history, or revert commit on main

## Risk-Based Autonomy

| Track | Risk | Examples | Gate |
|-------|------|----------|------|
| **A** | Low | Docs, tests, config | CI passes -> auto-deploy |
| **B** | Medium | New extractor, API changes | CI + integration tests -> auto-deploy |
| **C** | High | DB migrations, security, pipeline core | CI + **human review** (PR required) |
