"""E2E tests for the chat page."""

from __future__ import annotations

import pytest
from playwright.sync_api import Page, expect

pytestmark = pytest.mark.e2e


def test_chat_page_elements(authed_page: Page, base_url: str):
    authed_page.goto(base_url + "/chat")
    expect(authed_page.locator(".chat-input")).to_be_visible()
    expect(authed_page.locator(".send-btn")).to_be_visible()
    expect(authed_page.locator(".topic-filter")).to_be_visible()


def test_empty_state_shows_suggestions(authed_page: Page, base_url: str):
    authed_page.goto(base_url + "/chat")
    expect(authed_page.locator(".empty-state")).to_be_visible()
    expect(authed_page.locator("text=Chat con IA")).to_be_visible()
    expect(authed_page.locator(".suggestion-chip").first).to_be_visible()


def test_send_button_disabled_when_empty(authed_page: Page, base_url: str):
    authed_page.goto(base_url + "/chat")
    expect(authed_page.locator(".send-btn")).to_be_disabled()


def test_send_message_shows_response(authed_page: Page, base_url: str):
    authed_page.goto(base_url + "/chat")
    authed_page.fill(".chat-input", "What models were released?")
    authed_page.click(".send-btn")
    expect(authed_page.locator(".message.user")).to_be_visible()
    expect(authed_page.locator(".message.assistant")).to_be_visible(timeout=5000)


def test_suggestion_chip_sends_question(authed_page: Page, base_url: str):
    authed_page.goto(base_url + "/chat")
    authed_page.click(".suggestion-chip >> nth=0")
    expect(authed_page.locator(".message.user")).to_be_visible(timeout=5000)


def test_sources_displayed(authed_page: Page, base_url: str):
    authed_page.goto(base_url + "/chat")
    authed_page.fill(".chat-input", "test query for sources")
    authed_page.click(".send-btn")
    expect(authed_page.locator(".source-link").first).to_be_visible(timeout=5000)
