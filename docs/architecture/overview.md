# Architecture Overview

## System Architecture

AI News Platform runs as a Docker Compose stack on a Hetzner VPS (4GB RAM, ~5 EUR/month).

### Components

| Component | Technology | RAM Budget | Purpose |
|-----------|-----------|-----------|---------|
| Database | PostgreSQL 16 + pgvector | 300MB | Persistent storage, FTS, vector search |
| API | FastAPI (2 workers) | 200MB | REST API for frontend and MCP |
| Pipeline | Python (temporal) | 300MB | Daily news extraction + classification |
| Nginx | Nginx 1.27 | 50MB | TLS termination, reverse proxy, static files |
| OS + Docker | Linux | 400MB | Infrastructure |

### Data Flow

1. **Extraction**: Pipeline runs daily (cron), extractors fetch from 4-6 sources in parallel
2. **Deduplication**: 2-pass hash dedup (content_hash + url_hash)
3. **Classification**: Batched LLM calls (Kimi/Moonshot) assign topic, relevance, summary
4. **Event Dedup**: LLM groups items about the same event, picks winners
5. **Validation**: Concurrent URL verification, credibility scoring
6. **Storage**: Validated items inserted into PostgreSQL via SQLAlchemy async
7. **Notification**: Telegram briefing + web UI

### Interface Architecture

Every major component is defined as an ABC (Abstract Base Class).
Existing implementations marked with **bold**, planned ones in *italics*:

- `BaseExtractor` -> **`HackerNewsExtractor`** (M1), *`ArxivExtractor`* (M2), *`RedditExtractor`* (M2), *`RSSExtractor`* (M2), *`GitHubTrendingExtractor`* (M3), *`HuggingFaceExtractor`* (M3)
- `BaseClassifier` -> *`LLMClassifier`* (M2), *`KeywordClassifier`* (M2)
- `BaseValidator` -> *`CredibilityValidator`* (M2)
- `BaseNotifier` -> *`TelegramNotifier`* (M2)
- *`BaseEmbedder`* -> (Milestone 4)

New implementations extend the system without modifying existing code (Open/Closed Principle).

### Security Model

- **Auth**: Shared password -> JWT token (semi-public, small group)
- **SSRF**: All external URL fetches check for private IP ranges
- **Secrets**: `.env` file, never committed
- **Scanning**: bandit in CI, ruff security rules
- **Network**: Nginx rate limiting, HTTPS via Let's Encrypt

### Observability

- **Logging**: structlog (JSON), correlation IDs per pipeline run / API request
- **Metrics**: Prometheus counters and histograms at /metrics
- **Alerts**: Telegram notifications for pipeline failures, deploy issues, backup failures, extractor 0 items
