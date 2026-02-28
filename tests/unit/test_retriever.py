"""Tests for the RAG retriever."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

from src.rag.retriever import Retriever


def _fake_embedding(dims: int = 1536) -> list[float]:
    return [0.1] * dims


def _make_news_item(title: str = "Test News", topic: str = "models"):
    item = MagicMock()
    item.id = uuid.uuid4()
    item.title = title
    item.summary = "Test summary"
    item.url = "https://example.com"
    item.source = "hackernews"
    item.topic = topic
    item.published_at = datetime.now(tz=UTC)
    return item


def _mock_session_returning(items: list) -> AsyncMock:
    """Create a mock session where every execute() returns the given items."""
    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = items
    mock_session.execute.return_value = mock_result
    return mock_session


class TestRetrieve:
    async def test_returns_list_of_items(self):
        mock_embed = AsyncMock()
        mock_embed.embed_text.return_value = _fake_embedding()
        items = [_make_news_item(f"AI News {i}") for i in range(5)]
        mock_session = _mock_session_returning(items)

        retriever = Retriever(embedding_service=mock_embed)
        result = await retriever.retrieve(mock_session, "AI models")
        assert len(result) == 5
        mock_embed.embed_text.assert_called_once_with("AI models")
        # Only one DB call (recent search found enough items)
        mock_session.execute.assert_called_once()

    async def test_recency_fallback_when_not_enough_recent(self):
        """When recent search returns fewer than limit, falls back to full range."""
        mock_embed = AsyncMock()
        mock_embed.embed_text.return_value = _fake_embedding()
        recent_items = [_make_news_item("Recent")]
        all_items = [_make_news_item(f"Item {i}") for i in range(5)]

        mock_session = AsyncMock()
        recent_result = MagicMock()
        recent_result.scalars.return_value.all.return_value = recent_items
        full_result = MagicMock()
        full_result.scalars.return_value.all.return_value = all_items
        mock_session.execute.side_effect = [recent_result, full_result]

        retriever = Retriever(embedding_service=mock_embed)
        result = await retriever.retrieve(mock_session, "AI tools")
        assert len(result) == 5
        # Two DB calls: recent search + fallback
        assert mock_session.execute.call_count == 2

    async def test_passes_limit_and_topic(self):
        mock_embed = AsyncMock()
        mock_embed.embed_text.return_value = _fake_embedding()
        items = [_make_news_item(f"Item {i}") for i in range(3)]
        mock_session = _mock_session_returning(items)

        retriever = Retriever(embedding_service=mock_embed)
        result = await retriever.retrieve(mock_session, "test", topic="models", limit=3)
        assert len(result) == 3
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

    async def test_no_matching_embeddings_returns_empty(self):
        """Query that embeds successfully but has no similar items in DB."""
        mock_embed = AsyncMock()
        mock_embed.embed_text.return_value = _fake_embedding()
        mock_session = _mock_session_returning([])

        retriever = Retriever(embedding_service=mock_embed)
        result = await retriever.retrieve(mock_session, "completely unrelated query")
        assert result == []
        mock_embed.embed_text.assert_called_once_with("completely unrelated query")
        # Two calls: recent (empty) + fallback (empty)
        assert mock_session.execute.call_count == 2

    async def test_custom_recency_days(self):
        mock_embed = AsyncMock()
        mock_embed.embed_text.return_value = _fake_embedding()
        items = [_make_news_item(f"Item {i}") for i in range(5)]
        mock_session = _mock_session_returning(items)

        retriever = Retriever(embedding_service=mock_embed)
        result = await retriever.retrieve(mock_session, "test", recency_days=7)
        assert len(result) == 5
        mock_session.execute.assert_called_once()
