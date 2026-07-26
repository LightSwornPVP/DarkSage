from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
import hashlib
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True, slots=True)
class VerificationSpec:
    category: str
    arguments: list[str]
    validator: str
    required: bool = True
    waiver_id: str | None = None
    registration_id: str | None = None
    expected_sha256: str | None = None


@dataclass(frozen=True, slots=True)
class VerificationWaiver:
    waiver_id: str
    category: str
    task_id: str
    approving_authority: str
    reason: str
    expires_at: str
    revoked_at: str | None = None


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
    waivers: Iterable[VerificationWaiver] = (),
    task_id: str | None = None,
    now: datetime | None = None,
) -> None:
    values = list(specs)
    if not values:
        raise ValueError("verification specification cannot be empty")
    seen_commands: set[tuple[str, ...]] = set()
    covered: set[str] = set()
    waiver_map = {item.waiver_id: item for item in waivers}
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
        if spec.required:
            if spec.waiver_id is None:
                covered.add(spec.category)
            else:
                waiver = waiver_map.get(spec.waiver_id)
                if waiver is None:
                    raise PermissionError("verification waiver is missing or malformed")
                validate_waiver(
                    waiver,
                    task_id=task_id or "",
                    category=spec.category,
                    now=now or datetime.now(UTC),
                )
                covered.add(spec.category)
    missing = set(required_categories) - covered
    if missing:
        raise ValueError(f"mandatory verification categories are unsatisfied: {sorted(missing)}")


def validate_waiver(
    waiver: VerificationWaiver, *, task_id: str, category: str, now: datetime
) -> None:
    try:
        expires = datetime.fromisoformat(waiver.expires_at)
    except ValueError as error:
        raise PermissionError("verification waiver expiration is malformed") from error
    if expires.tzinfo is None or expires.utcoffset() is None:
        raise PermissionError("verification waiver expiration must be timezone-aware")
    if (
        waiver.task_id != task_id
        or waiver.category != category
        or not waiver.approving_authority.strip()
        or not waiver.reason.strip()
        or waiver.revoked_at is not None
        or expires <= now
    ):
        raise PermissionError("verification waiver is invalid for this task and category")


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
    if spec.validator == "pytest" and not _trusted_module_command(args, "pytest"):
        raise ValueError("pytest category requires a Python pytest module command")
    if spec.validator == "mypy" and not _trusted_module_command(args, "mypy"):
        raise ValueError("typing category requires a Python mypy module command")
    if spec.validator == "compileall" and not _trusted_module_command(args, "compileall"):
        raise ValueError("compilation category requires Python compileall")
    if spec.validator == "foundation-script":
        matches = [
            Path(original)
            for original, normalized in zip(spec.arguments, args, strict=True)
            if normalized.endswith("scripts/verify-foundation.sh")
        ]
        if len(matches) != 1:
            raise ValueError("foundation category requires the registered foundation script")
        script = matches[0]
        if (
            spec.expected_sha256 is None
            or not script.is_absolute()
            or script.is_symlink()
            or not script.is_file()
        ):
            raise ValueError("foundation script requires an absolute pinned regular file")
        actual = hashlib.sha256(script.read_bytes()).hexdigest()
        if actual != spec.expected_sha256:
            raise PermissionError("foundation script hash does not match its registration")
    if spec.validator == "file-equals" and args[0] != "keeper:file-equals":
        raise ValueError("file-equals validator requires the Keeper registered command")
    if spec.validator == "registered-command":
        executable = Path(spec.arguments[0]).name.lower()
        if executable in {"cmd", "cmd.exe", "powershell", "powershell.exe", "pwsh", "bash", "sh"}:
            raise ValueError("generic shell commands cannot be registered verification commands")


def _trusted_module_command(arguments: list[str], module: str) -> bool:
    return (
        len(arguments) >= 3
        and arguments[0] == "{python}"
        and arguments[1:3] == ["-m", module]
    )
