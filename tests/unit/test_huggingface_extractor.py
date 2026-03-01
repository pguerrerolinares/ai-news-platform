"""Tests for the HuggingFace extractor."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import httpx
import respx

from src.core.config import Settings
from src.extractors.base import ExtractedItem
from src.extractors.huggingface import API_URL, DAILY_PAPERS_URL, HuggingFaceExtractor


def _recent_iso() -> str:
    """Return an ISO 8601 date string for 1 hour ago (always within 48h window)."""
    dt = datetime.now(tz=UTC) - timedelta(hours=1)
    return dt.strftime("%Y-%m-%dT%H:%M:%S.000Z")


def _make_model(
    model_id: str = "meta-llama/Llama-3-8B",
    author: str = "meta-llama",
    downloads: int = 50000,
    likes: int = 1200,
    pipeline_tag: str = "text-generation",
    tags: list[str] | None = None,
    last_modified: str | None = None,
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
        "lastModified": last_modified or _recent_iso(),
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
        models = [
            _make_model("org/model-a", downloads=5000),
            _make_model("org/model-b", downloads=3000),
        ]
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
        with patch(
            "src.extractors.huggingface.get_settings",
            return_value=_mock_settings(hf_min_downloads=100),
        ):
            result = await HuggingFaceExtractor().extract()
        assert len(result) == 1
        assert result[0].title == "a/popular"

    @respx.mock
    async def test_url_points_to_huggingface(self):
        respx.get(API_URL).mock(
            return_value=httpx.Response(200, json=[_make_model("org/my-model")])
        )
        with patch("src.extractors.huggingface.get_settings", return_value=_mock_settings()):
            result = await HuggingFaceExtractor().extract()
        assert result[0].url == "https://huggingface.co/org/my-model"

    @respx.mock
    async def test_metadata_has_expected_keys(self):
        model = _make_model(
            pipeline_tag="image-classification",
            downloads=9999,
            likes=500,
            tags=["pytorch", "vision"],
        )
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
        with patch(
            "src.extractors.huggingface.get_settings",
            return_value=_mock_settings(max_items_per_source=3),
        ):
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
        respx.get(API_URL).mock(
            return_value=httpx.Response(200, json=[_make_model("google/gemma-2b", author="google")])
        )
        with patch("src.extractors.huggingface.get_settings", return_value=_mock_settings()):
            result = await HuggingFaceExtractor().extract()
        assert result[0].author == "google"

    @respx.mock
    async def test_since_hours_filters_old_models(self):
        old_date = (datetime.now(tz=UTC) - timedelta(hours=72)).isoformat().replace("+00:00", "Z")
        model = _make_model("org/old-model", last_modified=old_date)
        respx.get(API_URL).mock(return_value=httpx.Response(200, json=[model]))
        with patch("src.extractors.huggingface.get_settings", return_value=_mock_settings()):
            result = await HuggingFaceExtractor().extract(since_hours=48)
        assert result == []

    @respx.mock
    async def test_since_hours_includes_recent_models(self):
        recent_date = (datetime.now(tz=UTC) - timedelta(hours=1)).isoformat().replace("+00:00", "Z")
        model = _make_model("org/recent-model", last_modified=recent_date)
        respx.get(API_URL).mock(return_value=httpx.Response(200, json=[model]))
        with patch("src.extractors.huggingface.get_settings", return_value=_mock_settings()):
            result = await HuggingFaceExtractor().extract(since_hours=48)
        assert len(result) == 1
        assert result[0].title == "org/recent-model"

    @respx.mock
    async def test_model_without_author_uses_model_id_prefix(self):
        model = _make_model("meta-llama/Llama-3-8B")
        del model["author"]
        respx.get(API_URL).mock(return_value=httpx.Response(200, json=[model]))
        with patch("src.extractors.huggingface.get_settings", return_value=_mock_settings()):
            result = await HuggingFaceExtractor().extract()
        assert result[0].author == "meta-llama"

    @respx.mock
    async def test_model_without_slash_in_id_uses_unknown(self):
        model = _make_model("singleton", downloads=5000)
        del model["author"]
        respx.get(API_URL).mock(return_value=httpx.Response(200, json=[model]))
        with patch("src.extractors.huggingface.get_settings", return_value=_mock_settings()):
            result = await HuggingFaceExtractor().extract()
        assert result[0].author == "unknown"

    @respx.mock
    async def test_invalid_last_modified_returns_none(self):
        model = _make_model("org/bad-date", last_modified="not-a-date")
        respx.get(API_URL).mock(return_value=httpx.Response(200, json=[model]))
        with patch("src.extractors.huggingface.get_settings", return_value=_mock_settings()):
            result = await HuggingFaceExtractor().extract(since_hours=48)
        assert len(result) == 1
        assert result[0].title == "org/bad-date"

    @respx.mock
    async def test_model_with_zero_downloads_filtered(self):
        model = _make_model("org/no-downloads", downloads=0)
        respx.get(API_URL).mock(return_value=httpx.Response(200, json=[model]))
        with patch(
            "src.extractors.huggingface.get_settings",
            return_value=_mock_settings(hf_min_downloads=100),
        ):
            result = await HuggingFaceExtractor().extract()
        assert result == []

    @respx.mock
    async def test_score_is_downloads_count(self):
        model = _make_model("org/scored-model", downloads=42000)
        respx.get(API_URL).mock(return_value=httpx.Response(200, json=[model]))
        with patch("src.extractors.huggingface.get_settings", return_value=_mock_settings()):
            result = await HuggingFaceExtractor().extract()
        assert result[0].score == 42000


def _make_daily_paper(
    title: str = "Attention Is All You Need v2",
    paper_id: str = "2401.12345",
    authors: list[str] | None = None,
    upvotes: int = 42,
    published_at: str | None = None,
) -> dict:
    if authors is None:
        authors = ["Author A", "Author B"]
    if published_at is None:
        published_at = _recent_iso()
    return {
        "paper": {
            "id": paper_id,
            "title": title,
            "authors": [{"name": a} for a in authors],
            "publishedAt": published_at,
            "upvotes": upvotes,
        },
    }


class TestDailyPapers:
    @respx.mock
    async def test_daily_papers_included_in_results(self):
        respx.get(API_URL).mock(return_value=httpx.Response(200, json=[]))
        papers = [_make_daily_paper("Cool Paper", "2401.00001", upvotes=50)]
        respx.get(DAILY_PAPERS_URL).mock(return_value=httpx.Response(200, json=papers))

        with patch("src.extractors.huggingface.get_settings", return_value=_mock_settings()):
            result = await HuggingFaceExtractor().extract()

        assert len(result) == 1
        assert result[0].title == "Cool Paper"
        assert result[0].url == "https://arxiv.org/abs/2401.00001"
        assert result[0].source == "huggingface"

    @respx.mock
    async def test_daily_papers_deduped_with_models(self):
        models = [_make_model("org/model-a", downloads=5000)]
        respx.get(API_URL).mock(return_value=httpx.Response(200, json=models))
        papers = [_make_daily_paper("Same URL Paper", "2401.00001")]
        respx.get(DAILY_PAPERS_URL).mock(return_value=httpx.Response(200, json=papers))

        with patch("src.extractors.huggingface.get_settings", return_value=_mock_settings()):
            result = await HuggingFaceExtractor().extract()

        urls = {item.url for item in result}
        assert "https://huggingface.co/org/model-a" in urls
        assert "https://arxiv.org/abs/2401.00001" in urls

    @respx.mock
    async def test_daily_papers_api_failure_still_returns_models(self):
        models = [_make_model("org/model-b", downloads=3000)]
        respx.get(API_URL).mock(return_value=httpx.Response(200, json=models))
        respx.get(DAILY_PAPERS_URL).mock(return_value=httpx.Response(500, text="Server Error"))

        with patch("src.extractors.huggingface.get_settings", return_value=_mock_settings()):
            result = await HuggingFaceExtractor().extract()

        assert len(result) == 1
        assert result[0].title == "org/model-b"

    @respx.mock
    async def test_daily_papers_author_from_first_author(self):
        authors = ["Alice", "Bob", "Charlie"]
        papers = [_make_daily_paper("Multi Author Paper", "2401.99999", authors=authors)]
        respx.get(API_URL).mock(return_value=httpx.Response(200, json=[]))
        respx.get(DAILY_PAPERS_URL).mock(return_value=httpx.Response(200, json=papers))

        with patch("src.extractors.huggingface.get_settings", return_value=_mock_settings()):
            result = await HuggingFaceExtractor().extract()

        assert result[0].author == "Alice"


class TestSourceCreatedAt:
    """Tests for source_created_at capture."""

    @respx.mock
    async def test_extract_models_captures_created_at(self):
        """source_created_at should be set from HF model createdAt field."""
        model = _make_model("org/model-x", downloads=5000)
        model["createdAt"] = "2025-01-10T08:00:00Z"
        respx.get(API_URL).mock(return_value=httpx.Response(200, json=[model]))
        respx.get(DAILY_PAPERS_URL).mock(return_value=httpx.Response(200, json=[]))
        with patch("src.extractors.huggingface.get_settings", return_value=_mock_settings()):
            result = await HuggingFaceExtractor().extract()
        assert result[0].source_created_at is not None
        assert result[0].source_created_at.year == 2025
        assert result[0].source_created_at.month == 1

    @respx.mock
    async def test_missing_created_at_returns_none(self):
        """source_created_at should be None when createdAt is missing."""
        model = _make_model("org/no-created", downloads=5000)
        respx.get(API_URL).mock(return_value=httpx.Response(200, json=[model]))
        respx.get(DAILY_PAPERS_URL).mock(return_value=httpx.Response(200, json=[]))
        with patch("src.extractors.huggingface.get_settings", return_value=_mock_settings()):
            result = await HuggingFaceExtractor().extract()
        assert result[0].source_created_at is None

    @respx.mock
    async def test_model_metadata_includes_type(self):
        """Model metadata should include type='model' for velocity calculation."""
        model = _make_model("org/typed-model", downloads=5000)
        respx.get(API_URL).mock(return_value=httpx.Response(200, json=[model]))
        respx.get(DAILY_PAPERS_URL).mock(return_value=httpx.Response(200, json=[]))
        with patch("src.extractors.huggingface.get_settings", return_value=_mock_settings()):
            result = await HuggingFaceExtractor().extract()
        assert result[0].metadata["type"] == "model"


class TestEdgeCases:
    """Edge-case tests for HuggingFaceExtractor robustness."""

    @respx.mock
    async def test_model_no_pipeline_tag(self):
        """Model without pipeline_tag is still extracted with None in metadata."""
        model = _make_model("org/no-pipe", downloads=5000)
        del model["pipeline_tag"]
        respx.get(API_URL).mock(return_value=httpx.Response(200, json=[model]))
        with patch("src.extractors.huggingface.get_settings", return_value=_mock_settings()):
            result = await HuggingFaceExtractor().extract()
        assert len(result) == 1
        assert result[0].metadata["pipeline_tag"] is None

    @respx.mock
    async def test_missing_model_id_keys(self):
        """Model missing both modelId and id falls back to empty string."""
        model = _make_model("org/fallback", downloads=5000)
        del model["modelId"]
        del model["id"]
        respx.get(API_URL).mock(return_value=httpx.Response(200, json=[model]))
        with patch("src.extractors.huggingface.get_settings", return_value=_mock_settings()):
            result = await HuggingFaceExtractor().extract()
        assert len(result) == 1
        assert result[0].url == "https://huggingface.co/"

    @respx.mock
    async def test_http_timeout(self):
        """Timeout returns []."""
        respx.get(API_URL).mock(side_effect=httpx.TimeoutException("read timed out"))
        with patch("src.extractors.huggingface.get_settings", return_value=_mock_settings()):
            result = await HuggingFaceExtractor().extract()
        assert result == []
