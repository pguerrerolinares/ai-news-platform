"""Tests for src.pipeline.pipeline -- pipeline orchestration."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.classifiers.base import ClassifiedItem
from src.extractors.arxiv import ArxivExtractor
from src.extractors.base import ExtractedItem
from src.extractors.hackernews import HackerNewsExtractor
from src.extractors.reddit import RedditExtractor
from src.extractors.rss import RSSExtractor
from src.pipeline.dedup import deduplicate_items
from src.pipeline.pipeline import (
    _extract_all,
    _get_extractors,
    _save_briefing,
    _store_classified_items,
    run_pipeline,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _mock_settings(**overrides):
    """Return a Settings instance suitable for pipeline tests."""
    from src.core.config import Settings

    defaults = {
        "enabled_sources": "hackernews",
        "telegram_bot_token": "",
        "telegram_chat_id": "",
        "telegram_alerts_enabled": False,
    }
    defaults.update(overrides)
    return Settings(**defaults)


def _make_extracted_item(
    title="Test Story",
    source="hackernews",
    url="https://example.com",
    score=100,
):
    """Create an ExtractedItem for testing."""
    return ExtractedItem(title=title, source=source, url=url, score=score)


def _make_classified_item(
    title="Test Story",
    source="hackernews",
    url="https://example.com",
    score=100,
    topic="models",
    relevance_score=0.9,
    credibility_score=0.8,
    summary="Test summary",
    priority=2,
    trending=False,
    dev_value_score=0.7,
):
    """Create a ClassifiedItem for testing."""
    item = _make_extracted_item(title=title, source=source, url=url, score=score)
    return ClassifiedItem(
        item=item,
        topic=topic,
        relevance_score=relevance_score,
        credibility_score=credibility_score,
        summary=summary,
        priority=priority,
        trending=trending,
        dev_value_score=dev_value_score,
    )


def _mock_session():
    """Create a mock AsyncSession."""
    session = AsyncMock()
    # Make execute return a result with rowcount=1 (successful insert)
    mock_result = MagicMock()
    mock_result.rowcount = 1
    session.execute.return_value = mock_result
    # For _save_briefing: select query returns no existing briefing
    mock_select_result = MagicMock()
    mock_select_result.scalar_one_or_none.return_value = None
    # Default: first call is _store_classified_items (insert), second is _save_briefing (select)
    # We need to handle both cases, so let execute return the right thing based on context
    session.execute = AsyncMock(return_value=mock_result)
    session.commit = AsyncMock()
    session.add = MagicMock()
    return session


# ---------------------------------------------------------------------------
# _get_extractors tests
# ---------------------------------------------------------------------------
class TestGetExtractors:
    """Verify _get_extractors returns the right extractors for enabled sources."""

    def test_returns_hackernews_when_enabled(self):
        """When hackernews is in ENABLED_SOURCES, HackerNewsExtractor is returned."""
        settings = _mock_settings(enabled_sources="hackernews")
        with patch("src.pipeline.pipeline.get_settings", return_value=settings):
            extractors = _get_extractors()

        assert len(extractors) == 1
        assert isinstance(extractors[0], HackerNewsExtractor)
        assert extractors[0].source_name == "hackernews"

    def test_returns_empty_list_when_no_sources_enabled(self):
        """When ENABLED_SOURCES is empty, no extractors should be returned."""
        settings = _mock_settings(enabled_sources="")
        with patch("src.pipeline.pipeline.get_settings", return_value=settings):
            extractors = _get_extractors()

        assert extractors == []

    def test_returns_all_four_extractors_when_all_enabled(self):
        """When all four sources are enabled, all four extractors should be returned."""
        settings = _mock_settings(enabled_sources="hackernews,arxiv,reddit,rss")
        with patch("src.pipeline.pipeline.get_settings", return_value=settings):
            extractors = _get_extractors()

        assert len(extractors) == 4
        source_names = [e.source_name for e in extractors]
        assert "hackernews" in source_names
        assert "arxiv" in source_names
        assert "reddit" in source_names
        assert "rss" in source_names

    def test_returns_correct_extractor_types(self):
        """Each enabled source should produce the correct extractor class."""
        settings = _mock_settings(enabled_sources="hackernews,arxiv,reddit,rss")
        with patch("src.pipeline.pipeline.get_settings", return_value=settings):
            extractors = _get_extractors()

        type_map = {e.source_name: type(e) for e in extractors}
        assert type_map["hackernews"] is HackerNewsExtractor
        assert type_map["arxiv"] is ArxivExtractor
        assert type_map["reddit"] is RedditExtractor
        assert type_map["rss"] is RSSExtractor

    def test_returns_arxiv_when_enabled_alone(self):
        """When only arxiv is enabled, only ArxivExtractor is returned."""
        settings = _mock_settings(enabled_sources="arxiv")
        with patch("src.pipeline.pipeline.get_settings", return_value=settings):
            extractors = _get_extractors()

        assert len(extractors) == 1
        assert isinstance(extractors[0], ArxivExtractor)

    def test_returns_reddit_when_enabled_alone(self):
        """When only reddit is enabled, only RedditExtractor is returned."""
        settings = _mock_settings(enabled_sources="reddit")
        with patch("src.pipeline.pipeline.get_settings", return_value=settings):
            extractors = _get_extractors()

        assert len(extractors) == 1
        assert isinstance(extractors[0], RedditExtractor)

    def test_returns_rss_when_enabled_alone(self):
        """When only rss is enabled, only RSSExtractor is returned."""
        settings = _mock_settings(enabled_sources="rss")
        with patch("src.pipeline.pipeline.get_settings", return_value=settings):
            extractors = _get_extractors()

        assert len(extractors) == 1
        assert isinstance(extractors[0], RSSExtractor)

    def test_returns_hackernews_among_multiple_sources(self):
        """When multiple sources are enabled, hackernews is still included."""
        settings = _mock_settings(enabled_sources="hackernews,arxiv,reddit")
        with patch("src.pipeline.pipeline.get_settings", return_value=settings):
            extractors = _get_extractors()

        source_names = [e.source_name for e in extractors]
        assert "hackernews" in source_names
        assert "arxiv" in source_names
        assert "reddit" in source_names

    def test_unknown_source_is_ignored(self):
        """Unknown source names should not produce extractors or crash."""
        settings = _mock_settings(enabled_sources="hackernews,unknown_source")
        with patch("src.pipeline.pipeline.get_settings", return_value=settings):
            extractors = _get_extractors()

        source_names = [e.source_name for e in extractors]
        assert source_names == ["hackernews"]

    def test_only_unknown_sources_returns_empty(self):
        """If only unrecognized sources are listed, result should be empty."""
        settings = _mock_settings(enabled_sources="twitter,mastodon")
        with patch("src.pipeline.pipeline.get_settings", return_value=settings):
            extractors = _get_extractors()

        assert extractors == []

    def test_preserves_order_hackernews_arxiv_reddit_rss(self):
        """Extractors should be returned in the order: hackernews, arxiv, reddit, rss."""
        settings = _mock_settings(enabled_sources="hackernews,arxiv,reddit,rss")
        with patch("src.pipeline.pipeline.get_settings", return_value=settings):
            extractors = _get_extractors()

        source_names = [e.source_name for e in extractors]
        assert source_names == ["hackernews", "arxiv", "reddit", "rss"]

    def test_partial_sources_subset(self):
        """Only the enabled subset of sources should have extractors."""
        settings = _mock_settings(enabled_sources="arxiv,rss")
        with patch("src.pipeline.pipeline.get_settings", return_value=settings):
            extractors = _get_extractors()

        assert len(extractors) == 2
        source_names = [e.source_name for e in extractors]
        assert "arxiv" in source_names
        assert "rss" in source_names
        assert "hackernews" not in source_names
        assert "reddit" not in source_names


# ---------------------------------------------------------------------------
# deduplicate_items integration with pipeline
# ---------------------------------------------------------------------------
class TestDeduplicateInPipeline:
    """Verify that deduplicate_items works correctly as used by the pipeline."""

    def test_dedup_called_with_extracted_items(self):
        """deduplicate_items should accept ExtractedItem list and return deduped list."""
        items = [
            ExtractedItem(title="Story A", source="hackernews", url="https://a.com", score=100),
            ExtractedItem(title="Story A", source="hackernews", url="https://a.com", score=200),
            ExtractedItem(title="Story B", source="hackernews", url="https://b.com", score=150),
        ]

        result = deduplicate_items(items)

        # Story A is duplicated by content_hash -> 1 copy kept
        # Story B is unique -> 1 copy kept
        assert len(result) == 2

    def test_dedup_preserves_all_unique_items(self):
        """All items with distinct content should be preserved."""
        items = [
            ExtractedItem(title=f"Story {i}", source="hackernews", url=f"https://s{i}.com", score=i)
            for i in range(5)
        ]

        result = deduplicate_items(items)

        assert len(result) == 5

    def test_dedup_empty_from_pipeline(self):
        """Pipeline scenario: no items extracted means dedup receives []."""
        result = deduplicate_items([])
        assert result == []


# ---------------------------------------------------------------------------
# _store_classified_items tests
# ---------------------------------------------------------------------------
class TestStoreClassifiedItems:
    """Verify _store_classified_items maps ClassifiedItem fields to DB columns."""

    @pytest.mark.asyncio
    async def test_stores_classified_item_fields(self):
        """ClassifiedItem classification fields should be included in the insert."""
        session = _mock_session()
        ci = _make_classified_item(
            title="GPT-5 Released",
            topic="models",
            relevance_score=0.95,
            credibility_score=0.85,
            summary="New GPT-5 model",
            priority=1,
            trending=True,
            dev_value_score=0.9,
        )

        count = await _store_classified_items(session, [ci])

        assert count == 1
        session.execute.assert_called_once()
        session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_stores_empty_list_returns_zero(self):
        """Empty input should return 0 without calling session."""
        session = _mock_session()

        count = await _store_classified_items(session, [])

        assert count == 0
        session.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_stores_multiple_items(self):
        """Multiple items should all be inserted."""
        session = _mock_session()
        items = [
            _make_classified_item(title=f"Story {i}", url=f"https://s{i}.com") for i in range(3)
        ]

        count = await _store_classified_items(session, items)

        assert count == 3
        assert session.execute.call_count == 3

    @pytest.mark.asyncio
    async def test_counts_only_new_inserts(self):
        """When on_conflict_do_nothing triggers, rowcount=0 items should not be counted."""
        session = _mock_session()
        # First insert succeeds (rowcount=1), second is a conflict (rowcount=0)
        result_new = MagicMock()
        result_new.rowcount = 1
        result_conflict = MagicMock()
        result_conflict.rowcount = 0
        session.execute = AsyncMock(side_effect=[result_new, result_conflict])

        items = [
            _make_classified_item(title="New Story", url="https://new.com"),
            _make_classified_item(title="Duplicate Story", url="https://dup.com"),
        ]

        count = await _store_classified_items(session, items)

        assert count == 1


# ---------------------------------------------------------------------------
# _save_briefing tests
# ---------------------------------------------------------------------------
class TestSaveBriefing:
    """Verify _save_briefing stores trending_count."""

    @pytest.mark.asyncio
    async def test_saves_trending_count_new_briefing(self):
        """New briefing should include trending_count."""
        session = _mock_session()
        # select returns None (no existing briefing)
        mock_select_result = MagicMock()
        mock_select_result.scalar_one_or_none.return_value = None
        session.execute = AsyncMock(return_value=mock_select_result)

        await _save_briefing(
            session,
            items_extracted=10,
            items_after_dedup=8,
            items_stored=5,
            sources_used=["hackernews"],
            duration_seconds=30.0,
            trending_count=3,
        )

        # Verify session.add was called with a DailyBriefing that has trending_count
        session.add.assert_called_once()
        briefing = session.add.call_args[0][0]
        assert briefing.trending_count == 3

    @pytest.mark.asyncio
    async def test_saves_trending_count_existing_briefing(self):
        """Existing briefing replaces per-run stats; only total_items accumulates."""
        session = _mock_session()
        # Simulate existing briefing with proper integer fields
        from src.core.models import DailyBriefing

        existing_briefing = MagicMock(spec=DailyBriefing)
        existing_briefing.total_items = 5
        existing_briefing.items_extracted = 10
        existing_briefing.items_after_dedup = 8
        existing_briefing.items_filtered = 5
        existing_briefing.trending_count = 1
        existing_briefing.duration_seconds = 15.0
        existing_briefing.sources_used = {"sources": ["hackernews"]}
        mock_select_result = MagicMock()
        mock_select_result.scalar_one_or_none.return_value = existing_briefing
        session.execute = AsyncMock(return_value=mock_select_result)

        await _save_briefing(
            session,
            items_extracted=10,
            items_after_dedup=8,
            items_stored=5,
            sources_used=["hackernews"],
            duration_seconds=30.0,
            trending_count=2,
        )

        # Only total_items accumulates; per-run stats are replaced
        assert existing_briefing.total_items == 10  # 5 + 5
        assert existing_briefing.items_filtered == 5  # replaced, not accumulated
        assert existing_briefing.trending_count == 2  # replaced, not accumulated
        assert existing_briefing.duration_seconds == 30.0  # replaced, not accumulated

    @pytest.mark.asyncio
    async def test_save_briefing_replaces_extraction_stats_on_existing(self):
        """When a briefing already exists, extraction stats are replaced, not accumulated."""
        from src.core.models import DailyBriefing

        # Simulate existing briefing with prior stats
        existing_briefing = MagicMock(spec=DailyBriefing)
        existing_briefing.total_items = 50
        existing_briefing.items_extracted = 100  # old extraction count
        existing_briefing.items_after_dedup = 80
        existing_briefing.items_filtered = 50
        existing_briefing.trending_count = 5
        existing_briefing.duration_seconds = 30.0
        existing_briefing.sources_used = {"sources": ["hackernews"]}

        mock_select_result = MagicMock()
        mock_select_result.scalar_one_or_none.return_value = existing_briefing

        session = AsyncMock()
        session.execute = AsyncMock(return_value=mock_select_result)
        session.commit = AsyncMock()

        await _save_briefing(
            session,
            items_extracted=20,
            items_after_dedup=15,
            items_stored=5,
            sources_used=["hackernews"],
            duration_seconds=10.0,
            trending_count=2,
        )

        # total_items (= items_stored) should ACCUMULATE: 50 + 5 = 55
        assert existing_briefing.total_items == 55
        # Extraction stats should be REPLACED, not accumulated
        assert existing_briefing.items_extracted == 20
        assert existing_briefing.items_after_dedup == 15
        assert existing_briefing.items_filtered == 5
        assert existing_briefing.trending_count == 2
        assert existing_briefing.duration_seconds == 10.0

    @pytest.mark.asyncio
    async def test_trending_count_defaults_to_zero(self):
        """When trending_count is not passed, it defaults to 0."""
        session = _mock_session()
        mock_select_result = MagicMock()
        mock_select_result.scalar_one_or_none.return_value = None
        session.execute = AsyncMock(return_value=mock_select_result)

        await _save_briefing(
            session,
            items_extracted=10,
            items_after_dedup=8,
            items_stored=5,
            sources_used=["hackernews"],
            duration_seconds=30.0,
        )

        briefing = session.add.call_args[0][0]
        assert briefing.trending_count == 0

    @pytest.mark.asyncio
    async def test_save_briefing_merges_sources_used(self):
        """When a briefing already exists, sources_used should merge, not replace."""
        from src.core.models import DailyBriefing

        existing_briefing = MagicMock(spec=DailyBriefing)
        existing_briefing.total_items = 10
        existing_briefing.items_extracted = 20
        existing_briefing.items_after_dedup = 15
        existing_briefing.items_filtered = 10
        existing_briefing.trending_count = 2
        existing_briefing.duration_seconds = 15.0
        existing_briefing.sources_used = {"sources": ["arxiv", "hackernews"]}

        mock_select_result = MagicMock()
        mock_select_result.scalar_one_or_none.return_value = existing_briefing

        session = AsyncMock()
        session.execute = AsyncMock(return_value=mock_select_result)
        session.commit = AsyncMock()

        await _save_briefing(
            session,
            items_extracted=10,
            items_after_dedup=8,
            items_stored=5,
            sources_used=["hackernews", "reddit"],
            duration_seconds=20.0,
            trending_count=1,
        )

        # sources_used should be merged: arxiv + hackernews + reddit (sorted)
        assert existing_briefing.sources_used == {"sources": ["arxiv", "hackernews", "reddit"]}


# ---------------------------------------------------------------------------
# run_pipeline tests
# ---------------------------------------------------------------------------
class TestRunPipeline:
    """Verify the full pipeline flow with classification, validation, and notification."""

    @pytest.fixture
    def _extracted_items(self):
        """Sample extracted items for pipeline tests."""
        return [
            ExtractedItem(
                title="New LLM model released",
                source="hackernews",
                url="https://example.com/llm",
                score=200,
                text="A new LLM model has been released with improved benchmarks.",
            ),
            ExtractedItem(
                title="AI agent framework update",
                source="arxiv",
                url="https://arxiv.org/paper1",
                score=50,
                text="Research paper on agentic AI systems.",
            ),
        ]

    @pytest.fixture
    def _classified_items(self, _extracted_items):
        """Sample classified items for pipeline tests."""
        return [
            ClassifiedItem(
                item=_extracted_items[0],
                topic="models",
                relevance_score=0.9,
                summary="New LLM model",
                priority=2,
                trending=True,
            ),
            ClassifiedItem(
                item=_extracted_items[1],
                topic="agents",
                relevance_score=0.85,
                summary="Agent framework",
                priority=3,
            ),
        ]

    @pytest.mark.asyncio
    async def test_pipeline_uses_keyword_classifier_when_no_openai_key(
        self,
        _extracted_items,
        _classified_items,
    ):
        """Pipeline should use KeywordClassifier when openai_api_key is empty."""
        settings = _mock_settings(
            enabled_sources="hackernews",
            openai_api_key="",
            enable_news_validation=False,
        )
        session = _mock_session()

        with (
            patch("src.pipeline.pipeline.get_settings", return_value=settings),
            patch(
                "src.pipeline.pipeline._extract_all",
                new_callable=AsyncMock,
                return_value=_extracted_items,
            ),
            patch("src.pipeline.pipeline.deduplicate_items", return_value=_extracted_items),
            patch("src.pipeline.pipeline.KeywordClassifier") as mock_kw_cls,
            patch("src.pipeline.pipeline.CredibilityValidator") as mock_validator_cls,
            patch("src.pipeline.pipeline.AlertService") as mock_alerts_cls,
        ):
            mock_classifier = AsyncMock()
            mock_classifier.classify.return_value = _classified_items
            mock_kw_cls.return_value = mock_classifier

            mock_validator = AsyncMock()
            mock_validator.validate.return_value = _classified_items
            mock_validator_cls.return_value = mock_validator

            mock_alerts = AsyncMock()
            mock_alerts_cls.return_value = mock_alerts

            result = await run_pipeline(session)

        assert result is True
        mock_kw_cls.assert_called_once()
        mock_classifier.classify.assert_called_once_with(_extracted_items)

    @pytest.mark.asyncio
    async def test_pipeline_uses_llm_classifier_when_openai_key_set(
        self,
        _extracted_items,
        _classified_items,
    ):
        """Pipeline should use LLMClassifier when openai_api_key is set."""
        settings = _mock_settings(
            enabled_sources="hackernews",
            openai_api_key="sk-test-key",
            enable_news_validation=False,
        )
        session = _mock_session()

        with (
            patch("src.pipeline.pipeline.get_settings", return_value=settings),
            patch(
                "src.pipeline.pipeline._extract_all",
                new_callable=AsyncMock,
                return_value=_extracted_items,
            ),
            patch("src.pipeline.pipeline.deduplicate_items", return_value=_extracted_items),
            patch("src.pipeline.pipeline.LLMClassifier") as mock_llm_cls,
            patch(
                "src.pipeline.pipeline.deduplicate_events",
                new_callable=AsyncMock,
                return_value=_classified_items,
            ),
            patch("src.pipeline.pipeline.CredibilityValidator") as mock_validator_cls,
            patch("src.pipeline.pipeline.AlertService") as mock_alerts_cls,
        ):
            mock_classifier = AsyncMock()
            mock_classifier.classify.return_value = _classified_items
            mock_llm_cls.return_value = mock_classifier

            mock_validator = AsyncMock()
            mock_validator.validate.return_value = _classified_items
            mock_validator_cls.return_value = mock_validator

            mock_alerts = AsyncMock()
            mock_alerts_cls.return_value = mock_alerts

            result = await run_pipeline(session)

        assert result is True
        mock_llm_cls.assert_called_once()
        mock_classifier.classify.assert_called_once_with(_extracted_items)

    @pytest.mark.asyncio
    async def test_pipeline_calls_event_dedup_when_llm_available(
        self,
        _extracted_items,
        _classified_items,
    ):
        """Event dedup should be called when openai_api_key is set and >1 classified items."""
        settings = _mock_settings(
            enabled_sources="hackernews",
            openai_api_key="sk-test-key",
            enable_news_validation=False,
        )
        session = _mock_session()

        with (
            patch("src.pipeline.pipeline.get_settings", return_value=settings),
            patch(
                "src.pipeline.pipeline._extract_all",
                new_callable=AsyncMock,
                return_value=_extracted_items,
            ),
            patch("src.pipeline.pipeline.deduplicate_items", return_value=_extracted_items),
            patch("src.pipeline.pipeline.LLMClassifier") as mock_llm_cls,
            patch(
                "src.pipeline.pipeline.deduplicate_events",
                new_callable=AsyncMock,
                return_value=_classified_items,
            ) as mock_event_dedup,
            patch("src.pipeline.pipeline.CredibilityValidator") as mock_validator_cls,
            patch("src.pipeline.pipeline.AlertService") as mock_alerts_cls,
        ):
            mock_classifier = AsyncMock()
            mock_classifier.classify.return_value = _classified_items
            mock_llm_cls.return_value = mock_classifier

            mock_validator = AsyncMock()
            mock_validator.validate.return_value = _classified_items
            mock_validator_cls.return_value = mock_validator

            mock_alerts = AsyncMock()
            mock_alerts_cls.return_value = mock_alerts

            result = await run_pipeline(session)

        assert result is True
        mock_event_dedup.assert_called_once_with(_classified_items)

    @pytest.mark.asyncio
    async def test_pipeline_skips_event_dedup_when_no_llm(
        self,
        _extracted_items,
        _classified_items,
    ):
        """Event dedup should NOT be called when openai_api_key is empty."""
        settings = _mock_settings(
            enabled_sources="hackernews",
            openai_api_key="",
            enable_news_validation=False,
        )
        session = _mock_session()

        with (
            patch("src.pipeline.pipeline.get_settings", return_value=settings),
            patch(
                "src.pipeline.pipeline._extract_all",
                new_callable=AsyncMock,
                return_value=_extracted_items,
            ),
            patch("src.pipeline.pipeline.deduplicate_items", return_value=_extracted_items),
            patch("src.pipeline.pipeline.KeywordClassifier") as mock_kw_cls,
            patch(
                "src.pipeline.pipeline.deduplicate_events",
                new_callable=AsyncMock,
            ) as mock_event_dedup,
            patch("src.pipeline.pipeline.CredibilityValidator") as mock_validator_cls,
            patch("src.pipeline.pipeline.AlertService") as mock_alerts_cls,
        ):
            mock_classifier = AsyncMock()
            mock_classifier.classify.return_value = _classified_items
            mock_kw_cls.return_value = mock_classifier

            mock_validator = AsyncMock()
            mock_validator.validate.return_value = _classified_items
            mock_validator_cls.return_value = mock_validator

            mock_alerts = AsyncMock()
            mock_alerts_cls.return_value = mock_alerts

            result = await run_pipeline(session)

        assert result is True
        mock_event_dedup.assert_not_called()

    @pytest.mark.asyncio
    async def test_pipeline_calls_validate(
        self,
        _extracted_items,
        _classified_items,
    ):
        """Pipeline should call CredibilityValidator.validate."""
        settings = _mock_settings(
            enabled_sources="hackernews",
            openai_api_key="",
            enable_news_validation=True,
        )
        session = _mock_session()

        with (
            patch("src.pipeline.pipeline.get_settings", return_value=settings),
            patch(
                "src.pipeline.pipeline._extract_all",
                new_callable=AsyncMock,
                return_value=_extracted_items,
            ),
            patch("src.pipeline.pipeline.deduplicate_items", return_value=_extracted_items),
            patch("src.pipeline.pipeline.KeywordClassifier") as mock_kw_cls,
            patch("src.pipeline.pipeline.CredibilityValidator") as mock_validator_cls,
            patch("src.pipeline.pipeline.AlertService") as mock_alerts_cls,
        ):
            mock_classifier = AsyncMock()
            mock_classifier.classify.return_value = _classified_items
            mock_kw_cls.return_value = mock_classifier

            mock_validator = AsyncMock()
            mock_validator.validate.return_value = _classified_items
            mock_validator_cls.return_value = mock_validator

            mock_alerts = AsyncMock()
            mock_alerts_cls.return_value = mock_alerts

            result = await run_pipeline(session)

        assert result is True
        mock_validator.validate.assert_called_once_with(_classified_items)

    @pytest.mark.asyncio
    async def test_pipeline_notifies_when_telegram_configured(
        self,
        _extracted_items,
        _classified_items,
    ):
        """Pipeline should call TelegramNotifier.send_briefing when telegram is configured."""
        settings = _mock_settings(
            enabled_sources="hackernews",
            openai_api_key="",
            enable_news_validation=False,
            telegram_bot_token="bot-token-123",
            telegram_chat_id="chat-456",
            telegram_alerts_enabled=True,
        )
        session = _mock_session()

        with (
            patch("src.pipeline.pipeline.get_settings", return_value=settings),
            patch(
                "src.pipeline.pipeline._extract_all",
                new_callable=AsyncMock,
                return_value=_extracted_items,
            ),
            patch("src.pipeline.pipeline.deduplicate_items", return_value=_extracted_items),
            patch("src.pipeline.pipeline.KeywordClassifier") as mock_kw_cls,
            patch("src.pipeline.pipeline.CredibilityValidator") as mock_validator_cls,
            patch("src.pipeline.pipeline.TelegramNotifier") as mock_notifier_cls,
            patch("src.pipeline.pipeline.AlertService") as mock_alerts_cls,
        ):
            mock_classifier = AsyncMock()
            mock_classifier.classify.return_value = _classified_items
            mock_kw_cls.return_value = mock_classifier

            mock_validator = AsyncMock()
            mock_validator.validate.return_value = _classified_items
            mock_validator_cls.return_value = mock_validator

            mock_notifier = AsyncMock()
            mock_notifier.send_briefing.return_value = True
            mock_notifier_cls.return_value = mock_notifier

            mock_alerts = AsyncMock()
            mock_alerts_cls.return_value = mock_alerts

            result = await run_pipeline(session)

        assert result is True
        mock_notifier_cls.assert_called_once()
        mock_notifier.send_briefing.assert_called_once()
        # Check that validated items and duration were passed
        call_args = mock_notifier.send_briefing.call_args
        assert call_args[0][0] == _classified_items  # first positional arg: items
        assert "duration_seconds" in call_args[1]  # keyword arg

    @pytest.mark.asyncio
    async def test_pipeline_skips_notify_when_no_telegram(
        self,
        _extracted_items,
        _classified_items,
    ):
        """Pipeline should NOT call TelegramNotifier when telegram is not configured."""
        settings = _mock_settings(
            enabled_sources="hackernews",
            openai_api_key="",
            enable_news_validation=False,
            telegram_bot_token="",
            telegram_chat_id="",
        )
        session = _mock_session()

        with (
            patch("src.pipeline.pipeline.get_settings", return_value=settings),
            patch(
                "src.pipeline.pipeline._extract_all",
                new_callable=AsyncMock,
                return_value=_extracted_items,
            ),
            patch("src.pipeline.pipeline.deduplicate_items", return_value=_extracted_items),
            patch("src.pipeline.pipeline.KeywordClassifier") as mock_kw_cls,
            patch("src.pipeline.pipeline.CredibilityValidator") as mock_validator_cls,
            patch("src.pipeline.pipeline.TelegramNotifier") as mock_notifier_cls,
            patch("src.pipeline.pipeline.AlertService") as mock_alerts_cls,
        ):
            mock_classifier = AsyncMock()
            mock_classifier.classify.return_value = _classified_items
            mock_kw_cls.return_value = mock_classifier

            mock_validator = AsyncMock()
            mock_validator.validate.return_value = _classified_items
            mock_validator_cls.return_value = mock_validator

            mock_alerts = AsyncMock()
            mock_alerts_cls.return_value = mock_alerts

            result = await run_pipeline(session)

        assert result is True
        mock_notifier_cls.assert_not_called()

    @pytest.mark.asyncio
    async def test_pipeline_handles_notification_failure_gracefully(
        self,
        _extracted_items,
        _classified_items,
    ):
        """Pipeline should succeed even when notification fails."""
        settings = _mock_settings(
            enabled_sources="hackernews",
            openai_api_key="",
            enable_news_validation=False,
            telegram_bot_token="bot-token-123",
            telegram_chat_id="chat-456",
            telegram_alerts_enabled=True,
        )
        session = _mock_session()

        with (
            patch("src.pipeline.pipeline.get_settings", return_value=settings),
            patch(
                "src.pipeline.pipeline._extract_all",
                new_callable=AsyncMock,
                return_value=_extracted_items,
            ),
            patch("src.pipeline.pipeline.deduplicate_items", return_value=_extracted_items),
            patch("src.pipeline.pipeline.KeywordClassifier") as mock_kw_cls,
            patch("src.pipeline.pipeline.CredibilityValidator") as mock_validator_cls,
            patch("src.pipeline.pipeline.TelegramNotifier") as mock_notifier_cls,
            patch("src.pipeline.pipeline.AlertService") as mock_alerts_cls,
        ):
            mock_classifier = AsyncMock()
            mock_classifier.classify.return_value = _classified_items
            mock_kw_cls.return_value = mock_classifier

            mock_validator = AsyncMock()
            mock_validator.validate.return_value = _classified_items
            mock_validator_cls.return_value = mock_validator

            # Notifier raises an exception
            mock_notifier = AsyncMock()
            mock_notifier.send_briefing.side_effect = RuntimeError("Telegram API down")
            mock_notifier_cls.return_value = mock_notifier

            mock_alerts = AsyncMock()
            mock_alerts_cls.return_value = mock_alerts

            # Should NOT raise, should return True
            result = await run_pipeline(session)

        assert result is True

    @pytest.mark.asyncio
    async def test_pipeline_returns_false_on_no_items(self):
        """Pipeline should return False when no items are extracted."""
        settings = _mock_settings(
            enabled_sources="hackernews",
            openai_api_key="",
        )
        session = _mock_session()

        with (
            patch("src.pipeline.pipeline.get_settings", return_value=settings),
            patch("src.pipeline.pipeline._extract_all", new_callable=AsyncMock, return_value=[]),
            patch("src.pipeline.pipeline.AlertService") as mock_alerts_cls,
        ):
            mock_alerts = AsyncMock()
            mock_alerts_cls.return_value = mock_alerts

            result = await run_pipeline(session)

        assert result is False

    @pytest.mark.asyncio
    async def test_pipeline_computes_trending_count(self, _extracted_items):
        """Pipeline should compute trending_count from validated items."""
        settings = _mock_settings(
            enabled_sources="hackernews",
            openai_api_key="",
            enable_news_validation=False,
        )
        session = _mock_session()

        # Create items where 2 out of 3 are trending
        classified_items = [
            ClassifiedItem(
                item=_extracted_items[0],
                topic="models",
                relevance_score=0.9,
                priority=1,
                trending=True,
            ),
            ClassifiedItem(
                item=_extracted_items[1],
                topic="agents",
                relevance_score=0.85,
                priority=3,
                trending=False,
            ),
        ]

        with (
            patch("src.pipeline.pipeline.get_settings", return_value=settings),
            patch(
                "src.pipeline.pipeline._extract_all",
                new_callable=AsyncMock,
                return_value=_extracted_items,
            ),
            patch("src.pipeline.pipeline.deduplicate_items", return_value=_extracted_items),
            patch("src.pipeline.pipeline.KeywordClassifier") as mock_kw_cls,
            patch("src.pipeline.pipeline.CredibilityValidator") as mock_validator_cls,
            patch("src.pipeline.pipeline._save_briefing", new_callable=AsyncMock) as mock_save,
            patch("src.pipeline.pipeline.AlertService") as mock_alerts_cls,
        ):
            mock_classifier = AsyncMock()
            mock_classifier.classify.return_value = classified_items
            mock_kw_cls.return_value = mock_classifier

            mock_validator = AsyncMock()
            mock_validator.validate.return_value = classified_items
            mock_validator_cls.return_value = mock_validator

            mock_alerts = AsyncMock()
            mock_alerts_cls.return_value = mock_alerts

            result = await run_pipeline(session)

        assert result is True
        # Check trending_count was passed to _save_briefing
        call_kwargs = mock_save.call_args[1]
        assert call_kwargs["trending_count"] == 1  # only first item is trending


# ---------------------------------------------------------------------------
# _extract_all tests (coverage for lines 72-101)
# ---------------------------------------------------------------------------
class TestExtractAll:
    """Test _extract_all concurrent extraction with error handling."""

    @pytest.mark.asyncio
    async def test_single_extractor_returns_items(self):
        """A single extractor returning items works correctly."""
        items = [_make_extracted_item(title="Story 1")]
        extractor = AsyncMock()
        extractor.source_name = "hackernews"
        extractor.extract.return_value = items

        settings = _mock_settings()
        alerts = AsyncMock()

        with patch("src.pipeline.pipeline.get_settings", return_value=settings):
            result = await _extract_all([extractor], alerts=alerts)

        assert len(result) == 1
        assert result[0].title == "Story 1"

    @pytest.mark.asyncio
    async def test_multiple_extractors_combined(self):
        """Items from multiple extractors are combined."""
        items_hn = [_make_extracted_item(title="HN Story", source="hackernews")]
        items_arxiv = [_make_extracted_item(title="ArXiv Paper", source="arxiv")]

        ext_hn = AsyncMock()
        ext_hn.source_name = "hackernews"
        ext_hn.extract.return_value = items_hn

        ext_arxiv = AsyncMock()
        ext_arxiv.source_name = "arxiv"
        ext_arxiv.extract.return_value = items_arxiv

        settings = _mock_settings()
        alerts = AsyncMock()

        with patch("src.pipeline.pipeline.get_settings", return_value=settings):
            result = await _extract_all([ext_hn, ext_arxiv], alerts=alerts)

        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_extractor_failure_returns_empty_for_that_source(self):
        """When one extractor raises, others should still return items."""
        good_items = [_make_extracted_item(title="Good Story")]

        ext_good = AsyncMock()
        ext_good.source_name = "hackernews"
        ext_good.extract.return_value = good_items

        ext_bad = AsyncMock()
        ext_bad.source_name = "arxiv"
        ext_bad.extract.side_effect = RuntimeError("Connection refused")

        settings = _mock_settings()
        alerts = AsyncMock()

        with patch("src.pipeline.pipeline.get_settings", return_value=settings):
            result = await _extract_all([ext_good, ext_bad], alerts=alerts)

        assert len(result) == 1
        assert result[0].title == "Good Story"
        # Alert should have been called for the failed extractor
        alerts.extractor_empty.assert_called_once_with("arxiv")

    @pytest.mark.asyncio
    async def test_all_extractors_fail_returns_empty(self):
        """When all extractors fail, result should be empty list."""
        ext1 = AsyncMock()
        ext1.source_name = "hackernews"
        ext1.extract.side_effect = RuntimeError("fail")

        ext2 = AsyncMock()
        ext2.source_name = "arxiv"
        ext2.extract.side_effect = RuntimeError("fail")

        settings = _mock_settings()
        alerts = AsyncMock()

        with patch("src.pipeline.pipeline.get_settings", return_value=settings):
            result = await _extract_all([ext1, ext2], alerts=alerts)

        assert result == []
        assert alerts.extractor_empty.call_count == 2

    @pytest.mark.asyncio
    async def test_empty_extractor_triggers_alert(self):
        """When an extractor returns [], alerts.extractor_empty should be called."""
        ext = AsyncMock()
        ext.source_name = "reddit"
        ext.extract.return_value = []

        settings = _mock_settings()
        alerts = AsyncMock()

        with patch("src.pipeline.pipeline.get_settings", return_value=settings):
            result = await _extract_all([ext], alerts=alerts)

        assert result == []
        alerts.extractor_empty.assert_called_once_with("reddit")

    @pytest.mark.asyncio
    async def test_extract_all_creates_default_alerts_if_none(self):
        """When alerts is None, _extract_all creates its own AlertService."""
        ext = AsyncMock()
        ext.source_name = "hackernews"
        ext.extract.return_value = [_make_extracted_item()]

        settings = _mock_settings()

        with (
            patch("src.pipeline.pipeline.get_settings", return_value=settings),
            patch("src.pipeline.pipeline.AlertService") as mock_alerts_cls,
        ):
            mock_alerts_cls.return_value = AsyncMock()
            result = await _extract_all([ext])

        assert len(result) == 1
        mock_alerts_cls.assert_called_once()


# ---------------------------------------------------------------------------
# run_pipeline exception path (coverage for lines 326-331)
# ---------------------------------------------------------------------------
class TestRunPipelineExceptionPath:
    """Test the exception handler in run_pipeline."""

    @pytest.mark.asyncio
    async def test_pipeline_reraises_exception_after_logging(self):
        """When a mid-pipeline exception occurs, it should be logged and re-raised."""
        settings = _mock_settings(
            enabled_sources="hackernews",
            openai_api_key="",
        )
        session = _mock_session()
        items = [_make_extracted_item()]

        with (
            patch("src.pipeline.pipeline.get_settings", return_value=settings),
            patch(
                "src.pipeline.pipeline._extract_all",
                new_callable=AsyncMock,
                return_value=items,
            ),
            patch("src.pipeline.pipeline.deduplicate_items", return_value=items),
            patch("src.pipeline.pipeline.KeywordClassifier") as mock_kw_cls,
            patch("src.pipeline.pipeline.AlertService") as mock_alerts_cls,
        ):
            mock_classifier = AsyncMock()
            mock_classifier.classify.side_effect = RuntimeError("LLM exploded")
            mock_kw_cls.return_value = mock_classifier

            mock_alerts = AsyncMock()
            mock_alerts_cls.return_value = mock_alerts

            with pytest.raises(RuntimeError, match="LLM exploded"):
                await run_pipeline(session)

            # Verify alert was sent about the failure
            mock_alerts.pipeline_failure.assert_called_once()

    @pytest.mark.asyncio
    async def test_pipeline_exception_path_increments_error_metric(self):
        """Pipeline exception should increment error metric and call alerts."""
        settings = _mock_settings(
            enabled_sources="hackernews",
            openai_api_key="",
            enable_news_validation=False,
        )
        session = _mock_session()
        items = [_make_extracted_item()]

        with (
            patch("src.pipeline.pipeline.get_settings", return_value=settings),
            patch(
                "src.pipeline.pipeline._extract_all",
                new_callable=AsyncMock,
                return_value=items,
            ),
            patch("src.pipeline.pipeline.deduplicate_items", return_value=items),
            patch("src.pipeline.pipeline.KeywordClassifier") as mock_kw_cls,
            patch("src.pipeline.pipeline.CredibilityValidator") as mock_validator_cls,
            patch("src.pipeline.pipeline.AlertService") as mock_alerts_cls,
        ):
            mock_classifier = AsyncMock()
            mock_classifier.classify.return_value = [_make_classified_item()]
            mock_kw_cls.return_value = mock_classifier

            mock_validator = AsyncMock()
            mock_validator.validate.side_effect = ValueError("Validation crashed")
            mock_validator_cls.return_value = mock_validator

            mock_alerts = AsyncMock()
            mock_alerts_cls.return_value = mock_alerts

            with pytest.raises(ValueError, match="Validation crashed"):
                await run_pipeline(session)

            mock_alerts.pipeline_failure.assert_called_once()


# ---------------------------------------------------------------------------
# Edge-case tests (M9 Task 6)
# ---------------------------------------------------------------------------
class TestPipelineEdgeCases:
    """Edge-case scenarios for pipeline orchestration."""

    @pytest.mark.asyncio
    async def test_classifier_returns_empty(self):
        """When classifier returns [], pipeline continues with 0 items and returns True."""
        settings = _mock_settings(
            enabled_sources="hackernews",
            openai_api_key="",
            enable_news_validation=False,
            embedding_api_key="",
        )
        session = _mock_session()
        items = [_make_extracted_item()]

        with (
            patch("src.pipeline.pipeline.get_settings", return_value=settings),
            patch(
                "src.pipeline.pipeline._extract_all",
                new_callable=AsyncMock,
                return_value=items,
            ),
            patch("src.pipeline.pipeline.deduplicate_items", return_value=items),
            patch("src.pipeline.pipeline.KeywordClassifier") as mock_kw_cls,
            patch("src.pipeline.pipeline.CredibilityValidator") as mock_validator_cls,
            patch(
                "src.pipeline.pipeline._store_classified_items", new_callable=AsyncMock
            ) as mock_store,
            patch("src.pipeline.pipeline._save_briefing", new_callable=AsyncMock) as mock_briefing,
            patch("src.pipeline.pipeline.AlertService") as mock_alerts_cls,
        ):
            mock_classifier = AsyncMock()
            mock_classifier.classify.return_value = []  # <-- empty classification
            mock_kw_cls.return_value = mock_classifier

            mock_validator = AsyncMock()
            mock_validator.validate.return_value = []
            mock_validator_cls.return_value = mock_validator

            mock_store.return_value = 0

            mock_alerts = AsyncMock()
            mock_alerts_cls.return_value = mock_alerts

            result = await run_pipeline(session)

        assert result is True
        mock_store.assert_called_once_with(session, [])
        # Briefing should still be saved with items_stored=0
        mock_briefing.assert_called_once()
        assert mock_briefing.call_args[1]["items_stored"] == 0
        assert mock_briefing.call_args[1]["trending_count"] == 0

    @pytest.mark.asyncio
    async def test_validator_filters_all(self):
        """When validator returns [], pipeline still succeeds with 0 stored items."""
        settings = _mock_settings(
            enabled_sources="hackernews",
            openai_api_key="",
            enable_news_validation=True,
            embedding_api_key="",
        )
        session = _mock_session()
        items = [_make_extracted_item()]
        classified = [_make_classified_item()]

        with (
            patch("src.pipeline.pipeline.get_settings", return_value=settings),
            patch(
                "src.pipeline.pipeline._extract_all",
                new_callable=AsyncMock,
                return_value=items,
            ),
            patch("src.pipeline.pipeline.deduplicate_items", return_value=items),
            patch("src.pipeline.pipeline.KeywordClassifier") as mock_kw_cls,
            patch("src.pipeline.pipeline.CredibilityValidator") as mock_validator_cls,
            patch(
                "src.pipeline.pipeline._store_classified_items", new_callable=AsyncMock
            ) as mock_store,
            patch("src.pipeline.pipeline._save_briefing", new_callable=AsyncMock) as mock_briefing,
            patch("src.pipeline.pipeline.AlertService") as mock_alerts_cls,
        ):
            mock_classifier = AsyncMock()
            mock_classifier.classify.return_value = classified
            mock_kw_cls.return_value = mock_classifier

            mock_validator = AsyncMock()
            mock_validator.validate.return_value = []  # <-- validator filters everything
            mock_validator_cls.return_value = mock_validator

            mock_store.return_value = 0

            mock_alerts = AsyncMock()
            mock_alerts_cls.return_value = mock_alerts

            result = await run_pipeline(session)

        assert result is True
        mock_validator.validate.assert_called_once_with(classified)
        mock_store.assert_called_once_with(session, [])
        assert mock_briefing.call_args[1]["trending_count"] == 0

    @pytest.mark.asyncio
    async def test_store_integrity_error_propagates(self):
        """IntegrityError during DB insert propagates and triggers pipeline_failure alert."""
        from sqlalchemy.exc import IntegrityError

        settings = _mock_settings(
            enabled_sources="hackernews",
            openai_api_key="",
            enable_news_validation=False,
        )
        session = _mock_session()
        items = [_make_extracted_item()]
        classified = [_make_classified_item()]

        # Make session.execute raise IntegrityError (e.g., a non-content_hash constraint)
        session.execute = AsyncMock(
            side_effect=IntegrityError("duplicate key", {}, Exception("unique constraint")),
        )

        with (
            patch("src.pipeline.pipeline.get_settings", return_value=settings),
            patch(
                "src.pipeline.pipeline._extract_all",
                new_callable=AsyncMock,
                return_value=items,
            ),
            patch("src.pipeline.pipeline.deduplicate_items", return_value=items),
            patch("src.pipeline.pipeline.KeywordClassifier") as mock_kw_cls,
            patch("src.pipeline.pipeline.CredibilityValidator") as mock_validator_cls,
            patch("src.pipeline.pipeline.AlertService") as mock_alerts_cls,
        ):
            mock_classifier = AsyncMock()
            mock_classifier.classify.return_value = classified
            mock_kw_cls.return_value = mock_classifier

            mock_validator = AsyncMock()
            mock_validator.validate.return_value = classified
            mock_validator_cls.return_value = mock_validator

            mock_alerts = AsyncMock()
            mock_alerts_cls.return_value = mock_alerts

            with pytest.raises(IntegrityError):
                await run_pipeline(session)

            # Alert should fire for the unhandled DB error
            mock_alerts.pipeline_failure.assert_called_once()

    @pytest.mark.asyncio
    async def test_embedding_skipped_when_api_key_not_set(self):
        """Embedding step is skipped entirely when embedding_api_key is empty."""
        settings = _mock_settings(
            enabled_sources="hackernews",
            openai_api_key="",
            enable_news_validation=False,
            embedding_api_key="",  # <-- no key
        )
        session = _mock_session()
        items = [_make_extracted_item()]
        classified = [_make_classified_item()]

        with (
            patch("src.pipeline.pipeline.get_settings", return_value=settings),
            patch(
                "src.pipeline.pipeline._extract_all",
                new_callable=AsyncMock,
                return_value=items,
            ),
            patch("src.pipeline.pipeline.deduplicate_items", return_value=items),
            patch("src.pipeline.pipeline.KeywordClassifier") as mock_kw_cls,
            patch("src.pipeline.pipeline.CredibilityValidator") as mock_validator_cls,
            patch(
                "src.pipeline.pipeline._embed_new_items",
                new_callable=AsyncMock,
            ) as mock_embed,
            patch("src.pipeline.pipeline.AlertService") as mock_alerts_cls,
        ):
            mock_classifier = AsyncMock()
            mock_classifier.classify.return_value = classified
            mock_kw_cls.return_value = mock_classifier

            mock_validator = AsyncMock()
            mock_validator.validate.return_value = classified
            mock_validator_cls.return_value = mock_validator

            mock_alerts = AsyncMock()
            mock_alerts_cls.return_value = mock_alerts

            result = await run_pipeline(session)

        assert result is True
        # _embed_new_items should NOT have been called
        mock_embed.assert_not_called()


# ---------------------------------------------------------------------------
# _get_extractors with sources filter (Task 3)
# ---------------------------------------------------------------------------
class TestGetExtractorsWithFilter:
    """_get_extractors with sources filter parameter."""

    def test_filter_to_single_source(self):
        settings = _mock_settings(enabled_sources="hackernews,arxiv,reddit,rss")
        with patch("src.pipeline.pipeline.get_settings", return_value=settings):
            extractors = _get_extractors(sources=["hackernews"])
        assert len(extractors) == 1
        assert extractors[0].source_name == "hackernews"

    def test_filter_to_multiple_sources(self):
        settings = _mock_settings(enabled_sources="hackernews,arxiv,reddit,rss")
        with patch("src.pipeline.pipeline.get_settings", return_value=settings):
            extractors = _get_extractors(sources=["hackernews", "reddit"])
        assert len(extractors) == 2
        names = [e.source_name for e in extractors]
        assert "hackernews" in names
        assert "reddit" in names

    def test_filter_none_returns_all_enabled(self):
        settings = _mock_settings(enabled_sources="hackernews,arxiv,reddit,rss")
        with patch("src.pipeline.pipeline.get_settings", return_value=settings):
            extractors = _get_extractors(sources=None)
        assert len(extractors) == 4

    def test_filter_source_not_enabled_returns_empty(self):
        settings = _mock_settings(enabled_sources="hackernews")
        with patch("src.pipeline.pipeline.get_settings", return_value=settings):
            extractors = _get_extractors(sources=["reddit"])
        assert extractors == []


# ---------------------------------------------------------------------------
# run_pipeline with sources parameter (Task 3)
# ---------------------------------------------------------------------------
class TestRunPipelineWithSources:
    """run_pipeline with sources parameter."""

    @pytest.mark.asyncio
    async def test_pipeline_passes_sources_to_get_extractors(self):
        settings = _mock_settings(
            enabled_sources="hackernews,reddit",
            openai_api_key="",
            enable_news_validation=False,
            embedding_api_key="",
        )
        session = _mock_session()
        items = [_make_extracted_item()]
        classified = [_make_classified_item()]

        with (
            patch("src.pipeline.pipeline.get_settings", return_value=settings),
            patch("src.pipeline.pipeline._get_extractors") as mock_get_ext,
            patch(
                "src.pipeline.pipeline._extract_all",
                new_callable=AsyncMock,
                return_value=items,
            ),
            patch("src.pipeline.pipeline.deduplicate_items", return_value=items),
            patch("src.pipeline.pipeline.KeywordClassifier") as mock_kw_cls,
            patch("src.pipeline.pipeline.CredibilityValidator") as mock_val_cls,
            patch("src.pipeline.pipeline.AlertService") as mock_alerts_cls,
        ):
            mock_ext = MagicMock()
            mock_ext.source_name = "hackernews"
            mock_get_ext.return_value = [mock_ext]

            mock_classifier = AsyncMock()
            mock_classifier.classify.return_value = classified
            mock_kw_cls.return_value = mock_classifier

            mock_validator = AsyncMock()
            mock_validator.validate.return_value = classified
            mock_val_cls.return_value = mock_validator

            mock_alerts = AsyncMock()
            mock_alerts_cls.return_value = mock_alerts

            result = await run_pipeline(session, sources=["hackernews"])

        assert result is True
        mock_get_ext.assert_called_once_with(sources=["hackernews"])


# ---------------------------------------------------------------------------
# since_hours override (Task 3 — per-tier extraction windows)
# ---------------------------------------------------------------------------
class TestPipelineSinceHoursOverride:
    """Verify _extract_all uses custom since_hours when provided."""

    @pytest.mark.asyncio
    async def test_extract_all_uses_custom_since_hours(self):
        mock_extractor = AsyncMock()
        mock_extractor.source_name = "hackernews"
        mock_extractor.extract = AsyncMock(return_value=[])

        settings = _mock_settings(extraction_since_hours=24)
        with patch("src.pipeline.pipeline.get_settings", return_value=settings):
            await _extract_all([mock_extractor], since_hours=1)

        mock_extractor.extract.assert_called_once_with(since_hours=1)

    @pytest.mark.asyncio
    async def test_extract_all_uses_settings_default_when_no_override(self):
        mock_extractor = AsyncMock()
        mock_extractor.source_name = "hackernews"
        mock_extractor.extract = AsyncMock(return_value=[])

        settings = _mock_settings(extraction_since_hours=24)
        with patch("src.pipeline.pipeline.get_settings", return_value=settings):
            await _extract_all([mock_extractor])

        mock_extractor.extract.assert_called_once_with(since_hours=24)
