"""Shared, dependency-free helpers for the DarkSage publication tooling.

Standard library only. No network access, no credentials, no hard-coded
personal paths — every path is resolved relative to this file's own location
(the repository root is this file's grandparent directory:
scripts/publication/_repo.py -> scripts/publication -> scripts -> repo root).
"""

from __future__ import annotations

import hashlib
import os
import subprocess
import sys
from pathlib import Path
from typing import Optional

REPO_ROOT: Path = Path(__file__).resolve().parents[2]


class PathContainmentError(ValueError):
    """Raised when a user-supplied path is absolute, contains a '..'
    traversal segment, or would resolve (directly or via a symlink) to a
    location outside the repository root. HIGH3 repair: every publication
    tool that reads or writes a user-supplied path must let this propagate
    (or catch it and fail clearly/nonzero) rather than silently touching
    anything outside the repository."""


def _is_contained(root: Path, candidate: Path) -> bool:
    """Ancestry-based containment check (not a naive string-prefix check).
    Tries proper path ancestry first; falls back to a separator-bounded,
    case-normalized comparison only to tolerate Windows' case-insensitive,
    not-always-case-preserving filesystem for paths that don't exist yet
    (so "docs/Publication" still matches "docs/publication" on Windows)."""
    try:
        candidate.relative_to(root)
        return True
    except ValueError:
        pass
    root_s = os.path.normcase(str(root))
    cand_s = os.path.normcase(str(candidate))
    return cand_s == root_s or cand_s.startswith(root_s + os.sep)


def repo_relative(path: Path) -> str:
    """Render a path relative to the repository root, POSIX-style, for
    deterministic, environment-independent output."""
    try:
        rel = path.resolve().relative_to(REPO_ROOT)
    except ValueError:
        rel = path
    return rel.as_posix()


def resolve_repo_path(rel_path: str) -> Path:
    """Resolve a repository-relative path (as recorded in a manifest,
    register, or CLI argument) against REPO_ROOT, enforcing containment.

    Rejects, by raising PathContainmentError:
    - an empty/blank path;
    - an absolute path (POSIX `/...` or Windows `C:\\...`) — every accepted
      input is repository-relative, with no "trusted absolute" bypass;
    - any path containing a literal '..' segment, regardless of whether the
      resolved target would actually escape (defense in depth: the pattern
      itself is rejected, not only its eventual effect);
    - any resolved target — including one reached only after following a
      symlink — that is not contained within REPO_ROOT, checked by path
      ancestry (Path.relative_to), not string-prefix matching.

    Never produces or accepts an absolute, machine-specific path as a
    *result* callers should persist — return values are always REPO_ROOT-
    contained Path objects, and repo_relative() renders them back to a
    portable, repository-relative string for output.
    """
    if rel_path is None or not str(rel_path).strip():
        raise PathContainmentError("path must not be empty")

    candidate = Path(rel_path)

    if candidate.is_absolute():
        raise PathContainmentError(
            f"absolute paths are not accepted: {rel_path!r} — supply a repository-relative path instead"
        )

    if ".." in candidate.parts:
        raise PathContainmentError(
            f"parent-directory traversal ('..') is not accepted: {rel_path!r}"
        )

    resolved = (REPO_ROOT / candidate).resolve()

    if not _is_contained(REPO_ROOT, resolved):
        raise PathContainmentError(
            f"resolved path escapes the repository root: {rel_path!r} -> {resolved}"
        )

    return resolved


class GitUnavailableError(RuntimeError):
    """Raised when Git metadata cannot be determined. Callers must fail
    clearly and must never substitute a hard-coded commit hash."""


def git_head(repo_root: Path = REPO_ROOT) -> str:
    """Return the actual current Git HEAD commit hash via `git rev-parse
    HEAD`. Raises GitUnavailableError on any failure — never returns a
    fabricated or previously-hard-coded hash."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise GitUnavailableError(f"could not invoke git: {exc}") from exc

    if result.returncode != 0:
        stderr = result.stderr.strip()
        raise GitUnavailableError(
            f"git rev-parse HEAD failed (exit {result.returncode}): {stderr}"
        )

    head = result.stdout.strip()
    if not head:
        raise GitUnavailableError("git rev-parse HEAD returned empty output")
    return head


def sha256_of_file(path: Path) -> Optional[str]:
    """Return the SHA-256 hex digest of an existing file, or None if the
    file does not exist. Never fabricates a checksum for a missing file."""
    if not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def eprint(*args, **kwargs) -> None:
    print(*args, file=sys.stderr, **kwargs)
