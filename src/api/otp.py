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
