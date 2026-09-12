"""Unit tests for historical backfill extractors."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from src.pipeline.backfill.extractors import (
    HistoricalHNExtractor,
    generate_month_ranges,
    request_with_retry,
)

pytestmark = pytest.mark.asyncio(loop_scope="session")


class TestMonthRanges:
    def test_generates_correct_ranges(self) -> None:
        ranges = generate_month_ranges("2024-01", "2024-03")
        assert len(ranges) == 3
        assert ranges[0] == ("2024-01", "2024-02")
        assert ranges[1] == ("2024-02", "2024-03")
        assert ranges[2] == ("2024-03", "2024-04")

    def test_single_month(self) -> None:
        ranges = generate_month_ranges("2024-06", "2024-06")
        assert len(ranges) == 1


class TestHistoricalHNExtractor:
    async def test_paginates_through_all_pages(self) -> None:
        """Must fetch all pages, not just page 0."""
        page0 = {
            "hits": [
                {
                    "objectID": "1",
                    "title": "AI",
                    "url": "http://a.com",
                    "points": 100,
                    "created_at_i": 1704067200,
                    "author": "u1",
                    "num_comments": 5,
                }
            ],
            "nbPages": 2,
        }
        page1 = {
            "hits": [
                {
                    "objectID": "2",
                    "title": "LLM",
                    "url": "http://b.com",
                    "points": 200,
                    "created_at_i": 1704067200,
                    "author": "u2",
                    "num_comments": 3,
                }
            ],
            "nbPages": 2,
        }

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json = MagicMock(side_effect=[page0, page1])

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_resp)

        extractor = HistoricalHNExtractor(min_points=10, queries=["AI"])
        items = await extractor.fetch_month(mock_client, "2024-01", "2024-02")

        assert len(items) == 2
        assert mock_client.get.call_count == 2  # 2 pages

    async def test_deduplicates_by_story_id(self) -> None:
        """Same objectID across queries should not produce duplicates."""
        page = {
            "hits": [
                {
                    "objectID": "1",
                    "title": "AI",
                    "url": "http://a.com",
                    "points": 100,
                    "created_at_i": 1704067200,
                    "author": "u1",
                    "num_comments": 5,
                }
            ],
            "nbPages": 1,
        }

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json = MagicMock(return_value=page)

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_resp)

        extractor = HistoricalHNExtractor(min_points=10, queries=["AI", "LLM"])
        items = await extractor.fetch_month(mock_client, "2024-01", "2024-02")

        assert len(items) == 1  # same objectID, deduplicated

    async def test_pagination_recovers_from_mid_stream_429(self) -> None:
        """A transient 429 between pages must not lose data: retry succeeds and
        pagination continues to completion instead of aborting mid-fetch.
        """
        page0 = {
            "hits": [
                {
                    "objectID": "1",
                    "title": "AI",
                    "points": 100,
                    "created_at_i": 1704067200,
                }
            ],
            "nbPages": 2,
        }
        page1 = {
            "hits": [
                {
                    "objectID": "2",
                    "title": "LLM",
                    "points": 200,
                    "created_at_i": 1704067200,
                }
            ],
            "nbPages": 2,
        }

        resp_page0 = MagicMock()
        resp_page0.status_code = 200
        resp_page0.raise_for_status = MagicMock()
        resp_page0.json = MagicMock(return_value=page0)

        resp_429 = MagicMock()
        resp_429.status_code = 429
        resp_429.headers = {"Retry-After": "0"}

        resp_page1 = MagicMock()
        resp_page1.status_code = 200
        resp_page1.raise_for_status = MagicMock()
        resp_page1.json = MagicMock(return_value=page1)

        mock_client = AsyncMock()
        # page 0 succeeds; fetching page 1 hits a transient 429, then succeeds on retry.
        mock_client.get = AsyncMock(side_effect=[resp_page0, resp_429, resp_page1])

        extractor = HistoricalHNExtractor(min_points=10, queries=["AI"])
        items = await extractor.fetch_month(mock_client, "2024-01", "2024-02")

        assert {item.source_id for item in items} == {"1", "2"}
        assert mock_client.get.call_count == 3  # page0 + 429 + retried page1


class TestRequestWithRetry:
    """Tests for the shared retry/backoff wrapper used by all backfill extractors."""

    async def test_succeeds_immediately_on_200(self) -> None:
        resp = MagicMock()
        resp.status_code = 200
        resp.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=resp)

        result = await request_with_retry(mock_client, "https://example.com")

        assert result is resp
        assert mock_client.get.call_count == 1

    async def test_retries_after_429_then_succeeds(self) -> None:
        resp_429 = MagicMock()
        resp_429.status_code = 429
        resp_429.headers = {"Retry-After": "0"}

        resp_200 = MagicMock()
        resp_200.status_code = 200
        resp_200.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=[resp_429, resp_200])

        result = await request_with_retry(mock_client, "https://example.com")

        assert result is resp_200
        assert mock_client.get.call_count == 2

    async def test_retries_after_5xx_then_succeeds(self, monkeypatch: pytest.MonkeyPatch) -> None:
        resp_500 = MagicMock()
        resp_500.status_code = 500
        resp_500.headers = {}

        resp_200 = MagicMock()
        resp_200.status_code = 200
        resp_200.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=[resp_500, resp_200])

        monkeypatch.setattr("src.pipeline.backfill.extractors.asyncio.sleep", AsyncMock())

        result = await request_with_retry(mock_client, "https://example.com")

        assert result is resp_200
        assert mock_client.get.call_count == 2

    async def test_exhausts_retries_and_raises_on_persistent_5xx(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When every attempt (including the final one) keeps failing, the
        original HTTP error must propagate instead of being swallowed.
        """
        resp_500 = MagicMock()
        resp_500.status_code = 500
        resp_500.headers = {}

        resp_final = MagicMock()
        resp_final.status_code = 500
        resp_final.raise_for_status = MagicMock(
            side_effect=httpx.HTTPStatusError(
                "server error", request=MagicMock(), response=resp_final
            )
        )

        mock_client = AsyncMock()
        # _MAX_RETRIES (3) failing attempts + one final unretried attempt.
        mock_client.get = AsyncMock(side_effect=[resp_500, resp_500, resp_500, resp_final])

        monkeypatch.setattr("src.pipeline.backfill.extractors.asyncio.sleep", AsyncMock())

        with pytest.raises(httpx.HTTPStatusError):
            await request_with_retry(mock_client, "https://example.com")

        assert mock_client.get.call_count == 4
