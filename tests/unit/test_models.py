"""Tests for src.core.models -- ORM model definitions and constants."""

from __future__ import annotations

from src.core.models import (
    VALID_SOURCES,
    VALID_TOPICS,
    Base,
    DailyBriefing,
    ItemEmbedding,
    NewsItem,
    OtpCode,
    User,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
class TestValidTopics:
    """Ensure the VALID_TOPICS tuple matches the expected categories."""

    def test_valid_topics_is_tuple(self):
        assert isinstance(VALID_TOPICS, tuple)

    def test_valid_topics_contains_expected(self):
        expected = {
            "models",
            "papers",
            "agents",
            "products",
            "tools",
            "open_source",
            "regulation",
        }
        assert set(VALID_TOPICS) == expected

    def test_valid_topics_length(self):
        assert len(VALID_TOPICS) == 7


class TestValidSources:
    """Ensure the VALID_SOURCES tuple matches the expected sources."""

    def test_valid_sources_is_tuple(self):
        assert isinstance(VALID_SOURCES, tuple)

    def test_valid_sources_contains_expected(self):
        expected = {
            "hackernews",
            "arxiv",
            "reddit",
            "rss",
            "github",
            "huggingface",
        }
        assert set(VALID_SOURCES) == expected

    def test_valid_sources_length(self):
        assert len(VALID_SOURCES) == 6


# ---------------------------------------------------------------------------
# NewsItem model
# ---------------------------------------------------------------------------
class TestNewsItemModel:
    """Verify the NewsItem ORM model has all expected columns."""

    def test_tablename(self):
        assert NewsItem.__tablename__ == "news_items"

    def test_has_all_expected_columns(self):
        column_names = {c.name for c in NewsItem.__table__.columns}
        expected_columns = {
            "id",
            "title",
            "summary",
            "url",
            "source",
            "topic",
            "relevance_score",
            "dev_value_score",
            "credibility_score",
            "priority",
            "trending",
            "published_at",
            "created_at",
            "content_hash",
            "url_hash",
            "full_text",
            "author",
            "score",
            "metadata",
            "language",
            "search_vector",
        }
        assert expected_columns.issubset(column_names)

    def test_primary_key_is_id(self):
        pk_cols = [c.name for c in NewsItem.__table__.primary_key.columns]
        assert pk_cols == ["id"]

    def test_content_hash_is_unique(self):
        col = NewsItem.__table__.c.content_hash
        assert col.unique is True

    def test_title_is_not_nullable(self):
        col = NewsItem.__table__.c.title
        assert col.nullable is False

    def test_source_is_not_nullable(self):
        col = NewsItem.__table__.c.source
        assert col.nullable is False

    def test_inherits_from_base(self):
        assert issubclass(NewsItem, Base)


# ---------------------------------------------------------------------------
# DailyBriefing model
# ---------------------------------------------------------------------------
class TestDailyBriefingModel:
    """Verify the DailyBriefing ORM model structure."""

    def test_tablename(self):
        assert DailyBriefing.__tablename__ == "daily_briefings"

    def test_primary_key_is_date(self):
        pk_cols = [c.name for c in DailyBriefing.__table__.primary_key.columns]
        assert pk_cols == ["date"]

    def test_has_expected_columns(self):
        column_names = {c.name for c in DailyBriefing.__table__.columns}
        expected = {
            "date",
            "total_items",
            "items_extracted",
            "items_after_dedup",
            "items_filtered",
            "trending_count",
            "duration_seconds",
            "sources_used",
            "generated_at",
        }
        assert expected.issubset(column_names)

    def test_inherits_from_base(self):
        assert issubclass(DailyBriefing, Base)


# ---------------------------------------------------------------------------
# ItemEmbedding model
# ---------------------------------------------------------------------------
class TestItemEmbeddingModel:
    """Verify the ItemEmbedding ORM model structure."""

    def test_tablename(self):
        assert ItemEmbedding.__tablename__ == "item_embeddings"

    def test_composite_primary_key(self):
        pk_cols = sorted(c.name for c in ItemEmbedding.__table__.primary_key.columns)
        assert pk_cols == ["item_id", "model"]

    def test_has_created_at(self):
        column_names = {c.name for c in ItemEmbedding.__table__.columns}
        assert "created_at" in column_names


# ---------------------------------------------------------------------------
# Topic constraint validation
# ---------------------------------------------------------------------------
class TestTopicConstraint:
    """Verify the CHECK constraint on NewsItem.topic rejects invalid values."""

    def test_valid_topic_check_constraint_exists(self):
        """The table has a CHECK constraint named 'valid_topic'."""
        constraints = NewsItem.__table__.constraints  # type: ignore[attr-defined]
        check_constraints = [
            c for c in constraints if hasattr(c, "sqltext") and c.name == "valid_topic"
        ]
        assert len(check_constraints) == 1

    def test_valid_topic_constraint_references_all_topics(self):
        """The CHECK constraint SQL text mentions every VALID_TOPICS entry."""
        constraints = NewsItem.__table__.constraints  # type: ignore[attr-defined]
        check_constraint = next(
            c for c in constraints if hasattr(c, "sqltext") and c.name == "valid_topic"
        )
        sql_text = str(check_constraint.sqltext)
        for topic in VALID_TOPICS:
            assert topic in sql_text, f"Topic '{topic}' not found in constraint SQL"
        # An invalid topic should NOT appear in the constraint
        assert "invalid_topic" not in sql_text


# ---------------------------------------------------------------------------
# User model
# ---------------------------------------------------------------------------
class TestUserModel:
    """User ORM model structure."""

    def test_user_tablename(self):
        assert User.__tablename__ == "users"

    def test_user_has_expected_columns(self):
        columns = {c.name for c in User.__table__.columns}
        expected = {"id", "email", "name", "role", "created_at", "last_login_at"}
        assert expected.issubset(columns)

    def test_user_role_default(self):
        role_col = User.__table__.columns["role"]
        assert role_col.server_default.arg.text == "'reader'"

    def test_user_email_is_unique(self):
        col = User.__table__.c.email
        assert col.unique is True

    def test_user_email_not_nullable(self):
        col = User.__table__.c.email
        assert col.nullable is False

    def test_user_inherits_from_base(self):
        assert issubclass(User, Base)

    def test_valid_role_constraint_exists(self):
        constraints = User.__table__.constraints
        check_constraints = [
            c for c in constraints if hasattr(c, "sqltext") and c.name == "valid_role"
        ]
        assert len(check_constraints) == 1


# ---------------------------------------------------------------------------
# OtpCode model
# ---------------------------------------------------------------------------
class TestOtpCodeModel:
    """OTP code ORM model structure."""

    def test_otp_code_tablename(self):
        assert OtpCode.__tablename__ == "otp_codes"

    def test_otp_code_has_expected_columns(self):
        columns = {c.name for c in OtpCode.__table__.columns}
        expected = {"id", "email", "code", "expires_at", "used", "created_at"}
        assert expected.issubset(columns)

    def test_otp_code_used_default_false(self):
        used_col = OtpCode.__table__.columns["used"]
        assert used_col.server_default.arg.text == "false"

    def test_otp_code_inherits_from_base(self):
        assert issubclass(OtpCode, Base)

    def test_otp_code_lookup_index_exists(self):
        index_names = {idx.name for idx in OtpCode.__table__.indexes}
        assert "idx_otp_codes_lookup" in index_names
