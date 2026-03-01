"""WebAuthn (passkey) authentication endpoints."""

import json
import uuid as uuid_mod
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from slowapi import Limiter
from sqlalchemy import delete, select
from webauthn import (
    generate_authentication_options,
    generate_registration_options,
    verify_authentication_response,
    verify_registration_response,
)
from webauthn.helpers import (
    options_to_json,
    parse_authentication_credential_json,
    parse_registration_credential_json,
)
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
from src.api.webauthn import get_challenge, store_challenge
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

    exclude_credentials = [PublicKeyCredentialDescriptor(id=cred_id) for cred_id in existing_creds]

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

    return JSONResponse(content=json.loads(options_to_json(options)))


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
        user_result = await session.execute(select(User).where(User.email == email))
        user = user_result.scalar_one_or_none()
        if user is None:
            raise APIError(404, "USER_NOT_FOUND", "No account found for this email")

        # Get user's credentials
        cred_result = await session.execute(
            select(WebAuthnCredential).where(WebAuthnCredential.user_id == user.id)
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

    return JSONResponse(content=json.loads(options_to_json(options)))


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
        user_result = await session.execute(select(User).where(User.email == email))
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

    access_token = create_access_token(subject=str(user.id), role=user.role, email=user.email)
    refresh_token = create_refresh_token(subject=str(user.id), role=user.role, email=user.email)

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
