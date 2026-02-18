"""Event deduplication: groups items covering the same event within each topic.

Uses LLM to identify items about the same event, picks the best item per
group, and marks winners as trending with a priority boost. Falls back
gracefully to keeping all items if LLM fails.
"""

from __future__ import annotations

import json
import re

import openai

from src.classifiers.base import ClassifiedItem
from src.classifiers.llm import SYSTEM_MESSAGE, llm_call
from src.core.config import get_settings
from src.core.logging import get_logger

logger = get_logger(__name__)


def _build_dedup_prompt(items: list[ClassifiedItem]) -> str:
    """Build prompt asking LLM to group items by event."""
    items_lines: list[str] = []
    for i, ci in enumerate(items):
        items_lines.append(
            f"[{i}] {ci.item.title} (source: {ci.item.source}, "
            f"score: {ci.item.score or 0}, relevance: {ci.relevance_score:.2f})"
        )
    items_text = "\n".join(items_lines)

    header = (
        f"Agrupa estos {len(items)} items por EVENTO. "
        "Items sobre el mismo evento/noticia van juntos."
    )
    instructions = (
        "Responde SOLO con un JSON array de arrays. "
        "Cada sub-array contiene los indices de items sobre el MISMO evento.\n"
        "Items que NO comparten evento van solos en su propio sub-array."
    )
    return f"""{header}

Items:
{items_text}

{instructions}

Ejemplo: [[0,3,5], [1], [2,4]]

JSON:"""


def _parse_groups(raw: str) -> list[list[int]] | None:
    """Parse grouping response from LLM. Returns None on failure."""
    cleaned = raw.strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    cleaned = cleaned.strip()

    # Try direct parse
    try:
        result = json.loads(cleaned)
        if isinstance(result, list) and all(isinstance(g, list) for g in result):
            return result
    except json.JSONDecodeError:
        pass

    # Fallback: extract outermost array (first '[' to last ']')
    start = cleaned.find("[")
    end = cleaned.rfind("]")
    if start != -1 and end > start:
        try:
            result = json.loads(cleaned[start : end + 1])
            if isinstance(result, list) and all(isinstance(g, list) for g in result):
                return result
        except json.JSONDecodeError:
            pass

    return None


def _pick_winner(group: list[ClassifiedItem]) -> ClassifiedItem:
    """Pick the best item from a group based on score + relevance.

    The winner gets trending=True and a priority boost of -1.
    """
    best = max(
        group,
        key=lambda ci: (ci.item.score or 0) + ci.relevance_score * 100,
    )
    best.trending = True
    best.source_count = len(group)
    best.priority = max(1, best.priority - 1)
    return best


async def deduplicate_events(
    items: list[ClassifiedItem],
    client: openai.AsyncOpenAI | None = None,
) -> list[ClassifiedItem]:
    """Deduplicate items by event within each topic.

    Groups items covering the same event using LLM, picks the best item
    per group (highest score + relevance), marks it as trending with
    priority boost.

    On LLM failure, returns all items unchanged (graceful fallback).

    Args:
        items: Classified items to deduplicate.
        client: Optional pre-configured OpenAI client (for testing).

    Returns:
        Deduplicated list of classified items.
    """
    if not items:
        return []

    settings = get_settings()

    if client is None:
        client = openai.AsyncOpenAI(
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url,
        )

    model = settings.openai_model

    # Group items by topic
    by_topic: dict[str, list[ClassifiedItem]] = {}
    for ci in items:
        by_topic.setdefault(ci.topic, []).append(ci)

    results: list[ClassifiedItem] = []

    for topic, topic_items in by_topic.items():
        if len(topic_items) <= 1:
            results.extend(topic_items)
            continue

        try:
            deduped = await _deduplicate_topic(client, model, topic_items)
            results.extend(deduped)
        except Exception:
            logger.warning(
                "event_dedup_failed_keeping_all",
                topic=topic,
                item_count=len(topic_items),
                exc_info=True,
            )
            results.extend(topic_items)

    return results


async def _deduplicate_topic(
    client: openai.AsyncOpenAI,
    model: str,
    topic_items: list[ClassifiedItem],
) -> list[ClassifiedItem]:
    """Deduplicate items within a single topic using LLM grouping."""
    prompt = _build_dedup_prompt(topic_items)
    raw_response = await llm_call(client, model, SYSTEM_MESSAGE, prompt)
    groups = _parse_groups(raw_response)

    if groups is None:
        logger.warning("event_dedup_parse_failed_keeping_all", item_count=len(topic_items))
        return list(topic_items)

    # Validate indices
    all_indices = set()
    valid_groups: list[list[int]] = []
    for group in groups:
        valid_indices = [
            idx for idx in group if isinstance(idx, int) and 0 <= idx < len(topic_items)
        ]
        if valid_indices:
            valid_groups.append(valid_indices)
            all_indices.update(valid_indices)

    # Any items not covered by groups get added individually
    results: list[ClassifiedItem] = []
    for group_indices in valid_groups:
        group_items = [topic_items[idx] for idx in group_indices]
        if len(group_items) == 1:
            results.append(group_items[0])
        else:
            winner = _pick_winner(group_items)
            results.append(winner)

    # Add orphaned items (not mentioned in any group)
    for i, item in enumerate(topic_items):
        if i not in all_indices:
            results.append(item)

    return results
