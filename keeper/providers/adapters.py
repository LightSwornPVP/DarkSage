from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import uuid
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

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class CodexCommandAdapter(CliProvider):
    def __init__(self, executable: str) -> None:
        resolved = str(Path(executable).resolve(strict=True))
        digest = hashlib.sha256(Path(resolved).read_bytes()).hexdigest()
        super().__init__(
            (resolved, "{prompt}"),
            provider_name="codex-command",
            expected_executable_sha256=digest,
        )
        self.executable = resolved
        self.executable_sha256 = digest
        self.instance_id = uuid.uuid4().hex

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

    def __init__(self, executable: str) -> None:
        resolved = str(Path(executable).resolve(strict=True))
        digest = hashlib.sha256(Path(resolved).read_bytes()).hexdigest()
        super().__init__(
            (resolved, "{prompt}"),
            provider_name="claude-command",
            expected_executable_sha256=digest,
        )
        self.executable = resolved
        self.executable_sha256 = digest
        self.instance_id = uuid.uuid4().hex

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
    def __init__(self, configured_paths: dict[str, str] | None = None) -> None:
        self.configured_paths = configured_paths or {}

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
        version = _version(executable) if executable else None
        return ProviderDiagnostic(
            identifier,
            display_name,
            executable is not None,
            executable,
            version,
            verification,
            ProviderCapabilities(),
            "" if executable else "Executable was not found; configure its full path in Settings.",
        )

    def _ollama(self) -> ProviderDiagnostic:
        executable = self.configured_paths.get("ollama") or shutil.which("ollama")
        return ProviderDiagnostic(
            "ollama",
            "Ollama local models",
            bool(executable),
            executable,
            _version(executable) if executable else None,
            "adapter verified with deterministic client; local service not exercised"
            if not executable
            else "executable detected; health check required before use",
            ProviderCapabilities(local_only=True, streaming=False),
            "" if executable else "Ollama is optional and was not found.",
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


def _version(executable: str) -> str | None:
    try:
        result = subprocess.run(
            [executable, "--version"],
            capture_output=True,
            text=True,
            shell=False,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    value = (result.stdout or result.stderr).strip().splitlines()
    return value[0][:200] if value else None


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
