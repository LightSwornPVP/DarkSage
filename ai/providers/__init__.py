"""AI provider adapters — common interface, no vendor SDK leaks into callers."""

from ai.providers.base import AIProvider

__all__ = ["AIProvider"]
