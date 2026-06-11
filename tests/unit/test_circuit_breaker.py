"""Tests for src.pipeline.circuit_breaker."""

from __future__ import annotations

import time

from src.pipeline.circuit_breaker import CircuitBreaker


class TestCircuitBreaker:
    """CircuitBreaker tracks failures and disables sources."""

    def test_initial_state_is_closed(self):
        cb = CircuitBreaker(threshold=3, cooldown_seconds=60)
        assert cb.is_open("hackernews") is False

    def test_opens_after_threshold_failures(self):
        cb = CircuitBreaker(threshold=3, cooldown_seconds=60)
        cb.record_failure("hackernews")
        cb.record_failure("hackernews")
        assert cb.is_open("hackernews") is False
        cb.record_failure("hackernews")
        assert cb.is_open("hackernews") is True

    def test_success_resets_failure_count(self):
        cb = CircuitBreaker(threshold=3, cooldown_seconds=60)
        cb.record_failure("hackernews")
        cb.record_failure("hackernews")
        cb.record_success("hackernews")
        cb.record_failure("hackernews")
        assert cb.is_open("hackernews") is False

    def test_circuit_closes_after_cooldown(self):
        cb = CircuitBreaker(threshold=3, cooldown_seconds=1)
        cb.record_failure("reddit")
        cb.record_failure("reddit")
        cb.record_failure("reddit")
        assert cb.is_open("reddit") is True
        time.sleep(1.1)
        assert cb.is_open("reddit") is False

    def test_sustained_failures_do_not_reset_cooldown(self):
        """Sustained failures after threshold must not restart the cooldown timer.

        Regression: record_failure used to re-stamp _opened_at on every call
        once failures >= threshold, so the cooldown window kept sliding forward
        and the circuit never re-closed.
        """
        cb = CircuitBreaker(threshold=3, cooldown_seconds=1)
        cb.record_failure("reddit")
        cb.record_failure("reddit")
        cb.record_failure("reddit")
        assert cb.is_open("reddit") is True
        # Simulate scheduler continuing to call record_failure during cooldown
        cb.record_failure("reddit")
        cb.record_failure("reddit")
        cb.record_failure("reddit")
        # After cooldown, circuit must allow a retry regardless of extra failures
        time.sleep(1.1)
        assert cb.is_open("reddit") is False

    def test_independent_per_source(self):
        cb = CircuitBreaker(threshold=2, cooldown_seconds=60)
        cb.record_failure("hackernews")
        cb.record_failure("hackernews")
        assert cb.is_open("hackernews") is True
        assert cb.is_open("reddit") is False
