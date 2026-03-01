"""Tests for WebAuthn request/response schemas."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from src.api.schemas import (
    WebAuthnCredentialResponse,
    WebAuthnLoginOptionsRequest,
    WebAuthnRegisterVerifyRequest,
)


class TestWebAuthnLoginOptionsRequest:
    def test_valid_email(self):
        req = WebAuthnLoginOptionsRequest(email="user@example.com")
        assert req.email == "user@example.com"

    def test_invalid_email_rejected(self):
        with pytest.raises(ValidationError):
            WebAuthnLoginOptionsRequest(email="not-an-email")


class TestWebAuthnRegisterVerifyRequest:
    def test_requires_device_name_and_credential(self):
        req = WebAuthnRegisterVerifyRequest(
            device_name="My Phone",
            credential={"id": "abc", "response": {}},
        )
        assert req.device_name == "My Phone"

    def test_device_name_min_length(self):
        with pytest.raises(ValidationError):
            WebAuthnRegisterVerifyRequest(device_name="", credential={})


class TestWebAuthnCredentialResponse:
    def test_from_attributes(self):
        resp = WebAuthnCredentialResponse(
            id=uuid.uuid4(),
            device_name="Laptop",
            backed_up=False,
            created_at=datetime.now(tz=UTC),
            last_used_at=None,
        )
        assert resp.device_name == "Laptop"
