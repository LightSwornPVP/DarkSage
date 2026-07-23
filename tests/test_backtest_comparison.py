"""Tests for the experiment comparison/ranking foundation: fair comparison
on one explicit metric, safe handling of undefined metrics, small-sample
warnings, reproducibility metadata retention, and deterministic ranking."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from backend.app.backtesting.comparison import (
    ExperimentEntry,
    ExperimentRegistry,
    build_comparison_table,
    compare_experiments,
    compare_two,
)
from backend.app.backtesting.config import BacktestConfig
from backend.app.backtesting.metrics import compute_performance_metrics
from backend.app.backtesting.types import FLAT_POSITION, BacktestResult, BacktestRun, EquityObservation
from shared.models.candle import Timeframe

START = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _config(strategy_id: str, **overrides: object) -> BacktestConfig:
    fields: dict[str, object] = dict(
        strategy_id=strategy_id,
        strategy_version="1.0.0",
        symbol="AAPL",
        timeframe=Timeframe.D1,
        start=START,
        end=START + timedelta(days=100),
        initial_capital=Decimal(10000),
        reproducibility_id=f"repro-{strategy_id}",
    )
    fields.update(overrides)
    return BacktestConfig(**fields)  # type: ignore[arg-type]


def _entry(name: str, ending_equity: str, *, num_observations: int = 2) -> ExperimentEntry:
    config = _config(name)
    run = BacktestRun(config=config, run_id=f"run-{name}", generated_at=START)
    equity_curve = tuple(
        EquityObservation(
            timestamp=START + timedelta(days=i),
            equity=Decimal(10000) if i < num_observations - 1 else Decimal(ending_equity),
            cash=Decimal(10000),
            position=FLAT_POSITION,
        )
        for i in range(num_observations)
    )
    result = BacktestResult(run=run, equity_curve=equity_curve, trades=(), final_position=FLAT_POSITION)
    return ExperimentEntry(name=name, result=result, metrics=compute_performance_metrics(result))


# --- Registry basics ---


def test_registry_rejects_duplicate_names() -> None:
    with pytest.raises(ValueError):
        ExperimentRegistry(entries=(_entry("a", "11000"), _entry("a", "9000")))


def test_registry_get_returns_matching_entry() -> None:
    entry_a = _entry("a", "11000")
    registry = ExperimentRegistry(entries=(entry_a, _entry("b", "9000")))
    assert registry.get("a") is entry_a


def test_registry_get_unknown_name_raises() -> None:
    registry = ExperimentRegistry(entries=(_entry("a", "11000"),))
    with pytest.raises(KeyError):
        registry.get("nonexistent")


# --- Fair, explicit-metric comparison ---


def test_compare_experiments_ranks_by_explicit_metric_higher_is_better() -> None:
    registry = ExperimentRegistry(
        entries=(_entry("low", "10500"), _entry("high", "12000"), _entry("mid", "11000"))
    )
    result = compare_experiments(registry, metric_name="total_return", higher_is_better=True)
    assert [r.name for r in result.ranked] == ["high", "mid", "low"]
    assert [r.rank for r in result.ranked] == [1, 2, 3]


def test_compare_experiments_ranks_lower_is_better_when_requested() -> None:
    registry = ExperimentRegistry(entries=(_entry("low", "10500"), _entry("high", "12000")))
    result = compare_experiments(registry, metric_name="total_return", higher_is_better=False)
    assert [r.name for r in result.ranked] == ["low", "high"]


def test_compare_experiments_rejects_unknown_metric_name() -> None:
    registry = ExperimentRegistry(entries=(_entry("a", "11000"),))
    with pytest.raises(ValueError):
        compare_experiments(registry, metric_name="not_a_real_metric")


# --- Undefined metrics handled safely (never treated as zero or a win) ---


def test_compare_experiments_sorts_undefined_metric_last() -> None:
    # A single equity observation leaves cagr undefined (None).
    registry = ExperimentRegistry(
        entries=(_entry("has_cagr", "11000"), _entry("no_cagr", "9000", num_observations=1))
    )
    result = compare_experiments(registry, metric_name="cagr")
    assert result.ranked[-1].name == "no_cagr"
    assert result.ranked[-1].metric_value is None


def test_compare_experiments_all_undefined_breaks_ties_by_name() -> None:
    registry = ExperimentRegistry(
        entries=(
            _entry("zebra", "9000", num_observations=1),
            _entry("alpha", "9000", num_observations=1),
        )
    )
    result = compare_experiments(registry, metric_name="cagr")
    assert [r.name for r in result.ranked] == ["alpha", "zebra"]


# --- Small-sample warning ---


def test_compare_experiments_flags_small_sample() -> None:
    registry = ExperimentRegistry(entries=(_entry("a", "11000"),))  # 0 trades < default min_sample_size
    result = compare_experiments(registry, metric_name="total_return", min_sample_size=20)
    assert result.ranked[0].small_sample_warning is True


# --- Reproducibility metadata retained ---


def test_comparison_table_retains_reproducibility_metadata() -> None:
    registry = ExperimentRegistry(entries=(_entry("a", "11000"),))
    table = build_comparison_table(registry)
    assert table[0].strategy_id == "a"
    assert table[0].strategy_version == "1.0.0"
    assert table[0].run_id == "run-a"
    # The full config (including reproducibility_id) is still reachable via the entry itself.
    assert registry.get("a").result.run.config.reproducibility_id == "repro-a"


# --- Deterministic ranking ---


def test_compare_experiments_is_deterministic() -> None:
    registry = ExperimentRegistry(entries=(_entry("a", "11000"), _entry("b", "12000"), _entry("c", "9000")))
    result_a = compare_experiments(registry, metric_name="total_return")
    result_b = compare_experiments(registry, metric_name="total_return")
    assert result_a == result_b


def test_compare_experiments_ties_break_by_name_deterministically() -> None:
    registry = ExperimentRegistry(entries=(_entry("zebra", "11000"), _entry("alpha", "11000")))
    result = compare_experiments(registry, metric_name="total_return")
    assert [r.name for r in result.ranked] == ["alpha", "zebra"]


# --- Champion vs challenger convenience ---


def test_compare_two_is_equivalent_to_two_entry_registry() -> None:
    champion = _entry("champion", "11000")
    challenger = _entry("challenger", "13000")
    result = compare_two(champion, challenger, metric_name="total_return")
    assert [r.name for r in result.ranked] == ["challenger", "champion"]
