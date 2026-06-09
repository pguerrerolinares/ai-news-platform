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

# Production endpoint
claude mcp add ai-news \
  --env MCP_API_BASE_URL=https://pguerrero.me \
  -- python -m src.mcp.server
```

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
        "MCP_API_BASE_URL": "https://pguerrero.me"
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

| Operation          | Works? |
|--------------------|--------|
| Search (keyword)   | Yes    |
| Semantic search    | Yes    |
| Latest items       | Yes    |
| Trending items     | Yes    |
| Daily briefing     | Yes    |
| Chat / RAG         | No — requires full user auth |

The server exposes **read-only** tools. There is no chat tool because the RAG
chat endpoint requires a full authenticated user session.

---

## Available tools (5 total)

| Tool              | Description                                                                    |
|-------------------|--------------------------------------------------------------------------------|
| `search_news`     | Keyword search across all indexed articles                                     |
| `semantic_search` | Vector/embedding search — finds conceptually related articles without exact keyword matches |
| `get_latest`      | Today's most recent items (optionally filtered by topic)                       |
| `get_trending`    | Items with the highest engagement score right now                              |
| `get_briefing`    | Daily pipeline summary with stats and top articles                             |

### Example prompts

```
Search my AI news for "mixture of experts"
Find articles semantically similar to "inference optimization at scale"
What's trending in AI news today?
Get the latest news about LLM agents
Show me the daily briefing for 2026-06-10
What were the top items from last Monday?
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
- Prod: verify `https://pguerrero.me` is reachable and the backend container
  is healthy (`docker ps` in Coolify).

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
