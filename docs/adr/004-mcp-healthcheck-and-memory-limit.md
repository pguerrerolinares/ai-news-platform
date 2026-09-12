# ADR-004: MCP healthcheck rewrite + memory limit fix

**Date**: 2026-09-13
**Status**: Accepted
**Track**: A (config + non-behavioral endpoint addition; no change to MCP tool semantics)

## Context

Two related production issues on the `mcp` service (`docker-compose.coolify.yml`):

1. **Unfalsifiable healthcheck**. The healthcheck was:
   ```
   curl -s -o /dev/null -w '%{http_code}' http://localhost:8001/mcp | grep -qE '^[0-9]+$' && exit 0 || exit 1
   ```
   `GET /mcp` legitimately returns `406` by MCP protocol design (Accept-header negotiation), and
   `%{http_code}` prints `000` when curl can't connect at all. Both match `^[0-9]+$`, so the check
   passed unconditionally — it never went unhealthy, including when the process was down.

2. **Restarts with no visible cause**. Before today's deploy, the `mcp` container had
   `RestartCount=15`, `ExitCode=0`, `OOMKilled=false` (last recorded state). `docker events`'
   in-memory ring buffer and per-container counters don't survive a redeploy, so that state told
   us nothing once the container was recreated.

   `journalctl -k` (kernel ring buffer, survives container recreation) showed the real cause:
   memcg OOM kills of the `mcp` container's main `python` process, at least 3 times in two weeks
   (2026-09-03, 2026-09-08, 2026-09-12), always at anon-rss ≈ 247-250MiB against a
   `deploy.resources.limits.memory: 256M` cap — only `mcp` has a memory limit in the compose file,
   every other service is uncapped, and the OOM'd cgroup path names the `mcp` container's own
   memory.max. On 2026-09-12 the allocation that tipped the cgroup over the edge was `curl` itself
   — the (broken) healthcheck's own `docker exec` shares the container's cgroup. Full evidence in
   `docs/runbooks/troubleshooting.md`.

## Decision

1. Add a dedicated `GET /health` route to the FastMCP server (`src/mcp/server.py`), registered via
   the SDK's own `@mcp.custom_route()` — the pattern the SDK's docstring recommends for exactly
   this ("health checks... intended to be public"). It returns a plain `{"status": "ok"}` with no
   MCP protocol semantics (no Accept-header negotiation, no session, no Host/DNS-rebinding check),
   so it only responds when the ASGI app is actually alive and routing.
2. Change the healthcheck to `curl -f http://localhost:8001/health` — `curl -f` fails on any
   non-2xx and on connection failure, unlike the old `%{http_code}` + regex.
3. Raise `mcp`'s `deploy.resources.limits.memory` from `256M` to `512M` — the steady-state
   footprint (~250MiB) left ~3MiB of headroom under the old cap, which is what made a healthcheck
   `curl` exec (or ordinary request-handling variance) enough to trigger an OOM kill.

## Alternatives considered

- **POST JSON-RPC `initialize` as the healthcheck** instead of a custom route: exercises the real
  protocol path, and works (`curl -X POST ... {"method":"initialize",...}` returns `200` against
  the live server). Rejected for the container healthcheck because (a) it's fragile in a
  `CMD-SHELL` string (JSON body escaping, `Accept: application/json, text/event-stream` header),
  and (b) every `initialize` call is intended to open an MCP session — running it every 30s forever
  adds protocol-level state/churn for a purpose (liveness) that doesn't need it. A dedicated
  `/health` route is simpler (KISS) and has zero session side effects. `initialize` remains a good
  *manual* smoke test (`curl -X POST .../mcp -H 'Accept: application/json, text/event-stream' -d
  '{"jsonrpc":"2.0","id":1,"method":"initialize",...}'`), just not the automated probe.
- **Only raise the memory limit, leave the healthcheck as-is**: rejected — the healthcheck was
  broken independently of the OOM issue (would still be unfalsifiable against a hang, a crash-loop
  before the process binds the port, or a future regression), and it's the more clear-cut
  root-cause fix of the two problems in scope.

## Consequences

- The healthcheck can now actually fail: verified locally that `curl -f http://.../health` against
  a dead port exits non-zero, while the old check against the same dead port exits `0` (see
  session report / commit message for the transcript).
- `mcp` now requests up to 512M instead of 256M — the host has 3.7GiB total / ~1.7GiB free, so this
  is not tight.
- Not resolved: *why* steady-state RSS is ~250MiB (vs. ~50MiB right after start) is undetermined —
  could be normal working-set growth or a slow leak. If restarts recur at 512M, this needs
  profiling (see runbook), not another limit bump.
- Rollback: revert the commit; both changes are config/endpoint-only, no data or schema impact.
