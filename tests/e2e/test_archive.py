"""E2E tests for the archive page."""

from __future__ import annotations

import pytest
from playwright.sync_api import Page, expect

from .conftest import MOCK_TOKEN

pytestmark = pytest.mark.e2e


def test_date_picker_present(authed_page: Page, base_url: str):
    authed_page.goto(base_url + "/archive")
    date_input = authed_page.locator("#archive-date")
    expect(date_input).to_be_visible()
    expect(date_input).to_have_attribute("type", "date")
    # max should be set (today's date)
    assert authed_page.locator("#archive-date").get_attribute("max") is not None


def test_shows_empty_initially(authed_page: Page, base_url: str):
    """Archive page shows empty message before any date change."""
    authed_page.goto(base_url + "/archive")
    expect(authed_page.locator("text=No hay noticias para esta fecha")).to_be_visible()


def test_date_change_loads_data(authed_page: Page, base_url: str):
    authed_page.goto(base_url + "/archive")
    authed_page.fill("#archive-date", "2026-02-16")
    # Items should appear
    expect(authed_page.locator("text=New AI Model Released")).to_be_visible()
    # Stats bar should appear
    expect(authed_page.locator(".stats-bar")).to_be_visible()
    expect(authed_page.locator("text=Extraidas")).to_be_visible()


def test_date_change_404_shows_error(page: Page, base_url: str):
    page.route(
        "**/api/briefings/*",
        lambda route: route.fulfill(
            status=404,
            content_type="application/json",
            body='{"detail":"Not found"}',
        ),
    )
    page.add_init_script(f"localStorage.setItem('ainews_token', '{MOCK_TOKEN}')")
    page.goto(base_url + "/archive")
    page.fill("#archive-date", "2025-01-01")
    expect(page.locator("text=No hay briefing para esta fecha")).to_be_visible()
