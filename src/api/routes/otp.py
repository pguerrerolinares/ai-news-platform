"""OTP authentication endpoints."""

import hmac
import uuid as uuid_mod
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, Request
from slowapi import Limiter
from src.api.ratelimit import get_client_ip
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
limiter = Limiter(key_func=get_client_ip)


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
        user_result = await session.execute(select(User).where(User.email == email))
        user = user_result.scalar_one_or_none()

        if user is None:
            # New user — determine role
            admin_email = settings.admin_email.lower().strip() if settings.admin_email else ""
            role = "admin" if email == admin_email else "reader"
            name = email.split("@")[0]
            user = User(email=email, name=name, role=role)
            session.add(user)
        else:
            user.last_login_at = datetime.now(tz=UTC)
            # Promote to admin if ADMIN_EMAIL matches
            admin_email = settings.admin_email.lower().strip() if settings.admin_email else ""
            if email == admin_email and user.role != "admin":
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
        subject=str(user.id),
        role=user.role,
        email=user.email,
    )
    refresh_token = create_refresh_token(
        subject=str(user.id),
        role=user.role,
        email=user.email,
    )

    return TokenResponseV2(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=settings.jwt_access_expire_minutes * 60,
    )


@router.get("/me", response_model=UserResponse, responses={401: {"model": ErrorWrapper}})
async def get_me(user: UserClaims = Depends(require_auth)) -> UserResponse:
    """Return current authenticated user info."""
    async with get_async_session() as session:
        result = await session.execute(select(User).where(User.email == user.email))
        db_user = result.scalar_one_or_none()

    if db_user is None:
        # Legacy token — no user in DB, return synthetic response
        try:
            user_id = uuid_mod.UUID(user.sub)
        except ValueError:
            user_id = uuid_mod.uuid4()

        return UserResponse(
            id=user_id,
            email=user.email or "legacy",
            name=user.email.split("@")[0] if user.email else "user",
            role=user.role,
        )

    return UserResponse.model_validate(db_user)
