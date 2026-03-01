"""Application configuration via environment variables."""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Database ---
    database_url: str = Field(
        default="postgresql+asyncpg://ainews:ainews@localhost:5432/ainews",
        description="Async database URL (postgresql+asyncpg://...)",
    )
    database_url_sync: str = Field(
        default="postgresql://ainews:ainews@localhost:5432/ainews",
        description="Sync database URL for Alembic (postgresql://...)",
    )

    # --- API ---
    api_host: str = "0.0.0.0"  # nosec B104
    api_port: int = 8000
    api_workers: int = 2
    debug: bool = False
    cors_origins: str = "http://localhost:5173"

    # --- Auth ---
    jwt_secret: str = Field(default="change-me-in-production", description="JWT signing secret")
    jwt_algorithm: str = "HS256"
    jwt_access_expire_minutes: int = 30
    jwt_refresh_expire_days: int = 7
    shared_password: str = Field(
        default="change-me-in-production",
        description="Shared password for login (semi-public app)",
    )

    # --- LLM (Kimi/Moonshot, OpenAI-compatible) ---
    openai_api_key: str = ""
    openai_base_url: str = "https://api.moonshot.cn/v1"
    openai_model: str = "kimi-latest"

    # --- Embeddings (OpenAI text-embedding-3-small) ---
    embedding_api_key: str = ""
    embedding_base_url: str = "https://api.openai.com/v1"
    embedding_model: str = "text-embedding-3-small"

    # --- Telegram ---
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    telegram_alerts_enabled: bool = True

    # --- Sources ---
    enabled_sources: str = "hackernews,arxiv,reddit,rss,github,huggingface"
    max_items_per_source: int = 50

    # HackerNews
    hn_min_points: int = 10
    extraction_since_hours: int = 24
    hn_search_queries: str = "AI,LLM,GPT,machine learning,neural network,deep learning"

    # arXiv
    arxiv_categories: str = "cs.AI,cs.CL,cs.LG"
    arxiv_keywords: str = (
        "LLM,transformer,language model,GPT,BERT,attention mechanism,"
        "fine-tuning,RLHF,RAG,retrieval,agent,multi-modal,diffusion,"
        "neural,deep learning,reinforcement learning"
    )

    # Reddit
    reddit_subreddits: str = "MachineLearning,LocalLLaMA,artificial"
    reddit_top_limit: int = 25

    # RSS feeds
    rss_feeds: str = (
        "https://openai.com/blog/rss.xml,"
        "https://blog.google/technology/ai/rss/,"
        "https://huggingface.co/blog/feed.xml"
    )

    # GitHub
    github_token: str = ""
    github_search_queries: str = "AI,LLM,machine-learning,generative-AI"
    github_min_stars: int = 50

    # HuggingFace
    hf_min_downloads: int = 100

    # --- Topics ---
    topics: str = "models,tools,papers,products,open_source,agents,regulation"
    min_relevance_score: float = 0.8

    # --- Composite Scoring Weights (must sum to 1.0 for each mode) ---
    composite_w_velocity: float = 0.35
    composite_w_relevance: float = 0.30
    composite_w_recency: float = 0.20
    composite_w_topic: float = 0.15
    # Weights when velocity is unavailable (Arxiv, RSS)
    composite_no_velocity_w_relevance: float = 0.45
    composite_no_velocity_w_recency: float = 0.30
    composite_no_velocity_w_topic: float = 0.25
    # Recency decay window in hours
    composite_recency_window_hours: float = 48.0
    # --- Velocity Thresholds (saturation point = 1.0) ---
    velocity_threshold_github: float = 1000.0  # stars/day (p95)
    velocity_threshold_hackernews: float = 0.15  # points/hour (p95)
    velocity_threshold_reddit: float = 0.15  # upvotes/hour (aligned with HN)
    velocity_threshold_huggingface: float = 1_000_000.0  # downloads/day (p95)
    velocity_threshold_huggingface_paper: float = 50.0  # upvotes/hour

    # --- Feed Algorithm ---
    feed_mmr_lambda: float = 0.7  # MMR quality vs diversity (0=diverse, 1=quality)
    feed_candidate_multiplier: int = 5  # Candidate pool = limit * multiplier
    feed_latest_max_age_hours: float = 48.0  # Time window for /latest endpoint
    feed_latest_min_items: int = 5  # Min items before expanding time window

    # --- Validation ---
    enable_news_validation: bool = True
    trusted_news_domains: str = (
        "openai.com,anthropic.com,deepmind.google,ai.meta.com,"
        "huggingface.co,arxiv.org,github.com,techcrunch.com,"
        "theverge.com,wired.com,arstechnica.com,reuters.com"
    )

    # --- Pipeline ---
    pipeline_schedule_hour: int = 8
    pipeline_schedule_minute: int = 0

    # --- Scheduler ---
    scheduler_enabled: bool = True
    hn_poll_interval_minutes: int = 15
    reddit_poll_interval_minutes: int = 15
    rss_poll_interval_minutes: int = 60
    github_poll_interval_minutes: int = 60
    hf_poll_interval_minutes: int = 60
    arxiv_cron_hour: int = 1
    arxiv_cron_minute: int = 30

    # --- Reddit OAuth ---
    reddit_client_id: str = ""
    reddit_client_secret: str = ""

    # --- Auth (multi-user) ---
    admin_email: str = ""
    resend_api_key: str = ""
    otp_from_email: str = "noreply@resend.dev"
    otp_expire_minutes: int = 10

    # --- WebAuthn (Passkeys) ---
    webauthn_rp_id: str = "localhost"
    webauthn_rp_name: str = "AI News"
    webauthn_origin: str = "http://localhost:5173"

    # --- Observability ---
    log_level: str = "INFO"
    log_format: str = "json"  # json or console

    @property
    def jwt_expire_minutes(self) -> int:
        return self.jwt_access_expire_minutes

    @property
    def enabled_sources_list(self) -> list[str]:
        return [s.strip() for s in self.enabled_sources.split(",") if s.strip()]

    @property
    def topics_list(self) -> list[str]:
        return [t.strip() for t in self.topics.split(",") if t.strip()]

    @property
    def hn_search_queries_list(self) -> list[str]:
        return [q.strip() for q in self.hn_search_queries.split(",") if q.strip()]

    @property
    def arxiv_categories_list(self) -> list[str]:
        return [c.strip() for c in self.arxiv_categories.split(",") if c.strip()]

    @property
    def arxiv_keywords_list(self) -> list[str]:
        return [k.strip() for k in self.arxiv_keywords.split(",") if k.strip()]

    @property
    def reddit_subreddits_list(self) -> list[str]:
        return [s.strip() for s in self.reddit_subreddits.split(",") if s.strip()]

    @property
    def rss_feeds_list(self) -> list[str]:
        return [f.strip() for f in self.rss_feeds.split(",") if f.strip()]

    @property
    def github_search_queries_list(self) -> list[str]:
        return [q.strip() for q in self.github_search_queries.split(",") if q.strip()]

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def trusted_news_domains_list(self) -> list[str]:
        return [d.strip() for d in self.trusted_news_domains.split(",") if d.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
