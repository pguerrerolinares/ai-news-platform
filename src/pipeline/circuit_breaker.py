"""Simple in-memory circuit breaker for pipeline sources."""

from __future__ import annotations

import time

from src.core.logging import get_logger

logger = get_logger(__name__)


class CircuitBreaker:
    """Tracks consecutive failures per source and disables after threshold.

    After ``threshold`` consecutive failures, the circuit opens (source
    disabled) for ``cooldown_seconds``. After the cooldown, the circuit
    closes and the source is retried.

    State resets on process restart (acceptable for this use case).
    """

    def __init__(self, threshold: int = 3, cooldown_seconds: int = 3600) -> None:
        self._threshold = threshold
        self._cooldown = cooldown_seconds
        self._failures: dict[str, int] = {}
        self._opened_at: dict[str, float] = {}

    def record_failure(self, source: str) -> None:
        """Record a failure for a source."""
        self._failures[source] = self._failures.get(source, 0) + 1
        if self._failures[source] >= self._threshold:
            self._opened_at[source] = time.monotonic()
            logger.warning(
                "circuit_breaker_opened",
                source=source,
                failures=self._failures[source],
                cooldown_seconds=self._cooldown,
            )

    def record_success(self, source: str) -> None:
        """Record a success, resetting the failure counter."""
        self._failures.pop(source, None)
        self._opened_at.pop(source, None)

    def is_open(self, source: str) -> bool:
        """Check if the circuit is open (source should be skipped)."""
        if self._failures.get(source, 0) < self._threshold:
            return False

        opened_at = self._opened_at.get(source)
        if opened_at is None:
            return False

        # Check if cooldown has elapsed
        if time.monotonic() - opened_at >= self._cooldown:
            # Reset — allow retry
            self._failures.pop(source, None)
            self._opened_at.pop(source, None)
            logger.info("circuit_breaker_reset", source=source)
            return False

        return True
