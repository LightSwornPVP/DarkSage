"""Tests for the backtest domain/engine foundation: config validation,
history validation, deterministic no-lookahead iteration, and the trivial
end-to-end run."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from backend.app.backtesting.config import BacktestConfig, CostConfig
from backend.app.backtesting.engine import (
    BacktestEngine,
    compute_run_id,
    iter_backtest_steps,
    validate_backtest_history,
)
from backend.app.backtesting.errors import (
    InsufficientHistoryError,
    InvalidBacktestConfigError,
    InvalidExecutionConfigError,
    InvalidHistoryError,
)
from shared.models.candle import Candle, Timeframe

START = datetime(2026, 1, 1, tzinfo=timezone.utc)
END = datetime(2026, 2, 1, tzinfo=timezone.utc)


def _candle(day_offset: int, close: str, *, symbol: str = "AAPL", timeframe: Timeframe = Timeframe.D1) -> Candle:
    price = Decimal(close)
    return Candle(
        symbol=symbol,
        timeframe=timeframe,
        timestamp=START + timedelta(days=day_offset),
        open=price,
        high=price + 1,
        low=price - 1,
        close=price,
        volume=Decimal(1000),
    )


def _config(**overrides: object) -> BacktestConfig:
    fields: dict[str, object] = dict(
        strategy_id="test-strategy",
        strategy_version="1.0.0",
        symbol="AAPL",
        timeframe=Timeframe.D1,
        start=START,
        end=END,
        initial_capital=Decimal(10000),
    )
    fields.update(overrides)
    return BacktestConfig(**fields)  # type: ignore[arg-type]


def _candles(n: int, start_offset: int = 0) -> list[Candle]:
    return [_candle(start_offset + i, str(100 + i)) for i in range(n)]


# --- BacktestConfig validation ---


def test_config_accepts_valid_values() -> None:
    config = _config()
    assert config.symbol == "AAPL"


def test_config_rejects_end_before_start() -> None:
    with pytest.raises(InvalidBacktestConfigError):
        _config(start=END, end=START)


def test_config_rejects_naive_start() -> None:
    with pytest.raises(InvalidBacktestConfigError):
        _config(start=datetime(2026, 1, 1))


def test_config_rejects_non_positive_capital() -> None:
    with pytest.raises(InvalidBacktestConfigError):
        _config(initial_capital=Decimal(0))


def test_config_rejects_blank_strategy_id() -> None:
    with pytest.raises(InvalidBacktestConfigError):
        _config(strategy_id="  ")


def test_cost_config_rejects_negative_commission() -> None:
    with pytest.raises(InvalidExecutionConfigError):
        CostConfig(commission_rate=Decimal("-0.01"))


# --- History validation ---


def test_validate_history_rejects_empty() -> None:
    with pytest.raises(InvalidHistoryError):
        validate_backtest_history([], _config())


def test_validate_history_rejects_mixed_symbol() -> None:
    candles = [_candle(0, "100", symbol="AAPL"), _candle(1, "101", symbol="MSFT")]
    with pytest.raises(InvalidHistoryError):
        validate_backtest_history(candles, _config())


def test_validate_history_rejects_mixed_timeframe() -> None:
    candles = [_candle(0, "100", timeframe=Timeframe.D1), _candle(1, "101", timeframe=Timeframe.H1)]
    with pytest.raises(InvalidHistoryError):
        validate_backtest_history(candles, _config())


def test_validate_history_rejects_non_increasing_timestamps() -> None:
    candles = [_candle(1, "100"), _candle(0, "101")]
    with pytest.raises(InvalidHistoryError):
        validate_backtest_history(candles, _config())


def test_validate_history_rejects_candles_beyond_end() -> None:
    candles = _candles(5) + [_candle(400, "999")]  # far beyond configured end
    with pytest.raises(InvalidHistoryError):
        validate_backtest_history(candles, _config())


def test_validate_history_rejects_history_entirely_before_start() -> None:
    candles = [_candle(-100 + i, str(100 + i)) for i in range(3)]  # all before START
    with pytest.raises(InsufficientHistoryError):
        validate_backtest_history(candles, _config())


def test_validate_history_allows_warmup_candles_before_start() -> None:
    warmup = [_candle(-5 + i, str(90 + i)) for i in range(5)]  # before START, for indicator warmup
    active = _candles(5)
    validate_backtest_history(warmup + active, _config())  # must not raise


# --- No-lookahead iteration ---


def test_iter_backtest_steps_visible_candles_never_include_future() -> None:
    candles = _candles(5)
    config = _config()
    for step in iter_backtest_steps(candles, config):
        assert step.visible_candles == tuple(candles[: step.index + 1])
        assert step.candle == candles[step.index]
        visible_timestamps = {c.timestamp for c in step.visible_candles}
        future_timestamps = {c.timestamp for c in candles[step.index + 1 :]}
        assert visible_timestamps.isdisjoint(future_timestamps)


def test_iter_backtest_steps_is_chronologically_ordered() -> None:
    candles = _candles(5)
    steps = list(iter_backtest_steps(candles, _config()))
    timestamps = [step.candle.timestamp for step in steps]
    assert timestamps == sorted(timestamps)
    assert [step.index for step in steps] == list(range(5))


def test_iter_backtest_steps_marks_warmup_candles_inactive() -> None:
    warmup = [_candle(-2 + i, str(90 + i)) for i in range(2)]
    active = _candles(3)
    steps = list(iter_backtest_steps(warmup + active, _config()))
    assert [step.is_active for step in steps] == [False, False, True, True, True]


# --- Determinism ---


def test_compute_run_id_is_deterministic_for_identical_config() -> None:
    config_a = _config()
    config_b = _config()
    assert compute_run_id(config_a) == compute_run_id(config_b)


def test_compute_run_id_differs_for_different_parameters() -> None:
    config_a = _config(parameters={"fast": 10})
    config_b = _config(parameters={"fast": 20})
    assert compute_run_id(config_a) != compute_run_id(config_b)


def test_engine_run_is_deterministic_for_same_inputs() -> None:
    candles = _candles(10)

    def fixed_clock() -> datetime:
        return datetime(2026, 6, 1, tzinfo=timezone.utc)

    engine_a = BacktestEngine(_config(), candles, clock=fixed_clock)
    engine_b = BacktestEngine(_config(), candles, clock=fixed_clock)

    result_a = engine_a.run()
    result_b = engine_b.run()

    assert result_a == result_b
    assert result_a.run.run_id == result_b.run.run_id


def test_engine_run_flat_equity_curve_matches_initial_capital() -> None:
    candles = _candles(5)
    engine = BacktestEngine(_config(), candles)
    result = engine.run()

    assert len(result.equity_curve) == 5
    assert all(obs.equity == Decimal(10000) for obs in result.equity_curve)
    assert result.trades == ()
    assert result.final_position.is_flat


def test_engine_constructor_rejects_invalid_history() -> None:
    with pytest.raises(InvalidHistoryError):
        BacktestEngine(_config(), [])
