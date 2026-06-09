"""Tests for src.extractors.hackernews_leading -- HackerNewsLeadingExtractor.

The leading-indicator extractor polls the HN newest-first firehose
(`search_by_date`) and keeps only submissions whose linked URL is on an
allowlist of authoritative AI domains -- ingesting them at 0 points, before
they accumulate keyword-search traction. The domain replaces the points gate.
"""

from __future__ import annotations

from unittest.mock import patch

import httpx
import respx

from src.core.metrics import extractor_errors_total
from src.extractors.base import ExtractedItem
from src.extractors.hackernews_leading import BASE_URL, HackerNewsLeadingExtractor


def _error_count() -> float:
    return extractor_errors_total.labels(source="hackernews_leading")._value.get()


def _make_hit(
    object_id: str = "123",
    title: str = "Test AI Story",
    url: str | None = "https://example.com",
    points: int = 0,
    num_comments: int = 0,
    author: str = "testuser",
    created_at_i: int = 1708000000,
) -> dict:
    """Build a single HN Algolia hit dict (search_by_date shape)."""
    return {
        "objectID": object_id,
        "title": title,
        "url": url,
        "points": points,
        "num_comments": num_comments,
        "author": author,
        "created_at_i": created_at_i,
    }


def _algolia_response(hits: list[dict]) -> dict:
    return {
        "hits": hits,
        "nbHits": len(hits),
        "page": 0,
        "nbPages": 1,
        "hitsPerPage": 100,
    }


def _mock_settings(**overrides):
    from src.core.config import Settings

    defaults = {
        "hn_authoritative_domains": "anthropic.com,openai.com,deepmind.google",
        "max_items_per_source": 50,
        "extraction_since_hours": 24,
        "enabled_sources": "hackernews_leading",
    }
    defaults.update(overrides)
    return Settings(**defaults)


class TestSourceName:
    def test_source_name_is_distinct_lane(self):
        """source_name identifies the leading lane for metrics/scheduling."""
        assert HackerNewsLeadingExtractor().source_name == "hackernews_leading"


class TestDomainFiltering:
    """The core behavior: keep authoritative domains at 0 points, drop the rest."""

    @respx.mock
    async def test_keeps_authoritative_domain_at_zero_points(self):
        """An anthropic.com submission with 0 points is kept (domain is the gate)."""
        hits = [
            _make_hit("1", "Claude Fable 5", "https://www.anthropic.com/news/fable-5", 0),
        ]
        respx.get(BASE_URL).mock(return_value=httpx.Response(200, json=_algolia_response(hits)))

        settings = _mock_settings()
        with patch("src.extractors.hackernews_leading.get_settings", return_value=settings):
            result = await HackerNewsLeadingExtractor().extract()

        assert len(result) == 1
        assert result[0].url == "https://www.anthropic.com/news/fable-5"

    @respx.mock
    async def test_drops_non_authoritative_domain_even_with_high_points(self):
        """A high-points story on a non-allowlisted domain is dropped."""
        hits = [
            _make_hit("1", "Random viral post", "https://medium.com/some-post", 1500),
        ]
        respx.get(BASE_URL).mock(return_value=httpx.Response(200, json=_algolia_response(hits)))

        settings = _mock_settings()
        with patch("src.extractors.hackernews_leading.get_settings", return_value=settings):
            result = await HackerNewsLeadingExtractor().extract()

        assert result == []

    @respx.mock
    async def test_matches_subdomains(self):
        """Subdomains of an allowlisted host are kept (suffix match)."""
        hits = [
            _make_hit("1", "System Card", "https://www-cdn.anthropic.com/card.pdf", 0),
        ]
        respx.get(BASE_URL).mock(return_value=httpx.Response(200, json=_algolia_response(hits)))

        settings = _mock_settings()
        with patch("src.extractors.hackernews_leading.get_settings", return_value=settings):
            result = await HackerNewsLeadingExtractor().extract()

        assert len(result) == 1
        assert result[0].url == "https://www-cdn.anthropic.com/card.pdf"

    @respx.mock
    async def test_matches_trailing_dot_fqdn(self):
        """A fully-qualified hostname with a trailing dot still matches."""
        hits = [_make_hit("1", "X", "https://anthropic.com./news", 0)]
        respx.get(BASE_URL).mock(return_value=httpx.Response(200, json=_algolia_response(hits)))

        settings = _mock_settings(hn_authoritative_domains="anthropic.com")
        with patch("src.extractors.hackernews_leading.get_settings", return_value=settings):
            result = await HackerNewsLeadingExtractor().extract()

        assert len(result) == 1

    @respx.mock
    async def test_does_not_match_lookalike_domain(self):
        """A domain that merely ends with the allowlisted string but is a different
        registrable domain (e.g. notanthropic.com) must NOT match."""
        hits = [
            _make_hit("1", "Phishy", "https://notanthropic.com/news", 0),
            _make_hit("2", "Evil", "https://anthropic.com.evil.io/x", 0),
        ]
        respx.get(BASE_URL).mock(return_value=httpx.Response(200, json=_algolia_response(hits)))

        settings = _mock_settings()
        with patch("src.extractors.hackernews_leading.get_settings", return_value=settings):
            result = await HackerNewsLeadingExtractor().extract()

        assert result == []

    @respx.mock
    async def test_mixed_batch_keeps_only_authoritative(self):
        """In a realistic firehose batch, only allowlisted-domain items survive."""
        hits = [
            _make_hit("1", "Noise", "https://news.ycombinator.com/item?id=1", 200),
            _make_hit("2", "OpenAI launch", "https://openai.com/index/new-model", 0),
            _make_hit("3", "Blog", "https://someblog.dev/post", 50),
            _make_hit("4", "DeepMind", "https://deepmind.google/research/x", 1),
        ]
        respx.get(BASE_URL).mock(return_value=httpx.Response(200, json=_algolia_response(hits)))

        settings = _mock_settings()
        with patch("src.extractors.hackernews_leading.get_settings", return_value=settings):
            result = await HackerNewsLeadingExtractor().extract()

        urls = {item.url for item in result}
        assert urls == {
            "https://openai.com/index/new-model",
            "https://deepmind.google/research/x",
        }


class TestTargetedQuerying:
    """Approach B: one targeted URL-scoped query per domain, deduped by story_id.

    A pure firehose caps at the newest ~100 stories (~2h); a targeted
    `restrictSearchableAttributes=url` query returns a domain's items across the
    whole lookback window, which is what makes recall robust.
    """

    @respx.mock
    async def test_issues_one_url_scoped_query_per_domain(self):
        captured: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            captured.append(request)
            return httpx.Response(200, json=_algolia_response([]))

        respx.get(BASE_URL).mock(side_effect=handler)

        settings = _mock_settings(
            hn_authoritative_domains="anthropic.com,openai.com,deepmind.google"
        )
        with patch("src.extractors.hackernews_leading.get_settings", return_value=settings):
            await HackerNewsLeadingExtractor().extract()

        assert len(captured) == 3
        for req in captured:
            assert req.url.params.get("restrictSearchableAttributes") == "url"
        queried = {req.url.params.get("query") for req in captured}
        assert queried == {"anthropic.com", "openai.com", "deepmind.google"}

    @respx.mock
    async def test_dedupes_same_story_across_domain_queries(self):
        """The same story surfaced by multiple domain queries is kept once."""
        hit = _make_hit("777", "Shared", "https://www.anthropic.com/news/z", 0)
        respx.get(BASE_URL).mock(return_value=httpx.Response(200, json=_algolia_response([hit])))

        settings = _mock_settings(hn_authoritative_domains="anthropic.com,openai.com")
        with patch("src.extractors.hackernews_leading.get_settings", return_value=settings):
            result = await HackerNewsLeadingExtractor().extract()

        assert len(result) == 1
        assert result[0].metadata["story_id"] == "777"

    @respx.mock
    async def test_one_failing_domain_does_not_kill_the_rest(self):
        """A per-domain request error is isolated; other domains still yield items."""
        calls = {"n": 0}

        def handler(request: httpx.Request) -> httpx.Response:
            calls["n"] += 1
            if calls["n"] == 1:
                return httpx.Response(500, text="boom")
            return httpx.Response(
                200,
                json=_algolia_response([_make_hit("1", "OK", "https://openai.com/x", 0)]),
            )

        respx.get(BASE_URL).mock(side_effect=handler)

        settings = _mock_settings(hn_authoritative_domains="anthropic.com,openai.com")
        with patch("src.extractors.hackernews_leading.get_settings", return_value=settings):
            result = await HackerNewsLeadingExtractor().extract()

        assert len(result) == 1


class TestItemShape:
    @respx.mock
    async def test_items_emit_source_hackernews(self):
        """Items are stored under the unified 'hackernews' source, not the lane name."""
        hits = [_make_hit("1", "X", "https://openai.com/x", 0)]
        respx.get(BASE_URL).mock(return_value=httpx.Response(200, json=_algolia_response(hits)))

        settings = _mock_settings()
        with patch("src.extractors.hackernews_leading.get_settings", return_value=settings):
            result = await HackerNewsLeadingExtractor().extract()

        assert all(isinstance(i, ExtractedItem) for i in result)
        assert all(i.source == "hackernews" for i in result)

    @respx.mock
    async def test_metadata_marks_leading_lane(self):
        """Metadata carries lane='leading', domain, story_id, hn_url for observability."""
        hits = [_make_hit("555", "X", "https://www.anthropic.com/news/y", 0, num_comments=3)]
        respx.get(BASE_URL).mock(return_value=httpx.Response(200, json=_algolia_response(hits)))

        settings = _mock_settings()
        with patch("src.extractors.hackernews_leading.get_settings", return_value=settings):
            result = await HackerNewsLeadingExtractor().extract()

        meta = result[0].metadata
        assert meta["lane"] == "leading"
        assert meta["domain"] == "www.anthropic.com"
        assert meta["story_id"] == "555"
        assert meta["hn_url"] == "https://news.ycombinator.com/item?id=555"
        assert meta["num_comments"] == 3

    @respx.mock
    async def test_published_at_derived_from_created_at(self):
        hits = [_make_hit("1", "X", "https://openai.com/x", 0, created_at_i=1708000000)]
        respx.get(BASE_URL).mock(return_value=httpx.Response(200, json=_algolia_response(hits)))

        settings = _mock_settings()
        with patch("src.extractors.hackernews_leading.get_settings", return_value=settings):
            result = await HackerNewsLeadingExtractor().extract()

        assert result[0].published_at is not None
        assert result[0].published_at.year == 2024


class TestConfigAndErrors:
    @respx.mock
    async def test_empty_allowlist_returns_empty(self):
        """With no authoritative domains configured, the lane is a no-op."""
        hits = [_make_hit("1", "X", "https://openai.com/x", 0)]
        respx.get(BASE_URL).mock(return_value=httpx.Response(200, json=_algolia_response(hits)))

        settings = _mock_settings(hn_authoritative_domains="")
        with patch("src.extractors.hackernews_leading.get_settings", return_value=settings):
            result = await HackerNewsLeadingExtractor().extract()

        assert result == []

    @respx.mock
    async def test_skips_hits_without_url(self):
        """Hits with no url (Ask HN etc.) cannot be domain-matched and are skipped."""
        hit = _make_hit("1", "Ask HN", None, 0)
        respx.get(BASE_URL).mock(return_value=httpx.Response(200, json=_algolia_response([hit])))

        settings = _mock_settings()
        with patch("src.extractors.hackernews_leading.get_settings", return_value=settings):
            result = await HackerNewsLeadingExtractor().extract()

        assert result == []

    @respx.mock
    async def test_http_error_returns_empty(self):
        respx.get(BASE_URL).mock(return_value=httpx.Response(500, text="boom"))

        settings = _mock_settings()
        with patch("src.extractors.hackernews_leading.get_settings", return_value=settings):
            result = await HackerNewsLeadingExtractor().extract()

        assert result == []

    @respx.mock
    async def test_network_error_returns_empty(self):
        respx.get(BASE_URL).mock(side_effect=httpx.ConnectError("refused"))

        settings = _mock_settings()
        with patch("src.extractors.hackernews_leading.get_settings", return_value=settings):
            result = await HackerNewsLeadingExtractor().extract()

        assert result == []

    @respx.mock
    async def test_all_domains_failing_increments_error_metric(self):
        """If every domain query fails, the extractor-error metric fires (alerting)."""
        respx.get(BASE_URL).mock(return_value=httpx.Response(500, text="boom"))

        settings = _mock_settings(hn_authoritative_domains="anthropic.com,openai.com")
        before = _error_count()
        with patch("src.extractors.hackernews_leading.get_settings", return_value=settings):
            result = await HackerNewsLeadingExtractor().extract()

        assert result == []
        assert _error_count() == before + 1

    @respx.mock
    async def test_legitimate_empty_does_not_increment_error_metric(self):
        """A normal poll that simply finds no authoritative items is NOT an error."""
        respx.get(BASE_URL).mock(return_value=httpx.Response(200, json=_algolia_response([])))

        settings = _mock_settings(hn_authoritative_domains="anthropic.com,openai.com")
        before = _error_count()
        with patch("src.extractors.hackernews_leading.get_settings", return_value=settings):
            result = await HackerNewsLeadingExtractor().extract()

        assert result == []
        assert _error_count() == before
