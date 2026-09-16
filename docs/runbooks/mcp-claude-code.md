# MCP Server — Claude Code Integration Runbook

How to register the AI News Platform MCP server with Claude Code so you can
query your news platform directly from any Claude Code session.

---

## How the server starts

The entry point is `src/mcp/server.py`. The module-level docstring confirms the
launch command:

```
Run with: python -m src.mcp.server
```

The server speaks the MCP **stdio** transport (`mcp.run(transport="stdio")`),
which is the standard mode expected by Claude Code.

---

## Environment variables (read from `_get_client()`)

```python
# src/mcp/server.py
base_url = os.environ.get("MCP_API_BASE_URL", "http://localhost:8000")
_client = APIClient(base_url=base_url)
```

| Variable           | Required | Default                 | Notes                      |
|--------------------|----------|-------------------------|----------------------------|
| `MCP_API_BASE_URL` | No       | `http://localhost:8000` | Override for prod endpoint |

No credentials are required. The server auto-acquires a **guest token** via
`POST /api/auth/guest` on first use — that endpoint is unauthenticated by
design.

---

## Registering with Claude Code

### Option A — `claude mcp add` (recommended)

Run once from any directory inside the project:

```bash
# Local development (default base URL — no env override needed)
claude mcp add ai-news -- python -m src.mcp.server

# Production endpoint (API is mounted under /ai-news — see docs/MIGRATION-ai-news-path.md)
claude mcp add ai-news \
  --env MCP_API_BASE_URL=https://pguerrero.me/ai-news \
  -- python -m src.mcp.server
```

> This registers a **local** stdio server that calls the production REST API. To
> talk to the already-running **remote** MCP server instead (no local process),
> point your client at `https://pguerrero.me/ai-news/mcp` directly — see
> `docs/adr/001-remote-mcp-server.md`.

Claude Code saves this to `~/.claude/mcp_servers.json` and launches the process
automatically whenever an MCP-enabled session starts.

### Option B — `.mcp.json` in the project root

Create or extend `.mcp.json`:

```json
{
  "mcpServers": {
    "ai-news": {
      "command": "python",
      "args": ["-m", "src.mcp.server"],
      "env": {
        "MCP_API_BASE_URL": "https://pguerrero.me/ai-news"
      }
    }
  }
}
```

> The command must be run from the project root so that `src.mcp.server` is on
> the Python path. If you use the project virtualenv, replace `python` with the
> absolute path: `/path/to/project/.venv/bin/python`.

---

## Authentication model

The server calls `POST /api/auth/guest` on first use to obtain a short-lived
JWT. This token is cached in-process for the lifetime of the MCP server.

**Capabilities of the guest token:**

| Operation                          | Works? |
|-------------------------------------|--------|
| `search` (keyword or semantic)      | Yes    |
| `get_item`, `find_similar`          | Yes    |
| `topic_trend`, `get_top`            | Yes    |
| Chat / RAG (`POST /api/chat`)       | No — requires full user auth, not exposed as an MCP tool |

The server exposes **read-only** tools. There is no chat tool because the RAG
chat endpoint requires a full authenticated user session.

---

## Available tools (5 total, ADR-006)

| Tool          | Description                                                                                          |
|---------------|-------------------------------------------------------------------------------------------------------|
| `search`      | `query`, `mode=semantic\|keyword` (default semantic), `topic?`, `source?`, `date_from?`, `date_to?`, `limit≤50` — find AI news, papers and repos relevant to a query |
| `get_item`    | `item_id` — full record: untruncated `full_text`, `discussion_url`, `engagement`, `author`            |
| `find_similar`| `item_id`, `limit≤20` — semantic neighbours of an item (widen from a good hit)                        |
| `topic_trend` | `query`, `method=keyword\|semantic`, `granularity=week\|month`, `since?` — whether a topic is rising  |
| `get_top`     | `days=7`, `topic?`, `source?`, `limit≤50` — best-ranked items (`composite_score`) in a window          |

All 5 are read-only (`readOnlyHint=True`), return structured output, and reject invalid
arguments with an actionable error instead of an empty list (e.g. an unknown `topic`, an
inverted `date_from`/`date_to` range, or a query over 200 chars).

### Example prompts

```
Search my AI news for papers or repos on consolidating agent memory
Find articles semantically similar to "inference optimization at scale"
Is interest in spec-driven development for coding agents rising in the last 6 months?
Get the full text and engagement for item <id> from a previous search
What were the top items from the last 7 days in the "agents" topic?
```

---

## Troubleshooting

### Server fails to start — `ModuleNotFoundError: No module named 'src'`

The server must be launched from the project root, not from inside `src/`.
Ensure Claude Code's working directory or the `cwd` key in `.mcp.json` points
to the project root.

### `RuntimeError: MCP guest token acquisition failed: <status>`

The API server is not reachable at the configured `MCP_API_BASE_URL`.
- Local: ensure `uvicorn src.api.app:app` is running on port 8000.
- Prod: verify `https://pguerrero.me/ai-news` is reachable and the backend
  container is healthy (`docker ps` in Coolify).

### `ImportError: No module named 'mcp'`

The `mcp` package (FastMCP) is not installed in the Python environment being
used. Run:

```bash
.venv/bin/pip install mcp
# or check pyproject.toml for the correct dependency name
```

### Token expires mid-session

The in-process guest token is not refreshed automatically. Restart the MCP
server process (restart the Claude Code session or run `claude mcp restart
ai-news`).
