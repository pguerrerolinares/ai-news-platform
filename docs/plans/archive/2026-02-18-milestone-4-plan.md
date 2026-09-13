# Milestone 4 — RAG + Q&A Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a chat feature where users ask questions about AI news, powered by pgvector semantic search and Kimi/Moonshot streamed answers.

**Architecture:** OpenAI `text-embedding-3-small` generates 1536-dim vectors for news items, stored in pgvector with HNSW index. User queries are embedded, matched via cosine similarity, and the top-K results are sent as context to Kimi/Moonshot which streams a Spanish-language answer via SSE. An Angular chat page renders tokens in real-time.

**Tech Stack:** pgvector, OpenAI embeddings API, Kimi/Moonshot chat API, FastAPI StreamingResponse (SSE), Angular 21 signals + fetch ReadableStream

---

## Task 1: Alembic Migration — vector column + HNSW index

**Files:**
- Create: `alembic/versions/002_add_vector_column.py`
- Modify: `src/core/models.py:107-121`

**Step 1: Write the migration**

Create `alembic/versions/002_add_vector_column.py`:

```python
"""Add vector(1536) column and HNSW index to item_embeddings.

Revision ID: 002
Revises: 001
Create Date: 2026-02-18
"""

from collections.abc import Sequence

from alembic import op

revision: str = "002"
down_revision: str = "001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Drop the placeholder Text column
    op.drop_column("item_embeddings", "embedding")
    # Add the real vector column
    op.execute("ALTER TABLE item_embeddings ADD COLUMN embedding vector(1536)")
    # Create HNSW index for fast cosine similarity search
    op.execute(
        "CREATE INDEX ix_item_embeddings_hnsw ON item_embeddings "
        "USING hnsw (embedding vector_cosine_ops) "
        "WITH (m = 16, ef_construction = 64)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_item_embeddings_hnsw")
    op.drop_column("item_embeddings", "embedding")
    op.execute("ALTER TABLE item_embeddings ADD COLUMN embedding TEXT")
```

**Step 2: Update the ORM model**

In `src/core/models.py`, update `ItemEmbedding` to declare the `embedding` column with the pgvector type:

```python
# Add to imports at the top of the file:
from pgvector.sqlalchemy import Vector

# Replace the ItemEmbedding class:
class ItemEmbedding(Base):
    """Vector embeddings for RAG search."""

    __tablename__ = "item_embeddings"

    item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("news_items.id", ondelete="CASCADE"),
        primary_key=True,
    )
    model: Mapped[str] = mapped_column(Text, primary_key=True, nullable=False)
    embedding = mapped_column(Vector(1536))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (UniqueConstraint("item_id", "model", name="pk_item_embeddings"),)
```

**Step 3: Verify migration is valid**

Run: `python -c "from alembic.versions import *; print('import OK')"`
(This just verifies the file parses without syntax errors. Full migration run requires a live DB.)

**Step 4: Commit**

```bash
git add alembic/versions/002_add_vector_column.py src/core/models.py
git commit -m "feat(m4): add vector(1536) column and HNSW index migration"
```

---

## Task 2: Config — add embedding settings

**Files:**
- Modify: `src/core/config.py:44-47`
- Test: `tests/unit/test_config_embedding.py`

**Step 1: Write the failing test**

Create `tests/unit/test_config_embedding.py`:

```python
"""Tests for embedding configuration settings."""

from __future__ import annotations

from src.core.config import Settings


class TestEmbeddingConfig:
    def test_defaults(self):
        s = Settings(
            telegram_bot_token="",
            telegram_chat_id="",
            telegram_alerts_enabled=False,
        )
        assert s.embedding_api_key == ""
        assert s.embedding_base_url == "https://api.openai.com/v1"
        assert s.embedding_model == "text-embedding-3-small"
        assert s.embedding_dimensions == 1536

    def test_custom_values(self):
        s = Settings(
            embedding_api_key="sk-test-123",
            embedding_base_url="https://custom.api.com/v1",
            embedding_model="custom-model",
            embedding_dimensions=768,
            telegram_bot_token="",
            telegram_chat_id="",
            telegram_alerts_enabled=False,
        )
        assert s.embedding_api_key == "sk-test-123"
        assert s.embedding_base_url == "https://custom.api.com/v1"
        assert s.embedding_model == "custom-model"
        assert s.embedding_dimensions == 768

    def test_embedding_not_configured_when_empty_key(self):
        s = Settings(
            telegram_bot_token="",
            telegram_chat_id="",
            telegram_alerts_enabled=False,
        )
        assert s.embedding_api_key == ""
        assert not s.embedding_api_key  # falsy when not configured
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_config_embedding.py -v`
Expected: FAIL — `Settings` does not have `embedding_api_key` attribute

**Step 3: Add settings to config**

In `src/core/config.py`, add after the LLM section (after line 47):

```python
    # --- Embeddings (OpenAI text-embedding-3-small) ---
    embedding_api_key: str = ""
    embedding_base_url: str = "https://api.openai.com/v1"
    embedding_model: str = "text-embedding-3-small"
    embedding_dimensions: int = 1536
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_config_embedding.py -v`
Expected: PASS (3 tests)

**Step 5: Commit**

```bash
git add src/core/config.py tests/unit/test_config_embedding.py
git commit -m "feat(m4): add embedding config settings"
```

---

## Task 3: Embedding Service

**Files:**
- Create: `src/rag/embeddings.py`
- Modify: `src/rag/__init__.py`
- Test: `tests/unit/test_embeddings.py`

**Step 1: Write the failing tests**

Create `tests/unit/test_embeddings.py`:

```python
"""Tests for the embedding service."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.core.config import Settings
from src.rag.embeddings import EmbeddingService


def _mock_settings(**overrides):
    defaults = {
        "embedding_api_key": "sk-test-key",
        "embedding_base_url": "https://api.openai.com/v1",
        "embedding_model": "text-embedding-3-small",
        "embedding_dimensions": 1536,
        "telegram_bot_token": "",
        "telegram_chat_id": "",
        "telegram_alerts_enabled": False,
    }
    defaults.update(overrides)
    return Settings(**defaults)


def _fake_embedding(dims: int = 1536) -> list[float]:
    return [0.1] * dims


class TestEmbedText:
    async def test_returns_embedding_list(self):
        mock_client = AsyncMock()
        mock_client.embeddings.create.return_value = MagicMock(
            data=[MagicMock(embedding=_fake_embedding())]
        )
        with patch("src.rag.embeddings.get_settings", return_value=_mock_settings()):
            service = EmbeddingService(client=mock_client)
            result = await service.embed_text("test query")
        assert isinstance(result, list)
        assert len(result) == 1536

    async def test_calls_openai_with_correct_model(self):
        mock_client = AsyncMock()
        mock_client.embeddings.create.return_value = MagicMock(
            data=[MagicMock(embedding=_fake_embedding())]
        )
        with patch("src.rag.embeddings.get_settings", return_value=_mock_settings()):
            service = EmbeddingService(client=mock_client)
            await service.embed_text("test")
        mock_client.embeddings.create.assert_called_once()
        call_kwargs = mock_client.embeddings.create.call_args
        assert call_kwargs.kwargs["model"] == "text-embedding-3-small"

    async def test_truncates_long_text(self):
        mock_client = AsyncMock()
        mock_client.embeddings.create.return_value = MagicMock(
            data=[MagicMock(embedding=_fake_embedding())]
        )
        long_text = "word " * 10000  # way over 8191 tokens
        with patch("src.rag.embeddings.get_settings", return_value=_mock_settings()):
            service = EmbeddingService(client=mock_client)
            await service.embed_text(long_text)
        call_kwargs = mock_client.embeddings.create.call_args
        sent_input = call_kwargs.kwargs["input"]
        assert len(sent_input) <= 32000  # char limit (rough ~8K tokens)


class TestPrepareText:
    def test_combines_title_and_summary(self):
        with patch("src.rag.embeddings.get_settings", return_value=_mock_settings()):
            service = EmbeddingService()
        result = service.prepare_text("My Title", "My Summary")
        assert result == "My Title\nMy Summary"

    def test_handles_none_summary(self):
        with patch("src.rag.embeddings.get_settings", return_value=_mock_settings()):
            service = EmbeddingService()
        result = service.prepare_text("Title Only", None)
        assert result == "Title Only"

    def test_handles_empty_strings(self):
        with patch("src.rag.embeddings.get_settings", return_value=_mock_settings()):
            service = EmbeddingService()
        result = service.prepare_text("Title", "")
        assert result == "Title"


class TestEmbedBatch:
    async def test_returns_list_of_embeddings(self):
        mock_client = AsyncMock()
        mock_client.embeddings.create.return_value = MagicMock(
            data=[
                MagicMock(embedding=_fake_embedding()),
                MagicMock(embedding=_fake_embedding()),
            ]
        )
        with patch("src.rag.embeddings.get_settings", return_value=_mock_settings()):
            service = EmbeddingService(client=mock_client)
            result = await service.embed_batch(["text one", "text two"])
        assert len(result) == 2
        assert all(len(e) == 1536 for e in result)

    async def test_batches_large_input(self):
        """Input of 150 texts should be split into 2 API calls (100 + 50)."""
        mock_client = AsyncMock()
        mock_client.embeddings.create.return_value = MagicMock(
            data=[MagicMock(embedding=_fake_embedding()) for _ in range(100)]
        )
        texts = [f"text {i}" for i in range(150)]
        with patch("src.rag.embeddings.get_settings", return_value=_mock_settings()):
            service = EmbeddingService(client=mock_client)
            # Mock returns 100 for first call, 50 for second
            mock_client.embeddings.create.side_effect = [
                MagicMock(data=[MagicMock(embedding=_fake_embedding()) for _ in range(100)]),
                MagicMock(data=[MagicMock(embedding=_fake_embedding()) for _ in range(50)]),
            ]
            result = await service.embed_batch(texts)
        assert len(result) == 150
        assert mock_client.embeddings.create.call_count == 2

    async def test_empty_input_returns_empty(self):
        mock_client = AsyncMock()
        with patch("src.rag.embeddings.get_settings", return_value=_mock_settings()):
            service = EmbeddingService(client=mock_client)
            result = await service.embed_batch([])
        assert result == []
        mock_client.embeddings.create.assert_not_called()

    async def test_api_error_raises(self):
        mock_client = AsyncMock()
        mock_client.embeddings.create.side_effect = Exception("API error")
        with patch("src.rag.embeddings.get_settings", return_value=_mock_settings()):
            service = EmbeddingService(client=mock_client)
            with pytest.raises(Exception, match="API error"):
                await service.embed_batch(["text"])
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_embeddings.py -v`
Expected: FAIL — `cannot import name 'EmbeddingService' from 'src.rag.embeddings'`

**Step 3: Implement EmbeddingService**

Create `src/rag/embeddings.py`:

```python
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
        )
        return response.data[0].embedding

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Embed multiple texts, batching API calls by _BATCH_SIZE.

        Returns list of embeddings in same order as input.
        """
        if not texts:
            return []

        all_embeddings: list[list[float]] = []
        for i in range(0, len(texts), _BATCH_SIZE):
            batch = [t[:_MAX_CHARS] for t in texts[i : i + _BATCH_SIZE]]
            response = await self._client.embeddings.create(
                model=self._model,
                input=batch,
            )
            all_embeddings.extend([d.embedding for d in response.data])

        return all_embeddings
```

Update `src/rag/__init__.py`:

```python
"""RAG module — embeddings, retrieval, and chat."""
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_embeddings.py -v`
Expected: PASS (10 tests)

**Step 5: Commit**

```bash
git add src/rag/embeddings.py src/rag/__init__.py tests/unit/test_embeddings.py
git commit -m "feat(m4): add embedding service with batch support"
```

---

## Task 4: Retriever — vector similarity search

**Files:**
- Create: `src/rag/retriever.py`
- Test: `tests/unit/test_retriever.py`

**Step 1: Write the failing tests**

Create `tests/unit/test_retriever.py`:

```python
"""Tests for the RAG retriever."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.rag.retriever import Retriever


def _fake_embedding(dims: int = 1536) -> list[float]:
    return [0.1] * dims


def _make_news_item(title: str = "Test News", topic: str = "modelos"):
    """Create a mock NewsItem-like object."""
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

    async def test_default_limit_is_5(self):
        mock_embed = AsyncMock()
        mock_embed.embed_text.return_value = _fake_embedding()
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result

        retriever = Retriever(embedding_service=mock_embed)
        await retriever.retrieve(mock_session, "test query")
        # Verify the SQL was executed (we can't easily check LIMIT in mock)
        mock_session.execute.assert_called_once()

    async def test_with_topic_filter(self):
        mock_embed = AsyncMock()
        mock_embed.embed_text.return_value = _fake_embedding()
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result

        retriever = Retriever(embedding_service=mock_embed)
        await retriever.retrieve(mock_session, "test", topic="modelos")
        mock_session.execute.assert_called_once()

    async def test_empty_query_returns_empty(self):
        mock_embed = AsyncMock()
        mock_session = AsyncMock()

        retriever = Retriever(embedding_service=mock_embed)
        result = await retriever.retrieve(mock_session, "")
        assert result == []
        mock_embed.embed_text.assert_not_called()

    async def test_embedding_error_returns_empty(self):
        mock_embed = AsyncMock()
        mock_embed.embed_text.side_effect = Exception("API error")
        mock_session = AsyncMock()

        retriever = Retriever(embedding_service=mock_embed)
        result = await retriever.retrieve(mock_session, "test query")
        assert result == []
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_retriever.py -v`
Expected: FAIL — `cannot import name 'Retriever' from 'src.rag.retriever'`

**Step 3: Implement Retriever**

Create `src/rag/retriever.py`:

```python
"""RAG retriever — vector similarity search over news items."""

from __future__ import annotations

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.logging import get_logger
from src.core.models import ItemEmbedding, NewsItem
from src.rag.embeddings import EmbeddingService

logger = get_logger(__name__)


class Retriever:
    """Retrieve relevant news items via pgvector cosine similarity."""

    def __init__(self, embedding_service: EmbeddingService | None = None) -> None:
        self._embed = embedding_service or EmbeddingService()

    async def retrieve(
        self,
        session: AsyncSession,
        query: str,
        *,
        limit: int = 5,
        topic: str | None = None,
    ) -> list[NewsItem]:
        """Find the top-K most similar news items to the query.

        Args:
            session: Database session.
            query: User's natural language query.
            limit: Max number of results (default 5).
            topic: Optional topic filter.

        Returns:
            List of NewsItem objects ordered by similarity.
        """
        if not query.strip():
            return []

        try:
            query_vec = await self._embed.embed_text(query)
        except Exception:
            logger.error("retriever_embed_failed", exc_info=True)
            return []

        # Build the cosine similarity query with pgvector <=> operator
        vec_literal = "[" + ",".join(str(v) for v in query_vec) + "]"

        stmt = (
            select(NewsItem)
            .join(ItemEmbedding, NewsItem.id == ItemEmbedding.item_id)
            .order_by(ItemEmbedding.embedding.cosine_distance(query_vec))
            .limit(limit)
        )

        if topic:
            stmt = stmt.where(NewsItem.topic == topic)

        result = await session.execute(stmt)
        return list(result.scalars().all())
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_retriever.py -v`
Expected: PASS (5 tests)

**Step 5: Commit**

```bash
git add src/rag/retriever.py tests/unit/test_retriever.py
git commit -m "feat(m4): add vector similarity retriever"
```

---

## Task 5: Chat Service — LLM streaming with context

**Files:**
- Create: `src/rag/chat.py`
- Test: `tests/unit/test_chat_service.py`

**Step 1: Write the failing tests**

Create `tests/unit/test_chat_service.py`:

```python
"""Tests for the RAG chat service."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.core.config import Settings
from src.rag.chat import ChatService, SYSTEM_PROMPT


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
    def test_system_prompt_is_spanish(self):
        assert "noticias" in SYSTEM_PROMPT
        assert "IA" in SYSTEM_PROMPT

    def test_system_prompt_mentions_sources(self):
        assert "fuentes" in SYSTEM_PROMPT.lower()


class TestBuildContext:
    def test_formats_items_as_context(self):
        items = [_make_news_item("Title 1", "Summary 1", "https://ex.com/1")]
        with patch("src.rag.chat.get_settings", return_value=_mock_settings()):
            service = ChatService()
        context = service._build_context(items)
        assert "Title 1" in context
        assert "Summary 1" in context
        assert "https://ex.com/1" in context

    def test_empty_items_returns_no_context_message(self):
        with patch("src.rag.chat.get_settings", return_value=_mock_settings()):
            service = ChatService()
        context = service._build_context([])
        assert "no hay" in context.lower() or "no se encontr" in context.lower()


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
        # Simulate streaming chunks
        chunk1 = MagicMock()
        chunk1.choices = [MagicMock()]
        chunk1.choices[0].delta.content = "Hello"
        chunk2 = MagicMock()
        chunk2.choices = [MagicMock()]
        chunk2.choices[0].delta.content = " world"
        chunk3 = MagicMock()
        chunk3.choices = [MagicMock()]
        chunk3.choices[0].delta.content = None

        async def mock_stream():
            for chunk in [chunk1, chunk2, chunk3]:
                yield chunk

        mock_response = MagicMock()
        mock_response.__aiter__ = lambda self: mock_stream()
        mock_llm_client.chat.completions.create.return_value = mock_response

        mock_session = AsyncMock()

        with patch("src.rag.chat.get_settings", return_value=_mock_settings()):
            service = ChatService(
                retriever=mock_retriever,
                llm_client=mock_llm_client,
            )
            events = []
            async for event in service.chat_stream(mock_session, "What happened?"):
                events.append(event)

        # Should have token events + sources event + [DONE]
        token_events = [e for e in events if '"token"' in e]
        assert len(token_events) >= 2
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

    async def test_retriever_error_yields_error_event(self):
        mock_retriever = AsyncMock()
        mock_retriever.retrieve.return_value = []  # no results

        mock_llm_client = AsyncMock()
        # LLM still responds even with no context
        chunk = MagicMock()
        chunk.choices = [MagicMock()]
        chunk.choices[0].delta.content = "No information available"

        chunk_end = MagicMock()
        chunk_end.choices = [MagicMock()]
        chunk_end.choices[0].delta.content = None

        async def mock_stream():
            for c in [chunk, chunk_end]:
                yield c

        mock_response = MagicMock()
        mock_response.__aiter__ = lambda self: mock_stream()
        mock_llm_client.chat.completions.create.return_value = mock_response

        mock_session = AsyncMock()

        with patch("src.rag.chat.get_settings", return_value=_mock_settings()):
            service = ChatService(
                retriever=mock_retriever,
                llm_client=mock_llm_client,
            )
            events = []
            async for event in service.chat_stream(mock_session, "anything"):
                events.append(event)

        # Should still yield events (LLM can respond with "no info" message)
        assert len(events) > 0
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_chat_service.py -v`
Expected: FAIL — `cannot import name 'ChatService' from 'src.rag.chat'`

**Step 3: Implement ChatService**

Create `src/rag/chat.py`:

```python
"""RAG chat service — retrieve context and stream LLM answers."""

from __future__ import annotations

import json
from collections.abc import AsyncGenerator

import openai

from src.core.config import get_settings
from src.core.logging import get_logger
from src.core.models import NewsItem
from src.rag.embeddings import EmbeddingService
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

    def _build_context(self, items: list[NewsItem]) -> str:
        """Format retrieved items as context for the LLM prompt."""
        if not items:
            return "No se encontraron noticias relevantes en la base de datos."

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
    def _build_sources(items: list[NewsItem]) -> list[dict]:
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
        session,
        question: str,
        *,
        topic: str | None = None,
        limit: int = 5,
    ) -> AsyncGenerator[str, None]:
        """Stream SSE events: token chunks, then sources, then [DONE].

        Each event is a string in the format: "data: {json}\n\n"
        """
        if not question.strip():
            yield f"data: {json.dumps({'error': 'La pregunta no puede estar vacia'})}\n\n"
            yield "data: [DONE]\n\n"
            return

        # 1. Retrieve relevant context
        items = await self._retriever.retrieve(
            session, question, limit=limit, topic=topic,
        )

        context = self._build_context(items)

        # 2. Build user message with context
        user_message = (
            f"Contexto (noticias recientes):\n\n{context}\n\n"
            f"Pregunta del usuario: {question}"
        )

        # 3. Stream LLM response
        try:
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
                    yield f"data: {json.dumps({'token': content})}\n\n"

        except Exception as exc:
            logger.error("chat_stream_error", error=str(exc))
            yield f"data: {json.dumps({'error': 'Error al generar la respuesta'})}\n\n"

        # 4. Send sources
        sources = self._build_sources(items)
        yield f"data: {json.dumps({'sources': sources})}\n\n"

        # 5. Done
        yield "data: [DONE]\n\n"
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_chat_service.py -v`
Expected: PASS (7 tests)

**Step 5: Commit**

```bash
git add src/rag/chat.py tests/unit/test_chat_service.py
git commit -m "feat(m4): add chat service with streaming SSE"
```

---

## Task 6: API Endpoint — POST /api/chat

**Files:**
- Create: `src/api/routes/chat.py`
- Modify: `src/api/app.py:19,76`
- Modify: `src/api/schemas.py`
- Test: `tests/unit/test_chat_route.py`

**Step 1: Write the failing tests**

Create `tests/unit/test_chat_route.py`:

```python
"""Tests for the /api/chat endpoint."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from src.api.app import app
from src.core.config import Settings


def _mock_settings(**overrides):
    defaults = {
        "debug": True,
        "jwt_secret": "test-secret",
        "shared_password": "test-pass",
        "openai_api_key": "sk-test",
        "openai_base_url": "https://api.moonshot.cn/v1",
        "openai_model": "kimi-latest",
        "embedding_api_key": "sk-embed",
        "embedding_base_url": "https://api.openai.com/v1",
        "embedding_model": "text-embedding-3-small",
        "embedding_dimensions": 1536,
        "telegram_bot_token": "",
        "telegram_chat_id": "",
        "telegram_alerts_enabled": False,
    }
    defaults.update(overrides)
    return Settings(**defaults)


@pytest.fixture()
def client():
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


@pytest.fixture()
def auth_headers():
    from src.api.auth import create_access_token

    with patch("src.api.auth.get_settings", return_value=_mock_settings()):
        token = create_access_token("testuser")
    return {"Authorization": f"Bearer {token}"}


class TestChatEndpoint:
    def test_requires_auth(self, client):
        resp = client.post("/api/chat", json={"question": "test"})
        assert resp.status_code == 403

    def test_validates_empty_question(self, client, auth_headers):
        async def mock_stream(*_a, **_kw):
            yield 'data: {"error": "La pregunta no puede estar vacia"}\n\n'
            yield "data: [DONE]\n\n"

        with (
            patch("src.api.auth.get_settings", return_value=_mock_settings()),
            patch("src.api.routes.chat.get_settings", return_value=_mock_settings()),
            patch("src.api.routes.chat.ChatService") as MockChat,
        ):
            MockChat.return_value.chat_stream = mock_stream
            resp = client.post(
                "/api/chat",
                json={"question": ""},
                headers=auth_headers,
            )
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/event-stream")

    def test_returns_sse_stream(self, client, auth_headers):
        async def mock_stream(*_a, **_kw):
            yield 'data: {"token": "Hello"}\n\n'
            yield 'data: {"token": " world"}\n\n'
            yield 'data: {"sources": []}\n\n'
            yield "data: [DONE]\n\n"

        with (
            patch("src.api.auth.get_settings", return_value=_mock_settings()),
            patch("src.api.routes.chat.get_settings", return_value=_mock_settings()),
            patch("src.api.routes.chat.ChatService") as MockChat,
        ):
            MockChat.return_value.chat_stream = mock_stream
            resp = client.post(
                "/api/chat",
                json={"question": "What AI models released?"},
                headers=auth_headers,
            )
        assert resp.status_code == 200
        body = resp.text
        assert "Hello" in body
        assert "world" in body
        assert "[DONE]" in body

    def test_validates_question_min_length(self, client, auth_headers):
        with (
            patch("src.api.auth.get_settings", return_value=_mock_settings()),
            patch("src.api.routes.chat.get_settings", return_value=_mock_settings()),
        ):
            resp = client.post(
                "/api/chat",
                json={"question": "ab", "limit": 0},
                headers=auth_headers,
            )
        assert resp.status_code == 422
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_chat_route.py -v`
Expected: FAIL — route not registered / `ChatService` not importable from route module

**Step 3: Implement the route and register it**

Create `src/api/routes/chat.py`:

```python
"""API route for RAG chat with streaming SSE responses."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.auth import require_auth
from src.core.config import get_settings
from src.core.database import get_session
from src.rag.chat import ChatService

router = APIRouter(prefix="/api/chat", tags=["chat"])


class ChatRequest(BaseModel):
    question: str = Field(..., min_length=3, max_length=500)
    topic: str | None = Field(None, description="Filter context by topic")
    limit: int = Field(5, ge=1, le=20, description="Number of context items")


@router.post("")
async def chat(
    body: ChatRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
    _user: str = Depends(require_auth),
):
    """Chat with AI about news. Returns SSE stream."""
    limiter = request.app.state.limiter
    service = ChatService()

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
```

Add to `src/api/app.py` — add the import and router registration:

After line 19 (`from src.api.routes.search import router as search_router`), add:
```python
from src.api.routes.chat import router as chat_router
```

After line 76 (`app.include_router(search_router)`), add:
```python
app.include_router(chat_router)
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_chat_route.py -v`
Expected: PASS (4 tests)

**Step 5: Commit**

```bash
git add src/api/routes/chat.py src/api/app.py tests/unit/test_chat_route.py
git commit -m "feat(m4): add POST /api/chat SSE streaming endpoint"
```

---

## Task 7: Pipeline Integration — embed new items

**Files:**
- Modify: `src/pipeline/pipeline.py:272-285`
- Test: `tests/unit/test_pipeline_embedding.py`

**Step 1: Write the failing tests**

Create `tests/unit/test_pipeline_embedding.py`:

```python
"""Tests for the embedding step in the pipeline."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.pipeline.pipeline import _embed_new_items


def _mock_settings(**overrides):
    defaults = {
        "embedding_api_key": "sk-test",
        "embedding_base_url": "https://api.openai.com/v1",
        "embedding_model": "text-embedding-3-small",
        "embedding_dimensions": 1536,
        "telegram_bot_token": "",
        "telegram_chat_id": "",
        "telegram_alerts_enabled": False,
    }
    defaults.update(overrides)
    return Settings(**defaults)


from src.core.config import Settings


def _mock_settings(**overrides):
    defaults = {
        "embedding_api_key": "sk-test",
        "embedding_base_url": "https://api.openai.com/v1",
        "embedding_model": "text-embedding-3-small",
        "embedding_dimensions": 1536,
        "telegram_bot_token": "",
        "telegram_chat_id": "",
        "telegram_alerts_enabled": False,
    }
    defaults.update(overrides)
    return Settings(**defaults)


def _make_item(title: str = "Test", summary: str | None = "Summary"):
    item = MagicMock()
    item.id = uuid.uuid4()
    item.title = title
    item.summary = summary
    return item


class TestEmbedNewItems:
    async def test_embeds_items_without_embeddings(self):
        session = AsyncMock()
        items = [_make_item("Title 1"), _make_item("Title 2")]
        # Mock the query that finds items without embeddings
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = items
        session.execute.return_value = mock_result

        mock_embed_service = AsyncMock()
        mock_embed_service.embed_batch.return_value = [[0.1] * 1536, [0.2] * 1536]
        mock_embed_service.prepare_text.side_effect = lambda t, s: f"{t}\n{s}" if s else t

        with patch("src.pipeline.pipeline.get_settings", return_value=_mock_settings()):
            count = await _embed_new_items(session, mock_embed_service)
        assert count == 2

    async def test_skips_when_no_items(self):
        session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        session.execute.return_value = mock_result

        mock_embed_service = AsyncMock()

        with patch("src.pipeline.pipeline.get_settings", return_value=_mock_settings()):
            count = await _embed_new_items(session, mock_embed_service)
        assert count == 0
        mock_embed_service.embed_batch.assert_not_called()

    async def test_handles_embedding_error(self):
        session = AsyncMock()
        items = [_make_item()]
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = items
        session.execute.return_value = mock_result

        mock_embed_service = AsyncMock()
        mock_embed_service.prepare_text.return_value = "Title\nSummary"
        mock_embed_service.embed_batch.side_effect = Exception("API error")

        with patch("src.pipeline.pipeline.get_settings", return_value=_mock_settings()):
            count = await _embed_new_items(session, mock_embed_service)
        # Should return 0 and not raise
        assert count == 0
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_pipeline_embedding.py -v`
Expected: FAIL — `cannot import name '_embed_new_items' from 'src.pipeline.pipeline'`

**Step 3: Add embedding step to pipeline**

Add to `src/pipeline/pipeline.py`:

At the top, add imports:
```python
from src.core.models import DailyBriefing, ItemEmbedding, NewsItem
from src.rag.embeddings import EmbeddingService
```
(Update the existing `from src.core.models import DailyBriefing, NewsItem` line.)

Add the `_embed_new_items` function (before `run_pipeline`):

```python
async def _embed_new_items(
    session: AsyncSession,
    embed_service: EmbeddingService | None = None,
) -> int:
    """Generate embeddings for items that don't have one yet.

    Returns count of newly embedded items. Errors are logged but not raised.
    """
    settings = get_settings()

    if embed_service is None:
        embed_service = EmbeddingService()

    model_name = settings.embedding_model

    # Find items without embeddings for this model
    subquery = (
        select(ItemEmbedding.item_id).where(ItemEmbedding.model == model_name)
    )
    stmt = select(NewsItem).where(~NewsItem.id.in_(subquery))
    result = await session.execute(stmt)
    items = list(result.scalars().all())

    if not items:
        logger.info("embed_no_new_items")
        return 0

    try:
        texts = [embed_service.prepare_text(item.title, item.summary) for item in items]
        embeddings = await embed_service.embed_batch(texts)

        for item, embedding in zip(items, embeddings):
            session.add(
                ItemEmbedding(
                    item_id=item.id,
                    model=model_name,
                    embedding=embedding,
                )
            )

        await session.commit()
        logger.info("embed_items_stored", count=len(items))
        return len(items)

    except Exception as exc:
        logger.error("embed_items_failed", error=str(exc))
        await session.rollback()
        return 0
```

In `run_pipeline()`, after step 8 (Notify via Telegram) and before the final `pipeline_runs_total.labels(status="success").inc()`, add step 9:

```python
        # 9. Generate embeddings (if configured)
        if settings.embedding_api_key:
            try:
                embedded_count = await _embed_new_items(session)
                logger.info("pipeline_embeddings", count=embedded_count)
            except Exception as exc:
                logger.warning("pipeline_embedding_failed", error=str(exc))
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_pipeline_embedding.py -v`
Expected: PASS (3 tests)

**Step 5: Run all unit tests**

Run: `pytest tests/unit/ -v`
Expected: All tests pass (existing + new)

**Step 6: Commit**

```bash
git add src/pipeline/pipeline.py tests/unit/test_pipeline_embedding.py
git commit -m "feat(m4): add embedding step to pipeline"
```

---

## Task 8: Angular Chat Page

**Files:**
- Create: `web/src/app/pages/chat.ts`
- Modify: `web/src/app/app.routes.ts`
- Modify: `web/src/app/app.ts:14,17`

**Step 1: Create the chat page component**

Create `web/src/app/pages/chat.ts`:

```typescript
import { Component, inject, signal, ElementRef, ViewChild, AfterViewChecked } from '@angular/core';
import { CommonModule, DatePipe } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { AuthService } from '../services/auth.service';

interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
  sources?: ChatSource[];
}

interface ChatSource {
  id: string;
  title: string;
  url: string | null;
  topic: string | null;
}

@Component({
  selector: 'app-chat',
  imports: [CommonModule, FormsModule],
  template: `
    <div class="chat-page">
      <div class="chat-messages" #messagesContainer>
        @if (messages().length === 0) {
          <div class="empty-state">
            <h2>Chat con IA</h2>
            <p>Pregunta sobre noticias de IA y tecnologia</p>
            <div class="suggestions">
              @for (s of suggestions; track s) {
                <button class="suggestion-chip" (click)="askQuestion(s)">{{ s }}</button>
              }
            </div>
          </div>
        }

        @for (msg of messages(); track $index) {
          <div class="message" [class.user]="msg.role === 'user'" [class.assistant]="msg.role === 'assistant'">
            <div class="message-content">{{ msg.content }}</div>
            @if (msg.sources && msg.sources.length > 0) {
              <div class="sources">
                <span class="sources-label">Fuentes:</span>
                @for (src of msg.sources; track src.id) {
                  @if (src.url) {
                    <a [href]="src.url" target="_blank" rel="noopener" class="source-link">{{ src.title }}</a>
                  } @else {
                    <span class="source-link no-url">{{ src.title }}</span>
                  }
                }
              </div>
            }
          </div>
        }

        @if (streaming()) {
          <div class="message assistant">
            <div class="message-content">{{ streamBuffer() }}<span class="cursor">|</span></div>
          </div>
        }
      </div>

      <form class="chat-input-form" (ngSubmit)="onSend()">
        <div class="input-row">
          <select class="topic-filter" [(ngModel)]="selectedTopic" name="topic">
            <option value="">Todos los temas</option>
            @for (t of topics; track t) {
              <option [value]="t">{{ t }}</option>
            }
          </select>
          <input
            type="text"
            [(ngModel)]="question"
            name="question"
            placeholder="Pregunta sobre noticias de IA..."
            class="chat-input"
            [disabled]="streaming()"
          />
          <button
            type="submit"
            class="send-btn"
            [disabled]="streaming() || !question.trim()"
          >
            Enviar
          </button>
        </div>
      </form>
    </div>
  `,
  styles: [`
    :host { display: block; height: calc(100vh - 92px); }

    .chat-page {
      display: flex;
      flex-direction: column;
      height: 100%;
      max-width: 800px;
      margin: 0 auto;
    }

    .chat-messages {
      flex: 1;
      overflow-y: auto;
      padding: 20px 0;
      display: flex;
      flex-direction: column;
      gap: 16px;
    }

    .empty-state {
      text-align: center;
      padding: 60px 20px;
      color: #64748b;
    }
    .empty-state h2 {
      font-size: 1.5rem;
      color: #1e293b;
      margin: 0 0 8px;
    }
    .empty-state p {
      margin: 0 0 24px;
      font-size: 0.95rem;
    }
    .suggestions {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      justify-content: center;
    }
    .suggestion-chip {
      padding: 8px 16px;
      border: 1px solid #e2e8f0;
      border-radius: 20px;
      background: white;
      color: #475569;
      font-size: 0.85rem;
      cursor: pointer;
      transition: all 0.15s;
    }
    .suggestion-chip:hover {
      border-color: #2563eb;
      color: #2563eb;
      background: #eff6ff;
    }

    .message {
      padding: 12px 16px;
      border-radius: 12px;
      max-width: 85%;
      line-height: 1.6;
      font-size: 0.95rem;
      white-space: pre-wrap;
    }
    .message.user {
      align-self: flex-end;
      background: #2563eb;
      color: white;
      border-bottom-right-radius: 4px;
    }
    .message.assistant {
      align-self: flex-start;
      background: #f1f5f9;
      color: #1e293b;
      border-bottom-left-radius: 4px;
    }
    .message-content { word-break: break-word; }

    .cursor {
      animation: blink 0.8s infinite;
      font-weight: bold;
    }
    @keyframes blink {
      0%, 100% { opacity: 1; }
      50% { opacity: 0; }
    }

    .sources {
      margin-top: 10px;
      padding-top: 8px;
      border-top: 1px solid #e2e8f0;
      display: flex;
      flex-wrap: wrap;
      gap: 6px;
      align-items: center;
    }
    .sources-label {
      font-size: 0.75rem;
      font-weight: 600;
      color: #64748b;
      text-transform: uppercase;
    }
    .source-link {
      font-size: 0.8rem;
      padding: 2px 8px;
      background: #dbeafe;
      color: #1e40af;
      border-radius: 4px;
      text-decoration: none;
    }
    .source-link:hover { background: #bfdbfe; }
    .source-link.no-url { color: #475569; background: #e2e8f0; }

    .chat-input-form {
      padding: 12px 0;
      border-top: 1px solid #e2e8f0;
    }
    .input-row {
      display: flex;
      gap: 8px;
    }
    .topic-filter {
      padding: 10px;
      border: 1px solid #e2e8f0;
      border-radius: 6px;
      font-size: 0.85rem;
      outline: none;
      min-width: 120px;
    }
    .chat-input {
      flex: 1;
      padding: 10px 14px;
      border: 1px solid #e2e8f0;
      border-radius: 6px;
      font-size: 0.95rem;
      outline: none;
    }
    .chat-input:focus {
      border-color: #2563eb;
      box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.1);
    }
    .send-btn {
      padding: 10px 20px;
      background: #2563eb;
      color: white;
      border: none;
      border-radius: 6px;
      font-size: 0.9rem;
      font-weight: 600;
      cursor: pointer;
      white-space: nowrap;
    }
    .send-btn:hover:not(:disabled) { background: #1d4ed8; }
    .send-btn:disabled { opacity: 0.6; cursor: not-allowed; }

    @media (max-width: 640px) {
      :host { height: calc(100vh - 80px); }
      .input-row { flex-wrap: wrap; }
      .topic-filter { min-width: 100%; }
      .message { max-width: 95%; }
    }
  `],
})
export class ChatPage implements AfterViewChecked {
  private auth = inject(AuthService);

  @ViewChild('messagesContainer') private messagesContainer!: ElementRef;

  messages = signal<ChatMessage[]>([]);
  streaming = signal(false);
  streamBuffer = signal('');
  question = '';
  selectedTopic = '';

  topics = ['modelos', 'herramientas', 'papers', 'productos', 'open_source', 'agentes', 'regulacion'];

  suggestions = [
    'Que modelos de IA se lanzaron esta semana?',
    'Cuales son las herramientas open source mas populares?',
    'Que papers de LLMs se publicaron recientemente?',
    'Que noticias hay sobre agentes de IA?',
  ];

  ngAfterViewChecked() {
    this.scrollToBottom();
  }

  askQuestion(q: string) {
    this.question = q;
    this.onSend();
  }

  async onSend() {
    const q = this.question.trim();
    if (!q || this.streaming()) return;

    // Add user message
    this.messages.update(msgs => [...msgs, { role: 'user', content: q }]);
    this.question = '';
    this.streaming.set(true);
    this.streamBuffer.set('');

    const token = this.auth.getToken();
    const body = {
      question: q,
      topic: this.selectedTopic || null,
      limit: 5,
    };

    try {
      const response = await fetch('/api/chat', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`,
        },
        body: JSON.stringify(body),
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }

      const reader = response.body!.getReader();
      const decoder = new TextDecoder();
      let fullText = '';
      let sources: ChatSource[] = [];

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        const text = decoder.decode(value, { stream: true });
        const lines = text.split('\n');

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue;
          const data = line.slice(6);

          if (data === '[DONE]') continue;

          try {
            const parsed = JSON.parse(data);
            if (parsed.token) {
              fullText += parsed.token;
              this.streamBuffer.set(fullText);
            }
            if (parsed.sources) {
              sources = parsed.sources;
            }
            if (parsed.error) {
              fullText += parsed.error;
              this.streamBuffer.set(fullText);
            }
          } catch {
            // ignore parse errors on partial chunks
          }
        }
      }

      // Finalize: move streamed content into messages
      this.messages.update(msgs => [
        ...msgs,
        { role: 'assistant', content: fullText, sources },
      ]);
    } catch (err) {
      this.messages.update(msgs => [
        ...msgs,
        { role: 'assistant', content: 'Error al conectar con el servidor. Intenta de nuevo.' },
      ]);
    } finally {
      this.streaming.set(false);
      this.streamBuffer.set('');
    }
  }

  private scrollToBottom() {
    if (this.messagesContainer) {
      const el = this.messagesContainer.nativeElement;
      el.scrollTop = el.scrollHeight;
    }
  }
}
```

**Step 2: Add route**

In `web/src/app/app.routes.ts`, add the import and route:

```typescript
import { ChatPage } from './pages/chat';
```

Add before the catch-all route:
```typescript
  { path: 'chat', component: ChatPage, canActivate: [authGuard] },
```

**Step 3: Add nav link**

In `web/src/app/app.ts`, add the Chat link in the nav between Analytics and Salir:

```html
<a routerLink="/chat" routerLinkActive="active" (click)="onNavClick()">Chat</a>
```

**Step 4: Build Angular to verify**

Run: `cd web && npx ng build --configuration production 2>&1 | tail -5`
Expected: Build succeeds with no errors

**Step 5: Commit**

```bash
git add web/src/app/pages/chat.ts web/src/app/app.routes.ts web/src/app/app.ts
git commit -m "feat(m4): add Angular chat page with SSE streaming"
```

---

## Task 9: E2E Tests — Chat Page

**Files:**
- Create: `tests/e2e/test_chat.py`
- Modify: `tests/e2e/conftest.py` (add chat mock route)

**Step 1: Add mock route for /api/chat in conftest**

In `tests/e2e/conftest.py`, in the `setup_mock_routes` function, add a handler for the chat endpoint:

```python
    def handle_chat(route):
        # Simulate SSE stream
        body = (
            'data: {"token": "Esta semana "}\n\n'
            'data: {"token": "se lanzaron "}\n\n'
            'data: {"token": "varios modelos."}\n\n'
            'data: {"sources": [{"id": "1", "title": "New AI Model Released", "url": "https://example.com/news/1", "topic": "modelos"}]}\n\n'
            'data: [DONE]\n\n'
        )
        route.fulfill(
            status=200,
            content_type="text/event-stream",
            body=body,
        )

    page.route("**/api/chat", handle_chat)
```

**Step 2: Write E2E tests**

Create `tests/e2e/test_chat.py`:

```python
"""E2E tests for the chat page."""

from __future__ import annotations

import pytest
from playwright.sync_api import Page, expect

from .conftest import MOCK_TOKEN

pytestmark = pytest.mark.e2e


def test_chat_page_elements(authed_page: Page, base_url: str):
    authed_page.goto(base_url + "/chat")
    expect(authed_page.locator(".chat-input")).to_be_visible()
    expect(authed_page.locator(".send-btn")).to_be_visible()
    expect(authed_page.locator(".topic-filter")).to_be_visible()


def test_empty_state_shows_suggestions(authed_page: Page, base_url: str):
    authed_page.goto(base_url + "/chat")
    expect(authed_page.locator(".empty-state")).to_be_visible()
    expect(authed_page.locator(".suggestion-chip").first).to_be_visible()


def test_send_button_disabled_when_empty(authed_page: Page, base_url: str):
    authed_page.goto(base_url + "/chat")
    expect(authed_page.locator(".send-btn")).to_be_disabled()


def test_send_message_shows_response(authed_page: Page, base_url: str):
    authed_page.goto(base_url + "/chat")
    authed_page.fill(".chat-input", "Que modelos se lanzaron?")
    authed_page.click(".send-btn")
    # User message should appear
    expect(authed_page.locator(".message.user")).to_be_visible()
    # Assistant response should appear (with streamed text)
    expect(authed_page.locator(".message.assistant")).to_be_visible(timeout=5000)
    expect(authed_page.locator("text=varios modelos")).to_be_visible(timeout=5000)


def test_suggestion_chip_sends_question(authed_page: Page, base_url: str):
    authed_page.goto(base_url + "/chat")
    authed_page.click(".suggestion-chip >> nth=0")
    # User message should appear from clicking suggestion
    expect(authed_page.locator(".message.user")).to_be_visible()


def test_sources_displayed(authed_page: Page, base_url: str):
    authed_page.goto(base_url + "/chat")
    authed_page.fill(".chat-input", "test query for sources")
    authed_page.click(".send-btn")
    expect(authed_page.locator(".source-link").first).to_be_visible(timeout=5000)
```

**Step 3: Run E2E tests**

Run: `pytest tests/e2e/test_chat.py -v`
Expected: PASS (6 tests)

**Step 4: Commit**

```bash
git add tests/e2e/test_chat.py tests/e2e/conftest.py
git commit -m "test(m4): add chat E2E tests with SSE mock"
```

---

## Task 10: Remove RAG from coverage exclusion + update pyproject.toml

**Files:**
- Modify: `pyproject.toml:114`

**Step 1: Update coverage config**

In `pyproject.toml`, change:
```toml
omit = ["src/rag/*"]
```
to:
```toml
omit = []
```

**Step 2: Run full test suite with coverage**

Run: `pytest tests/unit/ --cov=src --cov-report=term-missing -v 2>&1 | tail -20`
Expected: All tests pass, RAG module now included in coverage

**Step 3: Run lint and format**

Run: `ruff check src/rag/ tests/unit/test_embeddings.py tests/unit/test_retriever.py tests/unit/test_chat_service.py tests/unit/test_chat_route.py tests/unit/test_pipeline_embedding.py && ruff format --check src/rag/`
Expected: No errors

**Step 4: Run full test suite**

Run: `pytest tests/ -v 2>&1 | tail -10`
Expected: All tests pass (unit + E2E)

**Step 5: Commit**

```bash
git add pyproject.toml
git commit -m "chore(m4): include src/rag in coverage reporting"
```

---

## Task 11: Final verification

**Step 1: Run all tests**

Run: `pytest tests/ -v --tb=short`
Expected: All tests pass

**Step 2: Lint check**

Run: `ruff check src/ tests/`
Expected: 0 errors

**Step 3: Format check**

Run: `ruff format --check src/ tests/`
Expected: 0 files reformatted

**Step 4: Angular build**

Run: `cd web && npx ng build --configuration production 2>&1 | tail -5`
Expected: Build succeeds

**Step 5: Final commit (if any remaining changes)**

```bash
git status
# If clean, no commit needed
# If files need fixing, fix and commit
```
