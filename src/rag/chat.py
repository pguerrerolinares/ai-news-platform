"""RAG chat service — retrieve context and stream LLM answers."""

from __future__ import annotations

import asyncio
import json
import uuid
from collections.abc import AsyncGenerator

import openai
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import get_settings
from src.core.logging import get_logger
from src.core.models import NewsItem
from src.rag.retriever import Retriever

logger = get_logger(__name__)

SYSTEM_PROMPT = (
    "Eres un asistente experto en noticias de IA y tecnologia. "
    "Responde basandote SOLO en las noticias proporcionadas como contexto. "
    "Si no hay informacion relevante, dilo claramente. "
    "Incluye las fuentes (titulos y URLs) en tu respuesta. "
    "Responde en espanol."
)


class ChatService:
    """Stream chat answers using RAG: retrieve context, then query LLM."""

    def __init__(
        self,
        retriever: Retriever | None = None,
        llm_client: openai.AsyncOpenAI | None = None,
    ) -> None:
        settings = get_settings()
        self._retriever = retriever or Retriever()
        if llm_client is not None:
            self._llm = llm_client
        else:
            self._llm = openai.AsyncOpenAI(
                api_key=settings.openai_api_key,
                base_url=settings.openai_base_url,
            )
        self._model = settings.openai_model

    @staticmethod
    def _generate_msg_id() -> str:
        """Generate a unique message ID: msg_<12 hex chars>."""
        return f"msg_{uuid.uuid4().hex[:12]}"

    @staticmethod
    def _sse_event(event_type: str, data: dict[str, object]) -> str:
        """Format a single SSE frame with event type and JSON data."""
        return f"event: {event_type}\ndata: {json.dumps(data)}\n\n"

    def _build_context(self, items: list[NewsItem]) -> str:
        """Format retrieved items as context for the LLM prompt."""
        if not items:
            return "No se encontraron noticias relevantes en la " "base de datos."

        lines: list[str] = []
        for i, item in enumerate(items, 1):
            parts = [f"[{i}] {item.title}"]
            if item.summary:
                parts.append(f"   Resumen: {item.summary}")
            if item.url:
                parts.append(f"   URL: {item.url}")
            if item.source:
                parts.append(f"   Fuente: {item.source}")
            if item.topic:
                parts.append(f"   Tema: {item.topic}")
            if item.published_at:
                parts.append(f"   Fecha: {item.published_at.strftime('%Y-%m-%d')}")
            lines.append("\n".join(parts))

        return "\n\n".join(lines)

    @staticmethod
    def _build_sources(items: list[NewsItem]) -> list[dict[str, str | None]]:
        """Build source list for the final SSE event."""
        return [
            {
                "id": str(item.id),
                "title": item.title,
                "url": item.url,
                "topic": item.topic,
            }
            for item in items
        ]

    async def chat_stream(
        self,
        session: AsyncSession,
        question: str,
        *,
        topic: str | None = None,
        limit: int = 5,
    ) -> AsyncGenerator[str, None]:
        """Stream OpenAI-style SSE events: tokens, sources, done."""
        msg_id = self._generate_msg_id()

        if not question.strip():
            msg = "La pregunta no puede estar vacia"
            yield self._sse_event(
                "error",
                {
                    "id": msg_id,
                    "error": {"code": "INVALID_INPUT", "message": msg},
                },
            )
            yield self._sse_event("done", {"id": msg_id})
            return

        # 1. Retrieve relevant context
        items = await self._retriever.retrieve(
            session,
            question,
            limit=limit,
            topic=topic,
        )
        context = self._build_context(items)

        # 2. Build user message with context
        user_message = (
            f"Contexto (noticias recientes):\n\n{context}\n\n" f"Pregunta del usuario: {question}"
        )

        # 3. Stream LLM response
        try:
            async with asyncio.timeout(30):
                stream = await self._llm.chat.completions.create(
                    model=self._model,
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": user_message},
                    ],
                    temperature=0.3,
                    stream=True,
                )

                async for chunk in stream:
                    content = chunk.choices[0].delta.content
                    if content:
                        yield self._sse_event(
                            "message",
                            {
                                "id": msg_id,
                                "type": "token",
                                "content": content,
                            },
                        )

        except TimeoutError:
            logger.error("chat_stream_timeout", question=question[:100])
            yield self._sse_event(
                "error",
                {
                    "id": msg_id,
                    "error": {
                        "code": "LLM_TIMEOUT",
                        "message": "AI response timed out",
                    },
                },
            )

        except Exception as exc:
            logger.error("chat_stream_error", error=str(exc))
            yield self._sse_event(
                "error",
                {
                    "id": msg_id,
                    "error": {
                        "code": "CHAT_ERROR",
                        "message": "Error al generar la respuesta",
                    },
                },
            )

        # 4. Send sources
        sources = self._build_sources(items)
        yield self._sse_event(
            "message",
            {
                "id": msg_id,
                "type": "sources",
                "content": sources,
            },
        )

        # 5. Done
        yield self._sse_event("done", {"id": msg_id})
