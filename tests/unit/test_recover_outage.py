"""Regression tests for the guards of scripts/recover_outage.py (dry-run and cost cap)."""

from __future__ import annotations

import argparse
import importlib.util
from contextlib import asynccontextmanager
from pathlib import Path
from types import ModuleType
from unittest.mock import AsyncMock

import pytest

from src.extractors.base import ExtractedItem

ROOT = Path(__file__).resolve().parents[2]


def _load_script() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "recover_outage", ROOT / "scripts" / "recover_outage.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _candidates() -> list[ExtractedItem]:
    # 1-2 keyword matches each, so they land in the LLM bucket (to_llm > 0).
    return [
        ExtractedItem(
            title=f"New open source LLM number {i} beats baseline",
            source="hackernews",
            url=f"https://example.com/story-{i}",
        )
        for i in range(3)
    ]


@pytest.fixture()
def script(monkeypatch, settings):
    """Script module with every network/DB/LLM boundary replaced by mocks."""
    mod = _load_script()

    async def fake_fetch(_settings):
        return _candidates()

    @asynccontextmanager
    async def fake_session():
        yield object()

    settings.embedding_api_key = "sk-test"
    # Patch attributes of the loaded module: run() resolves these globals at call time.
    monkeypatch.setattr(mod, "FETCHERS", {"hackernews": fake_fetch})
    monkeypatch.setattr(mod, "get_settings", lambda: settings)
    monkeypatch.setattr(mod, "get_session_factory", lambda: fake_session)
    monkeypatch.setattr(
        mod.recovery, "load_existing_hashes", AsyncMock(return_value=(set(), set()))
    )
    monkeypatch.setattr(mod.recovery, "load_recent_titles", AsyncMock(return_value=[]))
    monkeypatch.setattr(mod, "run_classification", AsyncMock(return_value=[]))
    monkeypatch.setattr(mod, "run_scoring", lambda items: items)
    validator = AsyncMock()
    validator.validate = AsyncMock(return_value=[])
    monkeypatch.setattr(mod, "CredibilityValidator", lambda: validator)
    monkeypatch.setattr(mod, "store_classified_items", AsyncMock(return_value=0))
    monkeypatch.setattr(mod, "embed_new_items", AsyncMock(return_value=0))
    return mod


def _args(**overrides: object) -> argparse.Namespace:
    values: dict[str, object] = {"sources": ["hackernews"], "dry_run": False, "max_cost": 100.0}
    values.update(overrides)
    return argparse.Namespace(**values)


async def test_dry_run_never_classifies_or_stores(script) -> None:
    await script.run(_args(dry_run=True))
    assert script.run_classification.await_count == 0
    assert script.store_classified_items.await_count == 0
    assert script.embed_new_items.await_count == 0


async def test_estimate_above_max_cost_aborts_before_llm(script) -> None:
    with pytest.raises(SystemExit):
        await script.run(_args(max_cost=0.0))
    assert script.run_classification.await_count == 0
    assert script.store_classified_items.await_count == 0


async def test_run_within_budget_classifies_stores_and_embeds(script) -> None:
    await script.run(_args())
    script.run_classification.assert_awaited_once()
    (candidates,) = script.run_classification.await_args.args
    assert [c.title for c in candidates] == [c.title for c in _candidates()]
    script.store_classified_items.assert_awaited_once()
    script.embed_new_items.assert_awaited_once()


async def test_unsupported_source_exits_before_touching_anything(script) -> None:
    with pytest.raises(SystemExit):
        await script.run(_args(sources=["arxiv"]))
    assert script.recovery.load_existing_hashes.await_count == 0
    assert script.run_classification.await_count == 0


async def test_similar_titles_are_filtered_before_the_llm(script) -> None:
    script.recovery.load_recent_titles.return_value = [
        "new open source llm number 0 beats baseline"
    ]
    await script.run(_args())
    (candidates,) = script.run_classification.await_args.args
    assert "New open source LLM number 0 beats baseline" not in [c.title for c in candidates]
