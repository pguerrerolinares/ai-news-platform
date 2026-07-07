"""Smoke guard: datetime-granularity in the seen/timestamp invalidation gate.

Bug class under test (onyx #11913): an incremental-ingestion invalidation
mechanism that keys purely on "have I seen this identity before, within a
window" -- without ever checking whether the *content* changed -- silently
drops a legitimate update to a source that happens on the same day (or any
day within the window) as the original ingestion.

`filter_already_seen` (src/pipeline/stages/seen_filter.py) is the pipeline's
timestamp-windowed "seen" gate: Pass 1 filters any candidate whose url_hash
already exists in the DB within `seen_window_days`. url_hash is
sha256(url) only (src/extractors/base.py) -- it carries no content or
timestamp signal, so a second extraction of the *same URL* with materially
different content (e.g. a source updates its own article the same day) is
filtered identically to an untouched repeat, and the update never reaches
storage/classification.

RED  = the updated version is silently dropped (bug class present).
GREEN = the updated version is still surfaced (already guarded).
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from src.extractors.base import ExtractedItem
from src.pipeline.stages.seen_filter import filter_already_seen


def _mock_session_two_queries(
    url_content_pairs: list[tuple[str, str | None]], titles: list[str]
) -> AsyncMock:
    """Mock session that returns (url_hash, content_hash) rows on first
    execute, titles on second.

    Mirrors the helper in tests/unit/test_seen_filter.py to match repo style.
    `url_content_pairs` models DB rows matched by url_hash within the seen
    window, paired with their stored content_hash -- the signal
    filter_already_seen() needs to tell an unchanged duplicate from a
    same-day content update.
    """
    session = AsyncMock()

    result_url = MagicMock()
    result_url.all.return_value = url_content_pairs

    result_titles = MagicMock()
    result_titles.scalars.return_value.all.return_value = titles

    session.execute = AsyncMock(side_effect=[result_url, result_titles])
    return session


class TestSameDayUpdateGuard:
    async def test_same_url_updated_same_day_is_not_silently_dropped(self):
        """A source updates the SAME url later the SAME calendar day; the new
        version must still surface, not be dropped purely because its
        url_hash already exists within the seen window.
        """
        url = "https://example.com/breaking-news"

        # Morning: original article ingested and stored -- its url_hash is
        # now present in the DB within the seen window.
        original = ExtractedItem(title="Company X announces plans", source="rss", url=url)

        # Afternoon, same calendar day: the source edits the same URL with
        # materially different content (this is the "second update, same
        # day" the bug class is about).
        updated = ExtractedItem(
            title="UPDATED: Company X announces plans, adds pricing and date",
            source="rss",
            url=url,
        )
        assert original.url_hash == updated.url_hash  # sanity: identical identity key

        # DB already has this url_hash stored from the morning run, with the
        # ORIGINAL content_hash -- the afternoon update's content_hash differs.
        session = _mock_session_two_queries([(updated.url_hash, original.content_hash)], [])

        with patch("src.pipeline.stages.seen_filter.get_settings") as mock_settings:
            mock_settings.return_value.seen_window_days = 7
            result = await filter_already_seen(session, [updated])

        assert len(result) == 1, (
            "seen_filter silently dropped a same-day content update: it "
            "matches purely on url_hash presence within the seen window, "
            "blind to whether the content actually changed. This is the "
            "timestamp/identity-invalidation granularity bug (onyx #11913 "
            "class) -- a real update on the same day as the original "
            "ingestion is lost with no signal to the pipeline."
        )
