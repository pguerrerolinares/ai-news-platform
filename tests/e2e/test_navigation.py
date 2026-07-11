"""E2E tests for navigation, auth guards, and logout."""

from __future__ import annotations

import pytest
from playwright.sync_api import Page, expect

pytestmark = pytest.mark.e2e


def test_navbar_visible_on_authenticated_pages(authed_page: Page, base_url: str):
    authed_page.goto(base_url + "/dashboard")
    expect(authed_page.locator(".navbar")).to_be_visible()
    expect(authed_page.locator("text=AI News Platform").first).to_be_visible()
    expect(authed_page.locator("text=Dashboard")).to_be_visible()
    expect(authed_page.locator("text=Archivo")).to_be_visible()
    expect(authed_page.locator("text=Buscar")).to_be_visible()
    expect(authed_page.locator("text=Analytics")).to_be_visible()
    expect(authed_page.locator("text=Salir")).to_be_visible()


def test_nav_links_navigate(authed_page: Page, base_url: str):
    authed_page.goto(base_url + "/dashboard")

    # Navigate to Archive
    authed_page.click("a[href='/archive']")
    authed_page.wait_for_url("**/archive")
    expect(authed_page.locator("#archive-date")).to_be_visible()

    # Navigate to Search
    authed_page.click("a[href='/search']")
    authed_page.wait_for_url("**/search")
    expect(authed_page.locator(".search-input")).to_be_visible()

    # Navigate back to Dashboard
    authed_page.click("a[href='/dashboard']")
    authed_page.wait_for_url("**/dashboard")
