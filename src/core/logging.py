"""Structured logging with structlog and correlation IDs."""

from __future__ import annotations

import logging
import uuid
from contextvars import ContextVar
from typing import Any

import structlog

from src.core.config import get_settings

# Correlation ID for tracing requests/pipeline runs across log entries
correlation_id_var: ContextVar[str] = ContextVar("correlation_id", default="")


def get_correlation_id() -> str:
    """Get current correlation ID, generating one if not set."""
    cid = correlation_id_var.get()
    if not cid:
        cid = uuid.uuid4().hex[:12]
        correlation_id_var.set(cid)
    return cid


def set_correlation_id(cid: str | None = None) -> str:
    """Set a new correlation ID. Returns the ID."""
    cid = cid or uuid.uuid4().hex[:12]
    correlation_id_var.set(cid)
    return cid


def add_correlation_id(logger: Any, method_name: str, event_dict: dict[str, Any]) -> dict[str, Any]:
    """Structlog processor that adds correlation_id to every log entry."""
    cid = correlation_id_var.get()
    if cid:
        event_dict["correlation_id"] = cid
    return event_dict


def setup_logging() -> None:
    """Configure structlog for the application."""
    settings = get_settings()

    # Configure stdlib logging level so structlog messages are not silently dropped.
    # structlog uses stdlib.LoggerFactory, which delegates to Python's logging module;
    # without this, the root logger stays at WARNING and filters out INFO messages.
    log_level = getattr(logging, settings.log_level.upper(), logging.INFO)
    logging.basicConfig(format="%(message)s", level=log_level)

    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        add_correlation_id,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.UnicodeDecoder(),
    ]

    if settings.log_format == "json":
        renderer: structlog.types.Processor = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer()

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.processors.format_exc_info,
            renderer,
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Get a named logger instance."""
    return structlog.get_logger(name)
