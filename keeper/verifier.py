from __future__ import annotations

import os
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from keeper.models.task import now_iso

from keeper.policies import filtered_environment
from keeper.policies import resolve_within


@dataclass(frozen=True, slots=True)
class VerificationCommand:
    arguments: list[str]
    required: bool = True
    timeout_seconds: int = 600


@dataclass(frozen=True, slots=True)
class VerificationResult:
    arguments: list[str]
    required: bool
    exit_code: int
    stdout: str
    stderr: str
    timed_out: bool = False

    @property
    def passed(self) -> bool:
        return self.exit_code == 0

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


class Verifier:
    def run(self, workspace: Path, commands: list[VerificationCommand]) -> list[VerificationResult]:
        if not commands:
            raise ValueError("at least one mandatory verification command is required")
        results: list[VerificationResult] = []
        for command in commands:
            if not command.arguments:
                raise ValueError("verification command cannot be empty")
            if command.arguments[0] == "keeper:file-equals":
                if len(command.arguments) != 3:
                    raise ValueError("keeper:file-equals requires a path and expected content")
                target = resolve_within(workspace, command.arguments[1])
                actual = target.read_text(encoding="utf-8") if target.is_file() else ""
                expected = command.arguments[2]
                result = VerificationResult(
                    command.arguments,
                    command.required,
                    0 if actual == expected else 1,
                    "file content matched\n" if actual == expected else "",
                    "" if actual == expected else f"unexpected content in {command.arguments[1]}\n",
                )
                results.append(result)
                if result.required and not result.passed:
                    break
                continue
            arguments = [
                sys.executable if item == "{python}" else item for item in command.arguments
            ]
            try:
                completed = subprocess.run(
                    arguments,
                    cwd=workspace,
                    env=filtered_environment(dict(os.environ)),
                    capture_output=True,
                    text=True,
                    shell=False,
                    timeout=command.timeout_seconds,
                    check=False,
                )
                result = VerificationResult(
                    arguments,
                    command.required,
                    completed.returncode,
                    completed.stdout,
                    completed.stderr,
                )
            except subprocess.TimeoutExpired as error:
                timeout_stdout = error.stdout.decode() if isinstance(error.stdout, bytes) else (error.stdout or "")
                timeout_stderr = error.stderr.decode() if isinstance(error.stderr, bytes) else (error.stderr or "")
                result = VerificationResult(
                    arguments,
                    command.required,
                    124,
                    timeout_stdout,
                    timeout_stderr,
                    True,
                )
            except FileNotFoundError as error:
                result = VerificationResult(
                    arguments,
                    command.required,
                    127,
                    "",
                    str(error),
                )
            results.append(result)
            if result.required and not result.passed:
                break
        return results

    @staticmethod
    def required_passed(results: list[VerificationResult]) -> bool:
        return bool(results) and any(result.required for result in results) and all(
            result.passed for result in results if result.required
        )


def verification_evidence(
    *,
    task_id: str,
    attempt_id: str,
    run_id: str,
    stage: str,
    workspace: Path,
    branch: str,
    head: str,
    tree_identity: str,
    results: list[VerificationResult],
) -> dict[str, object]:
    return {
        "task_id": task_id,
        "attempt_id": attempt_id,
        "run_id": run_id,
        "stage": stage,
        "workspace": str(workspace.resolve()),
        "branch": branch,
        "head": head,
        "tree_identity": tree_identity,
        "timestamp": now_iso(),
        "passed": Verifier.required_passed(results),
        "commands": [result.to_dict() for result in results],
    }
