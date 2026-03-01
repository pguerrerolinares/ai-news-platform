"""Tests for HuggingFace variant collapse module."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from src.feed.variant_collapse import collapse_variants, normalize_model_name


def _make_item(**kwargs: object) -> SimpleNamespace:
    return SimpleNamespace(**kwargs)


# --- normalize_model_name ---


class TestNormalizeModelName:
    @pytest.mark.parametrize(
        ("title", "expected"),
        [
            ("TheBloke/Llama-2-7B-GGUF", "llama-2-7b"),
            ("bartowski/Mistral-7B-GPTQ", "mistral-7b"),
            ("turboderp/Phi-3-AWQ", "phi-3"),
            ("mradermacher/Qwen-2-EXL2", "qwen-2"),
            ("user/SomeModel-ONNX", "somemodel"),
            ("user/Model-MLX", "model"),
        ],
    )
    def test_strips_quantization_suffixes(self, title: str, expected: str) -> None:
        assert normalize_model_name(title) == expected

    @pytest.mark.parametrize(
        ("title", "expected"),
        [
            ("meta-llama/Llama-2-7B", "llama-2-7b"),
            ("mistralai/Mistral-7B-v0.1", "mistral-7b-v0.1"),
            ("google/gemma-2b", "gemma-2b"),
        ],
    )
    def test_preserves_original_model_names(self, title: str, expected: str) -> None:
        assert normalize_model_name(title) == expected

    @pytest.mark.parametrize(
        "title",
        [
            "no-slash-here",
            "JustAWord",
            "",
        ],
    )
    def test_returns_none_for_non_org_model(self, title: str) -> None:
        assert normalize_model_name(title) is None

    def test_case_insensitive_suffix(self) -> None:
        assert normalize_model_name("user/Model-gguf") == "model"
        assert normalize_model_name("user/Model-Gptq") == "model"


# --- collapse_variants ---


class TestCollapseVariants:
    def test_keeps_original_drops_gguf_variant(self) -> None:
        original = _make_item(
            source="huggingface", title="meta-llama/Llama-2-7B", score=100
        )
        variant = _make_item(
            source="huggingface", title="TheBloke/Llama-2-7B-GGUF", score=50
        )
        result = collapse_variants([original, variant])
        assert len(result) == 1
        assert result[0] is original

    def test_keeps_highest_score_variant(self) -> None:
        low = _make_item(
            source="huggingface", title="meta-llama/Llama-2-7B", score=10
        )
        high = _make_item(
            source="huggingface", title="TheBloke/Llama-2-7B-GGUF", score=200
        )
        result = collapse_variants([low, high])
        assert len(result) == 1
        assert result[0] is high

    def test_non_hf_items_pass_through(self) -> None:
        hn = _make_item(source="hackernews", title="Some HN Post", score=50)
        reddit = _make_item(source="reddit", title="Reddit Post", score=30)
        result = collapse_variants([hn, reddit])
        assert len(result) == 2
        assert hn in result
        assert reddit in result

    def test_mixed_sources(self) -> None:
        hn = _make_item(source="hackernews", title="Some Post", score=50)
        hf_original = _make_item(
            source="huggingface", title="meta-llama/Llama-2-7B", score=100
        )
        hf_variant = _make_item(
            source="huggingface", title="TheBloke/Llama-2-7B-GGUF", score=50
        )
        result = collapse_variants([hn, hf_original, hf_variant])
        assert len(result) == 2
        assert hn in result
        assert hf_original in result
        assert hf_variant not in result

    def test_does_not_collapse_different_models(self) -> None:
        llama = _make_item(
            source="huggingface", title="meta-llama/Llama-2-7B", score=100
        )
        mistral = _make_item(
            source="huggingface", title="mistralai/Mistral-7B", score=80
        )
        result = collapse_variants([llama, mistral])
        assert len(result) == 2
        assert llama in result
        assert mistral in result

    def test_empty_list(self) -> None:
        assert collapse_variants([]) == []

    def test_hf_item_without_org_model_pattern(self) -> None:
        item = _make_item(source="huggingface", title="NoSlashHere", score=10)
        result = collapse_variants([item])
        assert len(result) == 1
        assert result[0] is item

    def test_item_with_none_score(self) -> None:
        a = _make_item(
            source="huggingface", title="org/Model-GGUF", score=None
        )
        b = _make_item(
            source="huggingface", title="org/Model", score=5
        )
        result = collapse_variants([a, b])
        assert len(result) == 1
        assert result[0] is b
