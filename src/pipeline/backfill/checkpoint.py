"""Checkpoint persistence for resumable backfill."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


class BackfillCheckpoint:
    """Tracks backfill progress for resume capability."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.sources: dict[str, dict[str, Any]] = {}
        self.classify_cursor: str | None = None
        self.items_classified: int = 0
        self.cost_usd: float = 0.0
        self.updated_at: str | None = None

    def update_source(
        self,
        source: str,
        *,
        last_month: str | None = None,
        last_page: int | None = None,
        items_stored: int | None = None,
        offset: int | None = None,
    ) -> None:
        entry = self.sources.setdefault(source, {})
        if last_month is not None:
            entry["last_month"] = last_month
        if last_page is not None:
            entry["last_page"] = last_page
        if items_stored is not None:
            entry["items_stored"] = items_stored
        if offset is not None:
            entry["offset"] = offset

    def save(self) -> None:
        self.updated_at = datetime.now(tz=UTC).isoformat()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(
                {
                    "sources": self.sources,
                    "classify_cursor": self.classify_cursor,
                    "items_classified": self.items_classified,
                    "cost_usd": self.cost_usd,
                    "updated_at": self.updated_at,
                },
                indent=2,
            )
        )

    @classmethod
    def load(cls, path: Path) -> BackfillCheckpoint:
        cp = cls(path)
        if path.exists():
            data = json.loads(path.read_text())
            cp.sources = data.get("sources", {})
            cp.classify_cursor = data.get("classify_cursor")
            cp.items_classified = data.get("items_classified", 0)
            cp.cost_usd = data.get("cost_usd", 0.0)
            cp.updated_at = data.get("updated_at")
        return cp
