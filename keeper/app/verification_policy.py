from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True, slots=True)
class VerificationSpec:
    category: str
    arguments: list[str]
    validator: str
    required: bool = True
    waiver_id: str | None = None


@dataclass(frozen=True, slots=True)
class VerificationWaiver:
    waiver_id: str
    category: str
    task_id: str
    approving_authority: str
    reason: str
    expires_at: str


REGISTERED_CATEGORIES: dict[str, frozenset[str]] = {
    "tests": frozenset({"pytest"}),
    "typing": frozenset({"mypy"}),
    "compilation": frozenset({"compileall"}),
    "foundation": frozenset({"foundation-script"}),
    "task": frozenset({"file-equals", "registered-command"}),
    "security": frozenset({"security-scan"}),
    "packaging": frozenset({"package-smoke"}),
}


def validate_semantic_bindings(
    specs: Iterable[VerificationSpec],
    required_categories: Iterable[str],
) -> None:
    values = list(specs)
    if not values:
        raise ValueError("verification specification cannot be empty")
    seen_commands: set[tuple[str, ...]] = set()
    covered: set[str] = set()
    for spec in values:
        if not spec.arguments:
            raise ValueError("verification command cannot be empty")
        accepted = REGISTERED_CATEGORIES.get(spec.category)
        if accepted is None or spec.validator not in accepted:
            raise ValueError(
                f"validator {spec.validator!r} cannot satisfy category {spec.category!r}"
            )
        _validate_command_pattern(spec)
        fingerprint = tuple(spec.arguments)
        if fingerprint in seen_commands:
            raise ValueError("the same command cannot be counted more than once")
        seen_commands.add(fingerprint)
        if spec.required and spec.waiver_id is None:
            covered.add(spec.category)
    missing = set(required_categories) - covered
    if missing:
        raise ValueError(f"mandatory verification categories are unsatisfied: {sorted(missing)}")


def environment_summary(environment: dict[str, str]) -> dict[str, object]:
    safe_keys = sorted(
        key
        for key in environment
        if not any(
            marker in key.upper()
            for marker in ("TOKEN", "SECRET", "PASSWORD", "KEY", "COOKIE", "CREDENTIAL")
        )
    )
    return {"available_keys": safe_keys, "secret_values_included": False}


def _validate_command_pattern(spec: VerificationSpec) -> None:
    args = [item.lower().replace("\\", "/") for item in spec.arguments]
    if spec.validator == "pytest" and not _module_command(args, "pytest"):
        raise ValueError("pytest category requires a Python pytest module command")
    if spec.validator == "mypy" and not _module_command(args, "mypy"):
        raise ValueError("typing category requires a Python mypy module command")
    if spec.validator == "compileall" and not _module_command(args, "compileall"):
        raise ValueError("compilation category requires Python compileall")
    if spec.validator == "foundation-script":
        if not any(item.endswith("scripts/verify-foundation.sh") for item in args):
            raise ValueError("foundation category requires the registered foundation script")
    if spec.validator == "file-equals" and args[0] != "keeper:file-equals":
        raise ValueError("file-equals validator requires the Keeper registered command")
    if spec.validator == "registered-command":
        executable = Path(spec.arguments[0]).name.lower()
        if executable in {"cmd", "cmd.exe", "powershell", "powershell.exe", "pwsh", "bash", "sh"}:
            raise ValueError("generic shell commands cannot be registered verification commands")


def _module_command(arguments: list[str], module: str) -> bool:
    return len(arguments) >= 3 and arguments[1:3] == ["-m", module]
