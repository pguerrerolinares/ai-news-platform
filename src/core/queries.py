"""Shared query expressions for reuse across route modules."""

from __future__ import annotations

from sqlalchemy import func

from src.core.models import NewsItem

effective_date = func.coalesce(NewsItem.published_at, NewsItem.created_at)
