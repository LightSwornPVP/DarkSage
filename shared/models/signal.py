"""Signal domain model — see PROJECT_SPEC.md Section 16 (Signal System).

A Signal is advisory research output. It is not a trade and has no
authority over the canonical TradeValidationPipeline (ARCHITECTURE.md
Section 14) — see TradeProposal for the pipeline's entry point.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Annotated

from pydantic import BaseModel, Field, field_validator

PositivePrice = Annotated[Decimal, Field(gt=0)]


class SignalDirection(str, Enum):
    LONG = "long"
    SHORT = "short"


class SignalGrade(str, Enum):
    """Per PROJECT_SPEC.md Section 16 — grades must be based on measurable inputs."""

    A_PLUS = "A+"
    A = "A"
    B = "B"
    C = "C"
    D = "D"


class Signal(BaseModel):
    model_config = {"frozen": True}

    symbol: str = Field(min_length=1, max_length=32)
    company: str | None = None
    direction: SignalDirection
    strategy_id: str = Field(min_length=1)
    strategy_version: str = Field(min_length=1)
    entry: Decimal = Field(gt=0)
    stop: Decimal = Field(gt=0)
    targets: list[PositivePrice] = Field(default_factory=list)
    risk_reward: float | None = Field(default=None, ge=0)
    confidence: float = Field(ge=0, le=1)
    quantitative_score: float | None = Field(default=None, ge=0, le=1)
    technical_score: float | None = Field(default=None, ge=0, le=1)
    fundamental_score: float | None = Field(default=None, ge=0, le=1)
    sentiment_score: float | None = Field(default=None, ge=0, le=1)
    detected_patterns: list[str] = Field(default_factory=list)
    indicators: dict[str, float] = Field(default_factory=dict)
    reasoning: str = Field(default="")
    grade: SignalGrade
    timestamp: datetime
    expiration: datetime | None = None

    @field_validator("timestamp", "expiration")
    @classmethod
    def _timezone_aware(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            raise ValueError(
                "timestamp/expiration must be timezone-aware; naive datetimes "
                "are rejected rather than silently assumed to be UTC"
            )
        return value.astimezone(timezone.utc)

    @field_validator("symbol")
    @classmethod
    def _symbol_uppercase(cls, value: str) -> str:
        return value.strip().upper()
