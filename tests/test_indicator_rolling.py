"""Tests for the generic rolling-window primitives used by concrete indicators."""

from __future__ import annotations

from decimal import Decimal

import pytest

from backend.app.indicators.errors import InsufficientDataError
from backend.app.indicators.rolling import ema_series, require_minimum_length, rolling_mean


def _decimals(*values: str) -> list[Decimal]:
    return [Decimal(v) for v in values]


def test_rolling_mean_known_values() -> None:
    values = _decimals("1", "2", "3", "4", "5")
    result = rolling_mean(values, 3)
    assert result == _decimals("2", "3", "4")


def test_rolling_mean_raises_on_insufficient_data() -> None:
    with pytest.raises(InsufficientDataError):
        rolling_mean(_decimals("1", "2"), 3)


def test_rolling_mean_rejects_invalid_window() -> None:
    with pytest.raises(ValueError):
        rolling_mean(_decimals("1", "2", "3"), 0)


def test_rolling_mean_is_deterministic() -> None:
    values = _decimals("10", "20", "30", "40")
    assert rolling_mean(values, 2) == rolling_mean(values, 2)


def test_ema_series_seed_is_sma_of_first_window() -> None:
    values = _decimals("2", "4", "6")
    result = ema_series(values, 3)
    assert result[0] == Decimal("4")  # (2+4+6)/3


def test_ema_series_known_second_value() -> None:
    # window=4 -> multiplier = 2/(4+1) = 0.4 exactly (terminating decimal,
    # unlike e.g. 2/3, so the expected value is exact rather than rounded).
    # seed = (10+20+30+40)/4 = 25; next = (50-25)*0.4+25 = 35
    values = _decimals("10", "20", "30", "40", "50")
    result = ema_series(values, 4)
    assert result[0] == Decimal("25")
    assert result[1] == Decimal("35")


def test_ema_series_raises_on_insufficient_data() -> None:
    with pytest.raises(InsufficientDataError):
        ema_series(_decimals("1"), 2)


def test_require_minimum_length_rejects_non_positive_minimum() -> None:
    with pytest.raises(ValueError):
        require_minimum_length([1, 2, 3], 0, label="test")
