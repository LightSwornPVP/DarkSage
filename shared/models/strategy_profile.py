"""StrategyProfile domain model — see PROJECT_SPEC.md Section 6, ARCHITECTURE.md Section 10."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class StrategyStatus(str, Enum):
    """Per PROJECT_SPEC.md Section 6 / ARCHITECTURE.md Section 10."""

    EXPERIMENTAL = "experimental"
    WATCH = "watch"
    ACTIVE = "active"
    REDUCED = "reduced"
    SUSPENDED = "suspended"


class StrategyProfile(BaseModel):
    """A versioned, self-describing strategy definition.

    No silent changes: per AGENTS.md, changing strategy logic requires
    incrementing ``version`` and preserving prior results elsewhere
    (strategy performance history is out of scope for this model).
    """

    model_config = {"frozen": True}

    strategy_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    version: str = Field(min_length=1)
    status: StrategyStatus = StrategyStatus.EXPERIMENTAL
    rules: dict[str, str] = Field(default_factory=dict)
    indicators: list[str] = Field(default_factory=list)
    entry_logic: str = Field(default="")
    exit_logic: str = Field(default="")
    stop_logic: str = Field(default="")
    risk_rules: dict[str, float] = Field(default_factory=dict)
    supported_timeframes: list[str] = Field(default_factory=list)
    supported_instruments: list[str] = Field(default_factory=list)
    historical_statistics: dict[str, float] = Field(default_factory=dict)
