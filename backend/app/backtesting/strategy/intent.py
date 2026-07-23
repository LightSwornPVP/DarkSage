"""Strategy decisions and the simulated order intents they translate into.

Everything here is simulation-only and deliberately named/shaped so it can
never be mistaken for, or passed into, the real
Signal/TradeProposal/Execution Engine pipeline (ARCHITECTURE.md Section 14):
no shared base class, no field-compatible shape, no ``execute``/``submit``
capability anywhere in this module.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum

from backend.app.backtesting.types import PositionState


class StrategyAction(str, Enum):
    """What a strategy decided to do at one bar — an intent, not an order."""

    HOLD = "hold"
    ENTER_LONG = "enter_long"
    ENTER_SHORT = "enter_short"
    EXIT = "exit"


@dataclass(frozen=True, slots=True)
class StrategyDecision:
    """A strategy's output for one bar. ``HOLD`` is the explicit
    no-trade/abstention path — strategies are not required to always act."""

    action: StrategyAction
    stop_price: Decimal | None = None
    target_price: Decimal | None = None
    reason: str = ""

    def __post_init__(self) -> None:
        if self.stop_price is not None and self.stop_price <= 0:
            raise ValueError("stop_price must be > 0")
        if self.target_price is not None and self.target_price <= 0:
            raise ValueError("target_price must be > 0")


HOLD_DECISION = StrategyDecision(action=StrategyAction.HOLD)


class IntentAction(str, Enum):
    """What the *simulation* should attempt, after reconciling a decision
    against the current simulated position."""

    OPEN_LONG = "open_long"
    OPEN_SHORT = "open_short"
    CLOSE = "close"


@dataclass(frozen=True, slots=True)
class SimulatedOrderIntent:
    """A simulation-only intent to transact — never a real order.

    ``signal_time``/``signal_index`` identify the bar whose close the
    decision was based on; Slice 2.3's execution simulator locates the
    earliest permitted simulated fill from ``signal_index`` and never reads
    any candle at a later index.
    """

    action: IntentAction
    signal_time: datetime
    signal_index: int
    stop_price: Decimal | None = None
    target_price: Decimal | None = None

    def __post_init__(self) -> None:
        if self.signal_time.tzinfo is None:
            raise ValueError("SimulatedOrderIntent.signal_time must be timezone-aware")
        if self.signal_index < 0:
            raise ValueError("SimulatedOrderIntent.signal_index must be >= 0")


def translate_decision(
    decision: StrategyDecision, position: PositionState, signal_time: datetime, signal_index: int
) -> SimulatedOrderIntent | None:
    """Reconcile a strategy decision against the current position.

    Returns ``None`` (a safe no-op) for every impossible or redundant
    transition — entering a direction already held, or exiting while flat —
    rather than raising. A strategy re-affirming "stay long" every bar is
    normal, not an error; it simply produces no new intent.
    """
    if decision.action is StrategyAction.HOLD:
        return None

    if decision.action is StrategyAction.ENTER_LONG:
        if position.direction is not None:  # already long or short: no direct flip in this slice
            return None
        return SimulatedOrderIntent(
            action=IntentAction.OPEN_LONG,
            signal_time=signal_time,
            signal_index=signal_index,
            stop_price=decision.stop_price,
            target_price=decision.target_price,
        )

    if decision.action is StrategyAction.ENTER_SHORT:
        if position.direction is not None:
            return None
        return SimulatedOrderIntent(
            action=IntentAction.OPEN_SHORT,
            signal_time=signal_time,
            signal_index=signal_index,
            stop_price=decision.stop_price,
            target_price=decision.target_price,
        )

    if decision.action is StrategyAction.EXIT:
        if position.is_flat:
            return None
        return SimulatedOrderIntent(action=IntentAction.CLOSE, signal_time=signal_time, signal_index=signal_index)

    raise AssertionError(f"unhandled StrategyAction: {decision.action}")
