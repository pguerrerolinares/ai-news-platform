"""JWT authentication utilities for the API."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

from src.core.config import get_settings

security = HTTPBearer()


def create_access_token(subject: str = "user") -> str:
    """Create a JWT access token with expiration.

    Args:
        subject: The token subject (default "user").

    Returns:
        Encoded JWT string.
    """
    settings = get_settings()
    expire = datetime.now(tz=UTC) + timedelta(minutes=settings.jwt_expire_minutes)
    payload = {"sub": subject, "exp": expire}
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


async def require_auth(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> str:
    """Verify JWT token. Returns subject on success, raises 401 on failure."""
    settings = get_settings()
    try:
        payload = jwt.decode(
            credentials.credentials,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
        )
        sub: str | None = payload.get("sub")
        if sub is None:
            raise HTTPException(status_code=401, detail="Invalid or expired token")
        return sub
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token") from None
