"""Benchmark the production LLM classifier against a hand-labeled dataset,
reproducing the recall/false-positive/cost metrics from
docs/adr/003-llm-kimi-k26-fail-loud.md.

The hand-labeled dataset used for ADR-003 (166 items, single annotator) is NOT
in the repo. Supply your own as a JSONL file, one item per line:

    {"title": "...", "text": "...", "url": "...", "source": "...", "label": "news"}

Fields:
    title   (required) str
    text    (optional) str
    url     (optional) str -- stored for reference, not sent to the classifier
    source  (optional) str, defaults to "bench"
    label   (required) one of "news" / "not_news" / "ambiguous"
            ("ambiguous" is counted but excluded from recall/FP, same as ADR-003)

This script imports the production `LLMClassifier._classify_batch` from
`src.classifiers.llm` -- prompt, parser, AND the accept/reject decision
(is_news, enabled topic, relevance >= MIN_RELEVANCE_SCORE) -- so the bench
cannot drift from what the pipeline actually does. `--model` and the enabled
topics are explicit inputs; temperature/extra_body come from settings
(OPENAI_TEMPERATURE / OPENAI_EXTRA_BODY), same knobs production uses -- set
them to match whichever --model you're benchmarking (e.g. kimi-k3 requires
OPENAI_TEMPERATURE=1.0). A non-parseable LLM response raises `LLMParseError`
and aborts the run (fail-loud): ADR-003 measured "LLM only", so silently
falling back to keywords here would contaminate the metric.

Cost comes from the API-reported token usage (`response.usage`), captured by
wrapping the client (`UsageRecordingClient`) -- no change to production code.
It's multiplied by the model's published price (ADR-003). Cost prints "n/a"
if the API returned no usage, or the model has no listed price.

Usage:
    python scripts/bench_classifier.py --dataset labels.jsonl --model kimi-k2.6 --runs 2
    python scripts/bench_classifier.py --dataset synthetic.jsonl --dry-run  # no network, no API key
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import openai

from src.classifiers.keyword import TOPIC_DEFINITIONS
from src.classifiers.llm import BATCH_SIZE, LLMClassifier
from src.core.config import get_settings
from src.extractors.base import ExtractedItem

VALID_LABELS = {"news", "not_news", "ambiguous"}

# Published price per 1M tokens (input, output), from ADR-003. Unknown models
# print "n/a" for cost instead of guessing.
PRICING_PER_1M_USD: dict[str, tuple[float, float]] = {
    "kimi-k2.6": (0.95, 4.00),
    "kimi-k3": (3.00, 15.00),
}


@dataclass
class LabeledItem:
    """One dataset row: an item to classify plus its hand-assigned label."""

    item: ExtractedItem
    label: str


@dataclass
class RunScore:
    """Recall/FP/cost for a single run over the whole dataset."""

    news_total: int
    not_news_total: int
    ambiguous_total: int
    recall_on_news: float
    false_positives: int
    estimated_cost_usd: float | None


class FakeLLMClient:
    """Deterministic, network-free stand-in for `openai.AsyncOpenAI` (--dry-run).

    NOT a classifier: it exists to smoke-test the script's wiring (batching,
    prompt building, parsing, scoring, table rendering) without a real API
    key or network access. It alternates is_news True/False by item index --
    the resulting "metrics" are meaningless and must never be read as real
    benchmark numbers. Reports a deterministic fake `usage` (chars/4) so the
    dry-run also exercises the cost column.
    """

    def __init__(self) -> None:
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    async def _create(self, *, model: str, messages: list[dict], **_kwargs: Any) -> SimpleNamespace:
        user_prompt = messages[-1]["content"]
        n_items = user_prompt.count("<item_content idx=")
        fake_results = [
            {
                "idx": i,
                "is_news": i % 2 == 0,
                "topic": "models",
                "relevance": 0.85 if i % 2 == 0 else 0.0,
                "summary": "dry-run fake summary",
            }
            for i in range(n_items)
        ]
        content = json.dumps(fake_results)
        message = SimpleNamespace(content=content)
        choice = SimpleNamespace(message=message)
        usage = SimpleNamespace(
            prompt_tokens=len(user_prompt) // 4,
            completion_tokens=len(content) // 4,
        )
        return SimpleNamespace(choices=[choice], usage=usage)


class UsageRecordingClient:
    """Wraps an OpenAI-compatible client and accumulates token usage per run.

    The bench already injects the `client` used by `LLMClassifier`, so this
    captures real `response.usage` without touching production code (`llm_call`
    discards it). `usage_seen` stays False if the wrapped API never reports
    usage, so cost can print "n/a" instead of a silently-wrong zero.
    """

    def __init__(self, inner: Any) -> None:
        self._inner = inner
        self.prompt_tokens = 0
        self.completion_tokens = 0
        self.usage_seen = False
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    async def _create(self, **kwargs: Any) -> Any:
        response = await self._inner.chat.completions.create(**kwargs)
        usage = getattr(response, "usage", None)
        if usage is not None:
            self.usage_seen = True
            self.prompt_tokens += usage.prompt_tokens
            self.completion_tokens += usage.completion_tokens
        return response


def load_dataset(path: Path) -> list[LabeledItem]:
    """Load and validate a hand-labeled JSONL dataset (see module docstring)."""
    labeled: list[LabeledItem] = []
    with path.open(encoding="utf-8") as fh:
        for line_no, raw_line in enumerate(fh, start=1):
            line = raw_line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                msg = f"{path}:{line_no}: invalid JSON: {exc}"
                raise ValueError(msg) from exc

            label = row.get("label")
            if label not in VALID_LABELS:
                msg = (
                    f"{path}:{line_no}: label must be one of {sorted(VALID_LABELS)}, "
                    f"got {label!r}"
                )
                raise ValueError(msg)

            title = row.get("title")
            if not title:
                msg = f"{path}:{line_no}: missing required field 'title'"
                raise ValueError(msg)

            item = ExtractedItem(
                title=title,
                source=row.get("source") or "bench",
                url=row.get("url"),
                text=row.get("text"),
            )
            labeled.append(LabeledItem(item=item, label=label))
    return labeled


async def classify_dataset(
    labeled: list[LabeledItem],
    *,
    client: Any,
    model: str,
    enabled_topics: list[str],
    min_relevance: float,
    topics_info: str,
) -> dict[int, bool]:
    """Run production's `LLMClassifier._classify_batch` over the dataset.

    Batch by batch, using the exact same prompt, parser, and accept/reject
    decision (is_news, enabled topic, relevance >= min_relevance) production
    uses -- so the bench cannot silently accept what the pipeline rejects.
    `predictions[i]` is True iff item i was in the batch's accepted results.
    """
    items = [li.item for li in labeled]
    predictions: dict[int, bool] = {}
    classifier = LLMClassifier(client=client)

    for start in range(0, len(items), BATCH_SIZE):
        batch = items[start : start + BATCH_SIZE]
        accepted = await classifier._classify_batch(
            client, model, batch, topics_info, enabled_topics, min_relevance
        )
        accepted_ids = {id(r.item) for r in accepted}
        for local_idx, item in enumerate(batch):
            predictions[start + local_idx] = id(item) in accepted_ids

    return predictions


def score_run(
    labeled: list[LabeledItem],
    predictions: dict[int, bool],
    *,
    model: str | None = None,
    prompt_tokens: int | None = None,
    completion_tokens: int | None = None,
) -> RunScore:
    """Compute recall on news, false positives on not_news, and est. cost."""
    news_total = sum(1 for li in labeled if li.label == "news")
    not_news_total = sum(1 for li in labeled if li.label == "not_news")
    ambiguous_total = sum(1 for li in labeled if li.label == "ambiguous")

    news_hits = sum(
        1 for i, li in enumerate(labeled) if li.label == "news" and predictions.get(i, False)
    )
    false_positives = sum(
        1 for i, li in enumerate(labeled) if li.label == "not_news" and predictions.get(i, False)
    )
    recall = news_hits / news_total if news_total else 0.0

    cost: float | None = None
    if model in PRICING_PER_1M_USD and prompt_tokens is not None and completion_tokens is not None:
        price_in, price_out = PRICING_PER_1M_USD[model]
        cost = (prompt_tokens * price_in + completion_tokens * price_out) / 1_000_000

    return RunScore(
        news_total=news_total,
        not_news_total=not_news_total,
        ambiguous_total=ambiguous_total,
        recall_on_news=recall,
        false_positives=false_positives,
        estimated_cost_usd=cost,
    )


def _print_table(scores: list[RunScore], *, model: str, dataset_path: Path) -> None:
    first = scores[0]
    print(
        f"Benchmark: model={model} | dataset={dataset_path} | runs={len(scores)}\n"
        f"Dataset: news={first.news_total} | not_news={first.not_news_total} | "
        f"ambiguous={first.ambiguous_total} (excluded from recall/false_positives)\n"
        "Cost from API-reported token usage x ADR-003 list price; n/a if the API "
        "returned no usage or the model has no listed price.\n"
    )
    header = f"{'run':>4} | {'recall_on_news':>14} | {'false_positives':>16} | {'est_cost_usd':>13}"
    print(header)
    print("-" * len(header))
    for i, s in enumerate(scores, start=1):
        cost_str = f"{s.estimated_cost_usd:.6f}" if s.estimated_cost_usd is not None else "n/a"
        print(f"{i:>4} | {s.recall_on_news:>14.3f} | {s.false_positives:>16d} | {cost_str:>13}")

    mean_recall = sum(s.recall_on_news for s in scores) / len(scores)
    mean_fp = sum(s.false_positives for s in scores) / len(scores)
    costs = [s.estimated_cost_usd for s in scores if s.estimated_cost_usd is not None]
    mean_cost_str = f"{sum(costs) / len(costs):.6f}" if costs else "n/a"
    print(f"{'mean':>4} | {mean_recall:>14.3f} | {mean_fp:>16.2f} | {mean_cost_str:>13}")


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Benchmark the production LLM classifier against a hand-labeled dataset "
            "(see module docstring for the dataset format), reproducing the recall/FP/cost "
            "table from docs/adr/003-llm-kimi-k26-fail-loud.md."
        )
    )
    parser.add_argument(
        "--dataset", required=True, type=Path, help="Path to a labeled .jsonl dataset."
    )
    parser.add_argument(
        "--model", default=None, help="Model name for the API call (default: OPENAI_MODEL setting)."
    )
    parser.add_argument(
        "--runs", type=int, default=2, help="Runs per config, averaged (default: 2, per ADR-003)."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Use a deterministic fake LLM client -- no network, no API key. "
        "Smoke-tests the script only; not real metrics.",
    )
    return parser.parse_args(argv)


async def _run(args: argparse.Namespace) -> int:
    labeled = load_dataset(args.dataset)
    if not labeled:
        print(f"error: {args.dataset} contains no labeled items", file=sys.stderr)
        return 1

    settings = get_settings()
    model = args.model or settings.openai_model
    enabled_topics = settings.topics_list
    topics_info = "\n".join(
        f'- "{topic}": {data["description"]}'
        for topic, data in TOPIC_DEFINITIONS.items()
        if topic in enabled_topics
    )

    scores: list[RunScore] = []
    for _ in range(args.runs):
        inner_client: Any = (
            FakeLLMClient()
            if args.dry_run
            else openai.AsyncOpenAI(
                api_key=settings.openai_api_key, base_url=settings.openai_base_url
            )
        )
        client = UsageRecordingClient(inner_client)
        predictions = await classify_dataset(
            labeled,
            client=client,
            model=model,
            enabled_topics=enabled_topics,
            min_relevance=settings.min_relevance_score,
            topics_info=topics_info,
        )
        scores.append(
            score_run(
                labeled,
                predictions,
                model=model,
                prompt_tokens=client.prompt_tokens if client.usage_seen else None,
                completion_tokens=client.completion_tokens if client.usage_seen else None,
            )
        )

    _print_table(scores, model=model, dataset_path=args.dataset)
    return 0


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    return asyncio.run(_run(args))


if __name__ == "__main__":
    sys.exit(main())
