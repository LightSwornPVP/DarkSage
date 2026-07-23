"""``ExecutionSimulator`` — turns a ``SimulatedOrderIntent`` into a
``SimulatedFill``, applying costs and the configured fill-timing rule.

Order-of-events semantics (the anti-lookahead contract for this module):

    signal produced at bar N's close (``intent.signal_index == N``)
    -> earliest permitted fill is either bar N's own close (SAME_BAR_CLOSE)
       or bar N+1's open (NEXT_BAR_OPEN, the default)
    -> the simulator reads at most ``candles[N]`` or ``candles[N + 1]`` —
       never anything beyond that

If bar N is the last candle in history and ``NEXT_BAR_OPEN`` is configured,
there is no bar N+1 to fill against — ``fill_intent`` returns ``None``
(fail-safe: no fill, not a fabricated one) rather than reading past the end
of history.
"""

from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal

from backend.app.backtesting.config import ExecutionConfig, FillTiming
from backend.app.backtesting.errors import InvalidExecutionConfigError
from backend.app.backtesting.execution.fill import SimulatedFill
from backend.app.backtesting.strategy.intent import IntentAction, SimulatedOrderIntent
from backend.app.backtesting.types import PositionState
from shared.models.candle import Candle
from shared.models.signal import SignalDirection


class ExecutionSimulator:
    """Deterministically simulates fills for order intents against a fixed
    ``ExecutionConfig`` (costs, fill timing, position sizing)."""

    def __init__(self, config: ExecutionConfig) -> None:
        self._config = config

    def fill_intent(
        self,
        intent: SimulatedOrderIntent,
        *,
        candles: Sequence[Candle],
        position: PositionState,
        equity_at_signal: Decimal,
    ) -> SimulatedFill | None:
        fill_candle, use_close = self._resolve_fill_candle(candles, intent.signal_index)
        if fill_candle is None:
            return None  # no bar exists yet to fill against (end of history)

        base_price = fill_candle.close if use_close else fill_candle.open
        is_buy = self._is_buy_side(intent, position)
        fill_price = self._apply_costs(base_price, is_buy=is_buy)

        if intent.action is IntentAction.CLOSE:
            quantity = abs(position.quantity)
        else:
            quantity = self._size_entry(equity_at_signal, fill_price, fill_candle)
            if quantity <= 0:
                return None  # nothing tradeable after sizing/liquidity constraints

        commission = fill_price * quantity * self._config.cost.commission_rate
        return SimulatedFill(
            action=intent.action,
            signal_time=intent.signal_time,
            fill_time=fill_candle.timestamp,
            fill_price=fill_price,
            quantity=quantity,
            commission=commission,
        )

    def _resolve_fill_candle(
        self, candles: Sequence[Candle], signal_index: int
    ) -> tuple[Candle | None, bool]:
        """Returns (candle to price the fill from, whether to use its close
        rather than its open)."""
        if self._config.fill_timing is FillTiming.SAME_BAR_CLOSE:
            return candles[signal_index], True
        if self._config.fill_timing is FillTiming.NEXT_BAR_OPEN:
            next_index = signal_index + 1
            if next_index >= len(candles):
                return None, False
            return candles[next_index], False
        raise InvalidExecutionConfigError(f"unrecognized fill_timing: {self._config.fill_timing}")

    def _is_buy_side(self, intent: SimulatedOrderIntent, position: PositionState) -> bool:
        if intent.action is IntentAction.OPEN_LONG:
            return True
        if intent.action is IntentAction.OPEN_SHORT:
            return False
        if intent.action is IntentAction.CLOSE:
            if position.direction is SignalDirection.LONG:
                return False  # selling to close a long
            if position.direction is SignalDirection.SHORT:
                return True  # buying to cover a short
            raise InvalidExecutionConfigError("cannot fill a CLOSE intent against a flat position")
        raise AssertionError(f"unhandled IntentAction: {intent.action}")

    def _apply_costs(self, base_price: Decimal, *, is_buy: bool) -> Decimal:
        cost = self._config.cost
        adjustment = cost.spread / 2 + base_price * cost.slippage_rate
        fill_price = base_price + adjustment if is_buy else base_price - adjustment
        if fill_price <= 0:
            raise InvalidExecutionConfigError(
                f"cost configuration produced a non-positive fill price ({fill_price}) "
                f"from base price {base_price} — commission/spread/slippage assumptions are ambiguous"
            )
        return fill_price

    def _size_entry(self, equity: Decimal, fill_price: Decimal, fill_candle: Candle) -> Decimal:
        sizing = self._config.position_sizing
        quantity = (equity * sizing.equity_fraction) / fill_price
        if sizing.max_participation_rate is not None:
            liquidity_cap = fill_candle.volume * sizing.max_participation_rate
            quantity = min(quantity, liquidity_cap)
        return quantity
