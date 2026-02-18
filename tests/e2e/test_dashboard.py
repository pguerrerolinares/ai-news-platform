"""E2E tests for the dashboard page."""

from __future__ import annotations

import pytest
from playwright.sync_api import Page, expect

from .conftest import MOCK_TOKEN

pytestmark = pytest.mark.e2e


def test_shows_news_items(authed_page: Page, base_url: str):
    authed_page.goto(base_url + "/dashboard")
    expect(authed_page.locator("text=New AI Model Released")).to_be_visible()
    expect(authed_page.locator("text=Open Source Tool Launch")).to_be_visible()
    expect(authed_page.locator("text=Research Paper on LLMs")).to_be_visible()
    # Source badges
    expect(authed_page.locator("[data-source='hackernews']").first).to_be_visible()
    expect(authed_page.locator("[data-source='reddit']").first).to_be_visible()
    expect(authed_page.locator("[data-source='arxiv']").first).to_be_visible()
    # Score
    expect(authed_page.locator("text=150 pts")).to_be_visible()
    # Topic badge
    expect(authed_page.locator(".topic-badge", has_text="modelos").first).to_be_visible()
    # Summary
    expect(authed_page.locator("text=A revolutionary AI model")).to_be_visible()


def test_shows_stats_bar(authed_page: Page, base_url: str):
    authed_page.goto(base_url + "/dashboard")
    stats = authed_page.locator(".stats-bar")
    expect(stats).to_be_visible()
    expect(stats.locator("text=Extraidas")).to_be_visible()
    expect(stats.locator("text=120")).to_be_visible()
    expect(stats.locator("text=Dedup")).to_be_visible()
    expect(stats.locator("text=85")).to_be_visible()
    expect(stats.locator("text=Filtradas")).to_be_visible()
    expect(stats.locator("text=45")).to_be_visible()
    expect(stats.locator("text=Trending")).to_be_visible()
    expect(stats.get_by_text("5", exact=True)).to_be_visible()


def test_shows_topic_distribution(authed_page: Page, base_url: str):
    authed_page.goto(base_url + "/dashboard")
    expect(authed_page.locator("text=Distribucion por tema")).to_be_visible()
    expect(authed_page.locator(".topic-chip", has_text="modelos")).to_be_visible()
    expect(authed_page.locator(".topic-chip", has_text="herramientas")).to_be_visible()
    expect(authed_page.locator(".topic-chip", has_text="papers")).to_be_visible()


def test_empty_state(page: Page, base_url: str):
    page.route(
        "**/api/briefings/*",
        lambda route: route.fulfill(status=404, body='{"detail":"Not found"}'),
    )
    page.route(
        "**/api/items/today*",
        lambda route: route.fulfill(status=200, content_type="application/json", body="[]"),
    )
    page.add_init_script(f"localStorage.setItem('ainews_token', '{MOCK_TOKEN}')")
    page.goto(base_url + "/dashboard")
    expect(page.locator("text=No hay noticias disponibles hoy")).to_be_visible()


def test_links_open_in_new_tab(authed_page: Page, base_url: str):
    authed_page.goto(base_url + "/dashboard")
    link = authed_page.locator("article a[target='_blank']").first
    expect(link).to_be_visible()
    expect(link).to_have_attribute("target", "_blank")
