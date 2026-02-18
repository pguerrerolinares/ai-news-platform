"""Tests for the RAG chat service."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

from src.core.config import Settings
from src.rag.chat import SYSTEM_PROMPT, ChatService


def _mock_settings(**overrides):
    defaults = {
        "openai_api_key": "sk-kimi-key",
        "openai_base_url": "https://api.moonshot.cn/v1",
        "openai_model": "kimi-latest",
        "embedding_api_key": "sk-embed-key",
        "embedding_base_url": "https://api.openai.com/v1",
        "embedding_model": "text-embedding-3-small",
        "embedding_dimensions": 1536,
        "telegram_bot_token": "",
        "telegram_chat_id": "",
        "telegram_alerts_enabled": False,
    }
    defaults.update(overrides)
    return Settings(**defaults)


def _make_news_item(
    title: str = "AI News",
    summary: str = "Summary text",
    url: str = "https://example.com",
    topic: str = "modelos",
):
    item = MagicMock()
    item.id = uuid.uuid4()
    item.title = title
    item.summary = summary
    item.url = url
    item.source = "hackernews"
    item.topic = topic
    item.published_at = datetime(2026, 2, 17, tzinfo=UTC)
    return item


class TestSystemPrompt:
    def test_is_spanish(self):
        assert "noticias" in SYSTEM_PROMPT
        assert "IA" in SYSTEM_PROMPT

    def test_mentions_sources(self):
        assert "fuentes" in SYSTEM_PROMPT.lower()


class TestBuildContext:
    def test_formats_items(self):
        items = [_make_news_item("Title 1", "Summary 1", "https://ex.com/1")]
        with patch("src.rag.chat.get_settings", return_value=_mock_settings()):
            service = ChatService()
        context = service._build_context(items)
        assert "Title 1" in context
        assert "Summary 1" in context
        assert "https://ex.com/1" in context

    def test_empty_items_returns_no_context(self):
        with patch("src.rag.chat.get_settings", return_value=_mock_settings()):
            service = ChatService()
        context = service._build_context([])
        assert "no se encontr" in context.lower() or "no hay" in context.lower()


class TestBuildSources:
    def test_returns_source_dicts(self):
        item = _make_news_item("Title", "Sum", "https://ex.com/1")
        with patch("src.rag.chat.get_settings", return_value=_mock_settings()):
            service = ChatService()
        sources = service._build_sources([item])
        assert len(sources) == 1
        assert sources[0]["title"] == "Title"
        assert sources[0]["url"] == "https://ex.com/1"


class TestChatStream:
    async def test_yields_token_events(self):
        mock_retriever = AsyncMock()
        mock_retriever.retrieve.return_value = [_make_news_item()]

        mock_llm_client = AsyncMock()

        chunk1 = MagicMock()
        chunk1.choices = [MagicMock()]
        chunk1.choices[0].delta.content = "Hello"
        chunk2 = MagicMock()
        chunk2.choices = [MagicMock()]
        chunk2.choices[0].delta.content = " world"
        chunk3 = MagicMock()
        chunk3.choices = [MagicMock()]
        chunk3.choices[0].delta.content = None

        # Create an async iterator for the stream
        class MockStream:
            def __init__(self):
                self.chunks = [chunk1, chunk2, chunk3]
                self.index = 0

            def __aiter__(self):
                return self

            async def __anext__(self):
                if self.index >= len(self.chunks):
                    raise StopAsyncIteration
                c = self.chunks[self.index]
                self.index += 1
                return c

        mock_llm_client.chat.completions.create.return_value = MockStream()

        mock_session = AsyncMock()

        with patch("src.rag.chat.get_settings", return_value=_mock_settings()):
            service = ChatService(
                retriever=mock_retriever,
                llm_client=mock_llm_client,
            )
            events = []
            async for event in service.chat_stream(mock_session, "What happened?"):
                events.append(event)

        token_events = [e for e in events if '"token"' in e]
        assert len(token_events) == 2
        assert any('"sources"' in e for e in events)
        assert events[-1] == "data: [DONE]\n\n"

    async def test_empty_question_yields_error(self):
        mock_session = AsyncMock()
        with patch("src.rag.chat.get_settings", return_value=_mock_settings()):
            service = ChatService()
            events = []
            async for event in service.chat_stream(mock_session, ""):
                events.append(event)
        assert any("error" in e.lower() for e in events)
        assert events[-1] == "data: [DONE]\n\n"

    async def test_no_results_still_streams(self):
        mock_retriever = AsyncMock()
        mock_retriever.retrieve.return_value = []

        mock_llm_client = AsyncMock()

        chunk = MagicMock()
        chunk.choices = [MagicMock()]
        chunk.choices[0].delta.content = "No information"
        chunk_end = MagicMock()
        chunk_end.choices = [MagicMock()]
        chunk_end.choices[0].delta.content = None

        class MockStream:
            def __init__(self):
                self.chunks = [chunk, chunk_end]
                self.index = 0

            def __aiter__(self):
                return self

            async def __anext__(self):
                if self.index >= len(self.chunks):
                    raise StopAsyncIteration
                c = self.chunks[self.index]
                self.index += 1
                return c

        mock_llm_client.chat.completions.create.return_value = MockStream()
        mock_session = AsyncMock()

        with patch("src.rag.chat.get_settings", return_value=_mock_settings()):
            service = ChatService(retriever=mock_retriever, llm_client=mock_llm_client)
            events = []
            async for event in service.chat_stream(mock_session, "anything"):
                events.append(event)

        assert len(events) > 0
        assert events[-1] == "data: [DONE]\n\n"

    async def test_llm_error_yields_error_event(self):
        mock_retriever = AsyncMock()
        mock_retriever.retrieve.return_value = [_make_news_item()]

        mock_llm_client = AsyncMock()
        mock_llm_client.chat.completions.create.side_effect = Exception("LLM error")

        mock_session = AsyncMock()

        with patch("src.rag.chat.get_settings", return_value=_mock_settings()):
            service = ChatService(retriever=mock_retriever, llm_client=mock_llm_client)
            events = []
            async for event in service.chat_stream(mock_session, "test"):
                events.append(event)

        assert any('"error"' in e for e in events)
        assert events[-1] == "data: [DONE]\n\n"
