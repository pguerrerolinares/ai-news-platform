"""Collapse HuggingFace model variants (GGUF, GPTQ, AWQ, etc.)."""

from __future__ import annotations

import re

from src.core.logging import get_logger

log = get_logger(__name__)

# Known quantization/format suffixes to strip
_SUFFIXES = re.compile(
    r"-(GGUF|GPTQ|AWQ|ONNX|EXL2|MLX|FP8|FP16|NVFP4|abliterated|censored)$",
    re.IGNORECASE,
)

# Parameter size pattern: -0.8B, -7B, -27B, -397B-A17B, -35B-A3B, etc.
_PARAM_SIZE = re.compile(r"-\d+\.?\d*B(-A\d+\.?\d*B)?", re.IGNORECASE)

# Known re-upload publishers (strip these to find base model name)
_QUANT_PUBLISHERS = frozenset(
    {
        "unsloth",
        "thebloke",
        "bartowski",
        "turboderp",
        "mradermacher",
    }
)


def normalize_model_name(title: str) -> str | None:
    """Extract normalized base model name from a HuggingFace title.

    Returns None if title doesn't match org/model pattern.
    """
    if "/" not in title:
        return None

    org, model = title.split("/", 1)

    # Strip quantization suffix
    model = _SUFFIXES.sub("", model)

    # Strip parameter size
    model = _PARAM_SIZE.sub("", model)

    return model.lower()


def collapse_variants(items: list) -> list:
    """Collapse HuggingFace model variants, keeping highest-score per base model.

    Non-HuggingFace items pass through unchanged.
    """
    non_hf: list = []
    hf_groups: dict[str, list] = {}

    for item in items:
        source = getattr(item, "source", None)
        title = getattr(item, "title", "") or ""

        if source != "huggingface":
            non_hf.append(item)
            continue

        base_name = normalize_model_name(title)
        if base_name is None:
            non_hf.append(item)
            continue

        hf_groups.setdefault(base_name, []).append(item)

    # Keep highest-score item per group
    kept_hf = []
    collapsed_count = 0
    for _base_name, group in hf_groups.items():
        best = max(group, key=lambda x: getattr(x, "score", 0) or 0)
        kept_hf.append(best)
        collapsed_count += len(group) - 1

    if collapsed_count > 0:
        log.info("variants_collapsed", collapsed=collapsed_count, groups=len(hf_groups))

    return non_hf + kept_hf
