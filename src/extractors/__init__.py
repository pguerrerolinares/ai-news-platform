"""Extractor package — lazy registry of all concrete BaseExtractor implementations.

Extractor modules are imported on demand: eager imports here would pull
pipeline-only dependencies (feedparser, lxml, readability) into the API image,
which only installs the [api] extra.
"""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.extractors.base import BaseExtractor

# Maps source_name → "module:ClassName". Keys must match each extractor's
# source_name property and the strings used in settings.enabled_sources_list.
EXTRACTOR_REGISTRY: dict[str, str] = {
    "hackernews": "src.extractors.hackernews:HackerNewsExtractor",
    "hackernews_leading": "src.extractors.hackernews_leading:HackerNewsLeadingExtractor",
    "arxiv": "src.extractors.arxiv:ArxivExtractor",
    "reddit": "src.extractors.reddit:RedditExtractor",
    "rss": "src.extractors.rss:RSSExtractor",
    "github": "src.extractors.github_trending:GitHubTrendingExtractor",
    "github_search": "src.extractors.github:GitHubExtractor",
    "huggingface": "src.extractors.huggingface:HuggingFaceExtractor",
    "webscraper": "src.extractors.webscraper:WebScraperExtractor",
}


def load_extractor(source: str) -> type[BaseExtractor]:
    """Resolve a source name to its extractor class, importing lazily.

    Raises KeyError if the source is not registered (fail-fast on
    misconfiguration).
    """
    if source not in EXTRACTOR_REGISTRY:
        raise KeyError(
            f"Unknown extractor source {source!r}. Available: {sorted(EXTRACTOR_REGISTRY)}"
        )
    module_path, class_name = EXTRACTOR_REGISTRY[source].split(":")
    return getattr(import_module(module_path), class_name)


__all__ = ["EXTRACTOR_REGISTRY", "load_extractor"]
