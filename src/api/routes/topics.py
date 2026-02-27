"""API route for available topics."""

from fastapi import APIRouter, Request
from slowapi import Limiter

from src.api.ratelimit import get_client_ip
from src.core.config import get_settings

router = APIRouter(prefix="/api/topics", tags=["topics"])
limiter = Limiter(key_func=get_client_ip)


@router.get("")
@limiter.limit("30/minute")
async def get_topics(request: Request) -> dict[str, list[str]]:
    """Return the list of configured topics. No auth required."""
    settings = get_settings()
    return {"topics": settings.topics_list}
