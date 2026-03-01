"""SQLAlchemy ORM models for the AI News Platform."""

from __future__ import annotations

import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    column,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

VALID_ROLES = ("admin", "reader")


class Base(DeclarativeBase):
    pass


VALID_TOPICS = (
    "models",
    "papers",
    "agents",
    "products",
    "tools",
    "open_source",
    "regulation",
)

VALID_SOURCES = (
    "hackernews",
    "arxiv",
    "reddit",
    "rss",
    "github",
    "huggingface",
)


class NewsItem(Base):
    __tablename__ = "news_items"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    title: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[str | None] = mapped_column(Text)
    url: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(50), nullable=False)
    topic: Mapped[str | None] = mapped_column(String(50))
    relevance_score: Mapped[float | None] = mapped_column(Float)
    dev_value_score: Mapped[float | None] = mapped_column(Float)
    credibility_score: Mapped[float | None] = mapped_column(Float)
    priority: Mapped[int | None] = mapped_column(Integer)
    trending: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    content_hash: Mapped[str | None] = mapped_column(Text, unique=True)
    url_hash: Mapped[str | None] = mapped_column(Text)
    full_text: Mapped[str | None] = mapped_column(Text)
    author: Mapped[str | None] = mapped_column(Text)
    score: Mapped[int | None] = mapped_column(Integer)
    source_created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )
    composite_score: Mapped[float | None] = mapped_column(Float, default=None)
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSONB)
    language: Mapped[str] = mapped_column(String(5), server_default=text("'en'"))
    search_vector: Mapped[str | None] = mapped_column(TSVECTOR, deferred=True)

    __table_args__ = (
        CheckConstraint(
            f"topic IS NULL OR topic IN ({','.join(repr(t) for t in VALID_TOPICS)})",
            name="valid_topic",
        ),
        Index("idx_news_items_date", "published_at"),
        Index("idx_news_items_topic", "topic"),
        Index("idx_news_items_source", "source"),
        Index("idx_news_items_url_hash", "url_hash"),
        # M14: Performance indexes
        Index("idx_news_items_score", "score"),
        Index("idx_news_items_source_date", "source", "published_at"),
        Index("idx_news_items_topic_date", "topic", "published_at"),
        Index("idx_news_items_composite_score", "composite_score"),
        Index("idx_news_items_created_at", "created_at"),
        Index(
            "idx_news_items_effective_date",
            func.coalesce(column("published_at"), column("created_at")).desc(),
        ),
        Index("idx_news_items_search", "search_vector", postgresql_using="gin"),
        Index(
            "idx_news_items_trending_date",
            func.coalesce(column("published_at"), column("created_at")).desc(),
            postgresql_where=text("trending = true"),
        ),
    )


class DailyBriefing(Base):
    __tablename__ = "daily_briefings"

    date: Mapped[datetime] = mapped_column(Date, primary_key=True)
    total_items: Mapped[int | None] = mapped_column(Integer)
    items_extracted: Mapped[int | None] = mapped_column(Integer)
    items_after_dedup: Mapped[int | None] = mapped_column(Integer)
    items_filtered: Mapped[int | None] = mapped_column(Integer)
    trending_count: Mapped[int | None] = mapped_column(Integer)
    duration_seconds: Mapped[float | None] = mapped_column(Float)
    sources_used: Mapped[dict | None] = mapped_column(JSONB)
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class ItemEmbedding(Base):
    """Vector embeddings for RAG search."""

    __tablename__ = "item_embeddings"

    item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("news_items.id", ondelete="CASCADE"),
        primary_key=True,
    )
    model: Mapped[str] = mapped_column(Text, primary_key=True, nullable=False)
    embedding = mapped_column(Vector(1536))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index(
            "idx_embeddings_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )


class RawExtraction(Base):
    """Raw API responses preserved for future reprocessing."""

    __tablename__ = "raw_extractions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    source: Mapped[str] = mapped_column(String(50), nullable=False)
    source_id: Mapped[str] = mapped_column(String(255), nullable=False)
    raw_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    extracted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    backfill_batch: Mapped[str | None] = mapped_column(String(50))

    __table_args__ = (
        UniqueConstraint("source", "source_id", name="uq_raw_source_id"),
        Index("idx_raw_source", "source"),
        Index("idx_raw_batch", "backfill_batch"),
    )


class User(Base):
    """Registered user account."""

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    email: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    name: Mapped[str | None] = mapped_column(Text)
    role: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        server_default=text("'reader'"),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        CheckConstraint("role IN ('admin', 'reader')", name="valid_role"),
        Index("idx_users_email", "email"),
    )


class OtpCode(Base):
    """Email OTP verification code."""

    __tablename__ = "otp_codes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(Text, nullable=False)
    code: Mapped[str] = mapped_column(String(6), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    __table_args__ = (Index("idx_otp_codes_lookup", "email", "used", "expires_at"),)


class WebAuthnCredential(Base):
    """WebAuthn/passkey credential for biometric authentication."""

    __tablename__ = "webauthn_credentials"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    credential_id: Mapped[bytes] = mapped_column(
        "credential_id",
        nullable=False,
        unique=True,
    )
    public_key: Mapped[bytes] = mapped_column(nullable=False)
    sign_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    device_name: Mapped[str] = mapped_column(Text, nullable=False)
    transports: Mapped[list[str] | None] = mapped_column(JSONB)
    backed_up: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (Index("idx_webauthn_user_id", "user_id"),)
