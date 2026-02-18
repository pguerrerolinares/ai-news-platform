"""API route for available topics."""

from fastapi import APIRouter

from src.core.config import get_settings

router = APIRouter(prefix="/api/topics", tags=["topics"])


@router.get("")
async def get_topics() -> dict[str, list[str]]:
    """Return the list of configured topics. No auth required."""
    settings = get_settings()
    return {"topics": settings.topics_list}
