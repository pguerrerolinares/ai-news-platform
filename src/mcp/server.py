"""MCP server for AI News Platform.

Run with: python -m src.mcp.server
"""

from __future__ import annotations

import os
import threading

from mcp.server.fastmcp import FastMCP
from src.mcp.client import APIClient

mcp = FastMCP("AI News Platform")

_client: APIClient | None = None
_lock = threading.Lock()


def _get_client() -> APIClient:
    global _client
    if _client is None:
        with _lock:
            if _client is None:
                base_url = os.environ.get("MCP_API_BASE_URL", "http://localhost:8000")
                _client = APIClient(base_url=base_url)
    return _client


def _format_items(items: list[dict]) -> str:
    if not items:
        return "No items found."
    lines: list[str] = []
    for i, item in enumerate(items, 1):
        source = item.get("source", "?")
        title = item.get("title", "Untitled")
        topic = item.get("topic", "")
        score = item.get("score")
        summary = item.get("summary", "")
        url = item.get("url", "")

        header = f"{i}. [{source}] {title}"
        if score is not None:
            header += f" ({score} pts)"
        if topic:
            header += f" [{topic}]"

        lines.append(header)
        if summary:
            lines.append(f"   {summary}")
        if url:
            lines.append(f"   {url}")
        lines.append("")
    return "\n".join(lines)


@mcp.tool()
def search_news(
    query: str,
    topic: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    limit: int = 10,
) -> str:
    """Search AI news articles by keyword.

    Returns matching items with title, source, topic, summary, and URL.
    """
    client = _get_client()
    items = client.search(q=query, topic=topic, date_from=date_from, date_to=date_to, limit=limit)
    header = f'Found {len(items)} results for "{query}"'
    if topic:
        header += f" (topic: {topic})"
    return f"{header}:\n\n{_format_items(items)}"


@mcp.tool()
def semantic_search(query: str, limit: int = 10) -> str:
    """Search AI news articles by semantic similarity (vector search).

    Uses embeddings to find articles conceptually related to the query,
    even without exact keyword matches. Returns matching items with title,
    source, topic, summary, and URL.
    """
    client = _get_client()
    items = client.semantic_search(q=query, limit=limit)
    return f'Found {len(items)} results for "{query}":\n\n{_format_items(items)}'


@mcp.tool()
def get_latest(topic: str | None = None, limit: int = 10) -> str:
    """Get the most recent AI news items from today."""
    client = _get_client()
    items = client.get_latest(topic=topic, limit=limit)
    return f"Latest {len(items)} items:\n\n{_format_items(items)}"


@mcp.tool()
def get_trending() -> str:
    """Get currently trending AI news items."""
    client = _get_client()
    items = client.get_trending()
    return f"Trending items ({len(items)}):\n\n{_format_items(items)}"


@mcp.tool()
def get_briefing(date: str | None = None) -> str:
    """Get the daily briefing summary with pipeline stats and top items."""
    client = _get_client()
    briefing = client.get_briefing(date=date)

    lines = [f"Daily Briefing — {briefing.get('date', 'today')}"]
    lines.append("=" * 40)

    keys = (
        "total_items",
        "items_extracted",
        "items_after_dedup",
        "items_filtered",
        "trending_count",
    )
    for key in keys:
        val = briefing.get(key)
        if val is not None:
            lines.append(f"  {key}: {val}")

    duration = briefing.get("duration_seconds")
    if duration:
        lines.append(f"  duration: {duration:.0f}s")

    items = briefing.get("items", [])
    if items:
        lines.append(f"\nTop {min(len(items), 5)} items:")
        lines.append(_format_items(items[:5]))

    return "\n".join(lines)


if __name__ == "__main__":
    mcp.run(transport="stdio")
