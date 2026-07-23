"""Typed domain concepts for the backtesting engine: position/trade state,
equity observations, and run/result records.

``SimulatedTrade``/``PositionState`` are deliberately named and shaped so
they can never be mistaken for, or substituted into, the real
Signal/TradeProposal/Execution Engine pipeline (ARCHITECTURE.md Section 14)
— they share no base class or field-compatible shape with those types.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from backend.app.backtesting.config import BacktestConfig
from shared.models.signal import SignalDirection


@dataclass(frozen=True, slots=True)
class PositionState:
    """A snapshot of the simulated position at one point in time.

    ``quantity`` is signed: positive is long, negative is short, zero is flat.
    """

    quantity: Decimal
    average_entry_price: Decimal | None = None

    def __post_init__(self) -> None:
        if self.quantity == 0 and self.average_entry_price is not None:
            raise ValueError("a flat position (quantity=0) cannot have an entry price")
        if self.quantity != 0 and self.average_entry_price is None:
            raise ValueError("a non-flat position must have an entry price")
        if self.average_entry_price is not None and self.average_entry_price <= 0:
            raise ValueError("average_entry_price must be > 0")

    @property
    def is_flat(self) -> bool:
        return self.quantity == 0

    @property
    def direction(self) -> SignalDirection | None:
        if self.quantity > 0:
            return SignalDirection.LONG
        if self.quantity < 0:
            return SignalDirection.SHORT
        return None


FLAT_POSITION = PositionState(quantity=Decimal(0), average_entry_price=None)


@dataclass(frozen=True, slots=True)
class EquityObservation:
    """The simulated portfolio's state at one bar's timestamp."""

    timestamp: datetime
    equity: Decimal
    cash: Decimal
    position: PositionState

    def __post_init__(self) -> None:
        if self.timestamp.tzinfo is None:
            raise ValueError("EquityObservation.timestamp must be timezone-aware")


@dataclass(frozen=True, slots=True)
class SimulatedTrade:
    """A completed simulated round-trip (entry -> exit).

    Populated by Slice 2.3's execution simulator; the shape is fixed now so
    downstream consumers (BacktestResult, Slice 2.4 metrics) have a stable
    contract to build against.
    """

    symbol: str
    direction: SignalDirection
    entry_time: datetime
    entry_price: Decimal
    exit_time: datetime
    exit_price: Decimal
    quantity: Decimal
    fees_paid: Decimal
    pnl: Decimal

    def __post_init__(self) -> None:
        if self.entry_time.tzinfo is None or self.exit_time.tzinfo is None:
            raise ValueError("SimulatedTrade timestamps must be timezone-aware")
        if self.exit_time < self.entry_time:
            raise ValueError("exit_time must be >= entry_time (no lookahead into the past either)")
        if self.quantity <= 0:
            raise ValueError("quantity must be a positive magnitude")
        if self.entry_price <= 0 or self.exit_price <= 0:
            raise ValueError("entry_price and exit_price must be > 0")
        if self.fees_paid < 0:
            raise ValueError("fees_paid must be >= 0")


@dataclass(frozen=True, slots=True)
class BacktestRun:
    """One executed attempt at a ``BacktestConfig``.

    ``run_id`` is a deterministic function of ``config`` (see
    ``engine.compute_run_id``) — reproducing the same config always yields
    the same run identity. ``generated_at`` is wall-clock metadata only and
    never feeds into any calculation.
    """

    config: BacktestConfig
    run_id: str
    generated_at: datetime

    def __post_init__(self) -> None:
        if self.generated_at.tzinfo is None:
            raise ValueError("BacktestRun.generated_at must be timezone-aware")


@dataclass(frozen=True, slots=True)
class BacktestResult:
    """The full output of a backtest run."""

    run: BacktestRun
    equity_curve: tuple[EquityObservation, ...]
    trades: tuple[SimulatedTrade, ...]
    final_position: PositionState

    @property
    def config(self) -> BacktestConfig:
        return self.run.config
