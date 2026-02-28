"""E2E tests for the search page."""

from __future__ import annotations

import json

import pytest
from playwright.sync_api import Page, expect

from .conftest import MOCK_NEWS_ITEMS, MOCK_TOKEN

pytestmark = pytest.mark.e2e


def test_search_form_elements(authed_page: Page, base_url: str):
    authed_page.goto(base_url + "/search")
    expect(authed_page.locator(".search-input")).to_be_visible()
    expect(authed_page.locator(".search-btn")).to_be_visible()
    expect(authed_page.locator("#topic-select")).to_be_visible()
    expect(authed_page.locator("#date-from")).to_be_visible()
    expect(authed_page.locator("#date-to")).to_be_visible()


def test_button_disabled_with_empty_query(authed_page: Page, base_url: str):
    authed_page.goto(base_url + "/search")
    expect(authed_page.locator(".search-btn")).to_be_disabled()


def test_search_shows_results(authed_page: Page, base_url: str):
    authed_page.goto(base_url + "/search")
    authed_page.fill(".search-input", "AI models")
    authed_page.click(".search-btn")
    expect(authed_page.locator("text=resultados para")).to_be_visible()
    expect(authed_page.locator("text=New AI Model Released")).to_be_visible()
    expect(authed_page.locator("text=Open Source Tool Launch")).to_be_visible()


def _mock_topics(page: Page):
    """Register a mock for GET /api/topics (needed since topics are loaded dynamically)."""
    page.route(
        "**/api/topics",
        lambda route: route.fulfill(
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
        ),
    )


def test_search_no_results_message(page: Page, base_url: str):
    page.route(
        "**/api/search*",
        lambda route: route.fulfill(status=200, content_type="application/json", body="[]"),
    )
    _mock_topics(page)
    page.add_init_script(f"localStorage.setItem('ainews_token', '{MOCK_TOKEN}')")
    page.goto(base_url + "/search")
    page.fill(".search-input", "nonexistent query")
    page.click(".search-btn")
    expect(page.locator("text=No se encontraron resultados")).to_be_visible()


def test_topic_filter_sends_parameter(page: Page, base_url: str):
    captured_urls: list[str] = []

    def capture_search(route):
        captured_urls.append(route.request.url)
        route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps(MOCK_NEWS_ITEMS),
        )

    page.route("**/api/search*", capture_search)
    _mock_topics(page)
    page.add_init_script(f"localStorage.setItem('ainews_token', '{MOCK_TOKEN}')")
    page.goto(base_url + "/search")
    page.select_option("#topic-select", "models")
    page.fill(".search-input", "test query")
    page.click(".search-btn")
    expect(page.locator("text=resultados para")).to_be_visible()
    assert any("topic=models" in url for url in captured_urls)
