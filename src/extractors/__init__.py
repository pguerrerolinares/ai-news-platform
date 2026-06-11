"""Extractor package — registry of all concrete BaseExtractor implementations."""

from __future__ import annotations

from src.extractors.arxiv import ArxivExtractor
from src.extractors.base import BaseExtractor, ExtractedItem
from src.extractors.github import GitHubExtractor
from src.extractors.github_trending import GitHubTrendingExtractor
from src.extractors.hackernews import HackerNewsExtractor
from src.extractors.hackernews_leading import HackerNewsLeadingExtractor
from src.extractors.huggingface import HuggingFaceExtractor
from src.extractors.reddit import RedditExtractor
from src.extractors.rss import RSSExtractor
from src.extractors.webscraper import WebScraperExtractor

# Maps source_name → extractor class.  Keys must match the values returned by
# each extractor's source_name property and the strings used in
# settings.enabled_sources_list.
EXTRACTOR_REGISTRY: dict[str, type[BaseExtractor]] = {
    "hackernews": HackerNewsExtractor,
    "hackernews_leading": HackerNewsLeadingExtractor,
    "arxiv": ArxivExtractor,
    "reddit": RedditExtractor,
    "rss": RSSExtractor,
    "github": GitHubTrendingExtractor,
    "github_search": GitHubExtractor,
    "huggingface": HuggingFaceExtractor,
    "webscraper": WebScraperExtractor,
}

__all__ = [
    "EXTRACTOR_REGISTRY",
    "ArxivExtractor",
    "BaseExtractor",
    "ExtractedItem",
    "GitHubExtractor",
    "GitHubTrendingExtractor",
    "HackerNewsExtractor",
    "HackerNewsLeadingExtractor",
    "HuggingFaceExtractor",
    "RSSExtractor",
    "RedditExtractor",
    "WebScraperExtractor",
]
