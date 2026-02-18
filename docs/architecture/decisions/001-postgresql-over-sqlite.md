# ADR-001: PostgreSQL over SQLite

## Status: Accepted
## Date: 2026-02-17

## Context
The predecessor project (`x-news-summarizer`) uses JSON files for state management. The new platform needs concurrent access (pipeline writes + API reads), full-text search, and eventually vector search for RAG. We needed to choose between SQLite, PostgreSQL, and other databases.

## Decision
PostgreSQL 16 with pgvector extension.

## Consequences
**Pros:**
- True concurrent read/write (pipeline + API + frontend simultaneously)
- pgvector for RAG embeddings (Milestone 4) without additional infrastructure
- Full-text search via GIN indexes (no external search engine needed)
- Alembic migrations for schema versioning
- Production-grade reliability and ecosystem
- Fits in 300MB RAM budget on 4GB VPS

**Cons:**
- Requires Docker service (vs. SQLite embedded)
- Slightly more complex local development setup
- Backup strategy needed (pg_dump + Backblaze B2)
