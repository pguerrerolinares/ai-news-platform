# Multi-User Auth Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace shared password auth with passwordless email OTP + real user accounts with admin/reader roles.

**Architecture:** New `users` + `otp_codes` tables via Alembic migration. OTP service generates 6-digit codes and sends via Resend API (plain httpx). JWT tokens now carry user UUID, role, and email. Frontend Login page becomes a two-step email→OTP flow. Shared password login kept for backward compatibility.

**Tech Stack:** FastAPI, SQLAlchemy async, Alembic, Resend API (httpx), React 19 + Shadcn UI

---

### Task 1: Add Auth Config Settings

**Files:**
- Modify: `src/core/config.py`
- Modify: `.env.example`
- Test: `tests/unit/test_config.py`

**Step 1: Write the failing tests**

Add to `tests/unit/test_config.py`:

```python
class TestAuthConfig:
    """Auth-related configuration settings."""

    def test_admin_email_default_empty(self):
        settings = Settings(
            database_url="postgresql+asyncpg://x:x@localhost/x",
            jwt_secret="test-secret",
            shared_password="test-pw",
        )
        assert settings.admin_email == ""

    def test_resend_api_key_default_empty(self):
        settings = Settings(
            database_url="postgresql+asyncpg://x:x@localhost/x",
            jwt_secret="test-secret",
            shared_password="test-pw",
        )
        assert settings.resend_api_key == ""

    def test_otp_from_email_default(self):
        settings = Settings(
            database_url="postgresql+asyncpg://x:x@localhost/x",
            jwt_secret="test-secret",
            shared_password="test-pw",
        )
        assert settings.otp_from_email == "noreply@resend.dev"

    def test_otp_expire_minutes_default(self):
        settings = Settings(
            database_url="postgresql+asyncpg://x:x@localhost/x",
            jwt_secret="test-secret",
            shared_password="test-pw",
        )
        assert settings.otp_expire_minutes == 10
```

**Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/unit/test_config.py::TestAuthConfig -v`
Expected: FAIL (attributes not found)

**Step 3: Add config settings**

Add to `src/core/config.py` in the `Settings` class, after the Reddit OAuth section:

```python
    # --- Auth (multi-user) ---
    admin_email: str = ""
    resend_api_key: str = ""
    otp_from_email: str = "noreply@resend.dev"
    otp_expire_minutes: int = 10
    otp_max_active: int = 3
```

Add to `.env.example`:

```bash
# --- Auth (multi-user) ---
ADMIN_EMAIL=                        # Superadmin email (auto-admin on first login)
RESEND_API_KEY=                     # Resend API key for OTP emails (resend.com)
OTP_FROM_EMAIL=noreply@resend.dev   # Sender email for OTP codes
```

**Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/unit/test_config.py::TestAuthConfig -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/core/config.py .env.example tests/unit/test_config.py
git commit -m "feat: add auth config settings for multi-user OTP"
```

---

### Task 2: Alembic Migration — users + otp_codes Tables

**Files:**
- Create: `alembic/versions/005_users_and_otp.py`
- Modify: `src/core/models.py`
- Test: `tests/unit/test_models.py`

**Step 1: Write the failing tests**

Add to `tests/unit/test_models.py`:

```python
class TestUserModel:
    """User ORM model structure."""

    def test_user_tablename(self):
        from src.core.models import User
        assert User.__tablename__ == "users"

    def test_user_has_expected_columns(self):
        from src.core.models import User
        columns = {c.name for c in User.__table__.columns}
        expected = {"id", "email", "name", "role", "created_at", "last_login_at"}
        assert expected.issubset(columns)

    def test_user_role_default(self):
        from src.core.models import User
        role_col = User.__table__.columns["role"]
        assert role_col.server_default.arg.text == "'reader'"


class TestOtpCodeModel:
    """OTP code ORM model structure."""

    def test_otp_code_tablename(self):
        from src.core.models import OtpCode
        assert OtpCode.__tablename__ == "otp_codes"

    def test_otp_code_has_expected_columns(self):
        from src.core.models import OtpCode
        columns = {c.name for c in OtpCode.__table__.columns}
        expected = {"id", "email", "code", "expires_at", "used", "created_at"}
        assert expected.issubset(columns)
```

**Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/unit/test_models.py::TestUserModel -v`
Expected: FAIL (ImportError: cannot import name 'User')

**Step 3: Add ORM models**

Add to `src/core/models.py` after the `RawExtraction` class:

```python
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
        String(20), nullable=False, server_default=text("'reader'"),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(),
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
        DateTime(timezone=True), server_default=func.now(),
    )

    __table_args__ = (
        Index("idx_otp_codes_lookup", "email", "used", "expires_at"),
    )
```

**Step 4: Create Alembic migration**

Create `alembic/versions/005_users_and_otp.py`:

```python
"""Add users and otp_codes tables for multi-user auth.

Revision ID: 005
Revises: 004
Create Date: 2026-02-25
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "005"
down_revision = "004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("email", sa.Text(), nullable=False, unique=True),
        sa.Column("name", sa.Text(), nullable=True),
        sa.Column("role", sa.String(20), nullable=False, server_default=sa.text("'reader'")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("role IN ('admin', 'reader')", name="valid_role"),
    )
    op.create_index("idx_users_email", "users", ["email"])

    op.create_table(
        "otp_codes",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("email", sa.Text(), nullable=False),
        sa.Column("code", sa.String(6), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used", sa.Boolean(), server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_otp_codes_lookup", "otp_codes", ["email", "used", "expires_at"])


def downgrade() -> None:
    op.drop_table("otp_codes")
    op.drop_table("users")
```

**Step 5: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/unit/test_models.py::TestUserModel tests/unit/test_models.py::TestOtpCodeModel -v`
Expected: PASS

**Step 6: Commit**

```bash
git add src/core/models.py alembic/versions/005_users_and_otp.py tests/unit/test_models.py
git commit -m "feat: User + OtpCode ORM models and Alembic migration 005"
```

---

### Task 3: OTP Service — Generate, Send, Verify

**Files:**
- Create: `src/api/otp.py`
- Test: `tests/unit/test_otp.py`

**Step 1: Write the failing tests**

Create `tests/unit/test_otp.py`:

```python
"""Tests for src.api.otp — OTP generation, sending, and verification."""
from __future__ import annotations

import time
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest

from src.api.otp import generate_otp_code, send_otp_email, verify_otp_code


class TestGenerateOtpCode:
    def test_returns_6_digit_string(self):
        code = generate_otp_code()
        assert len(code) == 6
        assert code.isdigit()

    def test_codes_are_zero_padded(self):
        # Generate many codes, at least some should start with 0
        codes = [generate_otp_code() for _ in range(1000)]
        assert all(len(c) == 6 for c in codes)

    def test_codes_vary(self):
        codes = {generate_otp_code() for _ in range(100)}
        assert len(codes) > 50  # Should be highly varied


class TestSendOtpEmail:
    @pytest.fixture
    def mock_settings(self):
        settings = type("S", (), {
            "resend_api_key": "re_test_key",
            "otp_from_email": "test@resend.dev",
        })()
        return settings

    async def test_sends_email_via_resend(self, mock_settings, respx_mock):
        import httpx
        respx_mock.post("https://api.resend.com/emails").mock(
            return_value=httpx.Response(200, json={"id": "email_123"}),
        )
        with patch("src.api.otp.get_settings", return_value=mock_settings):
            await send_otp_email("user@example.com", "123456")

        assert respx_mock.calls.call_count == 1
        req = respx_mock.calls[0].request
        assert b"123456" in req.content
        assert b"user@example.com" in req.content

    async def test_raises_on_resend_failure(self, mock_settings, respx_mock):
        import httpx
        respx_mock.post("https://api.resend.com/emails").mock(
            return_value=httpx.Response(500, text="Internal error"),
        )
        with patch("src.api.otp.get_settings", return_value=mock_settings):
            with pytest.raises(Exception):
                await send_otp_email("user@example.com", "123456")

    async def test_skips_when_no_api_key(self, respx_mock):
        settings = type("S", (), {
            "resend_api_key": "",
            "otp_from_email": "test@resend.dev",
        })()
        with patch("src.api.otp.get_settings", return_value=settings):
            # Should not raise — logs warning and returns (dev mode)
            await send_otp_email("user@example.com", "123456")
        assert respx_mock.calls.call_count == 0
```

**Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/unit/test_otp.py -v`
Expected: FAIL (ImportError)

**Step 3: Implement OTP service**

Create `src/api/otp.py`:

```python
"""OTP code generation, email sending (Resend), and verification."""
from __future__ import annotations

import secrets

import httpx

from src.core.config import get_settings
from src.core.logging import get_logger

logger = get_logger(__name__)

RESEND_URL = "https://api.resend.com/emails"


def generate_otp_code() -> str:
    """Generate a cryptographically secure 6-digit OTP code."""
    return f"{secrets.randbelow(1_000_000):06d}"


async def send_otp_email(email: str, code: str) -> None:
    """Send OTP code via Resend API.

    If RESEND_API_KEY is empty, logs the code instead (dev mode).
    Raises on Resend API failure.
    """
    settings = get_settings()

    if not settings.resend_api_key:
        logger.warning("otp_email_skipped_no_api_key", email=email, code=code)
        return

    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(
            RESEND_URL,
            headers={"Authorization": f"Bearer {settings.resend_api_key}"},
            json={
                "from": settings.otp_from_email,
                "to": [email],
                "subject": "Tu codigo de acceso — AI News",
                "html": (
                    f"<p>Tu codigo es: <strong>{code}</strong></p>"
                    f"<p>Expira en {settings.otp_expire_minutes} minutos.</p>"
                ),
            },
        )
        resp.raise_for_status()
        logger.info("otp_email_sent", email=email)
```

**Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/unit/test_otp.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/api/otp.py tests/unit/test_otp.py
git commit -m "feat: OTP service — generate codes and send via Resend API"
```

---

### Task 4: Auth Refactor — UserClaims + require_admin

**Files:**
- Modify: `src/api/auth.py`
- Modify: `tests/unit/test_auth.py`

**Step 1: Write the failing tests**

Add to `tests/unit/test_auth.py`:

```python
from src.api.auth import UserClaims, create_access_token


class TestUserClaims:
    def test_user_claims_from_token(self):
        token = create_access_token(
            subject="550e8400-e29b-41d4-a716-446655440000",
            role="admin",
            email="admin@test.com",
        )
        # Decode manually to verify payload
        from jose import jwt
        from src.core.config import get_settings
        settings = get_settings()
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        assert payload["sub"] == "550e8400-e29b-41d4-a716-446655440000"
        assert payload["role"] == "admin"
        assert payload["email"] == "admin@test.com"

    def test_access_token_backward_compatible(self):
        """Old-style tokens without role/email still work."""
        token = create_access_token(subject="user")
        from jose import jwt
        from src.core.config import get_settings
        settings = get_settings()
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        assert payload["sub"] == "user"
        assert payload.get("role") is None
```

**Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/unit/test_auth.py::TestUserClaims -v`
Expected: FAIL (signature mismatch — `create_access_token` doesn't accept `role`/`email`)

**Step 3: Refactor auth.py**

Modify `src/api/auth.py`:

1. Add `UserClaims` dataclass:
```python
from dataclasses import dataclass

@dataclass
class UserClaims:
    """Decoded JWT claims for an authenticated user."""
    sub: str
    role: str
    email: str
```

2. Update `create_access_token` signature:
```python
def create_access_token(
    subject: str = "user",
    role: str | None = None,
    email: str | None = None,
) -> str:
    settings = get_settings()
    expire = datetime.now(tz=UTC) + timedelta(minutes=settings.jwt_access_expire_minutes)
    payload: dict[str, object] = {"sub": subject, "exp": expire, "type": "access"}
    if role is not None:
        payload["role"] = role
    if email is not None:
        payload["email"] = email
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
```

3. Update `create_refresh_token` to also accept `role`/`email`:
```python
def create_refresh_token(
    subject: str = "user",
    role: str | None = None,
    email: str | None = None,
) -> str:
    settings = get_settings()
    expire = datetime.now(tz=UTC) + timedelta(days=settings.jwt_refresh_expire_days)
    payload: dict[str, object] = {
        "sub": subject, "exp": expire, "type": "refresh", "jti": uuid.uuid4().hex,
    }
    if role is not None:
        payload["role"] = role
    if email is not None:
        payload["email"] = email
    token = jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    # ... rest unchanged (store in _refresh_tokens)
```

4. Update `require_auth` to return `UserClaims`:
```python
async def require_auth(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> UserClaims:
    settings = get_settings()
    try:
        payload = jwt.decode(
            credentials.credentials,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
        )
        if payload.get("type") not in ("access", None):
            raise APIError(401, "INVALID_TOKEN", "Token is not an access token")
        sub: str | None = payload.get("sub")
        if sub is None:
            raise APIError(401, "INVALID_TOKEN", "Invalid or expired token")
        return UserClaims(
            sub=sub,
            role=payload.get("role", "reader"),
            email=payload.get("email", ""),
        )
    except JWTError:
        raise APIError(401, "INVALID_TOKEN", "Invalid or expired token") from None
```

5. Add `require_admin`:
```python
async def require_admin(
    user: UserClaims = Depends(require_auth),
) -> UserClaims:
    """Verify user has admin role."""
    if user.role != "admin":
        raise APIError(403, "FORBIDDEN", "Admin access required")
    return user
```

6. Update `validate_refresh_token` to return `UserClaims`:
```python
def validate_refresh_token(token: str) -> UserClaims:
    # ... decode JWT, check hash store, rotate ...
    return UserClaims(
        sub=sub,
        role=payload.get("role", "reader"),
        email=payload.get("email", ""),
    )
```

**Step 4: Fix existing tests that depend on `require_auth` returning `str`**

Search existing test files for usage of `require_auth` return value. Update routes that use `subject: str = Depends(require_auth)` to use `user: UserClaims = Depends(require_auth)`. The `user.sub` replaces the old `subject` string.

Specifically update these route files to accept `UserClaims` instead of `str`:
- `src/api/routes/items.py`
- `src/api/routes/briefings.py`
- `src/api/routes/search.py`
- `src/api/routes/chat.py`
- `src/api/routes/stats.py`
- `src/api/routes/sources.py`

Each file: change `_subject: str = Depends(require_auth)` to `_user: UserClaims = Depends(require_auth)` (variable name starts with `_` since it's unused).

Also update `src/api/routes/auth.py` — the refresh endpoint returns subject from `validate_refresh_token`, which now returns `UserClaims`.

**Step 5: Run all tests to verify they pass**

Run: `.venv/bin/pytest tests/unit/ -v --timeout=30`
Expected: All PASS (backward compatible — old tokens get `role="reader"`, `email=""`)

**Step 6: Commit**

```bash
git add src/api/auth.py src/api/routes/ tests/unit/test_auth.py
git commit -m "feat: UserClaims + require_admin, backward-compatible auth refactor"
```

---

### Task 5: OTP Auth Endpoints

**Files:**
- Create: `src/api/routes/otp.py`
- Modify: `src/api/schemas.py`
- Modify: `src/api/app.py`
- Test: `tests/unit/test_otp_routes.py`

**Step 1: Write the failing tests**

Create `tests/unit/test_otp_routes.py`:

```python
"""Tests for OTP auth endpoints."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch, MagicMock
import uuid

import pytest
from fastapi.testclient import TestClient

from src.api.app import app


@pytest.fixture
def client():
    return TestClient(app)


class TestOtpRequest:
    def test_request_otp_returns_200(self, client):
        """POST /api/auth/otp/request sends OTP and returns success."""
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        mock_session.execute = AsyncMock(return_value=MagicMock(scalars=lambda: MagicMock(all=lambda: [])))

        with (
            patch("src.api.routes.otp.get_async_session", return_value=mock_session),
            patch("src.api.routes.otp.send_otp_email", new_callable=AsyncMock) as mock_send,
            patch("src.api.routes.otp.generate_otp_code", return_value="123456"),
        ):
            resp = client.post("/api/auth/otp/request", json={"email": "test@example.com"})

        assert resp.status_code == 200
        data = resp.json()
        assert data["message"] == "Code sent"
        mock_send.assert_called_once()

    def test_request_otp_invalid_email(self, client):
        resp = client.post("/api/auth/otp/request", json={"email": "not-an-email"})
        assert resp.status_code == 422


class TestOtpVerify:
    def test_verify_valid_code_returns_tokens(self, client):
        """POST /api/auth/otp/verify with valid code returns JWT tokens."""
        mock_user = MagicMock()
        mock_user.id = uuid.uuid4()
        mock_user.email = "test@example.com"
        mock_user.name = "test"
        mock_user.role = "reader"

        mock_otp = MagicMock()
        mock_otp.code = "123456"
        mock_otp.used = False
        mock_otp.expires_at = MagicMock()

        # Complex DB mocking — this test verifies the endpoint contract
        with (
            patch("src.api.routes.otp._verify_and_login", new_callable=AsyncMock) as mock_verify,
        ):
            mock_verify.return_value = mock_user
            resp = client.post("/api/auth/otp/verify", json={
                "email": "test@example.com",
                "code": "123456",
            })

        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"

    def test_verify_invalid_code_returns_401(self, client):
        with patch("src.api.routes.otp._verify_and_login", new_callable=AsyncMock) as mock_verify:
            from src.api.errors import APIError
            mock_verify.side_effect = APIError(401, "INVALID_OTP", "Invalid or expired code")
            resp = client.post("/api/auth/otp/verify", json={
                "email": "test@example.com",
                "code": "999999",
            })

        assert resp.status_code == 401
```

**Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/unit/test_otp_routes.py -v`
Expected: FAIL (ImportError)

**Step 3: Add schemas**

Add to `src/api/schemas.py`:

```python
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
```

**Step 4: Create OTP routes**

Create `src/api/routes/otp.py`:

```python
"""OTP authentication endpoints."""
from __future__ import annotations

import hmac
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Request
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy import select, update

from src.api.auth import UserClaims, create_access_token, create_refresh_token, require_auth
from src.api.errors import APIError
from src.api.otp import generate_otp_code, send_otp_email
from src.api.schemas import (
    ErrorWrapper,
    OtpRequestBody,
    OtpRequestResponse,
    OtpVerifyBody,
    TokenResponseV2,
    UserResponse,
)
from src.core.config import get_settings
from src.core.database import get_async_session
from src.core.logging import get_logger
from src.core.models import OtpCode, User

logger = get_logger(__name__)
router = APIRouter(prefix="/api/auth", tags=["auth"])
limiter = Limiter(key_func=get_remote_address)


@router.post("/otp/request", response_model=OtpRequestResponse)
@limiter.limit("3/minute")
async def request_otp(request: Request, body: OtpRequestBody) -> OtpRequestResponse:
    """Send a 6-digit OTP code to the given email."""
    settings = get_settings()
    email = body.email.lower().strip()
    code = generate_otp_code()
    expires_at = datetime.now(tz=UTC) + timedelta(minutes=settings.otp_expire_minutes)

    async with get_async_session() as session:
        # Invalidate old unused codes for this email
        await session.execute(
            update(OtpCode)
            .where(OtpCode.email == email, OtpCode.used == False)  # noqa: E712
            .values(used=True)
        )

        # Store new code
        session.add(OtpCode(email=email, code=code, expires_at=expires_at))
        await session.commit()

    await send_otp_email(email, code)
    return OtpRequestResponse(message="Code sent")


async def _verify_and_login(email: str, code: str) -> User:
    """Verify OTP code and upsert user. Returns the User object."""
    settings = get_settings()
    email = email.lower().strip()

    async with get_async_session() as session:
        # Find valid OTP
        result = await session.execute(
            select(OtpCode)
            .where(
                OtpCode.email == email,
                OtpCode.used == False,  # noqa: E712
                OtpCode.expires_at > datetime.now(tz=UTC),
            )
            .order_by(OtpCode.created_at.desc())
            .limit(1)
        )
        otp = result.scalar_one_or_none()

        if otp is None or not hmac.compare_digest(otp.code, code):
            raise APIError(401, "INVALID_OTP", "Invalid or expired code")

        # Mark as used
        otp.used = True

        # Upsert user
        user_result = await session.execute(
            select(User).where(User.email == email)
        )
        user = user_result.scalar_one_or_none()

        if user is None:
            # New user — determine role
            role = "admin" if email == settings.admin_email.lower() else "reader"
            name = email.split("@")[0]
            user = User(email=email, name=name, role=role)
            session.add(user)
        else:
            user.last_login_at = datetime.now(tz=UTC)
            # Promote to admin if ADMIN_EMAIL matches
            if email == settings.admin_email.lower() and user.role != "admin":
                user.role = "admin"

        await session.commit()
        await session.refresh(user)

    return user


@router.post(
    "/otp/verify",
    response_model=TokenResponseV2,
    responses={401: {"model": ErrorWrapper}},
)
@limiter.limit("5/minute")
async def verify_otp(request: Request, body: OtpVerifyBody) -> TokenResponseV2:
    """Verify OTP code and return JWT tokens."""
    settings = get_settings()
    user = await _verify_and_login(body.email, body.code)

    access_token = create_access_token(
        subject=str(user.id), role=user.role, email=user.email,
    )
    refresh_token = create_refresh_token(
        subject=str(user.id), role=user.role, email=user.email,
    )

    return TokenResponseV2(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=settings.jwt_access_expire_minutes * 60,
    )


@router.get("/me", response_model=UserResponse, responses={401: {"model": ErrorWrapper}})
async def get_me(user: UserClaims = __import__("fastapi").Depends(require_auth)) -> UserResponse:
    """Return current authenticated user info."""
    async with get_async_session() as session:
        result = await session.execute(
            select(User).where(User.email == user.email)
        )
        db_user = result.scalar_one_or_none()

    if db_user is None:
        # Legacy token — no user in DB
        return UserResponse(
            id=__import__("uuid").UUID(user.sub) if len(user.sub) > 10 else __import__("uuid").uuid4(),
            email=user.email or "legacy",
            name=user.email.split("@")[0] if user.email else "user",
            role=user.role,
        )

    return UserResponse.model_validate(db_user)
```

**Step 5: Register router in app.py**

Add to `src/api/app.py`:

```python
from src.api.routes.otp import router as otp_router
# ... in the router registration section:
app.include_router(otp_router)
```

**Step 6: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/unit/test_otp_routes.py -v`
Expected: PASS

**Step 7: Run full suite**

Run: `.venv/bin/pytest tests/unit/ -q --timeout=30`
Expected: All PASS

**Step 8: Commit**

```bash
git add src/api/routes/otp.py src/api/schemas.py src/api/app.py tests/unit/test_otp_routes.py
git commit -m "feat: OTP auth endpoints — request, verify, and /me"
```

---

### Task 6: OTP Cleanup Scheduler Job

**Files:**
- Modify: `src/pipeline/scheduler.py`
- Modify: `tests/unit/test_scheduler.py`

**Step 1: Write the failing test**

Add to `tests/unit/test_scheduler.py`:

```python
class TestOtpCleanupJob:
    def test_scheduler_includes_otp_cleanup_job(self):
        settings = _mock_settings(scheduler_enabled=True)
        with patch("src.pipeline.scheduler.get_settings", return_value=settings):
            scheduler = create_scheduler()
        assert scheduler is not None
        job_ids = [j.id for j in scheduler.get_jobs()]
        assert "otp_cleanup" in job_ids
```

**Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/unit/test_scheduler.py::TestOtpCleanupJob -v`
Expected: FAIL (no job named `otp_cleanup`)

**Step 3: Add cleanup job**

Add to `src/pipeline/scheduler.py`:

```python
from src.core.models import OtpCode
from sqlalchemy import delete
from datetime import UTC, datetime, timedelta


async def cleanup_expired_otps() -> None:
    """Purge expired OTP codes older than 1 day."""
    async with get_async_session() as session:
        cutoff = datetime.now(tz=UTC) - timedelta(days=1)
        result = await session.execute(
            delete(OtpCode).where(OtpCode.expires_at < cutoff)
        )
        await session.commit()
        if result.rowcount:
            logger.info("otp_cleanup_done", deleted=result.rowcount)
```

Add to `create_scheduler()` before the `return scheduler` line:

```python
    # OTP cleanup: daily at 02:00 UTC
    scheduler.add_job(
        cleanup_expired_otps,
        CronTrigger(hour=2, minute=0),
        id="otp_cleanup",
        replace_existing=True,
    )
```

**Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/unit/test_scheduler.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/pipeline/scheduler.py tests/unit/test_scheduler.py
git commit -m "feat: OTP cleanup scheduler job — purge expired codes daily"
```

---

### Task 7: Frontend Login — Email OTP Two-Step Flow

**Files:**
- Modify: `frontend/src/pages/Login.tsx`
- Modify: `frontend/src/hooks/use-auth.tsx`
- Modify: `frontend/src/lib/api.ts`

**Step 1: Update use-auth.tsx**

Replace the `AuthContextValue` interface and `login` method:

```typescript
interface User {
  id: string
  email: string
  name: string | null
  role: 'admin' | 'reader'
}

interface AuthContextValue {
  isAuthenticated: boolean
  user: User | null
  requestOtp: (email: string) => Promise<void>
  verifyOtp: (email: string, code: string) => Promise<void>
  loginLegacy: (password: string) => Promise<void>
  logout: () => void
}
```

Add `requestOtp` and `verifyOtp`:

```typescript
const requestOtp = useCallback(async (email: string) => {
  await apiPost('/api/auth/otp/request', { email })
}, [])

const verifyOtp = useCallback(async (email: string, code: string) => {
  const tokens = await apiPost<AuthTokens>('/api/auth/otp/verify', { email, code })
  storeTokens(tokens)
  setIsAuthenticated(true)
}, [])

const loginLegacy = useCallback(async (password: string) => {
  const tokens = await apiPost<AuthTokens>('/api/auth/token', { password })
  storeTokens(tokens)
  setIsAuthenticated(true)
}, [])
```

Keep the old `login` working as `loginLegacy` for backward compatibility.

**Step 2: Rewrite Login.tsx**

Two-step form:
- **Step 1:** Email input + "Enviar codigo" button
- **Step 2:** 6-digit code input (auto-focus, numeric) + "Verificar" button + "Reenviar" link
- Small text link at bottom: "Acceso con contrasena" → toggles to legacy password form

```tsx
export default function Login() {
  const [step, setStep] = useState<'email' | 'code' | 'legacy'>('email')
  const [email, setEmail] = useState('')
  const [code, setCode] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const { requestOtp, verifyOtp, loginLegacy } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()

  const from = getRedirectPath(location)

  async function handleRequestOtp(e: React.FormEvent) {
    e.preventDefault()
    if (!email.trim()) return
    setError('')
    setLoading(true)
    try {
      await requestOtp(email)
      setStep('code')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error al enviar el codigo')
    } finally {
      setLoading(false)
    }
  }

  async function handleVerifyOtp(e: React.FormEvent) {
    e.preventDefault()
    if (code.length !== 6) return
    setError('')
    setLoading(true)
    try {
      await verifyOtp(email, code)
      navigate(from, { replace: true })
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Codigo invalido')
    } finally {
      setLoading(false)
    }
  }

  async function handleLegacyLogin(e: React.FormEvent) {
    e.preventDefault()
    if (!password.trim()) return
    setError('')
    setLoading(true)
    try {
      await loginLegacy(password)
      navigate(from, { replace: true })
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error de autenticacion')
    } finally {
      setLoading(false)
    }
  }

  // ... render three form variants based on step
}
```

**Step 3: Build and verify**

Run: `cd frontend && npm run build`
Expected: Build succeeds

**Step 4: Commit**

```bash
git add frontend/src/pages/Login.tsx frontend/src/hooks/use-auth.tsx
git commit -m "feat: frontend Login — email OTP two-step flow + legacy fallback"
```

---

### Task 8: Update Shared Password Endpoint for Backward Compatibility

**Files:**
- Modify: `src/api/routes/auth.py`
- Modify: `tests/unit/test_auth.py`

**Step 1: Update shared password login**

Modify `src/api/routes/auth.py` — the `login` function should pass `role` and `email` to token creators:

```python
@router.post("/token", response_model=TokenResponseV2, responses={401: {"model": ErrorWrapper}})
@limiter.limit("5/minute")
async def login(request: Request, body: TokenRequest) -> TokenResponseV2:
    settings = get_settings()
    if not hmac.compare_digest(body.password, settings.shared_password):
        raise APIError(401, "INVALID_PASSWORD", "Invalid password")

    access_token = create_access_token(subject="legacy", role="reader")
    refresh_token = create_refresh_token(subject="legacy", role="reader")

    return TokenResponseV2(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=settings.jwt_access_expire_minutes * 60,
    )
```

Update the refresh endpoint to propagate claims from the `UserClaims` returned by `validate_refresh_token`:

```python
@router.post("/refresh", response_model=TokenResponseV2, responses={401: {"model": ErrorWrapper}})
@limiter.limit("10/minute")
async def refresh(request: Request, body: RefreshRequest) -> TokenResponseV2:
    settings = get_settings()
    claims = validate_refresh_token(body.refresh_token)

    access_token = create_access_token(
        subject=claims.sub, role=claims.role, email=claims.email,
    )
    new_refresh_token = create_refresh_token(
        subject=claims.sub, role=claims.role, email=claims.email,
    )

    return TokenResponseV2(
        access_token=access_token,
        refresh_token=new_refresh_token,
        expires_in=settings.jwt_access_expire_minutes * 60,
    )
```

**Step 2: Run all tests**

Run: `.venv/bin/pytest tests/unit/ -q --timeout=30`
Expected: All PASS

**Step 3: Commit**

```bash
git add src/api/routes/auth.py tests/unit/test_auth.py
git commit -m "feat: shared password login returns legacy claims, refresh propagates UserClaims"
```

---

### Task 9: Update Docs and Final Verification

**Files:**
- Modify: `AGENTS.md`
- Modify: `docs/plans/ideas-backlog.md`
- Modify: `.env.example` (verify already updated in Task 1)

**Step 1: Update AGENTS.md**

- Add `users` and `otp_codes` to Database Schema section
- Add OTP endpoints to API Endpoints table
- Update file map: add `otp.py`, `routes/otp.py`, `test_otp.py`, `test_otp_routes.py`
- Update test count
- Add Multi-User Auth milestone section
- Update Development History table

**Step 2: Update ideas-backlog.md**

Move "Multi-user auth" from backlog to "In Progress" or "Done".

**Step 3: Run full test suite**

Run: `.venv/bin/pytest tests/unit/ -q --timeout=30`
Expected: All PASS

**Step 4: Run lint**

Run: `.venv/bin/ruff check . && .venv/bin/ruff format --check .`
Expected: All checks passed

**Step 5: Commit**

```bash
git add AGENTS.md docs/plans/ideas-backlog.md
git commit -m "docs: update AGENTS.md and backlog for multi-user auth milestone"
```

---

## Task Summary

| Task | Description | Key Files |
|------|-------------|-----------|
| 1 | Auth config settings | `config.py`, `.env.example` |
| 2 | Alembic migration + ORM models | `models.py`, `005_users_and_otp.py` |
| 3 | OTP service (generate, send, verify) | `otp.py` |
| 4 | Auth refactor (UserClaims, require_admin) | `auth.py`, all route files |
| 5 | OTP auth endpoints | `routes/otp.py`, `schemas.py` |
| 6 | OTP cleanup scheduler job | `scheduler.py` |
| 7 | Frontend Login (email OTP flow) | `Login.tsx`, `use-auth.tsx` |
| 8 | Shared password backward compatibility | `routes/auth.py` |
| 9 | Docs update + final verification | `AGENTS.md`, backlog |

**Dependencies:** Task 1 → Task 2 → Task 3 → Task 4 → Task 5 → Task 6. Task 7 is independent of 6. Task 8 depends on 4. Task 9 is last.
