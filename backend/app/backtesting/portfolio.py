"""``Portfolio`` — simulated cash/position bookkeeping driven by fills.

Pure in-memory simulation state: applying a ``SimulatedFill`` updates cash
and the current ``PositionState``, and a completed round-trip (an
opening fill followed by a closing fill) is recorded as a ``SimulatedTrade``.
Nothing here can place a real order or touch a real account.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from backend.app.backtesting.execution.fill import SimulatedFill
from backend.app.backtesting.strategy.intent import IntentAction
from backend.app.backtesting.types import FLAT_POSITION, PositionState, SimulatedTrade
from shared.models.signal import SignalDirection


class Portfolio:
    """Tracks cash, position, and completed trades through a sequence of
    simulated fills, in the order they are applied."""

    def __init__(self, *, initial_capital: Decimal, symbol: str) -> None:
        if initial_capital <= 0:
            raise ValueError("initial_capital must be > 0")
        self._symbol = symbol
        self._cash = initial_capital
        self._position = FLAT_POSITION
        self._entry_time: datetime | None = None
        self._entry_commission = Decimal(0)
        self._entry_stop_price: Decimal | None = None
        self._trades: list[SimulatedTrade] = []

    @property
    def cash(self) -> Decimal:
        return self._cash

    @property
    def position(self) -> PositionState:
        return self._position

    @property
    def trades(self) -> tuple[SimulatedTrade, ...]:
        return tuple(self._trades)

    def equity(self, current_price: Decimal) -> Decimal:
        """Mark-to-market equity: cash plus the position's current value.

        Signed quantity makes this formula correct for both long and short:
        a short position's quantity is negative, and cash already reflects
        the proceeds received when the short was opened, so
        ``cash + quantity * current_price`` naturally nets out the
        liability as price moves.
        """
        return self._cash + self._position.quantity * current_price

    def apply_fill(self, fill: SimulatedFill) -> None:
        if fill.action is IntentAction.OPEN_LONG:
            self._open(
                quantity=fill.quantity,
                price=fill.fill_price,
                commission=fill.commission,
                time=fill.fill_time,
                stop_price=fill.stop_price,
            )
        elif fill.action is IntentAction.OPEN_SHORT:
            self._open(
                quantity=-fill.quantity,
                price=fill.fill_price,
                commission=fill.commission,
                time=fill.fill_time,
                stop_price=fill.stop_price,
            )
        elif fill.action is IntentAction.CLOSE:
            self._close(fill)
        else:
            raise AssertionError(f"unhandled IntentAction: {fill.action}")

    def _open(
        self,
        *,
        quantity: Decimal,
        price: Decimal,
        commission: Decimal,
        time: datetime,
        stop_price: Decimal | None,
    ) -> None:
        if not self._position.is_flat:
            raise ValueError("cannot open a new position while one is already open")
        # Buying (positive quantity) spends cash; short-selling (negative
        # quantity) receives proceeds — both are `cash -= quantity * price`.
        self._cash -= quantity * price
        self._cash -= commission
        self._position = PositionState(quantity=quantity, average_entry_price=price)
        self._entry_time = time
        self._entry_commission = commission
        self._entry_stop_price = stop_price

    def _close(self, fill: SimulatedFill) -> None:
        position = self._position
        if position.is_flat:
            raise ValueError("cannot close a position while flat")
        assert position.average_entry_price is not None
        assert self._entry_time is not None

        entry_price = position.average_entry_price
        entry_time = self._entry_time
        entry_commission = self._entry_commission
        entry_stop_price = self._entry_stop_price
        quantity_magnitude = abs(position.quantity)
        direction = position.direction
        assert direction is not None

        # Closing is the mirror transaction of opening: opening used
        # `cash -= quantity * price` for signed `quantity`, so closing (a
        # transaction of the opposite sign) is `cash += quantity * price`.
        # Long (quantity > 0): selling receives cash. Short (quantity < 0):
        # buying back spends cash. Both fall out of this one formula.
        self._cash += position.quantity * fill.fill_price
        self._cash -= fill.commission

        if direction is SignalDirection.LONG:
            gross_pnl = (fill.fill_price - entry_price) * quantity_magnitude
        else:
            gross_pnl = (entry_price - fill.fill_price) * quantity_magnitude

        total_fees = entry_commission + fill.commission
        self._trades.append(
            SimulatedTrade(
                symbol=self._symbol,
                direction=direction,
                entry_time=entry_time,
                entry_price=entry_price,
                exit_time=fill.fill_time,
                exit_price=fill.fill_price,
                quantity=quantity_magnitude,
                fees_paid=total_fees,
                pnl=gross_pnl - total_fees,
                stop_price=entry_stop_price,
            )
        )
        self._position = FLAT_POSITION
        self._entry_time = None
        self._entry_commission = Decimal(0)
        self._entry_stop_price = None
