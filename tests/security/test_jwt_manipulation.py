"""Security tests for JWT manipulation attacks."""

from __future__ import annotations

import base64
import json
import time

import jwt
import pytest
from httpx import AsyncClient

from src.core.config import get_settings

pytestmark = [pytest.mark.security, pytest.mark.asyncio(loop_scope="session")]

# Target endpoint — any protected route works
_PROTECTED = "/api/items"


class TestJWTManipulation:
    """Adversarial JWT attacks that must all be rejected with 401."""

    async def test_algorithm_none(self, security_client: AsyncClient) -> None:
        """Token with alg=none must be rejected (algorithm confusion attack)."""
        header = (
            base64.urlsafe_b64encode(json.dumps({"alg": "none", "typ": "JWT"}).encode())
            .decode()
            .rstrip("=")
        )
        payload = (
            base64.urlsafe_b64encode(
                json.dumps({"sub": "attacker", "exp": int(time.time()) + 3600}).encode()
            )
            .decode()
            .rstrip("=")
        )
        fake_token = f"{header}.{payload}."

        resp = await security_client.get(
            _PROTECTED, headers={"Authorization": f"Bearer {fake_token}"}
        )
        assert resp.status_code == 401

    async def test_algorithm_confusion_hs384(self, security_client: AsyncClient) -> None:
        """Token signed with HS384 when server expects HS256 must be rejected."""
        settings = get_settings()
        token = jwt.encode(
            {"sub": "attacker", "exp": int(time.time()) + 3600},
            settings.jwt_secret,
            algorithm="HS384",
        )

        resp = await security_client.get(_PROTECTED, headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 401

    async def test_forged_signature(self, security_client: AsyncClient) -> None:
        """Valid payload with a forged (wrong-secret) signature must be rejected."""
        token = jwt.encode(
            {"sub": "attacker", "exp": int(time.time()) + 3600},
            "wrong-secret-key",
            algorithm="HS256",
        )

        resp = await security_client.get(_PROTECTED, headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 401

    async def test_expired_token(self, security_client: AsyncClient) -> None:
        """Expired token must be rejected."""
        settings = get_settings()
        token = jwt.encode(
            {"sub": "user", "exp": int(time.time()) - 3600},
            settings.jwt_secret,
            algorithm="HS256",
        )

        resp = await security_client.get(_PROTECTED, headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 401

    async def test_missing_sub_claim(self, security_client: AsyncClient) -> None:
        """Token without 'sub' claim must be rejected."""
        settings = get_settings()
        token = jwt.encode(
            {"exp": int(time.time()) + 3600, "role": "admin"},
            settings.jwt_secret,
            algorithm="HS256",
        )

        resp = await security_client.get(_PROTECTED, headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 401

    async def test_tampered_payload(self, security_client: AsyncClient) -> None:
        """Token with payload modified after signing must be rejected."""
        settings = get_settings()
        token = jwt.encode(
            {"sub": "user", "exp": int(time.time()) + 3600},
            settings.jwt_secret,
            algorithm="HS256",
        )
        # Tamper: replace payload section with a different one
        parts = token.split(".")
        tampered_payload = (
            base64.urlsafe_b64encode(
                json.dumps({"sub": "admin", "exp": int(time.time()) + 3600}).encode()
            )
            .decode()
            .rstrip("=")
        )
        tampered_token = f"{parts[0]}.{tampered_payload}.{parts[2]}"

        resp = await security_client.get(
            _PROTECTED, headers={"Authorization": f"Bearer {tampered_token}"}
        )
        assert resp.status_code == 401
