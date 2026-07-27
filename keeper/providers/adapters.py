from __future__ import annotations

import hashlib
import json
import os
import shutil
import uuid
from datetime import UTC, datetime
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from keeper.providers.base import AgentRequest, ProcessResult
from keeper.providers.codex_cli import CliProvider


@dataclass(frozen=True, slots=True)
class ProviderCapabilities:
    author: bool = True
    reviewer: bool = True
    repairer: bool = True
    structured_output: bool = True
    streaming: bool = True
    cancellation: bool = True
    usage_reporting: bool = False
    local_only: bool = False


@dataclass(frozen=True, slots=True)
class ProviderDiagnostic:
    provider_id: str
    display_name: str
    available: bool
    executable: str | None
    version: str | None
    verification_status: str
    capabilities: ProviderCapabilities
    detail: str = ""
    registration: dict[str, Any] | None = None
    discovery_state: str = "unavailable"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class CodexCommandAdapter(CliProvider):
    def __init__(self, executable: str, registration: dict[str, Any]) -> None:
        resolved = str(Path(executable).resolve(strict=True))
        super().__init__(
            (resolved, "{prompt}"),
            provider_name="codex-command",
            **_cli_registration_arguments(registration),
        )
        self.executable = resolved
        self.executable_sha256 = str(registration["executable_sha256"])
        self.registration = dict(registration)
        self.instance_id = uuid.uuid4().hex
        self.validate()

    def build_command(self, request: AgentRequest) -> list[str]:
        schema_path = request.stdout_path.parent / "provider-output-schema.json"
        schema_path.write_text(json.dumps(_domain_schema(request.role)), encoding="utf-8")
        prompt = request.prompt_path.read_text(encoding="utf-8")
        return [
            self.executable,
            "exec",
            "--ephemeral",
            "--sandbox",
            "workspace-write",
            "--output-schema",
            str(schema_path),
            prompt,
        ]


class ClaudeCommandAdapter(CliProvider):
    """Claude CLI adapter. Implemented against documented flags; locally unverified."""

    def __init__(self, executable: str, registration: dict[str, Any]) -> None:
        resolved = str(Path(executable).resolve(strict=True))
        super().__init__(
            (resolved, "{prompt}"),
            provider_name="claude-command",
            **_cli_registration_arguments(registration),
        )
        self.executable = resolved
        self.executable_sha256 = str(registration["executable_sha256"])
        self.registration = dict(registration)
        self.instance_id = uuid.uuid4().hex
        self.validate()

    def build_command(self, request: AgentRequest) -> list[str]:
        prompt = request.prompt_path.read_text(encoding="utf-8")
        return [
            self.executable,
            "--output-format",
            "json",
            "--json-schema",
            json.dumps(_domain_schema(request.role), separators=(",", ":")),
            "-p",
            prompt,
        ]

    def run(self, request: AgentRequest) -> ProcessResult:
        raw_path = request.stdout_path.with_suffix(".envelope.json")
        raw_request = AgentRequest(
            request.role,
            request.prompt_path,
            request.workspace,
            request.timeout_seconds,
            raw_path,
            request.stderr_path,
            request.reasoning_level,
            request.on_process_started,
            request.on_process_owned,
        )
        result = super().run(raw_request)
        if result.exit_code:
            return ProcessResult(
                result.exit_code,
                request.stdout_path,
                request.stderr_path,
                result.process_id,
                result.timed_out,
            )
        try:
            envelope = json.loads(raw_path.read_text(encoding="utf-8"))
            domain = envelope.get("structured_output", envelope.get("result"))
            if isinstance(domain, str):
                domain = json.loads(domain)
            if not isinstance(domain, dict):
                raise ValueError("Claude envelope contains no domain result")
            request.stdout_path.write_text(json.dumps(domain), encoding="utf-8")
            return ProcessResult(
                0, request.stdout_path, request.stderr_path, result.process_id, output=domain
            )
        except (json.JSONDecodeError, OSError, ValueError) as error:
            request.stdout_path.write_text("", encoding="utf-8")
            request.stderr_path.write_text(
                f"invalid Claude result envelope: {error}", encoding="utf-8"
            )
            return ProcessResult(65, request.stdout_path, request.stderr_path, result.process_id)


class ProviderDiscovery:
    def __init__(
        self,
        configured_paths: dict[str, str] | None = None,
        registrations: dict[str, dict[str, Any]] | None = None,
    ) -> None:
        self.configured_paths = configured_paths or {}
        self.registrations = registrations or {}

    def discover(self) -> list[ProviderDiagnostic]:
        return [
            self._command(
                "codex",
                "Codex command",
                ("codex", "codex.exe"),
                "implemented; local execution requires authenticated CLI",
            ),
            self._command(
                "claude",
                "Claude Code command",
                ("claude", "claude.exe"),
                "implemented; not verified on this machine",
            ),
            self._ollama(),
            ProviderDiagnostic(
                "mock",
                "Deterministic mock",
                True,
                None,
                "built-in",
                "verified",
                ProviderCapabilities(local_only=True, streaming=False),
                "Always available for diagnostics and demonstrations.",
            ),
        ]

    def _command(
        self,
        identifier: str,
        display_name: str,
        candidates: tuple[str, ...],
        verification: str,
    ) -> ProviderDiagnostic:
        configured = self.configured_paths.get(identifier)
        executable = configured if configured and Path(configured).is_file() else None
        if executable is None:
            executable = next(
                (path for candidate in candidates if (path := shutil.which(candidate))),
                None,
            )
        registration = self.registrations.get(identifier)
        valid, detail = _validate_discovery_registration(
            identifier, executable, registration
        )
        return ProviderDiagnostic(
            identifier,
            display_name,
            valid,
            executable,
            (
                str(registration.get("qualified_version"))
                if valid and registration
                and registration.get("qualified_version") is not None
                else None
            ),
            verification if valid else "blocked",
            ProviderCapabilities(),
            detail,
            dict(registration) if valid and registration else None,
            "qualified" if valid and registration and registration.get("qualified_version")
            else "registered" if valid else "blocked" if executable else "unavailable",
        )

    def _ollama(self) -> ProviderDiagnostic:
        executable = self.configured_paths.get("ollama") or shutil.which("ollama")
        return ProviderDiagnostic(
            "ollama",
            "Ollama local models",
            bool(executable),
            executable,
            None,
            "adapter verified with deterministic client; local service not exercised"
            if not executable
            else "executable detected; health check required before use",
            ProviderCapabilities(local_only=True, streaming=False),
            "" if executable else "Ollama is optional and was not found.",
            None,
            "configured" if executable else "unavailable",
        )


@dataclass(frozen=True, slots=True)
class RoutingRequest:
    role: str
    risk: str
    component: str
    previous_provider_ids: frozenset[str] = field(default_factory=frozenset)
    qwen_authored: bool = False


@dataclass(frozen=True, slots=True)
class RoutingDecision:
    provider_id: str
    reasons: list[str]


def route_provider(
    request: RoutingRequest, providers: list[ProviderDiagnostic]
) -> RoutingDecision:
    available = [provider for provider in providers if provider.available]
    if not available:
        raise RuntimeError("no provider is available")
    candidates = [
        provider
        for provider in available
        if provider.provider_id not in request.previous_provider_ids
        and _supports_role(provider.capabilities, request.role)
    ]
    if request.role in {"reviewer", "post_repair_reviewer"} and not candidates:
        raise RuntimeError("no independent reviewer is available")
    if not candidates:
        raise RuntimeError(f"no provider can perform role: {request.role}")
    strength = {"mock": 0, "ollama": 1, "claude": 2, "codex": 2}
    candidates.sort(key=lambda item: (-strength.get(item.provider_id, 0), item.provider_id))
    chosen = candidates[0]
    reasons = [
        f"provider is available and supports {request.role}",
        "provider identity has not participated in an incompatible prior role",
    ]
    if request.qwen_authored:
        if chosen.provider_id == "ollama":
            raise RuntimeError("Qwen-authored work requires a non-Qwen independent reviewer")
        reasons.append("non-Qwen reviewer required for Qwen-authored work")
    if request.risk.lower() in {"high", "critical"}:
        reasons.append("strongest available independent provider selected for high risk")
    return RoutingDecision(chosen.provider_id, reasons)


def _supports_role(capabilities: ProviderCapabilities, role: str) -> bool:
    if role == "builder":
        return capabilities.author
    if role in {"reviewer", "post_repair_reviewer"}:
        return capabilities.reviewer
    if role == "repairer":
        return capabilities.repairer
    return False


def create_provider_registration(
    provider_id: str,
    executable: Path,
    *,
    authorized_by: str,
) -> dict[str, Any]:
    configured = executable.resolve(strict=True)
    capabilities = asdict(ProviderCapabilities())
    launcher = configured
    script: Path | None = None
    if configured.suffix.casefold() in {".cmd", ".bat"}:
        script = configured
        launcher = Path(os.environ.get("COMSPEC", r"C:\Windows\System32\cmd.exe")).resolve(
            strict=True
        )
    launcher_content = launcher.read_bytes()
    invocation = (
        [str(launcher), "/d", "/c", str(script), "{prompt}"]
        if script is not None
        else [str(launcher), "{prompt}"]
    )
    registration: dict[str, Any] = {
        "trusted_registration_id": f"keeper-provider:{provider_id}:v1",
        "registration_version": "1",
        "logical_provider_id": provider_id,
        "provider_name": f"{provider_id}-command",
        "canonical_executable_path": str(configured),
        "launcher_path": str(launcher),
        "launcher_sha256": hashlib.sha256(launcher_content).hexdigest(),
        "launcher_size": len(launcher_content),
        "launcher_registration_id": f"keeper-launcher:{provider_id}:v1",
        "launcher_registration_version": "1",
        "script_path": str(script) if script is not None else None,
        "script_sha256": (
            hashlib.sha256(script.read_bytes()).hexdigest() if script is not None else None
        ),
        "script_size": script.stat().st_size if script is not None else None,
        "script_registration_id": (
            f"keeper-script:{provider_id}:v1" if script is not None else None
        ),
        "script_registration_version": "1" if script is not None else None,
        "invocation_shape": invocation,
        "working_directory_policy": "task-worktree",
        "allowed_environment": "keeper-filtered",
        "endpoint_identity": "local-process",
        "authentication_mode": "external-cli-session",
        "capability_set": capabilities,
        "provider_policy": "registered-command",
        "independence_classification": "role-enforced",
        "registration_status": "active",
        "authorized_by": authorized_by,
        "authorized_at": datetime.now(UTC).isoformat(),
        "revoked_at": None,
    }
    registration["executable_sha256"] = registration["launcher_sha256"]
    registration["executable_size"] = registration["launcher_size"]
    registration["configuration_digest"] = _registration_configuration_digest(
        registration
    )
    return registration


def _validate_discovery_registration(
    provider_id: str,
    executable: str | None,
    registration: dict[str, Any] | None,
) -> tuple[bool, str]:
    if executable is None:
        return False, "Executable was not found; configure its full path in Settings."
    if not isinstance(registration, dict):
        return False, "Configured provider has no immutable registration."
    required = {
        "trusted_registration_id", "registration_version", "logical_provider_id",
        "provider_name", "canonical_executable_path", "launcher_path",
        "launcher_sha256", "launcher_size", "configuration_digest",
        "authentication_mode", "capability_set", "provider_policy",
        "independence_classification", "registration_status", "authorized_by",
        "authorized_at",
    }
    if any(key not in registration for key in required):
        return False, "Provider registration is malformed or incomplete."
    if (
        registration.get("logical_provider_id") != provider_id
        or registration.get("registration_status") != "active"
        or registration.get("revoked_at") is not None
    ):
        return False, "Provider registration is stale, revoked, or mismatched."
    if registration.get("configuration_digest") != _registration_configuration_digest(
        registration
    ):
        return False, "Provider registration configuration digest is stale."
    try:
        configured = Path(executable).resolve(strict=True)
        if configured != Path(str(registration["canonical_executable_path"])).resolve(
            strict=True
        ):
            return False, "Configured provider path differs from registration."
        launcher = Path(str(registration["launcher_path"])).resolve(strict=True)
        launcher_content = launcher.read_bytes()
        if (
            hashlib.sha256(launcher_content).hexdigest()
            != registration["launcher_sha256"]
            or len(launcher_content) != registration["launcher_size"]
        ):
            return False, "Registered provider launcher identity changed."
        script_path = registration.get("script_path")
        if script_path is not None:
            script = Path(str(script_path)).resolve(strict=True)
            script_content = script.read_bytes()
            if (
                script != configured
                or hashlib.sha256(script_content).hexdigest()
                != registration.get("script_sha256")
                or len(script_content) != registration.get("script_size")
            ):
                return False, "Registered provider script identity changed."
    except (OSError, TypeError, ValueError):
        return False, "Provider registration could not be validated."
    return True, "Immutable registration validated; discovery did not execute provider code."


def _registration_configuration_digest(registration: dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(
            {
                "provider_id": registration.get("logical_provider_id"),
                "invocation_shape": registration.get("invocation_shape"),
                "launcher_sha256": registration.get("launcher_sha256"),
                "script_sha256": registration.get("script_sha256"),
                "working_directory_policy": registration.get(
                    "working_directory_policy"
                ),
                "allowed_environment": registration.get("allowed_environment"),
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


def _cli_registration_arguments(registration: dict[str, Any]) -> dict[str, Any]:
    return {
        "expected_executable_sha256": registration.get("launcher_sha256"),
        "expected_executable_size": registration.get("launcher_size"),
        "registration_id": registration.get("trusted_registration_id"),
        "registration_version": registration.get("registration_version"),
        "configuration_digest": registration.get("configuration_digest"),
        "expected_script_sha256": registration.get("script_sha256"),
        "expected_script_size": registration.get("script_size"),
        "script_registration_id": registration.get("script_registration_id"),
        "script_registration_version": registration.get("script_registration_version"),
    }


def _domain_schema(role: str) -> dict[str, Any]:
    properties: dict[str, Any] = {
        "status": {"type": "string", "enum": ["completed", "resolved"]},
        "files_changed": {"type": "array", "items": {"type": "string"}},
    }
    required = ["status", "files_changed"]
    if role in {"reviewer", "post_repair_reviewer"}:
        properties["findings"] = {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["finding_id", "severity", "title", "description"],
                "properties": {
                    "finding_id": {"type": "string"},
                    "severity": {
                        "type": "string",
                        "enum": ["Critical", "High", "Medium", "Low", "Minor"],
                    },
                    "title": {"type": "string"},
                    "description": {"type": "string"},
                    "file": {"type": ["string", "null"]},
                    "line": {"type": ["integer", "null"]},
                },
                "additionalProperties": False,
            },
        }
        required.append("findings")
    if role == "post_repair_reviewer":
        properties["dispositions"] = {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["finding_id", "status", "justification"],
                "properties": {
                    "finding_id": {"type": "string"},
                    "status": {"type": "string", "enum": ["resolved", "open"]},
                    "justification": {"type": "string"},
                },
                "additionalProperties": False,
            },
        }
        required.append("dispositions")
    return {
        "type": "object",
        "x-keeper-role": role,
        "required": required,
        "properties": properties,
        "additionalProperties": False,
    }
