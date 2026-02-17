"""E2E tests for the analytics page."""

from __future__ import annotations

import pytest
from playwright.sync_api import Page, expect

pytestmark = pytest.mark.e2e


def test_analytics_page_renders_charts(authed_page: Page, base_url: str):
    authed_page.goto(base_url + "/analytics")
    expect(authed_page.locator("text=Items por dia")).to_be_visible()
    expect(authed_page.locator("text=Distribucion por tema")).to_be_visible()
    expect(authed_page.locator("text=Fuentes")).to_be_visible()


def test_analytics_accessible_from_nav(authed_page: Page, base_url: str):
    authed_page.goto(base_url + "/dashboard")
    authed_page.click("a[href='/analytics']")
    authed_page.wait_for_url("**/analytics")
    expect(authed_page.locator("text=Items por dia")).to_be_visible()
