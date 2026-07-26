from __future__ import annotations

import subprocess
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from keeper.policies import enforce_path_scope


FORBIDDEN_GIT_ACTIONS = frozenset(
    {"merge", "rebase", "reset", "stash", "clean", "push-force", "branch-delete", "worktree-remove"}
)


@dataclass(frozen=True, slots=True)
class RepositoryInspection:
    root: str
    branch: str
    head: str
    dirty: bool
    detached: bool
    staged: list[str]
    unstaged: list[str]
    untracked: list[str]
    conflicts: list[str]
    worktrees: list[dict[str, str]]


class GitSafetyService:
    def inspect(self, repository: Path) -> RepositoryInspection:
        root = repository.resolve()
        head = self._git(root, "rev-parse", "HEAD").stdout.strip()
        branch_result = self._git(root, "branch", "--show-current")
        branch = branch_result.stdout.strip()
        status = self._git(root, "status", "--porcelain=v1", "--untracked-files=all")
        staged = self._lines(self._git(root, "diff", "--cached", "--name-only").stdout)
        unstaged = self._lines(self._git(root, "diff", "--name-only").stdout)
        untracked = self._lines(
            self._git(root, "ls-files", "--others", "--exclude-standard").stdout
        )
        conflicts = self._lines(
            self._git(root, "diff", "--name-only", "--diff-filter=U").stdout
        )
        worktrees = self._parse_worktrees(
            self._git(root, "worktree", "list", "--porcelain").stdout
        )
        return RepositoryInspection(
            str(root),
            branch,
            head,
            bool(status.stdout.strip()),
            not bool(branch),
            staged,
            unstaged,
            untracked,
            conflicts,
            worktrees,
        )

    def merge_base(self, repository: Path, baseline: str) -> str:
        self.validate_baseline(repository, baseline)
        return self._git(repository.resolve(), "merge-base", "HEAD", baseline).stdout.strip()

    def validate_baseline(self, repository: Path, baseline: str) -> None:
        if not baseline or self._git(
            repository.resolve(), "cat-file", "-e", f"{baseline}^{{commit}}", check=False
        ).returncode:
            raise ValueError("approved baseline commit does not exist")

    def stage_allowlisted(
        self, repository: Path, paths: list[str], allowed: list[str], blocked: list[str]
    ) -> None:
        if not paths:
            raise ValueError("no paths were authorized for staging")
        enforce_path_scope(paths, allowed, blocked)
        root = repository.resolve()
        for relative in paths:
            candidate = root / relative
            resolved = candidate.resolve()
            if not resolved.is_relative_to(root):
                raise PermissionError("staging path escapes repository")
            if candidate.is_symlink():
                raise PermissionError("Keeper does not stage symbolic links")
        self._git(repository.resolve(), "add", "--", *paths)
        conflicts = self._git(
            repository.resolve(), "diff", "--cached", "--name-only", "--diff-filter=U"
        ).stdout
        if conflicts.strip():
            raise RuntimeError("staged changes contain unresolved conflicts")
        binary = self._git(
            root, "diff", "--cached", "--numstat", "--", *paths
        ).stdout.splitlines()
        if any(line.startswith("-\t-\t") for line in binary):
            raise PermissionError("unexpected binary addition requires separate authorization")

    def commit(
        self, repository: Path, message: str, authorization: dict[str, object]
    ) -> str:
        self._require_authorization("commit", repository, authorization)
        if not message.strip():
            raise ValueError("commit message cannot be empty")
        result = self._git(repository.resolve(), "commit", "-m", message)
        authorization["consumed_at"] = datetime.now(UTC).isoformat()
        return result.stdout.strip()

    def push(
        self, repository: Path, remote: str, branch: str, authorization: dict[str, object]
    ) -> str:
        self._require_authorization("push", repository, authorization)
        if not remote or not branch or branch.startswith("-"):
            raise ValueError("push target is invalid")
        result = self._git(repository.resolve(), "push", remote, branch)
        authorization["consumed_at"] = datetime.now(UTC).isoformat()
        return result.stderr.strip() or result.stdout.strip()

    @staticmethod
    def reject_action(action: str) -> None:
        if action in FORBIDDEN_GIT_ACTIONS:
            raise PermissionError(f"Keeper never performs prohibited Git action: {action}")

    def _git(
        self, repository: Path, *arguments: str, check: bool = True
    ) -> subprocess.CompletedProcess[str]:
        result = subprocess.run(
            ["git", "-c", f"safe.directory={repository.as_posix()}", *arguments],
            cwd=repository,
            capture_output=True,
            text=True,
            shell=False,
            timeout=60,
            check=False,
        )
        if check and result.returncode:
            raise RuntimeError(result.stderr.strip() or "Git operation failed")
        return result

    @staticmethod
    def _parse_worktrees(value: str) -> list[dict[str, str]]:
        entries: list[dict[str, str]] = []
        current: dict[str, str] = {}
        for line in [*value.splitlines(), ""]:
            if not line:
                if current:
                    entries.append(current)
                    current = {}
            elif " " in line:
                key, content = line.split(" ", 1)
                current[key] = content
        return entries

    @staticmethod
    def _lines(value: str) -> list[str]:
        return [line for line in value.splitlines() if line]

    @staticmethod
    def _require_authorization(
        capability: str, repository: Path, authorization: dict[str, object]
    ) -> None:
        expires_at = authorization.get("expires_at")
        try:
            expires = datetime.fromisoformat(str(expires_at))
        except (TypeError, ValueError) as error:
            raise PermissionError("authorization expiration is malformed") from error
        if expires.tzinfo is None or expires.utcoffset() is None:
            raise PermissionError("authorization expiration must be timezone-aware")
        if (
            authorization.get("capability") != capability
            or authorization.get("repository") != str(repository.resolve())
            or authorization.get("consumed_at") is not None
            or authorization.get("revoked_at") is not None
            or not authorization.get("approving_authority")
            or expires <= datetime.now(UTC)
        ):
            raise PermissionError(f"explicit scoped {capability} authorization is required")
