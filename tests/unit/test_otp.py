"""Tests for src.api.otp — OTP generation and email sending."""

from __future__ import annotations

from unittest.mock import patch

import httpx
import pytest

from src.api.otp import generate_otp_code, send_otp_email


# ---------------------------------------------------------------------------
# generate_otp_code
# ---------------------------------------------------------------------------
class TestGenerateOtpCode:
    def test_returns_6_digit_string(self):
        code = generate_otp_code()
        assert len(code) == 6
        assert code.isdigit()

    def test_codes_are_zero_padded(self):
        codes = [generate_otp_code() for _ in range(1000)]
        assert all(len(c) == 6 for c in codes)

    def test_codes_vary(self):
        codes = {generate_otp_code() for _ in range(100)}
        assert len(codes) > 50


# ---------------------------------------------------------------------------
# send_otp_email
# ---------------------------------------------------------------------------
class TestSendOtpEmail:
    @pytest.fixture()
    def mock_settings_with_key(self):
        return type("S", (), {
            "resend_api_key": "re_test_key",
            "otp_from_email": "test@resend.dev",
            "otp_expire_minutes": 10,
        })()

    @pytest.fixture()
    def mock_settings_no_key(self):
        return type("S", (), {
            "resend_api_key": "",
            "otp_from_email": "test@resend.dev",
            "otp_expire_minutes": 10,
        })()

    async def test_sends_email_via_resend(self, mock_settings_with_key, respx_mock):
        respx_mock.post("https://api.resend.com/emails").mock(
            return_value=httpx.Response(200, json={"id": "email_123"}),
        )
        with patch("src.api.otp.get_settings", return_value=mock_settings_with_key):
            await send_otp_email("user@example.com", "123456")

        assert respx_mock.calls.call_count == 1
        req = respx_mock.calls[0].request
        assert b"123456" in req.content
        assert b"user@example.com" in req.content

    async def test_sends_correct_headers(self, mock_settings_with_key, respx_mock):
        respx_mock.post("https://api.resend.com/emails").mock(
            return_value=httpx.Response(200, json={"id": "email_123"}),
        )
        with patch("src.api.otp.get_settings", return_value=mock_settings_with_key):
            await send_otp_email("user@example.com", "123456")

        req = respx_mock.calls[0].request
        assert req.headers["authorization"] == "Bearer re_test_key"

    async def test_raises_on_resend_failure(self, mock_settings_with_key, respx_mock):
        respx_mock.post("https://api.resend.com/emails").mock(
            return_value=httpx.Response(500, text="Internal error"),
        )
        with (
            patch("src.api.otp.get_settings", return_value=mock_settings_with_key),
            pytest.raises(httpx.HTTPStatusError),
        ):
            await send_otp_email("user@example.com", "123456")

    async def test_skips_when_no_api_key(self, mock_settings_no_key, respx_mock):
        with patch("src.api.otp.get_settings", return_value=mock_settings_no_key):
            await send_otp_email("user@example.com", "123456")
        assert respx_mock.calls.call_count == 0
