from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from keeper.pass_b.enums import AssignmentState, ReservationMode
from keeper.pass_b.models import (
    AssignmentRecord,
    EvidenceBundleRecord,
    WorkspaceReservationRecord,
)
from keeper.pass_b.repository import (
    contains_pilot_evidence,
    is_pilot_evidence_path,
)


Runner = Callable[..., subprocess.CompletedProcess[str]]


@dataclass(frozen=True, slots=True)
class WorkspacePolicy:
    implementation_root: Path
    prohibited_roots: tuple[Path, ...]
    prohibited_fragments: tuple[str, ...] = (".ai-workflow/pw",)

    def validate_target(self, target: Path) -> Path:
        resolved = target.resolve()
        root = self.implementation_root.resolve()
        try:
            resolved.relative_to(root)
        except ValueError as error:
            raise PermissionError(
                "workspace must be inside the configured implementation root"
            ) from error
        normalized = str(resolved).replace("\\", "/").casefold()
        if any(
            normalized == str(item.resolve()).replace("\\", "/").casefold()
            or normalized.startswith(
                str(item.resolve()).replace("\\", "/").casefold().rstrip("/")
                + "/"
            )
            for item in self.prohibited_roots
        ) or any(
            fragment.casefold() in normalized
            for fragment in self.prohibited_fragments
        ) or is_pilot_evidence_path(resolved) or contains_pilot_evidence(
            resolved
        ):
            raise PermissionError("workspace target is in a protected scope")
        return resolved


class GitWorktreeService:
    """Explicit worktree lifecycle; cleanup is never automatic."""

    def __init__(
        self,
        policy: WorkspacePolicy,
        *,
        runner: Runner = subprocess.run,
    ) -> None:
        self.policy = policy
        self.runner = runner

    def create_implementation_worktree(
        self,
        repository: Path,
        target: Path,
        branch: str,
        base_commit: str,
        assignment: AssignmentRecord,
    ) -> Path:
        if assignment.read_only:
            raise PermissionError("read-only reviewer cannot create writer worktree")
        destination = self.policy.validate_target(target)
        if destination.exists():
            raise FileExistsError("implementation worktree target already exists")
        repository_root = repository.resolve(strict=True)
        result = self.runner(
            [
                "git",
                "-c",
                f"safe.directory={repository_root.as_posix()}",
                "-C",
                str(repository_root),
                "worktree",
                "add",
                "-b",
                branch,
                str(destination),
                base_commit,
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode:
            raise RuntimeError(
                f"isolated worktree creation failed: {result.stderr.strip()}"
            )
        return destination

    def validate_reviewer_workspace(
        self,
        assignment: AssignmentRecord,
        reservation: WorkspaceReservationRecord,
    ) -> Path:
        if (
            assignment.read_only is not True
            or reservation.mode != ReservationMode.READ_ONLY
            or reservation.assignment_id != assignment.assignment_id
        ):
            raise PermissionError("review workspace is not read-only")
        path = Path(reservation.canonical_path).resolve(strict=True)
        if not (path / ".git").exists():
            raise PermissionError("review workspace is not a Git worktree")
        return path

    def cleanup_worktree(
        self,
        repository: Path,
        reservation: WorkspaceReservationRecord,
        assignment: AssignmentRecord,
        evidence: tuple[EvidenceBundleRecord, ...],
        *,
        explicitly_approved: bool,
    ) -> None:
        if not explicitly_approved:
            raise PermissionError("worktree cleanup requires explicit approval")
        if assignment.state in {
            AssignmentState.LAUNCH_CLAIMED,
            AssignmentState.RUNNING,
            AssignmentState.UNCERTAIN,
            AssignmentState.WAITING_FOR_USAGE_RESET,
        }:
            raise PermissionError("active or uncertain worktree cannot be removed")
        if not evidence:
            raise PermissionError("worktree evidence must be preserved first")
        target = self.policy.validate_target(Path(reservation.canonical_path))
        status = self.runner(
            [
                "git",
                "-c",
                f"safe.directory={target.as_posix()}",
                "-C",
                str(target),
                "status",
                "--porcelain",
                "--untracked-files=all",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if status.returncode or status.stdout.strip():
            raise PermissionError(
                "worktree with unresolved or untracked state cannot be removed"
            )
        repository_root = repository.resolve(strict=True)
        result = self.runner(
            [
                "git",
                "-c",
                f"safe.directory={repository_root.as_posix()}",
                "-C",
                str(repository_root),
                "worktree",
                "remove",
                str(target),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode:
            raise RuntimeError(
                f"explicit worktree cleanup failed: {result.stderr.strip()}"
            )


def workspace_identity(path: Path) -> str:
    import hashlib

    normalized = os.path.normcase(str(path.resolve()))
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()
