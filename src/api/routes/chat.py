"""API route for RAG chat with streaming SSE responses."""

from functools import lru_cache

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from slowapi import Limiter
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.auth import UserClaims, require_auth
from src.api.ratelimit import get_client_ip
from src.api.schemas import ChatRequest, ErrorWrapper
from src.core.database import get_session
from src.rag.chat import ChatService

router = APIRouter(prefix="/api/chat", tags=["chat"])

limiter = Limiter(key_func=get_client_ip)


@lru_cache
def _get_chat_service() -> ChatService:
    return ChatService()


@router.post("", responses={401: {"model": ErrorWrapper}})
@limiter.limit("10/minute")
async def chat(
    request: Request,
    body: ChatRequest,
    session: AsyncSession = Depends(get_session),
    _user: UserClaims = Depends(require_auth),
) -> StreamingResponse:
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
