"""API routes for authentication."""

from fastapi import APIRouter, Request
from slowapi import Limiter

from src.api.auth import (
    create_access_token,
    create_guest_token,
    create_refresh_token,
    validate_refresh_token,
)
from src.api.ratelimit import get_client_ip
from src.api.schemas import (
    ErrorWrapper,
    GuestTokenResponse,
    RefreshRequest,
    TokenResponseV2,
)
from src.core.config import get_settings

router = APIRouter(prefix="/api/auth", tags=["auth"])
limiter = Limiter(key_func=get_client_ip)


@router.post("/guest", response_model=GuestTokenResponse)
@limiter.limit("10/minute")
async def guest_token(request: Request) -> GuestTokenResponse:
    """Issue a guest token for unauthenticated visitors."""
    token = create_guest_token()
    return GuestTokenResponse(
        access_token=token,
        expires_in=24 * 3600,
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
