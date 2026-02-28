"""Playwright E2E test fixtures.

Serves the Angular build via a local HTTP server with SPA fallback
and mocks all /api/** calls with page.route().
"""

from __future__ import annotations

import base64
import json
import os
import threading
import time
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Mock data
# ---------------------------------------------------------------------------


def _make_mock_token() -> str:
    """Create a JWT-like token that passes Angular's isAuthenticated() check."""
    header = (
        base64.urlsafe_b64encode(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
        .decode()
        .rstrip("=")
    )
    payload = (
        base64.urlsafe_b64encode(
            json.dumps({"sub": "admin", "exp": int(time.time()) + 86400}).encode()
        )
        .decode()
        .rstrip("=")
    )
    return f"{header}.{payload}.mock_signature"


MOCK_TOKEN = _make_mock_token()

MOCK_NEWS_ITEMS = [
    {
        "id": "item-1",
        "title": "New AI Model Released",
        "summary": "A revolutionary AI model was released today.",
        "url": "https://example.com/news/1",
        "source": "hackernews",
        "topic": "models",
        "relevance_score": 0.95,
        "dev_value_score": 0.88,
        "credibility_score": 0.92,
        "priority": 1,
        "trending": True,
        "published_at": "2026-02-17T10:00:00",
        "created_at": "2026-02-17T10:30:00",
        "author": "tech_author",
        "score": 150,
    },
    {
        "id": "item-2",
        "title": "Open Source Tool Launch",
        "summary": "A new open source developer tool.",
        "url": "https://example.com/news/2",
        "source": "reddit",
        "topic": "tools",
        "relevance_score": 0.80,
        "dev_value_score": 0.75,
        "credibility_score": 0.85,
        "priority": 2,
        "trending": False,
        "published_at": "2026-02-17T09:00:00",
        "created_at": "2026-02-17T09:30:00",
        "author": "dev_user",
        "score": 85,
    },
    {
        "id": "item-3",
        "title": "Research Paper on LLMs",
        "summary": None,
        "url": None,
        "source": "arxiv",
        "topic": "papers",
        "relevance_score": 0.70,
        "dev_value_score": None,
        "credibility_score": None,
        "priority": 3,
        "trending": False,
        "published_at": None,
        "created_at": "2026-02-17T08:30:00",
        "author": None,
        "score": None,
    },
]

MOCK_BRIEFING = {
    "date": "2026-02-17",
    "total_items": 120,
    "items_extracted": 120,
    "items_after_dedup": 85,
    "items_filtered": 45,
    "trending_count": 5,
    "duration_seconds": 42,
    "sources_used": {"sources": ["hackernews", "arxiv", "reddit"]},
    "generated_at": "2026-02-17T11:00:00",
    "items": MOCK_NEWS_ITEMS,
}

# ---------------------------------------------------------------------------
# SPA static server
# ---------------------------------------------------------------------------

_PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _find_dist_dir() -> Path:
    candidates = [
        _PROJECT_ROOT / "web" / "dist" / "web" / "browser",
        _PROJECT_ROOT / "web" / "dist" / "browser",
    ]
    for c in candidates:
        if (c / "index.html").exists():
            return c
    pytest.skip("Angular build not found - run 'ng build' first.")


class _SPAHandler(SimpleHTTPRequestHandler):
    """Serves static files; returns index.html for unknown paths (SPA fallback)."""

    def do_GET(self):  # noqa: N802
        path = self.translate_path(self.path)
        if os.path.isfile(path):
            return super().do_GET()
        self.path = "/index.html"
        return super().do_GET()

    def log_message(self, _format, *_args):
        pass  # suppress logs


@pytest.fixture(scope="session")
def base_url():
    dist_dir = _find_dist_dir()

    def handler(*a, **kw):
        return _SPAHandler(*a, directory=str(dist_dir), **kw)

    server = HTTPServer(("127.0.0.1", 0), handler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{port}"
    server.shutdown()


# ---------------------------------------------------------------------------
# API route mocking
# ---------------------------------------------------------------------------


def setup_mock_routes(
    page,
    *,
    login_status: int = 200,
    briefing: dict | None = None,
    briefing_status: int = 200,
    items: list | None = None,
    search: list | None = None,
):
    """Register page.route() handlers for all API endpoints."""
    _briefing = briefing if briefing is not None else MOCK_BRIEFING
    _items = items if items is not None else MOCK_NEWS_ITEMS
    _search = search if search is not None else MOCK_NEWS_ITEMS

    def handle_auth(route):
        if login_status == 200:
            route.fulfill(
                status=200,
                content_type="application/json",
                body=json.dumps({"access_token": MOCK_TOKEN, "token_type": "bearer"}),
            )
        else:
            route.fulfill(
                status=login_status,
                content_type="application/json",
                body=json.dumps({"detail": "Invalid credentials"}),
            )

    def handle_briefing(route):
        route.fulfill(
            status=briefing_status,
            content_type="application/json",
            body=json.dumps(_briefing),
        )

    def handle_items(route):
        route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps(_items),
        )

    def handle_search(route):
        route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps(_search),
        )

    def handle_briefings_list(route):
        route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps([_briefing]),
        )

    def handle_chat(route):
        body = (
            'data: {"token": "This week "}\n\n'
            'data: {"token": "several models "}\n\n'
            'data: {"token": "were released."}\n\n'
            'data: {"sources": [{"id": "1", "title": "New AI Model Released", '
            '"url": "https://example.com/news/1", "topic": "models"}]}\n\n'
            "data: [DONE]\n\n"
        )
        route.fulfill(
            status=200,
            content_type="text/event-stream",
            body=body,
        )

    page.route("**/api/auth/token", handle_auth)
    page.route("**/api/items/today*", handle_items)
    page.route("**/api/items?*", handle_items)

    def handle_topics(route):
        route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps(
                {
                    "topics": [
                        "models",
                        "tools",
                        "papers",
                        "products",
                        "open_source",
                        "agents",
                        "regulation",
                    ]
                }
            ),
        )

    page.route("**/api/briefings/*", handle_briefing)
    page.route("**/api/briefings", handle_briefings_list)
    page.route("**/api/search*", handle_search)
    page.route("**/api/chat", handle_chat)
    page.route("**/api/topics", handle_topics)


# ---------------------------------------------------------------------------
# Page fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def mock_page(page, base_url):
    """Page with all API routes mocked (happy-path). No auth token."""
    setup_mock_routes(page)
    return page


@pytest.fixture()
def authed_page(page, base_url):
    """Page with mocked APIs and a valid JWT pre-injected into localStorage."""
    setup_mock_routes(page)
    page.add_init_script(f"localStorage.setItem('ainews_token', '{MOCK_TOKEN}')")
    return page
