"""HuggingFace Trending models extractor."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import httpx

from src.core.config import get_settings
from src.core.logging import get_logger
from src.core.metrics import (
    extractor_duration_seconds,
    items_extracted_total,
)
from src.extractors.base import BaseExtractor, ExtractedItem

logger = get_logger(__name__)
API_URL = "https://huggingface.co/api/models"


class HuggingFaceExtractor(BaseExtractor):
    """Extracts trending AI models from HuggingFace Hub API."""

    @property
    def source_name(self) -> str:
        return "huggingface"

    async def extract(self, since_hours: int = 48) -> list[ExtractedItem]:
        settings = get_settings()
        min_downloads = settings.hf_min_downloads
        max_items = settings.max_items_per_source
        since_cutoff = datetime.now(tz=UTC) - timedelta(hours=since_hours)

        seen_urls: set[str] = set()
        items: list[ExtractedItem] = []

        with extractor_duration_seconds.labels(source=self.source_name).time():
            try:
                async with httpx.AsyncClient(
                    timeout=30,
                    headers={"User-Agent": "AI-News-Platform/1.0"},
                ) as client:
                    params = {
                        "sort": "trending",
                        "direction": "-1",
                        "limit": 50,
                    }
                    resp = await client.get(API_URL, params=params)
                    resp.raise_for_status()
                    models = resp.json()

                    for model in models:
                        downloads = model.get("downloads", 0)
                        if downloads < min_downloads:
                            continue

                        model_id = model.get("modelId") or model.get("id", "")
                        url = f"https://huggingface.co/{model_id}"

                        if url in seen_urls:
                            continue
                        seen_urls.add(url)

                        try:
                            last_mod = datetime.fromisoformat(
                                model.get("lastModified", "").replace("Z", "+00:00")
                            )
                        except (ValueError, AttributeError):
                            last_mod = datetime.now(tz=UTC)

                        if last_mod < since_cutoff:
                            continue

                        items.append(
                            ExtractedItem(
                                title=model_id,
                                source=self.source_name,
                                url=url,
                                text=model_id,
                                author=model.get(
                                    "author",
                                    model_id.split("/")[0] if "/" in model_id else "unknown",
                                ),
                                published_at=last_mod,
                                score=downloads,
                                metadata={
                                    "pipeline_tag": model.get("pipeline_tag"),
                                    "downloads": downloads,
                                    "likes": model.get("likes", 0),
                                    "tags": model.get("tags", []),
                                },
                            )
                        )
            except Exception as exc:
                logger.warning("huggingface_fetch_failed", error=str(exc))

        items.sort(key=lambda x: x.score or 0, reverse=True)
        items = items[:max_items]

        items_extracted_total.labels(source=self.source_name).inc(len(items))
        logger.info("extraction_complete", source=self.source_name, count=len(items))

        return items
