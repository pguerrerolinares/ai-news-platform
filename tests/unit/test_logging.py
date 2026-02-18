"""Tests for src.core.logging -- structlog setup and correlation IDs."""

from __future__ import annotations

from src.core.logging import (
    correlation_id_var,
    get_correlation_id,
    get_logger,
    set_correlation_id,
)


# ---------------------------------------------------------------------------
# get_logger
# ---------------------------------------------------------------------------
class TestGetLogger:
    """Verify get_logger returns a usable bound logger."""

    def test_returns_bound_logger(self):
        log = get_logger("test_module")
        # structlog.get_logger returns a proxy; check it has typical log methods
        assert hasattr(log, "info")
        assert hasattr(log, "warning")
        assert hasattr(log, "error")
        assert hasattr(log, "debug")

    def test_different_names_return_loggers(self):
        log1 = get_logger("module_a")
        log2 = get_logger("module_b")
        # Both should be valid logger instances
        assert log1 is not None
        assert log2 is not None


# ---------------------------------------------------------------------------
# Correlation ID -- get
# ---------------------------------------------------------------------------
class TestGetCorrelationId:
    """Verify correlation ID retrieval and auto-generation."""

    def test_generates_id_when_empty(self):
        # Reset the contextvar to empty
        token = correlation_id_var.set("")
        try:
            cid = get_correlation_id()
            assert isinstance(cid, str)
            assert len(cid) == 12  # hex[:12]
        finally:
            correlation_id_var.reset(token)

    def test_returns_existing_id(self):
        token = correlation_id_var.set("abc123def456")
        try:
            cid = get_correlation_id()
            assert cid == "abc123def456"
        finally:
            correlation_id_var.reset(token)


# ---------------------------------------------------------------------------
# Correlation ID -- set
# ---------------------------------------------------------------------------
class TestSetCorrelationId:
    """Verify setting correlation IDs."""

    def test_set_explicit_id(self):
        token = correlation_id_var.set("")
        try:
            returned = set_correlation_id("my-custom-id")
            assert returned == "my-custom-id"
            assert correlation_id_var.get() == "my-custom-id"
        finally:
            correlation_id_var.reset(token)

    def test_set_generates_when_none(self):
        token = correlation_id_var.set("")
        try:
            returned = set_correlation_id(None)
            assert isinstance(returned, str)
            assert len(returned) == 12
            assert correlation_id_var.get() == returned
        finally:
            correlation_id_var.reset(token)

    def test_set_generates_when_omitted(self):
        token = correlation_id_var.set("")
        try:
            returned = set_correlation_id()
            assert isinstance(returned, str)
            assert len(returned) == 12
        finally:
            correlation_id_var.reset(token)

    def test_generated_ids_are_unique(self):
        token = correlation_id_var.set("")
        try:
            id1 = set_correlation_id()
            id2 = set_correlation_id()
            assert id1 != id2
        finally:
            correlation_id_var.reset(token)
