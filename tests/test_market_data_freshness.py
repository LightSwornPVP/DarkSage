"""Tests for the provider freshness/staleness helper."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from backend.app.market_data.freshness import default_max_age, is_stale
from shared.models.candle import Timeframe

NOW = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)


def test_is_stale_true_when_older_than_max_age() -> None:
    timestamp = NOW - timedelta(hours=2)
    assert is_stale(timestamp, max_age=timedelta(hours=1), now=NOW) is True


def test_is_stale_false_when_within_max_age() -> None:
    timestamp = NOW - timedelta(minutes=30)
    assert is_stale(timestamp, max_age=timedelta(hours=1), now=NOW) is False


def test_is_stale_false_at_exact_boundary() -> None:
    timestamp = NOW - timedelta(hours=1)
    assert is_stale(timestamp, max_age=timedelta(hours=1), now=NOW) is False


def test_is_stale_rejects_naive_timestamp() -> None:
    with pytest.raises(ValueError):
        is_stale(datetime(2026, 1, 1), max_age=timedelta(hours=1), now=NOW)


def test_is_stale_rejects_naive_now() -> None:
    with pytest.raises(ValueError):
        is_stale(NOW, max_age=timedelta(hours=1), now=datetime(2026, 1, 1))


# --- Future-dated timestamps must be treated as invalid/stale (blocker 1) ---


def test_is_stale_true_for_timestamp_far_in_the_future() -> None:
    future_timestamp = NOW + timedelta(days=1)
    assert is_stale(future_timestamp, max_age=timedelta(hours=1), now=NOW) is True


def test_is_stale_false_for_timestamp_within_clock_skew_tolerance() -> None:
    slightly_future = NOW + timedelta(minutes=1)
    assert is_stale(slightly_future, max_age=timedelta(hours=1), now=NOW) is False


def test_is_stale_true_just_beyond_clock_skew_tolerance() -> None:
    just_beyond_tolerance = NOW + timedelta(minutes=10)
    assert (
        is_stale(
            just_beyond_tolerance,
            max_age=timedelta(hours=1),
            now=NOW,
            clock_skew_tolerance=timedelta(minutes=5),
        )
        is True
    )


def test_is_stale_rejects_negative_clock_skew_tolerance() -> None:
    with pytest.raises(ValueError):
        is_stale(NOW, max_age=timedelta(hours=1), now=NOW, clock_skew_tolerance=timedelta(seconds=-1))


# --- Explicit test-context override: caller can widen tolerance/max_age ---


def test_is_stale_explicit_wide_tolerance_accepts_future_timestamp() -> None:
    future_timestamp = NOW + timedelta(hours=2)
    assert (
        is_stale(
            future_timestamp,
            max_age=timedelta(hours=1),
            now=NOW,
            clock_skew_tolerance=timedelta(hours=3),
        )
        is False
    )


# --- Per-timeframe default staleness thresholds (enabled-by-default freshness) ---


def test_default_max_age_covers_every_timeframe() -> None:
    for timeframe in Timeframe:
        max_age = default_max_age(timeframe)
        assert max_age > timedelta(0)


def test_default_max_age_daily_allows_a_weekend_gap() -> None:
    friday_close = NOW
    monday_morning = friday_close + timedelta(days=3)
    assert is_stale(friday_close, max_age=default_max_age(Timeframe.D1), now=monday_morning) is False


def test_default_max_age_intraday_is_much_shorter_than_daily() -> None:
    assert default_max_age(Timeframe.M1) < default_max_age(Timeframe.D1)
