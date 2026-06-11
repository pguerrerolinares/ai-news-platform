"""JWT authentication utilities for the API."""

from __future__ import annotations

import hashlib
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

# In-memory store: hash -> expiry timestamp (bounded, auto-pruned)
_refresh_tokens: dict[str, float] = {}
_MAX_REFRESH_TOKENS = 100


@dataclass
class UserClaims:
    """Decoded JWT claims for an authenticated user."""

    sub: str
    role: str
    email: str


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _prune_expired() -> None:
    """Remove expired refresh token hashes from the store."""
    now = datetime.now(tz=UTC).timestamp()
    expired = [h for h, exp in _refresh_tokens.items() if exp < now]
    for h in expired:
        del _refresh_tokens[h]


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


def create_refresh_token(
    subject: str = "user",
    role: str | None = None,
    email: str | None = None,
) -> str:
    """Create a long-lived JWT refresh token."""
    settings = get_settings()
    expire = datetime.now(tz=UTC) + timedelta(days=settings.jwt_refresh_expire_days)
    payload: dict[str, object] = {
        "sub": subject,
        "exp": expire,
        "type": "refresh",
        "jti": uuid.uuid4().hex,
    }
    if role is not None:
        payload["role"] = role
    if email is not None:
        payload["email"] = email
    token = jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)

    _prune_expired()
    if len(_refresh_tokens) >= _MAX_REFRESH_TOKENS:
        oldest = min(_refresh_tokens, key=_refresh_tokens.get)  # type: ignore[arg-type]
        del _refresh_tokens[oldest]
    _refresh_tokens[_hash_token(token)] = expire.timestamp()
    return token


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


def validate_refresh_token(token: str) -> UserClaims:
    """Validate a refresh token. Returns UserClaims or raises APIError.

    Decodes JWT first (verifying signature/expiry), then checks the hash store.
    """
    settings = get_settings()

    # 1. Verify JWT signature and expiry first
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
        )
    except jwt.PyJWTError:
        raise APIError(401, "INVALID_TOKEN", "Invalid or expired refresh token") from None

    if payload.get("type") != "refresh":
        raise APIError(401, "INVALID_TOKEN", "Token is not a refresh token")
    sub = payload.get("sub")
    if sub is None:
        raise APIError(401, "INVALID_TOKEN", "Invalid token payload")

    # 2. Check hash store (rotation/revocation)
    token_hash = _hash_token(token)
    if token_hash not in _refresh_tokens:
        raise APIError(401, "INVALID_TOKEN", "Refresh token has been revoked")

    # 3. Rotate: invalidate old refresh token
    del _refresh_tokens[token_hash]
    return UserClaims(
        sub=sub,
        role=payload.get("role", "reader"),
        email=payload.get("email", ""),
    )


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


async def require_admin(
    user: UserClaims = Depends(require_auth),
) -> UserClaims:
    """Verify user has admin role."""
    if user.role != "admin":
        raise APIError(403, "FORBIDDEN", "Admin access required")
    return user


async def require_auth_or_guest(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> UserClaims:
    """Accept both authenticated users and guest tokens."""
    return _decode_access_claims(credentials, allow_guest=True)
