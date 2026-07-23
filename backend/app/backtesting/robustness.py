"""Deterministic, seeded robustness analysis: Monte Carlo resampling of
historical trades, and a parameter-stability testing foundation.

Neither of these is a forecast. Monte Carlo here answers "how sensitive was
this specific historical result to the order trades happened to occur in?"
— it reorders/resamples the *same* historical trade outcomes, it does not
simulate new, unseen market scenarios, and it makes no claim about future
probability. Parameter stability answers "how much does performance change
across nearby parameter values?" — it never selects or recommends a "best"
parameter set; that judgment call is left to the caller.
"""

from __future__ import annotations

import random
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from decimal import ROUND_CEILING, Decimal
from typing import Literal

from backend.app.backtesting.config import StrategyParameterValue
from backend.app.backtesting.errors import InsufficientSampleSizeError
from backend.app.backtesting.metrics import PerformanceMetrics, compute_performance_metrics, max_drawdown_from_values
from backend.app.backtesting.types import BacktestResult, SimulatedTrade

_DEFAULT_PERCENTILES: tuple[Decimal, ...] = (Decimal(5), Decimal(25), Decimal(50), Decimal(75), Decimal(95))
_DEFAULT_DRAWDOWN_THRESHOLDS: tuple[Decimal, ...] = (Decimal("0.1"), Decimal("0.2"), Decimal("0.3"))

ResamplingMethod = Literal["reshuffle", "bootstrap"]


@dataclass(frozen=True, slots=True)
class MonteCarloConfig:
    """Configuration for one Monte Carlo run — part of that run's
    reproducibility record alongside the random seed."""

    num_simulations: int = 1000
    random_seed: int = 0
    min_trades_required: int = 20
    method: ResamplingMethod = "reshuffle"

    def __post_init__(self) -> None:
        if self.num_simulations < 1:
            raise ValueError("num_simulations must be >= 1")
        if self.min_trades_required < 2:
            raise ValueError("min_trades_required must be >= 2")


@dataclass(frozen=True, slots=True)
class MonteCarloResult:
    """Distributional summary from resampling a fixed set of historical
    trades. See the module docstring for what this does and does not claim."""

    num_simulations: int
    random_seed: int
    method: ResamplingMethod
    ending_equity_percentiles: Mapping[str, Decimal]
    max_drawdown_percentiles: Mapping[str, Decimal]
    probability_of_drawdown_exceeding: Mapping[str, Decimal]
    assumptions: tuple[str, ...] = field(default_factory=tuple)


def _percentile(sorted_values: Sequence[Decimal], percentile: Decimal) -> Decimal:
    """Nearest-rank percentile: deterministic, no interpolation ambiguity."""
    count = len(sorted_values)
    rank = int((percentile / Decimal(100) * Decimal(count)).to_integral_value(rounding=ROUND_CEILING))
    index = min(max(rank, 1), count) - 1
    return sorted_values[index]


def _equity_path(trades: Sequence[SimulatedTrade], initial_capital: Decimal) -> list[Decimal]:
    equity = initial_capital
    path = [equity]
    for trade in trades:
        equity += trade.pnl
        path.append(equity)
    return path


def run_monte_carlo(
    trades: Sequence[SimulatedTrade],
    *,
    initial_capital: Decimal,
    config: MonteCarloConfig = MonteCarloConfig(),
    drawdown_thresholds: Sequence[Decimal] = _DEFAULT_DRAWDOWN_THRESHOLDS,
    percentiles: Sequence[Decimal] = _DEFAULT_PERCENTILES,
) -> MonteCarloResult:
    """Resample ``trades`` (by ``config.method``) ``config.num_simulations``
    times, tracking each resulting equity path's ending value and maximum
    drawdown. Deterministic: the same trades + config always produce the
    same result, since ``random.Random(config.random_seed)`` is consumed in
    a fixed order.
    """
    if len(trades) < config.min_trades_required:
        raise InsufficientSampleSizeError(
            f"Monte Carlo simulation requires at least {config.min_trades_required} trades, "
            f"got {len(trades)} — a smaller sample would fabricate false confidence"
        )

    rng = random.Random(config.random_seed)
    trades_list = list(trades)
    ending_equities: list[Decimal] = []
    max_drawdowns: list[Decimal] = []

    for _ in range(config.num_simulations):
        if config.method == "reshuffle":
            order = trades_list[:]
            rng.shuffle(order)
        elif config.method == "bootstrap":
            order = rng.choices(trades_list, k=len(trades_list))
        else:
            raise ValueError(f"unrecognized resampling method: {config.method}")

        path = _equity_path(order, initial_capital)
        ending_equities.append(path[-1])
        max_drawdowns.append(max_drawdown_from_values(path))

    ending_equities.sort()
    max_drawdowns.sort()

    ending_equity_percentiles = {f"p{p}": _percentile(ending_equities, p) for p in percentiles}
    max_drawdown_percentiles = {f"p{p}": _percentile(max_drawdowns, p) for p in percentiles}
    probability_of_drawdown_exceeding = {
        str(threshold): Decimal(sum(1 for dd in max_drawdowns if dd >= threshold)) / Decimal(len(max_drawdowns))
        for threshold in drawdown_thresholds
    }

    assumptions = (
        "Trade PnL values are reordered/resampled from the same historical trade set; this models "
        "sequencing/sampling risk only, not new or unseen market scenarios.",
        "This is not a forecast or a guarantee of future performance — it describes only how "
        "sensitive the historical result was to trade order/sampling.",
        f"Resampling method: {config.method}.",
    )

    return MonteCarloResult(
        num_simulations=config.num_simulations,
        random_seed=config.random_seed,
        method=config.method,
        ending_equity_percentiles=ending_equity_percentiles,
        max_drawdown_percentiles=max_drawdown_percentiles,
        probability_of_drawdown_exceeding=probability_of_drawdown_exceeding,
        assumptions=assumptions,
    )


@dataclass(frozen=True, slots=True)
class ParameterStabilityPoint:
    """One tested point in parameter space and its resulting metrics."""

    parameters: Mapping[str, StrategyParameterValue]
    metrics: PerformanceMetrics


@dataclass(frozen=True, slots=True)
class ParameterStabilityResult:
    """A neighborhood of tested parameter combinations. Deliberately has no
    "best parameters" field or method — identifying a winner from this data
    is a judgment call for the caller, not an automated claim this type
    makes for them."""

    points: tuple[ParameterStabilityPoint, ...]

    def metric_values(self, metric_name: str) -> tuple[Decimal | None, ...]:
        return tuple(getattr(point.metrics, metric_name) for point in self.points)


def run_parameter_stability(
    parameter_grid: Sequence[Mapping[str, StrategyParameterValue]],
    *,
    run_backtest: Callable[[Mapping[str, StrategyParameterValue]], BacktestResult],
) -> ParameterStabilityResult:
    """Run one backtest per entry in ``parameter_grid`` (e.g. neighboring
    values around a chosen parameter set) and collect their metrics."""
    if not parameter_grid:
        raise ValueError("parameter_grid must not be empty")
    points = tuple(
        ParameterStabilityPoint(parameters=params, metrics=compute_performance_metrics(run_backtest(params)))
        for params in parameter_grid
    )
    return ParameterStabilityResult(points=points)


def assess_stability(result: ParameterStabilityResult, metric_name: str) -> Decimal | None:
    """A simple stability score for one metric across the tested
    neighborhood: ``1 - coefficient_of_variation``. Closer to 1 means the
    metric stays broadly similar across nearby parameters (a "broad stable
    region"); a low or negative score flags a brittle result that swings
    heavily with small parameter changes.

    Returns ``None`` when the metric is undefined for enough points, or the
    mean is zero, to make the coefficient of variation itself undefined —
    never a fabricated stability score.
    """
    values = [value for value in result.metric_values(metric_name) if value is not None]
    if len(values) < 2:
        return None
    mean = sum(values, start=Decimal(0)) / Decimal(len(values))
    if mean == 0:
        return None
    variance = sum(((value - mean) ** 2 for value in values), start=Decimal(0)) / Decimal(len(values) - 1)
    coefficient_of_variation = variance.sqrt() / abs(mean)
    return Decimal(1) - coefficient_of_variation
