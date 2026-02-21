"""FastAPI application entry point."""

from __future__ import annotations

import time
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import ClassVar

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from prometheus_client import generate_latest
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from src.api.routes.auth import router as auth_router
from src.api.routes.briefings import router as briefings_router
from src.api.routes.chat import router as chat_router
from src.api.routes.items import router as items_router
from src.api.routes.search import router as search_router
from src.api.routes.topics import router as topics_router
from src.core.config import get_settings
from src.core.database import close_db, get_engine, init_db
from src.core.logging import get_logger, set_correlation_id, setup_logging
from src.core.metrics import api_request_duration_seconds, api_requests_total

logger = get_logger(__name__)

type ASGIApplication = object


class SecurityHeadersMiddleware:
    """ASGI middleware that adds standard security headers to every response."""

    _HEADERS: ClassVar[list[tuple[bytes, bytes]]] = [
        (b"x-content-type-options", b"nosniff"),
        (b"x-frame-options", b"DENY"),
        (b"referrer-policy", b"strict-origin-when-cross-origin"),
        (b"permissions-policy", b"camera=(), microphone=(), geolocation=()"),
        (b"x-xss-protection", b"0"),
    ]

    def __init__(self, app: ASGIApplication) -> None:
        self.app = app

    async def __call__(self, scope: dict, receive: object, send: object) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        is_debug = get_settings().debug

        async def _send_with_headers(message: dict) -> None:
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                headers.extend(self._HEADERS)
                if not is_debug:
                    headers.append(
                        (b"strict-transport-security", b"max-age=31536000; includeSubDomains")
                    )
                message["headers"] = headers
            await send(message)

        await self.app(scope, receive, _send_with_headers)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan: setup and teardown."""
    setup_logging()

    # Block startup with insecure defaults in production
    settings = get_settings()
    if not settings.debug:
        if settings.jwt_secret == "change-me-in-production":
            raise RuntimeError("JWT_SECRET must be set in production (DEBUG=false)")
        if settings.shared_password == "change-me-in-production":
            raise RuntimeError("SHARED_PASSWORD must be set in production (DEBUG=false)")

    logger.info("starting_application")
    await init_db()
    yield
    logger.info("shutting_down_application")
    await close_db()


app = FastAPI(
    title="AI News Platform",
    description="AI News aggregation, classification, and search API",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/api/docs" if get_settings().debug else None,
    redoc_url=None,
)

# Security headers (must wrap CORS so headers appear on preflight too)
app.add_middleware(SecurityHeadersMiddleware)  # type: ignore[arg-type]

# CORS
settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

# Rate limiting
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Register route modules
app.include_router(auth_router)
app.include_router(items_router)
app.include_router(briefings_router)
app.include_router(search_router)
app.include_router(chat_router)
app.include_router(topics_router)


@app.middleware("http")
async def metrics_middleware(request: Request, call_next: object) -> Response:
    """Track request metrics and add correlation ID."""
    cid = set_correlation_id()
    start = time.monotonic()

    response: Response = await call_next(request)  # type: ignore[misc]

    duration = time.monotonic() - start
    endpoint = request.url.path
    method = request.method

    api_requests_total.labels(method=method, endpoint=endpoint, status=response.status_code).inc()
    api_request_duration_seconds.labels(method=method, endpoint=endpoint).observe(duration)

    response.headers["X-Correlation-ID"] = cid
    return response


@app.get("/health")
async def health_check() -> JSONResponse:
    """Health check endpoint. Verifies DB connectivity."""
    engine = get_engine()
    try:
        async with engine.connect() as conn:
            await conn.execute(__import__("sqlalchemy").text("SELECT 1"))
        return JSONResponse(content={"status": "healthy", "database": "connected"})
    except Exception as exc:
        logger.error("health_check_failed", error=str(exc))
        return JSONResponse(
            status_code=503,
            content={"status": "unhealthy", "database": str(exc)},
        )


@app.get("/metrics")
async def metrics() -> Response:
    """Prometheus metrics endpoint."""
    return Response(
        content=generate_latest(),
        media_type="text/plain; version=0.0.4; charset=utf-8",
    )
