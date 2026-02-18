"""Base interface for all notifiers."""

from __future__ import annotations

from abc import ABC, abstractmethod


class BaseNotifier(ABC):
    """Abstract base for notification delivery."""

    @abstractmethod
    async def send_message(self, message: str) -> bool:
        """Send a text message. Returns True on success."""
        ...

    @abstractmethod
    async def send_error(self, error: str, context: str = "") -> bool:
        """Send an error notification. Returns True on success."""
        ...
