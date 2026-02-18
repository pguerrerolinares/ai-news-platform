"""API route for RAG chat with streaming SSE responses."""

from functools import lru_cache

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.auth import require_auth
from src.core.database import get_session
from src.rag.chat import ChatService

router = APIRouter(prefix="/api/chat", tags=["chat"])

limiter = Limiter(key_func=get_remote_address)


@lru_cache
def _get_chat_service() -> ChatService:
    return ChatService()


class ChatRequest(BaseModel):
    question: str = Field(..., min_length=3, max_length=500)
    topic: str | None = Field(None, description="Filter context by topic")
    limit: int = Field(5, ge=1, le=20, description="Number of context items")


@router.post("")
@limiter.limit("10/minute")
async def chat(
    request: Request,
    body: ChatRequest,
    session: AsyncSession = Depends(get_session),
    _user: str = Depends(require_auth),
):
    """Chat with AI about news. Returns SSE stream."""
    service = _get_chat_service()

    return StreamingResponse(
        service.chat_stream(
            session,
            body.question,
            topic=body.topic,
            limit=body.limit,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
