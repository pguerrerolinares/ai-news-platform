"""Embedding service using OpenAI text-embedding-3-small.

Generates vector embeddings for news items and queries.
"""

from __future__ import annotations

import openai

from src.core.config import get_settings
from src.core.logging import get_logger

logger = get_logger(__name__)

_BATCH_SIZE = 100
_MAX_CHARS = 30000  # ~8K tokens rough limit


class EmbeddingService:
    """Generate embeddings via OpenAI API."""

    def __init__(self, client: openai.AsyncOpenAI | None = None) -> None:
        settings = get_settings()
        if client is not None:
            self._client = client
        else:
            self._client = openai.AsyncOpenAI(
                api_key=settings.embedding_api_key,
                base_url=settings.embedding_base_url,
            )
        self._model = settings.embedding_model

    @staticmethod
    def prepare_text(title: str, summary: str | None) -> str:
        """Combine title and summary into embedding input text."""
        parts = [title]
        if summary:
            parts.append(summary)
        return "\n".join(parts)

    async def embed_text(self, text: str) -> list[float]:
        """Embed a single text string. Returns a list of floats."""
        truncated = text[:_MAX_CHARS]
        response = await self._client.embeddings.create(
            model=self._model,
            input=truncated,
            dimensions=512,
        )
        return response.data[0].embedding

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Embed multiple texts, batching API calls by _BATCH_SIZE."""
        if not texts:
            return []

        all_embeddings: list[list[float]] = []
        for i in range(0, len(texts), _BATCH_SIZE):
            batch = [t[:_MAX_CHARS] for t in texts[i : i + _BATCH_SIZE]]
            response = await self._client.embeddings.create(
                model=self._model,
                input=batch,
                dimensions=512,
            )
            all_embeddings.extend([d.embedding for d in response.data])

        return all_embeddings
