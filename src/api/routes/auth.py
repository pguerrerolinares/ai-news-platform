"""API routes for authentication."""

from fastapi import APIRouter, Request
from slowapi import Limiter

from src.api.auth import create_guest_token
from src.api.ratelimit import get_client_ip
from src.api.schemas import GuestTokenResponse

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
