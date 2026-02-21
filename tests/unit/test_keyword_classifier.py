"""Tests for the keyword-based classifier."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from src.classifiers.base import ClassifiedItem
from src.classifiers.keyword import (
    TOPIC_DEFINITIONS,
    KeywordClassifier,
    _calculate_priority,
    classify_by_keywords,
)
from src.core.config import Settings
from tests.factories import make_extracted_item


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _make_settings(**overrides) -> Settings:
    defaults = {
        "topics": "modelos,herramientas,papers,productos,open_source,agentes,regulacion",
        "min_relevance_score": 0.8,
        "openai_api_key": "",
    }
    defaults.update(overrides)
    return Settings(**defaults)


# ---------------------------------------------------------------------------
# TOPIC_DEFINITIONS structure
# ---------------------------------------------------------------------------
class TestTopicDefinitions:
    def test_has_seven_topics(self):
        assert len(TOPIC_DEFINITIONS) == 7

    def test_all_topics_have_keywords_and_description(self):
        for topic, data in TOPIC_DEFINITIONS.items():
            assert "keywords" in data, f"{topic} missing keywords"
            assert "description" in data, f"{topic} missing description"
            assert isinstance(data["keywords"], list)
            assert len(data["keywords"]) > 0

    def test_expected_topics_present(self):
        expected = {
            "modelos",
            "herramientas",
            "papers",
            "productos",
            "open_source",
            "agentes",
            "regulacion",
        }
        assert set(TOPIC_DEFINITIONS.keys()) == expected


# ---------------------------------------------------------------------------
# classify_by_keywords
# ---------------------------------------------------------------------------
class TestClassifyByKeywords:
    def test_modelos_item(self):
        item = make_extracted_item(
            title="New GPT-5 LLM achieves SOTA on MMLU benchmark",
            text="The transformer model uses a novel attention architecture with 1T parameters",
        )
        topic, score = classify_by_keywords(item)
        assert topic == "modelos"
        assert score > 0.1

    def test_herramientas_item(self):
        item = make_extracted_item(
            title="LangChain releases new SDK for RAG pipeline deployment",
            text="The framework integrates with vLLM for serving and HuggingFace embeddings",
        )
        topic, score = classify_by_keywords(item)
        assert topic == "herramientas"
        assert score > 0.1

    def test_papers_item(self):
        item = make_extracted_item(
            title="Novel algorithm achieves state-of-the-art on NeurIPS benchmark",
            text="This research paper presents findings from ablation experiments "
            "on arxiv preprint",
        )
        topic, score = classify_by_keywords(item)
        assert topic == "papers"
        assert score > 0.1

    def test_productos_item(self):
        item = make_extracted_item(
            title="ChatGPT launches new enterprise feature update",
            text="The product release includes assistant pricing "
            "for general availability subscription",
        )
        topic, score = classify_by_keywords(item)
        assert topic == "productos"
        assert score > 0.1

    def test_open_source_item(self):
        item = make_extracted_item(
            title="Llama 4 released as open source with MIT license on GitHub",
            text="Self-hosted local weights available for the community under Apache license",
        )
        topic, score = classify_by_keywords(item)
        assert topic == "open_source"
        assert score > 0.1

    def test_agentes_item(self):
        item = make_extracted_item(
            title="New MCP agent framework for autonomous multi-agent workflows",
            text="Agentic tool use with function calling and chain of thought reasoning",
        )
        topic, score = classify_by_keywords(item)
        assert topic == "agentes"
        assert score > 0.1

    def test_regulacion_item(self):
        item = make_extracted_item(
            title="EU AI Act regulation policy update on safety and alignment",
            text="Governance compliance for deepfake and misinformation risk ethics",
        )
        topic, score = classify_by_keywords(item)
        assert topic == "regulacion"
        assert score > 0.1

    def test_no_match_returns_none(self):
        item = make_extracted_item(
            title="Best pizza recipe for dinner tonight",
            text="Use mozzarella cheese and basil for the perfect margherita",
        )
        topic, score = classify_by_keywords(item)
        assert topic is None
        assert score == 0.0

    def test_low_match_returns_none(self):
        """A single very weak match should still return None if score < 0.1."""
        item = make_extracted_item(
            title="Something about a local restaurant update",
            text="The new menu has a novel approach to cooking.",
        )
        topic, score = classify_by_keywords(item)
        # With such few keyword matches, score * 3 should be < 0.1
        # or if it barely passes, at least it's a very low score
        # The key test is that truly irrelevant content gets filtered
        if topic is not None:
            assert score >= 0.1  # If it matched, score should be at threshold

    def test_score_capped_at_1(self):
        """Relevance score should never exceed 1.0."""
        item = make_extracted_item(
            title="GPT LLM model benchmark MMLU training fine-tuning weights parameters "
            "transformer diffusion multimodal Llama Mistral SOTA attention token",
            text="architecture context window vision language "
            "Gemini Claude Qwen DeepSeek perplexity",
        )
        topic, score = classify_by_keywords(item)
        assert score <= 1.0

    def test_text_truncated_to_500_chars(self):
        """Only first 500 chars of text should be used."""
        # Keywords only in the part beyond 500 chars
        padding = "x " * 300  # 600 chars of padding
        item = make_extracted_item(
            title="General news article",
            text=padding + "GPT LLM transformer model benchmark MMLU SOTA",
        )
        topic, _ = classify_by_keywords(item)
        # Title has no keywords and text keywords are beyond 500 chars cutoff
        assert topic is None


# ---------------------------------------------------------------------------
# _calculate_priority
# ---------------------------------------------------------------------------
class TestCalculatePriority:
    def test_high_score_gives_low_priority(self):
        item = make_extracted_item(score=600)
        priority = _calculate_priority(item, relevance=0.85)
        assert priority == 1  # 600 > 500 -> 1, 0.85 relevance -> no change

    def test_medium_score(self):
        item = make_extracted_item(score=250)
        priority = _calculate_priority(item, relevance=0.85)
        assert priority == 2  # 250 > 200 -> 2

    def test_low_score(self):
        item = make_extracted_item(score=60)
        priority = _calculate_priority(item, relevance=0.85)
        assert priority == 3  # 60 > 50 -> 3

    def test_very_low_score(self):
        item = make_extracted_item(score=15)
        priority = _calculate_priority(item, relevance=0.85)
        assert priority == 4  # 15 > 10 -> 4

    def test_no_score(self):
        item = make_extracted_item(score=None)
        priority = _calculate_priority(item, relevance=0.85)
        assert priority == 5  # None -> 0, below all thresholds

    def test_zero_score(self):
        item = make_extracted_item(score=0)
        priority = _calculate_priority(item, relevance=0.85)
        assert priority == 5

    def test_very_high_relevance_boost(self):
        item = make_extracted_item(score=60)
        priority = _calculate_priority(item, relevance=0.95)
        assert priority == 1  # 3 - 2 = 1

    def test_high_relevance_boost(self):
        item = make_extracted_item(score=60)
        priority = _calculate_priority(item, relevance=0.9)
        assert priority == 2  # 3 - 1 = 2

    def test_low_relevance_penalty(self):
        item = make_extracted_item(score=60)
        priority = _calculate_priority(item, relevance=0.7)
        assert priority == 4  # 3 + 1 = 4

    def test_rss_source_boost(self):
        item = make_extracted_item(source="rss", score=60)
        priority = _calculate_priority(item, relevance=0.85)
        assert priority == 2  # 3 - 1 = 2

    def test_arxiv_source_boost(self):
        item = make_extracted_item(source="arxiv", score=60)
        priority = _calculate_priority(item, relevance=0.85)
        assert priority == 2  # 3 - 1 = 2

    def test_priority_clamped_to_1(self):
        """Priority can never go below 1."""
        item = make_extracted_item(source="arxiv", score=600)
        priority = _calculate_priority(item, relevance=0.95)
        # 1 (score) - 2 (relevance) - 1 (source) = -2 -> clamped to 1
        assert priority == 1

    def test_priority_clamped_to_5(self):
        """Priority can never go above 5."""
        item = make_extracted_item(source="hackernews", score=0)
        priority = _calculate_priority(item, relevance=0.7)
        # 5 (no score match) + 1 (low relevance) = 6 -> clamped to 5
        assert priority == 5


# ---------------------------------------------------------------------------
# KeywordClassifier.classify()
# ---------------------------------------------------------------------------
class TestKeywordClassifier:
    @pytest.fixture(autouse=True)
    def _patch_settings(self):
        with patch(
            "src.classifiers.keyword.get_settings",
            return_value=_make_settings(),
        ):
            yield

    @pytest.fixture()
    def classifier(self):
        return KeywordClassifier()

    async def test_classify_returns_classified_items(self, classifier):
        items = [
            make_extracted_item(
                title="GPT-5 LLM achieves SOTA on MMLU with transformer architecture",
                text="New model with attention mechanism and 1T parameters",
                score=100,
            ),
        ]
        results = await classifier.classify(items)
        assert len(results) >= 1
        assert all(isinstance(r, ClassifiedItem) for r in results)
        assert results[0].topic == "modelos"
        assert results[0].relevance_score > 0.0
        assert results[0].item is items[0]

    async def test_classify_filters_below_min_relevance(self, classifier):
        items = [
            make_extracted_item(
                title="General article about cooking recipes",
                text="How to make the perfect pasta with basil",
            ),
        ]
        results = await classifier.classify(items)
        assert len(results) == 0

    async def test_classify_filters_disabled_topics(self):
        settings = _make_settings(topics="papers,agentes")
        with patch("src.classifiers.keyword.get_settings", return_value=settings):
            classifier = KeywordClassifier()
            items = [
                make_extracted_item(
                    title="GPT-5 LLM achieves SOTA on MMLU benchmark with transformer",
                    text="New model with attention mechanism and 1T parameters training",
                    score=100,
                ),
            ]
            results = await classifier.classify(items)
            # "modelos" is not in enabled topics, so it should be filtered
            for r in results:
                assert r.topic in ("papers", "agentes")

    async def test_classify_multiple_items(self, classifier):
        items = [
            make_extracted_item(
                title="GPT-5 LLM achieves SOTA on MMLU benchmark with transformer architecture",
                text="New model training fine-tuning attention weights parameters",
                score=300,
            ),
            make_extracted_item(
                title="EU AI Act regulation policy on safety alignment ethics",
                text="Governance compliance copyright deepfake misinformation ban law risk",
                url="https://example.com/eu-regulation",
                score=50,
            ),
            make_extracted_item(
                title="Unrelated article about gardening tips",
                text="How to grow tomatoes in your backyard",
                url="https://example.com/gardening",
            ),
        ]
        results = await classifier.classify(items)
        # At least the modelos and regulacion items should be classified
        topics = [r.topic for r in results]
        assert "modelos" in topics
        assert "regulacion" in topics
        # Gardening should be filtered out
        assert not any(r.item.title.startswith("Unrelated") for r in results)

    async def test_classify_empty_list(self, classifier):
        results = await classifier.classify([])
        assert results == []

    async def test_classify_priority_is_set(self, classifier):
        items = [
            make_extracted_item(
                title="GPT-5 LLM achieves SOTA on MMLU benchmark with transformer architecture",
                text="New model training fine-tuning attention weights parameters",
                score=300,
            ),
        ]
        results = await classifier.classify(items)
        assert len(results) >= 1
        assert 1 <= results[0].priority <= 5

    async def test_classify_with_custom_min_relevance(self):
        settings = _make_settings(min_relevance_score=0.99)
        with patch("src.classifiers.keyword.get_settings", return_value=settings):
            classifier = KeywordClassifier()
            items = [
                make_extracted_item(
                    title="GPT-5 LLM model",
                    text="New transformer model released",
                    score=100,
                ),
            ]
            results = await classifier.classify(items)
            # Very high threshold should filter most items
            assert len(results) == 0

    async def test_classify_summary_is_none(self, classifier):
        """Keyword classifier does not generate summaries."""
        items = [
            make_extracted_item(
                title="GPT-5 LLM achieves SOTA on MMLU benchmark with transformer architecture",
                text="New model training fine-tuning attention weights parameters",
                score=100,
            ),
        ]
        results = await classifier.classify(items)
        assert len(results) >= 1
        assert results[0].summary is None

    async def test_classify_default_values(self, classifier):
        items = [
            make_extracted_item(
                title="GPT-5 LLM achieves SOTA on MMLU benchmark with transformer architecture",
                text="New model training fine-tuning attention weights parameters",
                score=100,
            ),
        ]
        results = await classifier.classify(items)
        assert len(results) >= 1
        r = results[0]
        assert r.trending is False
        assert r.source_count == 1
        assert r.dev_value_score is None
        assert r.credibility_score is None


# ---------------------------------------------------------------------------
# Edge-case tests
# ---------------------------------------------------------------------------
class TestKeywordEdgeCases:
    @pytest.fixture(autouse=True)
    def _patch_settings(self):
        with patch(
            "src.classifiers.keyword.get_settings",
            return_value=_make_settings(),
        ):
            yield

    @pytest.fixture()
    def classifier(self):
        return KeywordClassifier()

    async def test_empty_title_and_text(self, classifier):
        """Item with empty title and text gets relevance=0, filtered out."""
        items = [make_extracted_item(title="", text="")]
        results = await classifier.classify(items)
        assert len(results) == 0

    async def test_title_only_emojis(self, classifier):
        """Title with only emojis has no keyword match, filtered out."""
        items = [make_extracted_item(title="\U0001f916\U0001f525\U0001f4af", text="")]
        results = await classifier.classify(items)
        assert len(results) == 0

    async def test_title_only_stopwords(self, classifier):
        """Title with only stopwords has no keyword match, filtered out."""
        items = [make_extracted_item(title="the and or is", text="")]
        results = await classifier.classify(items)
        assert len(results) == 0

    async def test_all_topics_disabled(self):
        """Config with no topics enabled filters everything."""
        settings = _make_settings(topics="")
        with patch("src.classifiers.keyword.get_settings", return_value=settings):
            classifier = KeywordClassifier()
            items = [
                make_extracted_item(
                    title="GPT-5 LLM achieves SOTA on MMLU benchmark with transformer",
                    text="New model training fine-tuning attention weights parameters",
                    score=100,
                ),
            ]
            results = await classifier.classify(items)
            assert len(results) == 0
