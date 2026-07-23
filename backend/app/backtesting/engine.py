"""``BacktestEngine`` — the top-level backtest orchestrator.

Owns the two ways to run a backtest:

- ``run()``: a trivial always-flat run (no strategy) that exercises the
  full ``BacktestResult`` shape — also useful later as a "flat"/"do
  nothing" baseline to compare a real strategy against.
- ``run_strategy()``: the real path — signal simulation (Slice 2.2) feeding
  execution simulation (Slice 2.3) feeding portfolio bookkeeping, producing
  actual trades and an equity curve driven by simulated fills.

See ``history.py`` for the underlying anti-lookahead iteration primitive
this engine is built on.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from datetime import datetime, timezone

from backend.app.backtesting.config import BacktestConfig
from backend.app.backtesting.execution.simulator import ExecutionSimulator
from backend.app.backtesting.history import (
    BacktestStep,
    compute_run_id,
    iter_backtest_steps,
    validate_backtest_history,
)
from backend.app.backtesting.portfolio import Portfolio
from backend.app.backtesting.strategy.base import Strategy
from backend.app.backtesting.strategy.simulate import simulate_signals
from backend.app.backtesting.types import FLAT_POSITION, BacktestResult, BacktestRun, EquityObservation
from shared.models.candle import Candle

__all__ = [
    "BacktestEngine",
    "BacktestStep",
    "compute_run_id",
    "iter_backtest_steps",
    "validate_backtest_history",
]


class BacktestEngine:
    """Drives deterministic chronological event processing over a candle
    series."""

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

    def iter_steps(self) -> Sequence[BacktestStep]:
        return list(iter_backtest_steps(self._candles, self._config))

    def _new_run(self) -> BacktestRun:
        return BacktestRun(
            config=self._config, run_id=compute_run_id(self._config), generated_at=self._clock()
        )

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
        return BacktestResult(
            run=self._new_run(), equity_curve=equity_curve, trades=(), final_position=FLAT_POSITION
        )

    def run_strategy(self, strategy: Strategy) -> BacktestResult:
        """Run ``strategy`` over this engine's candles: generate signals,
        simulate fills against ``self._config.execution_config``, and track
        portfolio state through to a full ``BacktestResult``."""
        steps = self.iter_steps()
        intents = simulate_signals(steps, strategy)

        simulator = ExecutionSimulator(self._config.execution_config)
        portfolio = Portfolio(initial_capital=self._config.initial_capital, symbol=self._config.symbol)

        intents_by_index = {intent.signal_index: intent for intent in intents}
        equity_curve: list[EquityObservation] = []

        for step in steps:
            intent = intents_by_index.get(step.index)
            if intent is not None:
                fill = simulator.fill_intent(
                    intent,
                    candles=self._candles,
                    position=portfolio.position,
                    equity_at_signal=portfolio.equity(step.candle.close),
                )
                if fill is not None:
                    portfolio.apply_fill(fill)

            if step.is_active:
                equity_curve.append(
                    EquityObservation(
                        timestamp=step.candle.timestamp,
                        equity=portfolio.equity(step.candle.close),
                        cash=portfolio.cash,
                        position=portfolio.position,
                    )
                )

        return BacktestResult(
            run=self._new_run(),
            equity_curve=tuple(equity_curve),
            trades=portfolio.trades,
            final_position=portfolio.position,
        )
