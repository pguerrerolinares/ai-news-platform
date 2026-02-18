# ADR-002: httpx over requests

## Status: Accepted
## Date: 2026-02-17

## Context
The predecessor project uses `requests` (sync) and `aiohttp` (async validation). Having two HTTP libraries adds complexity. We need a single async-first HTTP client.

## Decision
`httpx` as the sole HTTP client library.

## Consequences
**Pros:**
- Single library for all HTTP needs (extraction, validation, LLM API)
- Native async support (`httpx.AsyncClient`)
- `requests`-compatible API (easy migration)
- Built-in timeout, retry, and connection pooling
- Replaces both `requests` and `aiohttp`

**Cons:**
- Slightly less battle-tested than `requests` for sync use
- Different from predecessor (requires rewrite of extractors)
