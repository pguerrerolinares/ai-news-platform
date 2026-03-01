"""HuggingFace Trending models extractor."""

from __future__ import annotations

import html
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
DAILY_PAPERS_URL = "https://huggingface.co/api/daily_papers"


class HuggingFaceExtractor(BaseExtractor):
    """Extracts trending AI models from HuggingFace Hub API."""

    @property
    def source_name(self) -> str:
        return "huggingface"

    async def _fetch_daily_papers(
        self, client: httpx.AsyncClient, seen_urls: set[str]
    ) -> list[ExtractedItem]:
        """Fetch curated daily papers from HuggingFace."""
        items: list[ExtractedItem] = []
        try:
            resp = await client.get(DAILY_PAPERS_URL)
            resp.raise_for_status()
            papers = resp.json()

            for entry in papers:
                paper = entry.get("paper", {})
                paper_id = paper.get("id", "")
                if not paper_id:
                    continue

                url = f"https://arxiv.org/abs/{paper_id}"
                if url in seen_urls:
                    continue
                seen_urls.add(url)

                authors = paper.get("authors", [])
                author = authors[0].get("name", "unknown") if authors else "unknown"

                published_str = paper.get("publishedAt", "")
                try:
                    published = datetime.fromisoformat(published_str.replace("Z", "+00:00"))
                except (ValueError, AttributeError):
                    published = None

                items.append(
                    ExtractedItem(
                        title=html.unescape(paper.get("title", paper_id)),
                        source=self.source_name,
                        url=url,
                        text=paper.get("title", ""),
                        author=author,
                        published_at=published,
                        score=paper.get("upvotes", 0),
                        metadata={
                            "paper_id": paper_id,
                            "upvotes": paper.get("upvotes", 0),
                            "type": "daily_paper",
                        },
                    )
                )
        except Exception as exc:
            logger.warning("huggingface_daily_papers_failed", error=str(exc))

        return items

    async def extract(self, since_hours: int = 48) -> list[ExtractedItem]:
        settings = get_settings()
        min_downloads = settings.hf_min_downloads
        max_items = settings.max_items_per_source
        since_cutoff = datetime.now(tz=UTC) - timedelta(hours=since_hours)

        seen_urls: set[str] = set()
        items: list[ExtractedItem] = []

        with extractor_duration_seconds.labels(source=self.source_name).time():
            async with httpx.AsyncClient(
                timeout=30,
                headers={"User-Agent": "AI-News-Platform/1.0"},
            ) as client:
                try:
                    params = {
                        "sort": "trendingScore",
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
                            last_mod = None

                        if last_mod is not None and last_mod < since_cutoff:
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

                # Also fetch daily papers
                daily_items = await self._fetch_daily_papers(client, seen_urls)
                items.extend(daily_items)

        items.sort(key=lambda x: x.score or 0, reverse=True)
        items = items[:max_items]

        items_extracted_total.labels(source=self.source_name).inc(len(items))
        logger.info("extraction_complete", source=self.source_name, count=len(items))

        return items
