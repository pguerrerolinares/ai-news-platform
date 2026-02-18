# Milestone 0 — Foundation

**Objective**: Deployable infrastructure with quality gates.
**Status**: Complete (2026-02-17)

## Tasks

- [x] New project structure + git init
- [x] `pyproject.toml` with pinned dependencies (~=)
- [x] `Dockerfile` (Python 3.12-slim, non-root, healthcheck)
- [x] `docker-compose.yml` (PostgreSQL + API + Pipeline + Nginx)
- [x] `nginx.conf` (reverse proxy + static + rate limiting)
- [x] GitHub Actions CI (ruff, pyright, pytest, bandit, alembic check)
- [x] GitHub Actions CD (SSH deploy + health check + rollback)
- [x] PostgreSQL + pgvector in Docker
- [x] SQLAlchemy 2.0 async engine + session factory
- [x] Alembic initial migration (full schema)
- [x] Pydantic Settings config (`.env`)
- [x] structlog setup (JSON, correlation IDs)
- [x] prometheus-client setup (counters, histograms)
- [x] `.githooks/pre-push` (ruff + pyright + pytest --fast)
- [x] `.github/PULL_REQUEST_TEMPLATE.md` (Track C)
- [x] `AGENTS.md` (aligned with open standard)
- [x] `CLAUDE.md` (conventions + 8 principles)
- [x] ADRs: 001-005
- [x] Base interfaces (BaseExtractor, BaseClassifier, BaseValidator, BaseNotifier)
- [x] AlertService (Telegram alerts)
- [x] `scripts/backup.sh` (pg_dump + Backblaze B2)
- [x] `scripts/health_check.sh`
- [x] Tests (unit + fixtures)
- [x] Milestone plan docs
- [x] Runbooks
- [ ] Verify: `docker compose up` starts all services
- [ ] Verify: CI passes on first push
- [ ] Verify: Deploy workflow configured

## Verification

1. `docker compose up` — PostgreSQL starts, API responds /health
2. CI green on GitHub Actions
3. Backup script runs
4. All documentation files exist and are complete
