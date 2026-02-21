"""API routes for authentication."""

import hmac

from fastapi import APIRouter, Request
from src.api.errors import APIError
from slowapi import Limiter
from slowapi.util import get_remote_address

from src.api.auth import create_access_token
from src.api.schemas import TokenRequest, TokenResponse
from src.core.config import get_settings

router = APIRouter(prefix="/api/auth", tags=["auth"])

limiter = Limiter(key_func=get_remote_address)


@router.post("/token", response_model=TokenResponse)
@limiter.limit("5/minute")
async def login(request: Request, body: TokenRequest) -> TokenResponse:
    """Authenticate with a shared password and receive a JWT token.

    The password is compared against ``settings.shared_password``.
    On success a bearer token is returned; on failure HTTP 401 is raised.
    Uses timing-safe comparison to prevent timing attacks.
    """
    settings = get_settings()
    if not hmac.compare_digest(body.password, settings.shared_password):
        raise APIError(401, "INVALID_PASSWORD", "Invalid password")

    access_token = create_access_token(subject="user")
    return TokenResponse(access_token=access_token)
