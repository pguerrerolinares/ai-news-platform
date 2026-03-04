"""Tests for WebAuthn configuration settings."""

from __future__ import annotations

from src.core.config import Settings


class TestWebAuthnConfig:
    def test_default_rp_id(self):
        s = Settings(
            jwt_secret="x",
            database_url="postgresql+asyncpg://x:x@localhost/x",
            database_url_sync="postgresql://x:x@localhost/x",
        )
        assert s.webauthn_rp_id == "localhost"

    def test_default_rp_name(self):
        s = Settings(
            jwt_secret="x",
            database_url="postgresql+asyncpg://x:x@localhost/x",
            database_url_sync="postgresql://x:x@localhost/x",
        )
        assert s.webauthn_rp_name == "AI News"

    def test_default_origin(self):
        s = Settings(
            jwt_secret="x",
            database_url="postgresql+asyncpg://x:x@localhost/x",
            database_url_sync="postgresql://x:x@localhost/x",
        )
        assert s.webauthn_origin == "http://localhost:5173"

    def test_custom_values(self):
        s = Settings(
            jwt_secret="x",
            database_url="postgresql+asyncpg://x:x@localhost/x",
            database_url_sync="postgresql://x:x@localhost/x",
            webauthn_rp_id="pguerrero.me",
            webauthn_rp_name="My App",
            webauthn_origin="https://pguerrero.me",
        )
        assert s.webauthn_rp_id == "pguerrero.me"
        assert s.webauthn_rp_name == "My App"
        assert s.webauthn_origin == "https://pguerrero.me"
