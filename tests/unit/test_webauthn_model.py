"""Tests for WebAuthnCredential model."""

from __future__ import annotations

from src.core.models import WebAuthnCredential


class TestWebAuthnCredentialModel:
    def test_tablename(self):
        assert WebAuthnCredential.__tablename__ == "webauthn_credentials"

    def test_has_required_columns(self):
        col_names = {c.name for c in WebAuthnCredential.__table__.columns}
        expected = {
            "id", "user_id", "credential_id", "public_key",
            "sign_count", "device_name", "transports", "backed_up",
            "last_used_at", "created_at",
        }
        assert expected.issubset(col_names)

    def test_credential_id_is_unique(self):
        col = WebAuthnCredential.__table__.c.credential_id
        assert col.unique is True

    def test_user_id_foreign_key(self):
        col = WebAuthnCredential.__table__.c.user_id
        fk = list(col.foreign_keys)
        assert len(fk) == 1
        assert "users.id" in str(fk[0].target_fullname)
