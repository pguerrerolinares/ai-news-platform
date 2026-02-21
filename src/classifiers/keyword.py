"""Keyword-based classifier (pure computation, no external dependencies).

Uses word-boundary regex matching against 7 topic keyword maps to assign
topic and relevance score. Acts as a fast fallback when the LLM classifier
is unavailable.
"""

from __future__ import annotations

import re

from src.classifiers.base import BaseClassifier, ClassifiedItem
from src.core.config import get_settings
from src.extractors.base import ExtractedItem

# ---------------------------------------------------------------------------
# Topic definitions with keyword lists
# ---------------------------------------------------------------------------
TOPIC_DEFINITIONS: dict[str, dict[str, list[str] | str]] = {
    "modelos": {
        "keywords": [
            "GPT",
            "LLM",
            "model",
            "foundation model",
            "benchmark",
            "MMLU",
            "training",
            "fine-tuning",
            "weights",
            "parameters",
            "transformer",
            "diffusion",
            "multimodal",
            "vision language",
            "Llama",
            "Mistral",
            "Gemini",
            "Claude",
            "Qwen",
            "DeepSeek",
            "SOTA",
            "perplexity",
            "architecture",
            "attention",
            "context window",
            "token",
        ],
        "description": "Nuevos modelos, arquitecturas, benchmarks, entrenamientos",
    },
    "herramientas": {
        "keywords": [
            "framework",
            "library",
            "SDK",
            "API",
            "platform",
            "tool",
            "LangChain",
            "LlamaIndex",
            "HuggingFace",
            "vLLM",
            "Ollama",
            "deployment",
            "inference",
            "serving",
            "MLOps",
            "vector database",
            "embedding",
            "RAG pipeline",
            "prompt engineering",
            "eval",
        ],
        "description": "Frameworks, librerias, plataformas, herramientas de desarrollo",
    },
    "papers": {
        "keywords": [
            "paper",
            "research",
            "arxiv",
            "study",
            "findings",
            "novel",
            "approach",
            "method",
            "algorithm",
            "SOTA",
            "state-of-the-art",
            "NeurIPS",
            "ICML",
            "ICLR",
            "ACL",
            "EMNLP",
            "CVPR",
            "experiment",
            "ablation",
            "preprint",
        ],
        "description": "Papers academicos, investigacion, nuevos metodos",
    },
    "productos": {
        "keywords": [
            "launch",
            "release",
            "product",
            "feature",
            "update",
            "app",
            "ChatGPT",
            "Claude",
            "Gemini",
            "Copilot",
            "assistant",
            "pricing",
            "API",
            "beta",
            "GA",
            "general availability",
            "subscription",
            "enterprise",
            "consumer",
        ],
        "description": "Lanzamientos de productos, features, actualizaciones",
    },
    "open_source": {
        "keywords": [
            "open source",
            "open-source",
            "OSS",
            "GitHub",
            "weights",
            "MIT",
            "Apache",
            "license",
            "community",
            "Llama",
            "Mistral",
            "Qwen",
            "DeepSeek",
            "Falcon",
            "self-hosted",
            "local",
            "on-premise",
        ],
        "description": "Releases open source, modelos abiertos, codigo liberado",
    },
    "agentes": {
        "keywords": [
            "agent",
            "agentic",
            "MCP",
            "tool use",
            "function calling",
            "autonomous",
            "workflow",
            "orchestration",
            "multi-agent",
            "reasoning",
            "planning",
            "code generation",
            "computer use",
            "browser use",
            "automation",
            "chain of thought",
        ],
        "description": "Agentes de IA, automatizacion, MCP, workflows",
    },
    "regulacion": {
        "keywords": [
            "regulation",
            "policy",
            "law",
            "ban",
            "safety",
            "alignment",
            "ethics",
            "bias",
            "EU",
            "AI Act",
            "executive order",
            "governance",
            "responsible",
            "risk",
            "compliance",
            "copyright",
            "deepfake",
            "misinformation",
        ],
        "description": "Regulacion, etica, seguridad, politicas de IA",
    },
}

# ---------------------------------------------------------------------------
# Priority thresholds based on engagement score
# ---------------------------------------------------------------------------
_SCORE_THRESHOLDS: list[tuple[int, int]] = [(500, 1), (200, 2), (50, 3), (10, 4)]


def _calculate_priority(item: ExtractedItem, relevance: float) -> int:
    """Calculate priority (1-5) from item engagement score, relevance, and source."""
    priority_score = 5
    for threshold, value in _SCORE_THRESHOLDS:
        if (item.score or 0) > threshold:
            priority_score = value
            break

    if relevance >= 0.95:
        priority_score -= 2
    elif relevance >= 0.9:
        priority_score -= 1
    elif relevance <= 0.75:
        priority_score += 1

    if item.source in ("rss", "arxiv"):
        priority_score -= 1

    return max(1, min(5, priority_score))


def classify_by_keywords(item: ExtractedItem) -> tuple[str | None, float]:
    """Classify a single item by keyword matching.

    Returns:
        Tuple of (topic, relevance_score) or (None, 0.0) if no match.
    """
    text = f"{item.title} {(item.text or '')[:500]}".lower()
    scores: dict[str, float] = {}

    for topic, data in TOPIC_DEFINITIONS.items():
        keywords = data["keywords"]
        if not isinstance(keywords, list):
            continue
        score = 0
        for keyword in keywords:
            pattern = r"\b" + re.escape(keyword.lower()) + r"\b"
            if re.search(pattern, text):
                score += 1
        scores[topic] = score / len(keywords)

    if scores:
        best_topic = max(scores, key=lambda k: scores[k])
        score = min(scores[best_topic] * 3, 1.0)
        if score < 0.1:
            return None, 0.0
        return best_topic, score

    return None, 0.0


class KeywordClassifier(BaseClassifier):
    """Keyword-based classifier using word-boundary regex matching.

    Pure computation, no external dependencies. Serves as fallback
    when the LLM classifier is unavailable.
    """

    async def classify(self, items: list[ExtractedItem]) -> list[ClassifiedItem]:
        """Classify items by keyword matching.

        Filters by min_relevance_score and enabled topics from settings.
        """
        settings = get_settings()
        min_relevance = settings.min_relevance_score
        enabled_topics = settings.topics_list

        results: list[ClassifiedItem] = []
        for item in items:
            topic, relevance = classify_by_keywords(item)

            if topic is None or relevance < min_relevance:
                continue

            if topic not in enabled_topics:
                continue

            priority = _calculate_priority(item, relevance)

            results.append(
                ClassifiedItem(
                    item=item,
                    topic=topic,
                    relevance_score=relevance,
                    summary=None,
                    priority=priority,
                )
            )

        return results
