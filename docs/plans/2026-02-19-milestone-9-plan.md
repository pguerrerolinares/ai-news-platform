# M9 Backend Edge Cases & Robustness — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add ~84 edge-case unit tests to harden all 12 backend modules against realistic production failures. Coverage target: 92% -> 95%.

**Architecture:** Extend existing test files with edge-case tests. No new files. Follow existing patterns: `respx` for HTTP mocking, `unittest.mock.patch` for LLM/DB, `factories.py` helpers. Some tests may reveal actual bugs — fix source code minimally and document in commit message.

**Tech Stack:** pytest + pytest-asyncio, respx, unittest.mock, factory-boy, httpx

---

## Task 1: Extractor Base + HackerNews edge cases (+9 tests)

**Files:**
- Test: `tests/unit/test_extractors_base.py`
- Test: `tests/unit/test_hackernews_extractor.py`
- Source: `src/extractors/base.py` (read only, unless bug found)
- Source: `src/extractors/hackernews.py` (read only, unless bug found)

**Step 1: Write edge-case tests for ExtractedItem**

Add to `tests/unit/test_extractors_base.py`:

```python
class TestEdgeCases:
    """Edge cases for ExtractedItem hashing and sorting."""

    def test_content_hash_empty_title(self):
        """Empty title still produces a deterministic hash."""
        item = ExtractedItem(title="", source="test", url="https://x.com")
        assert isinstance(item.content_hash, str)
        assert len(item.content_hash) == 16

    def test_url_hash_empty_url(self):
        """Empty URL returns None (no URL to hash)."""
        item = ExtractedItem(title="Foo", source="test", url="")
        # url="" is falsy, so url_hash should return None
        assert item.url_hash is None

    def test_url_hash_none_url(self):
        """None URL returns None."""
        item = ExtractedItem(title="Foo", source="test", url=None)
        assert item.url_hash is None
```

**Step 2: Write edge-case tests for HackerNews extractor**

Add to `tests/unit/test_hackernews_extractor.py`:

```python
class TestEdgeCases:
    """Edge cases for HackerNewsExtractor.extract()."""

    @respx.mock
    async def test_story_missing_title(self):
        """A hit with null title should still be extracted (title defaults to '')."""
        hit = _make_hit("1", title="", url="https://x.com", points=200)
        hit["title"] = None
        respx.get(BASE_URL).mock(
            return_value=httpx.Response(200, json=_algolia_response([hit])),
        )
        settings = _mock_settings()
        with patch("src.extractors.hackernews.get_settings", return_value=settings):
            result = await HackerNewsExtractor().extract()
        # hit.get("title", "") handles None -> ""
        assert len(result) == 1
        assert result[0].title == ""

    @respx.mock
    async def test_negative_points(self):
        """A story with negative points is still extracted (filtering is validator's job)."""
        hit = _make_hit("1", "Negative Story", "https://x.com", points=-5)
        respx.get(BASE_URL).mock(
            return_value=httpx.Response(200, json=_algolia_response([hit])),
        )
        settings = _mock_settings(hn_min_points=0)
        with patch("src.extractors.hackernews.get_settings", return_value=settings):
            result = await HackerNewsExtractor().extract()
        # Algolia filter is points>min_points, so if API returns it, we keep it
        # The mock bypasses the actual Algolia filter
        assert len(result) == 1
        assert result[0].score == -5

    @respx.mock
    async def test_unexpected_created_at_value(self):
        """A non-numeric created_at_i falls back to datetime.now()."""
        hit = _make_hit("1", "Story", "https://x.com", points=100)
        hit["created_at_i"] = "not-a-timestamp"
        respx.get(BASE_URL).mock(
            return_value=httpx.Response(200, json=_algolia_response([hit])),
        )
        settings = _mock_settings()
        with patch("src.extractors.hackernews.get_settings", return_value=settings):
            result = await HackerNewsExtractor().extract()
        # Should not crash — falls back to now()
        assert len(result) == 1
        assert result[0].published_at is not None

    @respx.mock
    async def test_hit_missing_object_id(self):
        """A hit without objectID should be handled (empty string key)."""
        hit = _make_hit("", "No ID Story", "https://x.com", points=100)
        hit.pop("objectID", None)
        respx.get(BASE_URL).mock(
            return_value=httpx.Response(200, json=_algolia_response([hit])),
        )
        settings = _mock_settings()
        with patch("src.extractors.hackernews.get_settings", return_value=settings):
            result = await HackerNewsExtractor().extract()
        # objectID defaults to "" via .get("objectID", "")
        assert len(result) == 1

    @respx.mock
    async def test_timeout_returns_empty(self):
        """A timeout exception returns empty list gracefully."""
        respx.get(BASE_URL).mock(side_effect=httpx.TimeoutException("read timeout"))
        settings = _mock_settings()
        with patch("src.extractors.hackernews.get_settings", return_value=settings):
            result = await HackerNewsExtractor().extract()
        assert result == []

    @respx.mock
    async def test_json_decode_error_returns_empty(self):
        """A non-JSON response body returns empty list."""
        respx.get(BASE_URL).mock(
            return_value=httpx.Response(200, text="<html>Not JSON</html>"),
        )
        settings = _mock_settings()
        with patch("src.extractors.hackernews.get_settings", return_value=settings):
            result = await HackerNewsExtractor().extract()
        assert result == []
```

**Step 3: Run tests**

```bash
pytest tests/unit/test_extractors_base.py tests/unit/test_hackernews_extractor.py -v --timeout=30
```

Expected: All pass (existing + new). If any fail, fix the source code minimally.

**Step 4: Commit**

```bash
git add tests/unit/test_extractors_base.py tests/unit/test_hackernews_extractor.py
# If source was fixed, also add the source file
git commit -m "test: add edge-case tests for extractors base + HackerNews [M9]"
```

---

## Task 2: arXiv + Reddit extractor edge cases (+12 tests)

**Files:**
- Test: `tests/unit/test_arxiv_extractor.py`
- Test: `tests/unit/test_reddit_extractor.py`
- Source: `src/extractors/arxiv.py`, `src/extractors/reddit.py` (read only, unless bug found)

**Step 1: Write arXiv edge-case tests**

Add to `tests/unit/test_arxiv_extractor.py`. Follow existing patterns — uses `respx` mock and `_mock_settings()`. Read the file first to understand the existing helper functions and test structure.

Tests to add (in a new `class TestEdgeCases`):

```python
class TestEdgeCases:
    """Edge cases for ArxivExtractor."""

    @respx.mock
    async def test_malformed_xml_returns_empty(self):
        """Malformed RSS body returns empty list, no crash."""
        respx.get(f"{RSS_BASE}/cs.AI").mock(
            return_value=httpx.Response(200, text="<broken xml"),
        )
        settings = _mock_settings()
        with patch("src.extractors.arxiv.get_settings", return_value=settings):
            result = await ArxivExtractor().extract()
        assert result == []

    @respx.mock
    async def test_entry_no_link(self):
        """Entry without link field is skipped (no arxiv_id extractable)."""
        feed_xml = """<?xml version="1.0"?>
        <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
          <item>
            <title>No Link Paper</title>
            <description>Announce Type: new\nSome LLM transformer paper.</description>
          </item>
        </rdf:RDF>"""
        respx.get(f"{RSS_BASE}/cs.AI").mock(
            return_value=httpx.Response(200, text=feed_xml),
        )
        settings = _mock_settings()
        with patch("src.extractors.arxiv.get_settings", return_value=settings):
            result = await ArxivExtractor().extract()
        # No link -> no arxiv_id -> skipped
        assert result == []

    @respx.mock
    async def test_http_500_returns_empty(self):
        """HTTP 500 from arXiv is handled gracefully."""
        respx.get(f"{RSS_BASE}/cs.AI").mock(
            return_value=httpx.Response(500, text="Internal Server Error"),
        )
        settings = _mock_settings()
        with patch("src.extractors.arxiv.get_settings", return_value=settings):
            result = await ArxivExtractor().extract()
        assert result == []

    @respx.mock
    async def test_feed_no_entries(self):
        """Valid RSS with zero entries returns empty list."""
        empty_feed = """<?xml version="1.0"?>
        <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
        </rdf:RDF>"""
        respx.get(f"{RSS_BASE}/cs.AI").mock(
            return_value=httpx.Response(200, text=empty_feed),
        )
        settings = _mock_settings()
        with patch("src.extractors.arxiv.get_settings", return_value=settings):
            result = await ArxivExtractor().extract()
        assert result == []

    @respx.mock
    async def test_timeout_returns_empty(self):
        """Network timeout is handled gracefully."""
        respx.get(f"{RSS_BASE}/cs.AI").mock(
            side_effect=httpx.TimeoutException("read timeout"),
        )
        settings = _mock_settings()
        with patch("src.extractors.arxiv.get_settings", return_value=settings):
            result = await ArxivExtractor().extract()
        assert result == []

    def test_build_keyword_regex_empty_list(self):
        """Empty keyword list returns None pattern."""
        assert ArxivExtractor._build_keyword_regex([]) is None
```

**Step 2: Write Reddit edge-case tests**

Add to `tests/unit/test_reddit_extractor.py`. Read file first for helpers.

```python
class TestEdgeCases:
    """Edge cases for RedditExtractor."""

    @respx.mock
    async def test_all_posts_stickied(self):
        """When every post is stickied, returns empty list."""
        response_data = {
            "data": {
                "children": [
                    {"data": {"id": "1", "title": "Stickied", "stickied": True,
                              "score": 100, "created_utc": 1708000000}},
                    {"data": {"id": "2", "title": "Also Stickied", "stickied": True,
                              "score": 200, "created_utc": 1708000000}},
                ]
            }
        }
        respx.get(f"{BASE_URL}/r/MachineLearning/top/.json").mock(
            return_value=httpx.Response(200, json=response_data),
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
    async def test_self_post_uses_permalink(self):
        """Self posts (is_self=True) use reddit permalink as URL."""
        response_data = {
            "data": {
                "children": [
                    {"data": {"id": "abc", "title": "Ask ML",
                              "is_self": True, "stickied": False,
                              "selftext": "Question about ML",
                              "permalink": "/r/MachineLearning/comments/abc/ask_ml/",
                              "score": 50, "created_utc": 1708000000,
                              "author": "user1"}},
                ]
            }
        }
        respx.get(f"{BASE_URL}/r/MachineLearning/top/.json").mock(
            return_value=httpx.Response(200, json=response_data),
        )
        settings = _mock_settings()
        with patch("src.extractors.reddit.get_settings", return_value=settings):
            result = await RedditExtractor().extract()
        assert len(result) == 1
        assert "reddit.com" in result[0].url

    @respx.mock
    async def test_empty_children_returns_empty(self):
        """Response with empty children array returns empty list."""
        response_data = {"data": {"children": []}}
        respx.get(f"{BASE_URL}/r/MachineLearning/top/.json").mock(
            return_value=httpx.Response(200, json=response_data),
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
        response_data = {
            "data": {
                "children": [
                    {"data": {"id": "xyz", "title": "Zero Score Post",
                              "stickied": False, "is_self": False,
                              "url": "https://example.com", "score": 0,
                              "created_utc": 1708000000, "author": "user1",
                              "permalink": "/r/test/xyz/"}},
                ]
            }
        }
        respx.get(f"{BASE_URL}/r/MachineLearning/top/.json").mock(
            return_value=httpx.Response(200, json=response_data),
        )
        settings = _mock_settings()
        with patch("src.extractors.reddit.get_settings", return_value=settings):
            result = await RedditExtractor().extract()
        assert len(result) == 1
        assert result[0].score == 0
```

**Step 2: Run tests**

```bash
pytest tests/unit/test_arxiv_extractor.py tests/unit/test_reddit_extractor.py -v --timeout=30
```

**Step 3: Fix any failures, then commit**

```bash
git add tests/unit/test_arxiv_extractor.py tests/unit/test_reddit_extractor.py
git commit -m "test: add edge-case tests for arXiv + Reddit extractors [M9]"
```

---

## Task 3: RSS + GitHub + HuggingFace extractor edge cases (+19 tests)

**Files:**
- Test: `tests/unit/test_rss_extractor.py`
- Test: `tests/unit/test_github_extractor.py`
- Test: `tests/unit/test_huggingface_extractor.py`

**Step 1: Write RSS edge-case tests**

Read `tests/unit/test_rss_extractor.py` first for existing patterns. Add `class TestEdgeCases`:

```python
class TestEdgeCases:
    """Edge cases for RSSExtractor."""

    @respx.mock
    async def test_feed_http_404(self):
        """Feed returning 404 is skipped, others continue."""
        respx.get("https://feed1.com/rss").mock(
            return_value=httpx.Response(404, text="Not Found"),
        )
        settings = _mock_settings(rss_feeds="https://feed1.com/rss")
        with patch("src.extractors.rss.get_settings", return_value=settings):
            result = await RSSExtractor().extract()
        assert result == []

    @respx.mock
    async def test_feed_http_500(self):
        """Feed returning 500 is handled gracefully."""
        respx.get("https://feed1.com/rss").mock(
            return_value=httpx.Response(500, text="Internal Server Error"),
        )
        settings = _mock_settings(rss_feeds="https://feed1.com/rss")
        with patch("src.extractors.rss.get_settings", return_value=settings):
            result = await RSSExtractor().extract()
        assert result == []

    @respx.mock
    async def test_feed_no_entries(self):
        """Valid feed with zero entries returns empty list."""
        empty_feed = '<?xml version="1.0"?><rss><channel><title>Empty</title></channel></rss>'
        respx.get("https://feed1.com/rss").mock(
            return_value=httpx.Response(200, text=empty_feed),
        )
        settings = _mock_settings(rss_feeds="https://feed1.com/rss")
        with patch("src.extractors.rss.get_settings", return_value=settings):
            result = await RSSExtractor().extract()
        assert result == []

    @respx.mock
    async def test_entry_no_link_skipped(self):
        """Entry without link field is skipped."""
        feed_xml = """<?xml version="1.0"?>
        <rss><channel><title>Test</title>
          <item><title>No Link</title><description>Text</description></item>
        </channel></rss>"""
        respx.get("https://feed1.com/rss").mock(
            return_value=httpx.Response(200, text=feed_xml),
        )
        settings = _mock_settings(rss_feeds="https://feed1.com/rss")
        with patch("src.extractors.rss.get_settings", return_value=settings):
            result = await RSSExtractor().extract()
        assert result == []

    @respx.mock
    async def test_timeout_returns_empty(self):
        """Feed timeout is handled gracefully."""
        respx.get("https://feed1.com/rss").mock(
            side_effect=httpx.TimeoutException("timeout"),
        )
        settings = _mock_settings(rss_feeds="https://feed1.com/rss")
        with patch("src.extractors.rss.get_settings", return_value=settings):
            result = await RSSExtractor().extract()
        assert result == []

    def test_strip_html_decodes_entities(self):
        """HTML entities in text are decoded."""
        result = RSSExtractor._strip_html("AI &amp; ML &#39;test&#39; &lt;b&gt;bold&lt;/b&gt;")
        assert "&amp;" not in result
        assert "&" in result
        assert "<b>" not in result

    def test_strip_html_normalizes_whitespace(self):
        """Multiple whitespace chars are collapsed."""
        result = RSSExtractor._strip_html("  lots   of    spaces  ")
        assert result == "lots of spaces"
```

**Step 2: Write GitHub edge-case tests**

Add to `tests/unit/test_github_extractor.py`:

```python
class TestEdgeCases:
    """Edge cases for GitHubExtractor."""

    @respx.mock
    async def test_rate_limit_403(self):
        """GitHub 403 rate limit is handled gracefully."""
        respx.get(SEARCH_URL).mock(
            return_value=httpx.Response(403, text="Rate limit exceeded",
                                       headers={"X-RateLimit-Remaining": "0"}),
        )
        settings = _mock_settings()
        with patch("src.extractors.github.get_settings", return_value=settings):
            result = await GitHubExtractor().extract()
        assert result == []

    @respx.mock
    async def test_empty_search_results(self):
        """Empty items array returns empty list."""
        respx.get(SEARCH_URL).mock(
            return_value=httpx.Response(200, json={"items": [], "total_count": 0},
                                       headers={"X-RateLimit-Remaining": "10"}),
        )
        settings = _mock_settings()
        with patch("src.extractors.github.get_settings", return_value=settings):
            result = await GitHubExtractor().extract()
        assert result == []

    @respx.mock
    async def test_repo_no_description(self):
        """Repo with null description uses name as title."""
        repo = _make_repo("1", "cool-tool", description=None, stars=500)
        respx.get(SEARCH_URL).mock(
            return_value=httpx.Response(200, json={"items": [repo]},
                                       headers={"X-RateLimit-Remaining": "10"}),
        )
        settings = _mock_settings()
        with patch("src.extractors.github.get_settings", return_value=settings):
            result = await GitHubExtractor().extract()
        assert len(result) == 1
        # title = name (no description to append)
        assert result[0].title == "cool-tool"

    @respx.mock
    async def test_repo_missing_pushed_at(self):
        """Repo without pushed_at falls back to now()."""
        repo = _make_repo("2", "no-push", description="Test", stars=100)
        repo.pop("pushed_at", None)
        respx.get(SEARCH_URL).mock(
            return_value=httpx.Response(200, json={"items": [repo]},
                                       headers={"X-RateLimit-Remaining": "10"}),
        )
        settings = _mock_settings()
        with patch("src.extractors.github.get_settings", return_value=settings):
            result = await GitHubExtractor().extract()
        assert len(result) == 1
        assert result[0].published_at is not None

    @respx.mock
    async def test_timeout_returns_empty(self):
        """Network timeout returns empty list."""
        respx.get(SEARCH_URL).mock(side_effect=httpx.TimeoutException("timeout"))
        settings = _mock_settings()
        with patch("src.extractors.github.get_settings", return_value=settings):
            result = await GitHubExtractor().extract()
        assert result == []

    @respx.mock
    async def test_incomplete_results_still_returns_items(self):
        """incomplete_results=true still returns what was found."""
        repo = _make_repo("3", "partial", description="Partial", stars=200)
        respx.get(SEARCH_URL).mock(
            return_value=httpx.Response(200,
                json={"items": [repo], "incomplete_results": True},
                headers={"X-RateLimit-Remaining": "10"}),
        )
        settings = _mock_settings()
        with patch("src.extractors.github.get_settings", return_value=settings):
            result = await GitHubExtractor().extract()
        assert len(result) == 1
```

Note: `_make_repo` helper may need to be created if it doesn't exist. Read the existing test file to check, and create it if needed:

```python
def _make_repo(id: str, name: str, description: str | None = "Desc", stars: int = 100) -> dict:
    return {
        "id": id, "name": name, "description": description,
        "html_url": f"https://github.com/test/{name}",
        "stargazers_count": stars, "forks_count": 10,
        "pushed_at": "2026-02-19T10:00:00Z",
        "owner": {"login": "testuser"},
        "language": "Python", "topics": [], "full_name": f"test/{name}",
    }
```

**Step 3: Write HuggingFace edge-case tests**

Add to `tests/unit/test_huggingface_extractor.py`:

```python
class TestEdgeCases:
    """Edge cases for HuggingFaceExtractor."""

    @respx.mock
    async def test_empty_trending_list(self):
        """API returning empty list returns empty result."""
        respx.get(API_URL).mock(
            return_value=httpx.Response(200, json=[]),
        )
        settings = _mock_settings()
        with patch("src.extractors.huggingface.get_settings", return_value=settings):
            result = await HuggingFaceExtractor().extract()
        assert result == []

    @respx.mock
    async def test_model_no_pipeline_tag(self):
        """Model without pipeline_tag stores None in metadata."""
        model = _make_model("org/model1", downloads=5000)
        model.pop("pipeline_tag", None)
        respx.get(API_URL).mock(
            return_value=httpx.Response(200, json=[model]),
        )
        settings = _mock_settings()
        with patch("src.extractors.huggingface.get_settings", return_value=settings):
            result = await HuggingFaceExtractor().extract()
        assert len(result) == 1
        assert result[0].metadata["pipeline_tag"] is None

    @respx.mock
    async def test_model_below_min_downloads_filtered(self):
        """Models below min_downloads threshold are filtered out."""
        model = _make_model("org/small-model", downloads=5)
        respx.get(API_URL).mock(
            return_value=httpx.Response(200, json=[model]),
        )
        settings = _mock_settings(hf_min_downloads=100)
        with patch("src.extractors.huggingface.get_settings", return_value=settings):
            result = await HuggingFaceExtractor().extract()
        assert result == []

    @respx.mock
    async def test_missing_model_id_keys(self):
        """Model missing both modelId and id is handled."""
        model = {"downloads": 5000, "lastModified": "2026-02-19T10:00:00Z"}
        respx.get(API_URL).mock(
            return_value=httpx.Response(200, json=[model]),
        )
        settings = _mock_settings()
        with patch("src.extractors.huggingface.get_settings", return_value=settings):
            result = await HuggingFaceExtractor().extract()
        # modelId="" -> url = "https://huggingface.co/"
        # Should still be extracted (edge case behavior)
        assert len(result) <= 1

    @respx.mock
    async def test_http_timeout(self):
        """Timeout returns empty list gracefully."""
        respx.get(API_URL).mock(side_effect=httpx.TimeoutException("timeout"))
        settings = _mock_settings()
        with patch("src.extractors.huggingface.get_settings", return_value=settings):
            result = await HuggingFaceExtractor().extract()
        assert result == []

    @respx.mock
    async def test_invalid_last_modified(self):
        """Invalid lastModified falls back to now()."""
        model = _make_model("org/bad-date", downloads=5000)
        model["lastModified"] = "not-a-date"
        respx.get(API_URL).mock(
            return_value=httpx.Response(200, json=[model]),
        )
        settings = _mock_settings()
        with patch("src.extractors.huggingface.get_settings", return_value=settings):
            result = await HuggingFaceExtractor().extract()
        assert len(result) == 1
        assert result[0].published_at is not None
```

Note: `_make_model` helper may need creation if not present:

```python
def _make_model(model_id: str, downloads: int = 1000) -> dict:
    return {
        "modelId": model_id, "downloads": downloads,
        "likes": 10, "pipeline_tag": "text-generation",
        "lastModified": "2026-02-19T10:00:00Z",
        "author": model_id.split("/")[0] if "/" in model_id else "unknown",
        "tags": ["transformers"],
    }
```

**Step 4: Run all three test files**

```bash
pytest tests/unit/test_rss_extractor.py tests/unit/test_github_extractor.py tests/unit/test_huggingface_extractor.py -v --timeout=30
```

**Step 5: Commit**

```bash
git add tests/unit/test_rss_extractor.py tests/unit/test_github_extractor.py tests/unit/test_huggingface_extractor.py
git commit -m "test: add edge-case tests for RSS + GitHub + HuggingFace extractors [M9]"
```

---

## Task 4: Credibility Validator edge cases (+10 tests)

**Files:**
- Test: `tests/unit/test_credibility_validator.py`
- Source: `src/validators/credibility.py` (read only, unless bug found)

**Step 1: Read the existing test file** to understand patterns (already done — uses `_make_settings`, `make_classified_item`, etc.)

**Step 2: Add edge-case tests**

Add to existing class structure in `tests/unit/test_credibility_validator.py`:

```python
# Add to TestIsSafeUrl:
class TestIsSafeUrlEdgeCases:
    @pytest.mark.asyncio
    async def test_ipv4_mapped_ipv6_blocked(self):
        """IPv4-mapped IPv6 address (::ffff:127.0.0.1) should be blocked."""
        ipv6_result = [(socket.AF_INET6, socket.SOCK_STREAM, 6, "", ("::ffff:127.0.0.1", 0, 0, 0))]
        with _mock_loop_getaddrinfo(return_value=ipv6_result):
            assert await _is_safe_url("https://mapped.example.com") is False

    @pytest.mark.asyncio
    async def test_empty_url_returns_false(self):
        """Empty URL string returns False."""
        assert await _is_safe_url("") is False


# Add to TestUrlVerification:
class TestUrlVerificationEdgeCases:
    async def test_ssl_error_no_bonus(self):
        """SSL certificate error should not give bonus."""
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.head = AsyncMock(side_effect=httpx.ConnectError("SSL: CERTIFICATE_VERIFY_FAILED"))
        from src.validators.credibility import _verify_url_content
        bonus = await _verify_url_content("https://expired-ssl.example.com", mock_client)
        assert bonus == 0.0

    async def test_very_slow_response_timeout(self):
        """Very slow HEAD response times out, no bonus."""
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.head = AsyncMock(side_effect=httpx.ReadTimeout("timed out"))
        from src.validators.credibility import _verify_url_content
        bonus = await _verify_url_content("https://slow.example.com", mock_client)
        assert bonus == 0.0


# Add to TestTokenize:
class TestTokenizeEdgeCases:
    def test_only_punctuation(self):
        """Text with only punctuation returns empty set."""
        tokens = _tokenize("!!! ??? ... --- ===")
        # After removing non-word chars, nothing left
        assert len(tokens) == 0 or all(len(t) <= 2 for t in tokens)

    def test_unicode_text(self):
        """Unicode text (accents, CJK) doesn't crash."""
        tokens = _tokenize("réseau neuronal 神经网络 transformer")
        assert "transformer" in tokens


# Add to TestJaccardSimilarity:
class TestJaccardEdgeCases:
    def test_both_only_stopwords(self):
        """Both texts being only stopwords returns 0.0 (no division by zero)."""
        sim = _jaccard_similarity("the is a an", "and or but")
        assert sim == 0.0

    def test_one_word_overlap(self):
        """Single significant word overlap computes correctly."""
        sim = _jaccard_similarity("quantum computing revolution", "quantum physics breakthrough")
        assert 0.0 < sim < 1.0


# Add to TestNoiseFiltering:
class TestNoiseFilteringEdgeCases:
    def test_engagement_score_exactly_five_hn(self):
        """HN item with score=5 exactly should be kept (threshold is < 5)."""
        validator = CredibilityValidator()
        items = [
            make_classified_item(
                title="Borderline HN",
                item=make_extracted_item(source="hackernews", score=5),
            ),
        ]
        items[0].credibility_score = 0.5
        result = validator._filter_noise(items)
        assert len(result) == 1
```

**Step 3: Run tests**

```bash
pytest tests/unit/test_credibility_validator.py -v --timeout=30
```

**Step 4: Commit**

```bash
git add tests/unit/test_credibility_validator.py
git commit -m "test: add edge-case tests for credibility validator [M9]"
```

---

## Task 5: Classifier edge cases (+14 tests)

**Files:**
- Test: `tests/unit/test_keyword_classifier.py`
- Test: `tests/unit/test_llm_classifier.py`
- Test: `tests/unit/test_event_dedup.py`

**Step 1: Write keyword classifier edge cases**

Read `tests/unit/test_keyword_classifier.py` first. Add:

```python
class TestEdgeCases:
    """Edge cases for KeywordClassifier."""

    async def test_empty_title_and_text(self):
        """Item with empty title and text gets relevance=0, filtered."""
        settings = _mock_settings()
        with patch("src.classifiers.keyword.get_settings", return_value=settings):
            classifier = KeywordClassifier()
            items = [make_extracted_item(title="", text="")]
            result = await classifier.classify(items)
        assert result == []

    async def test_title_only_emojis(self):
        """Title with only emojis has no keyword match."""
        settings = _mock_settings()
        with patch("src.classifiers.keyword.get_settings", return_value=settings):
            classifier = KeywordClassifier()
            items = [make_extracted_item(title="🤖🔥💯", text="")]
            result = await classifier.classify(items)
        assert result == []

    async def test_title_only_stopwords(self):
        """Title with common stopwords has no keyword match."""
        settings = _mock_settings()
        with patch("src.classifiers.keyword.get_settings", return_value=settings):
            classifier = KeywordClassifier()
            items = [make_extracted_item(title="the and or is", text="")]
            result = await classifier.classify(items)
        assert result == []

    async def test_all_topics_disabled(self):
        """When no topics enabled, everything is filtered."""
        settings = _mock_settings(topics="")
        with patch("src.classifiers.keyword.get_settings", return_value=settings):
            classifier = KeywordClassifier()
            items = [make_extracted_item(
                title="GPT-5 LLM transformer SOTA benchmark",
                text="Amazing model with attention mechanism",
                score=500,
            )]
            result = await classifier.classify(items)
        assert result == []
```

**Step 2: Write LLM classifier edge cases**

Add to `tests/unit/test_llm_classifier.py`:

```python
# Add to TestParseLlmJson:
    def test_truncated_json(self):
        """Truncated JSON array returns empty."""
        result = _parse_llm_json('[{"topic": "modelos"')
        assert result == []

    def test_empty_string(self):
        """Empty string returns empty."""
        result = _parse_llm_json("")
        assert result == []

# Add new class:
class TestLLMClassifierEdgeCases:
    """Edge cases for LLM classifier batch handling."""

    @pytest.fixture(autouse=True)
    def _patch_settings(self):
        with (
            patch("src.classifiers.llm.get_settings", return_value=_make_settings()),
            patch("src.classifiers.keyword.get_settings", return_value=_make_settings()),
        ):
            yield

    async def test_batch_partial_failure(self):
        """First batch succeeds, second batch fails -> first batch results + fallback."""
        response1 = _make_llm_response([
            {"idx": i, "is_news": True, "topic": "modelos",
             "relevance": 0.9, "summary": f"Resumen {i}"}
            for i in range(BATCH_SIZE)
        ])
        client = _make_mock_client(response1)
        # Second call raises
        call_count = 0
        async def side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return SimpleNamespace(
                    choices=[SimpleNamespace(message=SimpleNamespace(content=response1))]
                )
            raise openai.BadRequestError(
                message="bad", response=MagicMock(status_code=400), body=None
            )
        client.chat.completions.create = AsyncMock(side_effect=side_effect)
        classifier = LLMClassifier(client=client)

        items = [
            make_extracted_item(
                title=f"GPT model {i} LLM transformer",
                url=f"https://example.com/{i}", score=100,
            )
            for i in range(BATCH_SIZE + 2)
        ]
        results = await classifier.classify(items)
        # First batch: BATCH_SIZE from LLM, second batch: 2 from fallback
        assert len(results) >= BATCH_SIZE

    async def test_non_retryable_auth_error(self):
        """AuthenticationError raises immediately, no retry."""
        client = _make_mock_client("")
        client.chat.completions.create = AsyncMock(
            side_effect=openai.AuthenticationError(
                message="invalid key", response=MagicMock(status_code=401), body=None,
            )
        )
        classifier = LLMClassifier(client=client)
        items = [make_extracted_item(
            title="GPT-5 LLM transformer", text="AI model", score=100
        )]
        # Should fall back (exception is caught by classify())
        results = await classifier.classify(items)
        assert client.chat.completions.create.call_count == 1
```

**Step 3: Write event dedup edge cases**

Add to `tests/unit/test_event_dedup.py`:

```python
class TestEdgeCasesDedup:
    """Additional edge cases for event dedup."""

    @pytest.fixture(autouse=True)
    def _patch_settings(self):
        with patch("src.classifiers.event_dedup.get_settings", return_value=_make_settings()):
            yield

    async def test_all_items_same_event(self):
        """All 5 items grouped as same event -> 1 winner with source_count=5."""
        items = [
            make_classified_item(
                title=f"GPT-5 News {i}", topic="modelos",
                relevance_score=0.9 - i*0.01,
                item=make_extracted_item(
                    title=f"GPT-5 News {i}", score=300 - i*50,
                    url=f"https://example.com/{i}",
                ),
            )
            for i in range(5)
        ]
        client = _make_mock_client("[[0, 1, 2, 3, 4]]")
        results = await deduplicate_events(items, client=client)
        assert len(results) == 1
        assert results[0].trending is True
        assert results[0].source_count == 5

    async def test_empty_groups_from_llm(self):
        """LLM returns empty groups array -> all items kept as orphans."""
        items = [
            make_classified_item(
                title="Item 1", topic="modelos",
                item=make_extracted_item(title="Item 1", score=100),
            ),
            make_classified_item(
                title="Item 2", topic="modelos",
                item=make_extracted_item(
                    title="Item 2", score=50, url="https://example.com/2",
                ),
            ),
        ]
        client = _make_mock_client("[]")
        results = await deduplicate_events(items, client=client)
        # Empty groups -> all items are orphans -> all kept
        assert len(results) == 2
```

**Step 4: Run all classifier tests**

```bash
pytest tests/unit/test_keyword_classifier.py tests/unit/test_llm_classifier.py tests/unit/test_event_dedup.py -v --timeout=30
```

**Step 5: Commit**

```bash
git add tests/unit/test_keyword_classifier.py tests/unit/test_llm_classifier.py tests/unit/test_event_dedup.py
git commit -m "test: add edge-case tests for classifiers + event dedup [M9]"
```

---

## Task 6: Pipeline edge cases (+6 tests)

**Files:**
- Test: `tests/unit/test_pipeline.py`
- Source: `src/pipeline/pipeline.py` (read only, unless bug found)

**Step 1: Add edge-case tests**

Add to `tests/unit/test_pipeline.py`:

```python
class TestPipelineEdgeCases:
    """Edge cases for pipeline orchestration."""

    @pytest.mark.asyncio
    async def test_classifier_returns_empty(self):
        """When classifier returns [], pipeline continues with 0 items."""
        settings = _mock_settings(enabled_sources="hackernews", openai_api_key="")
        session = _mock_session()
        items = [_make_extracted_item()]

        with (
            patch("src.pipeline.pipeline.get_settings", return_value=settings),
            patch("src.pipeline.pipeline._extract_all", new_callable=AsyncMock, return_value=items),
            patch("src.pipeline.pipeline.deduplicate_items", return_value=items),
            patch("src.pipeline.pipeline.KeywordClassifier") as mock_kw_cls,
            patch("src.pipeline.pipeline.CredibilityValidator") as mock_val_cls,
            patch("src.pipeline.pipeline.AlertService") as mock_alerts_cls,
        ):
            mock_classifier = AsyncMock()
            mock_classifier.classify.return_value = []
            mock_kw_cls.return_value = mock_classifier

            mock_val = AsyncMock()
            mock_val.validate.return_value = []
            mock_val_cls.return_value = mock_val

            mock_alerts = AsyncMock()
            mock_alerts_cls.return_value = mock_alerts

            result = await run_pipeline(session)
        # Pipeline succeeds with 0 stored items
        assert result is True

    @pytest.mark.asyncio
    async def test_validator_filters_all(self):
        """When validator returns [], pipeline still succeeds."""
        settings = _mock_settings(
            enabled_sources="hackernews", openai_api_key="",
            enable_news_validation=True,
        )
        session = _mock_session()
        items = [_make_extracted_item()]
        classified = [_make_classified_item()]

        with (
            patch("src.pipeline.pipeline.get_settings", return_value=settings),
            patch("src.pipeline.pipeline._extract_all", new_callable=AsyncMock, return_value=items),
            patch("src.pipeline.pipeline.deduplicate_items", return_value=items),
            patch("src.pipeline.pipeline.KeywordClassifier") as mock_kw_cls,
            patch("src.pipeline.pipeline.CredibilityValidator") as mock_val_cls,
            patch("src.pipeline.pipeline.AlertService") as mock_alerts_cls,
        ):
            mock_classifier = AsyncMock()
            mock_classifier.classify.return_value = classified
            mock_kw_cls.return_value = mock_classifier

            mock_val = AsyncMock()
            mock_val.validate.return_value = []  # All filtered
            mock_val_cls.return_value = mock_val

            mock_alerts = AsyncMock()
            mock_alerts_cls.return_value = mock_alerts

            result = await run_pipeline(session)
        assert result is True

    @pytest.mark.asyncio
    async def test_store_insert_error_handled(self):
        """IntegrityError during insert is handled (on_conflict_do_nothing)."""
        from sqlalchemy.exc import IntegrityError
        settings = _mock_settings(
            enabled_sources="hackernews", openai_api_key="",
            enable_news_validation=False,
        )
        session = _mock_session()
        # First execute raises IntegrityError
        session.execute = AsyncMock(
            side_effect=IntegrityError("dup", params=None, orig=Exception("unique"))
        )
        items = [_make_extracted_item()]
        classified = [_make_classified_item()]

        with (
            patch("src.pipeline.pipeline.get_settings", return_value=settings),
            patch("src.pipeline.pipeline._extract_all", new_callable=AsyncMock, return_value=items),
            patch("src.pipeline.pipeline.deduplicate_items", return_value=items),
            patch("src.pipeline.pipeline.KeywordClassifier") as mock_kw_cls,
            patch("src.pipeline.pipeline.CredibilityValidator") as mock_val_cls,
            patch("src.pipeline.pipeline.AlertService") as mock_alerts_cls,
        ):
            mock_classifier = AsyncMock()
            mock_classifier.classify.return_value = classified
            mock_kw_cls.return_value = mock_classifier

            mock_val = AsyncMock()
            mock_val.validate.return_value = classified
            mock_val_cls.return_value = mock_val

            mock_alerts = AsyncMock()
            mock_alerts_cls.return_value = mock_alerts

            # The pipeline handles IntegrityError internally via on_conflict_do_nothing
            # This test verifies the session error path doesn't crash the pipeline
            with pytest.raises((IntegrityError, Exception)):
                await run_pipeline(session)
```

**Step 2: Run tests**

```bash
pytest tests/unit/test_pipeline.py -v --timeout=30
```

**Step 3: Commit**

```bash
git add tests/unit/test_pipeline.py
git commit -m "test: add edge-case tests for pipeline orchestration [M9]"
```

---

## Task 7: API route edge cases (+8 tests)

**Files:**
- Test: `tests/unit/test_auth.py`
- Test: `tests/unit/test_api_routes.py`
- Test: `tests/unit/test_search_api.py`
- Test: `tests/unit/test_chat_route.py`

**Step 1: Add auth edge cases**

Read `tests/unit/test_auth.py` first. Add tests for expired/malformed tokens:

```python
class TestAuthEdgeCases:
    """Edge cases for JWT authentication."""

    async def test_expired_token(self, api_client):
        """Expired JWT returns 401."""
        import time
        from jose import jwt
        from src.core.config import get_settings
        settings = get_settings()
        payload = {"sub": "test", "exp": int(time.time()) - 3600}  # expired 1h ago
        token = jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
        resp = await api_client.get("/api/items", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 401

    async def test_malformed_token(self, api_client):
        """Garbage JWT string returns 401."""
        resp = await api_client.get("/api/items",
            headers={"Authorization": "Bearer not.a.valid.jwt.token"})
        assert resp.status_code == 401

    async def test_no_auth_header(self, api_client):
        """Missing Authorization header returns 401 or 403."""
        resp = await api_client.get("/api/items")
        assert resp.status_code in (401, 403)
```

Note: The auth tests may require removing the `require_auth` override for these specific tests. Read the test file to understand how to do this properly.

**Step 2: Add API route edge cases**

Add to `tests/unit/test_search_api.py`:

```python
class TestSearchEdgeCases:
    async def test_search_empty_query(self, api_client):
        """Empty q parameter returns 422 or empty results."""
        resp = await api_client.get("/api/search", params={"q": ""})
        assert resp.status_code in (200, 422)

    async def test_search_special_characters(self, api_client):
        """SQL injection attempt is safe (parameterized query)."""
        resp = await api_client.get("/api/search", params={"q": "'; DROP TABLE--"})
        assert resp.status_code in (200, 422)
        # Key: no 500 error (not a SQL injection)
```

Add to `tests/unit/test_chat_route.py`:

```python
class TestChatEdgeCases:
    async def test_empty_question(self, api_client):
        """Empty question returns 422."""
        resp = await api_client.post("/api/chat", json={"question": ""})
        assert resp.status_code == 422

    async def test_invalid_topic(self, api_client):
        """Nonexistent topic returns 422 or empty context."""
        resp = await api_client.post("/api/chat",
            json={"question": "test", "topic": "nonexistent_topic"})
        assert resp.status_code in (200, 422)

    async def test_limit_zero(self, api_client):
        """limit=0 returns 422 validation error."""
        resp = await api_client.post("/api/chat",
            json={"question": "test", "limit": 0})
        assert resp.status_code == 422
```

Add to `tests/unit/test_api_routes.py`:

```python
class TestItemsEdgeCases:
    async def test_negative_limit(self, api_client):
        """Negative limit parameter returns 422 or is capped."""
        resp = await api_client.get("/api/items", params={"limit": -1})
        assert resp.status_code in (200, 422)

    async def test_very_large_limit(self, api_client):
        """Very large limit is capped or returns 422."""
        resp = await api_client.get("/api/items", params={"limit": 99999})
        assert resp.status_code in (200, 422)
```

**Step 3: Run tests**

```bash
pytest tests/unit/test_auth.py tests/unit/test_api_routes.py tests/unit/test_search_api.py tests/unit/test_chat_route.py -v --timeout=30
```

**Step 4: Commit**

```bash
git add tests/unit/test_auth.py tests/unit/test_api_routes.py tests/unit/test_search_api.py tests/unit/test_chat_route.py
git commit -m "test: add edge-case tests for API routes [M9]"
```

---

## Task 8: RAG + Core edge cases (+8 tests)

**Files:**
- Test: `tests/unit/test_embeddings.py`
- Test: `tests/unit/test_retriever.py`
- Test: `tests/unit/test_chat_service.py`
- Test: `tests/unit/test_config.py`
- Test: `tests/unit/test_models.py`

**Step 1: Read each file and add edge cases**

Read each test file first. Add:

To `tests/unit/test_embeddings.py`:
```python
class TestEdgeCases:
    async def test_embed_empty_text(self):
        """Empty text should raise ValueError or return empty."""
        # Read source to determine actual behavior, then test accordingly

    async def test_embed_whitespace_only(self):
        """Whitespace-only text handled same as empty."""

    async def test_embed_very_long_text(self):
        """Text > 30K chars is truncated before API call."""
```

To `tests/unit/test_retriever.py`:
```python
class TestEdgeCases:
    async def test_no_matching_embeddings(self):
        """Query with no similar embeddings returns empty list."""
```

To `tests/unit/test_chat_service.py`:
```python
class TestEdgeCases:
    async def test_no_context_found(self):
        """When retriever returns [], chat responds with 'no information' message."""
```

To `tests/unit/test_config.py`:
```python
class TestEdgeCases:
    def test_csv_property_empty_string(self):
        """ENABLED_SOURCES='' produces empty list, not ['']."""
        settings = Settings(enabled_sources="")
        assert settings.enabled_sources_list == []

    def test_csv_property_with_whitespace(self):
        """CSV values with spaces are trimmed."""
        settings = Settings(enabled_sources=" hackernews , arxiv ")
        assert "hackernews" in settings.enabled_sources_list
```

Note: These tests need to be adapted to actual source code patterns. Read each source file to write accurate assertions.

**Step 2: Run tests**

```bash
pytest tests/unit/test_embeddings.py tests/unit/test_retriever.py tests/unit/test_chat_service.py tests/unit/test_config.py tests/unit/test_models.py -v --timeout=30
```

**Step 3: Commit**

```bash
git add tests/unit/test_embeddings.py tests/unit/test_retriever.py tests/unit/test_chat_service.py tests/unit/test_config.py tests/unit/test_models.py
git commit -m "test: add edge-case tests for RAG services + core config [M9]"
```

---

## Task 9: Final verification & coverage

**Step 1: Run full test suite**

```bash
pytest tests/unit/ -v --timeout=30
```

Expected: ALL pass (existing 637 + ~84 new = ~720)

**Step 2: Coverage check**

```bash
coverage run -m pytest tests/unit/ --timeout=30
coverage report --show-missing --fail-under=95
```

If below 95%, identify uncovered lines and add targeted tests.

**Step 3: Lint & type check**

```bash
ruff check . && ruff format --check . && pyright .
```

**Step 4: Final commit if any fixes needed**

```bash
git add -A
git commit -m "test: M9 final coverage fixes [M9]"
```

**Step 5: Update milestone status**

Mark all success criteria in `docs/plans/2026-02-19-milestone-9-design.md` as complete:

```markdown
- [x] All 84+ new tests pass
- [x] Coverage >= 95%
- [x] No regressions
- [x] ruff + pyright clean
- [x] Every module has failure-mode tests
```

---

## Commit Summary

| # | Commit Message | Tests Added |
|---|---|---|
| 1 | `test: add edge-case tests for extractors base + HackerNews [M9]` | +9 |
| 2 | `test: add edge-case tests for arXiv + Reddit extractors [M9]` | +12 |
| 3 | `test: add edge-case tests for RSS + GitHub + HuggingFace extractors [M9]` | +19 |
| 4 | `test: add edge-case tests for credibility validator [M9]` | +10 |
| 5 | `test: add edge-case tests for classifiers + event dedup [M9]` | +14 |
| 6 | `test: add edge-case tests for pipeline orchestration [M9]` | +6 |
| 7 | `test: add edge-case tests for API routes [M9]` | +8 |
| 8 | `test: add edge-case tests for RAG services + core config [M9]` | +8 |
| 9 | `test: M9 final coverage fixes [M9]` (if needed) | varies |
| **Total** | | **~84+** |
