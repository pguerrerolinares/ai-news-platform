# Context Optimization Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Reduce auto-loaded documentation from ~14,200 tokens to ~5,200 tokens (~63% reduction) by trimming AGENTS.md, archiving milestone history, and cleaning MEMORY.md.

**Architecture:** Documentation-only refactoring. Extract historical content from AGENTS.md into a new archive file, rewrite AGENTS.md with condensed sections, trim MEMORY.md of redundant entries.

**Tech Stack:** Markdown files only. No code changes, no tests needed.

---

### Task 1: Create milestone history archive

**Files:**
- Create: `docs/milestone-history.md`

**Step 1: Create the archive file**

Create `docs/milestone-history.md` with the following content extracted from AGENTS.md:

- Copy lines 533-825 from current AGENTS.md (everything from `## Current State` through the end including Development History table)
- Add a header explaining this is an archive:

```markdown
# Milestone History Archive

> Archived from AGENTS.md on 2026-02-27 to reduce context window consumption.
> This file is NOT auto-loaded. Read it when you need historical context.

## Current State (as of 2026-02-27)

[paste all milestone checklists, key design decisions, scheduling tiers,
frontend migration, multi-user auth, next tasks, and development history table]
```

**Step 2: Verify the archive**

Run: `wc -l docs/milestone-history.md`
Expected: ~300-310 lines

**Step 3: Commit**

```bash
git add docs/milestone-history.md
git commit -m "docs: archive milestone history from AGENTS.md

Extract all completed milestone checklists, key design decisions,
and development history to reduce auto-loaded context consumption."
```

---

### Task 2: Rewrite AGENTS.md

**Files:**
- Modify: `AGENTS.md` (full rewrite — replace 826 lines with ~250)

**Step 1: Write the new AGENTS.md**

The new file keeps these sections **unchanged** from the original:
- Project Overview (lines 1-16)
- Architecture + Data Flow diagrams (lines 18-48)
- How to Run (lines 50-83)

Then replaces the remaining sections with condensed versions:

**Trimmed File Map** (~40 lines replacing ~210):
```
ai-news-platform/
├── AGENTS.md / CLAUDE.md            # Agent guide / coding conventions
├── pyproject.toml                    # Dependencies + tool config
├── Dockerfile / docker-compose.yml / nginx.conf
├── alembic/                          # DB migrations (5 versions)
├── src/
│   ├── main.py                       # CLI entry point
│   ├── core/
│   │   ├── config.py                 # Pydantic Settings (all env vars)
│   │   ├── database.py               # Async SQLAlchemy engine + get_async_session()
│   │   ├── models.py                 # ORM: NewsItem, DailyBriefing, ItemEmbedding, User, OtpCode
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
│   │   └── routes/                   # auth, otp, items, briefings, search, chat, stats, sources
│   ├── pipeline/
│   │   ├── pipeline.py               # extract→dedup→classify→validate→embed→store→notify
│   │   ├── scheduler.py              # APScheduler 3-tier (15m/60m/daily)
│   │   └── circuit_breaker.py        # Per-source failure tracking
│   ├── rag/                          # embeddings, retriever, chat (SSE streaming)
│   └── mcp/                          # MCP server + client
├── frontend/                         # React 19 (Vite + Shadcn UI + Tailwind CSS 4)
│   └── src/
│       ├── lib/                      # api.ts, auth.ts, constants.ts, types.ts
│       ├── hooks/                    # use-auth, use-theme, use-mobile
│       ├── components/               # layout, app-nav, news-card, featured-card, ui/
│       └── pages/                    # Login, Dashboard, Trending, Buscar, Chat
├── tests/                            # 872 unit + 35 E2E (Playwright)
├── scripts/                          # backup, health check, pipeline scheduler
└── docs/                             # architecture, ADRs, plans, runbooks, milestone-history
```

**Condensed Database Schema** (~15 lines replacing ~80):
```markdown
## Database Schema

### Tables
- **news_items**: id(UUID PK), title, summary, url, source, topic, relevance_score, dev_value_score, credibility_score, priority, trending, published_at, created_at, content_hash(UNIQUE), url_hash, full_text, author, score, metadata(JSONB)
  Indexes: published_at DESC, topic, source, content_hash, url_hash, FTS(title+summary+full_text), score, created_at
- **raw_extractions**: id(SERIAL PK), title, url, source, extracted_at, data(JSONB) — staging table
- **daily_briefings**: date(DATE PK), total_items, items_extracted, items_after_dedup, items_filtered, trending_count, duration_seconds, sources_used(JSONB), generated_at
- **item_embeddings**: item_id(UUID FK→news_items PK), model(TEXT PK), embedding(vector(1536)), created_at
- **users**: id(UUID PK), email(UNIQUE), name, role(admin|reader), created_at, last_login_at
- **otp_codes**: id(SERIAL PK), email, code(6-digit), expires_at, used, created_at — purged daily by scheduler
```

**Condensed API Endpoints** (~25 lines replacing ~50):
```markdown
## API Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | /health | No | Health check (200/503) |
| GET | /metrics | No | Prometheus (localhost only) |
| POST | /api/auth/token | No | Login (shared password) → JWT |
| POST | /api/auth/refresh | No | Refresh access token (rotation, 10/min) |
| POST | /api/auth/otp/request | No | Send OTP email (3/min) |
| POST | /api/auth/otp/verify | No | Verify OTP → JWT (5/min) |
| GET | /api/auth/me | JWT | Current user info |
| GET | /api/items | JWT | List items (filters: source, topic, date, limit, offset) |
| GET | /api/items/count | JWT | Count matching items |
| GET | /api/items/today | JWT | Today's items by score |
| GET | /api/items/by-date/{date} | JWT | Items for specific date |
| GET | /api/items/trending | JWT | Trending items |
| GET | /api/items/top | JWT | Top items by score |
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
```

**Condensed Configuration** (~6 lines replacing ~40):
```markdown
## Configuration

All config via env vars. See `.env.example` for full list.

Key defaults: `OPENAI_BASE_URL=api.moonshot.cn/v1`, `OPENAI_MODEL=kimi-latest`, `EMBEDDING_MODEL=text-embedding-3-small`, `ENABLED_SOURCES=hackernews,arxiv,reddit,rss,github,huggingface`
Scheduler: HN+Reddit every 15min, RSS+GitHub+HF every 60min, arXiv daily 01:30 UTC. Circuit breaker: 3 failures → 1h cooldown.
Auth: Passwordless OTP via Resend API. `ADMIN_EMAIL` auto-promotes to admin. OTP expires in 10min. Shared password fallback (role=reader).
```

**Keep unchanged:**
- Testing section (lines 471-492)
- CI/CD Pipeline section (lines 494-512)
- Risk-Based Autonomy section (lines 514-521)

**Remove entirely:**
- Engineering Principles section (lines 522-531) — duplicated in CLAUDE.md
- Current State section (lines 533-807) — archived
- Development History table (lines 809-825) — archived

**Step 2: Verify the new file**

Run: `wc -l AGENTS.md`
Expected: ~240-260 lines

Run: `wc -c AGENTS.md`
Expected: ~12,000-16,000 bytes (down from 50,292)

**Step 3: Commit**

```bash
git add AGENTS.md
git commit -m "docs: slim AGENTS.md from 826 to ~250 lines (~70% reduction)

Trim file map to key files, condense schema/endpoints/config,
remove duplicated engineering principles, remove archived milestones.
Saves ~8,700 tokens of context window per session."
```

---

### Task 3: Trim MEMORY.md

**Files:**
- Modify: `~/.claude/projects/-home-paul-Documentos-proyectos-backend-ai-news-platform/memory/MEMORY.md`

**Step 1: Remove three sections**

Remove these sections from MEMORY.md:

1. **"Auth System" block** (lines 41-46) — covered in AGENTS.md Configuration section
2. **"Commit Style" block** (lines 48-51) — already in CLAUDE.md Quality Gates section
3. **"Context Window Tips" block** (lines 53-57) — meta-advice, not project knowledge

**Step 2: Verify**

Run: `wc -l ~/.claude/projects/-home-paul-Documentos-proyectos-backend-ai-news-platform/memory/MEMORY.md`
Expected: ~40 lines

**Step 3: No commit needed** — MEMORY.md is not tracked in git.

---

### Task 4: Final verification

**Step 1: Count lines across all auto-loaded files**

Run:
```bash
wc -l AGENTS.md CLAUDE.md ~/.claude/projects/-home-paul-Documentos-proyectos-backend-ai-news-platform/memory/MEMORY.md
```

Expected: ~350 total lines (down from ~944)

**Step 2: Count bytes**

Run:
```bash
wc -c AGENTS.md CLAUDE.md ~/.claude/projects/-home-paul-Documentos-proyectos-backend-ai-news-platform/memory/MEMORY.md
```

Expected: ~20,000 bytes total (down from ~57,000)

**Step 3: Verify milestone archive exists and has full content**

Run: `wc -l docs/milestone-history.md`
Expected: ~300 lines

**Step 4: Spot-check AGENTS.md has all required sections**

Verify these headings exist in AGENTS.md:
- `## Project Overview`
- `## Architecture`
- `### Data Flow`
- `## How to Run`
- `## File Map`
- `## Database Schema`
- `## API Endpoints`
- `## Configuration`
- `## Testing`
- `## CI/CD Pipeline`
- `## Risk-Based Autonomy`

Run: `grep '^##' AGENTS.md`

**Step 5: Final commit if any adjustments were made**

Only if adjustments were needed. Otherwise, done.
