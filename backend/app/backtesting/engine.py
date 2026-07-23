"""``BacktestEngine`` — deterministic chronological event processing.

The central anti-lookahead primitive is ``iter_backtest_steps``: at index
``i`` it hands out ``candles[: i + 1]`` and nothing else. There is no way
for a consumer to reach into ``candles[i + 1:]`` short of holding a
reference to the original sequence — strategies and execution simulators in
later slices are built to only ever receive the sliced view.

``BacktestConfig.start``/``end`` bound the *active* simulation window;
candles dated before ``start`` may still be supplied as warm-up context
(visible to indicators, but no trade decisions are made until ``start``).
Candles dated after ``end`` are rejected outright — there is no legitimate
reason to supply them, and silently truncating them would only hide a
caller's mistake.
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable, Iterator, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone

from backend.app.backtesting.config import BacktestConfig
from backend.app.backtesting.errors import InsufficientHistoryError, InvalidHistoryError
from backend.app.backtesting.types import (
    FLAT_POSITION,
    BacktestResult,
    BacktestRun,
    EquityObservation,
)
from shared.models.candle import Candle


def validate_backtest_history(candles: Sequence[Candle], config: BacktestConfig) -> None:
    """Fail closed on any candle history a backtest cannot safely run over."""
    if not candles:
        raise InvalidHistoryError("no candles supplied for backtest")

    expected_symbol = config.symbol.strip().upper()
    symbols = {candle.symbol for candle in candles}
    if symbols != {expected_symbol}:
        raise InvalidHistoryError(
            f"candle history symbol(s) {sorted(symbols)} do not match config symbol '{expected_symbol}'"
        )

    timeframes = {candle.timeframe for candle in candles}
    if timeframes != {config.timeframe}:
        raise InvalidHistoryError(
            f"candle history timeframe(s) {sorted(t.value for t in timeframes)} do not match "
            f"config timeframe '{config.timeframe.value}'"
        )

    for previous, current in zip(candles, candles[1:], strict=False):
        if current.timestamp <= previous.timestamp:
            raise InvalidHistoryError(
                "candle history must be strictly ordered by ascending timestamp with no "
                f"duplicates (found {previous.timestamp} then {current.timestamp})"
            )

    if candles[-1].timestamp < config.start:
        raise InsufficientHistoryError(
            f"all supplied candles end at {candles[-1].timestamp.isoformat()}, before the "
            f"configured start {config.start.isoformat()}"
        )
    if any(candle.timestamp > config.end for candle in candles):
        raise InvalidHistoryError(f"candle history extends beyond the configured end {config.end.isoformat()}")


@dataclass(frozen=True, slots=True)
class BacktestStep:
    """One chronological step of the backtest: the current candle, and
    exactly the history that would have been visible at that instant."""

    index: int
    candle: Candle
    visible_candles: tuple[Candle, ...]
    is_active: bool


def iter_backtest_steps(candles: Sequence[Candle], config: BacktestConfig) -> Iterator[BacktestStep]:
    """Yield one ``BacktestStep`` per candle, in chronological order.

    ``visible_candles`` for step ``i`` is always exactly ``candles[: i + 1]``
    — never ``candles[i + 1 :]`` or anything computed from it.
    """
    validate_backtest_history(candles, config)
    for index, candle in enumerate(candles):
        yield BacktestStep(
            index=index,
            candle=candle,
            visible_candles=tuple(candles[: index + 1]),
            is_active=candle.timestamp >= config.start,
        )


def compute_run_id(config: BacktestConfig) -> str:
    """A deterministic identifier derived purely from ``config`` — the same
    config always yields the same run id, independent of wall-clock time."""
    payload = "|".join(
        [
            config.strategy_id,
            config.strategy_version,
            config.symbol,
            config.timeframe.value,
            config.start.isoformat(),
            config.end.isoformat(),
            str(config.initial_capital),
            repr(sorted(config.parameters.items(), key=lambda item: item[0])),
            str(config.cost_config.commission_rate),
            str(config.cost_config.spread),
            str(config.cost_config.slippage_rate),
            str(config.random_seed),
            str(config.data_source_id),
            str(config.reproducibility_id),
        ]
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


class BacktestEngine:
    """Drives deterministic chronological event processing over a candle
    series.

    This slice provides the validated iteration primitive and a trivial
    always-flat run (no strategy involved yet) so the full ``BacktestResult``
    shape is exercised end-to-end; Slice 2.2 wires in real strategy-driven
    decisions on top of the same ``iter_steps``.
    """

    def __init__(
        self,
        config: BacktestConfig,
        candles: Sequence[Candle],
        *,
        clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    ) -> None:
        validate_backtest_history(candles, config)
        self._config = config
        self._candles = tuple(candles)
        self._clock = clock

    @property
    def config(self) -> BacktestConfig:
        return self._config

    def iter_steps(self) -> Iterator[BacktestStep]:
        return iter_backtest_steps(self._candles, self._config)

    def run(self) -> BacktestResult:
        """Run with no strategy: the simulated position stays flat
        throughout, so the equity curve is constant at ``initial_capital``.
        """
        equity_curve = tuple(
            EquityObservation(
                timestamp=step.candle.timestamp,
                equity=self._config.initial_capital,
                cash=self._config.initial_capital,
                position=FLAT_POSITION,
            )
            for step in self.iter_steps()
            if step.is_active
        )
        run = BacktestRun(
            config=self._config, run_id=compute_run_id(self._config), generated_at=self._clock()
        )
        return BacktestResult(run=run, equity_curve=equity_curve, trades=(), final_position=FLAT_POSITION)
