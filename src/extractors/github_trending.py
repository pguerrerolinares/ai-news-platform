"""GitHub Trending extractor — scrapes github.com/trending for daily hot repos."""

from __future__ import annotations

import html
import re
from datetime import UTC, datetime

import httpx

from src.core.config import get_settings
from src.core.logging import get_logger
from src.core.metrics import extractor_duration_seconds, items_extracted_total
from src.extractors.base import BaseExtractor, ExtractedItem

logger = get_logger(__name__)

TRENDING_URL = "https://github.com/trending"  # SSRF: safe — hardcoded URL, not user-controlled

# Keywords to filter AI/ML-related repos from general trending
_AI_KEYWORDS = re.compile(
    r"\b("
    r"ai|llm|gpt|transformer|neural|machine.?learning|deep.?learning|"
    r"nlp|diffusion|embedding|rag|agent|langchain|pytorch|tensorflow|"
    r"hugging.?face|openai|anthropic|gemini|claude|llama|mistral|"
    r"fine.?tun|rlhf|bert|attention|inference|model|ml|gen.?ai|"
    r"computer.?vision|object.?detect|stable.?diffusion|lora|"
    r"vector.?database|chatbot|copilot|prompt|benchmark"
    r")\b",
    re.IGNORECASE,
)


def _parse_trending_html(html_content: str) -> list[dict]:
    """Parse GitHub trending page HTML into repo dicts."""
    repos: list[dict] = []

    # Split by Box-row
    rows = re.split(r'class="Box-row"', html_content)[1:]  # skip before first

    for row in rows:
        # Extract owner/name from h2 > a href
        href_match = re.search(r'<h2[^>]*>\s*<a[^>]*href="(/[^/]+/[^"]+)"', row)
        if not href_match:
            continue
        full_name = href_match.group(1).strip("/")
        parts = full_name.split("/")
        if len(parts) != 2:
            continue
        owner, name = parts

        # Extract description
        desc_match = re.search(r'<p\s+class="col-9[^"]*">\s*(.*?)\s*</p>', row, re.DOTALL)
        description = html.unescape(desc_match.group(1).strip()) if desc_match else ""

        # Extract language
        lang_match = re.search(r'itemprop="programmingLanguage">(.*?)</span>', row)
        language = lang_match.group(1).strip() if lang_match else None

        # Extract total stars (first Link with number)
        stars_match = re.search(r'href="/[^"]+/stargazers"[^>]*>\s*([\d,]+)\s*</a>', row)
        total_stars = int(stars_match.group(1).replace(",", "")) if stars_match else 0

        # Extract stars today
        today_match = re.search(r"([\d,]+)\s*stars\s*today", row)
        stars_today = int(today_match.group(1).replace(",", "")) if today_match else 0

        repos.append(
            {
                "full_name": full_name,
                "owner": owner,
                "name": name,
                "description": description,
                "language": language,
                "total_stars": total_stars,
                "stars_today": stars_today,
                "url": f"https://github.com/{full_name}",
            }
        )

    return repos


def _is_ai_related(repo: dict) -> bool:
    """Check if a repo is AI/ML related based on name + description."""
    text = f"{repo['name']} {repo['description']}"
    return bool(_AI_KEYWORDS.search(text))


class GitHubTrendingExtractor(BaseExtractor):
    """Extracts AI-related trending repos from GitHub Trending page."""

    @property
    def source_name(self) -> str:
        return "github"

    async def extract(self, since_hours: int = 24) -> list[ExtractedItem]:
        settings = get_settings()
        max_items = settings.max_items_per_source

        with extractor_duration_seconds.labels(source=self.source_name).time():
            try:
                async with httpx.AsyncClient(timeout=30) as client:
                    resp = await client.get(
                        TRENDING_URL,
                        params={"since": "daily", "spoken_language_code": "en"},
                        headers={"User-Agent": "AI-News-Platform/1.0"},
                    )
                    resp.raise_for_status()
            except httpx.HTTPError as exc:
                logger.warning("github_trending_fetch_failed", error=str(exc))
                return []

            all_repos = _parse_trending_html(resp.text)
            if not all_repos and len(resp.text) > 10000:
                logger.warning(
                    "github_trending_parse_empty",
                    response_length=len(resp.text),
                    hint="HTML structure may have changed",
                )
            ai_repos = [r for r in all_repos if _is_ai_related(r)]

            items: list[ExtractedItem] = []
            for repo in ai_repos:
                name = repo["name"]
                desc = repo["description"]
                title = f"{name}: {desc}" if desc else name
                items.append(
                    ExtractedItem(
                        title=title,
                        source=self.source_name,
                        url=repo["url"],
                        text=repo["description"],
                        author=repo["owner"],
                        published_at=datetime.now(tz=UTC),
                        score=repo["total_stars"],
                        metadata={
                            "language": repo["language"],
                            "stars": repo["total_stars"],
                            "stars_today": repo["stars_today"],
                            "full_name": repo["full_name"],
                            "trending": True,
                        },
                    )
                )

            items.sort(key=lambda x: x.score or 0, reverse=True)
            items = items[:max_items]

        items_extracted_total.labels(source=self.source_name).inc(len(items))
        logger.info(
            "extraction_complete",
            source=self.source_name,
            count=len(items),
            total_trending=len(all_repos),
            ai_filtered=len(ai_repos),
        )

        return items
