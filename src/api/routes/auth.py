"""API routes for authentication."""
import hmac

from fastapi import APIRouter, Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from src.api.auth import create_access_token, create_refresh_token, validate_refresh_token
from src.api.errors import APIError
from src.api.schemas import ErrorWrapper, RefreshRequest, TokenRequest, TokenResponseV2
from src.core.config import get_settings

router = APIRouter(prefix="/api/auth", tags=["auth"])
limiter = Limiter(key_func=get_remote_address)


@router.post("/token", response_model=TokenResponseV2, responses={401: {"model": ErrorWrapper}})
@limiter.limit("5/minute")
async def login(request: Request, body: TokenRequest) -> TokenResponseV2:
    """Authenticate and receive access + refresh tokens."""
    settings = get_settings()
    if not hmac.compare_digest(body.password, settings.shared_password):
        raise APIError(401, "INVALID_PASSWORD", "Invalid password")

    access_token = create_access_token(subject="user")
    refresh_token = create_refresh_token(subject="user")

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
    subject = validate_refresh_token(body.refresh_token)

    access_token = create_access_token(subject=subject)
    new_refresh_token = create_refresh_token(subject=subject)

    return TokenResponseV2(
        access_token=access_token,
        refresh_token=new_refresh_token,
        expires_in=settings.jwt_access_expire_minutes * 60,
    )
