"""API route for available topics."""

from fastapi import APIRouter, Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from src.core.config import get_settings

router = APIRouter(prefix="/api/topics", tags=["topics"])
limiter = Limiter(key_func=get_remote_address)


@router.get("")
@limiter.limit("30/minute")
async def get_topics(request: Request) -> dict[str, list[str]]:
    """Return the list of configured topics. No auth required."""
    settings = get_settings()
    return {"topics": settings.topics_list}
