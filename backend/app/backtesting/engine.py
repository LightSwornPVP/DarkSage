"""``BacktestEngine`` — the top-level backtest orchestrator.

Owns the two ways to run a backtest:

- ``run()``: a trivial always-flat run (no strategy) that exercises the
  full ``BacktestResult`` shape — also useful later as a "flat"/"do
  nothing" baseline to compare a real strategy against.
- ``run_strategy()``: the real path. One single chronological pass:

    for each bar N, in order:
        1. if a pending intent from an earlier bar is now permitted to
           fill (NEXT_BAR_OPEN -> exactly bar N, one bar after its signal),
           attempt the fill against bar N's own price data, and update the
           portfolio. An unfilled/rejected intent is simply dropped —
           it does not linger, and it never mutates position state.
        2. record this bar's equity/position snapshot — by construction
           this can only reflect fills resolved in step 1, i.e. fills
           priced using bar N's own data, never a later bar's.
        3. ask the strategy for a decision, using the *actual* portfolio
           position (never an assumed one) and ``visible_candles`` (never
           future ones). If it produces an intent, it becomes the new
           pending intent, to be resolved at the next permitted bar.

No bar's equity snapshot or strategy-visible position can ever reflect a
fill priced from a later bar, and no strategy decision can ever be based on
a fill that was assumed but never actually happened.

See ``history.py`` for the underlying anti-lookahead iteration primitive
this engine is built on.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal

from backend.app.backtesting.config import BacktestConfig, FillTiming
from backend.app.backtesting.errors import InvalidBacktestConfigError, InvalidExecutionConfigError
from backend.app.backtesting.execution.simulator import ExecutionSimulator
from backend.app.backtesting.history import (
    BacktestStep,
    compute_run_id,
    iter_backtest_steps,
    validate_backtest_history,
)
from backend.app.backtesting.portfolio import Portfolio
from backend.app.backtesting.strategy.base import Strategy
from backend.app.backtesting.strategy.context import StrategyContext
from backend.app.backtesting.strategy.intent import SimulatedOrderIntent, translate_decision
from backend.app.backtesting.types import FLAT_POSITION, BacktestResult, BacktestRun, EquityObservation
from shared.models.candle import Candle

__all__ = [
    "BacktestEngine",
    "BacktestStep",
    "compute_run_id",
    "iter_backtest_steps",
    "validate_backtest_history",
]


@dataclass(frozen=True, slots=True)
class _PendingOrder:
    """An intent queued at signal time, waiting for its permitted fill event."""

    intent: SimulatedOrderIntent
    equity_at_signal: Decimal


def _validate_strategy_matches_config(strategy: Strategy, config: BacktestConfig) -> None:
    """Fail closed if the strategy actually being run doesn't match what
    the config claims was run — otherwise a run's recorded lineage
    (strategy id/version/parameters) could silently lie about what
    produced its results."""
    if strategy.strategy_id != config.strategy_id:
        raise InvalidBacktestConfigError(
            f"strategy_id mismatch: strategy is '{strategy.strategy_id}' but config declares '{config.strategy_id}'"
        )
    if strategy.strategy_version != config.strategy_version:
        raise InvalidBacktestConfigError(
            f"strategy_version mismatch: strategy is '{strategy.strategy_version}' but config declares "
            f"'{config.strategy_version}'"
        )
    if dict(strategy.parameters) != dict(config.parameters):
        raise InvalidBacktestConfigError(
            f"strategy parameters mismatch: strategy has {dict(strategy.parameters)} but config declares "
            f"{dict(config.parameters)}"
        )


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
            config=self._config,
            run_id=compute_run_id(self._config, self._candles),
            generated_at=self._clock(),
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
        """Run ``strategy`` chronologically: decide, queue, fill-when-due,
        record — see the module docstring for the exact per-bar ordering.
        """
        _validate_strategy_matches_config(strategy, self._config)
        if self._config.execution_config.fill_timing is FillTiming.SAME_BAR_CLOSE:
            raise InvalidExecutionConfigError(
                "SAME_BAR_CLOSE is not available for strategy-driven runs: a decision based on a "
                "bar's completed close cannot be filled at that same close without look-ahead, and "
                "Phase 2 has no intrabar decision model to justify it. Use NEXT_BAR_OPEN."
            )

        simulator = ExecutionSimulator(self._config.execution_config)
        portfolio = Portfolio(initial_capital=self._config.initial_capital, symbol=self._config.symbol)
        equity_curve: list[EquityObservation] = []
        pending: _PendingOrder | None = None

        for step in self.iter_steps():
            # 1. Resolve any order pending from an earlier bar, using only
            #    this bar's own price data. Unfilled/rejected -> dropped,
            #    never retried, never mutates position.
            if pending is not None:
                fill = simulator.fill_intent(
                    pending.intent,
                    candles=self._candles,
                    position=portfolio.position,
                    equity_at_signal=pending.equity_at_signal,
                )
                if fill is not None:
                    portfolio.apply_fill(fill)
                pending = None

            # 2. Snapshot this bar's state — can only reflect the fill
            #    resolved above (bar N's own data), never a later bar's.
            if step.is_active:
                equity_curve.append(
                    EquityObservation(
                        timestamp=step.candle.timestamp,
                        equity=portfolio.equity(step.candle.close),
                        cash=portfolio.cash,
                        position=portfolio.position,
                    )
                )

            # 3. Let the strategy decide, from the *actual* current
            #    position and only the candles visible through this bar.
            if step.is_active and len(step.visible_candles) >= strategy.warmup_period:
                context = StrategyContext(
                    visible_candles=step.visible_candles,
                    position=portfolio.position,
                    parameters=strategy.parameters,
                )
                decision = strategy.decide(context)
                intent = translate_decision(decision, portfolio.position, step.candle.timestamp, step.index)
                if intent is not None:
                    pending = _PendingOrder(intent=intent, equity_at_signal=portfolio.equity(step.candle.close))

        # Any order still pending here was signalled on the final bar and
        # never reached a bar where it could legally fill — end-of-data,
        # discarded, never applied to the portfolio.

        return BacktestResult(
            run=self._new_run(),
            equity_curve=tuple(equity_curve),
            trades=portfolio.trades,
            final_position=portfolio.position,
        )
