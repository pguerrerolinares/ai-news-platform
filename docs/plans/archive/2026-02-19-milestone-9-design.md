# Milestone 9 — Backend Edge Cases & Robustness

## Goal

Harden every backend module against realistic production failures. The current test
suite (637 tests, 92% coverage) validates happy paths thoroughly but lacks edge-case
coverage for malformed data, API failures, timeouts, and boundary conditions.

This milestone adds ~84 unit tests focused on scenarios that **will** happen in
production: external APIs returning garbage, rate limits, empty responses, invalid
inputs, and boundary scoring.

## Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Scope | All 12 backend modules | Systematic coverage, no blind spots |
| Depth | Extractors deep, others balanced | Extractors hit 6 external APIs — highest failure surface |
| Edge case style | Realistic production scenarios | Not fuzzing/chaos — things that actually happen |
| Test location | Existing test files (add tests) | No new test files; extend current suites |
| Target coverage | >= 95% | Up from 92%, justified by edge-case additions |
| Mocking | respx for HTTP, unittest.mock for LLM | Same patterns as existing tests |

## Success Criteria

- [x] All 65 new tests pass (`pytest tests/unit/ -x --timeout=30`) — 702 total (was 637)
- [x] Coverage >= 95% (95% excluding src/main.py entrypoint, 94% overall)
- [x] No regressions in existing 637 tests
- [x] `ruff check .` clean
- [x] Every source module has at least one "failure mode" test

---

## Components

### 1. Extractors — Base (`tests/unit/test_extractors_base.py`) — 3 tests

| Test | Scenario | Expected |
|---|---|---|
| `test_content_hash_empty_title` | `ExtractedItem(title="", url="https://x.com")` | Deterministic hash (SHA256 of empty+url) |
| `test_url_hash_empty_url` | `ExtractedItem(title="Foo", url="")` | Deterministic hash, no crash |
| `test_sort_equal_scores` | 3 items with score=100 | Stable sort, no error |

### 2. HackerNews Extractor (`tests/unit/test_hackernews_extractor.py`) — 6 tests

| Test | Scenario | Expected |
|---|---|---|
| `test_algolia_zero_hits` | API returns `{"hits": []}` | Empty list, no error |
| `test_story_missing_title` | Hit with `title: null` | Item skipped gracefully |
| `test_story_no_url_ask_hn` | Hit without `url` key (Ask HN) | Item skipped or uses HN URL |
| `test_negative_points` | Hit with `points: -5` | Item included with score=-5 or filtered |
| `test_duplicate_story_ids` | Two hits with same `objectID` | Deduplicated, only one returned |
| `test_unexpected_date_format` | `created_at: "not-a-date"` | Item skipped, logged warning |

### 3. arXiv Extractor (`tests/unit/test_arxiv_extractor.py`) — 6 tests

| Test | Scenario | Expected |
|---|---|---|
| `test_malformed_xml` | RSS body is `<broken>` | Empty list, logged error |
| `test_entry_no_title` | Feed entry missing `<title>` | Entry skipped |
| `test_entry_no_links` | Entry without PDF/HTML links | Entry skipped or URL=None handled |
| `test_duplicate_paper_ids` | Same paper in 2 categories | Deduplicated by paper ID |
| `test_entries_older_than_window` | All entries > since_hours old | Empty list (all filtered) |
| `test_very_long_abstract` | Abstract > 10K chars | Truncated or handled, no OOM |

### 4. Reddit Extractor (`tests/unit/test_reddit_extractor.py`) — 6 tests

| Test | Scenario | Expected |
|---|---|---|
| `test_all_posts_stickied` | Every post has `stickied: true` | Empty list |
| `test_subreddit_private_403` | API returns 403 | Empty list, logged warning |
| `test_self_post_no_url` | `is_self: true`, no external URL | Uses reddit permalink or skipped |
| `test_post_score_zero` | Post with `score: 0` | Included (filtering is validator's job) |
| `test_empty_children` | `data.children: []` | Empty list |
| `test_missing_data_key` | Response lacks `data` key | Empty list, logged error |

### 5. RSS Extractor (`tests/unit/test_rss_extractor.py`) — 7 tests

| Test | Scenario | Expected |
|---|---|---|
| `test_feed_http_404` | Feed URL returns 404 | Skipped feed, others continue |
| `test_feed_http_500` | Feed URL returns 500 | Skipped feed, logged warning |
| `test_feed_no_entries` | Valid feed, 0 entries | Empty list from that feed |
| `test_entry_no_published_date` | Entry missing `published` | Uses current time or skipped |
| `test_entry_unparseable_date` | `published: "yesterday"` | Fallback date or skipped |
| `test_entry_html_entities_title` | Title: `"AI &amp; ML &#8212; News"` | Decoded to `"AI & ML — News"` |
| `test_entry_no_link` | Entry without `link` field | Entry skipped |

### 6. GitHub Extractor (`tests/unit/test_github_extractor.py`) — 6 tests

| Test | Scenario | Expected |
|---|---|---|
| `test_rate_limit_403` | API returns 403 with rate limit headers | Empty list, logged warning (not crash) |
| `test_empty_search_results` | `{"items": []}` | Empty list |
| `test_repo_no_description` | Repo with `description: null` | Uses empty string or repo name |
| `test_repo_zero_stars` | Repo with `stargazers_count: 0` | Handled (may be filtered by config) |
| `test_repo_no_pushed_at` | Missing `pushed_at` field | Fallback or skipped |
| `test_incomplete_results` | `incomplete_results: true` | Returns partial results, logged info |

### 7. HuggingFace Extractor (`tests/unit/test_huggingface_extractor.py`) — 6 tests

| Test | Scenario | Expected |
|---|---|---|
| `test_empty_trending_list` | API returns `[]` | Empty list |
| `test_model_no_pipeline_tag` | Model without `pipeline_tag` | Uses "unknown" or skipped |
| `test_model_zero_downloads` | `downloads: 0` | Included or filtered by threshold |
| `test_missing_response_keys` | Response missing expected keys | Graceful skip per item |
| `test_very_long_model_name` | Model ID > 500 chars | Truncated or handled |
| `test_http_timeout` | Request times out after 10s | Empty list, logged warning |

### 8. Credibility Validator (`tests/unit/test_credibility_validator.py`) — 10 tests

| Test | Scenario | Expected |
|---|---|---|
| `test_dns_resolution_failure` | URL with unresolvable domain | Penalty on credibility, not crash |
| `test_redirect_to_private_ip` | URL 302 → 10.0.0.1 | SSRF blocked, penalty applied |
| `test_ssl_certificate_error` | URL with expired SSL | Penalty, not filtered outright |
| `test_very_slow_url_response` | HEAD request takes 25s | Timeout, penalty applied |
| `test_score_at_exact_boundary` | credibility_score = 0.4 exactly | Kept (>= threshold, not >) or filtered (document behavior) |
| `test_engagement_score_zero` | HN/Reddit item with score=0 | Filtered (score < 5 rule) |
| `test_jaccard_identical_titles` | Two items with exact same title | Second one deduped |
| `test_jaccard_only_stopwords` | Title = "the and or but" | Tokenizes to empty set, no division by zero |
| `test_tone_all_caps` | Title = "SHOCKING AI BREAKTHROUGH!!!" | Suspicious patterns detected, score penalized |
| `test_tone_professional` | Title = "Published research methodology paper" | Professional bonus applied |

### 9. Keyword Classifier (`tests/unit/test_keyword_classifier.py`) — 4 tests

| Test | Scenario | Expected |
|---|---|---|
| `test_empty_title_and_text` | Item with title="" and text="" | Relevance=0, filtered out |
| `test_title_only_emojis` | Title = "🤖🔥💯" | No keyword match, relevance=0 |
| `test_title_only_stopwords` | Title = "the and or is" | No keyword match, relevance=0 |
| `test_all_topics_disabled` | Config with enabled_topics=[] | All items filtered |

### 10. LLM Classifier (`tests/unit/test_llm_classifier.py`) — 6 tests

| Test | Scenario | Expected |
|---|---|---|
| `test_malformed_json_response` | LLM returns `"Sure! Here's..."` | Falls back to keyword classifier |
| `test_partial_json_response` | LLM returns `[{"topic": "modelos"` (truncated) | Falls back to keyword classifier |
| `test_empty_response` | LLM returns `""` | Falls back to keyword classifier |
| `test_retry_exhaustion` | 3 consecutive RateLimitError | Falls back to keyword classifier after 3 retries |
| `test_batch_partial_failure` | Batch 1 succeeds, batch 2 fails | Batch 1 results kept + batch 2 falls back |
| `test_non_retryable_error` | AuthenticationError from LLM | Raises immediately (no retry) |

### 11. Event Deduplication (`tests/unit/test_event_dedup.py`) — 4 tests (new)

| Test | Scenario | Expected |
|---|---|---|
| `test_single_item_no_grouping` | Only 1 item in topic | Returned as-is, no LLM call |
| `test_all_items_same_event` | LLM groups all 5 items together | 1 winner with trending=True, source_count=5 |
| `test_llm_returns_invalid_groups` | LLM returns non-JSON or wrong schema | All items returned unchanged (graceful) |
| `test_empty_topic_group` | Topic with 0 items | No crash, skipped |

### 12. Pipeline (`tests/unit/test_pipeline.py`) — 6 tests

| Test | Scenario | Expected |
|---|---|---|
| `test_all_extractors_fail` | Every extractor raises exception | Pipeline logs error, sends alert, exits early |
| `test_all_items_filtered_by_classifier` | Classifier returns [] | Pipeline continues, briefing with 0 items |
| `test_all_items_filtered_by_validator` | Validator returns [] | Pipeline continues, briefing with 0 items |
| `test_partial_batch_insert_failure` | First batch OK, second raises IntegrityError | First batch committed, error logged |
| `test_briefing_upsert_existing_date` | Briefing for today already exists | Upserted (updated, not duplicated) |
| `test_embedding_api_unavailable` | Embedding API key not set | Embedding step skipped, rest succeeds |

### 13. API Routes — Auth (`tests/unit/test_auth.py`) — 3 tests

| Test | Scenario | Expected |
|---|---|---|
| `test_expired_token` | JWT expired 1 hour ago | 401 "Token has expired" |
| `test_malformed_token` | Authorization: Bearer garbage123 | 401 "Invalid token" |
| `test_missing_auth_header` | No Authorization header on protected route | 401/403 |

### 14. API Routes — Items & Search (`tests/unit/test_api_routes.py`, `test_search_api.py`) — 4 tests

| Test | Scenario | Expected |
|---|---|---|
| `test_invalid_date_format` | `date_from=not-a-date` | 422 validation error |
| `test_limit_exceeds_max` | `limit=9999` | Capped at 200 or 422 |
| `test_search_empty_query` | `GET /api/search?q=` | 422 or empty results |
| `test_search_special_characters` | `q="; DROP TABLE--"` | Safe (parameterized query), no injection |

### 15. API Routes — Chat (`tests/unit/test_chat_route.py`) — 3 tests

| Test | Scenario | Expected |
|---|---|---|
| `test_empty_question` | `{"question": ""}` | 422 validation error |
| `test_topic_nonexistent` | `{"question": "x", "topic": "crypto"}` | 422 or empty context |
| `test_limit_out_of_range` | `{"question": "x", "limit": 0}` | 422 validation error |

### 16. RAG Services (`tests/unit/test_embeddings.py`, `test_retriever.py`, `test_chat_service.py`) — 5 tests

| Test | Scenario | Expected |
|---|---|---|
| `test_embed_empty_text` | `embed_text("")` | Returns zero vector or raises ValueError |
| `test_embed_whitespace_only` | `embed_text("   \n\t  ")` | Same as empty |
| `test_embed_very_long_text` | Text > 30K chars | Truncated before API call |
| `test_retrieve_no_matches` | Query with no similar embeddings in DB | Empty list |
| `test_chat_no_context_found` | Retriever returns [] | LLM responds without context, or "no info" message |

### 17. Core — Config & Models (`tests/unit/test_config.py`, `test_models.py`) — 3 tests

| Test | Scenario | Expected |
|---|---|---|
| `test_missing_required_env_var` | DATABASE_URL not set | ValidationError at startup |
| `test_csv_property_empty_string` | `ENABLED_SOURCES=""` | Empty list, not `[""]` |
| `test_invalid_topic_in_model` | Insert NewsItem with topic="crypto" | DB constraint violation |

---

## File Map

| Test File | New Tests | Source Module |
|---|---|---|
| `tests/unit/test_extractors_base.py` | +3 | `src/extractors/base.py` |
| `tests/unit/test_hackernews_extractor.py` | +6 | `src/extractors/hackernews.py` |
| `tests/unit/test_arxiv_extractor.py` | +6 | `src/extractors/arxiv.py` |
| `tests/unit/test_reddit_extractor.py` | +6 | `src/extractors/reddit.py` |
| `tests/unit/test_rss_extractor.py` | +7 | `src/extractors/rss.py` |
| `tests/unit/test_github_extractor.py` | +6 | `src/extractors/github.py` |
| `tests/unit/test_huggingface_extractor.py` | +6 | `src/extractors/huggingface.py` |
| `tests/unit/test_credibility_validator.py` | +10 | `src/validators/credibility.py` |
| `tests/unit/test_keyword_classifier.py` | +4 | `src/classifiers/keyword.py` |
| `tests/unit/test_llm_classifier.py` | +6 | `src/classifiers/llm.py` |
| `tests/unit/test_event_dedup.py` | +4 | `src/classifiers/event_dedup.py` |
| `tests/unit/test_pipeline.py` | +6 | `src/pipeline/pipeline.py` |
| `tests/unit/test_auth.py` | +3 | `src/api/auth.py` |
| `tests/unit/test_api_routes.py` | +2 | `src/api/routes/items.py` |
| `tests/unit/test_search_api.py` | +2 | `src/api/routes/search.py` |
| `tests/unit/test_chat_route.py` | +3 | `src/api/routes/chat.py` |
| `tests/unit/test_embeddings.py` | +3 | `src/rag/embeddings.py` |
| `tests/unit/test_retriever.py` | +1 | `src/rag/retriever.py` |
| `tests/unit/test_chat_service.py` | +1 | `src/rag/chat.py` |
| `tests/unit/test_config.py` | +2 | `src/core/config.py` |
| `tests/unit/test_models.py` | +1 | `src/core/models.py` |
| **Total** | **+84** | |

## Implementation Notes

- **No new test files**: All tests added to existing files to maintain organization
- **Mocking**: Use `respx` for HTTP mocks, `unittest.mock.patch` for LLM/DB
- **Patterns**: Follow existing test patterns in each file (fixtures, parametrize, etc.)
- **Source fixes**: Some edge cases may reveal actual bugs — fix them and document in commits
- **Commit strategy**: One commit per module group (extractors, classifiers, etc.)

## Verification

1. `pytest tests/unit/ -x --timeout=30` — all pass
2. `coverage run -m pytest tests/unit/ && coverage report --fail-under=95`
3. `ruff check . && ruff format --check .`
4. `pyright .`
5. No existing test regressions

---

## Next Milestones (Outline)

### M10 — Integration Testing

Test real component interactions with a test database (PostgreSQL via testcontainers
or SQLite in-memory). Validate: pipeline end-to-end writes correct data, API routes
return correct query results, embedding storage/retrieval works, briefing upserts
accumulate correctly. Requires `tests/integration/` infrastructure setup.

### M11 — Security Hardening

Penetration-style tests: JWT manipulation (algorithm confusion, forged tokens), SSRF
bypass attempts (DNS rebinding, IPv6 mapped addresses, URL encoding tricks), SQL
injection via search/filter parameters, rate limit evasion, input fuzzing on all API
endpoints, header injection. Validates the "secure by default" principle holds under
adversarial inputs.
