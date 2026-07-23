"""Generic rolling-window primitives shared by concrete indicators.

Pure, deterministic, Decimal-only — no indicator-specific knowledge lives
here, only the arithmetic every moving-window indicator needs.
"""

from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal

from backend.app.indicators.errors import InsufficientDataError


def require_minimum_length(values: Sequence[object], minimum: int, *, label: str) -> None:
    if minimum < 1:
        raise ValueError("minimum must be >= 1")
    if len(values) < minimum:
        raise InsufficientDataError(
            f"{label}: need at least {minimum} value(s), got {len(values)}"
        )


def rolling_mean(values: Sequence[Decimal], window: int) -> list[Decimal]:
    """Simple moving average over ``window``-sized slices.

    Returns one value per index from ``window - 1`` to ``len(values) - 1``
    (i.e. only where a full window exists — no partial/leading windows).
    """
    require_minimum_length(values, window, label="rolling_mean")
    window_decimal = Decimal(window)
    result: list[Decimal] = []
    running_sum = sum(values[:window], start=Decimal(0))
    result.append(running_sum / window_decimal)
    for index in range(window, len(values)):
        running_sum += values[index] - values[index - window]
        result.append(running_sum / window_decimal)
    return result


def ema_series(values: Sequence[Decimal], window: int) -> list[Decimal]:
    """Exponential moving average, seeded with the SMA of the first ``window``
    values (a standard, deterministic seeding convention)."""
    require_minimum_length(values, window, label="ema_series")
    window_decimal = Decimal(window)
    multiplier = Decimal(2) / (window_decimal + Decimal(1))

    seed = sum(values[:window], start=Decimal(0)) / window_decimal
    result: list[Decimal] = [seed]
    previous = seed
    for index in range(window, len(values)):
        current = (values[index] - previous) * multiplier + previous
        result.append(current)
        previous = current
    return result
