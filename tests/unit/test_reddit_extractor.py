"""Tests for src.extractors.reddit -- RedditExtractor."""

from __future__ import annotations

from unittest.mock import patch

import httpx
import respx

from src.extractors.base import ExtractedItem
from src.extractors.reddit import BASE_URL, RedditExtractor


# ---------------------------------------------------------------------------
# Sample Reddit JSON API response data
# ---------------------------------------------------------------------------
def _make_post(
    post_id: str = "abc123",
    title: str = "New LLM breakthrough",
    url: str = "https://example.com/article",
    score: int = 500,
    num_comments: int = 100,
    author: str = "testuser",
    subreddit: str = "MachineLearning",
    is_self: bool = False,
    stickied: bool = False,
    selftext: str = "",
    upvote_ratio: float = 0.95,
    flair: str = "Research",
    domain: str = "example.com",
    created_utc: float = 1708000000.0,
    permalink: str | None = None,
) -> dict:
    """Build a single Reddit post child object."""
    if permalink is None:
        permalink = f"/r/{subreddit}/comments/{post_id}/test_post/"
    return {
        "kind": "t3",
        "data": {
            "id": post_id,
            "title": title,
            "url": url,
            "score": score,
            "num_comments": num_comments,
            "author": author,
            "subreddit": subreddit,
            "is_self": is_self,
            "stickied": stickied,
            "selftext": selftext,
            "upvote_ratio": upvote_ratio,
            "link_flair_text": flair,
            "domain": domain,
            "created_utc": created_utc,
            "permalink": permalink,
        },
    }


def _reddit_response(posts: list[dict]) -> dict:
    """Wrap posts in the Reddit listing response structure."""
    return {
        "kind": "Listing",
        "data": {
            "children": posts,
            "after": None,
            "before": None,
        },
    }


def _mock_settings(**overrides):
    """Return a minimal Settings-like object for Reddit extraction."""
    from src.core.config import Settings

    defaults = {
        "reddit_subreddits": "MachineLearning",
        "reddit_top_limit": 25,
        "max_items_per_source": 50,
        "enabled_sources": "reddit",
        "telegram_bot_token": "",
        "telegram_chat_id": "",
        "telegram_alerts_enabled": False,
    }
    defaults.update(overrides)
    return Settings(**defaults)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------
class TestSourceName:
    """RedditExtractor.source_name property."""

    def test_source_name_returns_reddit(self):
        extractor = RedditExtractor()
        assert extractor.source_name == "reddit"


class TestExtract:
    """RedditExtractor.extract() with mocked HTTP responses."""

    @respx.mock
    async def test_extract_returns_list_of_extracted_items(self):
        """extract() should return a list of ExtractedItem instances."""
        posts = [
            _make_post("abc1", "Post A", score=200),
            _make_post("abc2", "Post B", score=150),
        ]
        respx.get(f"{BASE_URL}/r/MachineLearning/top/.json").mock(
            return_value=httpx.Response(200, json=_reddit_response(posts)),
        )

        settings = _mock_settings()
        with patch("src.extractors.reddit.get_settings", return_value=settings):
            extractor = RedditExtractor()
            result = await extractor.extract(since_hours=24)

        assert isinstance(result, list)
        assert len(result) == 2
        for item in result:
            assert isinstance(item, ExtractedItem)

    @respx.mock
    async def test_items_have_correct_source(self):
        """Every returned item must have source='reddit'."""
        posts = [_make_post("abc1", "AI Post")]
        respx.get(f"{BASE_URL}/r/MachineLearning/top/.json").mock(
            return_value=httpx.Response(200, json=_reddit_response(posts)),
        )

        settings = _mock_settings()
        with patch("src.extractors.reddit.get_settings", return_value=settings):
            extractor = RedditExtractor()
            result = await extractor.extract()

        assert all(item.source == "reddit" for item in result)

    @respx.mock
    async def test_items_sorted_by_score_descending(self):
        """Items must be sorted by score in descending order."""
        posts = [
            _make_post("a", "Low", score=50),
            _make_post("b", "High", score=500),
            _make_post("c", "Mid", score=200),
        ]
        respx.get(f"{BASE_URL}/r/MachineLearning/top/.json").mock(
            return_value=httpx.Response(200, json=_reddit_response(posts)),
        )

        settings = _mock_settings()
        with patch("src.extractors.reddit.get_settings", return_value=settings):
            extractor = RedditExtractor()
            result = await extractor.extract()

        scores = [item.score for item in result]
        assert scores == [500, 200, 50]

    @respx.mock
    async def test_skips_stickied_posts(self):
        """Stickied posts should be filtered out."""
        posts = [
            _make_post("sticky1", "Weekly Discussion Thread", stickied=True, score=10),
            _make_post("normal1", "Real AI Post", stickied=False, score=200),
        ]
        respx.get(f"{BASE_URL}/r/MachineLearning/top/.json").mock(
            return_value=httpx.Response(200, json=_reddit_response(posts)),
        )

        settings = _mock_settings()
        with patch("src.extractors.reddit.get_settings", return_value=settings):
            extractor = RedditExtractor()
            result = await extractor.extract()

        assert len(result) == 1
        assert result[0].metadata["post_id"] == "normal1"

    @respx.mock
    async def test_deduplication_by_post_id(self):
        """Duplicate post IDs across subreddits should be deduplicated."""
        post = _make_post("dup1", "Duplicate Post", score=100)
        response = _reddit_response([post])

        respx.get(f"{BASE_URL}/r/MachineLearning/top/.json").mock(
            return_value=httpx.Response(200, json=response),
        )
        respx.get(f"{BASE_URL}/r/LocalLLaMA/top/.json").mock(
            return_value=httpx.Response(200, json=response),
        )

        settings = _mock_settings(reddit_subreddits="MachineLearning,LocalLLaMA")
        with patch("src.extractors.reddit.get_settings", return_value=settings):
            extractor = RedditExtractor()
            result = await extractor.extract()

        assert len(result) == 1
        assert result[0].metadata["post_id"] == "dup1"

    @respx.mock
    async def test_self_post_uses_permalink(self):
        """Self posts should use reddit permalink as URL."""
        posts = [
            _make_post(
                "self1",
                "Ask ML: Best practices?",
                is_self=True,
                selftext="What are the best practices for fine-tuning?",
                permalink="/r/MachineLearning/comments/self1/ask_ml/",
            ),
        ]
        respx.get(f"{BASE_URL}/r/MachineLearning/top/.json").mock(
            return_value=httpx.Response(200, json=_reddit_response(posts)),
        )

        settings = _mock_settings()
        with patch("src.extractors.reddit.get_settings", return_value=settings):
            extractor = RedditExtractor()
            result = await extractor.extract()

        assert len(result) == 1
        assert result[0].url == "https://www.reddit.com/r/MachineLearning/comments/self1/ask_ml/"
        assert result[0].metadata["is_self"] is True

    @respx.mock
    async def test_link_post_uses_external_url(self):
        """Link posts should use the external URL."""
        posts = [
            _make_post(
                "link1",
                "New Paper Released",
                url="https://arxiv.org/abs/2401.12345",
                is_self=False,
            ),
        ]
        respx.get(f"{BASE_URL}/r/MachineLearning/top/.json").mock(
            return_value=httpx.Response(200, json=_reddit_response(posts)),
        )

        settings = _mock_settings()
        with patch("src.extractors.reddit.get_settings", return_value=settings):
            extractor = RedditExtractor()
            result = await extractor.extract()

        assert len(result) == 1
        assert result[0].url == "https://arxiv.org/abs/2401.12345"
        assert result[0].metadata["is_self"] is False

    @respx.mock
    async def test_empty_response_returns_empty_list(self):
        """An API response with no posts should return an empty list."""
        respx.get(f"{BASE_URL}/r/MachineLearning/top/.json").mock(
            return_value=httpx.Response(200, json=_reddit_response([])),
        )

        settings = _mock_settings()
        with patch("src.extractors.reddit.get_settings", return_value=settings):
            extractor = RedditExtractor()
            result = await extractor.extract()

        assert result == []

    @respx.mock
    async def test_http_error_returns_empty_list(self):
        """An HTTP 500 error should be handled gracefully, returning []."""
        respx.get(f"{BASE_URL}/r/MachineLearning/top/.json").mock(
            return_value=httpx.Response(500, text="Internal Server Error"),
        )

        settings = _mock_settings()
        with patch("src.extractors.reddit.get_settings", return_value=settings):
            extractor = RedditExtractor()
            result = await extractor.extract()

        assert result == []

    @respx.mock
    async def test_network_error_returns_empty_list(self):
        """A network-level exception should be caught, returning []."""
        respx.get(f"{BASE_URL}/r/MachineLearning/top/.json").mock(
            side_effect=httpx.ConnectError("Connection refused"),
        )

        settings = _mock_settings()
        with patch("src.extractors.reddit.get_settings", return_value=settings):
            extractor = RedditExtractor()
            result = await extractor.extract()

        assert result == []

    @respx.mock
    async def test_item_metadata_contains_expected_keys(self):
        """Extracted items should carry expected metadata keys."""
        posts = [
            _make_post(
                "meta1",
                "Meta Test",
                score=300,
                num_comments=42,
                upvote_ratio=0.92,
                flair="Research",
                domain="arxiv.org",
            ),
        ]
        respx.get(f"{BASE_URL}/r/MachineLearning/top/.json").mock(
            return_value=httpx.Response(200, json=_reddit_response(posts)),
        )

        settings = _mock_settings()
        with patch("src.extractors.reddit.get_settings", return_value=settings):
            extractor = RedditExtractor()
            result = await extractor.extract()

        assert len(result) == 1
        meta = result[0].metadata
        assert meta["subreddit"] == "MachineLearning"
        assert meta["post_id"] == "meta1"
        assert meta["num_comments"] == 42
        assert meta["upvote_ratio"] == 0.92
        assert meta["is_self"] is False
        assert meta["flair"] == "Research"
        assert meta["domain"] == "arxiv.org"

    @respx.mock
    async def test_max_items_per_source_limits_output(self):
        """Result should be truncated to max_items_per_source."""
        posts = [_make_post(str(i), f"Post {i}", score=100 - i) for i in range(10)]
        respx.get(f"{BASE_URL}/r/MachineLearning/top/.json").mock(
            return_value=httpx.Response(200, json=_reddit_response(posts)),
        )

        settings = _mock_settings(max_items_per_source=3)
        with patch("src.extractors.reddit.get_settings", return_value=settings):
            extractor = RedditExtractor()
            result = await extractor.extract()

        assert len(result) == 3

    @respx.mock
    async def test_published_at_is_set(self):
        """Items should have published_at derived from created_utc."""
        posts = [_make_post("t1", "Dated Post", created_utc=1708000000.0)]
        respx.get(f"{BASE_URL}/r/MachineLearning/top/.json").mock(
            return_value=httpx.Response(200, json=_reddit_response(posts)),
        )

        settings = _mock_settings()
        with patch("src.extractors.reddit.get_settings", return_value=settings):
            extractor = RedditExtractor()
            result = await extractor.extract()

        assert result[0].published_at is not None
        assert result[0].published_at.year == 2024

    @respx.mock
    async def test_multiple_subreddits_fetched(self):
        """Each configured subreddit should be fetched."""
        post_ml = _make_post("ml1", "ML Post", subreddit="MachineLearning", score=200)
        post_llama = _make_post("ll1", "LLaMA Post", subreddit="LocalLLaMA", score=150)

        respx.get(f"{BASE_URL}/r/MachineLearning/top/.json").mock(
            return_value=httpx.Response(200, json=_reddit_response([post_ml])),
        )
        respx.get(f"{BASE_URL}/r/LocalLLaMA/top/.json").mock(
            return_value=httpx.Response(200, json=_reddit_response([post_llama])),
        )

        settings = _mock_settings(reddit_subreddits="MachineLearning,LocalLLaMA")
        with patch("src.extractors.reddit.get_settings", return_value=settings):
            extractor = RedditExtractor()
            result = await extractor.extract()

        assert len(result) == 2
        post_ids = {item.metadata["post_id"] for item in result}
        assert post_ids == {"ml1", "ll1"}


class TestEdgeCases:
    """Edge cases for RedditExtractor."""

    @respx.mock
    async def test_all_posts_stickied(self):
        """When every post is stickied, returns empty list."""
        posts = [
            _make_post("s1", "Weekly Discussion", stickied=True, score=10),
            _make_post("s2", "Monthly Showcase", stickied=True, score=5),
        ]
        respx.get(f"{BASE_URL}/r/MachineLearning/top/.json").mock(
            return_value=httpx.Response(200, json=_reddit_response(posts)),
        )

        settings = _mock_settings()
        with patch("src.extractors.reddit.get_settings", return_value=settings):
            result = await RedditExtractor().extract()

        assert result == []

    @respx.mock
    async def test_subreddit_403_returns_empty(self):
        """Private subreddit (403) is handled gracefully."""
        respx.get(f"{BASE_URL}/r/MachineLearning/top/.json").mock(
            return_value=httpx.Response(403, text="Forbidden"),
        )

        settings = _mock_settings()
        with patch("src.extractors.reddit.get_settings", return_value=settings):
            result = await RedditExtractor().extract()

        assert result == []

    @respx.mock
    async def test_post_missing_id_skipped(self):
        """Post without an id field is skipped."""
        posts = [_make_post("", "No ID Post", score=100)]
        posts[0]["id"] = ""
        respx.get(f"{BASE_URL}/r/MachineLearning/top/.json").mock(
            return_value=httpx.Response(200, json=_reddit_response(posts)),
        )

        settings = _mock_settings()
        with patch("src.extractors.reddit.get_settings", return_value=settings):
            result = await RedditExtractor().extract()

        # post_id="" is falsy, so `if not post_id: continue` skips it
        assert result == []

    @respx.mock
    async def test_timeout_returns_empty(self):
        """Network timeout is handled gracefully."""
        respx.get(f"{BASE_URL}/r/MachineLearning/top/.json").mock(
            side_effect=httpx.TimeoutException("read timeout"),
        )

        settings = _mock_settings()
        with patch("src.extractors.reddit.get_settings", return_value=settings):
            result = await RedditExtractor().extract()

        assert result == []

    @respx.mock
    async def test_missing_data_key_returns_empty(self):
        """Response without 'data' key returns empty list."""
        respx.get(f"{BASE_URL}/r/MachineLearning/top/.json").mock(
            return_value=httpx.Response(200, json={"kind": "Listing"}),
        )

        settings = _mock_settings()
        with patch("src.extractors.reddit.get_settings", return_value=settings):
            result = await RedditExtractor().extract()

        assert result == []

    @respx.mock
    async def test_post_score_zero_included(self):
        """Posts with score=0 are included (filtering is validator's job)."""
        posts = [_make_post("zero1", "Zero Score Post", score=0)]
        respx.get(f"{BASE_URL}/r/MachineLearning/top/.json").mock(
            return_value=httpx.Response(200, json=_reddit_response(posts)),
        )

        settings = _mock_settings()
        with patch("src.extractors.reddit.get_settings", return_value=settings):
            result = await RedditExtractor().extract()

        assert len(result) == 1
        assert result[0].score == 0
        assert result[0].metadata["post_id"] == "zero1"
