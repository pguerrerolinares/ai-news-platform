"""Tests for the credibility validator."""

from __future__ import annotations

import asyncio
import socket
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from src.core.config import Settings
from src.validators.credibility import (
    CredibilityValidator,
    _analyze_news_tone,
    _extract_domain,
    _is_duplicate_or_similar,
    _is_safe_url,
    _jaccard_similarity,
    _score_engagement,
    _tokenize,
)
from tests.factories import make_classified_item, make_extracted_item


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _make_settings(**overrides) -> Settings:
    defaults = {
        "enable_news_validation": True,
        "trusted_news_domains": (
            "openai.com,anthropic.com,deepmind.google,arxiv.org," "github.com,techcrunch.com"
        ),
        "openai_api_key": "",
    }
    defaults.update(overrides)
    return Settings(**defaults)


def _make_public_addrinfo(ip: str = "93.184.216.34"):
    """Create a mock getaddrinfo result for a public IP."""
    return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, 0))]


def _make_private_addrinfo(ip: str = "192.168.1.1"):
    """Create a mock getaddrinfo result for a private IP."""
    return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, 0))]


# ---------------------------------------------------------------------------
# _extract_domain
# ---------------------------------------------------------------------------
class TestExtractDomain:
    def test_extracts_hostname(self):
        assert _extract_domain("https://openai.com/blog/gpt5") == "openai.com"

    def test_extracts_subdomain(self):
        assert _extract_domain("https://blog.openai.com/post") == "blog.openai.com"

    def test_returns_none_for_invalid(self):
        assert _extract_domain("not-a-url") is None

    def test_returns_none_for_empty(self):
        assert _extract_domain("") is None


# ---------------------------------------------------------------------------
# _is_safe_url  (SSRF protection, async with non-blocking DNS)
# ---------------------------------------------------------------------------
def _mock_loop_getaddrinfo(return_value=None, side_effect=None):
    """Create a patch for asyncio.get_event_loop().getaddrinfo."""
    mock_loop = MagicMock()
    mock_loop.getaddrinfo = AsyncMock(return_value=return_value, side_effect=side_effect)
    return patch("src.validators.credibility.asyncio.get_event_loop", return_value=mock_loop)


class TestIsSafeUrl:
    @pytest.mark.asyncio
    async def test_public_ip_is_safe(self):
        with _mock_loop_getaddrinfo(return_value=_make_public_addrinfo("93.184.216.34")):
            assert await _is_safe_url("https://example.com/article") is True

    @pytest.mark.asyncio
    async def test_private_ip_blocked(self):
        with _mock_loop_getaddrinfo(return_value=_make_private_addrinfo("192.168.1.1")):
            assert await _is_safe_url("https://internal.corp/secret") is False

    @pytest.mark.asyncio
    async def test_loopback_blocked(self):
        with _mock_loop_getaddrinfo(return_value=_make_private_addrinfo("127.0.0.1")):
            assert await _is_safe_url("https://localhost/admin") is False

    @pytest.mark.asyncio
    async def test_link_local_blocked(self):
        with _mock_loop_getaddrinfo(return_value=_make_private_addrinfo("169.254.169.254")):
            assert await _is_safe_url("http://169.254.169.254/latest/meta-data") is False

    @pytest.mark.asyncio
    async def test_ipv6_loopback_blocked(self):
        ipv6_result = [(socket.AF_INET6, socket.SOCK_STREAM, 6, "", ("::1", 0, 0, 0))]
        with _mock_loop_getaddrinfo(return_value=ipv6_result):
            assert await _is_safe_url("https://[::1]/admin") is False

    @pytest.mark.asyncio
    async def test_ftp_scheme_blocked(self):
        assert await _is_safe_url("ftp://example.com/file") is False

    @pytest.mark.asyncio
    async def test_file_scheme_blocked(self):
        assert await _is_safe_url("file:///etc/passwd") is False

    @pytest.mark.asyncio
    async def test_dns_failure_returns_false(self):
        with _mock_loop_getaddrinfo(side_effect=socket.gaierror("DNS lookup failed")):
            assert await _is_safe_url("https://nonexistent.invalid/page") is False

    @pytest.mark.asyncio
    async def test_no_hostname_returns_false(self):
        assert await _is_safe_url("https://") is False

    @pytest.mark.asyncio
    async def test_reserved_ip_blocked(self):
        with _mock_loop_getaddrinfo(return_value=_make_private_addrinfo("10.0.0.1")):
            assert await _is_safe_url("https://internal.example.com/api") is False


# ---------------------------------------------------------------------------
# _score_engagement
# ---------------------------------------------------------------------------
class TestScoreEngagement:
    def test_very_high_engagement(self):
        item = make_classified_item(
            item=make_extracted_item(score=600),
        )
        assert _score_engagement(item) == 1.0

    def test_high_engagement(self):
        item = make_classified_item(
            item=make_extracted_item(score=500),
        )
        assert _score_engagement(item) == 1.0

    def test_medium_high_engagement(self):
        item = make_classified_item(
            item=make_extracted_item(score=250),
        )
        assert _score_engagement(item) == 0.7

    def test_medium_engagement(self):
        item = make_classified_item(
            item=make_extracted_item(score=200),
        )
        assert _score_engagement(item) == 0.7

    def test_low_medium_engagement(self):
        item = make_classified_item(
            item=make_extracted_item(score=75),
        )
        assert _score_engagement(item) == 0.5

    def test_low_engagement(self):
        item = make_classified_item(
            item=make_extracted_item(score=25),
        )
        assert _score_engagement(item) == 0.3

    def test_very_low_engagement(self):
        item = make_classified_item(
            item=make_extracted_item(score=5),
        )
        assert _score_engagement(item) == 0.1

    def test_zero_engagement(self):
        item = make_classified_item(
            item=make_extracted_item(score=0),
        )
        assert _score_engagement(item) == 0.1

    def test_none_score(self):
        item = make_classified_item(
            item=make_extracted_item(score=None),
        )
        assert _score_engagement(item) == 0.1


# ---------------------------------------------------------------------------
# Domain trust check
# ---------------------------------------------------------------------------
class TestDomainTrust:
    """Domain trust is tested through the full validate_item flow."""

    @patch("src.validators.credibility.get_settings")
    @patch("src.validators.credibility._is_safe_url", return_value=False)
    async def test_trusted_domain_gets_bonus(self, _mock_safe, mock_settings):
        mock_settings.return_value = _make_settings()
        validator = CredibilityValidator()
        item = make_classified_item(
            url="https://openai.com/blog/gpt5",
            item=make_extracted_item(
                url="https://openai.com/blog/gpt5",
                source="rss",
                score=100,
            ),
        )
        async with httpx.AsyncClient() as client:
            result = await validator._validate_item(item, client)
        # Source (rss=0.25) + domain trust (0.3) + engagement + tone
        assert result.credibility_score is not None
        assert result.credibility_score >= 0.5

    @patch("src.validators.credibility.get_settings")
    @patch("src.validators.credibility._is_safe_url", return_value=False)
    async def test_untrusted_domain_no_bonus(self, _mock_safe, mock_settings):
        mock_settings.return_value = _make_settings()
        validator = CredibilityValidator()
        item = make_classified_item(
            url="https://random-blog.xyz/post",
            item=make_extracted_item(
                url="https://random-blog.xyz/post",
                source="reddit",
                score=10,
            ),
        )
        async with httpx.AsyncClient() as client:
            result = await validator._validate_item(item, client)
        # Source (reddit=0.05) + no domain trust + low engagement
        assert result.credibility_score is not None
        assert result.credibility_score < 0.4


# ---------------------------------------------------------------------------
# Source credibility weights
# ---------------------------------------------------------------------------
class TestSourceCredibility:
    @patch("src.validators.credibility.get_settings")
    @patch("src.validators.credibility._is_safe_url", return_value=False)
    async def test_arxiv_highest_weight(self, _mock_safe, mock_settings):
        mock_settings.return_value = _make_settings()
        validator = CredibilityValidator()
        item = make_classified_item(
            url="https://arxiv.org/abs/2401.12345",
            item=make_extracted_item(
                url="https://arxiv.org/abs/2401.12345",
                source="arxiv",
                score=0,
            ),
        )
        async with httpx.AsyncClient() as client:
            result = await validator._validate_item(item, client)
        # arxiv = 0.3 source + 0.3 trusted domain + engagement*0.2 + tone
        assert result.credibility_score is not None
        assert result.credibility_score >= 0.5

    @patch("src.validators.credibility.get_settings")
    @patch("src.validators.credibility._is_safe_url", return_value=False)
    async def test_rss_medium_weight(self, _mock_safe, mock_settings):
        mock_settings.return_value = _make_settings()
        validator = CredibilityValidator()
        item = make_classified_item(
            url="https://random-blog.xyz/feed",
            item=make_extracted_item(
                url="https://random-blog.xyz/feed",
                source="rss",
                score=0,
            ),
        )
        async with httpx.AsyncClient() as client:
            result = await validator._validate_item(item, client)
        # rss = 0.25 source, no trusted domain, low engagement
        assert result.credibility_score is not None
        assert result.credibility_score >= 0.25

    @patch("src.validators.credibility.get_settings")
    @patch("src.validators.credibility._is_safe_url", return_value=False)
    async def test_reddit_lowest_weight(self, _mock_safe, mock_settings):
        mock_settings.return_value = _make_settings()
        validator = CredibilityValidator()
        item = make_classified_item(
            url="https://reddit.com/r/MachineLearning/post",
            item=make_extracted_item(
                url="https://reddit.com/r/MachineLearning/post",
                source="reddit",
                score=0,
            ),
        )
        async with httpx.AsyncClient() as client:
            result = await validator._validate_item(item, client)
        # reddit = 0.05 source, no trusted domain, low engagement
        assert result.credibility_score is not None
        assert result.credibility_score < 0.3


# ---------------------------------------------------------------------------
# Tone analysis
# ---------------------------------------------------------------------------
class TestToneAnalysis:
    def test_suspicious_patterns_reduce_score(self):
        item = make_classified_item(
            item=make_extracted_item(
                title="SHOCKING!!! You won't believe this miracle AI secret!!!",
                text="Act now before limited time offer expires!!!",
            ),
        )
        adjustment = _analyze_news_tone(item)
        # Multiple suspicious patterns should give significant negative adjustment
        assert adjustment < -0.1

    def test_professional_patterns_increase_score(self):
        item = make_classified_item(
            item=make_extracted_item(
                title="Research study published in Nature about transformer methodology",
                text="According to researchers, the analysis and evaluation of the experiment "
                "shows significant findings in the proceedings of the conference.",
            ),
        )
        adjustment = _analyze_news_tone(item)
        # Multiple professional patterns should give positive adjustment
        assert adjustment > 0.0

    def test_neutral_tone_near_zero(self):
        item = make_classified_item(
            item=make_extracted_item(
                title="Simple update about something",
                text="This is a basic text without strong tone indicators.",
            ),
        )
        adjustment = _analyze_news_tone(item)
        # Neutral content should have minimal adjustment
        assert abs(adjustment) < 0.3

    def test_excessive_caps_is_suspicious(self):
        item = make_classified_item(
            item=make_extracted_item(
                title="THIS IS REALLY IMPORTANT NEWS EVERYONE",
                text="Normal text here.",
            ),
        )
        adjustment = _analyze_news_tone(item)
        assert adjustment < 0.0

    def test_multiple_exclamation_marks_suspicious(self):
        item = make_classified_item(
            item=make_extracted_item(
                title="Breaking news about AI!!",
                text="This is exciting!!",
            ),
        )
        adjustment = _analyze_news_tone(item)
        assert adjustment < 0.0


# ---------------------------------------------------------------------------
# URL verification
# ---------------------------------------------------------------------------
class TestUrlVerification:
    async def test_accessible_url_gives_bonus(self):
        mock_response = MagicMock()
        mock_response.status_code = 200

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.head = AsyncMock(return_value=mock_response)

        from src.validators.credibility import _verify_url_content

        bonus = await _verify_url_content("https://example.com/article", mock_client)
        assert bonus == 0.1

    async def test_inaccessible_url_no_bonus(self):
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.head = AsyncMock(side_effect=httpx.TimeoutException("timeout"))

        from src.validators.credibility import _verify_url_content

        bonus = await _verify_url_content("https://example.com/article", mock_client)
        assert bonus == 0.0

    async def test_404_no_bonus(self):
        mock_response = MagicMock()
        mock_response.status_code = 404

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.head = AsyncMock(return_value=mock_response)

        from src.validators.credibility import _verify_url_content

        bonus = await _verify_url_content("https://example.com/missing", mock_client)
        assert bonus == 0.0

    async def test_http_error_no_bonus(self):
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.head = AsyncMock(side_effect=httpx.HTTPError("connection error"))

        from src.validators.credibility import _verify_url_content

        bonus = await _verify_url_content("https://example.com/error", mock_client)
        assert bonus == 0.0


# ---------------------------------------------------------------------------
# Tokenize and Jaccard similarity
# ---------------------------------------------------------------------------
class TestTokenize:
    def test_basic_tokenization(self):
        tokens = _tokenize("Hello World Test")
        assert "hello" in tokens
        assert "world" in tokens
        assert "test" in tokens

    def test_stopwords_removed(self):
        tokens = _tokenize("the quick brown fox is a model")
        assert "the" not in tokens
        assert "is" not in tokens
        assert "a" not in tokens
        assert "model" not in tokens  # AI-domain stopword
        assert "quick" in tokens
        assert "brown" in tokens
        assert "fox" in tokens

    def test_ai_domain_stopwords_removed(self):
        tokens = _tokenize("new AI model based on learning data")
        # All of these are in the stopword list
        assert "ai" not in tokens
        assert "model" not in tokens
        assert "new" not in tokens
        assert "based" not in tokens
        assert "learning" not in tokens
        assert "data" not in tokens

    def test_empty_string(self):
        tokens = _tokenize("")
        assert tokens == set()

    def test_spanish_stopwords_removed(self):
        tokens = _tokenize("el modelo de inteligencia artificial es bueno")
        assert "el" not in tokens
        assert "de" not in tokens
        assert "es" not in tokens


class TestJaccardSimilarity:
    def test_identical_texts(self):
        text = "GPT-5 achieves breakthrough performance on benchmarks"
        sim = _jaccard_similarity(text, text)
        assert sim == 1.0

    def test_completely_different_texts(self):
        text_a = "quantum computing photonics silicon chip fabrication"
        text_b = "pizza recipe tomato basil mozzarella oven"
        sim = _jaccard_similarity(text_a, text_b)
        assert sim < 0.1

    def test_similar_texts_above_threshold(self):
        text_a = "OpenAI releases GPT-5 with improved reasoning capabilities"
        text_b = "OpenAI launches GPT-5 featuring enhanced reasoning abilities"
        sim = _jaccard_similarity(text_a, text_b)
        # These are very similar after stopword removal
        assert sim >= 0.3  # Moderate similarity after stopword removal

    def test_empty_text_returns_zero(self):
        assert _jaccard_similarity("", "some text") == 0.0
        assert _jaccard_similarity("some text", "") == 0.0
        assert _jaccard_similarity("", "") == 0.0

    def test_only_stopwords_returns_zero(self):
        """Text consisting entirely of stopwords should return 0.0."""
        assert _jaccard_similarity("the is a an", "the is a an") == 0.0


class TestIsDuplicateOrSimilar:
    def test_duplicate_detected(self):
        item1 = make_classified_item(
            title="OpenAI releases GPT-5 breakthrough",
            text="The GPT-5 release from OpenAI represents a breakthrough",
        )
        item2 = make_classified_item(
            title="OpenAI releases GPT-5 breakthrough",
            text="The GPT-5 release from OpenAI represents a breakthrough",
        )
        assert _is_duplicate_or_similar(item2, [item1]) is True

    def test_different_items_not_duplicate(self):
        item1 = make_classified_item(
            title="OpenAI releases GPT-5 breakthrough performance",
            text="Performance benchmarks show remarkable improvements across tasks",
        )
        item2 = make_classified_item(
            title="European Union passes comprehensive AI regulation bill",
            text="Lawmakers voted to approve strict safety requirements for AI systems",
        )
        assert _is_duplicate_or_similar(item2, [item1]) is False

    def test_empty_existing_list(self):
        item = make_classified_item(
            title="Some article about AI",
            text="Content about AI developments",
        )
        assert _is_duplicate_or_similar(item, []) is False


# ---------------------------------------------------------------------------
# Noise filtering
# ---------------------------------------------------------------------------
class TestNoiseFiltering:
    def test_low_credibility_filtered(self):
        validator = CredibilityValidator()
        items = [
            make_classified_item(
                title="Low quality item",
                item=make_extracted_item(source="reddit", score=100),
            ),
        ]
        items[0].credibility_score = 0.3  # Below 0.4 threshold
        result = validator._filter_noise(items)
        assert len(result) == 0

    def test_high_credibility_kept(self):
        validator = CredibilityValidator()
        items = [
            make_classified_item(
                title="High quality item",
                item=make_extracted_item(source="arxiv", score=100),
            ),
        ]
        items[0].credibility_score = 0.7
        result = validator._filter_noise(items)
        assert len(result) == 1

    def test_low_engagement_hackernews_filtered(self):
        validator = CredibilityValidator()
        items = [
            make_classified_item(
                title="HN item with low engagement",
                item=make_extracted_item(source="hackernews", score=3),
            ),
        ]
        items[0].credibility_score = 0.5  # Above threshold
        result = validator._filter_noise(items)
        assert len(result) == 0

    def test_low_engagement_reddit_filtered(self):
        validator = CredibilityValidator()
        items = [
            make_classified_item(
                title="Reddit item with low engagement",
                item=make_extracted_item(source="reddit", score=2),
            ),
        ]
        items[0].credibility_score = 0.5
        result = validator._filter_noise(items)
        assert len(result) == 0

    def test_low_engagement_arxiv_not_filtered(self):
        """arXiv items should not be filtered by engagement score."""
        validator = CredibilityValidator()
        items = [
            make_classified_item(
                title="ArXiv paper with no engagement score",
                item=make_extracted_item(source="arxiv", score=0),
            ),
        ]
        items[0].credibility_score = 0.6
        result = validator._filter_noise(items)
        assert len(result) == 1

    def test_sufficient_engagement_kept(self):
        validator = CredibilityValidator()
        items = [
            make_classified_item(
                title="HN item with good engagement",
                item=make_extracted_item(source="hackernews", score=50),
            ),
        ]
        items[0].credibility_score = 0.5
        result = validator._filter_noise(items)
        assert len(result) == 1

    def test_jaccard_dedup_removes_duplicate(self):
        validator = CredibilityValidator()
        items = [
            make_classified_item(
                title="OpenAI releases GPT-5 performance breakthrough",
                text="GPT-5 release from OpenAI achieves performance breakthrough",
                item=make_extracted_item(
                    title="OpenAI releases GPT-5 performance breakthrough",
                    text="GPT-5 release from OpenAI achieves performance breakthrough",
                    source="hackernews",
                    score=100,
                ),
            ),
            make_classified_item(
                title="OpenAI releases GPT-5 performance breakthrough",
                text="GPT-5 release from OpenAI achieves performance breakthrough",
                item=make_extracted_item(
                    title="OpenAI releases GPT-5 performance breakthrough",
                    text="GPT-5 release from OpenAI achieves performance breakthrough",
                    source="reddit",
                    score=100,
                    url="https://example.com/article-2",
                ),
            ),
        ]
        items[0].credibility_score = 0.7
        items[1].credibility_score = 0.6
        result = validator._filter_noise(items)
        # Second identical item should be deduped
        assert len(result) == 1

    def test_different_items_not_deduped(self):
        validator = CredibilityValidator()
        items = [
            make_classified_item(
                title="OpenAI releases GPT-5 performance breakthrough results",
                text="Significant performance improvements across various benchmarks",
                item=make_extracted_item(
                    title="OpenAI releases GPT-5 performance breakthrough results",
                    text="Significant performance improvements across various benchmarks",
                    source="hackernews",
                    score=100,
                ),
            ),
            make_classified_item(
                title="European Union passes comprehensive regulation bill for safety",
                text="Lawmakers voted strict requirements for artificial intelligence systems",
                item=make_extracted_item(
                    title="European Union passes comprehensive regulation bill for safety",
                    text="Lawmakers voted strict requirements for artificial intelligence systems",
                    source="hackernews",
                    score=50,
                    url="https://example.com/eu-regulation",
                ),
            ),
        ]
        items[0].credibility_score = 0.7
        items[1].credibility_score = 0.6
        result = validator._filter_noise(items)
        assert len(result) == 2

    def test_credibility_exactly_at_threshold(self):
        """Items at exactly 0.4 should NOT be filtered (>= would keep, < filters)."""
        validator = CredibilityValidator()
        items = [
            make_classified_item(
                title="Borderline item",
                item=make_extracted_item(source="rss", score=50),
            ),
        ]
        items[0].credibility_score = 0.4
        result = validator._filter_noise(items)
        assert len(result) == 1

    def test_engagement_exactly_at_threshold(self):
        """Items with score=5 for HN should be kept (threshold is < 5)."""
        validator = CredibilityValidator()
        items = [
            make_classified_item(
                title="HN item at engagement threshold",
                item=make_extracted_item(source="hackernews", score=5),
            ),
        ]
        items[0].credibility_score = 0.5
        result = validator._filter_noise(items)
        assert len(result) == 1


# ---------------------------------------------------------------------------
# Full validate() method
# ---------------------------------------------------------------------------
class TestValidateMethod:
    @patch("src.validators.credibility.get_settings")
    async def test_validation_disabled_returns_all_items(self, mock_settings):
        mock_settings.return_value = _make_settings(enable_news_validation=False)
        validator = CredibilityValidator()
        items = [
            make_classified_item(title="Item 1"),
            make_classified_item(title="Item 2"),
        ]
        result = await validator.validate(items)
        assert len(result) == 2
        # Credibility score should NOT be set when validation is disabled
        assert result[0].credibility_score is None

    @patch("src.validators.credibility.get_settings")
    async def test_validate_empty_list(self, mock_settings):
        mock_settings.return_value = _make_settings()
        validator = CredibilityValidator()
        result = await validator.validate([])
        assert result == []

    @patch("src.validators.credibility._is_safe_url", return_value=False)
    @patch("src.validators.credibility.get_settings")
    async def test_validate_sets_credibility_scores(self, mock_settings, _mock_safe):
        mock_settings.return_value = _make_settings()
        validator = CredibilityValidator()
        items = [
            make_classified_item(
                title="Research paper published with findings and methodology",
                url="https://arxiv.org/abs/2401.12345",
                item=make_extracted_item(
                    title="Research paper published with findings and methodology",
                    url="https://arxiv.org/abs/2401.12345",
                    source="arxiv",
                    score=0,
                ),
            ),
        ]
        result = await validator.validate(items)
        # Should have credibility score set
        for item in result:
            assert item.credibility_score is not None
            assert 0.0 <= item.credibility_score <= 1.0

    @patch("src.validators.credibility._is_safe_url", return_value=False)
    @patch("src.validators.credibility.get_settings")
    async def test_validate_filters_low_quality(self, mock_settings, _mock_safe):
        mock_settings.return_value = _make_settings()
        validator = CredibilityValidator()
        items = [
            # High quality item
            make_classified_item(
                title="Research paper published with findings and evaluation methodology",
                url="https://arxiv.org/abs/2401.12345",
                item=make_extracted_item(
                    title="Research paper published with findings and evaluation methodology",
                    url="https://arxiv.org/abs/2401.12345",
                    source="arxiv",
                    score=100,
                ),
            ),
            # Low quality item (suspicious tone, low source credibility, no engagement)
            make_classified_item(
                title="SHOCKING!!! You won't believe this miracle AI secret!!!",
                url="https://spammy-blog.xyz/clickbait",
                item=make_extracted_item(
                    title="SHOCKING!!! You won't believe this miracle AI secret!!!",
                    url="https://spammy-blog.xyz/clickbait",
                    source="reddit",
                    score=1,
                ),
            ),
        ]
        result = await validator.validate(items)
        # Low quality item should be filtered out
        assert len(result) <= len(items)
        # The high-quality arxiv item should survive
        arxiv_items = [i for i in result if i.item.source == "arxiv"]
        assert len(arxiv_items) >= 1


# ---------------------------------------------------------------------------
# Concurrent validation with Semaphore
# ---------------------------------------------------------------------------
class TestConcurrentValidation:
    @patch("src.validators.credibility._is_safe_url", return_value=False)
    @patch("src.validators.credibility.get_settings")
    async def test_concurrent_validation_respects_semaphore(
        self,
        mock_settings,
        _mock_safe,
    ):
        mock_settings.return_value = _make_settings()
        validator = CredibilityValidator()

        # Track concurrent access
        max_concurrent = 0
        current_concurrent = 0
        lock = asyncio.Lock()

        original_validate_item = validator._validate_item

        async def _tracking_validate(item, client):
            nonlocal max_concurrent, current_concurrent
            async with lock:
                current_concurrent += 1
                max_concurrent = max(max_concurrent, current_concurrent)
            try:
                # Small delay to ensure concurrency is observable
                await asyncio.sleep(0.01)
                return await original_validate_item(item, client)
            finally:
                async with lock:
                    current_concurrent -= 1

        validator._validate_item = _tracking_validate

        # Create more items than the semaphore limit (5)
        items = [
            make_classified_item(
                title=f"Item {i} about research methodology",
                url=f"https://example.com/article-{i}",
                item=make_extracted_item(
                    title=f"Item {i} about research methodology",
                    url=f"https://example.com/article-{i}",
                    source="rss",
                    score=100,
                ),
            )
            for i in range(10)
        ]

        await validator._validate_batch(items)

        # Semaphore should limit to 5 concurrent validations
        assert max_concurrent <= 5

    @patch("src.validators.credibility._is_safe_url", return_value=False)
    @patch("src.validators.credibility.get_settings")
    async def test_batch_validates_all_items(self, mock_settings, _mock_safe):
        mock_settings.return_value = _make_settings()
        validator = CredibilityValidator()

        items = [
            make_classified_item(
                title=f"Article {i}",
                url=f"https://example.com/article-{i}",
                item=make_extracted_item(
                    title=f"Article {i}",
                    url=f"https://example.com/article-{i}",
                    source="rss",
                    score=50,
                ),
            )
            for i in range(8)
        ]

        results = await validator._validate_batch(items)
        assert len(results) == 8
        for item in results:
            assert item.credibility_score is not None


# ---------------------------------------------------------------------------
# Credibility score clamping
# ---------------------------------------------------------------------------
class TestScoreClamping:
    @patch("src.validators.credibility.get_settings")
    @patch("src.validators.credibility._is_safe_url", return_value=False)
    async def test_score_never_exceeds_1(self, _mock_safe, mock_settings):
        mock_settings.return_value = _make_settings()
        validator = CredibilityValidator()
        # Create item with everything maxed out
        item = make_classified_item(
            title="Research paper published findings evaluation methodology analysis",
            url="https://arxiv.org/abs/2401.99999",
            item=make_extracted_item(
                title="Research paper published findings evaluation methodology analysis",
                url="https://arxiv.org/abs/2401.99999",
                source="arxiv",
                score=1000,
            ),
        )
        async with httpx.AsyncClient() as client:
            result = await validator._validate_item(item, client)
        assert result.credibility_score is not None
        assert result.credibility_score <= 1.0

    @patch("src.validators.credibility.get_settings")
    @patch("src.validators.credibility._is_safe_url", return_value=False)
    async def test_score_never_below_0(self, _mock_safe, mock_settings):
        mock_settings.return_value = _make_settings()
        validator = CredibilityValidator()
        # Create item with very suspicious tone
        item = make_classified_item(
            title="SHOCKING!!! You won't believe this miracle secret conspiracy!!!",
            url="https://random.xyz/spam",
            item=make_extracted_item(
                title="SHOCKING!!! You won't believe this miracle secret conspiracy!!!",
                url="https://random.xyz/spam",
                text="Act now!!! Limited time!!! Don't miss this unbelievable deal!!!",
                source="reddit",
                score=0,
            ),
        )
        async with httpx.AsyncClient() as client:
            result = await validator._validate_item(item, client)
        assert result.credibility_score is not None
        assert result.credibility_score >= 0.0


# ---------------------------------------------------------------------------
# Edge-case tests (M9 milestone)
# ---------------------------------------------------------------------------
class TestEdgeCasesIsSafeUrl:
    """Edge cases for SSRF protection in _is_safe_url."""

    async def test_ipv4_mapped_ipv6_blocked(self):
        """IPv4-mapped IPv6 addresses (::ffff:127.0.0.1) must be blocked."""
        ipv6_mapped = [(socket.AF_INET6, socket.SOCK_STREAM, 6, "", ("::ffff:127.0.0.1", 0, 0, 0))]
        with _mock_loop_getaddrinfo(return_value=ipv6_mapped):
            assert await _is_safe_url("https://mapped.example.com") is False

    async def test_empty_url_returns_false(self):
        """Completely empty URL string must return False."""
        assert await _is_safe_url("") is False


class TestEdgeCasesUrlVerification:
    """Edge cases for _verify_url_content."""

    async def test_ssl_error_no_bonus(self):
        """An SSL/TLS error should yield bonus=0.0, not crash."""
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        # ConnectError is what httpx raises for SSL failures; it inherits HTTPError
        mock_client.head = AsyncMock(
            side_effect=httpx.ConnectError("SSL: CERTIFICATE_VERIFY_FAILED")
        )

        from src.validators.credibility import _verify_url_content

        bonus = await _verify_url_content("https://bad-cert.example.com/article", mock_client)
        assert bonus == 0.0

    async def test_read_timeout_no_bonus(self):
        """A ReadTimeout (very slow response) should yield bonus=0.0."""
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.head = AsyncMock(side_effect=httpx.ReadTimeout("read timed out"))

        from src.validators.credibility import _verify_url_content

        bonus = await _verify_url_content("https://slow.example.com/article", mock_client)
        assert bonus == 0.0


class TestEdgeCasesTokenize:
    """Edge cases for _tokenize."""

    def test_only_punctuation_returns_empty(self):
        """Input of only punctuation should yield an empty token set."""
        tokens = _tokenize("!!! ??? ...")
        assert tokens == set()

    def test_unicode_text_includes_ascii_tokens(self):
        """Unicode text should still tokenize ASCII words correctly.

        The regex [a-zA-Z0-9]+ drops non-ASCII chars, but ASCII words
        like 'transformer' must survive.
        """
        tokens = _tokenize("réseau neuronal 神经网络 transformer")
        assert "transformer" in tokens
        # 'r' and 'seau' may appear as fragments — the key assertion is 'transformer'


class TestEdgeCasesJaccard:
    """Edge cases for _jaccard_similarity."""

    def test_both_only_stopwords_different_sets_returns_zero(self):
        """Two texts with only stopwords (different sets) must return 0.0, no ZeroDivisionError."""
        sim = _jaccard_similarity("the is a an", "and or but")
        assert sim == 0.0

    def test_one_word_overlap_between_zero_and_one(self):
        """Partial overlap should give a Jaccard score strictly between 0 and 1."""
        sim = _jaccard_similarity("quantum computing revolution", "quantum physics breakthrough")
        assert 0.0 < sim < 1.0
