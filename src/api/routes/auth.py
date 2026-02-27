"""API routes for authentication."""

import hmac

from fastapi import APIRouter, Request
from slowapi import Limiter
from src.api.ratelimit import get_client_ip

from src.api.auth import create_access_token, create_refresh_token, validate_refresh_token
from src.api.errors import APIError
from src.api.schemas import ErrorWrapper, RefreshRequest, TokenRequest, TokenResponseV2
from src.core.config import get_settings

router = APIRouter(prefix="/api/auth", tags=["auth"])
limiter = Limiter(key_func=get_client_ip)


@router.post("/token", response_model=TokenResponseV2, responses={401: {"model": ErrorWrapper}})
@limiter.limit("5/minute")
async def login(request: Request, body: TokenRequest) -> TokenResponseV2:
    """Authenticate and receive access + refresh tokens."""
    settings = get_settings()
    if not hmac.compare_digest(body.password, settings.shared_password):
        raise APIError(401, "INVALID_PASSWORD", "Invalid password")

    access_token = create_access_token(subject="legacy", role="reader")
    refresh_token = create_refresh_token(subject="legacy", role="reader")

    return TokenResponseV2(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=settings.jwt_access_expire_minutes * 60,
    )


@router.post("/refresh", response_model=TokenResponseV2, responses={401: {"model": ErrorWrapper}})
@limiter.limit("10/minute")
async def refresh(request: Request, body: RefreshRequest) -> TokenResponseV2:
    """Exchange a refresh token for new access + refresh tokens."""
    settings = get_settings()
    claims = validate_refresh_token(body.refresh_token)

    access_token = create_access_token(
        subject=claims.sub,
        role=claims.role,
        email=claims.email,
    )
    new_refresh_token = create_refresh_token(
        subject=claims.sub,
        role=claims.role,
        email=claims.email,
    )

    return TokenResponseV2(
        access_token=access_token,
        refresh_token=new_refresh_token,
        expires_in=settings.jwt_access_expire_minutes * 60,
    )
