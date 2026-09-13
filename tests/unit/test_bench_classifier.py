"""Tests for scripts/bench_classifier.py (#15 / ADR-003 reproducibility).

`scripts/` is not an installed package (see scripts/rescore_all.py), so the
module is loaded from its file path via importlib, same as running it with
`python scripts/bench_classifier.py`. The subprocess-based tests exercise the
actual CLI contract (--help, --dry-run exit code and output).
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

import src.classifiers.llm as llm_module

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / "scripts" / "bench_classifier.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("bench_classifier", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module  # dataclass field resolution needs this registered
    spec.loader.exec_module(module)
    return module


bench_classifier = _load_module()


def _write_dataset(path: Path, rows: list[dict]) -> Path:
    with path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row) + "\n")
    return path


SYNTHETIC_ROWS = [
    {
        "title": "OpenAI releases GPT-6 with major benchmark gains",
        "text": "Full technical report with weights and benchmarks.",
        "url": "https://example.com/gpt6",
        "source": "hackernews",
        "label": "news",
    },
    {
        "title": "My honest opinion on my career switch to AI",
        "text": "A personal story, no technical content.",
        "url": "https://example.com/opinion",
        "source": "reddit",
        "label": "not_news",
    },
    {
        "title": "Minor patch release for a small internal tool",
        "text": "Bumps a dependency version.",
        "url": "https://example.com/patch",
        "source": "github",
        "label": "ambiguous",
    },
    {
        "title": "New SOTA open-source model tops leaderboard",
        "text": "Weights released on HuggingFace with full eval suite.",
        "url": "https://example.com/sota",
        "source": "huggingface",
        "label": "news",
    },
]


# ---------------------------------------------------------------------------
# load_dataset
# ---------------------------------------------------------------------------
class TestLoadDataset:
    def test_loads_valid_dataset(self, tmp_path):
        path = _write_dataset(tmp_path / "ds.jsonl", SYNTHETIC_ROWS)
        labeled = bench_classifier.load_dataset(path)
        assert len(labeled) == 4
        assert labeled[0].label == "news"
        assert labeled[0].item.title == SYNTHETIC_ROWS[0]["title"]
        assert labeled[0].item.url == SYNTHETIC_ROWS[0]["url"]

    def test_skips_blank_lines(self, tmp_path):
        path = tmp_path / "ds.jsonl"
        path.write_text(
            json.dumps(SYNTHETIC_ROWS[0]) + "\n\n" + json.dumps(SYNTHETIC_ROWS[1]) + "\n",
            encoding="utf-8",
        )
        labeled = bench_classifier.load_dataset(path)
        assert len(labeled) == 2

    def test_rejects_invalid_label(self, tmp_path):
        rows = [{**SYNTHETIC_ROWS[0], "label": "definitely_news"}]
        path = _write_dataset(tmp_path / "ds.jsonl", rows)
        with pytest.raises(ValueError, match="label"):
            bench_classifier.load_dataset(path)

    def test_rejects_missing_title(self, tmp_path):
        rows = [{"label": "news", "text": "no title here"}]
        path = _write_dataset(tmp_path / "ds.jsonl", rows)
        with pytest.raises(ValueError, match="title"):
            bench_classifier.load_dataset(path)

    def test_rejects_malformed_json_line(self, tmp_path):
        path = tmp_path / "ds.jsonl"
        path.write_text("not json at all\n", encoding="utf-8")
        with pytest.raises(ValueError, match="invalid JSON"):
            bench_classifier.load_dataset(path)


# ---------------------------------------------------------------------------
# scoring
# ---------------------------------------------------------------------------
class TestScoreRun:
    def test_recall_and_false_positives(self, tmp_path):
        path = _write_dataset(tmp_path / "ds.jsonl", SYNTHETIC_ROWS)
        labeled = bench_classifier.load_dataset(path)
        # idx 0 (news) predicted True, idx 1 (not_news) predicted True (FP),
        # idx 2 (ambiguous) predicted True (ignored), idx 3 (news) predicted False.
        predictions = {0: True, 1: True, 2: True, 3: False}
        score = bench_classifier.score_run(labeled, predictions)
        assert score.news_total == 2
        assert score.not_news_total == 1
        assert score.recall_on_news == pytest.approx(0.5)
        assert score.false_positives == 1

    def test_perfect_predictions(self, tmp_path):
        path = _write_dataset(tmp_path / "ds.jsonl", SYNTHETIC_ROWS)
        labeled = bench_classifier.load_dataset(path)
        predictions = {0: True, 1: False, 2: False, 3: True}
        score = bench_classifier.score_run(labeled, predictions)
        assert score.recall_on_news == pytest.approx(1.0)
        assert score.false_positives == 0


class _TopicMismatchClient:
    """Always answers is_news=true for a topic NOT in enabled_topics.

    Used to prove the bench cannot accept what production's
    `LLMClassifier._classify_batch` would reject (F1): a real pipeline run
    drops any entry whose topic isn't enabled, no matter how high its
    relevance or how true its is_news flag.
    """

    def __init__(self) -> None:
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    async def _create(self, **_kwargs: object) -> SimpleNamespace:
        content = json.dumps([{"idx": 0, "is_news": True, "topic": "crypto", "relevance": 0.9}])
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=content))],
            usage=SimpleNamespace(prompt_tokens=10, completion_tokens=5),
        )


# ---------------------------------------------------------------------------
# The bench must use production's actual accept/reject decision, not just
# is_news + relevance -- otherwise it accepts what the pipeline rejects (F1).
# ---------------------------------------------------------------------------
class TestBenchMatchesProductionDecision:
    async def test_classify_dataset_calls_production_build_prompt(self, tmp_path, monkeypatch):
        path = _write_dataset(tmp_path / "ds.jsonl", SYNTHETIC_ROWS[:2])
        labeled = bench_classifier.load_dataset(path)

        calls: list[str] = []
        original = llm_module._build_prompt

        def spy(batch, topics_info):
            prompt = original(batch, topics_info)
            calls.append(prompt)
            return prompt

        monkeypatch.setattr(llm_module, "_build_prompt", spy)

        client = bench_classifier.FakeLLMClient()
        predictions = await bench_classifier.classify_dataset(
            labeled,
            client=client,
            model="fake-model",
            enabled_topics=["models"],
            min_relevance=0.8,
            topics_info="- models: AI models",
        )
        assert len(calls) == 1
        assert '<item_content idx="0">' in calls[0]
        assert isinstance(predictions, dict)
        assert set(predictions.keys()) == {0, 1}

    async def test_rejects_item_whose_topic_is_not_enabled(self, tmp_path):
        """Production's `_classify_batch` drops entries with a disabled topic
        (`if topic not in enabled_topics: continue`) regardless of is_news/
        relevance. The bench must mirror that, not just check is_news+relevance.
        """
        path = _write_dataset(tmp_path / "ds.jsonl", [SYNTHETIC_ROWS[0]])
        labeled = bench_classifier.load_dataset(path)

        predictions = await bench_classifier.classify_dataset(
            labeled,
            client=_TopicMismatchClient(),
            model="fake-model",
            enabled_topics=["models"],  # "crypto" is NOT in here
            min_relevance=0.8,
            topics_info="- models: AI models",
        )
        assert predictions == {0: False}


# ---------------------------------------------------------------------------
# CLI contract (subprocess, matches how Paul will actually invoke it)
# ---------------------------------------------------------------------------
class TestCli:
    def test_help_exits_zero(self):
        result = subprocess.run(  # noqa: S603
            [sys.executable, str(SCRIPT_PATH), "--help"],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=REPO_ROOT,
        )
        assert result.returncode == 0
        assert "--dataset" in result.stdout
        assert "--dry-run" in result.stdout

    def test_dry_run_exits_zero_and_prints_table_no_network(self, tmp_path):
        dataset_path = tmp_path / "synthetic.jsonl"
        _write_dataset(dataset_path, SYNTHETIC_ROWS)
        result = subprocess.run(  # noqa: S603
            [
                sys.executable,
                str(SCRIPT_PATH),
                "--dataset",
                str(dataset_path),
                "--dry-run",
                "--runs",
                "1",
            ],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=REPO_ROOT,
        )
        assert result.returncode == 0, result.stderr
        assert "recall" in result.stdout.lower()
        assert "false_positives" in result.stdout.lower() or "fp" in result.stdout.lower()
        assert "news=2" in result.stdout or "news: 2" in result.stdout.lower()

    def test_missing_dataset_argument_fails_fast(self):
        result = subprocess.run(  # noqa: S603
            [sys.executable, str(SCRIPT_PATH), "--dry-run"],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=REPO_ROOT,
        )
        assert result.returncode != 0
        assert "--dataset" in result.stderr or "required" in result.stderr.lower()
