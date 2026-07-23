"""Extensible registry of available indicators."""

from __future__ import annotations

from backend.app.indicators.base import Indicator


class IndicatorRegistry:
    """Deterministic name -> ``Indicator`` lookup.

    New indicators (Phase 1.8 and beyond) are added by constructing one and
    calling ``register`` — this class has no knowledge of any specific
    indicator.
    """

    def __init__(self) -> None:
        self._indicators: dict[str, Indicator] = {}

    def register(self, indicator: Indicator) -> None:
        if indicator.name in self._indicators:
            raise ValueError(f"indicator '{indicator.name}' is already registered")
        self._indicators[indicator.name] = indicator

    def get(self, name: str) -> Indicator:
        try:
            return self._indicators[name]
        except KeyError as exc:
            raise KeyError(f"no indicator registered under name '{name}'") from exc

    def names(self) -> tuple[str, ...]:
        return tuple(sorted(self._indicators))

    def __contains__(self, name: object) -> bool:
        return name in self._indicators
