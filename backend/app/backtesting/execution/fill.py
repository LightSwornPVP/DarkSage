"""``SimulatedFill`` — the result of simulating one order intent's execution.

Simulation-only: this is what actually happened in the backtest's model of
the market, after costs — never a real fill from a real broker.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from backend.app.backtesting.strategy.intent import IntentAction


@dataclass(frozen=True, slots=True)
class SimulatedFill:
    """A completed simulated fill, after spread/slippage/commission."""

    action: IntentAction
    signal_time: datetime
    fill_time: datetime
    fill_price: Decimal
    quantity: Decimal
    commission: Decimal
    stop_price: Decimal | None = None
    """Carried through from the opening intent so ``Portfolio`` can attach
    it to the resulting ``SimulatedTrade`` for R-multiple support."""

    def __post_init__(self) -> None:
        if self.signal_time.tzinfo is None or self.fill_time.tzinfo is None:
            raise ValueError("SimulatedFill timestamps must be timezone-aware")
        if self.fill_time < self.signal_time:
            raise ValueError("fill_time must be >= signal_time — a fill cannot precede its own signal")
        if self.fill_price <= 0:
            raise ValueError("fill_price must be > 0")
        if self.quantity <= 0:
            raise ValueError("quantity must be a positive magnitude")
        if self.commission < 0:
            raise ValueError("commission must be >= 0")
        if self.stop_price is not None and self.stop_price <= 0:
            raise ValueError("stop_price must be > 0")
