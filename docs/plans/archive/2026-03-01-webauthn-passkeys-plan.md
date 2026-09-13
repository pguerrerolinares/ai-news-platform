# WebAuthn Passkeys Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add WebAuthn/passkey biometric authentication alongside existing OTP login.

**Architecture:** New `WebAuthnCredential` DB model, 6 new API endpoints in `src/api/routes/webauthn.py` using `py_webauthn`, frontend passkey login button + Settings page for credential management.

**Tech Stack:** py_webauthn (backend), @simplewebauthn/browser (frontend), Alembic migration, FastAPI routes, React + Shadcn UI.

---

### Task 1: Add py_webauthn dependency

**Files:**
- Modify: `pyproject.toml:35` (add to Auth section of dependencies)

**Step 1: Add dependency to pyproject.toml**

In `pyproject.toml`, add `py_webauthn` to the `dependencies` list under the Auth comment:

```toml
    # Auth
    "python-jose[cryptography]~=3.3.0",
    "passlib[bcrypt]~=1.7.0",
    "py_webauthn~=2.5.0",
```

**Step 2: Install the dependency**

Run: `pip install -e ".[dev]"`
Expected: Successful install, py_webauthn and its dependencies (cbor2, cryptography) installed.

**Step 3: Commit**

```bash
git add pyproject.toml
git commit -m "feat: add py_webauthn dependency for passkey authentication"
```

---

### Task 2: Add WebAuthn config settings

**Files:**
- Modify: `src/core/config.py:127` (after OTP settings)

**Step 1: Write the failing test**

Create `tests/unit/test_webauthn_config.py`:

```python
"""Tests for WebAuthn configuration settings."""

from __future__ import annotations

from src.core.config import Settings


class TestWebAuthnConfig:
    def test_default_rp_id(self):
        s = Settings(
            jwt_secret="x",
            shared_password="x",
            database_url="postgresql+asyncpg://x:x@localhost/x",
            database_url_sync="postgresql://x:x@localhost/x",
        )
        assert s.webauthn_rp_id == "localhost"

    def test_default_rp_name(self):
        s = Settings(
            jwt_secret="x",
            shared_password="x",
            database_url="postgresql+asyncpg://x:x@localhost/x",
            database_url_sync="postgresql://x:x@localhost/x",
        )
        assert s.webauthn_rp_name == "AI News"

    def test_default_origin(self):
        s = Settings(
            jwt_secret="x",
            shared_password="x",
            database_url="postgresql+asyncpg://x:x@localhost/x",
            database_url_sync="postgresql://x:x@localhost/x",
        )
        assert s.webauthn_origin == "http://localhost:5173"

    def test_custom_values(self):
        s = Settings(
            jwt_secret="x",
            shared_password="x",
            database_url="postgresql+asyncpg://x:x@localhost/x",
            database_url_sync="postgresql://x:x@localhost/x",
            webauthn_rp_id="pguerrero.me",
            webauthn_rp_name="My App",
            webauthn_origin="https://pguerrero.me",
        )
        assert s.webauthn_rp_id == "pguerrero.me"
        assert s.webauthn_rp_name == "My App"
        assert s.webauthn_origin == "https://pguerrero.me"
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_webauthn_config.py -v`
Expected: FAIL — `webauthn_rp_id` attribute not found.

**Step 3: Add settings to config.py**

In `src/core/config.py`, after the OTP settings block (after `otp_expire_minutes`), add:

```python
    # --- WebAuthn (Passkeys) ---
    webauthn_rp_id: str = "localhost"
    webauthn_rp_name: str = "AI News"
    webauthn_origin: str = "http://localhost:5173"
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_webauthn_config.py -v`
Expected: All 4 PASS.

**Step 5: Commit**

```bash
git add src/core/config.py tests/unit/test_webauthn_config.py
git commit -m "feat: add WebAuthn configuration settings"
```

---

### Task 3: Add WebAuthnCredential model

**Files:**
- Modify: `src/core/models.py` (add new model after `OtpCode`)

**Step 1: Write the failing test**

Create `tests/unit/test_webauthn_model.py`:

```python
"""Tests for WebAuthnCredential model."""

from __future__ import annotations

from src.core.models import WebAuthnCredential


class TestWebAuthnCredentialModel:
    def test_tablename(self):
        assert WebAuthnCredential.__tablename__ == "webauthn_credentials"

    def test_has_required_columns(self):
        col_names = {c.name for c in WebAuthnCredential.__table__.columns}
        expected = {
            "id", "user_id", "credential_id", "public_key",
            "sign_count", "device_name", "transports", "backed_up",
            "last_used_at", "created_at",
        }
        assert expected.issubset(col_names)

    def test_credential_id_is_unique(self):
        col = WebAuthnCredential.__table__.c.credential_id
        assert col.unique is True

    def test_user_id_foreign_key(self):
        col = WebAuthnCredential.__table__.c.user_id
        fk = list(col.foreign_keys)
        assert len(fk) == 1
        assert "users.id" in str(fk[0].target_fullname)
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_webauthn_model.py -v`
Expected: FAIL — ImportError for `WebAuthnCredential`.

**Step 3: Add the model to models.py**

In `src/core/models.py`, after the `OtpCode` class, add:

```python
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
    transports: Mapped[dict | None] = mapped_column(JSONB)
    backed_up: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    __table_args__ = (
        Index("idx_webauthn_user_id", "user_id"),
    )
```

Note: `LargeBinary` should be imported from sqlalchemy for `credential_id` and `public_key`, OR use the default `LargeBinary` type. Check: SQLAlchemy maps `Mapped[bytes]` to `LargeBinary` by default, so no extra import needed.

**Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_webauthn_model.py -v`
Expected: All 4 PASS.

**Step 5: Commit**

```bash
git add src/core/models.py tests/unit/test_webauthn_model.py
git commit -m "feat: add WebAuthnCredential model"
```

---

### Task 4: Create Alembic migration

**Files:**
- Create: `alembic/versions/009_webauthn_credentials.py`

**Step 1: Write the migration**

Create `alembic/versions/009_webauthn_credentials.py`:

```python
"""Add webauthn_credentials table for passkey auth.

Revision ID: 009
Revises: 008
Create Date: 2026-03-01
"""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

from alembic import op

revision = "009"
down_revision = "008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "webauthn_credentials",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("credential_id", sa.LargeBinary(), nullable=False, unique=True),
        sa.Column("public_key", sa.LargeBinary(), nullable=False),
        sa.Column("sign_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("device_name", sa.Text(), nullable=False),
        sa.Column("transports", JSONB(), nullable=True),
        sa.Column("backed_up", sa.Boolean(), server_default=sa.text("false")),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
    )
    op.create_index("idx_webauthn_user_id", "webauthn_credentials", ["user_id"])


def downgrade() -> None:
    op.drop_table("webauthn_credentials")
```

**Step 2: Verify migration is valid**

Run: `python -c "from alembic.versions import *; print('import ok')"`
This just checks syntax. Full migration test requires a DB.

**Step 3: Commit**

```bash
git add alembic/versions/009_webauthn_credentials.py
git commit -m "feat: add migration for webauthn_credentials table"
```

---

### Task 5: Add WebAuthn Pydantic schemas

**Files:**
- Modify: `src/api/schemas.py` (add at the end)

**Step 1: Write the failing test**

Create `tests/unit/test_webauthn_schemas.py`:

```python
"""Tests for WebAuthn request/response schemas."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from src.api.schemas import (
    WebAuthnCredentialResponse,
    WebAuthnLoginOptionsRequest,
    WebAuthnRegisterVerifyRequest,
)


class TestWebAuthnLoginOptionsRequest:
    def test_valid_email(self):
        req = WebAuthnLoginOptionsRequest(email="user@example.com")
        assert req.email == "user@example.com"

    def test_invalid_email_rejected(self):
        with pytest.raises(ValidationError):
            WebAuthnLoginOptionsRequest(email="not-an-email")


class TestWebAuthnRegisterVerifyRequest:
    def test_requires_device_name_and_credential(self):
        req = WebAuthnRegisterVerifyRequest(
            device_name="My Phone",
            credential={"id": "abc", "response": {}},
        )
        assert req.device_name == "My Phone"

    def test_device_name_min_length(self):
        with pytest.raises(ValidationError):
            WebAuthnRegisterVerifyRequest(device_name="", credential={})


class TestWebAuthnCredentialResponse:
    def test_from_attributes(self):
        resp = WebAuthnCredentialResponse(
            id=uuid.uuid4(),
            device_name="Laptop",
            backed_up=False,
            created_at=datetime.now(tz=UTC),
            last_used_at=None,
        )
        assert resp.device_name == "Laptop"
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_webauthn_schemas.py -v`
Expected: FAIL — ImportError.

**Step 3: Add schemas to schemas.py**

At the end of `src/api/schemas.py`, add:

```python
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
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_webauthn_schemas.py -v`
Expected: All PASS.

**Step 5: Commit**

```bash
git add src/api/schemas.py tests/unit/test_webauthn_schemas.py
git commit -m "feat: add WebAuthn Pydantic schemas"
```

---

### Task 6: Implement WebAuthn challenge store

**Files:**
- Create: `src/api/webauthn.py`

**Step 1: Write the failing test**

Create `tests/unit/test_webauthn_challenges.py`:

```python
"""Tests for WebAuthn challenge store."""

from __future__ import annotations

import time

from src.api.webauthn import clear_challenge, get_challenge, store_challenge


class TestChallengeStore:
    def test_store_and_retrieve(self):
        challenge = b"test-challenge-bytes"
        store_challenge("user@test.com", challenge, ttl_seconds=300)
        result = get_challenge("user@test.com")
        assert result == challenge

    def test_retrieve_consumes_challenge(self):
        store_challenge("user2@test.com", b"challenge", ttl_seconds=300)
        get_challenge("user2@test.com")
        assert get_challenge("user2@test.com") is None

    def test_expired_challenge_returns_none(self):
        store_challenge("user3@test.com", b"old", ttl_seconds=0)
        time.sleep(0.01)
        assert get_challenge("user3@test.com") is None

    def test_clear_challenge(self):
        store_challenge("user4@test.com", b"data", ttl_seconds=300)
        clear_challenge("user4@test.com")
        assert get_challenge("user4@test.com") is None

    def test_missing_key_returns_none(self):
        assert get_challenge("nonexistent@test.com") is None
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_webauthn_challenges.py -v`
Expected: FAIL — ImportError.

**Step 3: Implement challenge store**

Create `src/api/webauthn.py`:

```python
"""WebAuthn challenge store and helpers."""

from __future__ import annotations

import time

# In-memory challenge store: key -> (challenge_bytes, expiry_timestamp)
_challenges: dict[str, tuple[bytes, float]] = {}
_MAX_CHALLENGES = 200


def _prune_expired() -> None:
    now = time.time()
    expired = [k for k, (_, exp) in _challenges.items() if exp < now]
    for k in expired:
        del _challenges[k]


def store_challenge(key: str, challenge: bytes, *, ttl_seconds: int = 300) -> None:
    """Store a challenge with expiry. Prunes old entries."""
    _prune_expired()
    if len(_challenges) >= _MAX_CHALLENGES:
        oldest = min(_challenges, key=lambda k: _challenges[k][1])
        del _challenges[oldest]
    _challenges[key] = (challenge, time.time() + ttl_seconds)


def get_challenge(key: str) -> bytes | None:
    """Retrieve and consume a challenge. Returns None if missing/expired."""
    _prune_expired()
    entry = _challenges.pop(key, None)
    if entry is None:
        return None
    challenge, expiry = entry
    if time.time() > expiry:
        return None
    return challenge


def clear_challenge(key: str) -> None:
    """Remove a challenge without returning it."""
    _challenges.pop(key, None)
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_webauthn_challenges.py -v`
Expected: All 5 PASS.

**Step 5: Commit**

```bash
git add src/api/webauthn.py tests/unit/test_webauthn_challenges.py
git commit -m "feat: add WebAuthn in-memory challenge store"
```

---

### Task 7: Implement WebAuthn registration endpoints

**Files:**
- Create: `src/api/routes/webauthn.py`
- Modify: `src/api/app.py` (register router)

**IMPORTANT:** Do NOT use `from __future__ import annotations` in route files that use `@limiter.limit()` decorators — it breaks FastAPI's type resolution with slowapi.

**Step 1: Write the failing test**

Create `tests/unit/test_webauthn_routes.py`:

```python
"""Tests for WebAuthn route endpoints."""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from src.api.app import app
from src.core.config import Settings


TEST_SECRET = "test-jwt-secret-key"
TEST_PASSWORD = "test-password-123"


def _make_test_settings(**overrides) -> Settings:
    defaults = {
        "jwt_secret": TEST_SECRET,
        "jwt_algorithm": "HS256",
        "jwt_access_expire_minutes": 30,
        "jwt_refresh_expire_days": 7,
        "shared_password": TEST_PASSWORD,
        "database_url": "postgresql+asyncpg://x:x@localhost/x",
        "database_url_sync": "postgresql://x:x@localhost/x",
        "telegram_bot_token": "",
        "telegram_chat_id": "",
        "telegram_alerts_enabled": False,
        "webauthn_rp_id": "localhost",
        "webauthn_rp_name": "AI News",
        "webauthn_origin": "http://localhost:5173",
    }
    defaults.update(overrides)
    return Settings(**defaults)


@pytest.fixture(autouse=True)
def _override_settings():
    test_settings = _make_test_settings()
    from src.api.routes.webauthn import limiter

    original_enabled = limiter.enabled
    limiter.enabled = False
    with patch("src.api.routes.webauthn.get_settings", return_value=test_settings):
        yield
    limiter.enabled = original_enabled


@pytest.fixture()
async def api_client() -> AsyncClient:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac  # type: ignore[misc]


def _auth_header() -> dict[str, str]:
    from src.api.auth import create_access_token

    test_settings = _make_test_settings()
    with patch("src.api.auth.get_settings", return_value=test_settings):
        token = create_access_token(
            subject=str(uuid.uuid4()),
            role="reader",
            email="test@example.com",
        )
    return {"Authorization": f"Bearer {token}"}


class TestRegisterOptions:
    async def test_unauthenticated_returns_403(self, api_client: AsyncClient):
        resp = await api_client.post("/api/auth/webauthn/register/options")
        assert resp.status_code == 403

    async def test_authenticated_returns_200(self, api_client: AsyncClient):
        test_settings = _make_test_settings()
        with patch("src.api.auth.get_settings", return_value=test_settings):
            mock_session = AsyncMock()
            mock_result = MagicMock()
            mock_result.scalars.return_value.all.return_value = []
            mock_session.execute = AsyncMock(return_value=mock_result)

            with patch(
                "src.api.routes.webauthn.get_async_session"
            ) as mock_get_session:
                mock_get_session.return_value.__aenter__ = AsyncMock(
                    return_value=mock_session
                )
                mock_get_session.return_value.__aexit__ = AsyncMock(return_value=False)
                resp = await api_client.post(
                    "/api/auth/webauthn/register/options",
                    headers=_auth_header(),
                )
            assert resp.status_code == 200
            data = resp.json()
            assert "challenge" in data or "publicKey" in data


class TestLoginOptions:
    async def test_missing_email_returns_422(self, api_client: AsyncClient):
        resp = await api_client.post(
            "/api/auth/webauthn/login/options", json={}
        )
        assert resp.status_code == 422

    async def test_no_credentials_returns_404(self, api_client: AsyncClient):
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)

        with patch(
            "src.api.routes.webauthn.get_async_session"
        ) as mock_get_session:
            mock_get_session.return_value.__aenter__ = AsyncMock(
                return_value=mock_session
            )
            mock_get_session.return_value.__aexit__ = AsyncMock(return_value=False)
            resp = await api_client.post(
                "/api/auth/webauthn/login/options",
                json={"email": "nobody@test.com"},
            )
        assert resp.status_code == 404


class TestCredentialsList:
    async def test_unauthenticated_returns_403(self, api_client: AsyncClient):
        resp = await api_client.get("/api/auth/webauthn/credentials")
        assert resp.status_code == 403
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_webauthn_routes.py -v`
Expected: FAIL — ImportError.

**Step 3: Implement the route file**

Create `src/api/routes/webauthn.py`:

```python
"""WebAuthn (passkey) authentication endpoints."""

import uuid as uuid_mod
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Request
from slowapi import Limiter
from sqlalchemy import delete, select
from webauthn import (
    generate_authentication_options,
    generate_registration_options,
    verify_authentication_response,
    verify_registration_response,
)
from webauthn.helpers import bytes_to_base64url, parse_authentication_credential_json
from webauthn.helpers import parse_registration_credential_json
from webauthn.helpers.structs import (
    AuthenticatorSelectionCriteria,
    PublicKeyCredentialDescriptor,
    ResidentKeyRequirement,
    UserVerificationRequirement,
)

from src.api.auth import (
    UserClaims,
    create_access_token,
    create_refresh_token,
    require_auth,
)
from src.api.errors import APIError
from src.api.ratelimit import get_client_ip
from src.api.schemas import (
    ErrorWrapper,
    TokenResponseV2,
    WebAuthnCredentialResponse,
    WebAuthnLoginOptionsRequest,
    WebAuthnLoginVerifyRequest,
    WebAuthnRegisterVerifyRequest,
)
from src.api.webauthn import clear_challenge, get_challenge, store_challenge
from src.core.config import get_settings
from src.core.database import get_async_session
from src.core.logging import get_logger
from src.core.models import User, WebAuthnCredential

logger = get_logger(__name__)
router = APIRouter(prefix="/api/auth/webauthn", tags=["webauthn"])
limiter = Limiter(key_func=get_client_ip)

CHALLENGE_TTL = 300  # 5 minutes


# --- Registration (authenticated) ---


@router.post("/register/options")
@limiter.limit("3/minute")
async def register_options(
    request: Request,
    user: UserClaims = Depends(require_auth),
):
    """Generate registration options for a new passkey."""
    settings = get_settings()

    # Get existing credentials to exclude
    async with get_async_session() as session:
        result = await session.execute(
            select(WebAuthnCredential.credential_id).where(
                WebAuthnCredential.user_id == uuid_mod.UUID(user.sub)
            )
        )
        existing_creds = result.scalars().all()

    exclude_credentials = [
        PublicKeyCredentialDescriptor(id=cred_id)
        for cred_id in existing_creds
    ]

    options = generate_registration_options(
        rp_id=settings.webauthn_rp_id,
        rp_name=settings.webauthn_rp_name,
        user_id=user.sub.encode(),
        user_name=user.email or user.sub,
        user_display_name=user.email or user.sub,
        exclude_credentials=exclude_credentials,
        authenticator_selection=AuthenticatorSelectionCriteria(
            resident_key=ResidentKeyRequirement.PREFERRED,
            user_verification=UserVerificationRequirement.PREFERRED,
        ),
    )

    # Store challenge for verification
    store_challenge(
        f"reg:{user.sub}",
        options.challenge,
        ttl_seconds=CHALLENGE_TTL,
    )

    return options


@router.post("/register/verify")
@limiter.limit("3/minute")
async def register_verify(
    request: Request,
    body: WebAuthnRegisterVerifyRequest,
    user: UserClaims = Depends(require_auth),
):
    """Verify registration and store the new passkey."""
    settings = get_settings()

    challenge = get_challenge(f"reg:{user.sub}")
    if challenge is None:
        raise APIError(400, "CHALLENGE_EXPIRED", "Registration challenge expired or not found")

    try:
        credential = parse_registration_credential_json(body.credential)
        verification = verify_registration_response(
            credential=credential,
            expected_challenge=challenge,
            expected_rp_id=settings.webauthn_rp_id,
            expected_origin=settings.webauthn_origin,
        )
    except Exception as exc:
        logger.warning("webauthn_register_failed", error=str(exc), user=user.sub)
        raise APIError(400, "REGISTRATION_FAILED", "Passkey registration failed") from None

    async with get_async_session() as session:
        session.add(
            WebAuthnCredential(
                user_id=uuid_mod.UUID(user.sub),
                credential_id=verification.credential_id,
                public_key=verification.credential_public_key,
                sign_count=verification.sign_count,
                device_name=body.device_name,
                transports=(
                    [str(t) for t in credential.response.transports]
                    if credential.response.transports
                    else None
                ),
                backed_up=verification.credential_backed_up,
            )
        )
        await session.commit()

    logger.info("webauthn_registered", user=user.sub, device=body.device_name)
    return {"status": "ok", "device_name": body.device_name}


# --- Login (unauthenticated) ---


@router.post(
    "/login/options",
    responses={404: {"model": ErrorWrapper}},
)
@limiter.limit("5/minute")
async def login_options(
    request: Request,
    body: WebAuthnLoginOptionsRequest,
):
    """Generate authentication options for passkey login."""
    settings = get_settings()
    email = body.email.lower().strip()

    async with get_async_session() as session:
        # Find user
        user_result = await session.execute(
            select(User).where(User.email == email)
        )
        user = user_result.scalar_one_or_none()
        if user is None:
            raise APIError(404, "USER_NOT_FOUND", "No account found for this email")

        # Get user's credentials
        cred_result = await session.execute(
            select(WebAuthnCredential).where(
                WebAuthnCredential.user_id == user.id
            )
        )
        credentials = cred_result.scalars().all()

    if not credentials:
        raise APIError(404, "NO_PASSKEYS", "No passkeys registered for this account")

    allow_credentials = [
        PublicKeyCredentialDescriptor(
            id=cred.credential_id,
            transports=cred.transports if cred.transports else None,
        )
        for cred in credentials
    ]

    options = generate_authentication_options(
        rp_id=settings.webauthn_rp_id,
        allow_credentials=allow_credentials,
        user_verification=UserVerificationRequirement.PREFERRED,
    )

    store_challenge(
        f"login:{email}",
        options.challenge,
        ttl_seconds=CHALLENGE_TTL,
    )

    return options


@router.post(
    "/login/verify",
    response_model=TokenResponseV2,
    responses={401: {"model": ErrorWrapper}},
)
@limiter.limit("5/minute")
async def login_verify(
    request: Request,
    body: WebAuthnLoginVerifyRequest,
):
    """Verify passkey assertion and return JWT tokens."""
    settings = get_settings()
    email = body.email.lower().strip()

    challenge = get_challenge(f"login:{email}")
    if challenge is None:
        raise APIError(400, "CHALLENGE_EXPIRED", "Login challenge expired or not found")

    # Look up user and credential
    async with get_async_session() as session:
        user_result = await session.execute(
            select(User).where(User.email == email)
        )
        user = user_result.scalar_one_or_none()
        if user is None:
            raise APIError(401, "AUTH_FAILED", "Authentication failed")

        try:
            credential = parse_authentication_credential_json(body.credential)
        except Exception:
            raise APIError(401, "AUTH_FAILED", "Invalid credential format") from None

        cred_result = await session.execute(
            select(WebAuthnCredential).where(
                WebAuthnCredential.credential_id == credential.raw_id,
                WebAuthnCredential.user_id == user.id,
            )
        )
        stored_cred = cred_result.scalar_one_or_none()

        if stored_cred is None:
            raise APIError(401, "AUTH_FAILED", "Authentication failed")

        try:
            verification = verify_authentication_response(
                credential=credential,
                expected_challenge=challenge,
                expected_rp_id=settings.webauthn_rp_id,
                expected_origin=settings.webauthn_origin,
                credential_public_key=stored_cred.public_key,
                credential_current_sign_count=stored_cred.sign_count,
            )
        except Exception as exc:
            logger.warning("webauthn_login_failed", error=str(exc), email=email)
            raise APIError(401, "AUTH_FAILED", "Authentication failed") from None

        # Update sign count and last_used_at
        stored_cred.sign_count = verification.new_sign_count
        stored_cred.last_used_at = datetime.now(tz=UTC)
        user.last_login_at = datetime.now(tz=UTC)
        await session.commit()

    access_token = create_access_token(
        subject=str(user.id), role=user.role, email=user.email
    )
    refresh_token = create_refresh_token(
        subject=str(user.id), role=user.role, email=user.email
    )

    return TokenResponseV2(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=settings.jwt_access_expire_minutes * 60,
    )


# --- Credential management (authenticated) ---


@router.get("/credentials", response_model=list[WebAuthnCredentialResponse])
@limiter.limit("10/minute")
async def list_credentials(
    request: Request,
    user: UserClaims = Depends(require_auth),
):
    """List the current user's registered passkeys."""
    async with get_async_session() as session:
        result = await session.execute(
            select(WebAuthnCredential)
            .where(WebAuthnCredential.user_id == uuid_mod.UUID(user.sub))
            .order_by(WebAuthnCredential.created_at.desc())
        )
        credentials = result.scalars().all()

    return [WebAuthnCredentialResponse.model_validate(c) for c in credentials]


@router.delete(
    "/credentials/{credential_id}",
    responses={404: {"model": ErrorWrapper}},
)
@limiter.limit("3/minute")
async def delete_credential(
    request: Request,
    credential_id: uuid_mod.UUID,
    user: UserClaims = Depends(require_auth),
):
    """Delete a registered passkey."""
    async with get_async_session() as session:
        result = await session.execute(
            delete(WebAuthnCredential).where(
                WebAuthnCredential.id == credential_id,
                WebAuthnCredential.user_id == uuid_mod.UUID(user.sub),
            )
        )
        await session.commit()

    if result.rowcount == 0:  # type: ignore[union-attr]
        raise APIError(404, "NOT_FOUND", "Credential not found")

    return {"status": "ok"}
```

**Step 4: Register the router in app.py**

In `src/api/app.py`, add the import:

```python
from src.api.routes.webauthn import router as webauthn_router
```

Add to the router registrations (after `otp_router`):

```python
app.include_router(webauthn_router)
```

Also update the CORS `allow_methods` to include DELETE:

```python
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
```

**Step 5: Run tests to verify**

Run: `pytest tests/unit/test_webauthn_routes.py -v`
Expected: All tests PASS.

**Step 6: Run full test suite**

Run: `pytest tests/unit/ -x --timeout=30`
Expected: All existing tests still pass.

**Step 7: Commit**

```bash
git add src/api/routes/webauthn.py src/api/app.py tests/unit/test_webauthn_routes.py
git commit -m "feat: add WebAuthn registration, login, and credential management endpoints"
```

---

### Task 8: Add @simplewebauthn/browser frontend dependency

**Files:**
- Modify: `frontend/package.json`

**Step 1: Install the dependency**

Run: `cd frontend && npm install @simplewebauthn/browser`

**Step 2: Verify install succeeded**

Run: `cd frontend && npm ls @simplewebauthn/browser`
Expected: Shows the installed version.

**Step 3: Commit**

```bash
git add frontend/package.json frontend/package-lock.json
git commit -m "feat: add @simplewebauthn/browser for passkey support"
```

---

### Task 9: Create frontend WebAuthn helper module

**Files:**
- Create: `frontend/src/lib/webauthn.ts`

**Step 1: Create the module**

Create `frontend/src/lib/webauthn.ts`:

```typescript
import { startRegistration, startAuthentication } from '@simplewebauthn/browser'
import type {
  PublicKeyCredentialCreationOptionsJSON,
  PublicKeyCredentialRequestOptionsJSON,
} from '@simplewebauthn/browser'
import { apiPost, apiGet } from './api'
import type { AuthTokens } from './auth'

export interface WebAuthnCredential {
  id: string
  device_name: string
  backed_up: boolean
  created_at: string
  last_used_at: string | null
}

export async function registerPasskey(deviceName: string): Promise<void> {
  // 1. Get registration options from server
  const { data: options } = await apiGet<PublicKeyCredentialCreationOptionsJSON>(
    '/api/auth/webauthn/register/options',
    undefined,
    undefined,
  )

  // Workaround: apiGet returns { data, totalCount } but register/options is POST
  const optionsData = await apiPost<PublicKeyCredentialCreationOptionsJSON>(
    '/api/auth/webauthn/register/options',
    {},
  )

  // 2. Create credential via browser API (triggers biometric prompt)
  const credential = await startRegistration({ optionsJSON: optionsData })

  // 3. Send to server for verification
  await apiPost('/api/auth/webauthn/register/verify', {
    device_name: deviceName,
    credential,
  })
}

export async function loginWithPasskey(email: string): Promise<AuthTokens> {
  // 1. Get authentication options from server
  const options = await apiPost<PublicKeyCredentialRequestOptionsJSON>(
    '/api/auth/webauthn/login/options',
    { email },
  )

  // 2. Get assertion via browser API (triggers biometric prompt)
  const credential = await startAuthentication({ optionsJSON: options })

  // 3. Verify with server, get tokens
  return apiPost<AuthTokens>('/api/auth/webauthn/login/verify', {
    email,
    credential,
  })
}

export async function listPasskeys(): Promise<WebAuthnCredential[]> {
  const { data } = await apiGet<WebAuthnCredential[]>('/api/auth/webauthn/credentials')
  return data
}

export async function deletePasskey(id: string): Promise<void> {
  const BASE_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'
  const token = localStorage.getItem('auth_access_token')
  const res = await fetch(`${BASE_URL}/api/auth/webauthn/credentials/${id}`, {
    method: 'DELETE',
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
  })
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new Error(body.error?.message ?? `Error ${res.status}`)
  }
}
```

**Step 2: Verify TypeScript compiles**

Run: `cd frontend && npx tsc --noEmit`
Expected: No errors (or only pre-existing ones).

**Step 3: Commit**

```bash
git add frontend/src/lib/webauthn.ts
git commit -m "feat: add WebAuthn browser helper module"
```

---

### Task 10: Update auth hook with passkey login

**Files:**
- Modify: `frontend/src/hooks/use-auth.tsx`

**Step 1: Add loginWithPasskey to the auth context**

In `frontend/src/hooks/use-auth.tsx`:

1. Add import: `import { loginWithPasskey as webauthnLogin } from '@/lib/webauthn'`

2. Add to `AuthContextValue` interface:
```typescript
loginPasskey: (email: string) => Promise<void>
```

3. Add the callback in `AuthProvider`:
```typescript
const loginPasskey = useCallback(async (email: string) => {
  const tokens = await webauthnLogin(email)
  storeTokens(tokens)
  setIsAuthenticated(true)
}, [])
```

4. Add `loginPasskey` to the context value:
```typescript
<AuthContext value={{ isAuthenticated, requestOtp, verifyOtp, loginLegacy, loginPasskey, logout }}>
```

**Step 2: Verify it compiles**

Run: `cd frontend && npx tsc --noEmit`

**Step 3: Commit**

```bash
git add frontend/src/hooks/use-auth.tsx
git commit -m "feat: add passkey login to auth context"
```

---

### Task 11: Update Login page with passkey button

**Files:**
- Modify: `frontend/src/pages/Login.tsx`
- Modify: `frontend/src/locales/en.json`

**Step 1: Add i18n keys**

In `frontend/src/locales/en.json`, add to the `"login"` section:

```json
"passkeyLogin": "Sign in with Passkey",
"passkeyLoading": "Authenticating...",
"passkeyError": "Passkey authentication failed"
```

**Step 2: Update Login.tsx**

In `frontend/src/pages/Login.tsx`:

1. Add `loginPasskey` to the destructured auth hook:
```typescript
const { requestOtp, verifyOtp, loginLegacy, loginPasskey } = useAuth()
```

2. Add the passkey handler function after `handleLegacyLogin`:
```typescript
async function handlePasskeyLogin() {
  if (!email.trim()) return
  setError('')
  setLoading(true)
  try {
    await loginPasskey(email)
    navigate(from, { replace: true })
  } catch (err) {
    setError(err instanceof Error ? err.message : t('login.passkeyError'))
  } finally {
    setLoading(false)
  }
}
```

3. In the `step === 'email'` form, add a passkey button between the "Send code" button and the "Password access" link:
```tsx
<Button
  type="button"
  variant="outline"
  className="w-full"
  disabled={loading || !email.trim()}
  onClick={handlePasskeyLogin}
>
  {loading ? t('login.passkeyLoading') : t('login.passkeyLogin')}
</Button>
```

**Step 3: Verify it compiles and builds**

Run: `cd frontend && npm run build`

**Step 4: Commit**

```bash
git add frontend/src/pages/Login.tsx frontend/src/locales/en.json
git commit -m "feat: add passkey login button to Login page"
```

---

### Task 12: Create Settings page with passkey management

**Files:**
- Create: `frontend/src/pages/Settings.tsx`
- Modify: `frontend/src/App.tsx` (add route)
- Modify: `frontend/src/components/app-nav.tsx` (add Settings link)
- Modify: `frontend/src/locales/en.json` (add translations)

**Step 1: Add i18n keys**

In `frontend/src/locales/en.json`, add a `"settings"` section:

```json
"settings": {
  "title": "Settings",
  "security": "Security",
  "passkeys": "Passkeys",
  "passkeysDescription": "Use fingerprint or Face ID to sign in without a code",
  "noPasskeys": "No passkeys registered yet",
  "registerPasskey": "Register new passkey",
  "deviceName": "Device name",
  "deviceNamePlaceholder": "e.g. My iPhone",
  "registering": "Registering...",
  "register": "Register",
  "cancel": "Cancel",
  "deleteConfirm": "Remove this passkey?",
  "delete": "Remove",
  "lastUsed": "Last used",
  "never": "Never",
  "registered": "Registered",
  "backedUp": "Synced"
}
```

**Step 2: Create Settings.tsx**

Create `frontend/src/pages/Settings.tsx`:

```tsx
import { useState, useEffect } from 'react'
import { useTranslation } from 'react-i18next'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { listPasskeys, registerPasskey, deletePasskey } from '@/lib/webauthn'
import type { WebAuthnCredential } from '@/lib/webauthn'

export default function Settings() {
  const { t } = useTranslation()
  const [passkeys, setPasskeys] = useState<WebAuthnCredential[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [showRegister, setShowRegister] = useState(false)
  const [deviceName, setDeviceName] = useState('')
  const [registering, setRegistering] = useState(false)

  async function loadPasskeys() {
    try {
      const keys = await listPasskeys()
      setPasskeys(keys)
    } catch {
      setError('Failed to load passkeys')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { loadPasskeys() }, [])

  async function handleRegister(e: React.FormEvent) {
    e.preventDefault()
    if (!deviceName.trim()) return
    setRegistering(true)
    setError('')
    try {
      await registerPasskey(deviceName.trim())
      setDeviceName('')
      setShowRegister(false)
      await loadPasskeys()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Registration failed')
    } finally {
      setRegistering(false)
    }
  }

  async function handleDelete(id: string) {
    if (!confirm(t('settings.deleteConfirm'))) return
    try {
      await deletePasskey(id)
      setPasskeys(prev => prev.filter(p => p.id !== id))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Delete failed')
    }
  }

  function formatDate(dateStr: string | null) {
    if (!dateStr) return t('settings.never')
    return new Date(dateStr).toLocaleDateString(undefined, {
      year: 'numeric', month: 'short', day: 'numeric',
    })
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">{t('settings.title')}</h1>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>{t('settings.passkeys')}</CardTitle>
          <CardDescription>{t('settings.passkeysDescription')}</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {error && <p className="text-sm text-destructive">{error}</p>}

          {loading ? (
            <p className="text-sm text-muted-foreground">Loading...</p>
          ) : passkeys.length === 0 ? (
            <p className="text-sm text-muted-foreground">{t('settings.noPasskeys')}</p>
          ) : (
            <div className="space-y-3">
              {passkeys.map(pk => (
                <div
                  key={pk.id}
                  className="flex items-center justify-between rounded-lg border p-3"
                >
                  <div className="space-y-1">
                    <p className="text-sm font-medium">{pk.device_name}</p>
                    <p className="text-xs text-muted-foreground">
                      {t('settings.registered')}: {formatDate(pk.created_at)}
                      {' · '}
                      {t('settings.lastUsed')}: {formatDate(pk.last_used_at)}
                      {pk.backed_up && (
                        <span className="ml-2 text-green-600">
                          {t('settings.backedUp')}
                        </span>
                      )}
                    </p>
                  </div>
                  <Button
                    variant="ghost"
                    size="sm"
                    className="text-destructive hover:text-destructive"
                    onClick={() => handleDelete(pk.id)}
                  >
                    {t('settings.delete')}
                  </Button>
                </div>
              ))}
            </div>
          )}

          {showRegister ? (
            <form onSubmit={handleRegister} className="flex gap-2">
              <Input
                value={deviceName}
                onChange={e => setDeviceName(e.target.value)}
                placeholder={t('settings.deviceNamePlaceholder')}
                disabled={registering}
                autoFocus
              />
              <Button type="submit" disabled={registering || !deviceName.trim()}>
                {registering ? t('settings.registering') : t('settings.register')}
              </Button>
              <Button
                type="button"
                variant="ghost"
                onClick={() => { setShowRegister(false); setDeviceName('') }}
              >
                {t('settings.cancel')}
              </Button>
            </form>
          ) : (
            <Button
              variant="outline"
              onClick={() => setShowRegister(true)}
            >
              {t('settings.registerPasskey')}
            </Button>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
```

**Step 3: Add route in App.tsx**

In `frontend/src/App.tsx`:

1. Add import: `import Settings from '@/pages/Settings'`

2. Add route inside the `RequireAuth` layout group:
```tsx
<Route path="settings" element={<Settings />} />
```

**Step 4: Add Settings link to navbar**

In `frontend/src/components/app-nav.tsx`:

1. Add import: `import { IconSettings } from '@tabler/icons-react'`

2. In both the mobile and desktop nav sections, add a Settings icon button before the logout button:
```tsx
<NavLink to="/settings">
  <Button variant="ghost" size="icon" aria-label="Settings">
    <IconSettings className="size-4" />
  </Button>
</NavLink>
```

**Step 5: Verify it builds**

Run: `cd frontend && npm run build`

**Step 6: Commit**

```bash
git add frontend/src/pages/Settings.tsx frontend/src/App.tsx \
  frontend/src/components/app-nav.tsx frontend/src/locales/en.json
git commit -m "feat: add Settings page with passkey management UI"
```

---

### Task 13: Fix registerPasskey to use POST correctly

**Files:**
- Modify: `frontend/src/lib/webauthn.ts`

**Step 1: Clean up the registerPasskey function**

Remove the duplicate `apiGet` call and keep only the `apiPost`:

```typescript
export async function registerPasskey(deviceName: string): Promise<void> {
  // 1. Get registration options from server (POST, authenticated)
  const options = await apiPost<PublicKeyCredentialCreationOptionsJSON>(
    '/api/auth/webauthn/register/options',
    {},
  )

  // 2. Create credential via browser API (triggers biometric prompt)
  const credential = await startRegistration({ optionsJSON: options })

  // 3. Send to server for verification
  await apiPost('/api/auth/webauthn/register/verify', {
    device_name: deviceName,
    credential,
  })
}
```

**Step 2: Verify it builds**

Run: `cd frontend && npm run build`

**Step 3: Commit**

```bash
git add frontend/src/lib/webauthn.ts
git commit -m "fix: clean up registerPasskey to use POST correctly"
```

---

### Task 14: Run full quality gates

**Step 1: Backend lint and type check**

Run: `ruff check . && ruff format --check . && pyright .`

Fix any issues found.

**Step 2: Backend tests**

Run: `pytest tests/unit/ -x --timeout=30`

Fix any failures.

**Step 3: Frontend build**

Run: `cd frontend && npm run build`

Fix any TypeScript errors.

**Step 4: Commit any fixes**

```bash
git add -A
git commit -m "fix: address lint and type check issues from WebAuthn implementation"
```

---

### Task 15: Update AGENTS.md and design doc

**Files:**
- Modify: `AGENTS.md` (add new files to file map, new endpoints)
- Modify: `docs/plans/2026-03-01-webauthn-passkeys-design.md` (mark as Implemented)

**Step 1: Update AGENTS.md**

Add to the file map:
- `src/api/webauthn.py` — WebAuthn challenge store
- `src/api/routes/webauthn.py` — WebAuthn endpoints (register, login, credential CRUD)
- `frontend/src/lib/webauthn.ts` — WebAuthn browser helpers
- `frontend/src/pages/Settings.tsx` — Settings page with passkey management

Add to API endpoints section:
- `POST /api/auth/webauthn/register/options` — Generate passkey registration options (auth required)
- `POST /api/auth/webauthn/register/verify` — Verify and store new passkey (auth required)
- `POST /api/auth/webauthn/login/options` — Generate passkey login options
- `POST /api/auth/webauthn/login/verify` — Verify passkey login, return JWT
- `GET /api/auth/webauthn/credentials` — List user's passkeys (auth required)
- `DELETE /api/auth/webauthn/credentials/{id}` — Delete a passkey (auth required)

**Step 2: Mark design doc status**

Change `**Status**: Approved` to `**Status**: Implemented` in the design doc.

**Step 3: Commit**

```bash
git add AGENTS.md docs/plans/2026-03-01-webauthn-passkeys-design.md
git commit -m "docs: update AGENTS.md and design doc for WebAuthn passkeys"
```

---

## Production Deployment Notes

After merging, set these env vars in Coolify:

```
WEBAUTHN_RP_ID=pguerrero.me
WEBAUTHN_RP_NAME=AI News
WEBAUTHN_ORIGIN=https://pguerrero.me
```

Run the Alembic migration:

```bash
alembic upgrade head
```
