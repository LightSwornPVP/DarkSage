#!/usr/bin/env python3
"""Record the actual current Git HEAD commit hash for the publication batch.

Never uses a hard-coded commit. Fails clearly (nonzero exit, message on
stderr) when Git metadata is unavailable — it does not fall back to a
guessed or previously-recorded hash.

Usage:
    python scripts/publication/record_baseline.py
    python scripts/publication/record_baseline.py --output docs/publication/BASELINE.json
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from _repo import (
    REPO_ROOT,
    GitUnavailableError,
    PathContainmentError,
    eprint,
    git_head,
    repo_relative,
    resolve_repo_path,
)


def record_baseline() -> dict:
    """Return a deterministic dict describing the actual current baseline.
    Raises GitUnavailableError if HEAD cannot be determined."""
    head = git_head()
    return {
        "baseline_commit": head,
        "recorded_at_utc": None,  # filled by caller only if --timestamp is passed
        "repo_root": repo_relative(REPO_ROOT) or ".",
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        help="Optional repository-relative path to write the baseline record as JSON.",
    )
    parser.add_argument(
        "--timestamp",
        action="store_true",
        help="Include the current UTC timestamp (wall-clock, not fabricated) in the output.",
    )
    args = parser.parse_args(argv)

    try:
        record = record_baseline()
    except GitUnavailableError as exc:
        eprint(f"ERROR: cannot record baseline — {exc}")
        eprint("No commit hash was written. Nothing was fabricated.")
        return 1

    if args.timestamp:
        record["recorded_at_utc"] = datetime.now(timezone.utc).isoformat()
    else:
        del record["recorded_at_utc"]

    text = json.dumps(record, indent=2, sort_keys=True) + "\n"

    if args.output:
        try:
            out_path = resolve_repo_path(args.output)
        except PathContainmentError as exc:
            eprint(f"ERROR: refusing to write outside the repository — {exc}")
            eprint("No file was written.")
            return 1
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(text, encoding="utf-8")
        print(f"Baseline recorded: {record['baseline_commit']}")
        print(f"Written to: {repo_relative(out_path)}")
    else:
        print(text, end="")

    return 0


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    raise SystemExit(main())
