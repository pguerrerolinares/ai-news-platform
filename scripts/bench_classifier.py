"""Benchmark the production LLM classifier prompt/parser against a hand-labeled
dataset, reproducing the recall/false-positive/cost metrics from
docs/adr/003-llm-kimi-k26-fail-loud.md.

The hand-labeled dataset used for ADR-003 (166 items, single annotator) is NOT
in the repo. Supply your own as a JSONL file, one item per line:

    {"title": "...", "text": "...", "url": "...", "source": "...", "label": "news"}

Fields:
    title   (required) str
    text    (optional) str
    url     (optional) str
    source  (optional) str, defaults to "bench"
    label   (required) one of "news" / "not_news" / "ambiguous"
            ("ambiguous" is counted but excluded from recall/FP, same as ADR-003)

This script imports the *production* prompt builder (`_build_prompt`) and
parser (`_parse_llm_json`) from `src.classifiers.llm` -- it does not
reimplement them. It replicates the classification decision itself
(is_news and relevance >= MIN_RELEVANCE_SCORE) rather than calling
`LLMClassifier.classify()` directly, so the topic list and model are explicit
CLI/settings inputs instead of hidden inside that method.

Model options (temperature, extra_body) are read from settings
(OPENAI_TEMPERATURE / OPENAI_EXTRA_BODY), same knobs production uses -- set
them to match whichever --model you're benchmarking (e.g. kimi-k3 requires
OPENAI_TEMPERATURE=1.0).

Cost is an ESTIMATE: `llm_call` (production code) discards token usage, so
this script approximates prompt/completion tokens via a chars/4 heuristic and
multiplies by the model's published price. Unknown models print "n/a", same
as ADR-003 did for gpt-5.4-mini's daily projection.

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
from src.classifiers.llm import BATCH_SIZE, SYSTEM_MESSAGE, _build_prompt, _parse_llm_json, llm_call
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
    benchmark numbers.
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
        return SimpleNamespace(choices=[choice])


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
    temperature: float,
    extra_body: dict[str, Any] | None,
    min_relevance: float,
    topics_info: str,
) -> tuple[dict[int, bool], int, int]:
    """Run the production prompt+parser over the dataset, batch by batch.

    Returns (predictions, total_prompt_chars, total_completion_chars) where
    `predictions[i]` is True iff the model marked item i as news with
    relevance >= min_relevance (the same decision `LLMClassifier` makes).
    """
    items = [li.item for li in labeled]
    predictions: dict[int, bool] = {}
    total_prompt_chars = 0
    total_completion_chars = 0

    for start in range(0, len(items), BATCH_SIZE):
        batch = items[start : start + BATCH_SIZE]
        prompt = _build_prompt(batch, topics_info)
        total_prompt_chars += len(prompt)

        raw = await llm_call(
            client, model, SYSTEM_MESSAGE, prompt, temperature=temperature, extra_body=extra_body
        )
        total_completion_chars += len(raw)
        parsed = _parse_llm_json(raw)

        batch_predictions = dict.fromkeys(range(len(batch)), False)
        for entry in parsed:
            idx = entry.get("idx")
            if not isinstance(idx, int) or idx < 0 or idx >= len(batch):
                continue
            is_news = bool(entry.get("is_news", False))
            relevance = float(entry.get("relevance", 0.0))
            batch_predictions[idx] = is_news and relevance >= min_relevance

        for local_idx, predicted in batch_predictions.items():
            predictions[start + local_idx] = predicted

    return predictions, total_prompt_chars, total_completion_chars


def score_run(
    labeled: list[LabeledItem],
    predictions: dict[int, bool],
    *,
    model: str | None = None,
    prompt_chars: int = 0,
    completion_chars: int = 0,
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
    if model in PRICING_PER_1M_USD:
        price_in, price_out = PRICING_PER_1M_USD[model]
        prompt_tokens_est = prompt_chars / 4
        completion_tokens_est = completion_chars / 4
        cost = (prompt_tokens_est * price_in + completion_tokens_est * price_out) / 1_000_000

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
        "Cost estimate uses a chars/4 token heuristic (llm_call does not expose real "
        "usage) -- treat as order-of-magnitude only.\n"
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
            "Benchmark the production LLM classifier prompt/parser against a "
            "hand-labeled dataset (see module docstring for the dataset format), "
            "reproducing the recall/FP/cost table from docs/adr/003-llm-kimi-k26-fail-loud.md."
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
    topics_info = "\n".join(
        f'- "{topic}": {data["description"]}'
        for topic, data in TOPIC_DEFINITIONS.items()
        if topic in settings.topics_list
    )

    scores: list[RunScore] = []
    for _ in range(args.runs):
        client: Any = (
            FakeLLMClient()
            if args.dry_run
            else openai.AsyncOpenAI(
                api_key=settings.openai_api_key, base_url=settings.openai_base_url
            )
        )
        predictions, prompt_chars, completion_chars = await classify_dataset(
            labeled,
            client=client,
            model=model,
            temperature=settings.openai_temperature,
            extra_body=settings.openai_extra_body,
            min_relevance=settings.min_relevance_score,
            topics_info=topics_info,
        )
        scores.append(
            score_run(
                labeled,
                predictions,
                model=model,
                prompt_chars=prompt_chars,
                completion_chars=completion_chars,
            )
        )

    _print_table(scores, model=model, dataset_path=args.dataset)
    return 0


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    return asyncio.run(_run(args))


if __name__ == "__main__":
    sys.exit(main())
