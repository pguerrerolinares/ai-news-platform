# Milestone 5 — Production Hardening Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make the platform production-ready — fix health endpoint, Nginx SSE/security, pipeline cron, auto-migrations, and update all docs.

**Architecture:** Fix infrastructure gaps found in code review: health endpoint returns proper HTTP status codes, Nginx supports SSE streaming with security headers, pipeline runs on a schedule via Docker, and containers auto-migrate on startup. All changes are testable locally without a VPS.

**Tech Stack:** FastAPI, Nginx, Docker Compose, Alembic, pytest

---

### Task 1: Health Endpoint Returns 503 When Unhealthy

The `/health` endpoint currently returns HTTP 200 even when the database is down. Docker healthcheck, Nginx, and monitoring tools need a non-2xx status to detect failure.

**Files:**
- Modify: `src/api/app.py:100-110`
- Modify: `tests/unit/test_api.py:32-104`

**Step 1: Write the failing test**

Add a new test to `tests/unit/test_api.py` inside the `TestHealthEndpoint` class. Also update the existing `test_health_unhealthy_when_db_fails` test to expect 503 instead of 200.

Add this test at the end of `TestHealthEndpoint` (after line 103):

```python
    async def test_health_returns_503_when_db_fails(self, api_client: AsyncClient):
        """When the DB is unreachable, HTTP status should be 503."""
        mock_connect = AsyncMock()
        mock_connect.__aenter__ = AsyncMock(side_effect=ConnectionError("refused"))
        mock_connect.__aexit__ = AsyncMock(return_value=False)

        mock_engine = MagicMock()
        mock_engine.connect.return_value = mock_connect

        with patch("src.api.app.get_engine", return_value=mock_engine):
            resp = await api_client.get("/health")

        assert resp.status_code == 503
        data = resp.json()
        assert data["status"] == "unhealthy"
```

Update `test_health_returns_200` docstring from `"""Health endpoint should always return HTTP 200."""` to `"""Health endpoint returns 200 when DB is connected."""`.

**Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/unit/test_api.py::TestHealthEndpoint::test_health_returns_503_when_db_fails -v`
Expected: FAIL (currently returns 200)

**Step 3: Implement the fix**

In `src/api/app.py`, change the `health_check` function (lines 100-110) to:

```python
from fastapi.responses import JSONResponse

@app.get("/health")
async def health_check() -> JSONResponse:
    """Health check endpoint. Verifies DB connectivity."""
    engine = get_engine()
    try:
        async with engine.connect() as conn:
            await conn.execute(__import__("sqlalchemy").text("SELECT 1"))
        return JSONResponse(content={"status": "healthy", "database": "connected"})
    except Exception as exc:
        logger.error("health_check_failed", error=str(exc))
        return JSONResponse(
            status_code=503,
            content={"status": "unhealthy", "database": str(exc)},
        )
```

Note: import `JSONResponse` from `fastapi.responses` — it's already imported for `StreamingResponse` patterns elsewhere, but check if `Response` import on line 9 covers it. If not, add `JSONResponse` to the import from `fastapi`.

**Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/unit/test_api.py -v`
Expected: ALL PASS (including new 503 test)

**Step 5: Run full test suite**

Run: `.venv/bin/pytest tests/unit/ -v --timeout=30`
Expected: ALL PASS

**Step 6: Commit**

```bash
git add src/api/app.py tests/unit/test_api.py
git commit -m "fix(m5): health endpoint returns 503 when DB unreachable"
```

---

### Task 2: Nginx Config — SSE Streaming, Security Headers, Metrics Restriction

The current Nginx config buffers SSE responses (breaks chat streaming), exposes `/metrics` to the internet, and has no security headers. Also the HTTPS block uses a hardcoded `YOUR_DOMAIN` placeholder.

**Files:**
- Modify: `nginx.conf`

**Step 1: Rewrite `nginx.conf`**

Replace the entire file with:

```nginx
worker_processes auto;
error_log /var/log/nginx/error.log warn;
pid /tmp/nginx.pid;

events {
    worker_connections 256;
}

http {
    include /etc/nginx/mime.types;
    default_type application/octet-stream;

    log_format main '$remote_addr - $remote_user [$time_local] "$request" '
                    '$status $body_bytes_sent "$http_referer" '
                    '"$http_user_agent"';
    access_log /var/log/nginx/access.log main;

    sendfile on;
    keepalive_timeout 65;
    client_max_body_size 10m;

    # Gzip
    gzip on;
    gzip_types text/plain text/css application/json application/javascript text/xml;
    gzip_min_length 256;

    # Rate limiting
    limit_req_zone $binary_remote_addr zone=api:10m rate=30r/m;

    # Security headers (applied to all responses)
    add_header X-Frame-Options "DENY" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;

    # Upstream
    upstream api_backend {
        server api:8000;
    }

    server {
        listen 80;
        server_name _;

        # Let's Encrypt challenge
        location /.well-known/acme-challenge/ {
            root /var/www/certbot;
        }

        # Health check (used by docker healthcheck)
        location = /health {
            proxy_pass http://api_backend/health;
        }

        # Redirect all HTTP to HTTPS (enable after SSL setup)
        # location / {
        #     return 301 https://$host$request_uri;
        # }

        # API routes
        location /api/ {
            limit_req zone=api burst=10 nodelay;
            proxy_pass http://api_backend/api/;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
        }

        # SSE streaming for chat (no buffering)
        location = /api/chat {
            limit_req zone=api burst=10 nodelay;
            proxy_pass http://api_backend/api/chat;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
            proxy_buffering off;
            proxy_cache off;
            proxy_read_timeout 300s;
            chunked_transfer_encoding on;
        }

        # Prometheus metrics (localhost only)
        location /metrics {
            allow 127.0.0.1;
            deny all;
            proxy_pass http://api_backend/metrics;
        }

        # Angular SPA
        location / {
            root /usr/share/nginx/html;
            index index.html;
            try_files $uri $uri/ /index.html;
        }
    }

    # HTTPS server (enable after obtaining SSL certificate)
    # 1. Set DOMAIN env var in .env
    # 2. Run: docker compose --profile certbot run certbot certonly --webroot -w /var/www/certbot -d YOUR_DOMAIN
    # 3. Uncomment this block and the HTTP->HTTPS redirect above
    # 4. Replace YOUR_DOMAIN with your actual domain
    # 5. Restart nginx: docker compose restart nginx
    #
    # server {
    #     listen 443 ssl;
    #     server_name YOUR_DOMAIN;
    #
    #     ssl_certificate /etc/letsencrypt/live/YOUR_DOMAIN/fullchain.pem;
    #     ssl_certificate_key /etc/letsencrypt/live/YOUR_DOMAIN/privkey.pem;
    #     ssl_protocols TLSv1.2 TLSv1.3;
    #     ssl_ciphers HIGH:!aNULL:!MD5;
    #
    #     location /api/ {
    #         limit_req zone=api burst=10 nodelay;
    #         proxy_pass http://api_backend/api/;
    #         proxy_set_header Host $host;
    #         proxy_set_header X-Real-IP $remote_addr;
    #         proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    #         proxy_set_header X-Forwarded-Proto $scheme;
    #     }
    #
    #     location = /api/chat {
    #         limit_req zone=api burst=10 nodelay;
    #         proxy_pass http://api_backend/api/chat;
    #         proxy_set_header Host $host;
    #         proxy_set_header X-Real-IP $remote_addr;
    #         proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    #         proxy_set_header X-Forwarded-Proto $scheme;
    #         proxy_buffering off;
    #         proxy_cache off;
    #         proxy_read_timeout 300s;
    #         chunked_transfer_encoding on;
    #     }
    #
    #     location /metrics {
    #         allow 127.0.0.1;
    #         deny all;
    #         proxy_pass http://api_backend/metrics;
    #     }
    #
    #     location / {
    #         root /usr/share/nginx/html;
    #         index index.html;
    #         try_files $uri $uri/ /index.html;
    #     }
    # }
}
```

Key changes from current:
- Added dedicated `/api/chat` location with `proxy_buffering off`, `proxy_cache off`, `proxy_read_timeout 300s`
- Added 3 security headers in the `http` block
- `/metrics` now has `allow 127.0.0.1; deny all;`
- HTTPS block has step-by-step instructions as comments

**Step 2: Validate nginx config**

Run: `docker run --rm -v "$(pwd)/nginx.conf:/etc/nginx/nginx.conf:ro" nginx:1.27-alpine nginx -t`
Expected: `nginx: the configuration file /etc/nginx/nginx.conf syntax is ok`

**Step 3: Commit**

```bash
git add nginx.conf
git commit -m "feat(m5): nginx SSE streaming, security headers, metrics restriction"
```

---

### Task 3: Docker Entrypoint with Auto-Migration

Currently migrations only run during CD deploy. If a container restarts, it might have stale schema. Create an entrypoint script that runs `alembic upgrade head` before starting uvicorn.

**Files:**
- Create: `docker-entrypoint.sh`
- Modify: `Dockerfile:30-32`

**Step 1: Create `docker-entrypoint.sh`**

```bash
#!/usr/bin/env bash
set -e

echo "Running database migrations..."
alembic upgrade head

echo "Starting API server..."
exec uvicorn src.api.app:app \
    --host "${API_HOST:-0.0.0.0}" \
    --port "${API_PORT:-8000}" \
    --workers "${API_WORKERS:-2}"
```

**Step 2: Update `Dockerfile`**

Replace the last two lines (CMD line 32) with:

```dockerfile
COPY docker-entrypoint.sh ./
RUN chmod +x docker-entrypoint.sh

EXPOSE 8000

ENTRYPOINT ["./docker-entrypoint.sh"]
```

The full Dockerfile becomes:

```dockerfile
FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN groupadd --gid 1000 appuser && \
    useradd --uid 1000 --gid appuser --create-home appuser

WORKDIR /app

# Install system dependencies for asyncpg
RUN apt-get update && \
    apt-get install -y --no-install-recommends curl && \
    rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
RUN pip install --no-cache-dir . && \
    pip cache purge

COPY alembic/ alembic/
COPY alembic.ini ./
COPY src/ src/
COPY docker-entrypoint.sh ./

RUN chown -R appuser:appuser /app
USER appuser

RUN chmod +x docker-entrypoint.sh

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

EXPOSE 8000

ENTRYPOINT ["./docker-entrypoint.sh"]
```

Note: `start_period` increased to 15s to account for migration time.

**Step 3: Verify docker-compose config is valid**

Run: `docker compose config --quiet`
Expected: No output (success)

**Step 4: Commit**

```bash
git add docker-entrypoint.sh Dockerfile
git commit -m "feat(m5): docker entrypoint with auto-migration on startup"
```

---

### Task 4: Pipeline Cron Service

The pipeline currently only runs manually with `docker compose --profile pipeline run pipeline`. Add a `pipeline-cron` service that runs the pipeline on a schedule using a simple sleep loop.

**Files:**
- Create: `scripts/pipeline-scheduler.sh`
- Modify: `docker-compose.yml`

**Step 1: Create `scripts/pipeline-scheduler.sh`**

```bash
#!/usr/bin/env bash
# Simple pipeline scheduler using sleep loop.
# Runs the pipeline once at startup, then daily at PIPELINE_SCHEDULE_HOUR.
set -e

SCHEDULE_HOUR="${PIPELINE_SCHEDULE_HOUR:-8}"

echo "Pipeline scheduler started. Will run daily at ${SCHEDULE_HOUR}:00 UTC."

# Run once at startup
echo "Running initial pipeline..."
python -m src.main || echo "Initial pipeline run failed (non-fatal)."

while true; do
    CURRENT_HOUR=$(date -u +%H)
    CURRENT_MIN=$(date -u +%M)

    if [ "$CURRENT_HOUR" -eq "$SCHEDULE_HOUR" ] && [ "$CURRENT_MIN" -eq "0" ]; then
        echo "Scheduled run at $(date -u +%Y-%m-%dT%H:%M:%SZ)"
        python -m src.main || echo "Pipeline run failed (non-fatal)."
        # Sleep 61 seconds to avoid running twice in the same minute
        sleep 61
    else
        sleep 30
    fi
done
```

**Step 2: Add `pipeline-cron` service to `docker-compose.yml`**

Add after the `pipeline` service block (after line 50):

```yaml
  pipeline-cron:
    build: .
    restart: unless-stopped
    depends_on:
      db:
        condition: service_healthy
    environment:
      DATABASE_URL: postgresql+asyncpg://${POSTGRES_USER:-ainews}:${POSTGRES_PASSWORD}@db:5432/${POSTGRES_DB:-ainews}
      DATABASE_URL_SYNC: postgresql://${POSTGRES_USER:-ainews}:${POSTGRES_PASSWORD}@db:5432/${POSTGRES_DB:-ainews}
    env_file:
      - .env
    command: ["bash", "scripts/pipeline-scheduler.sh"]
    profiles:
      - cron
```

It uses the `cron` profile so it doesn't start by default. Deploy with:
`docker compose --profile cron up -d pipeline-cron`

**Step 3: Verify docker-compose config is valid**

Run: `docker compose config --quiet`
Expected: No output (success)

**Step 4: Commit**

```bash
git add scripts/pipeline-scheduler.sh docker-compose.yml
git commit -m "feat(m5): add pipeline-cron service with daily scheduler"
```

---

### Task 5: Update `.env.example`

The `.env.example` is missing all M3 (GitHub, HuggingFace) and M4 (embeddings) configuration variables. Also missing `CORS_ORIGINS`.

**Files:**
- Modify: `.env.example`

**Step 1: Add missing variables**

Add after the RSS section (after line 51):

```bash
# GitHub
GITHUB_TOKEN=
GITHUB_SEARCH_QUERIES=AI,LLM,machine-learning,generative-AI
GITHUB_MIN_STARS=50

# HuggingFace
HF_MIN_DOWNLOADS=100
```

Add after the `LOG_FORMAT` line (after line 67):

```bash
# --- Embeddings (OpenAI, for RAG chat) ---
EMBEDDING_API_KEY=sk-your-openai-key-here
EMBEDDING_BASE_URL=https://api.openai.com/v1
EMBEDDING_MODEL=text-embedding-3-small
```

Add after `CORS_ORIGINS` is missing. Add it after the `DEBUG` line in the API section:

```bash
CORS_ORIGINS=http://localhost:4200
```

Also update `ENABLED_SOURCES` default to include github and huggingface:

```bash
ENABLED_SOURCES=hackernews,arxiv,reddit,rss,github,huggingface
```

**Step 2: Verify no secrets leaked**

Review the file to ensure only placeholder/default values are present.

**Step 3: Commit**

```bash
git add .env.example
git commit -m "docs(m5): update .env.example with M3/M4 variables"
```

---

### Task 6: Update AGENTS.md

The AGENTS.md is stuck at Milestone 2. It needs to reflect the current state: M0-M4 complete, 666+ tests, all new files from M3 (GitHub, HuggingFace, MCP) and M4 (RAG, chat, analytics).

**Files:**
- Modify: `AGENTS.md`

**Step 1: Update AGENTS.md**

This is a documentation-only task. The key changes:

1. **Header**: Change `Current milestone: 2` to `Current milestone: 5` and status to `In progress`
2. **File Map**: Add all M3/M4/M5 files:
   - `src/extractors/github.py`, `src/extractors/huggingface.py`
   - `src/mcp/server.py`, `src/mcp/client.py`
   - `src/rag/embeddings.py`, `src/rag/retriever.py`, `src/rag/chat.py`
   - `src/api/routes/chat.py`
   - `web/src/app/pages/analytics.ts`, `web/src/app/pages/chat.ts`
   - `docker-entrypoint.sh`, `scripts/pipeline-scheduler.sh`
   - All new test files
3. **API Endpoints**: Update `POST /api/chat` from "Planned" to "Done"
4. **Database Schema**: Update `item_embeddings.embedding` from `vector(768)` to `vector(1536)`
5. **Current State**: Add M3, M4, M5 sections
6. **Test counts**: Update all test counts
7. **Configuration**: Add embedding settings
8. **Next Tasks**: Update to reflect current priorities

Read the full current file, then rewrite it with all updates. The file is large (~430 lines) so provide the complete replacement.

**Step 2: Commit**

```bash
git add AGENTS.md
git commit -m "docs(m5): update AGENTS.md to reflect M0-M5 state"
```

---

### Task 7: Final Verification

**Step 1: Run all linting**

Run: `.venv/bin/ruff check src/ tests/`
Expected: `All checks passed!`

Run: `.venv/bin/ruff format --check src/ tests/`
Expected: `N files already formatted`

**Step 2: Run full unit test suite**

Run: `.venv/bin/pytest tests/unit/ -v --timeout=30`
Expected: 633+ tests pass (632 existing + 1 new health 503 test)

**Step 3: Run E2E tests**

Run: `.venv/bin/pytest tests/e2e/ -v --timeout=30`
Expected: 34 tests pass

**Step 4: Verify docker-compose is valid**

Run: `docker compose config --quiet`
Expected: No output (success)

**Step 5: Verify nginx config is valid**

Run: `docker run --rm -v "$(pwd)/nginx.conf:/etc/nginx/nginx.conf:ro" nginx:1.27-alpine nginx -t`
Expected: `syntax is ok`

**Step 6: Verify Angular build**

Run: `cd web && npx ng build`
Expected: Build succeeds

**Step 7: Report final counts**

Report: total unit tests, E2E tests, lint status, format status, docker-compose validity, nginx validity.
