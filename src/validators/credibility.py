"""Credibility validator for classified news items.

Validates items through domain trust checks, SSRF-safe URL verification,
source credibility weighting, engagement scoring, tone analysis, noise
filtering, and Jaccard-similarity deduplication.
"""

from __future__ import annotations

import asyncio
import re
from urllib.parse import urlparse

import httpx

from src.classifiers.base import ClassifiedItem
from src.core.config import get_settings
from src.core.logging import get_logger
from src.core.ssrf import is_safe_url as _is_safe_url
from src.validators.base import BaseValidator

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
_HEADERS = {"User-Agent": "AI-News-Validator/1.0"}
_MAX_CONTENT_BYTES = 4096
_JACCARD_THRESHOLD = 0.65
_URL_TIMEOUT = 5.0
_SEMAPHORE_LIMIT = 5

_STOPWORDS = frozenset(
    {
        # English
        "the",
        "a",
        "an",
        "is",
        "are",
        "was",
        "were",
        "be",
        "been",
        "being",
        "have",
        "has",
        "had",
        "do",
        "does",
        "did",
        "will",
        "would",
        "could",
        "should",
        "may",
        "might",
        "shall",
        "can",
        "to",
        "of",
        "in",
        "for",
        "on",
        "with",
        "at",
        "by",
        "from",
        "as",
        "into",
        "through",
        "during",
        "before",
        "after",
        "above",
        "below",
        "between",
        "out",
        "off",
        "over",
        "under",
        "again",
        "further",
        "then",
        "once",
        "and",
        "but",
        "or",
        "nor",
        "not",
        "so",
        "yet",
        "both",
        "each",
        "few",
        "more",
        "most",
        "other",
        "some",
        "such",
        "no",
        "only",
        "own",
        "same",
        "than",
        "too",
        "very",
        "just",
        "about",
        "up",
        "its",
        "it",
        "this",
        "that",
        "these",
        "those",
        "i",
        "me",
        "my",
        "we",
        "our",
        "you",
        "your",
        "he",
        "him",
        "his",
        "she",
        "her",
        "they",
        "them",
        "their",
        "what",
        "which",
        "who",
        "whom",
        "how",
        "when",
        "where",
        "why",
        "all",
        "if",
        "there",
        "here",
        # Spanish
        "el",
        "la",
        "los",
        "las",
        "un",
        "una",
        "unos",
        "unas",
        "de",
        "del",
        "en",
        "con",
        "por",
        "para",
        "al",
        "es",
        "son",
        "fue",
        "ser",
        "como",
        "mas",
        "pero",
        "su",
        "sus",
        "se",
        "le",
        "lo",
        "que",
        "y",
        "o",
        "e",
        "ni",
        "si",
        "ya",
        "ha",
        "han",
        "hay",
        # AI-domain common words that inflate Jaccard similarity
        "ai",
        "model",
        "new",
        "data",
        "using",
        "based",
        "learning",
    }
)

_SOURCE_CREDIBILITY: dict[str, float] = {
    "arxiv": 0.3,
    "rss": 0.25,
    "hackernews": 0.2,
    "github": 0.2,
    "github_search": 0.2,
    "huggingface": 0.2,
    "reddit": 0.1,
}

_ENGAGEMENT_THRESHOLDS: list[tuple[int, float]] = [
    (500, 1.0),
    (200, 0.7),
    (50, 0.5),
    (10, 0.3),
    (0, 0.1),
]

# Tone analysis patterns
_SUSPICIOUS_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\b(shocking|unbelievable|you won'?t believe)\b", re.IGNORECASE),
    re.compile(r"\b(miracle|secret|conspiracy)\b", re.IGNORECASE),
    re.compile(r"\b(act now|limited time|don'?t miss)\b", re.IGNORECASE),
    re.compile(r"[!]{2,}"),  # Multiple exclamation marks
    re.compile(r"[A-Z]{5,}"),  # Excessive caps (5+ consecutive uppercase letters)
]

_PROFESSIONAL_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\b(research|study|findings|published)\b", re.IGNORECASE),
    re.compile(r"\b(according to|researchers|scientists|engineers)\b", re.IGNORECASE),
    re.compile(r"\b(paper|journal|conference|proceedings)\b", re.IGNORECASE),
    re.compile(r"\b(analysis|methodology|experiment|evaluation)\b", re.IGNORECASE),
    re.compile(r"\b(announcement|release|update|version)\b", re.IGNORECASE),
]


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------
def _extract_domain(url: str) -> str | None:
    """Extract the hostname from a URL, returning None on failure."""
    try:
        parsed = urlparse(url)
        return parsed.hostname
    except Exception:
        return None


def _score_engagement(item: ClassifiedItem) -> float:
    """Score engagement based on the item's score using tiered thresholds."""
    score = item.item.score or 0
    for threshold, value in _ENGAGEMENT_THRESHOLDS:
        if score >= threshold:
            return value
    return 0.1  # pragma: no cover — fallback (0 threshold always matches)


def _analyze_news_tone(item: ClassifiedItem) -> float:
    """Analyze the tone of the item's title and text.

    Returns a score adjustment: negative for suspicious patterns,
    positive for professional patterns.
    """
    content = (item.item.title or "") + " " + (item.item.text or "")[:500]
    adjustment = 0.0

    for pattern in _SUSPICIOUS_PATTERNS:
        if pattern.search(content):
            adjustment -= 0.1

    for pattern in _PROFESSIONAL_PATTERNS:
        if pattern.search(content):
            adjustment += 0.05

    return adjustment


def _tokenize(text: str) -> set[str]:
    """Tokenize text into a set of lowercased words with stopwords removed."""
    words = set(re.findall(r"[a-zA-Z0-9]+", text.lower()))
    return words - _STOPWORDS


def _jaccard_similarity(text_a: str, text_b: str) -> float:
    """Compute Jaccard similarity between two texts after tokenization."""
    tokens_a = _tokenize(text_a)
    tokens_b = _tokenize(text_b)
    if not tokens_a or not tokens_b:
        return 0.0
    intersection = tokens_a & tokens_b
    union = tokens_a | tokens_b
    return len(intersection) / len(union)


def _is_duplicate_or_similar(
    candidate: ClassifiedItem,
    existing: list[ClassifiedItem],
) -> bool:
    """Check if a candidate item is a duplicate of any existing item.

    Uses Jaccard similarity on title + first 200 chars of text.
    """
    candidate_text = (candidate.item.title or "") + " " + (candidate.item.text or "")[:200]
    for item in existing:
        item_text = (item.item.title or "") + " " + (item.item.text or "")[:200]
        if _jaccard_similarity(candidate_text, item_text) >= _JACCARD_THRESHOLD:
            return True
    return False


async def _verify_url_content(url: str, client: httpx.AsyncClient) -> float:
    """Verify that a URL is accessible via HEAD request.

    Returns a bonus score: 0.1 if accessible, 0.0 if not.
    """
    try:
        response = await client.head(
            url,
            headers=_HEADERS,
            timeout=_URL_TIMEOUT,
            follow_redirects=False,
        )
        if response.status_code < 400:
            return 0.1
    except (httpx.HTTPError, httpx.TimeoutException):
        pass
    return 0.0


# ---------------------------------------------------------------------------
# Credibility Validator
# ---------------------------------------------------------------------------
class CredibilityValidator(BaseValidator):
    """Validates news items for credibility, filtering low-quality content.

    Scoring components:
    - Source credibility weight (arxiv=0.3, rss=0.25, hackernews=0.1, reddit=0.05)
    - Domain trust bonus (+0.3 for trusted domains)
    - Engagement score bonus (tiered from item score)
    - URL verification bonus (+0.1 for accessible URLs)
    - Tone analysis adjustment (suspicious -0.1 each, professional +0.05 each)

    Filtering:
    - Remove items with credibility < 0.3
    - Remove low engagement items (score < 5) from HackerNews/Reddit
    - Jaccard similarity dedup (threshold 0.65) with EN+ES+AI stopwords
    """

    async def validate(self, items: list[ClassifiedItem]) -> list[ClassifiedItem]:
        """Validate a batch of classified items.

        Sets credibility_score and filters out low-quality/duplicate items.
        """
        settings = get_settings()
        if not settings.enable_news_validation:
            logger.info("validation_skipped", reason="disabled")
            return items

        if not items:
            return items

        # Score credibility for all items
        scored = await self._validate_batch(items)
        # Filter noise and deduplicate
        filtered = self._filter_noise(scored)

        logger.info(
            "validation_complete",
            input_count=len(items),
            output_count=len(filtered),
            filtered_out=len(items) - len(filtered),
        )
        return filtered

    async def _validate_batch(
        self,
        items: list[ClassifiedItem],
    ) -> list[ClassifiedItem]:
        """Score credibility for all items concurrently with a semaphore."""
        semaphore = asyncio.Semaphore(_SEMAPHORE_LIMIT)

        async with httpx.AsyncClient() as client:

            async def _validate_one(item: ClassifiedItem) -> ClassifiedItem:
                async with semaphore:
                    return await self._validate_item(item, client)

            results = await asyncio.gather(
                *[_validate_one(item) for item in items],
            )

        return list(results)

    async def _validate_item(
        self,
        item: ClassifiedItem,
        client: httpx.AsyncClient,
    ) -> ClassifiedItem:
        """Compute credibility score for a single item."""
        settings = get_settings()
        score = 0.0

        # 1. Source credibility weight
        source = item.item.source.lower()
        score += _SOURCE_CREDIBILITY.get(source, 0.05)

        # 2. Domain trust check
        if item.item.url:
            domain = _extract_domain(item.item.url)
            if domain:
                trusted_domains = settings.trusted_news_domains_list
                for trusted in trusted_domains:
                    if domain == trusted or domain.endswith("." + trusted):
                        score += 0.3
                        break

        # 3. Engagement score bonus
        engagement = _score_engagement(item)
        score += engagement * 0.2  # Scale engagement contribution

        # 4. URL verification (SSRF-safe)
        if item.item.url and await _is_safe_url(item.item.url):
            url_bonus = await _verify_url_content(item.item.url, client)
            score += url_bonus

        # 5. Tone analysis
        tone_adjustment = _analyze_news_tone(item)
        score += tone_adjustment

        # Clamp to [0.0, 1.0]
        item.credibility_score = max(0.0, min(1.0, score))

        logger.debug(
            "item_validated",
            title=item.item.title[:60],
            source=item.item.source,
            credibility=item.credibility_score,
        )
        return item

    def _filter_noise(self, items: list[ClassifiedItem]) -> list[ClassifiedItem]:
        """Remove low-quality items and deduplicate by Jaccard similarity.

        Filtering rules:
        1. Remove items with credibility_score < 0.4
        2. Remove low-engagement items (score < 5) from HackerNews/Reddit
        3. Jaccard dedup: remove items similar to already-accepted items
        """
        accepted: list[ClassifiedItem] = []

        for item in items:
            # Rule 1: credibility threshold
            if (item.credibility_score or 0.0) < 0.3:
                logger.debug(
                    "item_filtered_low_credibility",
                    title=item.item.title[:60],
                    credibility=item.credibility_score,
                )
                continue

            # Rule 2: low engagement filter for social sources.
            # The leading-indicator lane is exempt: those items arrive at 0
            # points by design and rely on the authoritative-domain allowlist
            # as their quality gate instead of engagement.
            source = item.item.source.lower()
            is_leading = item.item.metadata.get("lane") == "leading"
            if source in ("hackernews", "reddit") and not is_leading:
                item_score = item.item.score or 0
                if item_score < 5:
                    logger.debug(
                        "item_filtered_low_engagement",
                        title=item.item.title[:60],
                        source=source,
                        score=item_score,
                    )
                    continue

            # Rule 3: Jaccard dedup
            if _is_duplicate_or_similar(item, accepted):
                logger.debug(
                    "item_filtered_duplicate",
                    title=item.item.title[:60],
                )
                continue

            accepted.append(item)

        return accepted
