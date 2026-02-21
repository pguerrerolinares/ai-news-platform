"""JWT authentication utilities for the API."""
from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime, timedelta

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

from src.api.errors import APIError
from src.core.config import get_settings

security = HTTPBearer()

# In-memory store for refresh token hashes (sufficient for single-user scale)
_refresh_tokens: set[str] = set()


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def create_access_token(subject: str = "user") -> str:
    """Create a short-lived JWT access token."""
    settings = get_settings()
    expire = datetime.now(tz=UTC) + timedelta(minutes=settings.jwt_access_expire_minutes)
    payload = {"sub": subject, "exp": expire, "type": "access"}
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def create_refresh_token(subject: str = "user") -> str:
    """Create a long-lived JWT refresh token."""
    settings = get_settings()
    expire = datetime.now(tz=UTC) + timedelta(days=settings.jwt_refresh_expire_days)
    payload = {"sub": subject, "exp": expire, "type": "refresh", "jti": uuid.uuid4().hex}
    token = jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    _refresh_tokens.add(_hash_token(token))
    return token


def validate_refresh_token(token: str) -> str:
    """Validate a refresh token. Returns subject or raises APIError."""
    settings = get_settings()
    token_hash = _hash_token(token)

    if token_hash not in _refresh_tokens:
        raise APIError(401, "INVALID_TOKEN", "Refresh token has been revoked or is invalid")

    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        if payload.get("type") != "refresh":
            raise APIError(401, "INVALID_TOKEN", "Token is not a refresh token")
        sub = payload.get("sub")
        if sub is None:
            raise APIError(401, "INVALID_TOKEN", "Invalid token payload")
        # Rotate: invalidate old refresh token
        _refresh_tokens.discard(token_hash)
        return sub
    except JWTError:
        _refresh_tokens.discard(token_hash)
        raise APIError(401, "INVALID_TOKEN", "Invalid or expired refresh token") from None


async def require_auth(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> str:
    """Verify JWT access token. Returns subject on success, raises 401 on failure."""
    settings = get_settings()
    try:
        payload = jwt.decode(
            credentials.credentials,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
        )
        if payload.get("type") not in ("access", None):
            raise APIError(401, "INVALID_TOKEN", "Token is not an access token")
        sub: str | None = payload.get("sub")
        if sub is None:
            raise APIError(401, "INVALID_TOKEN", "Invalid or expired token")
        return sub
    except JWTError:
        raise APIError(401, "INVALID_TOKEN", "Invalid or expired token") from None
