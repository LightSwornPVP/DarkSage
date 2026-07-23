"""Reproducible backtest run configuration.

A ``BacktestConfig`` is the complete, frozen "recipe" for a run: everything
needed to reproduce it exactly (ARCHITECTURE.md Section 7 lineage —
Provider -> Normalizer -> ... -> Backtester). It never includes wall-clock
metadata (e.g. "when was this run executed") — that belongs on
``BacktestRun``, so two configs with identical substantive inputs compare
equal regardless of when each was executed.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import Enum

from backend.app.backtesting.errors import InvalidBacktestConfigError, InvalidExecutionConfigError
from shared.models.candle import Timeframe

# A strategy parameter value must be a plain, comparable, reproducibility-safe
# type — no callables, no mutable containers.
StrategyParameterValue = Decimal | int | float | str | bool


@dataclass(frozen=True, slots=True)
class CostConfig:
    """Trading-cost assumptions. Purely data at this layer — Slice 2.3's
    execution simulator is what actually applies these.

    ``commission_rate``/``slippage_rate`` are fractions of notional value
    (e.g. ``Decimal("0.001")`` == 10 bps). ``spread`` is an absolute
    price-unit half-spread applied on top of slippage.
    """

    commission_rate: Decimal = Decimal(0)
    spread: Decimal = Decimal(0)
    slippage_rate: Decimal = Decimal(0)

    def __post_init__(self) -> None:
        if self.commission_rate < 0:
            raise InvalidExecutionConfigError("commission_rate must be >= 0")
        if self.spread < 0:
            raise InvalidExecutionConfigError("spread must be >= 0")
        if self.slippage_rate < 0:
            raise InvalidExecutionConfigError("slippage_rate must be >= 0")


class FillTiming(str, Enum):
    """When a simulated fill may occur relative to the bar that produced
    the signal — the explicit rule Slice 2.3 uses to avoid any lookahead
    ambiguity about "what price could this order actually have filled at?".
    """

    NEXT_BAR_OPEN = "next_bar_open"
    """Fill at the opening price of the bar *after* the signal bar. The
    safest default: the signal is based on bar N's close, and the earliest
    tradable price after that close is bar N+1's open."""

    SAME_BAR_CLOSE = "same_bar_close"
    """Fill at the same bar's close — only non-lookahead because the
    strategy's decision was itself based on that same close, so no
    information later than the signal is used."""


@dataclass(frozen=True, slots=True)
class PositionSizingConfig:
    """How much to trade, expressed as a fraction of equity at entry time.

    ``max_participation_rate``, if set, caps the entry quantity at that
    fraction of the fill bar's volume — a simple, single-tranche liquidity
    constraint. It is deliberately not a full partial-fill/order-book model
    (that would be over-engineering for this slice): the cap only ever
    reduces the *initial* sizing decision, and an exit always fully closes
    the existing position regardless of that bar's volume.
    """

    equity_fraction: Decimal = Decimal(1)
    max_participation_rate: Decimal | None = None

    def __post_init__(self) -> None:
        if not (Decimal(0) < self.equity_fraction <= Decimal(1)):
            raise InvalidExecutionConfigError("equity_fraction must be in (0, 1]")
        if self.max_participation_rate is not None and not (Decimal(0) < self.max_participation_rate <= Decimal(1)):
            raise InvalidExecutionConfigError("max_participation_rate must be in (0, 1]")


@dataclass(frozen=True, slots=True)
class ExecutionConfig:
    """Everything Slice 2.3's execution simulator needs: costs, fill
    timing, and position sizing."""

    cost: CostConfig = field(default_factory=CostConfig)
    fill_timing: FillTiming = FillTiming.NEXT_BAR_OPEN
    position_sizing: PositionSizingConfig = field(default_factory=PositionSizingConfig)


@dataclass(frozen=True, slots=True)
class BacktestConfig:
    """The complete, reproducible configuration for one backtest run.

    Two configs with identical field values are, by construction,
    reproducibility-equivalent — running the engine twice against the same
    config and the same candle history must produce an identical
    ``BacktestResult`` (Slice 2.1 requirement: "same inputs => same outputs").
    """

    strategy_id: str
    strategy_version: str
    symbol: str
    timeframe: Timeframe
    start: datetime
    end: datetime
    initial_capital: Decimal
    parameters: Mapping[str, StrategyParameterValue] = field(default_factory=dict)
    execution_config: ExecutionConfig = field(default_factory=ExecutionConfig)
    random_seed: int | None = None
    data_source_id: str | None = None
    reproducibility_id: str | None = None

    def __post_init__(self) -> None:
        if not self.strategy_id.strip():
            raise InvalidBacktestConfigError("strategy_id must not be blank")
        if not self.strategy_version.strip():
            raise InvalidBacktestConfigError("strategy_version must not be blank")
        if not self.symbol.strip():
            raise InvalidBacktestConfigError("symbol must not be blank")
        if self.start.tzinfo is None or self.end.tzinfo is None:
            raise InvalidBacktestConfigError("start and end must be timezone-aware")
        if self.end <= self.start:
            raise InvalidBacktestConfigError("end must be after start")
        if self.initial_capital <= 0:
            raise InvalidBacktestConfigError("initial_capital must be > 0")
