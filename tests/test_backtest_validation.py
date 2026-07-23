"""Tests for date partitioning and walk-forward validation: no temporal
leakage, deterministic partitioning, and rejecting invalid overlaps."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from backend.app.backtesting.config import BacktestConfig
from backend.app.backtesting.errors import InvalidPartitionError
from backend.app.backtesting.strategy.base import Strategy
from backend.app.backtesting.strategy.reference import MovingAverageCrossoverStrategy
from backend.app.backtesting.validation.partitions import DatePartition, split_periods, validate_no_overlap
from backend.app.backtesting.validation.walkforward import (
    generate_walk_forward_windows,
    run_walk_forward,
)
from shared.models.candle import Candle, Timeframe

START = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _candle(day_offset: int, close: str) -> Candle:
    price = Decimal(close)
    return Candle(
        symbol="AAPL",
        timeframe=Timeframe.D1,
        timestamp=START + timedelta(days=day_offset),
        open=price,
        high=price + 1,
        low=price - 1,
        close=price,
        volume=Decimal(1000),
    )


# --- DatePartition / split_periods ---


def test_date_partition_rejects_end_before_start() -> None:
    with pytest.raises(InvalidPartitionError):
        DatePartition("x", START + timedelta(days=1), START)


def test_date_partition_contains_is_half_open() -> None:
    partition = DatePartition("x", START, START + timedelta(days=1))
    assert partition.contains(START) is True
    assert partition.contains(START + timedelta(days=1)) is False  # end is exclusive


def test_split_periods_is_deterministic_and_covers_the_full_range() -> None:
    end = START + timedelta(days=100)
    fractions = {"train": Decimal("0.6"), "test": Decimal("0.4")}

    partitions_a = split_periods(START, end, fractions)
    partitions_b = split_periods(START, end, fractions)

    assert partitions_a == partitions_b
    assert partitions_a[0].start == START
    assert partitions_a[-1].end == end
    assert partitions_a[0].end == partitions_a[1].start  # contiguous, no gap or overlap


def test_split_periods_rejects_fractions_not_summing_to_one() -> None:
    with pytest.raises(InvalidPartitionError):
        split_periods(START, START + timedelta(days=10), {"train": Decimal("0.5"), "test": Decimal("0.4")})


def test_split_periods_three_way_train_validation_test() -> None:
    end = START + timedelta(days=100)
    fractions = {"train": Decimal("0.6"), "validation": Decimal("0.2"), "test": Decimal("0.2")}
    partitions = split_periods(START, end, fractions)
    assert [p.label for p in partitions] == ["train", "validation", "test"]
    assert partitions[-1].end == end


def test_validate_no_overlap_rejects_overlapping_partitions() -> None:
    overlapping = (
        DatePartition("a", START, START + timedelta(days=10)),
        DatePartition("b", START + timedelta(days=5), START + timedelta(days=15)),
    )
    with pytest.raises(InvalidPartitionError):
        validate_no_overlap(overlapping)


def test_validate_no_overlap_accepts_contiguous_partitions() -> None:
    contiguous = (
        DatePartition("a", START, START + timedelta(days=10)),
        DatePartition("b", START + timedelta(days=10), START + timedelta(days=20)),
    )
    validate_no_overlap(contiguous)  # must not raise


# --- Walk-forward window generation ---


def test_generate_windows_rolling_slides_in_sample_start() -> None:
    windows = generate_walk_forward_windows(
        START,
        START + timedelta(days=40),
        in_sample_duration=timedelta(days=20),
        out_of_sample_duration=timedelta(days=10),
        anchored=False,
    )
    assert len(windows) == 2
    assert windows[0].in_sample.start == START
    assert windows[1].in_sample.start == START + timedelta(days=10)  # slid forward
    assert windows[0].out_of_sample.end == windows[1].in_sample.end  # contiguous


def test_generate_windows_anchored_keeps_in_sample_start_fixed() -> None:
    windows = generate_walk_forward_windows(
        START,
        START + timedelta(days=40),
        in_sample_duration=timedelta(days=20),
        out_of_sample_duration=timedelta(days=10),
        anchored=True,
    )
    assert len(windows) == 2
    assert windows[0].in_sample.start == START
    assert windows[1].in_sample.start == START  # fixed anchor
    assert windows[1].in_sample.end > windows[0].in_sample.end  # expanding window


def test_generate_windows_no_overlap_between_in_sample_and_out_of_sample() -> None:
    windows = generate_walk_forward_windows(
        START,
        START + timedelta(days=40),
        in_sample_duration=timedelta(days=20),
        out_of_sample_duration=timedelta(days=10),
    )
    for window in windows:
        validate_no_overlap([window.in_sample, window.out_of_sample])  # must not raise
        assert window.in_sample.end == window.out_of_sample.start


def test_generate_windows_raises_when_none_fit() -> None:
    with pytest.raises(InvalidPartitionError):
        generate_walk_forward_windows(
            START,
            START + timedelta(days=5),
            in_sample_duration=timedelta(days=20),
            out_of_sample_duration=timedelta(days=10),
        )


def test_generate_windows_is_deterministic() -> None:
    kwargs = dict(
        start=START,
        end=START + timedelta(days=100),
        in_sample_duration=timedelta(days=30),
        out_of_sample_duration=timedelta(days=15),
    )
    windows_a = generate_walk_forward_windows(**kwargs)  # type: ignore[arg-type]
    windows_b = generate_walk_forward_windows(**kwargs)  # type: ignore[arg-type]
    assert windows_a == windows_b


# --- run_walk_forward: no leakage, frozen parameters ---


class _RecordingSelector:
    """Records exactly which candles it was shown, to prove no leakage."""

    def __init__(self) -> None:
        self.calls: list[tuple[datetime, datetime]] = []

    def __call__(self, candles: list[Candle]) -> dict[str, object]:
        if candles:
            self.calls.append((candles[0].timestamp, candles[-1].timestamp))
        return {"fast_period": 3, "slow_period": 5}


def _crossover_candles(n: int) -> list[Candle]:
    flat = [100] * 8
    up = list(range(101, 116))
    down = list(range(114, 89, -1))
    prices = (flat + up + down) * ((n // len(flat + up + down)) + 1)
    return [_candle(i, str(prices[i])) for i in range(n)]


def _base_config(end_offset: int) -> BacktestConfig:
    return BacktestConfig(
        strategy_id="reference-ma-crossover",
        strategy_version="1.0.0",
        symbol="AAPL",
        timeframe=Timeframe.D1,
        start=START,
        end=START + timedelta(days=end_offset),
        initial_capital=Decimal(10000),
    )


def _make_strategy_factory() -> object:
    def strategy_factory(params: object) -> Strategy:
        assert isinstance(params, dict)
        return MovingAverageCrossoverStrategy(
            fast_period=int(params["fast_period"]), slow_period=int(params["slow_period"])
        )

    return strategy_factory


def test_walk_forward_parameter_selection_never_sees_out_of_sample_candles() -> None:
    candles = _crossover_candles(80)
    windows = generate_walk_forward_windows(
        START,
        START + timedelta(days=80),
        in_sample_duration=timedelta(days=40),
        out_of_sample_duration=timedelta(days=20),
    )
    selector = _RecordingSelector()

    result = run_walk_forward(
        windows,
        base_config=_base_config(80),
        candles=candles,
        strategy_factory=_make_strategy_factory(),  # type: ignore[arg-type]
        select_parameters=selector,
    )

    assert len(result.windows) == len(windows)
    for window, (first_seen, last_seen) in zip(windows, selector.calls, strict=True):
        assert last_seen < window.in_sample.end  # never saw a candle at/after in-sample end
        assert last_seen < window.out_of_sample.start  # therefore never saw any out-of-sample candle


def test_walk_forward_uses_same_frozen_parameters_for_in_and_out_of_sample() -> None:
    candles = _crossover_candles(80)
    windows = generate_walk_forward_windows(
        START,
        START + timedelta(days=80),
        in_sample_duration=timedelta(days=40),
        out_of_sample_duration=timedelta(days=20),
    )

    def select_parameters(candles_slice: list[Candle]) -> dict[str, object]:
        return {"fast_period": 3, "slow_period": 5}

    result = run_walk_forward(
        windows,
        base_config=_base_config(80),
        candles=candles,
        strategy_factory=_make_strategy_factory(),  # type: ignore[arg-type]
        select_parameters=select_parameters,
    )

    for window_result in result.windows:
        assert window_result.in_sample_result.config.parameters == window_result.parameters
        assert window_result.out_of_sample_result.config.parameters == window_result.parameters


def test_walk_forward_is_deterministic() -> None:
    candles = _crossover_candles(80)
    windows = generate_walk_forward_windows(
        START,
        START + timedelta(days=80),
        in_sample_duration=timedelta(days=40),
        out_of_sample_duration=timedelta(days=20),
    )

    def select_parameters(candles_slice: list[Candle]) -> dict[str, object]:
        return {"fast_period": 3, "slow_period": 5}

    def fixed_clock() -> datetime:
        return datetime(2026, 6, 1, tzinfo=timezone.utc)

    result_a = run_walk_forward(
        windows,
        base_config=_base_config(80),
        candles=candles,
        strategy_factory=_make_strategy_factory(),  # type: ignore[arg-type]
        select_parameters=select_parameters,
        clock=fixed_clock,
    )
    result_b = run_walk_forward(
        windows,
        base_config=_base_config(80),
        candles=candles,
        strategy_factory=_make_strategy_factory(),  # type: ignore[arg-type]
        select_parameters=select_parameters,
        clock=fixed_clock,
    )

    assert result_a == result_b
    assert result_a.aggregate_out_of_sample_metrics == result_b.aggregate_out_of_sample_metrics


def test_walk_forward_aggregate_combines_all_out_of_sample_trades() -> None:
    candles = _crossover_candles(80)
    windows = generate_walk_forward_windows(
        START,
        START + timedelta(days=80),
        in_sample_duration=timedelta(days=40),
        out_of_sample_duration=timedelta(days=20),
    )

    def select_parameters(candles_slice: list[Candle]) -> dict[str, object]:
        return {"fast_period": 3, "slow_period": 5}

    result = run_walk_forward(
        windows,
        base_config=_base_config(80),
        candles=candles,
        strategy_factory=_make_strategy_factory(),  # type: ignore[arg-type]
        select_parameters=select_parameters,
    )

    expected_trade_count = sum(len(wr.out_of_sample_result.trades) for wr in result.windows)
    assert result.aggregate_out_of_sample_metrics.num_trades == expected_trade_count
