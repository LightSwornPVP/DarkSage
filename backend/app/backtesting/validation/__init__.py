"""Anti-overfitting validation: train/validation/test partitioning and
walk-forward out-of-sample testing. A general strategy-validation
framework — no machine-learning training is implemented here.
"""

from backend.app.backtesting.validation.partitions import DatePartition, split_periods, validate_no_overlap
from backend.app.backtesting.validation.walkforward import (
    WalkForwardResult,
    WalkForwardWindow,
    WalkForwardWindowResult,
    generate_walk_forward_windows,
    run_walk_forward,
)

__all__ = [
    "DatePartition",
    "WalkForwardResult",
    "WalkForwardWindow",
    "WalkForwardWindowResult",
    "generate_walk_forward_windows",
    "run_walk_forward",
    "split_periods",
    "validate_no_overlap",
]
