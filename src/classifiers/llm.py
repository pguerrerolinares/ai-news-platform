"""LLM-based classifier using OpenAI-compatible API (Kimi/Moonshot).

Batches items into groups of BATCH_SIZE, sends English prompts for
classification, and falls back to KeywordClassifier on failure.
"""

from __future__ import annotations

import asyncio
import json
import random
import re

import openai

from src.classifiers.base import BaseClassifier, ClassifiedItem
from src.classifiers.keyword import (
    TOPIC_DEFINITIONS,
    KeywordClassifier,
    _calculate_priority,
)
from src.core.config import get_settings
from src.core.logging import get_logger
from src.extractors.base import ExtractedItem

logger = get_logger(__name__)

BATCH_SIZE = 10
MAX_RETRIES = 5
RETRY_BACKOFF = [2, 5, 15, 30]

SYSTEM_MESSAGE = (
    "You are an AI news classifier. " "Respond ONLY with a valid JSON array, no additional text."
)

# Retry-eligible exceptions
_RETRYABLE_ERRORS = (
    openai.RateLimitError,
    openai.APITimeoutError,
    openai.APIConnectionError,
)


async def llm_call(
    client: openai.AsyncOpenAI,
    model: str,
    system: str,
    prompt: str,
) -> str:
    """Call the LLM with retry logic for transient errors.

    Retries up to MAX_RETRIES times on RateLimitError, APITimeoutError,
    and APIConnectionError with backoff [2, 5, 15, 30] seconds + 30% jitter.
    Other APIError subclasses are NOT retried.
    """
    last_error: Exception | None = None

    for attempt in range(MAX_RETRIES):
        try:
            response = await client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.1,
            )
            return response.choices[0].message.content or ""
        except _RETRYABLE_ERRORS as exc:
            last_error = exc
            if attempt < MAX_RETRIES - 1:
                wait = RETRY_BACKOFF[min(attempt, len(RETRY_BACKOFF) - 1)]
                jitter = random.uniform(0, wait * 0.3)  # noqa: S311  # nosec B311
                logger.warning(
                    "llm_call_retry",
                    attempt=attempt + 1,
                    error=str(exc),
                    wait_seconds=round(wait + jitter, 1),
                )
                await asyncio.sleep(wait + jitter)
            else:
                logger.error(
                    "llm_call_retries_exhausted",
                    attempts=MAX_RETRIES,
                    error=str(exc),
                )
        except openai.APIError:
            raise

    msg = f"LLM call failed after {MAX_RETRIES} retries"
    raise last_error or RuntimeError(msg)


def _parse_llm_json(raw: str) -> list[dict]:
    """Parse JSON from LLM response, handling code fences and extracting arrays."""
    # Strip code fences
    cleaned = raw.strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    cleaned = cleaned.strip()

    # Try direct parse
    try:
        result = json.loads(cleaned)
        if isinstance(result, list):
            return result
    except json.JSONDecodeError:
        pass

    # Fallback: extract outermost array (first '[' to last ']')
    start = cleaned.find("[")
    end = cleaned.rfind("]")
    if start != -1 and end > start:
        try:
            result = json.loads(cleaned[start : end + 1])
            if isinstance(result, list):
                return result
        except json.JSONDecodeError:
            pass

    return []


def _build_prompt(batch: list[ExtractedItem], topics_info: str) -> str:
    """Build the classification prompt for a batch of items."""
    items_lines: list[str] = []
    for i, item in enumerate(batch):
        text_preview = (item.text or "")[:200]
        items_lines.append(
            f"\n[{i}] title: {item.title}\n"
            f"    source: {item.source} | score: {item.score or 0}\n"
            f"    text: {text_preview}"
        )
    items_text = "".join(items_lines)

    return f"""Classify these {len(batch)} items. BE STRICT with is_news.

REJECT (is_news=false):
- Opinions, rants, personal stories, career/job discussions
- Generic tips, basic tutorials, beginner questions
- Content unrelated to AI/ML/LLM (child safety, photography, etc.)
- Memes, spam, trivial content without technical substance

ACCEPT (is_news=true):
- Model launches, AI tools, AI products
- Papers with clear technical contribution
- AI company news (OpenAI, Google, Meta, Anthropic, etc.)
- Technical advances, benchmarks, open source releases

RELEVANCE SCORING — you MUST use the full range. Each item gets ONE score.
Score by comparing against these real-world anchors:

1.0  = "OpenAI releases GPT-5 with 2x performance on all benchmarks"
0.95 = "Meta open-sources Llama 4 405B model weights"
0.90 = "Google DeepMind publishes new SOTA on protein folding"
0.85 = "New framework reaches #1 on GitHub trending with 10K stars in a day"
0.80 = "Incremental update to an existing popular tool"
0.75 = "Niche library or minor paper with limited audience"
<0.75: Reject (is_news=false)

FORCED DISTRIBUTION: In a batch of {len(batch)} items, you MUST NOT give more than
3 items the same score. Spread your scores across the range.

DISAMBIGUATION RULES:
- arXiv preprint without code/weights release -> "papers" (NOT "models")
- Model with published weights on HuggingFace/GitHub -> "models"
- Paper about agents/tool-use -> "agents" (NOT "papers")
- Consumer product (ChatGPT feature, Claude update) -> "products" (NOT "models")

Topics:
{topics_info}

Items:{items_text}

SUMMARY - MAX 25 words in English:
- Do NOT repeat the title: add context
- If paper: mention main result
- If release: mention key improvement
GOOD: "New MoE 397B params, 17B active; surpasses Llama 3.1 on MMLU and code"
BAD: "New model release" (too vague)

JSON array. relevance: 0.75-1.0 per scale above.
[
  {{"idx": 0, "is_news": true, "topic": "models",
    "relevance": 0.85, "summary": "Short phrase in English max 25 words"}},
  {{"idx": 1, "is_news": false}},
  ...
]"""


class LLMClassifier(BaseClassifier):
    """LLM-based content classifier using OpenAI-compatible API.

    Batches items for classification, uses English prompts with exact
    topic definitions and relevance scale. Falls back to KeywordClassifier
    on failure.
    """

    def __init__(self, client: openai.AsyncOpenAI | None = None) -> None:
        """Initialize with optional pre-configured client (useful for testing)."""
        self._client = client
        self._fallback = KeywordClassifier()

    def _get_client(self) -> openai.AsyncOpenAI:
        """Get or create the OpenAI client, caching it for connection-pool reuse."""
        if self._client is None:
            settings = get_settings()
            self._client = openai.AsyncOpenAI(
                api_key=settings.openai_api_key,
                base_url=settings.openai_base_url,
            )
        return self._client

    async def classify(self, items: list[ExtractedItem]) -> list[ClassifiedItem]:
        """Classify items using LLM with fallback to keyword classifier."""
        if not items:
            return []

        settings = get_settings()
        enabled_topics = settings.topics_list
        min_relevance = settings.min_relevance_score

        # Build topics info string
        topics_info = "\n".join(
            f'- "{topic}": {data["description"]}'
            for topic, data in TOPIC_DEFINITIONS.items()
            if topic in enabled_topics
        )

        client = self._get_client()
        model = settings.openai_model

        # Process batches concurrently, bounded to 3 in-flight to respect rate limits
        sem = asyncio.Semaphore(3)
        starts = list(range(0, len(items), BATCH_SIZE))

        async def _bounded(batch_start: int) -> list[ClassifiedItem]:
            batch = items[batch_start : batch_start + BATCH_SIZE]
            async with sem:
                try:
                    return await self._classify_batch(
                        client, model, batch, topics_info, enabled_topics, min_relevance
                    )
                except Exception:
                    logger.warning(
                        "llm_batch_failed_using_fallback",
                        batch_start=batch_start,
                        batch_size=len(batch),
                        exc_info=True,
                    )
                    return await self._fallback.classify(batch)

        batches: list[list[ClassifiedItem]] = await asyncio.gather(*[_bounded(s) for s in starts])
        all_results: list[ClassifiedItem] = [item for batch in batches for item in batch]
        return all_results

    async def _classify_batch(
        self,
        client: openai.AsyncOpenAI,
        model: str,
        batch: list[ExtractedItem],
        topics_info: str,
        enabled_topics: list[str],
        min_relevance: float,
    ) -> list[ClassifiedItem]:
        """Classify a single batch via LLM."""
        prompt = _build_prompt(batch, topics_info)
        raw_response = await llm_call(client, model, SYSTEM_MESSAGE, prompt)
        parsed = _parse_llm_json(raw_response)

        results: list[ClassifiedItem] = []
        for entry in parsed:
            idx = entry.get("idx")
            is_news = entry.get("is_news", False)

            if idx is None or not isinstance(idx, int) or idx < 0 or idx >= len(batch):
                continue

            if not is_news:
                continue

            topic = entry.get("topic", "")
            relevance = float(entry.get("relevance", 0.0))
            summary = entry.get("summary")

            if topic not in enabled_topics:
                continue

            if relevance < min_relevance:
                continue

            item = batch[idx]
            priority = _calculate_priority(item, relevance)

            results.append(
                ClassifiedItem(
                    item=item,
                    topic=topic,
                    relevance_score=relevance,
                    summary=summary,
                    priority=priority,
                    classifier="llm",
                )
            )

        return results
