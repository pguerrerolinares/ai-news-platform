# Add New Extractor Runbook

## Steps

### 1. Create Extractor File
```bash
# src/extractors/<source_name>.py
```

### 2. Implement BaseExtractor

```python
from __future__ import annotations
import httpx
from src.extractors.base import BaseExtractor, ExtractedItem
from src.core.config import get_settings
from src.core.logging import get_logger

logger = get_logger(__name__)

class SourceNameExtractor(BaseExtractor):
    @property
    def source_name(self) -> str:
        return "source_name"

    async def extract(self, since_hours: int = 24) -> list[ExtractedItem]:
        settings = get_settings()
        items: list[ExtractedItem] = []

        async with httpx.AsyncClient(timeout=30) as client:
            # Fetch from source API
            resp = await client.get("https://api.source.com/...")
            resp.raise_for_status()
            data = resp.json()

        for entry in data:
            items.append(ExtractedItem(
                title=entry["title"],
                source=self.source_name,
                url=entry.get("url"),
                text=entry.get("text"),
                author=entry.get("author"),
                published_at=...,
                score=entry.get("score"),
                metadata={...},
            ))

        logger.info("extraction_complete", source=self.source_name, count=len(items))
        return sorted(items, key=lambda x: x.score or 0, reverse=True)[:settings.max_items_per_source]
```

### 3. Add Config (if needed)
Add environment variables to `src/core/config.py` and `.env.example`.

### 4. Register in the Extractor Registry
Add an entry to `EXTRACTOR_REGISTRY` in `src/extractors/__init__.py`, mapping the
`source_name` to a `"module:ClassName"` string (imported lazily via `load_extractor`):

```python
EXTRACTOR_REGISTRY: dict[str, str] = {
    # ...
    "source_name": "src.extractors.source_name:SourceNameExtractor",
}
```

The key must match the extractor's `source_name` property and the value used in
`settings.enabled_sources_list`. To enable the source, add it to the
`enabled_sources` default in `src/core/config.py`.

### 5. Write Tests
```bash
# tests/unit/test_<source_name>_extractor.py
```
- Test parsing logic with sample data
- Test error handling (API timeout, bad response)
- Test deduplication and sorting

### 6. Update Documentation
- Add source to `AGENTS.md` file map
- Add to source table in architecture docs
- Update `.env.example` if new config added

### 7. Risk Classification
New extractors are **Track B** (medium risk). Push directly to main after CI passes.

## Checklist
- [ ] Implements `BaseExtractor` interface
- [ ] Uses `httpx.AsyncClient` (not requests)
- [ ] Handles errors gracefully (logs, doesn't crash pipeline)
- [ ] Respects `max_items_per_source` limit
- [ ] Has unit tests
- [ ] Config documented in `.env.example`
- [ ] AGENTS.md updated
