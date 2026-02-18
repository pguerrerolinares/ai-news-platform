"""E2E tests for the login page."""

from __future__ import annotations

import pytest
from playwright.sync_api import Page, expect

from .conftest import setup_mock_routes

pytestmark = pytest.mark.e2e


def test_login_page_renders(mock_page: Page, base_url: str):
    mock_page.goto(base_url + "/login")
    expect(mock_page.locator("h1")).to_have_text("AI News Platform")
    expect(mock_page.locator("text=Ingresa para acceder al panel")).to_be_visible()
    expect(mock_page.locator("#password")).to_be_visible()
    expect(mock_page.locator("button[type='submit']")).to_be_visible()


def test_password_field_is_password_type(mock_page: Page, base_url: str):
    mock_page.goto(base_url + "/login")
    expect(mock_page.locator("#password")).to_have_attribute("type", "password")


def test_submit_disabled_with_empty_password(mock_page: Page, base_url: str):
    mock_page.goto(base_url + "/login")
    expect(mock_page.locator("button[type='submit']")).to_be_disabled()


def test_login_success_redirects_to_dashboard(mock_page: Page, base_url: str):
    mock_page.goto(base_url + "/login")
    mock_page.fill("#password", "correct_password")
    mock_page.click("button[type='submit']")
    mock_page.wait_for_url("**/dashboard")


def test_login_wrong_password_shows_error(page: Page, base_url: str):
    setup_mock_routes(page, login_status=401)
    page.goto(base_url + "/login")
    page.fill("#password", "wrong_password")
    page.click("button[type='submit']")
    expect(page.locator("text=Contrasena incorrecta")).to_be_visible()


def test_login_connection_error_shows_error(page: Page, base_url: str):
    page.route("**/api/auth/token", lambda route: route.abort())
    page.goto(base_url + "/login")
    page.fill("#password", "anything")
    page.click("button[type='submit']")
    expect(page.locator("text=Error de conexion")).to_be_visible()


def test_enter_submits_form(mock_page: Page, base_url: str):
    mock_page.goto(base_url + "/login")
    mock_page.fill("#password", "correct_password")
    mock_page.press("#password", "Enter")
    mock_page.wait_for_url("**/dashboard")
