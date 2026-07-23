"""Tests for the historical replay foundation: step order, pause/resume,
reset, no future access, determinism, and end-of-data behavior."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from backend.app.backtesting.replay import HistoricalReplay, ReplayState
from backend.app.indicators.engine import IndicatorEngine
from backend.app.indicators.library import SMAIndicator
from backend.app.indicators.registry import IndicatorRegistry
from shared.models.candle import Candle, Timeframe

START = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _candles(n: int) -> list[Candle]:
    return [
        Candle(
            symbol="AAPL",
            timeframe=Timeframe.D1,
            timestamp=START + timedelta(days=i),
            open=Decimal(100 + i),
            high=Decimal(101 + i),
            low=Decimal(99 + i),
            close=Decimal(100 + i),
            volume=Decimal(1000),
        )
        for i in range(n)
    ]


def test_construction_rejects_empty_candles() -> None:
    with pytest.raises(ValueError):
        HistoricalReplay([])


def test_construction_rejects_non_increasing_timestamps() -> None:
    candles = _candles(3)
    with pytest.raises(ValueError):
        HistoricalReplay([candles[1], candles[0], candles[2]])


def test_construction_accepts_homogeneous_single_symbol_single_timeframe() -> None:
    replay = HistoricalReplay(_candles(3))  # must not raise
    assert replay.state is ReplayState.STOPPED


def test_construction_rejects_mixed_symbols() -> None:
    candles = _candles(3)
    mixed = list(candles[:2]) + [candles[2].model_copy(update={"symbol": "MSFT"})]
    with pytest.raises(ValueError):
        HistoricalReplay(mixed)


def test_construction_rejects_mixed_timeframes() -> None:
    candles = _candles(3)
    mixed = list(candles[:2]) + [candles[2].model_copy(update={"timeframe": Timeframe.H1})]
    with pytest.raises(ValueError):
        HistoricalReplay(mixed)


def test_initial_state_is_stopped_with_no_visible_candles() -> None:
    replay = HistoricalReplay(_candles(3))
    assert replay.state is ReplayState.STOPPED
    assert replay.snapshot.current_candle is None
    assert replay.snapshot.visible_candles == ()


# --- Step order ---


def test_step_advances_one_candle_at_a_time_in_order() -> None:
    candles = _candles(5)
    replay = HistoricalReplay(candles)

    for expected_index in range(5):
        snapshot = replay.step()
        assert snapshot.index == expected_index
        assert snapshot.current_candle == candles[expected_index]
        assert snapshot.visible_candles == tuple(candles[: expected_index + 1])


# --- No future access ---


def test_visible_candles_never_include_future_candles() -> None:
    candles = _candles(6)
    replay = HistoricalReplay(candles)
    for _ in range(3):
        replay.step()
    snapshot = replay.snapshot
    future_timestamps = {c.timestamp for c in candles[snapshot.index + 1 :]}
    visible_timestamps = {c.timestamp for c in snapshot.visible_candles}
    assert visible_timestamps.isdisjoint(future_timestamps)


def test_compute_indicator_uses_only_visible_candles() -> None:
    candles = _candles(10)
    replay = HistoricalReplay(candles)
    registry = IndicatorRegistry()
    registry.register(SMAIndicator(3))
    engine = IndicatorEngine(registry)

    for _ in range(3):
        replay.step()  # 3 candles visible: exactly enough for SMA(3)'s warm-up

    result = replay.compute_indicator(engine, "sma_3")
    assert len(result.points) == 1
    current_candle = replay.snapshot.current_candle
    assert current_candle is not None
    assert result.points[0].timestamp == current_candle.timestamp


def test_compute_indicator_before_any_step_raises() -> None:
    replay = HistoricalReplay(_candles(5))
    registry = IndicatorRegistry()
    registry.register(SMAIndicator(3))
    with pytest.raises(ValueError):
        replay.compute_indicator(IndicatorEngine(registry), "sma_3")


# --- Play / pause ---


def test_play_sets_playing_state() -> None:
    replay = HistoricalReplay(_candles(3))
    replay.play()
    assert replay.is_playing() is True
    assert replay.state is ReplayState.PLAYING


def test_step_while_playing_remains_playing() -> None:
    replay = HistoricalReplay(_candles(3))
    replay.play()
    snapshot = replay.step()
    assert snapshot.state is ReplayState.PLAYING


def test_step_without_play_leaves_paused() -> None:
    replay = HistoricalReplay(_candles(3))
    snapshot = replay.step()
    assert snapshot.state is ReplayState.PAUSED


def test_pause_stops_playing_without_losing_position() -> None:
    replay = HistoricalReplay(_candles(5))
    replay.play()
    replay.step()
    replay.step()
    snapshot = replay.pause()
    assert snapshot.state is ReplayState.PAUSED
    assert snapshot.index == 1  # position preserved, not reset


def test_pause_while_not_playing_is_a_noop() -> None:
    replay = HistoricalReplay(_candles(3))
    replay.step()
    snapshot_before = replay.snapshot
    snapshot_after = replay.pause()
    assert snapshot_after == snapshot_before


# --- Reset ---


def test_reset_returns_to_pre_start_state() -> None:
    replay = HistoricalReplay(_candles(5))
    replay.step()
    replay.step()
    snapshot = replay.reset()
    assert snapshot.state is ReplayState.STOPPED
    assert snapshot.current_candle is None
    assert snapshot.visible_candles == ()


def test_reset_allows_replaying_from_the_start_deterministically() -> None:
    candles = _candles(5)
    replay = HistoricalReplay(candles)

    first_pass = [replay.step().current_candle for _ in range(5)]
    replay.reset()
    second_pass = [replay.step().current_candle for _ in range(5)]

    assert first_pass == second_pass


# --- End-of-data behavior ---


def test_step_past_the_end_transitions_to_finished_and_is_idempotent() -> None:
    replay = HistoricalReplay(_candles(2))
    replay.step()
    replay.step()
    final_snapshot = replay.step()  # past the end
    assert final_snapshot.state is ReplayState.FINISHED
    assert replay.is_finished() is True

    again = replay.step()  # calling step() again must not error or move further
    assert again == final_snapshot


def test_play_after_finished_does_not_resume() -> None:
    replay = HistoricalReplay(_candles(1))
    replay.step()
    replay.step()  # now finished
    replay.play()
    assert replay.state is ReplayState.FINISHED
