"""Pydantic schemas for API request/response models."""

from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str
    database: str


class NewsItemResponse(BaseModel):
    id: uuid.UUID
    title: str
    summary: str | None = None
    url: str | None = None
    source: str
    topic: str | None = None
    relevance_score: float | None = None
    dev_value_score: float | None = None
    credibility_score: float | None = None
    priority: int | None = None
    trending: bool = False
    published_at: datetime | None = None
    created_at: datetime
    author: str | None = None
    score: int | None = None

    model_config = {"from_attributes": True}


class BriefingResponse(BaseModel):
    date: date
    total_items: int | None = None
    items_extracted: int | None = None
    items_after_dedup: int | None = None
    items_filtered: int | None = None
    trending_count: int | None = None
    duration_seconds: float | None = None
    sources_used: dict | None = None
    generated_at: datetime
    items: list[NewsItemResponse] = []

    model_config = {"from_attributes": True}


class TokenRequest(BaseModel):
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class StatsSummaryResponse(BaseModel):
    total_items: int
    items_today: int
    sources_count: int
    topics_count: int
    trending_today: int


class StatsGroupResponse(BaseModel):
    name: str
    count: int


class StatsDateResponse(BaseModel):
    date: date
    count: int


class ErrorResponse(BaseModel):
    code: str
    message: str


class ErrorWrapper(BaseModel):
    error: ErrorResponse


class TokenResponseV2(BaseModel):
    access_token: str
    refresh_token: str
    expires_in: int
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str
