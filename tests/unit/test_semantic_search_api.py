"""Tests for GET /api/search/semantic -- vector similarity search endpoint."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from src.api.app import app
from src.api.auth import require_auth_or_guest
from src.core.database import get_session


# ---------------------------------------------------------------------------
# Mock helpers
# ---------------------------------------------------------------------------
def _make_mock_news_item(**overrides):
    """Create a mock NewsItem ORM object."""
    defaults = {
        "id": uuid.uuid4(),
        "title": "Test AI Article",
        "summary": "A summary of the article",
        "url": "https://example.com/article",
        "source": "hackernews",
        "topic": "models",
        "relevance_score": 0.9,
        "dev_value_score": 0.8,
        "credibility_score": 0.95,
        "priority": 1,
        "trending": False,
        "published_at": datetime(2026, 2, 15, 12, 0, tzinfo=UTC),
        "created_at": datetime(2026, 2, 15, 12, 0, tzinfo=UTC),
        "author": "test-author",
        "score": 42,
    }
    defaults.update(overrides)
    item = MagicMock()
    for k, v in defaults.items():
        setattr(item, k, v)
    return item


def _make_mock_session(items=None):
    """Create a mock AsyncSession that returns the given items on scalars().all()."""
    if items is None:
        items = []

    mock_result = MagicMock()
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = items
    mock_result.scalars.return_value = mock_scalars
    mock_result.scalar_one.return_value = 0
    mock_result.scalar_one_or_none.return_value = None

    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(return_value=mock_result)
    return mock_session


async def _mock_get_session_empty():
    yield _make_mock_session([])


async def _mock_get_session_with_items():
    items = [
        _make_mock_news_item(title="Semantic AI Model", topic="models", score=100),
        _make_mock_news_item(title="Vector Search Paper", topic="papers", score=80),
        _make_mock_news_item(title="LLM Embeddings Tool", topic="tools", score=60),
    ]
    yield _make_mock_session(items)


# A deterministic fake embedding vector (512 dims, as used by the service).
_FAKE_VECTOR: list[float] = [0.1] * 512


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture(autouse=True)
def _override_dependencies():
    """Override auth and session dependencies for all tests.

    Auth is bypassed. Session defaults to empty. Individual tests can
    re-override get_session for result-bearing cases.
    """
    app.dependency_overrides[require_auth_or_guest] = lambda: "test-user"
    app.dependency_overrides[get_session] = _mock_get_session_empty
    yield
    app.dependency_overrides.pop(require_auth_or_guest, None)
    app.dependency_overrides.pop(get_session, None)


@pytest.fixture()
async def api_client() -> AsyncClient:
    """Create an httpx AsyncClient wired to the FastAPI app."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Happy path: 200 with ranked results
# ---------------------------------------------------------------------------
class TestSemanticSearchHappyPath:
    """Semantic search returns items ranked by cosine similarity."""

    async def test_semantic_search_returns_200(self, api_client: AsyncClient):
        """GET /api/search/semantic?q=... should return HTTP 200."""
        with patch(
            "src.rag.retriever.Retriever.retrieve",
            new_callable=AsyncMock,
            return_value=[],
        ):
            resp = await api_client.get("/api/search/semantic", params={"q": "AI models"})
        assert resp.status_code == 200

    async def test_semantic_search_returns_list(self, api_client: AsyncClient):
        """Response body must be a JSON array."""
        with patch(
            "src.rag.retriever.Retriever.retrieve",
            new_callable=AsyncMock,
            return_value=[],
        ):
            resp = await api_client.get("/api/search/semantic", params={"q": "AI models"})
        assert isinstance(resp.json(), list)

    async def test_semantic_search_returns_items_from_retriever(self, api_client: AsyncClient):
        """Items returned by Retriever are serialised as NewsItemResponse."""
        items = [
            _make_mock_news_item(title="Semantic AI Model", topic="models", score=100),
            _make_mock_news_item(title="Vector Search Paper", topic="papers", score=80),
        ]
        with patch(
            "src.rag.retriever.Retriever.retrieve",
            new_callable=AsyncMock,
            return_value=items,
        ):
            resp = await api_client.get("/api/search/semantic", params={"q": "transformers"})
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) == 2

    async def test_semantic_search_result_has_expected_fields(self, api_client: AsyncClient):
        """Each result must contain standard NewsItemResponse fields."""
        items = [_make_mock_news_item()]
        with patch(
            "src.rag.retriever.Retriever.retrieve",
            new_callable=AsyncMock,
            return_value=items,
        ):
            resp = await api_client.get("/api/search/semantic", params={"q": "llm"})
        data = resp.json()
        assert len(data) == 1
        item = data[0]
        assert "id" in item
        assert "title" in item
        assert "source" in item
        assert "created_at" in item

    async def test_semantic_search_passes_query_to_retriever(self, api_client: AsyncClient):
        """The query string must be forwarded to Retriever.retrieve()."""
        with patch(
            "src.rag.retriever.Retriever.retrieve",
            new_callable=AsyncMock,
            return_value=[],
        ) as mock_retrieve:
            await api_client.get("/api/search/semantic", params={"q": "neural networks"})
        mock_retrieve.assert_called_once()
        call_kwargs = mock_retrieve.call_args
        # First positional arg after self is session; second is query string
        assert (
            "neural networks" in call_kwargs.args
            or call_kwargs.kwargs.get("query") == "neural networks"
        )

    async def test_semantic_search_respects_limit_param(self, api_client: AsyncClient):
        """The limit param must be forwarded to Retriever.retrieve()."""
        with patch(
            "src.rag.retriever.Retriever.retrieve",
            new_callable=AsyncMock,
            return_value=[],
        ) as mock_retrieve:
            await api_client.get("/api/search/semantic", params={"q": "test", "limit": 10})
        mock_retrieve.assert_called_once()
        call_kwargs = mock_retrieve.call_args
        limit_passed = call_kwargs.kwargs.get("limit") or (
            call_kwargs.args[2] if len(call_kwargs.args) > 2 else None
        )
        assert limit_passed == 10


# ---------------------------------------------------------------------------
# Auth requirement
# ---------------------------------------------------------------------------
class TestSemanticSearchAuth:
    """Semantic search must enforce authentication."""

    async def test_semantic_search_requires_auth(self, api_client: AsyncClient):
        """Without auth, endpoint must return 403."""
        app.dependency_overrides.pop(require_auth_or_guest, None)
        resp = await api_client.get("/api/search/semantic", params={"q": "test"})
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------
class TestSemanticSearchValidation:
    """Validate query parameter constraints."""

    async def test_missing_q_returns_422(self, api_client: AsyncClient):
        """GET /api/search/semantic without 'q' must return 422."""
        resp = await api_client.get("/api/search/semantic")
        assert resp.status_code == 422

    async def test_empty_string_q_returns_422(self, api_client: AsyncClient):
        """GET /api/search/semantic?q= (empty string) must return 422."""
        resp = await api_client.get("/api/search/semantic", params={"q": ""})
        assert resp.status_code == 422

    async def test_limit_too_large_returns_422(self, api_client: AsyncClient):
        """limit above cap must return 422."""
        resp = await api_client.get("/api/search/semantic", params={"q": "test", "limit": 999})
        assert resp.status_code == 422

    async def test_limit_zero_returns_422(self, api_client: AsyncClient):
        """limit=0 must return 422."""
        resp = await api_client.get("/api/search/semantic", params={"q": "test", "limit": 0})
        assert resp.status_code == 422

    async def test_valid_limit_accepted(self, api_client: AsyncClient):
        """A limit within bounds must be accepted."""
        with patch(
            "src.rag.retriever.Retriever.retrieve",
            new_callable=AsyncMock,
            return_value=[],
        ):
            resp = await api_client.get("/api/search/semantic", params={"q": "test", "limit": 10})
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Embeddings unavailable (empty API key → retriever returns [])
# ---------------------------------------------------------------------------
class TestSemanticSearchEmbeddingsUnavailable:
    """When embeddings are unavailable, the endpoint returns an empty list."""

    async def test_returns_empty_list_when_retriever_returns_empty(self, api_client: AsyncClient):
        """Retriever returning [] (e.g. embed failure) → 200 with empty list."""
        with patch(
            "src.rag.retriever.Retriever.retrieve",
            new_callable=AsyncMock,
            return_value=[],
        ):
            resp = await api_client.get("/api/search/semantic", params={"q": "test"})
        assert resp.status_code == 200
        assert resp.json() == []
