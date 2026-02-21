"""Tests for embedding configuration settings."""

from __future__ import annotations

from src.core.config import Settings


class TestEmbeddingConfig:
    def test_defaults(self):
        s = Settings(
            embedding_api_key="",
            embedding_base_url="https://api.openai.com/v1",
            embedding_model="text-embedding-3-small",
            telegram_bot_token="",
            telegram_chat_id="",
            telegram_alerts_enabled=False,
        )
        assert s.embedding_api_key == ""
        assert s.embedding_base_url == "https://api.openai.com/v1"
        assert s.embedding_model == "text-embedding-3-small"

    def test_custom_values(self):
        s = Settings(
            embedding_api_key="sk-test-123",
            embedding_base_url="https://custom.api.com/v1",
            embedding_model="custom-model",
            telegram_bot_token="",
            telegram_chat_id="",
            telegram_alerts_enabled=False,
        )
        assert s.embedding_api_key == "sk-test-123"
        assert s.embedding_base_url == "https://custom.api.com/v1"
        assert s.embedding_model == "custom-model"

    def test_embedding_not_configured_when_empty_key(self):
        s = Settings(
            embedding_api_key="",
            telegram_bot_token="",
            telegram_chat_id="",
            telegram_alerts_enabled=False,
        )
        assert s.embedding_api_key == ""
        assert not s.embedding_api_key
