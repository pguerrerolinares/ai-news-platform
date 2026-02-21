"""Unit tests for historical backfill extractors."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.pipeline.backfill.extractors import (
    HistoricalHNExtractor,
    generate_month_ranges,
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
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json = MagicMock(return_value=page)

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_resp)

        extractor = HistoricalHNExtractor(min_points=10, queries=["AI", "LLM"])
        items = await extractor.fetch_month(mock_client, "2024-01", "2024-02")

        assert len(items) == 1  # same objectID, deduplicated
