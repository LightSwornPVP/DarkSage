"""Deterministic Strategy Lab comparison: register multiple backtest
results and rank them on one explicitly chosen metric at a time.

There is no default ranking metric and no composite "quality score" —
``win_rate`` alone must never stand in for strategy quality (see
``metrics.py``), so callers must name exactly which metric they want to
rank by. This module also does not implement live promotion or
Auto-Trader strategy promotion; it only builds the comparison/ranking
primitives that a future champion-vs-challenger or tournament workflow
would sit on top of.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from backend.app.backtesting.metrics import PerformanceMetrics
from backend.app.backtesting.robustness import MonteCarloResult
from backend.app.backtesting.types import BacktestResult


@dataclass(frozen=True, slots=True)
class ExperimentEntry:
    """One named, fully-reproducible result registered for comparison.

    Reproducibility metadata (strategy id/version, parameters, data source,
    seed, ...) is never duplicated here — it is preserved by reference
    through ``result.run.config``.
    """

    name: str
    result: BacktestResult
    metrics: PerformanceMetrics
    robustness: MonteCarloResult | None = None

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("ExperimentEntry.name must not be blank")


@dataclass(frozen=True, slots=True)
class ExperimentRegistry:
    """A fixed set of experiments to compare, keyed by unique name."""

    entries: tuple[ExperimentEntry, ...]

    def __post_init__(self) -> None:
        names = [entry.name for entry in self.entries]
        if len(names) != len(set(names)):
            raise ValueError(f"duplicate experiment names: {sorted({n for n in names if names.count(n) > 1})}")

    def get(self, name: str) -> ExperimentEntry:
        for entry in self.entries:
            if entry.name == name:
                return entry
        raise KeyError(f"no experiment registered under name '{name}'")


@dataclass(frozen=True, slots=True)
class RankedEntry:
    """One experiment's position in a single-metric ranking."""

    rank: int
    name: str
    metric_value: Decimal | None
    small_sample_warning: bool


@dataclass(frozen=True, slots=True)
class ComparisonResult:
    """The outcome of ranking an ``ExperimentRegistry`` by one metric."""

    metric_name: str
    higher_is_better: bool
    min_sample_size: int
    ranked: tuple[RankedEntry, ...]


def compare_experiments(
    registry: ExperimentRegistry,
    *,
    metric_name: str,
    higher_is_better: bool = True,
    min_sample_size: int = 20,
) -> ComparisonResult:
    """Rank every entry in ``registry`` by ``metric_name`` alone.

    Entries where the metric is undefined (``None``) always sort last,
    never treated as zero or as a tie-breaker win. Ties, and all entries
    with an undefined metric, are broken deterministically by name. Entries
    with fewer trades than ``min_sample_size`` are still ranked, but
    flagged via ``small_sample_warning`` rather than excluded or silently
    trusted.
    """
    if metric_name not in PerformanceMetrics.__dataclass_fields__:
        raise ValueError(f"'{metric_name}' is not a PerformanceMetrics field")

    candidates: list[tuple[str, Decimal | None, bool]] = [
        (entry.name, getattr(entry.metrics, metric_name), entry.metrics.num_trades < min_sample_size)
        for entry in registry.entries
    ]

    def sort_key(item: tuple[str, Decimal | None, bool]) -> tuple[int, tuple[Decimal, str] | str]:
        name, value, _ = item
        if value is None:
            return (1, name)
        signed = -value if higher_is_better else value
        return (0, (signed, name))

    ordered = sorted(candidates, key=sort_key)
    ranked = tuple(
        RankedEntry(rank=index + 1, name=name, metric_value=value, small_sample_warning=small_sample)
        for index, (name, value, small_sample) in enumerate(ordered)
    )
    return ComparisonResult(
        metric_name=metric_name, higher_is_better=higher_is_better, min_sample_size=min_sample_size, ranked=ranked
    )


def compare_two(
    champion: ExperimentEntry,
    challenger: ExperimentEntry,
    *,
    metric_name: str,
    higher_is_better: bool = True,
    min_sample_size: int = 20,
) -> ComparisonResult:
    """Convenience wrapper for the champion-vs-challenger / A-B case: just
    ``compare_experiments`` over exactly two entries. Produces a ranking
    only — it does not decide or perform any promotion."""
    return compare_experiments(
        ExperimentRegistry(entries=(champion, challenger)),
        metric_name=metric_name,
        higher_is_better=higher_is_better,
        min_sample_size=min_sample_size,
    )


@dataclass(frozen=True, slots=True)
class ComparisonRow:
    """One experiment's standard side-by-side comparison fields."""

    name: str
    strategy_id: str
    strategy_version: str
    run_id: str
    num_trades: int
    total_return: Decimal | None
    max_drawdown: Decimal | None
    expectancy: Decimal | None
    profit_factor: Decimal | None
    sharpe_ratio: Decimal | None
    sortino_ratio: Decimal | None


def build_comparison_table(registry: ExperimentRegistry) -> tuple[ComparisonRow, ...]:
    """A full side-by-side table across every registered experiment, for
    display — not a ranking. Never reduces to a single number."""
    rows = []
    for entry in registry.entries:
        config = entry.result.run.config
        rows.append(
            ComparisonRow(
                name=entry.name,
                strategy_id=config.strategy_id,
                strategy_version=config.strategy_version,
                run_id=entry.result.run.run_id,
                num_trades=entry.metrics.num_trades,
                total_return=entry.metrics.total_return,
                max_drawdown=entry.metrics.max_drawdown,
                expectancy=entry.metrics.expectancy,
                profit_factor=entry.metrics.profit_factor,
                sharpe_ratio=entry.metrics.sharpe_ratio,
                sortino_ratio=entry.metrics.sortino_ratio,
            )
        )
    return tuple(rows)
