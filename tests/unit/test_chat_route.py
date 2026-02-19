"""Tests for POST /api/chat -- SSE streaming chat endpoint."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from src.api.app import app
from src.api.auth import require_auth
from src.api.routes.chat import _get_chat_service, limiter
from src.core.database import get_session


# ---------------------------------------------------------------------------
# Mock helpers
# ---------------------------------------------------------------------------
def _make_mock_session():
    """Create a mock AsyncSession for dependency override."""
    return AsyncMock()


async def _mock_get_session():
    """Dependency override that yields a mock session."""
    yield _make_mock_session()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture(autouse=True)
def _override_dependencies():
    """Override auth and session dependencies for all tests.

    Auth is bypassed and session is mocked by default.
    Individual tests can remove the auth override to test auth requirement.
    Also clear the ChatService lru_cache between tests.
    """
    _get_chat_service.cache_clear()
    original_enabled = limiter.enabled
    limiter.enabled = False
    app.dependency_overrides[require_auth] = lambda: "test-user"
    app.dependency_overrides[get_session] = _mock_get_session
    yield
    app.dependency_overrides.pop(require_auth, None)
    app.dependency_overrides.pop(get_session, None)
    limiter.enabled = original_enabled
    _get_chat_service.cache_clear()


@pytest.fixture()
async def api_client() -> AsyncClient:
    """Create an httpx AsyncClient wired to the FastAPI app."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Auth requirement
# ---------------------------------------------------------------------------
class TestChatAuth:
    """Verify that the chat endpoint requires authentication."""

    async def test_requires_auth(self, api_client: AsyncClient):
        """POST /api/chat without auth should return 403 (no token)."""
        app.dependency_overrides.pop(require_auth, None)
        resp = await api_client.post("/api/chat", json={"question": "test question"})
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# SSE streaming
# ---------------------------------------------------------------------------
class TestChatStreaming:
    """Verify SSE streaming response from the chat endpoint."""

    async def test_returns_sse_stream(self, api_client: AsyncClient):
        """POST /api/chat should return a text/event-stream response."""
        mock_service = MagicMock()

        async def mock_stream(*_a, **_kw):
            yield 'data: {"token": "Hello"}\n\n'
            yield 'data: {"token": " world"}\n\n'
            yield 'data: {"sources": []}\n\n'
            yield "data: [DONE]\n\n"

        mock_service.chat_stream = mock_stream

        with patch("src.api.routes.chat._get_chat_service", return_value=mock_service):
            resp = await api_client.post(
                "/api/chat",
                json={"question": "What AI models released?"},
            )

        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers["content-type"]
        body = resp.text
        assert "Hello" in body
        assert "[DONE]" in body

    async def test_sse_headers_present(self, api_client: AsyncClient):
        """Response should include cache-control and x-accel-buffering headers."""
        mock_service = MagicMock()

        async def mock_stream(*_a, **_kw):
            yield "data: [DONE]\n\n"

        mock_service.chat_stream = mock_stream

        with patch("src.api.routes.chat._get_chat_service", return_value=mock_service):
            resp = await api_client.post(
                "/api/chat",
                json={"question": "What is new in AI?"},
            )

        assert resp.headers.get("cache-control") == "no-cache"
        assert resp.headers.get("x-accel-buffering") == "no"

    async def test_passes_topic_and_limit(self, api_client: AsyncClient):
        """Topic and limit should be forwarded to ChatService.chat_stream."""
        captured_kwargs = {}
        mock_service = MagicMock()

        async def mock_stream(*_a, **kw):
            captured_kwargs.update(kw)
            yield "data: [DONE]\n\n"

        mock_service.chat_stream = mock_stream

        with patch("src.api.routes.chat._get_chat_service", return_value=mock_service):
            resp = await api_client.post(
                "/api/chat",
                json={"question": "Tell me about GPT", "topic": "modelos", "limit": 10},
            )

        assert resp.status_code == 200
        assert captured_kwargs.get("topic") == "modelos"
        assert captured_kwargs.get("limit") == 10


# ---------------------------------------------------------------------------
# Input validation
# ---------------------------------------------------------------------------
class TestChatValidation:
    """Validate request body constraints."""

    async def test_validates_short_question(self, api_client: AsyncClient):
        """Question shorter than 3 chars should return 422."""
        resp = await api_client.post("/api/chat", json={"question": "ab"})
        assert resp.status_code == 422

    async def test_validates_missing_question(self, api_client: AsyncClient):
        """Missing question field should return 422."""
        resp = await api_client.post("/api/chat", json={})
        assert resp.status_code == 422

    async def test_validates_limit_too_low(self, api_client: AsyncClient):
        """Limit below 1 should return 422."""
        resp = await api_client.post(
            "/api/chat",
            json={"question": "valid question", "limit": 0},
        )
        assert resp.status_code == 422

    async def test_validates_limit_too_high(self, api_client: AsyncClient):
        """Limit above 20 should return 422."""
        resp = await api_client.post(
            "/api/chat",
            json={"question": "valid question", "limit": 21},
        )
        assert resp.status_code == 422

    async def test_empty_question_returns_422(self, api_client: AsyncClient):
        """An empty string question should return 422 (min_length=3 constraint)."""
        resp = await api_client.post("/api/chat", json={"question": ""})
        assert resp.status_code == 422

    async def test_invalid_topic_accepted_or_rejected(self, api_client: AsyncClient):
        """A nonexistent topic string should not cause a 500 error.

        The topic field has no enum constraint in ChatRequest, so the API
        should either accept it (200) or reject it (422), but never crash.
        """
        mock_service = MagicMock()

        async def mock_stream(*_a, **_kw):
            yield "data: [DONE]\n\n"

        mock_service.chat_stream = mock_stream

        with patch("src.api.routes.chat._get_chat_service", return_value=mock_service):
            resp = await api_client.post(
                "/api/chat",
                json={"question": "valid question", "topic": "nonexistent_topic_xyz"},
            )

        assert resp.status_code in (200, 422)
        assert resp.status_code != 500

    async def test_default_limit_is_5(self, api_client: AsyncClient):
        """When limit is omitted, it should default to 5."""
        captured_kwargs = {}
        mock_service = MagicMock()

        async def mock_stream(*_a, **kw):
            captured_kwargs.update(kw)
            yield "data: [DONE]\n\n"

        mock_service.chat_stream = mock_stream

        with patch("src.api.routes.chat._get_chat_service", return_value=mock_service):
            resp = await api_client.post(
                "/api/chat",
                json={"question": "What is new in AI?"},
            )

        assert resp.status_code == 200
        assert captured_kwargs.get("limit") == 5

    async def test_topic_is_optional(self, api_client: AsyncClient):
        """When topic is omitted, it should default to None."""
        captured_kwargs = {}
        mock_service = MagicMock()

        async def mock_stream(*_a, **kw):
            captured_kwargs.update(kw)
            yield "data: [DONE]\n\n"

        mock_service.chat_stream = mock_stream

        with patch("src.api.routes.chat._get_chat_service", return_value=mock_service):
            resp = await api_client.post(
                "/api/chat",
                json={"question": "What is new in AI?"},
            )

        assert resp.status_code == 200
        assert captured_kwargs.get("topic") is None
