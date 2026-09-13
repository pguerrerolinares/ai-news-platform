"""Capture a screenshot of the Admin health panel with synthetic API responses.

Builds the frontend, serves it with `vite preview`, mocks every `/api/**`
call the Admin page makes (auth, health, freshness, pipeline-runs, audit)
and screenshots the page. Used as a design-review artifact for the
admin-salud spec (`.superpowers/fabrica/specs/admin-salud.spec.md` §5.4) —
not part of the production pipeline; out of scope of the test suite.

Usage:
    .venv/bin/python scripts/capture_admin_health.py
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

from playwright.sync_api import Route, sync_playwright

REPO_ROOT = Path(__file__).resolve().parent.parent
FRONTEND_DIR = REPO_ROOT / "frontend"
FIXTURES_DIR = REPO_ROOT / "tests" / "fixtures"
OUTPUT_PATH = REPO_ROOT / ".superpowers" / "fabrica" / "captures" / "admin-salud.png"
PREVIEW_PORT = 4173
PREVIEW_URL = f"http://localhost:{PREVIEW_PORT}"

_CORS_HEADERS = {
    "access-control-allow-origin": "*",
    "access-control-allow-headers": "*",
}

_HEALTH_ALERTS = json.loads((FIXTURES_DIR / "admin_health_sample.json").read_text())

_FRESHNESS = [
    {
        "source": "hackernews",
        "last_item_at": "2026-09-13T00:00:00Z",
        "hours_ago": 1.0,
        "status": "ok",
    },
    {"source": "reddit", "last_item_at": None, "hours_ago": None, "status": "dead"},
]

_PIPELINE_RUNS = [
    {
        "id": "11111111-1111-1111-1111-111111111111",
        "started_at": "2026-09-13T00:00:00Z",
        "duration_seconds": 12.3,
        "status": "success",
        "sources": ["hackernews"],
        "items_extracted": 10,
        "items_after_dedup": 9,
        "items_seen_filtered": 8,
        "items_classified": 7,
        "items_validated": 6,
        "items_stored": 6,
        "error_message": None,
        "correlation_id": "abc123",
    },
    {
        "id": "22222222-2222-2222-2222-222222222222",
        "started_at": "2026-09-12T23:30:00Z",
        "duration_seconds": 5.1,
        "status": "error",
        "sources": ["rss"],
        "items_extracted": 0,
        "items_after_dedup": 0,
        "items_seen_filtered": 0,
        "items_classified": 0,
        "items_validated": 0,
        "items_stored": 0,
        "error_message": "connection timeout",
        "correlation_id": "def456",
    },
    {
        "id": "33333333-3333-3333-3333-333333333333",
        "started_at": "2026-09-12T23:00:00Z",
        "duration_seconds": 8.0,
        "status": "interrupted",
        "sources": ["arxiv"],
        "items_extracted": 3,
        "items_after_dedup": 3,
        "items_seen_filtered": 3,
        "items_classified": 0,
        "items_validated": 0,
        "items_stored": 0,
        "error_message": None,
        "correlation_id": "ghi789",
    },
    {
        "id": "44444444-4444-4444-4444-444444444444",
        "started_at": "2026-09-12T22:30:00Z",
        "duration_seconds": 15.7,
        "status": "degraded",
        "sources": ["github"],
        "items_extracted": 5,
        "items_after_dedup": 5,
        "items_seen_filtered": 5,
        "items_classified": 5,
        "items_validated": 5,
        "items_stored": 5,
        "error_message": None,
        "correlation_id": "jkl012",
    },
]

_AUDIT = {
    "total_items": 6,
    "date_range": {"oldest": "2026-09-01T00:00:00Z", "newest": "2026-09-13T00:00:00Z"},
    "sources": [{"source": "hackernews", "count": 6, "last_item_at": "2026-09-13T00:00:00Z"}],
    "daily_breakdown": [{"date": "2026-09-13", "source": "hackernews", "count": 6}],
    "duplicates": {"duplicate_groups": 0, "extra_items": 0},
}


def _json_route(route: Route, body: object, *, headers: dict[str, str] | None = None) -> None:
    route.fulfill(
        status=200,
        content_type="application/json",
        headers={**_CORS_HEADERS, **(headers or {})},
        body=json.dumps(body),
    )


def _handle_api(route: Route) -> None:
    request = route.request
    url = request.url
    if request.method == "OPTIONS":
        route.fulfill(status=204, headers=_CORS_HEADERS)
        return

    if request.method == "POST" and "/api/auth/guest" in url:
        _json_route(
            route,
            {"access_token": "header.eyJleHAiOjk5OTk5OTk5OTl9.signature", "expires_in": 86400},
        )
        return
    if "/api/admin/health" in url:
        _json_route(route, _HEALTH_ALERTS)
        return
    if "/api/admin/freshness" in url:
        _json_route(route, _FRESHNESS)
        return
    if "/api/admin/pipeline-runs" in url:
        _json_route(route, _PIPELINE_RUNS, headers={"x-total-count": "4"})
        return
    if "/api/admin/audit" in url:
        _json_route(route, _AUDIT)
        return

    route.fulfill(status=404, headers=_CORS_HEADERS, body="{}")


def _wait_for_preview(timeout_s: float = 30.0) -> None:
    import urllib.error
    import urllib.request

    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        try:
            urllib.request.urlopen(PREVIEW_URL, timeout=1.0)  # noqa: S310 (localhost only)
            return
        except (urllib.error.URLError, ConnectionError):
            time.sleep(0.5)
    raise RuntimeError(f"vite preview did not come up on {PREVIEW_URL} within {timeout_s}s")


def main() -> None:
    # Trusted local dev tool, fixed argv, no user input.
    subprocess.run(  # noqa: S603
        ["bun", "run", "build"],  # noqa: S607
        cwd=FRONTEND_DIR,
        check=True,
    )

    preview = subprocess.Popen(  # noqa: S603
        ["bun", "run", "preview", "--port", str(PREVIEW_PORT), "--strictPort"],  # noqa: S607
        cwd=FRONTEND_DIR,
    )
    try:
        _wait_for_preview()

        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(viewport={"width": 1280, "height": 1400})
            page.route("**/api/**", _handle_api)
            page.goto(f"{PREVIEW_URL}/admin")

            alerts = page.locator("[data-testid=health-alert]")
            alerts.first.wait_for(state="visible", timeout=10_000)
            count = alerts.count()
            if count != len(_HEALTH_ALERTS):
                raise AssertionError(f"expected {len(_HEALTH_ALERTS)} health alerts, got {count}")

            body_text = page.locator("body").inner_text()
            for expected in ("CRITICAL", "WARNING", "interrupted", "degraded"):
                if expected not in body_text:
                    raise AssertionError(f"expected {expected!r} visible on page, not found")

            OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
            page.screenshot(path=str(OUTPUT_PATH), full_page=True)
            browser.close()
    finally:
        preview.terminate()
        preview.wait(timeout=10)

    print(f"Saved capture to {OUTPUT_PATH}")


if __name__ == "__main__":
    sys.exit(main())
