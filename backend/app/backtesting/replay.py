"""``HistoricalReplay`` — deterministic, chronological step-through of a
candle series at the domain/service level.

"Speed" and rendering are deliberately not this class's concern: ``play()``
only flips a state flag, it does not start a timer or drive stepping
itself. An external driver (a UI loop, a test, a script) decides how often
to call ``step()`` while ``is_playing()`` is true — replay state is always
exactly what the sequence of ``step()``/``pause()``/``reset()`` calls made
it, independent of wall-clock speed or how a UI chooses to render it. Later
chart/UI integration is deferred entirely; nothing here imports or assumes
one.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum

from backend.app.indicators.engine import IndicatorEngine
from backend.app.indicators.types import IndicatorResult
from shared.models.candle import Candle


class ReplayState(str, Enum):
    STOPPED = "stopped"
    PLAYING = "playing"
    PAUSED = "paused"
    FINISHED = "finished"


@dataclass(frozen=True, slots=True)
class ReplaySnapshot:
    """The replay's current visible state — never contains a future candle."""

    index: int
    state: ReplayState
    current_candle: Candle | None
    visible_candles: tuple[Candle, ...]


class HistoricalReplay:
    """Step-through of a validated, chronologically ordered candle series."""

    def __init__(self, candles: Sequence[Candle]) -> None:
        if not candles:
            raise ValueError("HistoricalReplay requires at least one candle")
        for previous, current in zip(candles, candles[1:], strict=False):
            if current.timestamp <= previous.timestamp:
                raise ValueError("candles must be strictly ordered by ascending timestamp with no duplicates")
        self._candles = tuple(candles)
        self._index = -1  # -1 == not started: no candle has been revealed yet
        self._state = ReplayState.STOPPED

    @property
    def state(self) -> ReplayState:
        return self._state

    @property
    def snapshot(self) -> ReplaySnapshot:
        if self._index < 0:
            return ReplaySnapshot(index=self._index, state=self._state, current_candle=None, visible_candles=())
        return ReplaySnapshot(
            index=self._index,
            state=self._state,
            current_candle=self._candles[self._index],
            visible_candles=self._candles[: self._index + 1],
        )

    def is_playing(self) -> bool:
        return self._state is ReplayState.PLAYING

    def is_finished(self) -> bool:
        return self._state is ReplayState.FINISHED

    def play(self) -> ReplaySnapshot:
        """Mark the replay as playing. Does not itself step — an external
        driver calls ``step()`` repeatedly while ``is_playing()`` is true."""
        if self._state is not ReplayState.FINISHED:
            self._state = ReplayState.PLAYING
        return self.snapshot

    def pause(self) -> ReplaySnapshot:
        if self._state is ReplayState.PLAYING:
            self._state = ReplayState.PAUSED
        return self.snapshot

    def step(self) -> ReplaySnapshot:
        """Advance exactly one candle and return the resulting snapshot.

        A no-op (not an error) once the series is exhausted — repeatedly
        calling ``step()`` past the end just keeps returning the final,
        ``FINISHED`` snapshot.
        """
        if self._state is ReplayState.FINISHED:
            return self.snapshot
        next_index = self._index + 1
        if next_index >= len(self._candles):
            self._state = ReplayState.FINISHED
            return self.snapshot
        self._index = next_index
        if self._state is not ReplayState.PLAYING:
            self._state = ReplayState.PAUSED  # a manual step leaves it paused, not "playing"
        return self.snapshot

    def reset(self) -> ReplaySnapshot:
        """Return to the pre-start state — as if no ``step()`` had ever run."""
        self._index = -1
        self._state = ReplayState.STOPPED
        return self.snapshot

    def compute_indicator(self, engine: IndicatorEngine, name: str) -> IndicatorResult:
        """Compute indicator ``name`` over exactly the candles visible at
        the current replay point — never anything later."""
        if self._index < 0:
            raise ValueError("cannot compute an indicator before the replay has stepped at least once")
        return engine.compute(name, self._candles[: self._index + 1])
