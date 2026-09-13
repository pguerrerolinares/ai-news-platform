# Context Optimization Design

> **Date**: 2026-02-27 | **Status**: Approved

## Problem

The AI-feeding documentation (AGENTS.md, CLAUDE.md, MEMORY.md) consumes ~14,200 tokens
of context window on every Claude Code session. AGENTS.md alone is 826 lines / ~12,500
tokens (~88% of auto-loaded context). This causes conversations to hit context limits
and compress/lose information sooner, reducing usable working context.

## Constraints

- Every session must have full project context without extra file reads.
- Single-file approach preferred (AGENTS.md stays monolithic, just slimmer).

## Approach: Slim AGENTS.md

Aggressively trim AGENTS.md in-place and archive historical content to a separate file.

### 1. Archive milestone history → `docs/milestone-history.md`

**Remove from AGENTS.md entirely** (no summary table):
- All milestone checklists with `[x]` items (M0-M8, M14-M16, Scheduling, Auth)
- All "Key design decisions" blocks per milestone
- Development History table
- Angular-era details (M6, M7, M8 — deprecated frontend)
- "Next Tasks" section (belongs in backlog)

**New file**: `docs/milestone-history.md` (~500 lines). Never auto-loaded. Available
for reference when needed.

### 2. Trim File Map → key files only (~40 lines from ~210)

- Top-level directory structure with 1-line descriptions
- Individual files listed only for `core/`, `api/`, and `pipeline/` (most navigated)
- Other directories (`extractors/`, `classifiers/`, `frontend/`, etc.) get 1-line summaries

### 3. Condense Database Schema (~15 lines from ~80)

- Inline column lists instead of tables
- Keep index info in compact form
- Drop obvious "Notes" column details

### 4. Condense API Endpoints (~22 lines from ~35)

- Drop Milestone and Status columns (everything is Done)
- Collapse `/api/stats/*` into a single row
- Keep Method, Path, Auth, Description

### 5. Condense Configuration (~6 lines from ~40)

- Key defaults on 2 lines
- Scheduler summary on 1 line
- Auth summary on 1 line
- Point to `.env.example` for full list

### 6. Remove duplicated sections

- **Engineering Principles**: already in CLAUDE.md, remove from AGENTS.md
- **Development History table**: redundant with archived milestones

### 7. Trim MEMORY.md (~40 lines from ~57)

- Remove "Auth System" block (covered in AGENTS.md)
- Remove "Commit Style" block (already in CLAUDE.md)
- Remove "Context Window Tips" (meta-advice, not project knowledge)

### 8. CLAUDE.md — no changes

Already concise at 61 lines / ~750 tokens.

## Projected Result

| File | Before | After | Savings |
|------|--------|-------|---------|
| AGENTS.md | 826 lines / ~12,500 tokens | ~250 lines / ~3,800 tokens | ~70% |
| MEMORY.md | 57 lines / ~950 tokens | ~40 lines / ~650 tokens | ~30% |
| CLAUDE.md | 61 lines / ~750 tokens | 61 lines (unchanged) | 0% |
| **Total auto-loaded** | **~14,200 tokens** | **~5,200 tokens** | **~63%** |

New file: `docs/milestone-history.md` (~500 lines, never auto-loaded).

## What stays in AGENTS.md (unchanged)

- Project Overview (~17 lines)
- Architecture + Data Flow diagrams (~23 lines)
- How to Run (~20 lines)
- Testing section (~15 lines)
- CI/CD Pipeline (~15 lines)
- Risk-Based Autonomy (~10 lines)
- API conventions (pagination, errors, auth tokens, chat SSE contract)

## Risks

- **Information loss**: Agents working on specific subsystems may need to read extra
  files occasionally. Mitigated by keeping all key entry points in the trimmed file map.
- **Stale archive**: `docs/milestone-history.md` won't be maintained. Acceptable since
  it's purely historical reference.
