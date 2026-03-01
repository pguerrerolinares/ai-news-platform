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
