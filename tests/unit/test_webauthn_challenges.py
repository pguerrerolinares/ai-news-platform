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
