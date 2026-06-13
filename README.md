# AI News Platform

Plataforma de agregacion, clasificacion y busqueda de noticias de inteligencia artificial.
Extrae noticias de 9 fuentes, las clasifica con LLM, almacena en PostgreSQL con embeddings
vectoriales, y las sirve a traves de una API REST + frontend React.

**100% construido por agentes de IA. Cero lineas de codigo escritas por un humano.**

## Que hace

- **Extraccion automatica** de HackerNews, HackerNews Leading, arXiv, Reddit, RSS, GitHub Trending, GitHub Search, HuggingFace y sitios web configurables
- **Clasificacion inteligente** — two-phase: keyword pre-filter (>=3 matches auto-accept, 0 reject) + LLM para ambiguos. Fuzzy event dedup entre sources
- **Feed con ranking** — composite scoring (velocidad + relevancia + recencia), variant collapse para modelos HF duplicados, diversificacion MMR
- **Busqueda full-text** (PostgreSQL tsvector) + **busqueda semantica** (pgvector 512-dim cosine similarity)
- **Chat RAG** — preguntas sobre las noticias con respuestas basadas en contexto via SSE streaming
- **Autenticacion** — OTP por email (Resend API) + WebAuthn passkeys
- **Dedup persistente** — URL hash unique index + title similarity contra DB (cross-source, cross-tier)
- **Observabilidad** — pipeline_runs table con stats por etapa, admin API endpoints (audit, freshness, pipeline-runs)
- **Pipeline programado** — 5 tiers de frecuencia (15min / 30min / 60min / 4h / diario) con circuit breaker y seen filter

## Stack

| Capa | Tecnologia |
|------|-----------|
| Backend | Python 3.12, FastAPI, SQLAlchemy async, asyncpg |
| Base de datos | PostgreSQL 16 + pgvector |
| Frontend | React 19, TypeScript, Vite, Tailwind CSS 4, Shadcn UI |
| LLM | Kimi/Moonshot (OpenAI-compatible) |
| Embeddings | OpenAI text-embedding-3-small (512 dims) |
| Infra | Docker Compose, Nginx, Coolify, Hetzner VPS (4GB) |
| CI/CD | GitHub Actions → Coolify webhook auto-deploy |
| Observabilidad | structlog (JSON), Prometheus, pipeline_runs table, admin API |

## Inicio rapido

```bash
# Clonar y configurar
git clone <repo> && cd ai-news-platform
cp .env.example .env  # Rellenar secretos

# Entorno de desarrollo
python -m venv .venv && source .venv/bin/activate
pip install -e ".[api,pipeline,dev]"

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
│   ├── api/           # FastAPI app, auth, routes (40+ endpoints)
│   ├── extractors/    # 9 extractors (HN, HN-leading, arXiv, Reddit, RSS, GitHub Trending, GitHub Search, HF, WebScraper)
│   ├── classifiers/   # Two-phase (keyword→LLM), fuzzy event dedup
│   ├── validators/    # Credibility validation
│   ├── pipeline/      # Orchestrator + 5 stages (extract/classify/score/seen_filter/store), scheduler, scoring
│   ├── feed/          # Feed algorithm (variant collapse, MMR diversification)
│   ├── rag/           # Embeddings (512-dim), retriever, chat service (SSE)
│   ├── mcp/           # MCP server + client
│   └── core/          # Config, models, database, logging, metrics
├── frontend/          # React 19 + Vite + Shadcn UI (10 paginas)
├── tests/             # 1,179+ tests (unit + integration + E2E Playwright), 92% coverage
├── alembic/           # 17 migraciones de DB
├── docs/              # Arquitectura, ADRs, planes, runbooks
└── scripts/           # Backup, health check, rescore
```

## Servidor MCP

La plataforma expone un servidor [MCP](https://modelcontextprotocol.io) publico en
`https://pguerrero.me/mcp` con 5 tools de solo lectura: `search_news`, `semantic_search`,
`get_latest`, `get_trending` y `get_briefing`. No requiere autenticacion ni instalacion.

**Claude Code:**

```bash
claude mcp add --transport http ainews https://pguerrero.me/mcp
```

**claude.ai** (web/desktop): Settings → Connectors → Add custom connector → URL `https://pguerrero.me/mcp`.

**Otros clientes MCP** (config JSON generica para clientes con soporte streamable HTTP):

```json
{
  "mcpServers": {
    "ainews": {
      "type": "http",
      "url": "https://pguerrero.me/mcp"
    }
  }
}
```

Tambien puede ejecutarse en local via stdio contra la API publica:

```bash
MCP_API_BASE_URL=https://pguerrero.me python -m src.mcp.server
```

El endpoint tiene rate limiting por IP (3 req/s, burst 10). Detalles de despliegue en
[`docs/adr/001-remote-mcp-server.md`](docs/adr/001-remote-mcp-server.md).

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
| Commits | 592 |
| Backend (Python) | ~9,500 LOC |
| Frontend (TypeScript) | ~6,900 LOC |
| Tests | ~18,600 LOC |
| Tests passing | 1,179+ |
| Coverage | 92% |
| Design docs | ~110 |
| Codigo humano | 0 lineas |

## Licencia

Codigo publico para consulta. Todos los derechos reservados.

No se concede licencia de uso, copia, modificacion ni distribucion. El repositorio
es visible con fines de demostracion y portfolio; no es software de codigo abierto.
