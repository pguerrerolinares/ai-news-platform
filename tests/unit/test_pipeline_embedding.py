"""Tests for the embedding step in the pipeline."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

from src.core.config import Settings
from src.pipeline.stages.store import embed_new_items


def _mock_settings(**overrides):
    defaults = {
        "embedding_api_key": "sk-test",
        "embedding_base_url": "https://api.openai.com/v1",
        "embedding_model": "text-embedding-3-small",
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


def _make_session():
    """Create a mock session with sync add() and async execute/commit/rollback."""
    session = MagicMock()
    session.execute = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    return session


class TestEmbedNewItems:
    async def test_embeds_items_without_embeddings(self):
        session = _make_session()
        items = [_make_item("Title 1"), _make_item("Title 2")]
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = items
        session.execute.return_value = mock_result

        mock_embed_service = AsyncMock()
        mock_embed_service.embed_batch.return_value = [[0.1] * 1536, [0.2] * 1536]
        mock_embed_service.prepare_text.side_effect = lambda t, s: f"{t}\n{s}" if s else t

        with patch("src.pipeline.stages.store.get_settings", return_value=_mock_settings()):
            count = await embed_new_items(session, mock_embed_service)
        assert count == 2
        mock_embed_service.embed_batch.assert_called_once()

    async def test_skips_when_no_items(self):
        session = _make_session()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        session.execute.return_value = mock_result

        mock_embed_service = AsyncMock()

        with patch("src.pipeline.stages.store.get_settings", return_value=_mock_settings()):
            count = await embed_new_items(session, mock_embed_service)
        assert count == 0
        mock_embed_service.embed_batch.assert_not_called()

    async def test_handles_embedding_error(self):
        session = _make_session()
        items = [_make_item()]
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = items
        session.execute.return_value = mock_result

        mock_embed_service = AsyncMock()
        mock_embed_service.prepare_text.return_value = "Title\nSummary"
        mock_embed_service.embed_batch.side_effect = Exception("API error")

        with patch("src.pipeline.stages.store.get_settings", return_value=_mock_settings()):
            count = await embed_new_items(session, mock_embed_service)
        assert count == 0

    async def test_commits_after_storing(self):
        session = _make_session()
        items = [_make_item()]
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = items
        session.execute.return_value = mock_result

        mock_embed_service = AsyncMock()
        mock_embed_service.embed_batch.return_value = [[0.1] * 1536]
        mock_embed_service.prepare_text.return_value = "Title\nSummary"

        with patch("src.pipeline.stages.store.get_settings", return_value=_mock_settings()):
            await embed_new_items(session, mock_embed_service)
        session.commit.assert_called_once()

    async def test_rollback_on_error(self):
        session = _make_session()
        items = [_make_item()]
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = items
        session.execute.return_value = mock_result

        mock_embed_service = AsyncMock()
        mock_embed_service.prepare_text.return_value = "Title"
        mock_embed_service.embed_batch.side_effect = Exception("fail")

        with patch("src.pipeline.stages.store.get_settings", return_value=_mock_settings()):
            await embed_new_items(session, mock_embed_service)
        session.rollback.assert_called_once()
