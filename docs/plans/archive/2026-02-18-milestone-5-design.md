# Milestone 5 — Production Hardening Design

## Goal

Make the platform production-ready: fix Nginx for SSE streaming, parametrize domain for HTTPS, add security headers, fix health endpoint, automate pipeline scheduling, update config and docs.

## Decisions

| Decision | Choice | Rationale |
|---|---|---|
| HTTPS approach | Domain-ready config (commented) | No domain yet; prepare everything, uncomment when ready |
| Pipeline scheduling | Sleep loop in Docker container | Simpler than installing cron in a slim container |
| Auto-migration | Entrypoint script runs `alembic upgrade head` | Container always has correct schema on restart |
| Metrics access | Restrict to localhost in Nginx | Prometheus metrics should not be public |
| Health status code | 503 when unhealthy | Docker healthcheck and monitoring tools expect non-2xx on failure |

## Components

### 1. Nginx Config (`nginx.conf`)

- Parametrize `server_name` with `DOMAIN` env var (default `_`)
- Add `proxy_buffering off`, `proxy_cache off`, `proxy_read_timeout 300s` for `/api/chat` (SSE streaming)
- Add security headers: `X-Frame-Options DENY`, `X-Content-Type-Options nosniff`, `Referrer-Policy strict-origin-when-cross-origin`
- Restrict `/metrics` to `127.0.0.1` (deny all)
- HTTPS server block ready to uncomment with `${DOMAIN}` placeholder

### 2. Health Endpoint (`src/api/app.py`)

Return HTTP 503 with `{"status": "unhealthy", "database": "..."}` when DB connection fails. Keep HTTP 200 for healthy.

### 3. Pipeline Cron Service (`docker-compose.yml`)

New `pipeline-cron` service: sleep loop that runs `python -m src.main` at the configured hour. No external cron dependency. Uses the same image as `api`.

### 4. Docker Entrypoint (`docker-entrypoint.sh`)

Shell script: `alembic upgrade head && exec uvicorn ...`. Replaces the CMD in Dockerfile. Ensures migrations run on every container start/restart.

### 5. `.env.example` Updated

Add missing M3/M4 variables: `GITHUB_TOKEN`, `GITHUB_SEARCH_QUERIES`, `GITHUB_MIN_STARS`, `HF_MIN_DOWNLOADS`, `EMBEDDING_API_KEY`, `EMBEDDING_BASE_URL`, `EMBEDDING_MODEL`, `CORS_ORIGINS`.

### 6. AGENTS.md Updated

Reflect M0-M4 complete status, 666+ tests, updated file map with all M3/M4 files (MCP, RAG, chat, GitHub/HuggingFace extractors, analytics page).

## File Map

| File | Action |
|---|---|
| `nginx.conf` | Modify (SSE, security headers, metrics restriction, domain param) |
| `src/api/app.py` | Modify (health endpoint returns 503 on failure) |
| `docker-compose.yml` | Modify (add pipeline-cron service) |
| `docker-entrypoint.sh` | Create (alembic upgrade + exec uvicorn) |
| `Dockerfile` | Modify (use entrypoint script) |
| `.env.example` | Modify (add M3/M4 variables) |
| `AGENTS.md` | Modify (full update to reflect M0-M4) |
| `tests/unit/test_api.py` | Modify (add health 503 test) |

## Verification

1. `pytest tests/` — all tests pass (including new health 503 test)
2. `docker compose config` — valid compose file
3. `nginx -t` via docker — valid nginx config
4. Health endpoint returns 200 when DB connected, 503 when not
5. SSE streaming works through Nginx (no buffering)
