# ADR-003: structlog over stdlib logging

## Status: Accepted
## Date: 2026-02-17

## Context
The predecessor uses stdlib `logging` with basic formatters. For a production platform with pipeline runs, API requests, and background jobs running concurrently, we need structured logging with correlation IDs to trace requests across components.

## Decision
`structlog` with JSON output and correlation ID injection.

## Consequences
**Pros:**
- JSON-structured logs, machine-parseable
- Correlation IDs across pipeline runs and API requests
- Context variables (via contextvars) for automatic enrichment
- Easy to add fields (source, duration, item_count) per log entry
- Console renderer for development, JSON for production

**Cons:**
- Additional dependency
- Slightly different API from stdlib logging
- Team needs to learn structlog patterns
