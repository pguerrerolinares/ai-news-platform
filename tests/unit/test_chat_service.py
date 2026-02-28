"""Tests for the RAG chat service."""

from __future__ import annotations

import json
import re
import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

from src.core.config import Settings
from src.rag.chat import SYSTEM_PROMPT, ChatService

MSG_ID_RE = re.compile(r"^msg_[0-9a-f]{12}$")


def _mock_settings(**overrides: object) -> Settings:
    defaults: dict[str, object] = {
        "openai_api_key": "sk-kimi-key",
        "openai_base_url": "https://api.moonshot.cn/v1",
        "openai_model": "kimi-latest",
        "embedding_api_key": "sk-embed-key",
        "embedding_base_url": "https://api.openai.com/v1",
        "embedding_model": "text-embedding-3-small",
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
    topic: str = "models",
) -> MagicMock:
    item = MagicMock()
    item.id = uuid.uuid4()
    item.title = title
    item.summary = summary
    item.url = url
    item.source = "hackernews"
    item.topic = topic
    item.published_at = datetime(2026, 2, 17, tzinfo=UTC)
    return item


def _parse_sse(raw: str) -> tuple[str | None, dict | None]:
    """Parse a single SSE frame into (event_type, data_dict)."""
    event_type: str | None = None
    data_line: str | None = None
    for line in raw.strip().split("\n"):
        if line.startswith("event: "):
            event_type = line[len("event: ") :]
        elif line.startswith("data: "):
            data_line = line[len("data: ") :]
    if data_line is not None:
        return event_type, json.loads(data_line)
    return event_type, None


class TestSystemPrompt:
    def test_is_english(self) -> None:
        assert "news" in SYSTEM_PROMPT
        assert "AI" in SYSTEM_PROMPT

    def test_mentions_sources(self) -> None:
        assert "sources" in SYSTEM_PROMPT.lower()


class TestBuildContext:
    def test_formats_items(self) -> None:
        items = [_make_news_item("Title 1", "Summary 1", "https://ex.com/1")]
        with patch("src.rag.chat.get_settings", return_value=_mock_settings()):
            service = ChatService()
        context = service._build_context(items)
        assert "Title 1" in context
        assert "Summary 1" in context
        assert "https://ex.com/1" in context

    def test_empty_items_returns_no_context(self) -> None:
        with patch("src.rag.chat.get_settings", return_value=_mock_settings()):
            service = ChatService()
        context = service._build_context([])
        assert "no relevant news" in context.lower()


class TestBuildSources:
    def test_returns_source_dicts(self) -> None:
        item = _make_news_item("Title", "Sum", "https://ex.com/1")
        with patch("src.rag.chat.get_settings", return_value=_mock_settings()):
            service = ChatService()
        sources = service._build_sources([item])
        assert len(sources) == 1
        assert sources[0]["title"] == "Title"
        assert sources[0]["url"] == "https://ex.com/1"


class TestSseEvent:
    """Tests for the _sse_event static method."""

    def test_message_event_format(self) -> None:
        result = ChatService._sse_event(
            "message", {"id": "msg_abc123def456", "type": "token", "content": "hi"}
        )
        assert result.startswith("event: message\n")
        assert "data: " in result
        assert result.endswith("\n\n")
        _, data = _parse_sse(result)
        assert data is not None
        assert data["id"] == "msg_abc123def456"
        assert data["type"] == "token"
        assert data["content"] == "hi"

    def test_error_event_format(self) -> None:
        payload = {
            "id": "msg_abc123def456",
            "error": {"code": "TEST", "message": "fail"},
        }
        result = ChatService._sse_event("error", payload)
        assert result.startswith("event: error\n")
        _, data = _parse_sse(result)
        assert data is not None
        assert data["error"]["code"] == "TEST"

    def test_done_event_format(self) -> None:
        result = ChatService._sse_event("done", {"id": "msg_abc123def456"})
        assert result.startswith("event: done\n")
        _, data = _parse_sse(result)
        assert data is not None
        assert data["id"] == "msg_abc123def456"


class TestChatStream:
    async def test_yields_token_events(self) -> None:
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
            def __init__(self) -> None:
                self.chunks = [chunk1, chunk2, chunk3]
                self.index = 0

            def __aiter__(self) -> MockStream:
                return self

            async def __anext__(self) -> MagicMock:
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
            events: list[str] = []
            async for event in service.chat_stream(mock_session, "What happened?"):
                events.append(event)

        # All events should have the same message ID
        msg_ids: set[str] = set()
        for raw in events:
            _, data = _parse_sse(raw)
            assert data is not None
            assert "id" in data
            msg_ids.add(data["id"])

        assert len(msg_ids) == 1, "All events must share the same msg ID"
        msg_id = msg_ids.pop()
        assert MSG_ID_RE.match(msg_id), f"Bad msg ID format: {msg_id}"

        # Check token events
        token_events = [
            _parse_sse(e)
            for e in events
            if "event: message" in e and '"type":"token"' in e.replace(" ", "")
        ]
        assert len(token_events) == 2
        assert token_events[0][1]["content"] == "Hello"
        assert token_events[1][1]["content"] == " world"

        # Check sources event
        sources_events = [
            _parse_sse(e)
            for e in events
            if "event: message" in e and '"type":"sources"' in e.replace(" ", "")
        ]
        assert len(sources_events) == 1
        assert isinstance(sources_events[0][1]["content"], list)

        # Check done event
        done_event = events[-1]
        evt_type, done_data = _parse_sse(done_event)
        assert evt_type == "done"
        assert done_data is not None
        assert done_data["id"] == msg_id

    async def test_empty_question_yields_error(self) -> None:
        mock_session = AsyncMock()
        with patch("src.rag.chat.get_settings", return_value=_mock_settings()):
            service = ChatService()
            events: list[str] = []
            async for event in service.chat_stream(mock_session, ""):
                events.append(event)

        # Should have error + done events
        assert len(events) == 2

        err_type, err_data = _parse_sse(events[0])
        assert err_type == "error"
        assert err_data is not None
        assert err_data["error"]["code"] == "INVALID_INPUT"
        assert MSG_ID_RE.match(err_data["id"])

        done_type, done_data = _parse_sse(events[1])
        assert done_type == "done"
        assert done_data is not None
        assert done_data["id"] == err_data["id"]

    async def test_no_results_still_streams(self) -> None:
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
            def __init__(self) -> None:
                self.chunks = [chunk, chunk_end]
                self.index = 0

            def __aiter__(self) -> MockStream:
                return self

            async def __anext__(self) -> MagicMock:
                if self.index >= len(self.chunks):
                    raise StopAsyncIteration
                c = self.chunks[self.index]
                self.index += 1
                return c

        mock_llm_client.chat.completions.create.return_value = MockStream()
        mock_session = AsyncMock()

        with patch("src.rag.chat.get_settings", return_value=_mock_settings()):
            service = ChatService(retriever=mock_retriever, llm_client=mock_llm_client)
            events: list[str] = []
            async for event in service.chat_stream(mock_session, "anything"):
                events.append(event)

        assert len(events) > 0

        # Last event is done
        done_type, done_data = _parse_sse(events[-1])
        assert done_type == "done"
        assert done_data is not None

        # Sources event should have empty content list
        sources_events = [
            _parse_sse(e)
            for e in events
            if "event: message" in e and '"type":"sources"' in e.replace(" ", "")
        ]
        assert len(sources_events) == 1
        assert sources_events[0][1]["content"] == []

    async def test_llm_error_yields_error_event(self) -> None:
        mock_retriever = AsyncMock()
        mock_retriever.retrieve.return_value = [_make_news_item()]

        mock_llm_client = AsyncMock()
        mock_llm_client.chat.completions.create.side_effect = Exception("LLM error")

        mock_session = AsyncMock()

        with patch("src.rag.chat.get_settings", return_value=_mock_settings()):
            service = ChatService(retriever=mock_retriever, llm_client=mock_llm_client)
            events: list[str] = []
            async for event in service.chat_stream(mock_session, "test"):
                events.append(event)

        # Should have: error, sources, done
        err_events = [_parse_sse(e) for e in events if e.startswith("event: error")]
        assert len(err_events) == 1
        assert err_events[0][1]["error"]["code"] == "CHAT_ERROR"

        done_type, done_data = _parse_sse(events[-1])
        assert done_type == "done"
        assert done_data is not None

    async def test_whitespace_question_yields_error(self) -> None:
        """Whitespace-only question is treated same as empty question."""
        mock_session = AsyncMock()
        with patch("src.rag.chat.get_settings", return_value=_mock_settings()):
            service = ChatService()
            events: list[str] = []
            async for event in service.chat_stream(mock_session, "   \n\t  "):
                events.append(event)

        assert len(events) == 2

        err_type, err_data = _parse_sse(events[0])
        assert err_type == "error"
        assert err_data is not None
        assert err_data["error"]["code"] == "INVALID_INPUT"

        done_type, done_data = _parse_sse(events[1])
        assert done_type == "done"
        assert done_data["id"] == err_data["id"]

    async def test_timeout_yields_error_event(self) -> None:
        """Timeout during LLM streaming yields a proper error event."""
        mock_retriever = AsyncMock()
        mock_retriever.retrieve.return_value = [_make_news_item()]

        mock_llm_client = AsyncMock()
        mock_llm_client.chat.completions.create.side_effect = TimeoutError

        mock_session = AsyncMock()

        with patch("src.rag.chat.get_settings", return_value=_mock_settings()):
            service = ChatService(retriever=mock_retriever, llm_client=mock_llm_client)
            events: list[str] = []
            async for event in service.chat_stream(mock_session, "test"):
                events.append(event)

        err_events = [_parse_sse(e) for e in events if e.startswith("event: error")]
        assert len(err_events) == 1
        assert err_events[0][1]["error"]["code"] == "LLM_TIMEOUT"

        done_type, _ = _parse_sse(events[-1])
        assert done_type == "done"

    async def test_all_events_share_message_id(self) -> None:
        """Every event in a single stream shares the same msg ID."""
        mock_retriever = AsyncMock()
        mock_retriever.retrieve.return_value = [_make_news_item()]

        mock_llm_client = AsyncMock()

        chunk = MagicMock()
        chunk.choices = [MagicMock()]
        chunk.choices[0].delta.content = "Answer"

        class MockStream:
            def __init__(self) -> None:
                self.chunks = [chunk]
                self.index = 0

            def __aiter__(self) -> MockStream:
                return self

            async def __anext__(self) -> MagicMock:
                if self.index >= len(self.chunks):
                    raise StopAsyncIteration
                c = self.chunks[self.index]
                self.index += 1
                return c

        mock_llm_client.chat.completions.create.return_value = MockStream()
        mock_session = AsyncMock()

        with patch("src.rag.chat.get_settings", return_value=_mock_settings()):
            service = ChatService(retriever=mock_retriever, llm_client=mock_llm_client)
            events: list[str] = []
            async for event in service.chat_stream(mock_session, "q?"):
                events.append(event)

        ids: set[str] = set()
        for raw in events:
            _, data = _parse_sse(raw)
            assert data is not None
            ids.add(data["id"])

        assert len(ids) == 1
        assert MSG_ID_RE.match(ids.pop())
