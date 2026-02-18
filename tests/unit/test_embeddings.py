"""Tests for the embedding service."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.core.config import Settings
from src.rag.embeddings import EmbeddingService


def _mock_settings(**overrides):
    defaults = {
        "embedding_api_key": "sk-test-key",
        "embedding_base_url": "https://api.openai.com/v1",
        "embedding_model": "text-embedding-3-small",
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
        long_text = "word " * 10000
        with patch("src.rag.embeddings.get_settings", return_value=_mock_settings()):
            service = EmbeddingService(client=mock_client)
            await service.embed_text(long_text)
        call_kwargs = mock_client.embeddings.create.call_args
        sent_input = call_kwargs.kwargs["input"]
        assert len(sent_input) <= 32000


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
        texts = [f"text {i}" for i in range(150)]
        mock_client = AsyncMock()
        mock_client.embeddings.create.side_effect = [
            MagicMock(data=[MagicMock(embedding=_fake_embedding()) for _ in range(100)]),
            MagicMock(data=[MagicMock(embedding=_fake_embedding()) for _ in range(50)]),
        ]
        with patch("src.rag.embeddings.get_settings", return_value=_mock_settings()):
            service = EmbeddingService(client=mock_client)
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
