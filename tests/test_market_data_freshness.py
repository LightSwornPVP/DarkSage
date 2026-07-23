"""Tests for the provider freshness/staleness helper."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from backend.app.market_data.freshness import is_stale

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
