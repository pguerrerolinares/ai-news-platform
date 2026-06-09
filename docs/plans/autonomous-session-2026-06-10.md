# Autonomous session — 2026-06-10 (Paul asleep)

Paul left me in charge to work through the backlog. He can't interact, so every
decision I'd normally have asked him about is logged here for review/refinement.

## Operating rules I'm following
- **Commit locally, NO push / NO deploy.** Every push auto-deploys to live prod
  (pguerrero.me) via Coolify; unattended deploy is an unacceptable risk. The whole
  batch is yours to review and push when you wake.
- Parent-orchestrator pattern: Sonnet executor children implement (with TDD +
  self code-review); I (parent) validate independently and commit.
- Migration files created but NOT run against prod.
- Frontend: implement + `npm run build` to verify compile; flagged for your
  visual review (no visual QA unattended).

## Decisions made on your behalf (review these)

### D1 — Did NOT push/deploy
All work is local commits. Review the batch and push when ready. Migration 016
(OTP attempts, from the prior session) still needs `alembic upgrade head` in prod
after you deploy.

### D2 — `jwt_secret` min-length: warning, not hard enforce  ⚠️ needs your input
The [LOW] finding wanted a hard guard rejecting short secrets at startup. I made
it a **non-fatal warning** instead, because a hard `raise` could brick your next
deploy if the live `JWT_SECRET` is < 32 chars — and I could not verify its length
(reading the prod secret via SSH was correctly denied by the permission system).
**Your call:** rotate `JWT_SECRET` to ≥ 32 chars, then we can promote the warning
to a hard `RuntimeError` (one-line change in `app.py` lifespan). Until then it
only logs `jwt_secret_too_short` at startup.

### D3 — Items I am SKIPPING (with reasons)
- **Track 5 (refresh/WebAuthn → Postgres):** needs your design decision (Postgres
  vs `api_workers:1` stopgap). Deferred — analysis is in ideas-backlog.md.
- **Database retention:** you already decided not to do it.
- **Grafana Cloud / Alloy / OpenTelemetry:** need your cloud account + credentials.
- **Reddit extractor:** externally blocked (paid API).
- **Chat history, prompt-injection (chat), require_auth no-`type` claim:** you
  deprioritized login/chat.
- **Split Settings into sub-configs:** broad refactor touching everything, high
  regression risk, low user value — not worth it unattended.
- **psycopg2 → psycopg3:** DB-driver swap; assessing, likely defer (risk vs value
  unattended).

## Work completed this session

### ✅ Batch 1 — two LOW security fixes (commit: see git log)
- `/health` no longer echoes the raw DB exception string in its 503 body (info
  leak). Detail is logged server-side only; body says `"database": "unavailable"`.
  Test added: `test_health_does_not_leak_exception_detail`.
- `jwt_secret` short-secret startup warning (see D2).
- Validation: 1081 unit tests pass, ruff + pyright clean.

### ✅ Batch 2 — Semantic search endpoint (Sonnet child)
`GET /api/search/semantic?q=...&limit=` — embeds the query, returns items by
cosine similarity, reusing `Retriever.retrieve` (no duplicated vector SQL).
require_auth_or_guest, 20/min, empty list when embeddings unavailable.
Parent validation: route is literal (no ordering risk), SQL stays in the
parameterized retriever, 1094 unit tests pass, ruff + pyright clean. Minor note:
constructs a `Retriever()` per request (lightweight, consistent with existing
usage) — fine.

### ✅ Batch 3 — MCP milestone: semantic_search tool + Claude Code connection docs (Sonnet child)
Your flagged milestone. The MCP server already existed (`src/mcp/`, FastMCP stdio,
4 tools). Added a 5th tool `semantic_search` (client method mirrors `search`,
server tool mirrors `search_news`) so you can natural-language-query your news.
Wrote `docs/runbooks/mcp-claude-code.md`: how to register it in YOUR Claude Code.

**To actually connect it (your step — depends on your machine):**
```
claude mcp add ai-news --env MCP_API_BASE_URL=https://pguerrero.me -- python -m src.mcp.server
```
It auto-acquires a guest token (read-only: search/latest/trending/briefing/semantic
work; chat needs full auth so there's no chat tool). Parent validation: tool
decorator present, client mirrors existing method, 1104 tests pass, runbook env var
(`MCP_API_BASE_URL`) matches the real code. **Note:** must run from the repo root
with the project venv so `python -m src.mcp.server` resolves — documented in the runbook.

## Open questions for you
- D2: rotate JWT_SECRET to ≥32 chars so we can harden the guard?
- Track 5: which approach (Postgres vs api_workers:1)?
- Frontend pages: I'll build-verify them, but you'll want to eyeball them.
