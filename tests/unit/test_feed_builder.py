"""Tests for FeedBuilder orchestrator."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.feed.feed_builder import FeedBuilder


def _make_item(
    *,
    title: str = "Test Item",
    source: str = "hackernews",
    topic: str = "models",
    composite_score: float = 0.8,
    score: int = 100,
    author: str | None = None,
) -> SimpleNamespace:
    """Create a mock NewsItem-like object."""
    return SimpleNamespace(
        title=title,
        source=source,
        topic=topic,
        composite_score=composite_score,
        score=score,
        author=author,
    )


def _make_mock_session(items: list) -> AsyncMock:
    """Create a mock async session that returns the given items."""
    mock_result = MagicMock()
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = items
    mock_result.scalars.return_value = mock_scalars

    session = AsyncMock()
    session.execute = AsyncMock(return_value=mock_result)
    return session


def _make_settings(**overrides: object) -> SimpleNamespace:
    """Create a mock Settings object with feed defaults."""
    defaults = {
        "feed_mmr_lambda": 0.7,
        "feed_candidate_multiplier": 5,
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


@pytest.mark.asyncio
@patch("src.feed.feed_builder.get_settings")
async def test_build_returns_items_and_count(mock_get_settings: MagicMock) -> None:
    """Basic flow: items are fetched, collapsed, ranked, and returned with count."""
    mock_get_settings.return_value = _make_settings()
    items = [
        _make_item(title="Item A", composite_score=0.9),
        _make_item(title="Item B", composite_score=0.7),
        _make_item(title="Item C", composite_score=0.5),
    ]
    session = _make_mock_session(items)

    builder = FeedBuilder(session)
    result, total = await builder.build(limit=10)

    assert len(result) == 3
    assert total == 3
    session.execute.assert_awaited_once()


@pytest.mark.asyncio
@patch("src.feed.feed_builder.get_settings")
async def test_build_with_topic_filter(mock_get_settings: MagicMock) -> None:
    """Verify topic filter is applied to the query."""
    mock_get_settings.return_value = _make_settings()
    items = [_make_item(topic="papers", composite_score=0.8)]
    session = _make_mock_session(items)

    builder = FeedBuilder(session)
    result, total = await builder.build(topic="papers", limit=10)

    assert len(result) == 1
    assert total == 1
    # Verify execute was called (topic filter is in the query)
    session.execute.assert_awaited_once()


@pytest.mark.asyncio
@patch("src.feed.feed_builder.get_settings")
async def test_build_with_empty_results(mock_get_settings: MagicMock) -> None:
    """Returns ([], 0) when no candidates exist."""
    mock_get_settings.return_value = _make_settings()
    session = _make_mock_session([])

    builder = FeedBuilder(session)
    result, total = await builder.build(limit=20)

    assert result == []
    assert total == 0


@pytest.mark.asyncio
@patch("src.feed.feed_builder.get_settings")
async def test_build_respects_offset_and_limit(mock_get_settings: MagicMock) -> None:
    """Pagination: offset and limit slice the ranked results correctly."""
    mock_get_settings.return_value = _make_settings()
    items = [
        _make_item(title=f"Item {i}", composite_score=1.0 - i * 0.1, source=f"src{i}")
        for i in range(10)
    ]
    session = _make_mock_session(items)

    builder = FeedBuilder(session)

    # First page
    page1, total1 = await builder.build(limit=3, offset=0)
    assert len(page1) == 3
    assert total1 == 10

    # Second page (re-create session mock for fresh call)
    session2 = _make_mock_session(items)
    builder2 = FeedBuilder(session2)
    page2, total2 = await builder2.build(limit=3, offset=3)
    assert len(page2) == 3
    assert total2 == 10


@pytest.mark.asyncio
@patch("src.feed.feed_builder.get_settings")
async def test_build_filters_null_composite_scores(mock_get_settings: MagicMock) -> None:
    """Only items with composite_score are fetched (filter is in the query).

    The mock session simulates DB already filtering nulls, so all returned
    items should have composite_score set.
    """
    mock_get_settings.return_value = _make_settings()
    # Simulate DB returning only items with composite_score (nulls filtered by query)
    items = [
        _make_item(title="Scored Item A", composite_score=0.9),
        _make_item(title="Scored Item B", composite_score=0.6),
    ]
    session = _make_mock_session(items)

    builder = FeedBuilder(session)
    result, total = await builder.build(limit=10)

    assert len(result) == 2
    assert total == 2
    # All returned items have composite_score
    for item in result:
        assert item.composite_score is not None
