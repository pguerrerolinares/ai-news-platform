"""Tests for the HuggingFace extractor."""

from __future__ import annotations

from unittest.mock import patch

import httpx
import pytest
import respx

from src.core.config import Settings
from src.extractors.base import ExtractedItem
from src.extractors.huggingface import API_URL, HuggingFaceExtractor


def _make_model(
    model_id: str = "meta-llama/Llama-3-8B",
    author: str = "meta-llama",
    downloads: int = 50000,
    likes: int = 1200,
    pipeline_tag: str = "text-generation",
    tags: list[str] | None = None,
    last_modified: str = "2026-02-17T10:00:00.000Z",
    card_data: dict | None = None,
) -> dict:
    return {
        "modelId": model_id,
        "id": model_id,
        "author": author,
        "downloads": downloads,
        "likes": likes,
        "pipeline_tag": pipeline_tag,
        "tags": tags or ["text-generation", "pytorch"],
        "lastModified": last_modified,
        "cardData": card_data,
    }


def _mock_settings(**overrides):
    defaults = {
        "hf_min_downloads": 100,
        "max_items_per_source": 50,
        "enabled_sources": "huggingface",
        "telegram_bot_token": "",
        "telegram_chat_id": "",
        "telegram_alerts_enabled": False,
    }
    defaults.update(overrides)
    return Settings(**defaults)


class TestSourceName:
    def test_returns_huggingface(self):
        assert HuggingFaceExtractor().source_name == "huggingface"


class TestExtract:
    @respx.mock
    async def test_returns_list_of_extracted_items(self):
        models = [_make_model("org/model-a", downloads=5000), _make_model("org/model-b", downloads=3000)]
        respx.get(API_URL).mock(return_value=httpx.Response(200, json=models))

        with patch("src.extractors.huggingface.get_settings", return_value=_mock_settings()):
            result = await HuggingFaceExtractor().extract()

        assert isinstance(result, list)
        assert len(result) == 2
        for item in result:
            assert isinstance(item, ExtractedItem)

    @respx.mock
    async def test_items_have_correct_source(self):
        respx.get(API_URL).mock(return_value=httpx.Response(200, json=[_make_model()]))
        with patch("src.extractors.huggingface.get_settings", return_value=_mock_settings()):
            result = await HuggingFaceExtractor().extract()
        assert all(item.source == "huggingface" for item in result)

    @respx.mock
    async def test_items_sorted_by_downloads_descending(self):
        models = [
            _make_model("a/low", downloads=200),
            _make_model("a/high", downloads=90000),
            _make_model("a/mid", downloads=5000),
        ]
        respx.get(API_URL).mock(return_value=httpx.Response(200, json=models))
        with patch("src.extractors.huggingface.get_settings", return_value=_mock_settings()):
            result = await HuggingFaceExtractor().extract()
        scores = [item.score for item in result]
        assert scores == [90000, 5000, 200]

    @respx.mock
    async def test_filters_below_min_downloads(self):
        models = [
            _make_model("a/popular", downloads=5000),
            _make_model("a/unpopular", downloads=10),
        ]
        respx.get(API_URL).mock(return_value=httpx.Response(200, json=models))
        with patch("src.extractors.huggingface.get_settings", return_value=_mock_settings(hf_min_downloads=100)):
            result = await HuggingFaceExtractor().extract()
        assert len(result) == 1
        assert result[0].title == "a/popular"

    @respx.mock
    async def test_url_points_to_huggingface(self):
        respx.get(API_URL).mock(return_value=httpx.Response(200, json=[_make_model("org/my-model")]))
        with patch("src.extractors.huggingface.get_settings", return_value=_mock_settings()):
            result = await HuggingFaceExtractor().extract()
        assert result[0].url == "https://huggingface.co/org/my-model"

    @respx.mock
    async def test_metadata_has_expected_keys(self):
        model = _make_model(pipeline_tag="image-classification", downloads=9999, likes=500, tags=["pytorch", "vision"])
        respx.get(API_URL).mock(return_value=httpx.Response(200, json=[model]))
        with patch("src.extractors.huggingface.get_settings", return_value=_mock_settings()):
            result = await HuggingFaceExtractor().extract()
        meta = result[0].metadata
        assert meta["pipeline_tag"] == "image-classification"
        assert meta["downloads"] == 9999
        assert meta["likes"] == 500
        assert "pytorch" in meta["tags"]

    @respx.mock
    async def test_respects_max_items_per_source(self):
        models = [_make_model(f"org/model-{i}", downloads=1000 + i) for i in range(10)]
        respx.get(API_URL).mock(return_value=httpx.Response(200, json=models))
        with patch("src.extractors.huggingface.get_settings", return_value=_mock_settings(max_items_per_source=3)):
            result = await HuggingFaceExtractor().extract()
        assert len(result) <= 3

    @respx.mock
    async def test_handles_api_error(self):
        respx.get(API_URL).mock(return_value=httpx.Response(500, text="Internal Server Error"))
        with patch("src.extractors.huggingface.get_settings", return_value=_mock_settings()):
            result = await HuggingFaceExtractor().extract()
        assert result == []

    @respx.mock
    async def test_handles_network_error(self):
        respx.get(API_URL).mock(side_effect=httpx.ConnectError("connection failed"))
        with patch("src.extractors.huggingface.get_settings", return_value=_mock_settings()):
            result = await HuggingFaceExtractor().extract()
        assert result == []

    @respx.mock
    async def test_empty_response(self):
        respx.get(API_URL).mock(return_value=httpx.Response(200, json=[]))
        with patch("src.extractors.huggingface.get_settings", return_value=_mock_settings()):
            result = await HuggingFaceExtractor().extract()
        assert result == []

    @respx.mock
    async def test_deduplication_by_model_url(self):
        model = _make_model("org/same-model")
        respx.get(API_URL).mock(return_value=httpx.Response(200, json=[model, model]))
        with patch("src.extractors.huggingface.get_settings", return_value=_mock_settings()):
            result = await HuggingFaceExtractor().extract()
        assert len(result) == 1

    @respx.mock
    async def test_author_from_model_id(self):
        respx.get(API_URL).mock(return_value=httpx.Response(200, json=[_make_model("google/gemma-2b", author="google")]))
        with patch("src.extractors.huggingface.get_settings", return_value=_mock_settings()):
            result = await HuggingFaceExtractor().extract()
        assert result[0].author == "google"
