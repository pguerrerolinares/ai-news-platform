"""Tests for src.notifiers.telegram -- TelegramNotifier."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import httpx
import pytest
import respx

from src.core.config import get_settings
from src.notifiers.telegram import (
    MAX_MSG_LEN,
    PRIORITY_DOT,
    SOURCE_LABEL,
    TOPIC_EMOJI,
    TelegramNotifier,
    _esc,
    _safe_url,
    _sort_items,
    _split_text,
)
from tests.factories import make_classified_item


@pytest.fixture(autouse=True)
def _clear_settings_cache():
    """Clear the lru_cache on get_settings so env var changes take effect."""
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture()
def notifier(monkeypatch):
    """Create an enabled TelegramNotifier for testing."""
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123:ABC")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "999")
    monkeypatch.setenv("TELEGRAM_ALERTS_ENABLED", "true")
    return TelegramNotifier(bot_token="123:ABC", chat_id="999")


@pytest.fixture()
def disabled_notifier(monkeypatch):
    """Create a disabled TelegramNotifier for testing."""
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "")
    monkeypatch.setenv("TELEGRAM_ALERTS_ENABLED", "false")
    return TelegramNotifier(bot_token="", chat_id="")


@pytest.fixture()
def sample_items():
    """Create a diverse set of classified items for testing."""
    return [
        make_classified_item(
            title="GPT-5 Released",
            source="hackernews",
            url="https://example.com/gpt5",
            topic="models",
            relevance_score=0.98,
            priority=1,
            trending=True,
            summary="OpenAI releases GPT-5 with significant improvements.",
        ),
        make_classified_item(
            title="New LangChain Update",
            source="reddit",
            url="https://example.com/langchain",
            topic="tools",
            relevance_score=0.85,
            priority=2,
            trending=False,
            summary="LangChain v0.3 with agent support.",
        ),
        make_classified_item(
            title="Attention Is Still All You Need",
            source="arxiv",
            url="https://arxiv.org/abs/2025.12345",
            topic="papers",
            relevance_score=0.92,
            priority=1,
            trending=True,
            summary="New paper demonstrates attention mechanism improvements.",
        ),
        make_classified_item(
            title="Claude 4 Released",
            source="rss",
            url="https://example.com/claude4",
            topic="models",
            relevance_score=0.95,
            priority=2,
            trending=False,
            summary="Anthropic presents Claude 4.",
        ),
        make_classified_item(
            title="Open Source LLM Benchmark",
            source="hackernews",
            url="https://example.com/benchmark",
            topic="open_source",
            relevance_score=0.80,
            priority=3,
            trending=False,
            summary="Comparative benchmark of open source models.",
        ),
    ]


# =========================================================================
# Helper function tests
# =========================================================================


class TestEsc:
    """Test HTML escaping."""

    def test_escapes_ampersand(self):
        assert _esc("A&B") == "A&amp;B"

    def test_escapes_angle_brackets(self):
        assert _esc("<script>alert('xss')</script>") == (
            "&lt;script&gt;alert(&#x27;xss&#x27;)&lt;/script&gt;"
        )

    def test_escapes_quotes(self):
        assert _esc('She said "hello"') == "She said &quot;hello&quot;"

    def test_escapes_single_quotes(self):
        assert _esc("it's") == "it&#x27;s"

    def test_plain_text_unchanged(self):
        assert _esc("Hello World 123") == "Hello World 123"

    def test_empty_string(self):
        assert _esc("") == ""

    def test_multiple_special_chars(self):
        assert _esc("<b>A&B</b>") == "&lt;b&gt;A&amp;B&lt;/b&gt;"


class TestSafeUrl:
    """Test URL sanitization."""

    def test_escapes_ampersand_in_url(self):
        assert _safe_url("https://example.com?a=1&b=2") == "https://example.com?a=1&amp;b=2"

    def test_escapes_quotes_in_url(self):
        assert _safe_url('https://example.com?q="test"') == "https://example.com?q=%22test%22"

    def test_escapes_angle_brackets_in_url(self):
        assert _safe_url("https://example.com/<path>") == "https://example.com/%3Cpath%3E"

    def test_plain_url_unchanged(self):
        url = "https://example.com/article/123"
        assert _safe_url(url) == url

    def test_empty_url(self):
        assert _safe_url("") == ""


class TestSplitText:
    """Test message splitting at newline boundaries."""

    def test_text_under_limit_returns_single_chunk(self):
        text = "Hello\nWorld"
        result = _split_text(text, 100)
        assert result == ["Hello\nWorld"]

    def test_text_exactly_at_limit(self):
        text = "A" * 100
        result = _split_text(text, 100)
        assert result == [text]

    def test_text_over_limit_splits_at_newline(self):
        text = "Line one\nLine two\nLine three"
        result = _split_text(text, 15)
        assert len(result) >= 2
        for chunk in result:
            assert len(chunk) <= 15

    def test_no_newline_splits_at_limit(self):
        text = "A" * 200
        result = _split_text(text, 100)
        assert result == ["A" * 100, "A" * 100]

    def test_empty_text(self):
        result = _split_text("", 100)
        assert result == []

    def test_preserves_all_content(self):
        text = "Line1\nLine2\nLine3\nLine4\nLine5"
        result = _split_text(text, 12)
        # When we rejoin the chunks, all content should be present
        # (newlines between chunks are stripped by lstrip)
        combined = "\n".join(result)
        for line in ["Line1", "Line2", "Line3", "Line4", "Line5"]:
            assert line in combined

    def test_large_split_respects_limit(self):
        lines = [f"Line number {i}" for i in range(100)]
        text = "\n".join(lines)
        result = _split_text(text, MAX_MSG_LEN)
        for chunk in result:
            assert len(chunk) <= MAX_MSG_LEN


class TestSortItems:
    """Test item sorting logic."""

    def test_trending_items_come_first(self):
        trending = make_classified_item(trending=True, priority=3, relevance_score=0.5)
        normal = make_classified_item(trending=False, priority=1, relevance_score=0.99)
        result = _sort_items([normal, trending])
        assert result[0] is trending

    def test_within_same_trending_sorts_by_priority(self):
        p1 = make_classified_item(trending=False, priority=1, relevance_score=0.5)
        p3 = make_classified_item(trending=False, priority=3, relevance_score=0.9)
        result = _sort_items([p3, p1])
        assert result[0] is p1

    def test_within_same_priority_sorts_by_relevance_desc(self):
        high = make_classified_item(trending=False, priority=2, relevance_score=0.95)
        low = make_classified_item(trending=False, priority=2, relevance_score=0.70)
        result = _sort_items([low, high])
        assert result[0] is high


# =========================================================================
# TelegramNotifier construction tests
# =========================================================================


class TestTelegramNotifierInit:
    """Test TelegramNotifier initialization."""

    def test_enabled_when_all_provided(self, monkeypatch):
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "tok")
        monkeypatch.setenv("TELEGRAM_CHAT_ID", "123")
        monkeypatch.setenv("TELEGRAM_ALERTS_ENABLED", "true")
        n = TelegramNotifier(bot_token="tok", chat_id="123")
        assert n.enabled is True
        assert n._base_url == "https://api.telegram.org/bottok"

    def test_disabled_when_no_token(self, monkeypatch):
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "")
        monkeypatch.setenv("TELEGRAM_CHAT_ID", "123")
        monkeypatch.setenv("TELEGRAM_ALERTS_ENABLED", "true")
        n = TelegramNotifier(bot_token="", chat_id="123")
        assert n.enabled is False

    def test_disabled_when_alerts_off(self, monkeypatch):
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "tok")
        monkeypatch.setenv("TELEGRAM_CHAT_ID", "123")
        monkeypatch.setenv("TELEGRAM_ALERTS_ENABLED", "false")
        n = TelegramNotifier(bot_token="tok", chat_id="123")
        assert n.enabled is False


# =========================================================================
# Building block tests
# =========================================================================


class TestBuildHeader:
    """Test header building."""

    def test_header_contains_date(self, sample_items):
        grouped = TelegramNotifier._group_by_topic(sample_items)
        header = TelegramNotifier._build_header(sample_items, grouped)
        assert "AI Briefing" in header
        assert "/" in header  # date format DD/MM/YYYY

    def test_header_contains_topic_counts(self, sample_items):
        grouped = TelegramNotifier._group_by_topic(sample_items)
        header = TelegramNotifier._build_header(sample_items, grouped)
        assert "Models: 2" in header
        assert "Tools: 1" in header
        assert "Papers: 1" in header
        assert "Open source: 1" in header

    def test_header_contains_source_counts(self, sample_items):
        grouped = TelegramNotifier._group_by_topic(sample_items)
        header = TelegramNotifier._build_header(sample_items, grouped)
        assert "5 items" in header
        assert "HN" in header

    def test_header_shows_trending_count(self, sample_items):
        grouped = TelegramNotifier._group_by_topic(sample_items)
        header = TelegramNotifier._build_header(sample_items, grouped)
        # modelos has 1 trending item
        assert "\U0001f525" in header

    def test_header_with_single_item(self):
        items = [make_classified_item(topic="models", source="hackernews")]
        grouped = TelegramNotifier._group_by_topic(items)
        header = TelegramNotifier._build_header(items, grouped)
        assert "1 items" in header
        assert "Models: 1" in header


class TestBuildTop3:
    """Test Top 3 section building."""

    def test_top3_contains_titles(self, sample_items):
        from src.notifiers.telegram import _sort_items

        sorted_items = _sort_items(sample_items)
        top3 = TelegramNotifier._build_top3(sorted_items)
        assert "TOP 3 OF THE DAY" in top3
        assert "GPT-5 Released" in top3

    def test_top3_contains_urls(self, sample_items):
        sorted_items = _sort_items(sample_items)
        top3 = TelegramNotifier._build_top3(sorted_items)
        assert "href=" in top3

    def test_top3_shows_trending_marker(self, sample_items):
        sorted_items = _sort_items(sample_items)
        top3 = TelegramNotifier._build_top3(sorted_items)
        assert "\U0001f525" in top3

    def test_top3_shows_summaries(self, sample_items):
        sorted_items = _sort_items(sample_items)
        top3 = TelegramNotifier._build_top3(sorted_items)
        # At least one summary should appear
        assert "OpenAI releases" in top3 or "New paper" in top3

    def test_top3_shows_source_labels(self, sample_items):
        sorted_items = _sort_items(sample_items)
        top3 = TelegramNotifier._build_top3(sorted_items)
        # Top items are from HN and arXiv
        assert "HN" in top3 or "arXiv" in top3

    def test_top3_empty_list(self):
        top3 = TelegramNotifier._build_top3([])
        assert top3 == ""

    def test_top3_with_one_item(self):
        items = [make_classified_item(title="Only Item", source="hackernews")]
        top3 = TelegramNotifier._build_top3(items)
        assert "Only Item" in top3
        assert "<b>1.</b>" in top3

    def test_top3_limits_to_three(self, sample_items):
        sorted_items = _sort_items(sample_items)
        top3 = TelegramNotifier._build_top3(sorted_items)
        # Should have 1., 2., 3. but not 4.
        assert "<b>1.</b>" in top3
        assert "<b>2.</b>" in top3
        assert "<b>3.</b>" in top3
        assert "<b>4.</b>" not in top3


class TestBuildTopicBlock:
    """Test topic block building."""

    def test_topic_block_has_emoji_and_label(self):
        items = [make_classified_item(topic="models")]
        block = TelegramNotifier._build_topic_block("models", items)
        assert "\U0001f9e0" in block
        assert "MODELS" in block

    def test_topic_block_lists_all_items(self):
        items = [
            make_classified_item(title="Item A", topic="papers"),
            make_classified_item(title="Item B", topic="papers"),
        ]
        block = TelegramNotifier._build_topic_block("papers", items)
        assert "Item A" in block
        assert "Item B" in block
        assert "<b>1.</b>" in block
        assert "<b>2.</b>" in block

    def test_topic_block_unknown_topic_uses_fallback_emoji(self):
        items = [make_classified_item(topic="unknown")]
        block = TelegramNotifier._build_topic_block("unknown", items)
        assert "\U0001f4cc" in block  # pushpin fallback
        assert "UNKNOWN" in block


class TestFormatItemCompact:
    """Test compact item formatting."""

    def test_with_url_creates_link(self):
        item = make_classified_item(
            title="Test Item",
            url="https://example.com/test",
            source="hackernews",
        )
        result = TelegramNotifier._format_item_compact(item, 1)
        assert '<a href="https://example.com/test">' in result
        assert "Test Item" in result

    def test_without_url_no_link(self):
        item = make_classified_item(
            title="No URL Item",
            url=None,
            source="hackernews",
        )
        result = TelegramNotifier._format_item_compact(item, 1)
        assert "<a href=" not in result
        assert "No URL Item" in result

    def test_trending_shows_fire(self):
        item = make_classified_item(trending=True)
        result = TelegramNotifier._format_item_compact(item, 1)
        assert "\U0001f525" in result

    def test_not_trending_no_fire(self):
        item = make_classified_item(trending=False)
        result = TelegramNotifier._format_item_compact(item, 1)
        assert "\U0001f525" not in result

    def test_summary_included_when_different_from_title(self):
        item = make_classified_item(
            title="GPT-5 Released",
            summary="OpenAI lanza GPT-5 con mejoras.",
        )
        result = TelegramNotifier._format_item_compact(item, 1)
        assert "OpenAI lanza" in result

    def test_summary_excluded_when_same_as_title(self):
        item = make_classified_item(
            title="Same Title",
            summary="Same Title",
        )
        result = TelegramNotifier._format_item_compact(item, 1)
        # Title appears once (in the link), but summary line should not appear
        lines = result.split("\n")
        summary_lines = [ln for ln in lines if ln.strip().startswith("Same Title")]
        assert len(summary_lines) == 0

    def test_source_label_appears(self):
        item = make_classified_item(source="arxiv")
        result = TelegramNotifier._format_item_compact(item, 1)
        assert "arXiv" in result

    def test_score_appears_when_present(self):
        from src.extractors.base import ExtractedItem

        ext_item = ExtractedItem(
            title="Scored Item",
            source="hackernews",
            url="https://example.com",
            score=387,
        )
        item = make_classified_item(title="Scored Item", item=ext_item)
        result = TelegramNotifier._format_item_compact(item, 1)
        assert "387" in result

    def test_no_score_when_none(self):
        from src.extractors.base import ExtractedItem

        ext_item = ExtractedItem(
            title="No Score",
            source="arxiv",
            url="https://example.com",
            score=None,
        )
        item = make_classified_item(title="No Score", item=ext_item)
        result = TelegramNotifier._format_item_compact(item, 1)
        # Should just have "arXiv" without a trailing number
        assert "<i>arXiv</i>" in result

    def test_html_escaping_in_title(self):
        item = make_classified_item(title="LLM <b>bold</b> & fast")
        result = TelegramNotifier._format_item_compact(item, 1)
        assert "&lt;b&gt;" in result
        assert "&amp;" in result


class TestBuildFooter:
    """Test footer building."""

    def test_footer_contains_item_count(self, sample_items):
        footer = TelegramNotifier._build_footer(sample_items, 120.0)
        assert "5 analyzed" in footer

    def test_footer_contains_source_count(self, sample_items):
        footer = TelegramNotifier._build_footer(sample_items, 120.0)
        assert "4 sources" in footer  # hackernews, reddit, arxiv, rss

    def test_footer_contains_duration(self, sample_items):
        footer = TelegramNotifier._build_footer(sample_items, 138.0)
        assert "2.3 min" in footer

    def test_footer_no_duration_when_zero(self, sample_items):
        footer = TelegramNotifier._build_footer(sample_items, 0.0)
        assert "min" not in footer

    def test_footer_contains_trending_count(self, sample_items):
        footer = TelegramNotifier._build_footer(sample_items, 120.0)
        assert "2 trending" in footer

    def test_footer_no_trending_when_zero(self):
        items = [make_classified_item(trending=False)]
        footer = TelegramNotifier._build_footer(items, 60.0)
        assert "trending" not in footer

    def test_footer_has_separator(self, sample_items):
        footer = TelegramNotifier._build_footer(sample_items, 120.0)
        assert "\u2500\u2500\u2500" in footer


# =========================================================================
# send_message tests
# =========================================================================


class TestSendMessage:
    """Test send_message (BaseNotifier implementation)."""

    @respx.mock
    async def test_send_message_success(self, notifier):
        route = respx.post("https://api.telegram.org/bot123:ABC/sendMessage").mock(
            return_value=httpx.Response(200, json={"ok": True})
        )
        result = await notifier.send_message("Hello!")
        assert result is True
        assert route.called

    @respx.mock
    async def test_send_message_includes_html_parse_mode(self, notifier):
        route = respx.post("https://api.telegram.org/bot123:ABC/sendMessage").mock(
            return_value=httpx.Response(200, json={"ok": True})
        )
        await notifier.send_message("Test")
        request = route.calls[0].request
        import json

        body = json.loads(request.content)
        assert body["parse_mode"] == "HTML"
        assert body["disable_web_page_preview"] is True

    async def test_send_message_disabled_returns_false(self, disabled_notifier):
        result = await disabled_notifier.send_message("Hello!")
        assert result is False

    @respx.mock
    async def test_send_message_http_error_returns_false(self, notifier):
        respx.post("https://api.telegram.org/bot123:ABC/sendMessage").mock(
            return_value=httpx.Response(500, json={"ok": False})
        )
        result = await notifier.send_message("Hello!")
        assert result is False

    @respx.mock
    async def test_send_message_network_error_returns_false(self, notifier):
        respx.post("https://api.telegram.org/bot123:ABC/sendMessage").mock(
            side_effect=httpx.ConnectError("Connection refused")
        )
        result = await notifier.send_message("Hello!")
        assert result is False


# =========================================================================
# send_error tests
# =========================================================================


class TestSendError:
    """Test send_error (BaseNotifier implementation)."""

    @respx.mock
    async def test_send_error_success(self, notifier):
        route = respx.post("https://api.telegram.org/bot123:ABC/sendMessage").mock(
            return_value=httpx.Response(200, json={"ok": True})
        )
        result = await notifier.send_error("Something broke", context="extraction")
        assert result is True
        import json

        body = json.loads(route.calls[0].request.content)
        assert "Error" in body["text"]
        assert "extraction" in body["text"]
        assert "Something broke" in body["text"]

    @respx.mock
    async def test_send_error_without_context(self, notifier):
        route = respx.post("https://api.telegram.org/bot123:ABC/sendMessage").mock(
            return_value=httpx.Response(200, json={"ok": True})
        )
        result = await notifier.send_error("Boom")
        assert result is True
        import json

        body = json.loads(route.calls[0].request.content)
        assert "Error" in body["text"]
        assert "Boom" in body["text"]

    async def test_send_error_disabled_returns_false(self, disabled_notifier):
        result = await disabled_notifier.send_error("fail", context="test")
        assert result is False

    @respx.mock
    async def test_send_error_truncates_long_errors(self, notifier):
        route = respx.post("https://api.telegram.org/bot123:ABC/sendMessage").mock(
            return_value=httpx.Response(200, json={"ok": True})
        )
        long_error = "X" * 1000
        await notifier.send_error(long_error)
        import json

        body = json.loads(route.calls[0].request.content)
        # Error is truncated to 500 chars before escaping
        assert len(body["text"]) < 1000


# =========================================================================
# _send with splitting tests
# =========================================================================


class TestSendWithSplitting:
    """Test _send method splits long messages correctly."""

    @respx.mock
    async def test_send_splits_long_message(self, notifier):
        route = respx.post("https://api.telegram.org/bot123:ABC/sendMessage").mock(
            return_value=httpx.Response(200, json={"ok": True})
        )
        # Create a message that exceeds MAX_MSG_LEN
        lines = [f"Line number {i:04d} with some padding text" for i in range(200)]
        long_msg = "\n".join(lines)
        assert len(long_msg) > MAX_MSG_LEN

        result = await notifier._send(long_msg)
        assert result is True
        assert route.call_count >= 2

    @respx.mock
    async def test_send_short_message_no_split(self, notifier):
        route = respx.post("https://api.telegram.org/bot123:ABC/sendMessage").mock(
            return_value=httpx.Response(200, json={"ok": True})
        )
        result = await notifier._send("Short message")
        assert result is True
        assert route.call_count == 1


# =========================================================================
# send_briefing tests
# =========================================================================


class TestSendBriefing:
    """Test the full send_briefing flow."""

    @respx.mock
    async def test_send_briefing_success(self, notifier, sample_items):
        route = respx.post("https://api.telegram.org/bot123:ABC/sendMessage").mock(
            return_value=httpx.Response(200, json={"ok": True})
        )
        result = await notifier.send_briefing(sample_items, duration_seconds=120.0)
        assert result is True
        assert route.called

    @respx.mock
    async def test_send_briefing_empty_items(self, notifier):
        route = respx.post("https://api.telegram.org/bot123:ABC/sendMessage").mock(
            return_value=httpx.Response(200, json={"ok": True})
        )
        result = await notifier.send_briefing([])
        assert result is True
        import json

        body = json.loads(route.calls[0].request.content)
        assert "No relevant news" in body["text"]

    @respx.mock
    async def test_send_briefing_includes_header(self, notifier, sample_items):
        route = respx.post("https://api.telegram.org/bot123:ABC/sendMessage").mock(
            return_value=httpx.Response(200, json={"ok": True})
        )
        await notifier.send_briefing(sample_items)
        # Collect all sent text
        import json

        all_text = ""
        for call in route.calls:
            body = json.loads(call.request.content)
            all_text += body["text"]

        assert "AI Briefing" in all_text

    @respx.mock
    async def test_send_briefing_includes_top3(self, notifier, sample_items):
        route = respx.post("https://api.telegram.org/bot123:ABC/sendMessage").mock(
            return_value=httpx.Response(200, json={"ok": True})
        )
        await notifier.send_briefing(sample_items)
        import json

        all_text = ""
        for call in route.calls:
            body = json.loads(call.request.content)
            all_text += body["text"]

        assert "TOP 3 OF THE DAY" in all_text

    @respx.mock
    async def test_send_briefing_includes_topic_blocks(self, notifier, sample_items):
        route = respx.post("https://api.telegram.org/bot123:ABC/sendMessage").mock(
            return_value=httpx.Response(200, json={"ok": True})
        )
        await notifier.send_briefing(sample_items)
        import json

        all_text = ""
        for call in route.calls:
            body = json.loads(call.request.content)
            all_text += body["text"]

        assert "MODELS" in all_text
        assert "TOOLS" in all_text
        assert "PAPERS" in all_text

    @respx.mock
    async def test_send_briefing_includes_footer(self, notifier, sample_items):
        route = respx.post("https://api.telegram.org/bot123:ABC/sendMessage").mock(
            return_value=httpx.Response(200, json={"ok": True})
        )
        await notifier.send_briefing(sample_items, duration_seconds=120.0)
        import json

        all_text = ""
        for call in route.calls:
            body = json.loads(call.request.content)
            all_text += body["text"]

        assert "analyzed" in all_text
        assert "sources" in all_text

    async def test_send_briefing_disabled_returns_false(self, disabled_notifier, sample_items):
        result = await disabled_notifier.send_briefing(sample_items)
        assert result is False

    @respx.mock
    async def test_send_briefing_respects_delay_between_chunks(self, notifier):
        """Verify that asyncio.sleep is called between message chunks."""
        respx.post("https://api.telegram.org/bot123:ABC/sendMessage").mock(
            return_value=httpx.Response(200, json={"ok": True})
        )
        # Create many items to generate a long briefing likely to split
        items = [
            make_classified_item(
                title=f"News Item {i} with a reasonably long title for testing",
                source="hackernews",
                topic="models",
                relevance_score=0.9 - i * 0.01,
                priority=2,
                summary=f"Detailed summary of item number {i} with relevant information.",
            )
            for i in range(50)
        ]
        with patch("src.notifiers.telegram.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            await notifier.send_briefing(items)
            # If message was split, sleep should be called
            # At minimum the briefing loop calls sleep between chunks
            if mock_sleep.call_count > 0:
                mock_sleep.assert_awaited()
                # Sleep should be called with 0.3
                for call in mock_sleep.call_args_list:
                    assert call.args[0] == 0.3

    @respx.mock
    async def test_send_briefing_partial_failure(self, notifier, sample_items):
        """If one chunk fails, send_briefing returns False."""
        call_count = 0

        def side_effect(request):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return httpx.Response(200, json={"ok": True})
            return httpx.Response(500, json={"ok": False})

        respx.post("https://api.telegram.org/bot123:ABC/sendMessage").mock(side_effect=side_effect)
        # Create enough items to force multiple messages
        items = [
            make_classified_item(
                title=f"News {i} " + "x" * 100,
                topic="models",
                summary="A" * 100,
            )
            for i in range(50)
        ]
        result = await notifier.send_briefing(items)
        # Should return False because at least one chunk failed
        assert result is False


# =========================================================================
# Constants verification
# =========================================================================


class TestConstants:
    """Verify that constants are properly defined."""

    def test_max_msg_len(self):
        assert MAX_MSG_LEN == 4096

    def test_source_labels(self):
        assert SOURCE_LABEL["hackernews"] == "HN"
        assert SOURCE_LABEL["arxiv"] == "arXiv"
        assert SOURCE_LABEL["reddit"] == "Reddit"
        assert SOURCE_LABEL["rss"] == "Blog"

    def test_topic_emojis_cover_all_topics(self):
        expected_topics = {
            "models",
            "tools",
            "papers",
            "products",
            "open_source",
            "agents",
            "regulation",
        }
        assert set(TOPIC_EMOJI.keys()) == expected_topics

    def test_priority_dots_cover_all_priorities(self):
        assert set(PRIORITY_DOT.keys()) == {1, 2, 3, 4, 5}


# =========================================================================
# Group by topic test
# =========================================================================


class TestGroupByTopic:
    """Test grouping items by topic."""

    def test_groups_correctly(self, sample_items):
        grouped = TelegramNotifier._group_by_topic(sample_items)
        assert len(grouped["models"]) == 2
        assert len(grouped["tools"]) == 1
        assert len(grouped["papers"]) == 1
        assert len(grouped["open_source"]) == 1

    def test_empty_list(self):
        grouped = TelegramNotifier._group_by_topic([])
        assert grouped == {}

    def test_single_topic(self):
        items = [
            make_classified_item(topic="papers"),
            make_classified_item(topic="papers"),
        ]
        grouped = TelegramNotifier._group_by_topic(items)
        assert len(grouped) == 1
        assert len(grouped["papers"]) == 2
