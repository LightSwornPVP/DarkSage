"""Quote domain model — a single point-in-time bid/ask/last snapshot."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from pydantic import BaseModel, Field, field_validator, model_validator


class Quote(BaseModel):
    """A point-in-time quote for a symbol.

    Provider-agnostic: see ARCHITECTURE.md Section 7 (Market Data Architecture).
    """

    model_config = {"frozen": True}

    symbol: str = Field(min_length=1, max_length=32)
    timestamp: datetime
    bid: Decimal = Field(gt=0)
    ask: Decimal = Field(gt=0)
    last: Decimal = Field(gt=0)
    volume: Decimal | None = Field(default=None, ge=0)

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
    def _validate_bid_ask_spread(self) -> "Quote":
        if self.ask < self.bid:
            raise ValueError("ask must be >= bid")
        return self

    @property
    def spread(self) -> Decimal:
        return self.ask - self.bid
