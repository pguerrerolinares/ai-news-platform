"""Integration tests for RAG — embeddings, retrieval, and chat via pgvector."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy import func, select

from src.core.models import ItemEmbedding
from src.rag.chat import ChatService
from src.rag.embeddings import EmbeddingService
from src.rag.retriever import Retriever
from tests.integration.conftest import seed_embedding, seed_news_item

pytestmark = [pytest.mark.integration, pytest.mark.asyncio(loop_scope="session")]


class TestEmbeddingStorage:
    async def test_store_and_retrieve_by_similarity(self, db_session):
        """Items with embeddings can be retrieved by cosine similarity."""
        item_a = await seed_news_item(db_session, title="Close Match", url="https://x.com/close")
        item_b = await seed_news_item(db_session, title="Far Match", url="https://x.com/far")

        # item_a: vector pointing "right" — item_b: vector pointing "left"
        vec_a = [1.0] + [0.0] * 1535
        vec_b = [-1.0] + [0.0] * 1535
        await seed_embedding(db_session, item_a, vector=vec_a)
        await seed_embedding(db_session, item_b, vector=vec_b)

        # Query vector similar to item_a
        query_vec = [0.9] + [0.0] * 1535

        mock_embed = AsyncMock(spec=EmbeddingService)
        mock_embed.embed_text.return_value = query_vec

        retriever = Retriever(embedding_service=mock_embed)
        results = await retriever.retrieve(db_session, "test query", limit=2)

        assert len(results) == 2
        assert results[0].title == "Close Match"
        assert results[1].title == "Far Match"

    async def test_retrieve_with_topic_filter(self, db_session):
        """Retriever respects topic filter."""
        item_a = await seed_news_item(
            db_session,
            title="Models Item",
            topic="models",
            url="https://x.com/topic-a",
        )
        item_b = await seed_news_item(
            db_session,
            title="Tools Item",
            topic="tools",
            url="https://x.com/topic-b",
        )

        vec = [0.5] * 1536
        await seed_embedding(db_session, item_a, vector=vec)
        await seed_embedding(db_session, item_b, vector=vec)

        mock_embed = AsyncMock(spec=EmbeddingService)
        mock_embed.embed_text.return_value = vec

        retriever = Retriever(embedding_service=mock_embed)
        results = await retriever.retrieve(db_session, "test", limit=10, topic="models")

        assert len(results) == 1
        assert results[0].topic == "models"

    async def test_retrieve_empty_table(self, db_session):
        """Retriever returns [] when no embeddings exist."""
        mock_embed = AsyncMock(spec=EmbeddingService)
        mock_embed.embed_text.return_value = [0.1] * 1536

        retriever = Retriever(embedding_service=mock_embed)
        results = await retriever.retrieve(db_session, "anything")

        assert results == []


class TestEmbedNewItems:
    async def test_new_items_get_embeddings(self, db_session):
        """embed_new_items stores vectors for items without embeddings."""
        from src.pipeline.stages.store import embed_new_items

        for i in range(3):
            await seed_news_item(
                db_session,
                title=f"Embed Test {i}",
                url=f"https://x.com/embed-new-{i}",
            )

        mock_embed = AsyncMock(spec=EmbeddingService)
        mock_embed.prepare_text = EmbeddingService.prepare_text
        mock_embed.embed_batch.return_value = [[0.3] * 1536] * 3

        count = await embed_new_items(db_session, embed_service=mock_embed)

        assert count == 3
        result = await db_session.execute(select(func.count(ItemEmbedding.item_id)))
        assert result.scalar_one() == 3


class TestChatStream:
    async def test_returns_sse_events(self, db_session):
        """ChatService.chat_stream yields SSE token + sources + [DONE]."""
        # Seed item + embedding
        item = await seed_news_item(db_session, title="Chat Context Item", url="https://x.com/chat")
        await seed_embedding(db_session, item, vector=[0.5] * 1536)

        # Mock embedding service (for retriever query embedding)
        mock_embed = AsyncMock(spec=EmbeddingService)
        mock_embed.embed_text.return_value = [0.5] * 1536

        # Mock LLM stream: one chunk with content, then stop
        mock_chunk = MagicMock()
        mock_chunk.choices = [MagicMock()]
        mock_chunk.choices[0].delta.content = "Respuesta"

        async def _fake_stream():
            yield mock_chunk

        mock_llm = MagicMock()
        mock_llm.chat.completions.create = AsyncMock(return_value=_fake_stream())

        retriever = Retriever(embedding_service=mock_embed)
        service = ChatService(retriever=retriever, llm_client=mock_llm)

        events = []
        async for event in service.chat_stream(db_session, "test question"):
            events.append(event)

        # Should have: token event + sources + done
        assert len(events) == 3

        # Helper to extract data dict from SSE frame
        def parse_sse_data(raw: str) -> dict:
            for line in raw.strip().split("\n"):
                if line.startswith("data: "):
                    return json.loads(line[len("data: ") :])
            raise ValueError(f"No data line in SSE event: {raw!r}")

        # First event: token
        first = parse_sse_data(events[0])
        assert first["type"] == "token"
        assert first["content"] == "Respuesta"

        # Second event: sources
        sources = parse_sse_data(events[1])
        assert sources["type"] == "sources"
        assert len(sources["content"]) == 1
        assert sources["content"][0]["title"] == "Chat Context Item"

        # Last event: done
        done = parse_sse_data(events[2])
        assert "id" in done
        assert events[2].startswith("event: done")
