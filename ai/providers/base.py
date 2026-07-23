"""AIProvider — common interface for all AI providers (local and cloud).

See ARCHITECTURE.md Section 22 (AI Provider Interface). Concrete providers
(local runtime, OpenAI, Anthropic, Google Gemini, custom OpenAI-compatible
endpoints) implement this interface in later slices — this slice defines
the contract only, with no network calls and no vendor SDK dependency.

AI output is advisory only (SECURITY_RULES.md: "AI Output Is Untrusted
Input"). No implementation of this interface may hold broker credentials,
submit orders, or bypass the canonical TradeValidationPipeline
(ARCHITECTURE.md Section 14) — callers must never grant it that authority.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass


@dataclass(frozen=True)
class AIMessage:
    """A single message in a chat-style exchange."""

    role: str  # "system" | "user" | "assistant"
    content: str


@dataclass(frozen=True)
class AICompletionResult:
    """Result of a single-shot completion or chat call."""

    text: str
    provider_name: str
    model: str


class AIProvider(ABC):
    """Abstract base for every AI provider adapter.

    Implementations must be interchangeable: feature code depends only on
    this interface, never on a specific vendor SDK (ARCHITECTURE.md
    Section 22, "avoids vendor lock-in").
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Short, stable identifier for this provider (e.g. 'local', 'openai')."""

    @abstractmethod
    async def complete(self, prompt: str, *, model: str) -> AICompletionResult:
        """Single-shot text completion."""

    @abstractmethod
    async def chat(self, messages: list[AIMessage], *, model: str) -> AICompletionResult:
        """Multi-turn chat completion."""

    @abstractmethod
    def stream(self, messages: list[AIMessage], *, model: str) -> AsyncIterator[str]:
        """Streamed chat completion, yielding text chunks as they arrive."""
