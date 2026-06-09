"""API route for available topics."""

from fastapi import APIRouter, Depends, Request
from slowapi import Limiter

from src.api.auth import UserClaims, require_auth_or_guest
from src.api.ratelimit import get_client_ip
from src.core.config import get_settings

router = APIRouter(prefix="/api/topics", tags=["topics"])
limiter = Limiter(key_func=get_client_ip)


@router.get("")
@limiter.limit("30/minute")
async def get_topics(
    request: Request,
    _user: UserClaims = Depends(require_auth_or_guest),
) -> dict[str, list[str]]:
    """Return the list of configured topics. Requires auth or a guest token."""
    settings = get_settings()
    return {"topics": settings.topics_list}
