from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import uuid
from datetime import UTC, datetime
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable

from keeper.providers.base import AgentRequest, ProcessResult
from keeper.providers.codex_cli import CliProvider

REGISTRATION_SCHEMA_VERSION = 2
_SHA256_LENGTH = 64
_REGISTRATION_FIELDS = {
    "registration_schema_version",
    "trusted_registration_id",
    "registration_version",
    "logical_provider_id",
    "provider_name",
    "provider_type",
    "canonical_executable_path",
    "executable_sha256",
    "executable_size",
    "executable_registration_id",
    "executable_registration_version",
    "launcher_path",
    "launcher_sha256",
    "launcher_size",
    "launcher_registration_id",
    "launcher_registration_version",
    "script_path",
    "script_sha256",
    "script_size",
    "script_registration_id",
    "script_registration_version",
    "invocation_shape",
    "working_directory_policy",
    "allowed_environment",
    "endpoint_identity",
    "authentication_mode",
    "authentication_profile",
    "capability_set",
    "provider_policy",
    "independence_classification",
    "role_eligibility",
    "model_or_service_identity",
    "qualified_version",
    "qualification_timestamp",
    "qualification_method",
    "qualification_result",
    "registration_lifecycle",
    "qualification_evidence_id",
    "qualification_evidence_digest",
    "qualifying_component_digests",
    "registration_status",
    "authorized_by",
    "authorized_at",
    "revoked_at",
    "expires_at",
    "configuration_digest",
}


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
    role_eligibility: tuple[str, ...] = ()
    independence_classification: str = ""
    provider_policy: str = ""

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
        qualification_evidence: dict[str, dict[str, Any]] | None = None,
        authority_verifier: Callable[[str, object], bool] | None = None,
    ) -> None:
        self.configured_paths = configured_paths or {}
        self.registrations = registrations or {}
        self.qualification_evidence = qualification_evidence or {}
        self.authority_verifier = authority_verifier

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
            identifier,
            executable,
            registration,
            self.qualification_evidence,
            self.authority_verifier,
        )
        capabilities = (
            ProviderCapabilities(**dict(registration["capability_set"]))
            if valid and registration
            else ProviderCapabilities(
                author=False,
                reviewer=False,
                repairer=False,
                structured_output=False,
                streaming=False,
                cancellation=False,
                usage_reporting=False,
                local_only=False,
            )
        )
        lifecycle = "BLOCKED"
        if isinstance(registration, dict):
            if (
                registration.get("registration_status") == "revoked"
                or registration.get("revoked_at") is not None
            ):
                lifecycle = "REVOKED"
            elif _registration_expired(registration):
                lifecycle = "EXPIRED"
            elif valid:
                lifecycle = str(registration.get("registration_lifecycle"))
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
            capabilities,
            detail,
            dict(registration) if valid and registration else None,
            lifecycle.casefold().replace("_", "-")
            if registration is not None
            else "blocked" if executable else "unavailable",
            tuple(registration.get("role_eligibility", ()))
            if valid and registration
            else (),
            str(registration.get("independence_classification", ""))
            if valid and registration
            else "",
            str(registration.get("provider_policy", ""))
            if valid and registration
            else "",
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
        and (
            provider.registration is None
            or provider.discovery_state == "qualified"
        )
        and _supports_role(provider, request.role)
        and (
            request.role not in {"reviewer", "post_repair_reviewer"}
            or provider.registration is None
            or provider.independence_classification == "independent-capable"
        )
        and not (
            provider.provider_id == "mock"
            and request.role in {"reviewer", "post_repair_reviewer"}
        )
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


def _supports_role(provider: ProviderDiagnostic, role: str) -> bool:
    if provider.registration is not None and role not in provider.role_eligibility:
        return False
    capabilities = provider.capabilities
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
    invocation_shape: list[str] | None = None,
    capabilities: ProviderCapabilities | None = None,
    role_eligibility: list[str] | None = None,
    independence_classification: str = "independent-capable",
) -> dict[str, Any]:
    configured = executable.resolve(strict=True)
    registration_nonce = uuid.uuid4().hex
    capability_values = asdict(capabilities or ProviderCapabilities())
    roles = role_eligibility if role_eligibility is not None else [
        "builder",
        "post_repair_reviewer",
        "repairer",
        "reviewer",
    ]
    launcher = configured
    script: Path | None = None
    if configured.suffix.casefold() in {".cmd", ".bat"}:
        script = configured
        launcher = Path(os.environ.get("COMSPEC", r"C:\Windows\System32\cmd.exe")).resolve(
            strict=True
        )
    executable_content = configured.read_bytes()
    launcher_content = launcher.read_bytes()
    invocation = invocation_shape or (
        [str(launcher), "/d", "/c", str(script), "{prompt}"]
        if script is not None
        else [str(launcher), "{prompt}"]
    )
    registration: dict[str, Any] = {
        "registration_schema_version": REGISTRATION_SCHEMA_VERSION,
        "trusted_registration_id": (
            f"keeper-provider:{provider_id}:v1:{registration_nonce}"
        ),
        "registration_version": "1",
        "logical_provider_id": provider_id,
        "provider_name": f"{provider_id}-command",
        "provider_type": "local-command",
        "canonical_executable_path": str(configured),
        "executable_sha256": hashlib.sha256(executable_content).hexdigest(),
        "executable_size": len(executable_content),
        "executable_registration_id": (
            f"keeper-executable:{provider_id}:v1:{registration_nonce}"
        ),
        "executable_registration_version": "1",
        "launcher_path": str(launcher),
        "launcher_sha256": hashlib.sha256(launcher_content).hexdigest(),
        "launcher_size": len(launcher_content),
        "launcher_registration_id": (
            f"keeper-launcher:{provider_id}:v1:{registration_nonce}"
        ),
        "launcher_registration_version": "1",
        "script_path": str(script) if script is not None else None,
        "script_sha256": (
            hashlib.sha256(script.read_bytes()).hexdigest() if script is not None else None
        ),
        "script_size": script.stat().st_size if script is not None else None,
        "script_registration_id": (
            f"keeper-script:{provider_id}:v1:{registration_nonce}"
            if script is not None
            else None
        ),
        "script_registration_version": "1" if script is not None else None,
        "invocation_shape": invocation,
        "working_directory_policy": "task-worktree",
        "allowed_environment": "keeper-filtered",
        "endpoint_identity": "local-process",
        "authentication_mode": "external-cli-session",
        "authentication_profile": f"external-session:{provider_id}",
        "capability_set": capability_values,
        "provider_policy": "registered-command",
        "independence_classification": independence_classification,
        "role_eligibility": roles,
        "model_or_service_identity": provider_id,
        "qualified_version": None,
        "qualification_timestamp": None,
        "qualification_method": "none",
        "qualification_result": "not-qualified",
        "registration_lifecycle": "REGISTERED_UNQUALIFIED",
        "qualification_evidence_id": None,
        "qualification_evidence_digest": None,
        "qualifying_component_digests": {
            "executable": hashlib.sha256(executable_content).hexdigest(),
            "launcher": hashlib.sha256(launcher_content).hexdigest(),
            "script": (
                hashlib.sha256(script.read_bytes()).hexdigest()
                if script is not None
                else None
            ),
        },
        "registration_status": "active",
        "authorized_by": authorized_by,
        "authorized_at": datetime.now(UTC).isoformat(),
        "revoked_at": None,
        "expires_at": None,
    }
    registration["configuration_digest"] = _registration_configuration_digest(
        registration
    )
    return registration


def _validate_discovery_registration(
    provider_id: str,
    executable: str | None,
    registration: dict[str, Any] | None,
    qualification_evidence: dict[str, dict[str, Any]] | None = None,
    authority_verifier: Callable[[str, object], bool] | None = None,
) -> tuple[bool, str]:
    if executable is None:
        return False, "Executable was not found; configure its full path in Settings."
    if not isinstance(registration, dict):
        return False, "Configured provider has no immutable registration."
    if set(registration) != _REGISTRATION_FIELDS:
        return False, "Provider registration is malformed or incomplete."
    if not _registration_types_valid(registration):
        return False, "Provider registration field types or values are invalid."
    if (
        registration.get("logical_provider_id") != provider_id
        or registration.get("registration_status") != "active"
        or registration.get("revoked_at") is not None
        or _registration_expired(registration)
    ):
        return False, "Provider registration is stale, revoked, or mismatched."
    if registration.get("configuration_digest") != _registration_configuration_digest(
        registration
    ):
        return False, "Provider registration configuration digest is stale."
    if not _qualification_is_consistent(
        registration, qualification_evidence or {}, authority_verifier
    ):
        return False, "Provider qualification authority is missing or inconsistent."
    try:
        configured = Path(executable).resolve(strict=True)
        registered_executable = Path(
            str(registration["canonical_executable_path"])
        ).resolve(strict=True)
        if configured != registered_executable or str(configured) != str(
            registration["canonical_executable_path"]
        ):
            return False, "Configured provider path differs from registration."
        executable_content = configured.read_bytes()
        if (
            hashlib.sha256(executable_content).hexdigest()
            != registration["executable_sha256"]
            or len(executable_content) != registration["executable_size"]
        ):
            return False, "Registered provider executable identity changed."
        launcher = Path(str(registration["launcher_path"])).resolve(strict=True)
        if str(launcher) != str(registration["launcher_path"]):
            return False, "Registered provider launcher path is not canonical."
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


def validate_provider_registration(
    provider_id: str,
    executable: str,
    registration: dict[str, Any],
    qualification_evidence: dict[str, dict[str, Any]] | None = None,
    authority_verifier: Callable[[str, object], bool] | None = None,
) -> tuple[bool, str]:
    """Validate the one canonical provider-registration schema without execution."""
    return _validate_discovery_registration(
        provider_id,
        executable,
        registration,
        qualification_evidence,
        authority_verifier,
    )


def canonical_provider_registration_digest(
    registration: dict[str, Any],
) -> str:
    """Return the deterministic digest over every authoritative schema field."""
    return _registration_configuration_digest(registration)


def qualification_evidence_digest(evidence: dict[str, Any]) -> str:
    value = {
        key: item
        for key, item in evidence.items()
        if key
        not in {
            "evidence_digest",
            "authority_schema_version",
            "authority_key_id",
            "authenticated_writer_proof",
        }
    }
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def apply_protected_qualification(
    registration: dict[str, Any],
    evidence: dict[str, Any],
    *,
    authority_verifier: Callable[[str, object], bool],
    expected_challenge: str,
    expected_authorization_reference: str,
) -> dict[str, Any]:
    updated = dict(registration)
    if updated.get("registration_lifecycle") != "REGISTERED_UNQUALIFIED":
        raise PermissionError("registration is not eligible for qualification")
    digest = qualification_evidence_digest(evidence)
    if not authority_verifier("provider-qualification", evidence):
        raise PermissionError("qualification writer authority is invalid")
    try:
        started_at = datetime.fromisoformat(str(evidence.get("started_at")))
        finished_at = datetime.fromisoformat(str(evidence.get("finished_at")))
    except ValueError as error:
        raise PermissionError("qualification chronology is invalid") from error
    if (
        started_at.tzinfo is None
        or finished_at.tzinfo is None
        or finished_at < started_at
        or not isinstance(evidence.get("id"), str)
        or not evidence["id"]
        or evidence.get("qualification_method") != "protected-registered-launch"
        or evidence.get("event_challenge") != expected_challenge
        or evidence.get("authorization_reference")
        != expected_authorization_reference
        or evidence.get("qualification_command")
        != [updated.get("canonical_executable_path"), "--version"]
        or evidence.get("command_digest")
        != hashlib.sha256(
            json.dumps(
                [updated.get("canonical_executable_path"), "--version"]
            ).encode("utf-8")
        ).hexdigest()
        or not isinstance(evidence.get("provider_instance_id"), str)
        or not evidence["provider_instance_id"]
        or not isinstance(evidence.get("provider_run_id"), str)
        or not evidence["provider_run_id"]
        or not isinstance(evidence.get("authorized_by"), str)
        or not evidence["authorized_by"]
        or not isinstance(evidence.get("ownership"), dict)
        or not evidence["ownership"].get("launch_nonce")
        or evidence.get("evidence_digest") != digest
        or evidence.get("registration_id") != updated.get("trusted_registration_id")
        or evidence.get("registration_version") != updated.get("registration_version")
        or evidence.get("provider_id") != updated.get("logical_provider_id")
        or evidence.get("executable_sha256") != updated.get("executable_sha256")
        or evidence.get("launcher_sha256") != updated.get("launcher_sha256")
        or evidence.get("script_sha256") != updated.get("script_sha256")
        or evidence.get("exit_status") != 0
        or evidence.get("qualification_result") != "qualified"
        or not isinstance(evidence.get("normalized_version"), str)
        or not evidence["normalized_version"]
        or not _version_output_valid(
            str(updated.get("logical_provider_id")),
            str(evidence.get("normalized_version")),
        )
    ):
        raise PermissionError("protected qualification evidence is inconsistent")
    updated.update(
        {
            "qualified_version": evidence["normalized_version"],
            "qualification_timestamp": evidence["finished_at"],
            "qualification_method": "protected-registered-launch",
            "qualification_result": "qualified",
            "registration_lifecycle": "QUALIFIED",
            "qualification_evidence_id": evidence["id"],
            "qualification_evidence_digest": digest,
        }
    )
    updated["configuration_digest"] = _registration_configuration_digest(updated)
    return updated


def _qualification_is_consistent(
    registration: dict[str, Any],
    evidence_by_id: dict[str, dict[str, Any]],
    authority_verifier: Callable[[str, object], bool] | None,
) -> bool:
    if registration.get("registration_lifecycle") == "QUALIFICATION_FAILED":
        evidence_id = registration.get("qualification_evidence_id")
        evidence = evidence_by_id.get(str(evidence_id))
        return bool(
            isinstance(evidence, dict)
            and authority_verifier is not None
            and authority_verifier("provider-qualification", evidence)
            and _qualification_start_is_valid(
                registration, evidence, evidence_by_id, authority_verifier
            )
            and evidence.get("evidence_digest")
            == qualification_evidence_digest(evidence)
            == registration.get("qualification_evidence_digest")
            and evidence.get("registration_id")
            == registration.get("trusted_registration_id")
            and evidence.get("provider_id")
            == registration.get("logical_provider_id")
            and evidence.get("qualification_result") == "failed"
            and (
                evidence.get("exit_status") != 0
                or not _version_output_valid(
                    str(registration.get("logical_provider_id")),
                    str(evidence.get("normalized_version", "")),
                )
            )
        )
    if registration.get("registration_lifecycle") != "QUALIFIED":
        return registration.get("qualification_result") in {
            "not-qualified",
            "pending",
        }
    evidence_id = registration.get("qualification_evidence_id")
    if not isinstance(evidence_id, str):
        return False
    evidence = evidence_by_id.get(evidence_id)
    if (
        not isinstance(evidence, dict)
        or authority_verifier is None
        or not authority_verifier("provider-qualification", evidence)
        or not _qualification_start_is_valid(
            registration, evidence, evidence_by_id, authority_verifier
        )
    ):
        return False
    try:
        expected = apply_protected_qualification(
            {
                **registration,
                "qualified_version": None,
                "qualification_timestamp": None,
                "qualification_method": "none",
                "qualification_result": "not-qualified",
                "registration_lifecycle": "REGISTERED_UNQUALIFIED",
                "qualification_evidence_id": None,
                "qualification_evidence_digest": None,
                "configuration_digest": "",
            },
            evidence,
            authority_verifier=authority_verifier,
            expected_challenge=str(evidence["event_challenge"]),
            expected_authorization_reference=str(
                evidence["authorization_reference"]
            ),
        )
    except (KeyError, PermissionError, TypeError):
        return False
    return all(
        expected.get(key) == registration.get(key)
        for key in (
            "qualified_version",
            "qualification_timestamp",
            "qualification_method",
            "qualification_result",
            "registration_lifecycle",
            "qualification_evidence_id",
            "qualification_evidence_digest",
        )
    )


def _qualification_start_is_valid(
    registration: dict[str, Any],
    evidence: dict[str, Any],
    evidence_by_id: dict[str, dict[str, Any]],
    authority_verifier: Callable[[str, object], bool],
) -> bool:
    reference = evidence.get("authorization_reference")
    start = evidence_by_id.get(str(reference))
    return bool(
        isinstance(start, dict)
        and authority_verifier("provider-qualification-start", start)
        and start.get("id") == reference
        and start.get("registration_id")
        == registration.get("trusted_registration_id")
        and start.get("provider_id") == registration.get("logical_provider_id")
        and start.get("event_challenge") == evidence.get("event_challenge")
    )


def _version_output_valid(provider_id: str, value: str) -> bool:
    allowed_names = {
        "codex": r"(?:codex|controlled-provider|protected-version)",
        "claude": r"(?:claude|controlled-provider|protected-version)",
    }
    name = allowed_names.get(provider_id)
    return bool(
        name
        and re.fullmatch(
            rf"(?i){name}(?:[\s_-]+(?:cli[\s_-]+)?)?v?\d+\.\d+(?:\.\d+)?(?:[-+.\w ]*)",
            value.strip(),
        )
    )


def qualified_version_is_valid(provider_id: str, value: str) -> bool:
    return _version_output_valid(provider_id, value)


def _registration_configuration_digest(registration: dict[str, Any]) -> str:
    authority = {
        key: registration.get(key)
        for key in sorted(_REGISTRATION_FIELDS - {"configuration_digest"})
    }
    return hashlib.sha256(
        json.dumps(authority, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _registration_types_valid(registration: dict[str, Any]) -> bool:
    string_fields = {
        "trusted_registration_id",
        "registration_version",
        "logical_provider_id",
        "provider_name",
        "provider_type",
        "canonical_executable_path",
        "executable_registration_id",
        "executable_registration_version",
        "launcher_path",
        "launcher_registration_id",
        "launcher_registration_version",
        "working_directory_policy",
        "allowed_environment",
        "endpoint_identity",
        "authentication_mode",
        "authentication_profile",
        "provider_policy",
        "independence_classification",
        "model_or_service_identity",
        "qualification_method",
        "qualification_result",
        "registration_status",
        "authorized_by",
        "authorized_at",
        "configuration_digest",
    }
    if registration.get("registration_schema_version") != REGISTRATION_SCHEMA_VERSION:
        return False
    if any(
        not isinstance(registration.get(key), str) or not registration[key]
        for key in string_fields
    ):
        return False
    if registration["provider_type"] != "local-command":
        return False
    if registration["endpoint_identity"] != "local-process":
        return False
    if registration["authentication_mode"] != "external-cli-session":
        return False
    if registration["provider_policy"] != "registered-command":
        return False
    if registration["independence_classification"] not in {
        "authoring-only",
        "independent-capable",
    }:
        return False
    if registration["registration_status"] not in {"active", "revoked"}:
        return False
    if registration["qualification_result"] not in {
        "qualified",
        "not-qualified",
        "failed",
        "pending",
    }:
        return False
    if registration["qualification_method"] not in {
        "protected-registered-launch",
        "none",
    }:
        return False
    for key in ("executable_sha256", "launcher_sha256", "configuration_digest"):
        value = registration.get(key)
        if (
            not isinstance(value, str)
            or len(value) != _SHA256_LENGTH
            or any(character not in "0123456789abcdef" for character in value)
        ):
            return False
    if any(
        not isinstance(registration.get(key), int) or registration[key] < 0
        for key in ("executable_size", "launcher_size")
    ):
        return False
    capabilities = registration.get("capability_set")
    if (
        not isinstance(capabilities, dict)
        or set(capabilities) != set(asdict(ProviderCapabilities()))
        or any(type(value) is not bool for value in capabilities.values())
    ):
        return False
    roles = registration.get("role_eligibility")
    if (
        not isinstance(roles, list)
        or any(not isinstance(item, str) or not item for item in roles)
        or roles != sorted(roles)
        or len(roles) != len(set(roles))
        or any(
            item
            not in {
                "builder",
                "reviewer",
                "repairer",
                "post_repair_reviewer",
            }
            for item in roles
        )
    ):
        return False
    required_capability = {
        "builder": "author",
        "reviewer": "reviewer",
        "repairer": "repairer",
        "post_repair_reviewer": "reviewer",
    }
    if any(
        capabilities[required_capability[role]] is not True for role in roles
    ):
        return False
    if any(
        role in {"reviewer", "post_repair_reviewer"}
        for role in roles
    ) and registration["independence_classification"] != "independent-capable":
        return False
    invocation = registration.get("invocation_shape")
    if (
        not isinstance(invocation, list)
        or not invocation
        or any(not isinstance(item, str) or not item for item in invocation)
    ):
        return False
    digests = registration.get("qualifying_component_digests")
    if not isinstance(digests, dict) or set(digests) != {
        "executable",
        "launcher",
        "script",
    }:
        return False
    if (
        digests.get("executable") != registration.get("executable_sha256")
        or digests.get("launcher") != registration.get("launcher_sha256")
        or digests.get("script") != registration.get("script_sha256")
    ):
        return False
    script_path = registration.get("script_path")
    script_fields = (
        registration.get("script_sha256"),
        registration.get("script_size"),
        registration.get("script_registration_id"),
        registration.get("script_registration_version"),
    )
    if script_path is None:
        if any(value is not None for value in script_fields):
            return False
        if invocation[0] != registration.get("launcher_path"):
            return False
    elif (
        not isinstance(script_path, str)
        or not script_path
        or not isinstance(script_fields[0], str)
        or len(script_fields[0]) != _SHA256_LENGTH
        or not isinstance(script_fields[1], int)
        or script_fields[1] < 0
        or not isinstance(script_fields[2], str)
        or not script_fields[2]
        or not isinstance(script_fields[3], str)
        or not script_fields[3]
    ):
        return False
    elif invocation[:4] != [
        registration.get("launcher_path"),
        "/d",
        "/c",
        script_path,
    ]:
        return False
    qualified = registration.get("qualification_result") == "qualified"
    qualification_values = (
        registration.get("qualified_version"),
        registration.get("qualification_timestamp"),
    )
    if qualified != all(isinstance(value, str) and value for value in qualification_values):
        return False
    lifecycle = registration.get("registration_lifecycle")
    expected_lifecycle = {
        "qualified": "QUALIFIED",
        "not-qualified": "REGISTERED_UNQUALIFIED",
        "pending": "QUALIFICATION_PENDING",
        "failed": "QUALIFICATION_FAILED",
    }.get(str(registration.get("qualification_result")))
    if lifecycle != expected_lifecycle:
        return False
    evidence_values = (
        registration.get("qualification_evidence_id"),
        registration.get("qualification_evidence_digest"),
    )
    evidence_required = registration.get("qualification_result") in {
        "qualified",
        "failed",
    }
    if evidence_required != all(
        isinstance(value, str) and value for value in evidence_values
    ):
        return False
    for key in ("revoked_at", "expires_at"):
        if registration.get(key) is not None and not isinstance(
            registration.get(key), str
        ):
            return False
    try:
        authorized = datetime.fromisoformat(str(registration["authorized_at"]))
        if authorized.tzinfo is None:
            return False
        if registration.get("qualification_timestamp"):
            qualified_at = datetime.fromisoformat(
                str(registration["qualification_timestamp"])
            )
            if qualified_at.tzinfo is None:
                return False
        if registration.get("expires_at"):
            datetime.fromisoformat(str(registration["expires_at"]))
    except ValueError:
        return False
    return True


def _registration_expired(registration: dict[str, Any]) -> bool:
    expires_at = registration.get("expires_at")
    if not isinstance(expires_at, str):
        return False
    try:
        expiry = datetime.fromisoformat(expires_at)
    except ValueError:
        return True
    if expiry.tzinfo is None:
        return True
    return expiry <= datetime.now(UTC)


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
