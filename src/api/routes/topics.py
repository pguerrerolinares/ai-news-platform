"""API route for available topics."""

from fastapi import APIRouter, Depends, Request, Response
from slowapi import Limiter

from src.api.auth import UserClaims, require_auth_or_guest
from src.api.caching import set_cache_header
from src.api.ratelimit import get_client_ip
from src.core.config import get_settings

router = APIRouter(prefix="/api/topics", tags=["topics"])
limiter = Limiter(key_func=get_client_ip)


@router.get("")
@limiter.limit("30/minute")
async def get_topics(
    request: Request,
    response: Response,
    _user: UserClaims = Depends(require_auth_or_guest),
) -> dict[str, list[str]]:
    """Return the list of configured topics. Requires auth or a guest token."""
    settings = get_settings()
    set_cache_header(response)
    return {"topics": settings.topics_list}
