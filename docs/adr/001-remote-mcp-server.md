# ADR-001: Remote MCP Server via Streamable-HTTP

**Date**: 2026-06-11
**Status**: Accepted
**Track**: B (medium risk — new public endpoint, no DB schema change)

## Context

The MCP server (`src/mcp/server.py`) was originally designed for local stdio transport (Claude Code CLI). Publishing it as a remote endpoint at `https://pguerrero.me/mcp` allows any MCP-compatible client (Claude.ai, third-party agents) to access news data without a local install.

Streamable-HTTP is the MCP-specified transport for remote servers: it uses a single `/mcp` path, HTTP POST for client→server messages, and SSE for server→client streaming. It is the successor to the deprecated SSE+POST dual-endpoint pattern.

## Decision

- Add `Dockerfile.mcp` that installs `.[api]` (which already includes `mcp~=1.13`) and runs `python -m src.mcp.server` with `MCP_TRANSPORT=streamable-http MCP_PORT=8001`.
- Add a `mcp` service to `docker-compose.coolify.yml` with:
  - Internal communication only: `MCP_API_BASE_URL=http://api:8000` (no internet round-trip)
  - Traefik router `mcp-https` with `PathPrefix(/mcp)` and explicit `priority=10` so it wins over the frontend catch-all
  - HTTP→HTTPS redirect reusing the existing `frontend-redirect` middleware
  - Resource limits: 0.5 CPU, 256 MB RAM (VPS is CX22: 2 vCPU, 4 GB)

## Abuse protections (rationale: "que no me tumben el server")

| Protection | Config | Rationale |
|---|---|---|
| Traefik rate-limit | average=3 req/s, burst=10, by source IP | MCP sessions are long-lived; 3 req/s is generous for legitimate use, blocks naive scrapers |
| CPU limit | 0.5 vCPU | Prevents one runaway LLM session from starving api/frontend |
| Memory limit | 256 MB | MCP server is stateless; 256 MB is ample, caps OOM risk |
| Internal API calls | `http://api:8000` (Docker network) | Avoids external traffic, latency, and SSRF surface |

## Alternatives considered

- **Expose stdio via socat**: Fragile, no auth, not supported by remote MCP clients.
- **Separate VPS**: Overkill for current traffic; CX22 has headroom with limits in place.
- **API key auth at Traefik level**: Deferred — MCP protocol has its own auth layer; add if needed.

## Consequences

- `https://pguerrero.me/mcp` is publicly reachable. Rate limiting is the primary abuse control until MCP-level auth is implemented.
- Health check uses `curl` accepting any HTTP response code (405/406 is correct MCP behaviour for GET on `/mcp`).
- If the MCP service crashes, frontend and API are unaffected (no reverse dependency).
