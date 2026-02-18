"""Tests for the RAG retriever."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

from src.rag.retriever import Retriever


def _fake_embedding(dims: int = 1536) -> list[float]:
    return [0.1] * dims


def _make_news_item(title: str = "Test News", topic: str = "modelos"):
    item = MagicMock()
    item.id = uuid.uuid4()
    item.title = title
    item.summary = "Test summary"
    item.url = "https://example.com"
    item.source = "hackernews"
    item.topic = topic
    item.published_at = datetime.now(tz=UTC)
    return item


class TestRetrieve:
    async def test_returns_list_of_items(self):
        mock_embed = AsyncMock()
        mock_embed.embed_text.return_value = _fake_embedding()
        mock_session = AsyncMock()
        items = [_make_news_item("AI News 1"), _make_news_item("AI News 2")]
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = items
        mock_session.execute.return_value = mock_result

        retriever = Retriever(embedding_service=mock_embed)
        result = await retriever.retrieve(mock_session, "AI models")
        assert len(result) == 2
        mock_embed.embed_text.assert_called_once_with("AI models")

    async def test_passes_limit_and_topic(self):
        mock_embed = AsyncMock()
        mock_embed.embed_text.return_value = _fake_embedding()
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result

        retriever = Retriever(embedding_service=mock_embed)
        await retriever.retrieve(mock_session, "test", topic="modelos", limit=3)
        mock_session.execute.assert_called_once()

    async def test_empty_query_returns_empty(self):
        mock_embed = AsyncMock()
        mock_session = AsyncMock()

        retriever = Retriever(embedding_service=mock_embed)
        result = await retriever.retrieve(mock_session, "")
        assert result == []
        mock_embed.embed_text.assert_not_called()

    async def test_whitespace_query_returns_empty(self):
        mock_embed = AsyncMock()
        mock_session = AsyncMock()

        retriever = Retriever(embedding_service=mock_embed)
        result = await retriever.retrieve(mock_session, "   ")
        assert result == []

    async def test_embedding_error_returns_empty(self):
        mock_embed = AsyncMock()
        mock_embed.embed_text.side_effect = Exception("API error")
        mock_session = AsyncMock()

        retriever = Retriever(embedding_service=mock_embed)
        result = await retriever.retrieve(mock_session, "test query")
        assert result == []
