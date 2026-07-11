"""JWT authentication utilities for the API."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import jwt
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from src.api.errors import APIError
from src.core.config import get_settings
from src.core.logging import get_logger

security = HTTPBearer()
logger = get_logger(__name__)


@dataclass
class UserClaims:
    """Decoded JWT claims for an authenticated user."""

    sub: str
    role: str
    email: str


def create_access_token(
    subject: str = "user",
    role: str | None = None,
    email: str | None = None,
) -> str:
    """Create a short-lived JWT access token."""
    settings = get_settings()
    expire = datetime.now(tz=UTC) + timedelta(minutes=settings.jwt_access_expire_minutes)
    payload: dict[str, object] = {"sub": subject, "exp": expire, "type": "access"}
    if role is not None:
        payload["role"] = role
    if email is not None:
        payload["email"] = email
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def create_guest_token() -> str:
    """Create a short-lived guest JWT for unauthenticated visitors."""
    settings = get_settings()
    expire = datetime.now(tz=UTC) + timedelta(hours=24)
    payload: dict[str, object] = {
        "sub": f"guest:{uuid.uuid4().hex[:12]}",
        "exp": expire,
        "type": "access",
        "role": "guest",
        "jti": uuid.uuid4().hex,
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def _decode_access_claims(
    credentials: HTTPAuthorizationCredentials,
    *,
    allow_guest: bool,
) -> UserClaims:
    """Decode and validate an access JWT, returning UserClaims.

    Raises APIError 401 on any validation failure.
    When *allow_guest* is False, guest-role tokens are rejected with GUEST_NOT_ALLOWED.
    """
    settings = get_settings()
    try:
        payload = jwt.decode(
            credentials.credentials,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
        )
    except jwt.PyJWTError:
        raise APIError(401, "INVALID_TOKEN", "Invalid or expired token") from None

    if payload.get("type") not in ("access", None):
        raise APIError(401, "INVALID_TOKEN", "Token is not an access token")
    if not allow_guest and payload.get("role") == "guest":
        raise APIError(401, "GUEST_NOT_ALLOWED", "Authentication required")
    sub: str | None = payload.get("sub")
    if sub is None:
        raise APIError(401, "INVALID_TOKEN", "Invalid or expired token")
    return UserClaims(
        sub=sub,
        role=payload.get("role", "reader"),
        email=payload.get("email", ""),
    )


async def require_auth(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> UserClaims:
    """Verify JWT access token. Returns UserClaims on success, raises 401 on failure."""
    return _decode_access_claims(credentials, allow_guest=False)


async def require_auth_or_guest(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> UserClaims:
    """Accept both authenticated users and guest tokens."""
    return _decode_access_claims(credentials, allow_guest=True)
