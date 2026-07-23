"""Walk-forward validation: freeze parameters chosen from in-sample data,
then measure them on out-of-sample data that the selection process never saw.

Anti-leakage guarantee: for a window with in-sample period ending at
``in_sample.end``, both the parameter selector and the in-sample backtest
only ever receive candles with ``timestamp < in_sample.end`` — never
candles from that window's out-of-sample period or any later window. The
out-of-sample backtest reuses the exact parameters chosen in-sample; it
never re-selects them from out-of-sample data.

Anti-contamination guarantee for rolling windows: a rolling (non-anchored)
window additionally never sees candles before its own ``in_sample.start``
— in parameter selection, the in-sample backtest, or the out-of-sample
backtest's warm-up context. Without this bound, a "rolling" window would
silently behave like an anchored one, defeating the point of testing
whether a strategy holds up when calibrated on only a recent, fixed-length
slice of history. Anchored windows have no such floor: their in-sample
start is fixed at the true start of the data by construction.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from backend.app.backtesting.config import BacktestConfig, StrategyParameterValue
from backend.app.backtesting.engine import BacktestEngine
from backend.app.backtesting.errors import InvalidPartitionError
from backend.app.backtesting.metrics import PerformanceMetrics, compute_performance_metrics
from backend.app.backtesting.strategy.base import Strategy
from backend.app.backtesting.types import FLAT_POSITION, BacktestResult, BacktestRun, EquityObservation
from backend.app.backtesting.validation.partitions import DatePartition
from shared.models.candle import Candle

StrategyFactory = Callable[[Mapping[str, StrategyParameterValue]], Strategy]
ParameterSelector = Callable[[Sequence[Candle]], Mapping[str, StrategyParameterValue]]


@dataclass(frozen=True, slots=True)
class WalkForwardWindow:
    """One in-sample/out-of-sample pair.

    ``anchored`` records which style produced this window, since in-sample
    candle selection differs by style: anchored windows legitimately use
    all history up to ``in_sample.end`` (an "expanding window" is defined
    that way), while rolling windows must be strictly bounded to
    ``[in_sample.start, in_sample.end)`` — using any earlier history would
    silently grow a supposedly fixed-length rolling window.
    """

    window_index: int
    in_sample: DatePartition
    out_of_sample: DatePartition
    anchored: bool


@dataclass(frozen=True, slots=True)
class WalkForwardWindowResult:
    """The full outcome of one walk-forward window."""

    window: WalkForwardWindow
    parameters: Mapping[str, StrategyParameterValue]
    in_sample_result: BacktestResult
    in_sample_metrics: PerformanceMetrics
    out_of_sample_result: BacktestResult
    out_of_sample_metrics: PerformanceMetrics


@dataclass(frozen=True, slots=True)
class WalkForwardResult:
    """The full walk-forward run: every window, plus out-of-sample
    performance aggregated across all of them (as if the strategy had
    traded through each out-of-sample period back to back)."""

    windows: tuple[WalkForwardWindowResult, ...]
    aggregate_out_of_sample_metrics: PerformanceMetrics


def generate_walk_forward_windows(
    start: datetime,
    end: datetime,
    *,
    in_sample_duration: timedelta,
    out_of_sample_duration: timedelta,
    anchored: bool = False,
) -> tuple[WalkForwardWindow, ...]:
    """Generate consecutive, non-overlapping in-sample/out-of-sample
    windows covering as much of ``[start, end)`` as fits exactly.

    ``anchored=False`` (default) produces a rolling fixed-length in-sample
    window that slides forward each step. ``anchored=True`` keeps the
    in-sample window's start fixed at ``start`` and lets it grow (an
    "expanding window"), which is the other standard walk-forward style.
    """
    if in_sample_duration <= timedelta(0) or out_of_sample_duration <= timedelta(0):
        raise InvalidPartitionError("in_sample_duration and out_of_sample_duration must be positive")
    if start.tzinfo is None or end.tzinfo is None:
        raise InvalidPartitionError("generate_walk_forward_windows: start/end must be timezone-aware")

    windows: list[WalkForwardWindow] = []
    in_sample_start = start
    out_of_sample_start = start + in_sample_duration

    while out_of_sample_start + out_of_sample_duration <= end:
        out_of_sample_end = out_of_sample_start + out_of_sample_duration
        in_sample = DatePartition("in_sample", in_sample_start, out_of_sample_start)
        out_of_sample = DatePartition("out_of_sample", out_of_sample_start, out_of_sample_end)
        windows.append(
            WalkForwardWindow(
                window_index=len(windows), in_sample=in_sample, out_of_sample=out_of_sample, anchored=anchored
            )
        )

        if not anchored:
            in_sample_start = in_sample_start + out_of_sample_duration
        out_of_sample_start = out_of_sample_end

    if not windows:
        raise InvalidPartitionError(
            "no walk-forward windows fit within the given start/end and durations"
        )
    return tuple(windows)


def _candles_before(candles: Sequence[Candle], end: datetime, *, floor: datetime | None = None) -> list[Candle]:
    """Candles strictly before ``end``. When ``floor`` is given, also
    excludes anything before it — used to keep a rolling window's
    parameter selection and both its backtests from reaching back into
    history the window is not supposed to see (see ``WalkForwardWindow``)."""
    if floor is None:
        return [candle for candle in candles if candle.timestamp < end]
    return [candle for candle in candles if floor <= candle.timestamp < end]


def _window_floor(window: WalkForwardWindow) -> datetime | None:
    """``None`` for anchored windows (full history back to the true start
    is the intended behavior). For rolling windows, the window's own
    in-sample start — never look further back than that, or the window
    silently stops being "rolling"."""
    return None if window.anchored else window.in_sample.start


def _run_partition(
    base_config: BacktestConfig,
    candles: Sequence[Candle],
    partition: DatePartition,
    parameters: Mapping[str, StrategyParameterValue],
    strategy_factory: StrategyFactory,
    clock: Callable[[], datetime],
    *,
    floor: datetime | None = None,
) -> BacktestResult:
    partition_candles = _candles_before(candles, partition.end, floor=floor)
    config = replace(base_config, start=partition.start, end=partition.end, parameters=parameters)
    engine = BacktestEngine(config, partition_candles, clock=clock)
    return engine.run_strategy(strategy_factory(parameters))


def _chain_out_of_sample_equity(
    results: Sequence[BacktestResult], initial_capital: Decimal
) -> tuple[EquityObservation, ...]:
    """Rescale each window's out-of-sample equity curve to continue
    compounding from where the previous window's left off, producing a
    single continuous curve — as opposed to naively concatenating raw
    equity values, which would show a fake jump back to initial_capital at
    every window boundary."""
    chained: list[EquityObservation] = []
    running_capital = initial_capital
    for result in results:
        curve = result.equity_curve
        if not curve:
            continue
        window_initial = result.config.initial_capital
        for observation in curve:
            scaled_equity = running_capital * (observation.equity / window_initial)
            chained.append(
                EquityObservation(
                    timestamp=observation.timestamp,
                    equity=scaled_equity,
                    cash=scaled_equity,
                    position=observation.position,
                )
            )
        running_capital = running_capital * (curve[-1].equity / window_initial)
    return tuple(chained)


def run_walk_forward(
    windows: Sequence[WalkForwardWindow],
    *,
    base_config: BacktestConfig,
    candles: Sequence[Candle],
    strategy_factory: StrategyFactory,
    select_parameters: ParameterSelector,
    clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
) -> WalkForwardResult:
    """Run every window: select parameters from in-sample data only, run
    the in-sample backtest with them (for reporting), then run the
    out-of-sample backtest with the *same frozen* parameters.

    ``clock`` is threaded through to every underlying ``BacktestEngine`` —
    inject a fixed clock for reproducible/testable runs, since the default
    real-time clock only ever affects metadata (``generated_at``), never a
    computed result, but does affect dataclass equality between two runs.
    """
    window_results: list[WalkForwardWindowResult] = []

    for window in windows:
        floor = _window_floor(window)
        in_sample_candles = _candles_before(candles, window.in_sample.end, floor=floor)
        parameters = select_parameters(in_sample_candles)

        in_sample_result = _run_partition(
            base_config, candles, window.in_sample, parameters, strategy_factory, clock, floor=floor
        )
        out_of_sample_result = _run_partition(
            base_config, candles, window.out_of_sample, parameters, strategy_factory, clock, floor=floor
        )

        window_results.append(
            WalkForwardWindowResult(
                window=window,
                parameters=parameters,
                in_sample_result=in_sample_result,
                in_sample_metrics=compute_performance_metrics(in_sample_result),
                out_of_sample_result=out_of_sample_result,
                out_of_sample_metrics=compute_performance_metrics(out_of_sample_result),
            )
        )

    chained_equity = _chain_out_of_sample_equity(
        [wr.out_of_sample_result for wr in window_results], base_config.initial_capital
    )
    all_out_of_sample_trades = tuple(
        trade for wr in window_results for trade in wr.out_of_sample_result.trades
    )
    aggregate_run = BacktestRun(
        config=base_config, run_id="walk-forward-aggregate-oos", generated_at=base_config.start
    )
    aggregate_result = BacktestResult(
        run=aggregate_run,
        equity_curve=chained_equity,
        trades=all_out_of_sample_trades,
        final_position=FLAT_POSITION,
    )

    return WalkForwardResult(
        windows=tuple(window_results),
        aggregate_out_of_sample_metrics=compute_performance_metrics(aggregate_result),
    )
