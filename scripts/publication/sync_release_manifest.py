#!/usr/bin/env python3
"""Synchronize docs/codex/RELEASE_MANIFEST_2026-07-25.json's per-file
byte-count/SHA-256 fields against what is actually on disk under docs/codex/.

No dedicated generator ever existed for this specific Core release manifest
(unlike docs/publication/PUBLICATION_MANIFEST.json, which generate_manifest.py
owns) -- this script fills that gap using the same approved, dependency-free
primitives every other tool in this directory already uses
(_repo.sha256_of_file, _repo.resolve_repo_path): never fabricates a checksum
or byte count, never adds or removes a "files" entry, never touches any field
other than "bytes"/"sha256" on an entry whose file still exists at its
recorded path. A recorded path that no longer exists on disk is reported as
an error, not silently dropped or given a fabricated value.

Usage:
    python scripts/publication/sync_release_manifest.py
    python scripts/publication/sync_release_manifest.py --check   # exit 1 if stale
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from _repo import PathContainmentError, eprint, repo_relative, resolve_repo_path, sha256_of_file

MANIFEST_PATH = "docs/codex/RELEASE_MANIFEST_2026-07-25.json"
CODEX_BASE = "docs/codex"


def sync_manifest(manifest_rel_path: str = MANIFEST_PATH) -> tuple[dict, list[str]]:
    """Return (updated_manifest_dict, list_of_changed_entry_paths). Raises
    FileNotFoundError if a recorded entry's file no longer exists -- never
    silently drops or fabricates a value for a missing file."""
    manifest_path = resolve_repo_path(manifest_rel_path)
    if not manifest_path.is_file():
        raise FileNotFoundError(f"{manifest_rel_path} does not exist")

    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    changed = []

    for entry in data.get("files", []):
        rel = entry["path"]
        abs_path = resolve_repo_path(f"{CODEX_BASE}/{rel}")
        if not abs_path.is_file():
            raise FileNotFoundError(
                f"manifest entry '{rel}' has no corresponding file on disk at {repo_relative(abs_path)}"
            )
        actual_bytes = abs_path.stat().st_size
        actual_sha = sha256_of_file(abs_path)
        if entry.get("bytes") != actual_bytes or entry.get("sha256") != actual_sha:
            entry["bytes"] = actual_bytes
            entry["sha256"] = actual_sha
            changed.append(rel)

    return data, changed


def render(data: dict) -> str:
    return json.dumps(data, indent=2) + "\n"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", default=MANIFEST_PATH, help="Repository-relative path to the Core release manifest.")
    parser.add_argument("--check", action="store_true", help="Do not write; exit 1 if any entry is stale.")
    args = parser.parse_args(argv)

    try:
        data, changed = sync_manifest(args.manifest)
    except (FileNotFoundError, PathContainmentError) as exc:
        eprint(f"ERROR: {exc}")
        return 1

    if args.check:
        if changed:
            eprint(f"CHECK FAILED: {len(changed)} stale entry/entries: {changed}")
            return 1
        print(f"CHECK OK: {args.manifest} matches actual file bytes/SHA-256 for all {len(data['files'])} entries.")
        return 0

    manifest_path = resolve_repo_path(args.manifest)
    manifest_path.write_text(render(data), encoding="utf-8")
    if changed:
        print(f"Synchronized {len(changed)} stale entry/entries: {changed}")
    else:
        print("No stale entries found; manifest already matches actual file bytes/SHA-256.")
    return 0


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    raise SystemExit(main())
