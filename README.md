# AI News Platform

Plataforma de agregacion, clasificacion y busqueda de noticias de inteligencia artificial.
Extrae noticias de 7 fuentes, las clasifica con LLM, almacena en PostgreSQL con embeddings
vectoriales, y las sirve a traves de una API REST + frontend React.

**100% construido por agentes de IA. Cero lineas de codigo escritas por un humano.**

## Que hace

- **Extraccion automatica** de HackerNews, arXiv, Reddit, RSS, GitHub Trending, HuggingFace y sitios web configurables
- **Clasificacion inteligente** por topico (models, tools, papers, products, open_source, agents, regulation) usando LLM (Kimi/Moonshot)
- **Feed con ranking** — composite scoring (velocidad + relevancia + recencia), variant collapse para modelos HF duplicados, diversificacion MMR
- **Busqueda full-text** (PostgreSQL tsvector) + **busqueda semantica** (pgvector cosine similarity)
- **Chat RAG** — preguntas sobre las noticias con respuestas basadas en contexto via SSE streaming
- **Autenticacion** — OTP por email (Resend API) + WebAuthn passkeys + shared password fallback
- **Notificaciones** — briefing diario via Telegram
- **Pipeline programado** — 3 tiers de frecuencia (15min / 60min / diario) con circuit breaker

## Stack

| Capa | Tecnologia |
|------|-----------|
| Backend | Python 3.12, FastAPI, SQLAlchemy async, asyncpg |
| Base de datos | PostgreSQL 16 + pgvector |
| Frontend | React 19, TypeScript, Vite, Tailwind CSS 4, Shadcn UI |
| LLM | Kimi/Moonshot (OpenAI-compatible) |
| Embeddings | OpenAI text-embedding-3-small |
| Infra | Docker Compose, Nginx, Coolify, Hetzner VPS (4GB) |
| CI/CD | GitHub Actions → Coolify webhook auto-deploy |
| Observabilidad | structlog (JSON), Prometheus, alertas Telegram |

## Inicio rapido

```bash
# Clonar y configurar
git clone <repo> && cd ai-news-platform
cp .env.example .env  # Rellenar secretos

# Entorno de desarrollo
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# Base de datos
docker compose up db -d
alembic upgrade head

# API
uvicorn src.api.app:app --reload --port 8000

# Frontend
cd frontend && npm install && npm run dev

# Pipeline (ejecucion manual)
python -m src.main
```

### Produccion (Docker)

```bash
docker compose up -d                                          # db + api + nginx
docker compose --profile cron up -d pipeline-cron             # pipeline programado
docker compose --profile pipeline run --rm pipeline           # ejecucion unica
```

## Estructura del proyecto

```
ai-news-platform/
├── src/
│   ├── api/           # FastAPI app, auth, routes (25+ endpoints)
│   ├── extractors/    # 7 extractors (HN, arXiv, Reddit, RSS, GitHub, HF, WebScraper)
│   ├── classifiers/   # LLM + keyword classifiers, event dedup
│   ├── validators/    # Credibility validation
│   ├── pipeline/      # Orchestrator, scheduler, composite scoring, circuit breaker
│   ├── feed/          # Feed algorithm (variant collapse, MMR diversification)
│   ├── rag/           # Embeddings, retriever, chat service (SSE)
│   ├── notifiers/     # Telegram notifications + alerts
│   ├── mcp/           # MCP server + client
│   └── core/          # Config, models, database, logging, metrics
├── frontend/          # React 19 + Vite + Shadcn UI (6 paginas)
├── tests/             # 1,015+ tests (unit + E2E Playwright), 92% coverage
├── alembic/           # 9 migraciones de DB
├── docs/              # Arquitectura, ADRs, planes, runbooks
└── scripts/           # Backup, health check, rescore
```

## Quality gates

```bash
ruff check . && ruff format --check .   # Lint + formato
pyright .                                # Type checking
pytest tests/ -x --timeout=30           # Tests
bandit -r src/                           # Seguridad
```

## Documentacion

- [`AGENTS.md`](AGENTS.md) — Guia del agente: file map, endpoints, esquema DB, CI/CD
- [`CLAUDE.md`](CLAUDE.md) — Convenciones de codigo y principios de ingenieria
- [`docs/architecture/`](docs/architecture/) — Overview de arquitectura con diagramas + ADRs
- [`docs/plans/`](docs/plans/) — Design docs, planes de implementacion, backlog
- [`docs/runbooks/`](docs/runbooks/) — Guias operativas (deploy, backup, troubleshooting)

## Numeros

| Metrica | Valor |
|---------|-------|
| Commits | 437 |
| Backend (Python) | ~8,600 LOC |
| Frontend (TypeScript) | ~4,870 LOC |
| Tests | ~17,160 LOC |
| Tests passing | 1,015+ |
| Coverage | 92% |
| Design docs | ~75 |
| Tiempo de desarrollo | ~2 semanas |
| Codigo humano | 0 lineas |

## Licencia

Proyecto privado.
