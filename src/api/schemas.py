"""Pydantic schemas for API request/response models."""

from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field


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
    composite_score: float | None = None

    model_config = {"from_attributes": True}


class BriefingResponse(BaseModel):
    date: date
    total_items: int | None = None
    items_extracted: int | None = None
    items_after_dedup: int | None = None
    items_filtered: int | None = None
    trending_count: int | None = None
    duration_seconds: float | None = None
    sources_used: dict[str, list[str]] | None = None
    generated_at: datetime | None = None
    items: list[NewsItemResponse] = []

    model_config = {"from_attributes": True}


class TokenRequest(BaseModel):
    password: str


class CountResponse(BaseModel):
    count: int


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


class GuestTokenResponse(BaseModel):
    access_token: str
    expires_in: int
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


class ChatRequest(BaseModel):
    question: str = Field(..., min_length=3, max_length=500)
    topic: str | None = Field(None, description="Filter context by topic")
    limit: int = Field(5, ge=1, le=20, description="Number of context items")


class SourceInfo(BaseModel):
    name: str
    count: int


class SourcesResponse(BaseModel):
    sources: list[SourceInfo]


class StatsGroupDateResponse(BaseModel):
    date: date
    group: str
    count: int


class ScoreDistributionResponse(BaseModel):
    range: str
    min_score: int
    max_score: int
    count: int


# --- OTP Auth ---
class OtpRequestBody(BaseModel):
    email: str = Field(..., pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class OtpVerifyBody(BaseModel):
    email: str = Field(..., pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    code: str = Field(..., min_length=6, max_length=6, pattern=r"^\d{6}$")


class OtpRequestResponse(BaseModel):
    message: str


class UserResponse(BaseModel):
    id: uuid.UUID
    email: str
    name: str | None
    role: str

    model_config = {"from_attributes": True}


# --- WebAuthn (Passkeys) ---
class WebAuthnLoginOptionsRequest(BaseModel):
    email: str = Field(..., pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class WebAuthnRegisterVerifyRequest(BaseModel):
    device_name: str = Field(..., min_length=1, max_length=100)
    credential: dict  # Raw authenticator response from browser


class WebAuthnLoginVerifyRequest(BaseModel):
    email: str = Field(..., pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    credential: dict  # Raw authenticator assertion from browser


class WebAuthnCredentialResponse(BaseModel):
    id: uuid.UUID
    device_name: str
    backed_up: bool
    created_at: datetime
    last_used_at: datetime | None

    model_config = {"from_attributes": True}
