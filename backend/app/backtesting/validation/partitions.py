"""Date partitions for train/validation/test splits and walk-forward windows.

A ``DatePartition`` is a half-open range ``[start, end)`` — this makes
adjacent partitions (e.g. one window's out-of-sample period ending exactly
where the next window's in-sample period begins) unambiguous: a timestamp
belongs to exactly one partition, never both.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal

from backend.app.backtesting.errors import InvalidPartitionError


@dataclass(frozen=True, slots=True)
class DatePartition:
    """A single labeled, half-open date range: ``[start, end)``."""

    label: str
    start: datetime
    end: datetime

    def __post_init__(self) -> None:
        if not self.label.strip():
            raise InvalidPartitionError("DatePartition.label must not be blank")
        if self.start.tzinfo is None or self.end.tzinfo is None:
            raise InvalidPartitionError("DatePartition start/end must be timezone-aware")
        if self.end <= self.start:
            raise InvalidPartitionError(f"DatePartition '{self.label}': end must be after start")

    def contains(self, timestamp: datetime) -> bool:
        return self.start <= timestamp < self.end


def validate_no_overlap(partitions: Sequence[DatePartition]) -> None:
    """Fail closed if any two partitions overlap, or if they are not given
    in non-decreasing chronological order — this is the structural
    guarantee that no out-of-sample period can leak into another
    partition's data."""
    for previous, current in zip(partitions, partitions[1:], strict=False):
        if current.start < previous.end:
            raise InvalidPartitionError(
                f"partitions '{previous.label}' ({previous.start}..{previous.end}) and "
                f"'{current.label}' ({current.start}..{current.end}) overlap"
            )


def split_periods(
    start: datetime, end: datetime, fractions: Mapping[str, Decimal]
) -> tuple[DatePartition, ...]:
    """Split ``[start, end)`` into consecutive, non-overlapping partitions
    sized by ``fractions`` (which must sum to exactly 1), in the order given.

    Deterministic: the same inputs always produce byte-identical boundaries.
    The final partition always ends exactly at ``end`` regardless of
    rounding in earlier segments, so no time is lost or double-counted.
    """
    if start.tzinfo is None or end.tzinfo is None:
        raise InvalidPartitionError("split_periods: start/end must be timezone-aware")
    if end <= start:
        raise InvalidPartitionError("split_periods: end must be after start")
    if not fractions:
        raise InvalidPartitionError("split_periods: fractions must not be empty")
    total_fraction = sum(fractions.values(), start=Decimal(0))
    if total_fraction != Decimal(1):
        raise InvalidPartitionError(f"split_periods: fractions must sum to exactly 1, got {total_fraction}")
    for label, fraction in fractions.items():
        if fraction <= 0:
            raise InvalidPartitionError(f"split_periods: fraction for '{label}' must be > 0")

    total_seconds = Decimal(str((end - start).total_seconds()))
    items = list(fractions.items())
    partitions: list[DatePartition] = []
    cursor = start
    for index, (label, fraction) in enumerate(items):
        if index == len(items) - 1:
            segment_end = end  # exact: absorbs any rounding drift from earlier segments
        else:
            segment_end = cursor + timedelta(seconds=float(total_seconds * fraction))
        partitions.append(DatePartition(label, cursor, segment_end))
        cursor = segment_end

    validate_no_overlap(partitions)
    return tuple(partitions)
