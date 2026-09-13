# ADR-005: Prefix matching in `/api/search` (lexemes of 3+ chars)

**Date**: 2026-09-13
**Status**: Accepted
**Track**: C (migration item, no schema change)

## Context

Migration 019 removes the ILIKE fallback from `search.py` (revision-2026-09-13.md #1): it
OR'd `%q%` over title/source/summary to compensate for plural/prefix queries (`agent` finding
"AI Agents", `LLM` finding "LLMs", `hacker` finding source `hackernews`) that whole-word FTS
misses. Dropping it without a replacement is a visible recall regression on the most common
query pattern in this domain (singular/plural, acronyms) for both the frontend and the MCP
`search_news` tool.

## Decision

Rewrite `plainto_tsquery('simple', q)` so lexemes of 3+ characters become prefix matches
(`'agent'` → `'agent':*`), while 1-2 char lexemes stay exact — via a `regexp_replace` on the
tsquery's text form, cast (not `to_tsquery`, which re-parses compound lexemes like `gpt-4o`
into lossy `<->` phrases) back to `tsquery`. Still uses the GIN index (`@@` with a prefix
tsquery is indexable); no schema change, one file (`search.py`), reversible with `git revert`.

Alternatives rejected: **(a) whole-word** — simplest, but the recall regression above is real
and visible. **(c) pg_trgm** — recovers substrings too, but a new extension + 2 more GIN
indexes paying every insert/upsert is disproportionate for a guest-only read app. **(d) `english`
config (stemming)** — fixes plurals but not prefixes (`hacker`→`hackernews`), and undoes
migration 017's deliberate move to `simple` for mixed ES/EN content.

## Consequences

- Covers the dominant pattern (plural/prefix) at zero schema cost.
- Does **not** cover plural→singular (`agents` doesn't find "agent") or substring interior
  matches — documented limit, not a bug. If this starts to hurt, the next step is pg_trgm as
  its own ADR, not a patch here.
- `search.py`/`AGENTS.md`/MCP `search_news` docstring updated to say "prefix match, 3+ chars".
