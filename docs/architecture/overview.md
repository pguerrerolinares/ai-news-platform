# Architecture Overview

> **Last updated**: 2026-06-13 | **Status**: Production (pguerrero.me)

## System Architecture

AI News Platform runs as a Docker Compose stack on a Hetzner VPS (4GB RAM, ~5 EUR/month).

```mermaid
graph TB
    subgraph Internet
        HN[HackerNews API]
        AX[arXiv API]
        RD[Reddit API]
        RS[RSS Feeds]
        GH[GitHub API]
        HF[HuggingFace API]
        WS[Web URLs]
        LLM[Kimi/Moonshot LLM]
        EMB[OpenAI Embeddings]
        RE[Resend Email API]
    end

    subgraph "Docker Compose — Hetzner VPS (4GB)"
        subgraph "Nginx (TLS + Proxy)"
            NG[Nginx 1.27]
            STATIC[Static Files<br/>frontend/dist]
        end

        subgraph "API Container"
            FA[FastAPI<br/>uvicorn 2 workers]
            AUTH[Auth<br/>JWT + OTP + WebAuthn]
            ROUTES[40 REST Endpoints]
            SCHED[APScheduler<br/>multi-tier jobs]
            RAG[RAG Chat<br/>SSE streaming]
        end

        subgraph "Pipeline Container"
            PIPE[Pipeline Orchestrator]
            EXT[9 Extractors]
            CLASS[LLM + Keyword<br/>Classifiers]
            SCORE[Composite Scorer<br/>+ MMR Ranker]
        end

        subgraph "PostgreSQL 16"
            DB[(news_items<br/>+ 7 tables)]
            VEC[(pgvector<br/>embeddings)]
            FTS[(tsvector<br/>full-text search)]
        end
    end

    subgraph "Browser"
        REACT[React 19 + Shadcn UI]
    end

    HN & AX & RD & RS & GH & HF & WS --> EXT
    EXT --> PIPE
    PIPE --> CLASS
    CLASS -.- LLM
    PIPE --> SCORE
    PIPE --> DB
    PIPE --> VEC
    PIPE -.- EMB

    REACT --> NG
    NG --> STATIC
    NG --> FA
    FA --> DB & VEC & FTS
    FA --> RAG
    RAG -.- EMB
    AUTH -.- RE

    SCHED -->|triggers| PIPE

    style DB fill:#336791,color:#fff
    style VEC fill:#336791,color:#fff
    style FTS fill:#336791,color:#fff
```

### Component Resource Budget

| Component | Technology | RAM Budget | Purpose |
|-----------|-----------|-----------|---------|
| Database | PostgreSQL 16 + pgvector | ~300MB | Storage, FTS, vector search |
| API | FastAPI (2 workers) | ~200MB | REST API, scheduler, RAG chat |
| Pipeline | Python (temporal) | ~300MB | News extraction + classification |
| Nginx | Nginx 1.27 | ~50MB | TLS, reverse proxy, static files |
| OS + Docker | Linux | ~400MB | Infrastructure |

## Data Flow — Pipeline

The pipeline runs on a multi-tier schedule (15min / 30min / 60min / 4h / daily) with per-source circuit breakers.

```mermaid
flowchart LR
    subgraph Extract
        E1[HackerNews<br/>every 30min<br/>since 6h]
        E1B[HackerNews Leading<br/>every 15min<br/>since 2h]
        E3[RSS<br/>every 60min]
        E4[GitHub Trending<br/>every 60min]
        E5[HuggingFace<br/>every 60min<br/>quant filter + papers]
        E6[WebScraper<br/>every 60min]
        E4S[GitHub Search<br/>every 4h<br/>pushed>=date, since 12h]
        E7[arXiv<br/>daily 01:30]
        E2[Reddit<br/>disabled by default]
    end

    subgraph Process
        DD[Hash Dedup<br/>content + URL]
        VL[Pre-validation<br/>title + URL required]
        CL[LLM Classify<br/>topic + relevance + summary]
        ED[Event Dedup<br/>LLM grouping]
        VC[Variant Collapse<br/>HF model dedup<br/>11 suffixes + size norm]
        CS[Composite Score<br/>velocity + relevance<br/>+ recency + topic]
        CR[Credibility<br/>Validation]
    end

    subgraph Store
        DB[(PostgreSQL)]
        EM[Generate<br/>Embeddings]
        BR[Daily<br/>Briefing]
    end

    E1 & E1B & E3 & E4 & E5 & E6 & E4S & E7 --> DD
    DD --> VL --> CL --> ED --> VC --> CS --> CR
    CR --> DB
    DB --> EM & BR
```

### Pipeline Schedule

| Tier | Sources | Interval | Extraction Window |
|------|---------|----------|-------------------|
| 1 | HackerNews | 30 min | 6 hours |
| 1b | HackerNews Leading | 15 min | 2 hours |
| 2 | RSS, GitHub (trending), HuggingFace, WebScraper | 60 min | 3 hours |
| 2b | GitHub Search | 4 hours (240 min) | 12 hours |
| 3 | arXiv | Daily 01:30 UTC | 24 hours |
| — | OTP cleanup | Daily 02:00 UTC | — |

Reddit is registered but **disabled by default** (not scheduled; `reddit_poll_interval_minutes=15` is defined but unused).

Circuit breaker: 3 consecutive failures → 1 hour cooldown per source.

## Data Flow — API Request

```mermaid
flowchart LR
    Browser[React App] -->|HTTPS| Nginx
    Nginx -->|proxy_pass| FastAPI

    subgraph FastAPI
        MW[Middleware<br/>CORS + Security Headers<br/>+ Body Limit + Metrics]
        AUTH[JWT Auth<br/>require_auth / require_auth_or_guest]
        ROUTE[Route Handler]
    end

    FastAPI -->|query| DB[(PostgreSQL)]

    subgraph "Feed Algorithm (/items/latest)"
        TW[Time Window<br/>48h → 72h → 168h]
        RS[Live Rescore<br/>CompositeScorer]
        VC2[Variant Collapse]
        MMR[MMR Diversification<br/>λ=0.7]
        PAG[Paginate]
    end

    ROUTE --> TW --> RS --> VC2 --> MMR --> PAG
    PAG -->|JSON + X-Total-Count| Browser

    subgraph "RAG Chat (/chat)"
        RET[Vector Retriever<br/>pgvector cosine]
        CTX[Build Context<br/>top-k items]
        LLM[LLM Generate<br/>streaming]
        SSE[SSE Response]
    end

    ROUTE --> RET --> CTX --> LLM --> SSE
    SSE -->|event stream| Browser
```

## Interface Architecture

Every major component is defined as an ABC. New implementations extend the system
without modifying existing code (Open/Closed Principle).

```mermaid
classDiagram
    class BaseExtractor {
        <<abstract>>
        +source_name: str
        +extract(since_hours) list~ExtractedItem~
    }
    class BaseClassifier {
        <<abstract>>
        +classify(items) list~ClassifiedItem~
    }
    class BaseValidator {
        <<abstract>>
        +validate(items) list~ClassifiedItem~
    }

    BaseExtractor <|-- HackerNewsExtractor
    BaseExtractor <|-- HackerNewsLeadingExtractor
    BaseExtractor <|-- ArxivExtractor
    BaseExtractor <|-- RedditExtractor
    BaseExtractor <|-- RSSExtractor
    BaseExtractor <|-- GitHubTrendingExtractor
    BaseExtractor <|-- GitHubExtractor
    BaseExtractor <|-- HuggingFaceExtractor
    BaseExtractor <|-- WebScraperExtractor

    BaseClassifier <|-- LLMClassifier
    BaseClassifier <|-- KeywordClassifier

    BaseValidator <|-- CredibilityValidator
```

## Authentication Flow

Two access tiers: guest tokens for public read-only access, and full auth (OTP + WebAuthn) for protected features.

```mermaid
sequenceDiagram
    participant U as User
    participant F as Frontend
    participant A as API
    participant R as Resend
    participant DB as PostgreSQL

    Note over U,DB: Guest Access (automatic)
    F->>A: POST /auth/guest
    A-->>F: access_token (role=guest, 24h TTL)
    Note over F: Read-only access to items, search, stats

    Note over U,DB: Method 1 — Email OTP (primary)
    U->>F: Enter email
    F->>A: POST /auth/otp/request
    A->>R: Send OTP email
    A->>DB: Store OTP code (10min TTL)
    R-->>U: Email with 6-digit code
    U->>F: Enter code
    F->>A: POST /auth/otp/verify
    A->>DB: Verify code + upsert user
    A-->>F: access_token + refresh_token

    Note over U,DB: Method 2 — WebAuthn Passkey
    U->>F: Click "Login with passkey"
    F->>A: POST /auth/webauthn/login/options
    A-->>F: Challenge
    F->>U: Biometric prompt
    U-->>F: Signed assertion
    F->>A: POST /auth/webauthn/login/verify
    A->>DB: Verify credential + update sign_count
    A-->>F: access_token + refresh_token
```

## Database Schema

```mermaid
erDiagram
    news_items {
        uuid id PK
        text title
        text summary
        text url
        varchar source
        varchar topic
        float relevance_score
        float composite_score
        float credibility_score
        bool trending
        timestamptz published_at
        timestamptz created_at
        text content_hash UK
        tsvector search_vector
    }

    item_embeddings {
        uuid item_id PK,FK
        text model PK
        vector embedding "vector(512)"
        timestamptz created_at
    }

    daily_briefings {
        date date PK
        int total_items
        jsonb sources_used
        float duration_seconds
    }

    users {
        uuid id PK
        text email UK
        varchar role "admin | reader"
        timestamptz last_login_at
    }

    otp_codes {
        serial id PK
        text email
        varchar code "6 digits"
        timestamptz expires_at
        bool used
    }

    webauthn_credentials {
        uuid id PK
        uuid user_id FK
        bytea credential_id UK
        bytea public_key
        int sign_count
    }

    raw_extractions {
        uuid id PK
        varchar source
        varchar source_id
        jsonb raw_json
    }

    pipeline_runs {
        uuid id PK
        timestamptz started_at
        float duration_seconds
        varchar status "success | empty | error"
        jsonb sources
        int items_stored
    }

    news_items ||--o{ item_embeddings : "has embeddings"
    users ||--o{ webauthn_credentials : "has passkeys"
    users ||--o{ otp_codes : "has OTP codes"
```

### Key Indexes

| Table | Index | Type | Purpose |
|-------|-------|------|---------|
| news_items | content_hash | UNIQUE | Deduplication |
| news_items | search_vector | GIN | Full-text search |
| news_items | effective_date | B-tree DESC | Feed ordering |
| news_items | trending + date | Partial B-tree | Trending queries |
| news_items | composite_score | B-tree | Feed ranking |
| item_embeddings | embedding | HNSW (cosine) | Vector similarity |
| webauthn_credentials | credential_id | UNIQUE | Passkey lookup |

## Security Model

- **Auth**: Guest tokens (public, read-only, 24h TTL) + Passwordless OTP + WebAuthn passkeys → JWT (30min access + 7d refresh with rotation)
- **Access tiers**: Public endpoints use `require_auth_or_guest`, protected endpoints (chat, settings) use `require_auth`
- **SSRF**: All external URL fetches check for private IP ranges
- **Headers**: X-Content-Type-Options, X-Frame-Options, Referrer-Policy, Permissions-Policy, HSTS
- **Body limit**: 1MB max request body (ASGI middleware)
- **Rate limiting**: JWT-aware slowapi — guest by `jti` (30 req/min), user by `sub` (120 req/min), fallback to IP
- **Scanner blocking**: Nginx returns 444 (connection drop) for wp-admin, phpMyAdmin, .env, .git probes
- **Secrets**: `.env` file, never committed, validated at startup (fail-fast on insecure defaults)
- **Scanning**: bandit in CI, ruff security rules (S-series)
- **Network**: Nginx/Traefik TLS termination, HTTPS via Let's Encrypt

## Observability

- **Logging**: structlog JSON with `correlation_id` per pipeline run / API request
- **Metrics**: Prometheus counters and histograms at `/metrics` (localhost only)
  - `api_requests_total`, `api_request_duration_seconds`
  - `pipeline_runs_total`, `pipeline_duration_seconds`
  - Per-extractor duration, items stored, classification duration
  - Embedding failures, validation failures
- **Run tracking**: Per-stage stats (items extracted/deduped/filtered/stored, failures, duration) persisted to the `pipeline_runs` table on every pipeline run; surfaced via the admin API (audit, freshness, pipeline-runs). No push-alert channel — observability is pull-based.

## Feed Algorithm

The feed ranking system replaces simple chronological ordering with quality-aware diversification:

```mermaid
flowchart TD
    subgraph "Composite Score (per item)"
        V[Velocity<br/>stars/hr, points/hr<br/>weight: 0.35]
        R[Relevance<br/>LLM score<br/>weight: 0.30]
        T[Recency<br/>48h decay<br/>weight: 0.20]
        TP[Topic<br/>bonus for trending topics<br/>weight: 0.15]
        V & R & T & TP --> CS[composite_score<br/>0.0 — 1.0]
    end

    subgraph "Feed Builder (query-time)"
        CAN[Fetch Candidates<br/>limit × 5 pool] --> COL[Variant Collapse<br/>HF model dedup]
        COL --> LR[Live Rescore<br/>fresh composite_score]
        LR --> MMR[MMR Diversification<br/>λ=0.7 quality vs diversity]
        MMR --> PAG[Paginate<br/>offset + limit]
    end

    CS --> CAN
```

## CI/CD Pipeline

```mermaid
flowchart LR
    PUSH[Push to main] --> LINT[Lint<br/>ruff check + format]
    PUSH --> TYPE[Type Check<br/>pyright]
    LINT & TYPE --> TEST[Unit Tests<br/>pytest + coverage ≥80%]
    TEST --> INT[Integration<br/>+ Security Tests]
    INT --> DEPLOY[Deploy<br/>Coolify webhook]
    DEPLOY --> COOLIFY[Coolify rebuilds<br/>Docker containers]

    style DEPLOY fill:#2d6a4f,color:#fff
```

**Kill switch**: `COOLIFY_DEPLOY_ENABLED` GitHub Variable (set to `false` to disable auto-deploy).

---

*See also: [Architecture, File Map & API Reference](agents.md) for the complete file map, endpoint reference, and DB schema details.*
