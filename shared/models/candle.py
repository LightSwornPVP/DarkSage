"""Candle domain model — OHLCV price bar for a single symbol/timeframe/timestamp."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum

from pydantic import BaseModel, Field, field_validator, model_validator


class Timeframe(str, Enum):
    """Supported candle timeframes."""

    M1 = "1m"
    M5 = "5m"
    M15 = "15m"
    M30 = "30m"
    H1 = "1h"
    H4 = "4h"
    D1 = "1d"
    W1 = "1w"


class Candle(BaseModel):
    """A single OHLCV price bar.

    Deterministic and provider-agnostic: nothing here assumes a specific
    market-data provider (see ARCHITECTURE.md Section 7).
    """

    model_config = {"frozen": True}

    symbol: str = Field(min_length=1, max_length=32)
    timeframe: Timeframe
    timestamp: datetime
    open: Decimal = Field(gt=0)
    high: Decimal = Field(gt=0)
    low: Decimal = Field(gt=0)
    close: Decimal = Field(gt=0)
    volume: Decimal = Field(ge=0)

    @field_validator("timestamp")
    @classmethod
    def _timestamp_must_be_timezone_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError(
                "timestamp must be timezone-aware; naive datetimes are rejected "
                "rather than silently assumed to be UTC"
            )
        return value.astimezone(timezone.utc)

    @field_validator("symbol")
    @classmethod
    def _symbol_uppercase(cls, value: str) -> str:
        return value.strip().upper()

    @model_validator(mode="after")
    def _validate_ohlc_consistency(self) -> "Candle":
        if self.high < self.low:
            raise ValueError("high must be >= low")
        if self.high < self.open or self.high < self.close:
            raise ValueError("high must be >= open and >= close")
        if self.low > self.open or self.low > self.close:
            raise ValueError("low must be <= open and <= close")
        return self
