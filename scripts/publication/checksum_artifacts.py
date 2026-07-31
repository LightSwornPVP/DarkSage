#!/usr/bin/env python3
"""Compute SHA-256 checksums for publication artifacts that actually exist.

Never fabricates a checksum for a missing file — a nonexistent path is
reported with checksum: null, not omitted and not guessed.

Usage:
    python scripts/publication/checksum_artifacts.py <repo-relative-path> [<repo-relative-path> ...]
    python scripts/publication/checksum_artifacts.py --json <repo-relative-path> ...
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from _repo import PathContainmentError, REPO_ROOT, eprint, repo_relative, resolve_repo_path, sha256_of_file


def checksum_paths(rel_paths: list[str]) -> dict:
    """Return {repo_relative_path: {"exists": bool, "sha256": str|None,
    "rejected": str|None}} for each requested path, deterministically
    ordered by input order. A path outside the repository (absolute, '..'
    traversal, or symlink-escape) is never opened or hashed — it is
    reported with rejected=<reason>, exists=False, sha256=None."""
    results = {}
    for rel in rel_paths:
        try:
            abs_path = resolve_repo_path(rel)
        except PathContainmentError as exc:
            results[rel] = {"exists": False, "sha256": None, "rejected": str(exc)}
            continue
        digest = sha256_of_file(abs_path)
        results[rel] = {
            "exists": abs_path.is_file(),
            "sha256": digest,
            "rejected": None,
        }
    return results


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="+", help="Repository-relative file paths to checksum.")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
    args = parser.parse_args(argv)

    results = checksum_paths(args.paths)

    missing = [p for p, r in results.items() if not r["exists"] and not r.get("rejected")]
    rejected = [p for p, r in results.items() if r.get("rejected")]

    if args.json:
        print(json.dumps(results, indent=2, sort_keys=True))
    else:
        for rel, info in results.items():
            if info.get("rejected"):
                print(f"REJECTED  {rel}  ({info['rejected']})")
            elif info["exists"]:
                print(f"OK    {rel}  sha256={info['sha256']}")
            else:
                print(f"MISSING  {rel}  (no checksum computed — file does not exist)")

    if rejected:
        eprint(f"REJECTED {len(rejected)} path(s) outside the repository — nothing outside the repository was read.")
    if missing or rejected:
        return 2
    return 0


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    raise SystemExit(main())
