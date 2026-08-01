from __future__ import annotations

import hashlib
import json
import secrets
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Callable, Protocol

from keeper.evidence_input import structured_digest, validate_provider_input
from keeper.authority_service.key_ring import ServiceKeyRing
from keeper.authority_service.protocol import (
    PROTOCOL_VERSION,
    Operation,
    Request,
)
from keeper.authority_service.provenance import AUDIT_REPORT_PURPOSE
from keeper.authority_service.store import AuthorityStore
from keeper.executive.founder_capability import (
    ProductionFounderCapabilityVerifier,
    TestFounderCapabilityVerifier,
    capability_digest,
    capability_signature_digest,
)
from keeper.providers.adapters import (
    apply_protected_qualification,
    canonical_provider_registration_digest,
    create_provider_registration,
    qualification_evidence_digest,
    qualified_version_is_valid,
    validate_provider_registration_contract,
)


SERVICE_VERSION = "1.6.2"
RESTORE_FENCE_LIFETIME = timedelta(minutes=2)


@dataclass(frozen=True, slots=True)
class QualificationObservation:
    provider_instance_id: str
    process_ownership: dict[str, Any]
    started_at: str
    finished_at: str
    exit_status: int
    raw_version_output: str
    failure_reason: str | None = None


@dataclass(frozen=True, slots=True)
class ProcessObservation:
    pid: int
    creation_time: str
    executable: str
    executable_sha256: str
    restricted: bool
    integrity_level: str
    job_confined: bool


@dataclass(frozen=True, slots=True)
class CompletionObservation:
    evidence_digest: str
    exit_status: int
    normalized_result: str
    finished_at: str


@dataclass(frozen=True, slots=True)
class ExecutionObservation:
    process_id: int
    exit_status: int
    timed_out: bool
    stdout_path: str
    stderr_path: str
    provider_evidence_digest: str
    finished_at: str


class TrustedObserver(Protocol):
    def qualify(
        self, registration: dict[str, Any], challenge: str
    ) -> QualificationObservation: ...

    def register_provider(
        self,
        provider_id: str,
        executable: Path,
        client_sid: str,
        *,
        executive_capabilities: list[str],
        project_types: list[str],
        effort_levels: list[str],
        pricing_authority: dict[str, Any],
    ) -> dict[str, Any]: ...

    def observe_process(
        self, attempt: dict[str, Any], pid: int
    ) -> ProcessObservation: ...

    def execute_provider(
        self,
        registration: dict[str, Any],
        attempt: dict[str, Any],
        on_started: Callable[[ProcessObservation], None],
    ) -> ExecutionObservation: ...

    def observe_completion(
        self, attempt: dict[str, Any]
    ) -> CompletionObservation: ...


class ProvenanceReporter(Protocol):
    def build(
        self,
        request: Request,
        client_sid: str,
        *,
        installed_package_version: str,
        authority_key_id: str,
        authority_key_version: int,
        database_path: Path,
        database_identity: dict[str, Any] | None,
    ) -> dict[str, Any]: ...


class AuthorityServiceCore:
    """Service-owned lifecycle authority; callers never supply signed records."""

    def __init__(
        self,
        root: Path,
        *,
        observer: TrustedObserver | None = None,
        provenance_reporter: ProvenanceReporter | None = None,
        founder_capability_verifier: (
            ProductionFounderCapabilityVerifier
            | TestFounderCapabilityVerifier
            | None
        ) = None,
    ) -> None:
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.store = AuthorityStore(self.root / "authority.db")
        self.store.migrate()
        self.keys = ServiceKeyRing(self.root / "keys")
        self.observer = observer
        self.provenance_reporter = provenance_reporter
        if founder_capability_verifier is not None and type(
            founder_capability_verifier
        ) not in {
            ProductionFounderCapabilityVerifier,
            TestFounderCapabilityVerifier,
        }:
            raise TypeError("Founder capability verifier type is not trusted")
        self.founder_capability_verifier = founder_capability_verifier

    def dispatch(self, request: Request, client_sid: str) -> dict[str, Any]:
        if not client_sid:
            raise PermissionError("authority client identity is missing")
        try:
            self.store.consume_request(
                request.request_id,
                request.operation_id,
                request.nonce,
                client_sid,
            )
        except PermissionError:
            self.store.audit(
                uuid.uuid4().hex,
                "request_rejected",
                client_sid,
                None,
                {"operation": request.operation.value, "reason": "replay"},
            )
            raise
        handlers = {
            Operation.DIAGNOSTICS: self._diagnostics,
            Operation.AUDIT_PROVENANCE: self._audit_provenance,
            Operation.REGISTER_PROVIDER: self._register_provider,
            Operation.BEGIN_QUALIFICATION: self._qualify_provider,
            Operation.FINALIZE_QUALIFICATION: self._internal_only,
            Operation.RESERVE_ATTEMPT: self._reserve_attempt,
            Operation.AUTHORIZE_PROJECT_LAUNCH: self._authorize_project_launch,
            Operation.REVOKE_PROJECT_LAUNCH: self._revoke_project_launch,
            Operation.BIND_PROVIDER_INPUT: self._bind_provider_input,
            Operation.EXECUTE_PROVIDER: self._execute_provider,
            Operation.RECORD_PROVIDER_START: self._record_provider_start,
            Operation.FINALIZE_COMPLETION: self._finalize_completion,
            Operation.QUERY_STATE: self._query_state,
            Operation.RECONCILE_EXECUTIVE_RESTORE: (
                self._reconcile_executive_restore
            ),
            Operation.BEGIN_EXECUTIVE_RESTORE_FENCE: (
                self._begin_executive_restore_fence
            ),
            Operation.CONFIRM_EXECUTIVE_RESTORE_FENCE: (
                self._confirm_executive_restore_fence
            ),
            Operation.COMPLETE_EXECUTIVE_RESTORE_FENCE: (
                self._complete_executive_restore_fence
            ),
            Operation.ABORT_EXECUTIVE_RESTORE_FENCE: (
                self._abort_executive_restore_fence
            ),
            Operation.RECOVER_EXECUTIVE_RESTORE_FENCE: (
                self._recover_executive_restore_fence
            ),
            Operation.VERIFY_EVIDENCE: self._verify_evidence,
            Operation.PAUSE_ATTEMPT: self._pause_attempt,
            Operation.RESUME_ATTEMPT: self._resume_attempt,
            Operation.CANCEL_ATTEMPT: self._cancel_attempt,
            Operation.REVOKE_REGISTRATION: self._revoke_registration,
            Operation.ROTATE_KEY: self._rotate_key,
            Operation.MIGRATE_LEGACY: self._migrate_legacy,
        }
        try:
            if request.operation == Operation.AUDIT_PROVENANCE:
                result = self._audit_provenance_request(
                    request, client_sid
                )
            else:
                result = handlers[request.operation](
                    request.payload, client_sid
                )
        except (OSError, PermissionError, RuntimeError, TypeError, ValueError) as error:
            self.store.audit(
                request.operation_id,
                request.operation.value,
                client_sid,
                None,
                {
                    "outcome": "rejected",
                    "error_type": type(error).__name__,
                },
            )
            raise
        self.store.audit(
            request.operation_id,
            request.operation.value,
            client_sid,
            _object_id(result),
            {"outcome": "accepted"},
        )
        return result

    def _audit_provenance_request(
        self, request: Request, client_sid: str
    ) -> dict[str, Any]:
        _exact(request.payload, set())
        if self.provenance_reporter is None:
            raise RuntimeError(
                "Authority provenance reporter is unavailable"
            )
        try:
            database_identity = self.store.schema_identity()
        except (FileNotFoundError, OSError, RuntimeError, ValueError):
            database_identity = None
        report = self.provenance_reporter.build(
            request,
            client_sid,
            installed_package_version=SERVICE_VERSION,
            authority_key_id=self.keys.current_key_id,
            authority_key_version=self.keys.current_version,
            database_path=self.store.path,
            database_identity=database_identity,
        )
        return {
            "report": self.keys.sign(AUDIT_REPORT_PURPOSE, report)
        }

    def _audit_provenance(
        self, payload: dict[str, Any], client_sid: str
    ) -> dict[str, Any]:
        raise RuntimeError(
            "Authority provenance requires authenticated request binding"
        )

    def _diagnostics(
        self, payload: dict[str, Any], client_sid: str
    ) -> dict[str, Any]:
        _exact(payload, set())
        allowed_evidence_root = getattr(
            self.observer, "allowed_evidence_root", None
        )
        return {
            "service_version": SERVICE_VERSION,
            "protocol_version": PROTOCOL_VERSION,
            "service_root": str(self.root),
            "service_key_id": self.keys.current_key_id,
            "service_key_version": self.keys.current_version,
            "client_sid": client_sid,
            "observer_available": self.observer is not None,
            "registrations": len(self.store.list_records("registrations")),
            "qualifications": len(self.store.list_records("qualifications")),
            "attempts": len(self.store.list_records("attempts")),
            "allowed_evidence_root": (
                str(allowed_evidence_root)
                if isinstance(allowed_evidence_root, Path)
                else None
            ),
            "client_exchange_root": (
                str(allowed_evidence_root.parent)
                if isinstance(allowed_evidence_root, Path)
                else None
            ),
        }

    def _authorize_project_launch(
        self, payload: dict[str, Any], client_sid: str
    ) -> dict[str, Any]:
        if set(payload) != {"founder_capability"}:
            raise PermissionError(
                "cryptographically verified Founder capability is required"
            )
        value = payload["founder_capability"]
        verifier = self.founder_capability_verifier
        if verifier is None or not isinstance(value, dict):
            raise PermissionError(
                "cryptographically verified Founder capability is required"
            )
        try:
            capability = verifier.verify(value)
        except (KeyError, PermissionError, TypeError, ValueError) as error:
            raise PermissionError(
                "Founder authorization capability authentication failed"
            ) from error
        now = datetime.now(UTC)
        expires_at = datetime.fromisoformat(capability.expires_at)
        issued_at = datetime.fromisoformat(capability.issued_at)
        if (
            expires_at <= now
            or issued_at > now
            or capability.authorization_kind != "PROJECT_LAUNCH"
            or capability.protected_action != "DELEGATE_CHARTER"
            or capability.usage != "ONE_TIME_GENERATION"
            or capability.authorization_generation != capability.charter_revision
            or capability.revocation_epoch
            != capability.authorization_generation - 1
        ):
            raise PermissionError("Founder authorization capability is stale or invalid")
        generation = capability.authorization_generation
        project_id = capability.project_id
        identifier = (
            f"launch-authorization:{project_id}:generation:{generation}"
        )
        capability_value_digest = capability_digest(capability)
        signature_digest = capability_signature_digest(capability)
        record = self.keys.sign(
            "project-launch-authorization",
            {
                "id": identifier,
                "kind": "project_launch_authorization",
                "schema_version": 2,
                "project_id": project_id,
                "charter_id": capability.charter_id,
                "charter_revision": capability.charter_revision,
                "delegation_id": capability.approval_record_id,
                "founder_approval_event_id": capability.approval_event_id,
                "founder_approval_event_digest": (
                    capability.approval_event_digest
                ),
                "founder_approval_digest": capability.approval_digest,
                "founder_authenticated_session_id": (
                    capability.founder_authenticated_session_id
                ),
                "founder_principal_sid": capability.founder_principal_sid,
                "founder_challenge_id": capability.challenge_id,
                "founder_challenge_proof_digest": (
                    capability.challenge_proof_digest
                ),
                "founder_action_digest": capability.action_digest,
                "founder_capability_id": capability.capability_id,
                "founder_capability_digest": capability_value_digest,
                "founder_capability_signature_digest": signature_digest,
                "founder_capability_issuer_id": capability.issuer_id,
                "founder_capability_issuer_key_id": capability.issuer_key_id,
                "authorization_generation": generation,
                "revocation_epoch": capability.revocation_epoch,
                "authorized_client_sid": client_sid,
                "expires_at": capability.expires_at,
                "authorized_at": capability.issued_at,
            },
        )
        durable = self.store.create_launch_authorization(
            identifier,
            generation,
            client_sid,
            record,
            {
                "capability_id": capability.capability_id,
                "project_id": project_id,
                "approval_record_id": capability.approval_record_id,
                "approval_event_id": capability.approval_event_id,
                "founder_session_id": (
                    capability.founder_authenticated_session_id
                ),
                "challenge_id": capability.challenge_id,
                "approval_digest": capability.approval_digest,
                "challenge_proof_digest": (
                    capability.challenge_proof_digest
                ),
                "capability_digest": capability_value_digest,
                "signature_digest": signature_digest,
                "generation": generation,
                "authorization_id": identifier,
            },
        )
        return {"authorization": durable}

    def _revoke_project_launch(
        self, payload: dict[str, Any], client_sid: str
    ) -> dict[str, Any]:
        _exact(payload, {"project_id", "authorization_generation"})
        project_id = _text(payload["project_id"], "project ID")
        generation = _positive_int(
            payload["authorization_generation"], "authorization generation"
        )
        identifier = (
            f"launch-authorization:{project_id}:generation:{generation}"
        )
        prior = self.store.get("launch_authorizations", identifier)
        if (
            prior is None
            or prior.get("authorized_client_sid") != client_sid
            or prior.get("authorization_generation") != generation
        ):
            raise PermissionError("launch authorization revocation is misbound")
        record = self.keys.sign(
            "project-launch-revocation",
            {
                **{key: value for key, value in prior.items() if key != "service_state"},
                "kind": "project_launch_revocation",
                "revocation_epoch": generation,
                "revoked_at": _now(),
            },
        )
        canceled = self.store.revoke_launch_authorization(
            identifier, generation, client_sid, record
        )
        return {
            "authorization_id": identifier,
            "revocation_epoch": generation,
            "canceled_attempt_ids": list(canceled),
        }

    def _register_provider(
        self, payload: dict[str, Any], client_sid: str
    ) -> dict[str, Any]:
        _exact(
            payload,
            {
                "provider_id",
                "executable",
                "executive_capabilities",
                "project_types",
                "effort_levels",
                "pricing_authority",
            },
        )
        provider_id = _choice(payload["provider_id"], {"codex", "claude"})
        executable = Path(_text(payload["executable"], "provider executable"))
        executive_capabilities = payload["executive_capabilities"]
        project_types = payload["project_types"]
        effort_levels = payload["effort_levels"]
        pricing_authority = payload["pricing_authority"]
        if self.observer is not None and hasattr(
            self.observer, "register_provider"
        ):
            registration = self.observer.register_provider(
                provider_id,
                executable,
                client_sid,
                executive_capabilities=executive_capabilities,
                project_types=project_types,
                effort_levels=effort_levels,
                pricing_authority=pricing_authority,
            )
        else:
            registration = create_provider_registration(
                provider_id,
                executable,
                authorized_by=client_sid,
                executive_capabilities=executive_capabilities,
                project_types=project_types,
                effort_levels=effort_levels,
                pricing_authority=pricing_authority,
            )
        identifier = str(registration["trusted_registration_id"])
        self.store.insert("registrations", identifier, "REGISTERED_UNQUALIFIED", registration)
        return {"registration": registration, "registration_id": identifier}

    def _qualify_provider(
        self, payload: dict[str, Any], client_sid: str
    ) -> dict[str, Any]:
        _exact(payload, {"registration_id"})
        if self.observer is None:
            raise RuntimeError("authority provider observer is unavailable")
        identifier = _text(payload["registration_id"], "registration ID")
        registration = self.store.get("registrations", identifier)
        if (
            registration is None
            or registration.pop("service_state", None) != "REGISTERED_UNQUALIFIED"
        ):
            raise PermissionError("registration is not eligible for qualification")
        valid, detail = validate_provider_registration_contract(registration)
        if not valid:
            raise PermissionError(
                f"registration contract is incomplete or invalid: {detail}"
            )
        qualification_id = f"provider-qualification:{uuid.uuid4().hex}"
        challenge = secrets.token_hex(32)
        start = self.keys.sign(
            "provider-qualification-start",
            {
                "id": f"{qualification_id}:started",
                "kind": "provider_qualification_started",
                "schema_version": 2,
                "registration_id": identifier,
                "provider_id": registration["logical_provider_id"],
                "authorization_reference": client_sid,
                "event_challenge": challenge,
                "started_at": _now(),
            },
        )
        self.store.insert(
            "qualifications",
            qualification_id,
            "EXECUTION_STARTED",
            {"start": start},
            registration_id=identifier,
            challenge=challenge,
        )
        observation = self.observer.qualify(registration, challenge)
        normalized = (
            observation.raw_version_output.splitlines()[0].strip()[:200]
            if observation.raw_version_output
            else ""
        )
        command = [registration["canonical_executable_path"], "--version"]
        evidence: dict[str, Any] = {
            "id": qualification_id,
            "kind": "provider_qualification",
            "schema_version": 2,
            "registration_id": identifier,
            "registration_version": registration["registration_version"],
            "provider_id": registration["logical_provider_id"],
            "provider_instance_id": observation.provider_instance_id,
            "provider_run_id": qualification_id,
            "executable_sha256": registration["executable_sha256"],
            "launcher_sha256": registration["launcher_sha256"],
            "script_sha256": registration["script_sha256"],
            "qualification_command": command,
            "command_digest": hashlib.sha256(
                json.dumps(command).encode("utf-8")
            ).hexdigest(),
            "started_at": observation.started_at,
            "finished_at": observation.finished_at,
            "exit_status": observation.exit_status,
            "raw_version_output": observation.raw_version_output,
            "normalized_version": normalized,
            "qualification_method": "authority-service-restricted-launch",
            "qualification_result": (
                "qualified"
                if observation.exit_status == 0
                and qualified_version_is_valid(
                    str(registration["logical_provider_id"]), normalized
                )
                and observation.process_ownership.get("restricted") is True
                and observation.process_ownership.get("job_confined") is True
                else "failed"
            ),
            "authorized_by": client_sid,
            "authorization_reference": start["id"],
            "event_challenge": challenge,
            "ownership": observation.process_ownership,
            "failure_reason": observation.failure_reason,
        }
        # Preserve the legacy digest contract while changing the owning writer.
        evidence["qualification_method"] = "protected-registered-launch"
        evidence["evidence_digest"] = qualification_evidence_digest(evidence)
        evidence = self.keys.sign("provider-qualification", evidence)
        state = (
            "QUALIFIED"
            if evidence["qualification_result"] == "qualified"
            else "QUALIFICATION_FAILED"
        )
        self.store.transition(
            "qualifications",
            qualification_id,
            "EXECUTION_STARTED",
            state,
            {"start": start, "evidence": evidence},
        )
        if state == "QUALIFIED":
            updated = apply_protected_qualification(
                registration,
                evidence,
                authority_verifier=self.keys.verify,
                expected_challenge=challenge,
                expected_authorization_reference=str(start["id"]),
            )
        else:
            updated = {
                **registration,
                "qualification_timestamp": observation.finished_at,
                "qualification_method": "protected-registered-launch",
                "qualification_result": "failed",
                "registration_lifecycle": "QUALIFICATION_FAILED",
                "qualification_evidence_id": qualification_id,
                "qualification_evidence_digest": evidence["evidence_digest"],
            }
            updated["configuration_digest"] = canonical_provider_registration_digest(
                updated
            )
        self.store.transition(
            "registrations",
            identifier,
            "REGISTERED_UNQUALIFIED",
            state,
            updated,
        )
        return {
            "registration": updated,
            "qualification": evidence,
            "qualification_start": start,
        }

    def _reserve_attempt(
        self, payload: dict[str, Any], client_sid: str
    ) -> dict[str, Any]:
        fields = {
            "registration_id",
            "keeper_run_id",
            "task_id",
            "stage_id",
            "role",
            "attempt_number",
            "provider_run_id",
            "provider_instance_id",
            "evidence_path",
            "prompt_path",
            "stdout_path",
            "stderr_path",
            "workspace",
            "timeout_seconds",
            "reasoning_level",
            "environment",
            "launch_authorization_id",
            "authorization_generation",
            "delegation_id",
            "authorization_expires_at",
            "project_id",
            "charter_id",
            "charter_revision",
            "task_revision",
            "founder_approval_event_id",
            "founder_approval_event_digest",
            "founder_authenticated_session_id",
            "founder_principal_sid",
        }
        optional_fields = fields | {"provider_input_required"}
        if set(payload) not in {
            frozenset(fields),
            frozenset(optional_fields),
        }:
            raise ValueError("authority operation payload fields are invalid")
        registration_id = _text(payload["registration_id"], "registration ID")
        registration = self.store.get("registrations", registration_id)
        if registration is None or registration.pop("service_state", None) != "QUALIFIED":
            raise PermissionError("provider registration is not service-qualified")
        authorization_id = _text(
            payload["launch_authorization_id"], "launch authorization ID"
        )
        authorization = self.store.get(
            "launch_authorizations", authorization_id
        )
        if (
            authorization is None
            or authorization.pop("service_state", None) != "ACTIVE"
            or authorization.get("project_id") != payload["project_id"]
            or authorization.get("charter_id") != payload["charter_id"]
            or authorization.get("charter_revision")
            != payload["charter_revision"]
            or authorization.get("delegation_id") != payload["delegation_id"]
            or authorization.get("founder_approval_event_id")
            != payload["founder_approval_event_id"]
            or authorization.get("founder_approval_event_digest")
            != payload["founder_approval_event_digest"]
            or authorization.get("founder_authenticated_session_id")
            != payload["founder_authenticated_session_id"]
            or authorization.get("founder_principal_sid")
            != payload["founder_principal_sid"]
            or authorization.get("authorization_generation")
            != payload["authorization_generation"]
            or authorization.get("authorized_client_sid") != client_sid
            or authorization.get("expires_at")
            != payload["authorization_expires_at"]
        ):
            raise PermissionError(
                "attempt launch authorization generation is invalid"
            )
        role = _text(payload["role"], "role")
        stage_id = _text(payload["stage_id"], "stage ID")
        provider_input_required_value = payload.get("provider_input_required")
        if provider_input_required_value is None:
            provider_input_required = role.casefold() == "reviewer"
        elif type(provider_input_required_value) is not bool:
            raise ValueError(
                "authority provider input requirement is invalid"
            )
        else:
            provider_input_required = provider_input_required_value
        if role.casefold() == "reviewer" and not provider_input_required:
            raise PermissionError("reviewer provider input cannot be optional")
        attempt_id = (
            f"provider-attempt:{_text(payload['keeper_run_id'], 'run ID')}:"
            f"{_text(payload['provider_run_id'], 'provider run ID')}"
        )
        challenge = secrets.token_hex(32)
        record = self.keys.sign(
            "provider-launch-authorization",
            {
                "id": attempt_id,
                "kind": "provider_launch_authorization",
                "schema_version": 1,
                "registration_id": registration_id,
                "registration_digest": registration["configuration_digest"],
                "keeper_run_id": payload["keeper_run_id"],
                "task_id": _text(payload["task_id"], "task ID"),
                "stage_id": stage_id,
                "role": role,
                "attempt_number": _positive_int(
                    payload["attempt_number"], "attempt number"
                ),
                "provider_run_id": payload["provider_run_id"],
                "provider_instance_id": _text(
                    payload["provider_instance_id"], "provider instance ID"
                ),
                "evidence_path": _canonical_path(
                    payload["evidence_path"], "evidence path"
                ),
                "prompt_path": _canonical_path(
                    payload["prompt_path"], "prompt path"
                ),
                "stdout_path": _canonical_path(
                    payload["stdout_path"], "stdout path"
                ),
                "stderr_path": _canonical_path(
                    payload["stderr_path"], "stderr path"
                ),
                "workspace": _canonical_path(payload["workspace"], "workspace"),
                "timeout_seconds": _bounded_int(
                    payload["timeout_seconds"], "timeout seconds", 1, 86_400
                ),
                "reasoning_level": _choice(
                    payload["reasoning_level"],
                    {"low", "medium", "high", "extra-high"},
                ),
                "environment": _safe_environment(payload["environment"]),
                "provider_input_required": provider_input_required,
                "launch_challenge": challenge,
                "authorized_client_sid": client_sid,
                "reserved_at": _now(),
                "launch_authorization_id": authorization_id,
                "authorization_generation": payload[
                    "authorization_generation"
                ],
                "revocation_epoch": authorization["revocation_epoch"],
                "delegation_id": payload["delegation_id"],
                "founder_approval_event_id": payload[
                    "founder_approval_event_id"
                ],
                "founder_approval_event_digest": payload[
                    "founder_approval_event_digest"
                ],
                "founder_authenticated_session_id": payload[
                    "founder_authenticated_session_id"
                ],
                "founder_principal_sid": payload["founder_principal_sid"],
                "authorization_expires_at": payload[
                    "authorization_expires_at"
                ],
                "project_id": payload["project_id"],
                "charter_id": payload["charter_id"],
                "charter_revision": payload["charter_revision"],
                "task_revision": payload["task_revision"],
            },
        )
        self.store.insert(
            "attempts",
            attempt_id,
            "RESERVED",
            record,
            registration_id=registration_id,
            run_id=str(payload["keeper_run_id"]),
            attempt_number=int(payload["attempt_number"]),
            challenge=challenge,
        )
        return {"attempt": record, "attempt_id": attempt_id}

    def _verified_executive_input_receipt(
        self,
        value: object,
        attempt: dict[str, Any],
        provider_input: dict[str, Any],
        *,
        provider_input_digest: str,
        delivered_input_digest: str,
        manifest_digest: str,
    ) -> dict[str, object]:
        if not isinstance(value, dict):
            raise PermissionError(
                "provider input lacks an Executive commit receipt"
            )
        verifier = self.founder_capability_verifier
        if verifier is None:
            raise PermissionError(
                "Executive commit receipt verification is unavailable"
            )
        composition = provider_input["composition_identity"]
        if (
            composition == "PRODUCTION_AUTHORITY"
            and type(verifier) is not ProductionFounderCapabilityVerifier
        ) or (
            composition == "TEST_AUTHORITY"
            and type(verifier) is not TestFounderCapabilityVerifier
        ):
            raise PermissionError(
                "Executive receipt composition does not match Authority"
            )
        receipt = verifier.verify_executive_input_receipt(value)
        issued_at = datetime.fromisoformat(str(receipt["issued_at"]))
        now = datetime.now(UTC)
        if issued_at > now + timedelta(seconds=5) or issued_at < (
            now - timedelta(minutes=5)
        ):
            raise PermissionError(
                "Executive delivered-input receipt is stale"
            )
        expected: dict[str, object] = {
            "repository_mode": (
                "PRODUCTION"
                if provider_input["composition_identity"]
                == "PRODUCTION_AUTHORITY"
                else "TEST"
            ),
            "authority_attempt_id": attempt.get("id"),
            "reviewer_attempt_id": provider_input["reviewer_attempt_id"],
            "reviewer_assignment_id": attempt.get("task_id"),
            "project_id": attempt.get("project_id"),
            "charter_id": attempt.get("charter_id"),
            "charter_revision": attempt.get("charter_revision"),
            "workflow_id": provider_input["workflow_id"],
            "work_item_id": attempt.get("stage_id"),
            "producer_assignment_id": provider_input[
                "producer_assignment_id"
            ],
            "producer_attempt_id": provider_input["producer_attempt_id"],
            "provider_id": provider_input["provider_id"],
            "account_id": provider_input["account_id"],
            "session_id": attempt.get("provider_instance_id"),
            "model_id": provider_input["model_id"],
            "workspace": provider_input["workspace"],
            "composition_identity": provider_input[
                "composition_identity"
            ],
            "provider_input_digest": provider_input_digest,
            "delivered_input_digest": delivered_input_digest,
            "manifest_digest": manifest_digest,
            "reference_set_digest": structured_digest(
                provider_input["references"]
            ),
            "session_slot_claimed": True,
            "launch_claim_state": "LAUNCH_CLAIMED",
        }
        mismatches = [
            name
            for name, expected_value in expected.items()
            if receipt.get(name) != expected_value
        ]
        if mismatches:
            raise PermissionError(
                "Executive delivered-input receipt binding mismatch: "
                + ", ".join(sorted(mismatches))
            )
        return receipt

    def _bind_provider_input(
        self, payload: dict[str, Any], client_sid: str
    ) -> dict[str, Any]:
        _exact(
            payload,
            {
                "attempt_id",
                "provider_input",
                "provider_input_digest",
                "delivered_input_digest",
                "manifest_digest",
                "executive_commit_receipt",
            },
        )
        attempt_id = _text(payload["attempt_id"], "attempt ID")
        provider_input = validate_provider_input(payload["provider_input"])
        provider_input_digest = _sha256_text(
            payload["provider_input_digest"], "provider input digest"
        )
        delivered_input_digest = _sha256_text(
            payload["delivered_input_digest"], "delivered input digest"
        )
        manifest_digest = _sha256_text(
            payload["manifest_digest"], "manifest digest"
        )
        if (
            structured_digest(provider_input) != provider_input_digest
            or provider_input["delivered_input_digest"]
            != delivered_input_digest
            or provider_input["manifest_digest"] != manifest_digest
            or provider_input["authority_attempt_id"] != attempt_id
        ):
            raise PermissionError("provider input digest binding is invalid")
        current = self.store.get("attempts", attempt_id)
        if current is None:
            raise PermissionError("provider attempt is unavailable")
        state = current.pop("service_state", None)
        receipt = self._verified_executive_input_receipt(
            payload["executive_commit_receipt"],
            current,
            provider_input,
            provider_input_digest=provider_input_digest,
            delivered_input_digest=delivered_input_digest,
            manifest_digest=manifest_digest,
        )
        receipt_digest = structured_digest(receipt)
        if state == "INPUT_BOUND":
            if (
                current.get("authorized_client_sid") != client_sid
                or current.get("provider_input") != provider_input
                or current.get("provider_input_digest")
                != provider_input_digest
                or current.get("delivered_input_digest")
                != delivered_input_digest
                or current.get("executive_commit_receipt") != receipt
                or current.get("executive_commit_receipt_digest")
                != receipt_digest
                or not self.keys.verify("provider-input-binding", current)
            ):
                raise PermissionError(
                    "provider input is already bound differently"
                )
            return {"attempt": {**current, "service_state": "INPUT_BOUND"}}
        expected = {
            "project_id": current.get("project_id"),
            "charter_id": current.get("charter_id"),
            "charter_revision": current.get("charter_revision"),
            "reviewer_assignment_id": current.get("task_id"),
            "work_item_id": current.get("stage_id"),
            "session_id": current.get("provider_instance_id"),
            "launch_authorization_id": current.get(
                "launch_authorization_id"
            ),
            "authorization_generation": current.get(
                "authorization_generation"
            ),
        }
        mismatches = [
            name
            for name, value in expected.items()
            if provider_input[name] != value
        ]
        if str(Path(str(provider_input["workspace"])).resolve()).casefold() != str(
            Path(str(current.get("workspace"))).resolve()
        ).casefold():
            mismatches.append("workspace")
        if (
            state != "RESERVED"
            or current.get("authorized_client_sid") != client_sid
            or str(current.get("role", "")).casefold() != "reviewer"
            or (
                provider_input["composition_identity"]
                == "TEST_AUTHORITY"
                and type(self.founder_capability_verifier)
                is not TestFounderCapabilityVerifier
            )
            or mismatches
        ):
            raise PermissionError(
                "provider input does not match the reserved Authority attempt"
                + (
                    ": " + ", ".join(sorted(mismatches))
                    if mismatches
                    else ""
                )
            )
        bound = self.keys.sign(
            "provider-input-binding",
            {
                **current,
                "kind": "provider_input_binding",
                "provider_input": provider_input,
                "provider_input_digest": provider_input_digest,
                "delivered_input_digest": delivered_input_digest,
                "manifest_digest": manifest_digest,
                "executive_commit_receipt": receipt,
                "executive_commit_receipt_digest": receipt_digest,
                "provider_input_bound_at": _now(),
            },
        )
        self.store.transition(
            "attempts",
            attempt_id,
            "RESERVED",
            "INPUT_BOUND",
            bound,
        )
        return {"attempt": {**bound, "service_state": "INPUT_BOUND"}}

    def _execute_provider(
        self, payload: dict[str, Any], client_sid: str
    ) -> dict[str, Any]:
        _exact(payload, {"attempt_id"})
        if self.observer is None:
            raise RuntimeError("authority provider observer is unavailable")
        attempt_id = _text(payload["attempt_id"], "attempt ID")
        attempt = self.store.get("attempts", attempt_id)
        if attempt is None:
            raise PermissionError("provider launch is not reserved")
        state = attempt.pop("service_state", None)
        provider_input = attempt.get("provider_input")
        input_binding_valid = False
        if state == "INPUT_BOUND" and isinstance(provider_input, dict):
            try:
                validated_input = validate_provider_input(provider_input)
                receipt = self._verified_executive_input_receipt(
                    attempt.get("executive_commit_receipt"),
                    attempt,
                    validated_input,
                    provider_input_digest=str(
                        attempt.get("provider_input_digest")
                    ),
                    delivered_input_digest=str(
                        attempt.get("delivered_input_digest")
                    ),
                    manifest_digest=str(attempt.get("manifest_digest")),
                )
            except (PermissionError, ValueError):
                pass
            else:
                input_binding_valid = (
                    self.keys.verify("provider-input-binding", attempt)
                    and structured_digest(validated_input)
                    == attempt.get("provider_input_digest")
                    and validated_input["delivered_input_digest"]
                    == attempt.get("delivered_input_digest")
                    and validated_input["manifest_digest"]
                    == attempt.get("manifest_digest")
                    and structured_digest(receipt)
                    == attempt.get("executive_commit_receipt_digest")
                )
        if (
            state not in {"RESERVED", "INPUT_BOUND"}
            or (
                _provider_input_is_required(attempt)
                and state != "INPUT_BOUND"
            )
            or (
                state == "INPUT_BOUND"
                and not input_binding_valid
            )
        ):
            raise PermissionError(
                "provider launch is not reserved or validly input-bound"
            )
        if attempt.get("authorized_client_sid") != client_sid:
            raise PermissionError("provider launch belongs to another client")
        registration = self.store.get(
            "registrations", str(attempt["registration_id"])
        )
        if registration is None or registration.pop("service_state", None) != "QUALIFIED":
            raise PermissionError("provider registration is not qualified")
        claim = self.keys.sign(
            "provider-launch-claim",
            {
                **attempt,
                "kind": "provider_launch_claim",
                "claimed_at": _now(),
                "claim_transaction_id": uuid.uuid4().hex,
            },
        )
        self.store.claim_attempt_with_launch_authority(
            attempt_id,
            str(attempt["launch_authorization_id"]),
            int(attempt["authorization_generation"]),
            client_sid,
            claim,
            expected_attempt_state=str(state),
        )
        started_result: dict[str, Any] = {}

        def on_started(observation: ProcessObservation) -> None:
            if (
                not observation.restricted
                or observation.integrity_level != "low"
                or not observation.job_confined
            ):
                raise PermissionError(
                    "provider restricted confinement was not established"
                )
            expected = Path(str(registration["launcher_path"])).resolve()
            if (
                Path(observation.executable).resolve() != expected
                or observation.executable_sha256
                != registration["launcher_sha256"]
            ):
                raise PermissionError(
                    "provider process identity differs from registration"
                )
            started = self.keys.sign(
                "provider-start",
                {
                    **claim,
                    "kind": "provider_execution_started",
                    "pid": observation.pid,
                    "process_creation_time": observation.creation_time,
                    "process_executable": observation.executable,
                    "process_executable_sha256": observation.executable_sha256,
                    "restricted_token": observation.restricted,
                    "integrity_level": observation.integrity_level,
                    "job_confined": observation.job_confined,
                    "started_at": _now(),
                    "completion_challenge": secrets.token_hex(32),
                },
            )
            self.store.transition(
                "attempts",
                attempt_id,
                "LAUNCH_CLAIMED",
                "EXECUTION_STARTED",
                started,
            )
            started_result.update(started)

        observed = self.observer.execute_provider(
            registration, claim, on_started
        )
        if not started_result:
            raise RuntimeError("provider start was not service-observed")
        current = self.store.get("attempts", attempt_id)
        if (
            isinstance(current, dict)
            and current.get("service_state") == "CANCELLED"
        ):
            return {
                "attempt_id": attempt_id,
                "start": started_result,
                "cancelled": True,
                "process_result": {
                    "process_id": observed.process_id,
                    "exit_status": observed.exit_status,
                    "timed_out": observed.timed_out,
                    "stdout_path": observed.stdout_path,
                    "stderr_path": observed.stderr_path,
                },
            }
        normalized_result = (
            "completed" if observed.exit_status == 0 else "failed"
        )
        completion = self._completion_record(
            attempt_id,
            started_result,
            observed.provider_evidence_digest,
            observed.exit_status,
            normalized_result,
            observed.finished_at,
        )
        self.store.transition(
            "attempts",
            attempt_id,
            "EXECUTION_STARTED",
            normalized_result.upper(),
            completion,
        )
        return {
            "attempt_id": attempt_id,
            "start": started_result,
            "completion": completion,
            "process_result": {
                "process_id": observed.process_id,
                "exit_status": observed.exit_status,
                "timed_out": observed.timed_out,
                "stdout_path": observed.stdout_path,
                "stderr_path": observed.stderr_path,
            },
        }

    def _record_provider_start(
        self, payload: dict[str, Any], client_sid: str
    ) -> dict[str, Any]:
        _exact(payload, {"attempt_id", "pid"})
        if self.observer is None:
            raise RuntimeError("authority provider observer is unavailable")
        attempt_id = _text(payload["attempt_id"], "attempt ID")
        attempt = self.store.get("attempts", attempt_id)
        if attempt is None:
            raise PermissionError("provider launch is not reserved")
        state = attempt.pop("service_state", None)
        if state not in {"RESERVED", "INPUT_BOUND"}:
            raise PermissionError("provider launch is not reserved")
        if _provider_input_is_required(attempt):
            raise PermissionError(
                "typed reviewer execution must use Authority-bound provider input"
            )
        if attempt.get("authorized_client_sid") != client_sid:
            raise PermissionError("provider launch belongs to another client")
        observation = self.observer.observe_process(
            attempt, _positive_int(payload["pid"], "process ID")
        )
        if not observation.restricted or not observation.job_confined:
            raise PermissionError("provider restricted confinement was not established")
        expected = self.store.get("registrations", str(attempt["registration_id"]))
        if expected is None:
            raise PermissionError("provider registration is unavailable")
        expected.pop("service_state", None)
        if (
            Path(observation.executable).resolve()
            != Path(str(expected["launcher_path"])).resolve()
            or observation.executable_sha256 != expected["launcher_sha256"]
        ):
            raise PermissionError("provider process identity differs from registration")
        started = self.keys.sign(
            "provider-start",
            {
                **attempt,
                "kind": "provider_execution_started",
                "pid": observation.pid,
                "process_creation_time": observation.creation_time,
                "process_executable": observation.executable,
                "process_executable_sha256": observation.executable_sha256,
                "restricted_token": observation.restricted,
                "integrity_level": observation.integrity_level,
                "job_confined": observation.job_confined,
                "started_at": _now(),
                "completion_challenge": secrets.token_hex(32),
            },
        )
        self.store.transition(
            "attempts",
            attempt_id,
            str(state),
            "EXECUTION_STARTED",
            started,
        )
        return {"attempt": started, "attempt_id": attempt_id}

    def _finalize_completion(
        self, payload: dict[str, Any], client_sid: str
    ) -> dict[str, Any]:
        _exact(payload, {"attempt_id"})
        if self.observer is None:
            raise RuntimeError("authority provider observer is unavailable")
        attempt_id = _text(payload["attempt_id"], "attempt ID")
        attempt = self.store.get("attempts", attempt_id)
        if attempt is None:
            raise PermissionError("provider attempt is not finalizable")
        state = attempt.pop("service_state", None)
        if state in {"COMPLETED", "FAILED"}:
            if (
                attempt.get("kind") != "provider_completion"
                or attempt.get("authorized_client_sid") != client_sid
                or not self.keys.verify("provider-completion", attempt)
            ):
                raise PermissionError(
                    "provider terminal completion is not authentic"
                )
            return {"completion": attempt, "attempt_id": attempt_id}
        if state != "EXECUTION_STARTED":
            raise PermissionError("provider attempt is not finalizable")
        if attempt.get("authorized_client_sid") != client_sid:
            raise PermissionError("provider attempt belongs to another client")
        observed = self.observer.observe_completion(attempt)
        completion = self._completion_record(
            attempt_id,
            attempt,
            observed.evidence_digest,
            observed.exit_status,
            observed.normalized_result,
            observed.finished_at,
        )
        self.store.transition(
            "attempts",
            attempt_id,
            "EXECUTION_STARTED",
            observed.normalized_result.upper(),
            completion,
        )
        return {"completion": completion, "attempt_id": attempt_id}

    def _completion_record(
        self,
        attempt_id: str,
        attempt: dict[str, Any],
        evidence_digest: str,
        exit_status: int,
        normalized_result: str,
        finished_at: str,
    ) -> dict[str, Any]:
        return self.keys.sign(
            "provider-completion",
            {
                "id": f"provider-completion:{attempt_id}",
                "kind": "provider_completion",
                "schema_version": 2,
                "attempt_id": attempt_id,
                "project_id": attempt["project_id"],
                "charter_id": attempt.get("charter_id"),
                "charter_revision": attempt.get("charter_revision"),
                "approval_id": attempt.get("approval_id"),
                "budget_reservation_id": attempt.get("budget_reservation_id"),
                "launch_authorization_id": attempt["launch_authorization_id"],
                "authorization_generation": attempt["authorization_generation"],
                "completion_challenge": attempt["completion_challenge"],
                "keeper_run_id": attempt["keeper_run_id"],
                "task_id": attempt["task_id"],
                "stage_id": attempt["stage_id"],
                "role": attempt["role"],
                "attempt_number": attempt["attempt_number"],
                "provider_run_id": attempt["provider_run_id"],
                "provider_instance_id": attempt["provider_instance_id"],
                "registration_id": attempt["registration_id"],
                "registration_digest": attempt["registration_digest"],
                "process_id": attempt["pid"],
                "process_creation_time": attempt["process_creation_time"],
                "provider_evidence_digest": evidence_digest,
                "delivered_input_digest": attempt.get(
                    "delivered_input_digest"
                ),
                "provider_input_digest": attempt.get(
                    "provider_input_digest"
                ),
                "executive_commit_receipt_digest": attempt.get(
                    "executive_commit_receipt_digest"
                ),
                "manifest_digest": attempt.get("manifest_digest"),
                "exit_status": exit_status,
                "normalized_result": normalized_result,
                "terminal_disposition": normalized_result.upper(),
                "finished_at": finished_at,
                "authorized_client_sid": attempt["authorized_client_sid"],
                "transaction_id": uuid.uuid4().hex,
            },
        )

    def _reconcile_executive_restore(
        self, payload: dict[str, Any], client_sid: str
    ) -> dict[str, Any]:
        fields = {
            "restore_operation_id",
            "backup_sha256",
            "source_database_id",
            "source_recovery_epoch",
            "target_database_id",
            "target_recovery_epoch",
            "target_generation",
            "project_scope",
        }
        _exact(payload, fields)
        operation_id = _text(
            payload["restore_operation_id"], "restore operation ID"
        )
        backup_sha256 = _sha256_text(
            payload["backup_sha256"], "backup SHA-256"
        )
        source_database_id = _text(
            payload["source_database_id"], "source database ID"
        )
        target_database_id = _text(
            payload["target_database_id"], "target database ID"
        )
        source_epoch = _nonnegative_int(
            payload["source_recovery_epoch"], "source recovery epoch"
        )
        target_epoch = _nonnegative_int(
            payload["target_recovery_epoch"], "target recovery epoch"
        )
        target_generation = _nonnegative_int(
            payload["target_generation"], "target generation"
        )
        scope_value = payload["project_scope"]
        if (
            not isinstance(scope_value, list)
            or not all(isinstance(item, str) and item for item in scope_value)
            or scope_value != sorted(set(scope_value))
        ):
            raise ValueError("Authority restore project scope is invalid")
        project_scope = set(scope_value)
        attempts = sorted(
            (
                record
                for record in self.store.list_records("attempts")
                if record.get("project_id") in project_scope
            ),
            key=lambda item: str(item.get("id", "")),
        )
        authorizations = sorted(
            (
                record
                for record in self.store.list_records("launch_authorizations")
                if record.get("project_id") in project_scope
            ),
            key=lambda item: str(item.get("id", "")),
        )
        state = {
            "attempts": attempts,
            "launch_authorizations": authorizations,
        }
        receipt = self.keys.sign(
            "executive-restore-reconciliation",
            {
                "schema_version": 1,
                "kind": "executive-restore-reconciliation",
                "restore_operation_id": operation_id,
                "backup_sha256": backup_sha256,
                "source_database_id": source_database_id,
                "source_recovery_epoch": source_epoch,
                "target_database_id": target_database_id,
                "target_recovery_epoch": target_epoch,
                "target_generation": target_generation,
                "project_scope": scope_value,
                "protocol_version": PROTOCOL_VERSION,
                "service_key_id": self.keys.current_key_id,
                "authorized_client_sid": client_sid,
                **state,
                "state_digest": _canonical_digest(state),
                "reconciled_at": _now(),
            },
        )
        return {"reconciliation": receipt}

    def _begin_executive_restore_fence(
        self, payload: dict[str, Any], client_sid: str
    ) -> dict[str, Any]:
        identity = _validated_restore_fence_identity(payload)
        now = datetime.now(UTC)
        fence = self.store.begin_restore_fence(
            f"restore-fence:{identity['restore_operation_id']}",
            identity,
            client_sid,
            now.isoformat(),
            (now + RESTORE_FENCE_LIFETIME).isoformat(),
        )
        signed = self.keys.sign(
            "executive-restore-reconciliation-fence",
            {
                "schema_version": 1,
                "kind": "executive-restore-reconciliation-fence",
                "protocol_version": PROTOCOL_VERSION,
                "service_key_id": self.keys.current_key_id,
                **fence,
            },
        )
        return {"fence": signed}

    def _confirm_executive_restore_fence(
        self, payload: dict[str, Any], client_sid: str
    ) -> dict[str, Any]:
        _exact(payload, {"fence_id", "restore_operation_id"})
        confirmation = self.store.confirm_restore_fence(
            _text(payload["fence_id"], "restore fence ID"),
            _text(payload["restore_operation_id"], "restore operation ID"),
            client_sid,
        )
        signed = self.keys.sign(
            "executive-restore-fence-confirmation",
            {
                "schema_version": 1,
                "kind": "executive-restore-fence-confirmation",
                "protocol_version": PROTOCOL_VERSION,
                "service_key_id": self.keys.current_key_id,
                **confirmation,
            },
        )
        return {"confirmation": signed}

    def _complete_executive_restore_fence(
        self, payload: dict[str, Any], client_sid: str
    ) -> dict[str, Any]:
        return self._finish_executive_restore_fence(
            payload, client_sid, "COMPLETED"
        )

    def _abort_executive_restore_fence(
        self, payload: dict[str, Any], client_sid: str
    ) -> dict[str, Any]:
        return self._finish_executive_restore_fence(
            payload, client_sid, "ABORTED"
        )

    def _finish_executive_restore_fence(
        self, payload: dict[str, Any], client_sid: str, state: str
    ) -> dict[str, Any]:
        _exact(payload, {"fence_id", "restore_operation_id"})
        outcome = self.store.finish_restore_fence(
            _text(payload["fence_id"], "restore fence ID"),
            _text(payload["restore_operation_id"], "restore operation ID"),
            client_sid,
            state,
        )
        return {
            "outcome": self.keys.sign(
                "executive-restore-fence-outcome",
                {
                    "schema_version": 1,
                    "kind": "executive-restore-fence-outcome",
                    "protocol_version": PROTOCOL_VERSION,
                    "service_key_id": self.keys.current_key_id,
                    "authorized_client_sid": client_sid,
                    **outcome,
                },
            )
        }

    def _recover_executive_restore_fence(
        self, payload: dict[str, Any], client_sid: str
    ) -> dict[str, Any]:
        _exact(payload, {"fence_id", "restore_operation_id"})
        outcome = self.store.recover_restore_fence(
            _text(payload["fence_id"], "restore fence ID"),
            _text(payload["restore_operation_id"], "restore operation ID"),
            client_sid,
        )
        return {
            "outcome": self.keys.sign(
                "executive-restore-fence-outcome",
                {
                    "schema_version": 1,
                    "kind": "executive-restore-fence-outcome",
                    "protocol_version": PROTOCOL_VERSION,
                    "service_key_id": self.keys.current_key_id,
                    "authorized_client_sid": client_sid,
                    **outcome,
                },
            )
        }

    def _query_state(
        self, payload: dict[str, Any], client_sid: str
    ) -> dict[str, Any]:
        _exact(payload, {"kind", "id"})
        table = _choice(
            payload["kind"],
            {
                "registrations", "qualifications", "attempts",
                "launch_authorizations",
            },
        )
        identifier = _text(payload["id"], "state ID")
        value = self.store.get(table, identifier)
        return {"found": value is not None, "record": value}

    def _verify_evidence(
        self, payload: dict[str, Any], client_sid: str
    ) -> dict[str, Any]:
        _exact(payload, {"purpose", "record"})
        purpose = _choice(
            payload["purpose"],
            {
                "project-launch-authorization",
                "provider-registration",
                "provider-qualification-start",
                "provider-qualification",
                "provider-launch-authorization",
                "provider-input-binding",
                "provider-launch-claim",
                "provider-start",
                "provider-completion",
                "executive-restore-reconciliation",
                "executive-restore-reconciliation-fence",
                "executive-restore-fence-confirmation",
                "executive-restore-fence-outcome",
                AUDIT_REPORT_PURPOSE,
            },
        )
        return {"valid": self.keys.verify(purpose, payload["record"])}

    def _pause_attempt(
        self, payload: dict[str, Any], client_sid: str
    ) -> dict[str, Any]:
        return self._transition_attempt(payload, client_sid, "EXECUTION_STARTED", "PAUSED")

    def _resume_attempt(
        self, payload: dict[str, Any], client_sid: str
    ) -> dict[str, Any]:
        return self._transition_attempt(payload, client_sid, "PAUSED", "EXECUTION_STARTED")

    def _cancel_attempt(
        self, payload: dict[str, Any], client_sid: str
    ) -> dict[str, Any]:
        _exact(payload, {"attempt_id"})
        attempt_id = _text(payload["attempt_id"], "attempt ID")
        value = self.store.get("attempts", attempt_id)
        if value is None:
            raise PermissionError("provider attempt is unavailable")
        state = str(value.pop("service_state"))
        if state not in {
            "RESERVED",
            "INPUT_BOUND",
            "LAUNCH_CLAIMED",
            "EXECUTION_STARTED",
            "PAUSED",
        }:
            raise PermissionError("provider attempt cannot be cancelled")
        if value.get("authorized_client_sid") != client_sid:
            raise PermissionError("provider attempt belongs to another client")
        cancellation_intent_id = f"cancellation-intent:{uuid.uuid4().hex}"
        claimed = {
            **value,
            "cancellation_intent_id": cancellation_intent_id,
            "cancellation_requested_at": _now(),
        }
        self.store.transition(
            "attempts",
            attempt_id,
            state,
            "CANCELLATION_CLAIMED",
            claimed,
        )
        cancel_provider = getattr(self.observer, "cancel_provider", None)
        if callable(cancel_provider):
            cancel_provider(attempt_id)
        cancelled = {**claimed, "cancelled_at": _now()}
        self.store.transition(
            "attempts",
            attempt_id,
            "CANCELLATION_CLAIMED",
            "CANCELLED",
            cancelled,
        )
        return {
            "attempt_id": attempt_id,
            "state": "CANCELLED",
            "cancellation_intent_id": cancellation_intent_id,
        }

    def _transition_attempt(
        self,
        payload: dict[str, Any],
        client_sid: str,
        expected: str,
        state: str,
    ) -> dict[str, Any]:
        _exact(payload, {"attempt_id"})
        attempt_id = _text(payload["attempt_id"], "attempt ID")
        value = self.store.get("attempts", attempt_id)
        if value is None or value.pop("service_state", None) != expected:
            raise PermissionError("provider attempt transition was rejected")
        if value.get("authorized_client_sid") != client_sid:
            raise PermissionError("provider attempt belongs to another client")
        updated = {**value, f"{state.casefold()}_at": _now()}
        self.store.transition("attempts", attempt_id, expected, state, updated)
        return {"attempt_id": attempt_id, "state": state}

    def _revoke_registration(
        self, payload: dict[str, Any], client_sid: str
    ) -> dict[str, Any]:
        _exact(payload, {"registration_id"})
        identifier = _text(payload["registration_id"], "registration ID")
        value = self.store.get("registrations", identifier)
        if value is None:
            raise PermissionError("provider registration is unavailable")
        state = str(value.pop("service_state"))
        if state == "REVOKED":
            raise PermissionError("provider registration is already revoked")
        revoked = {
            **value,
            "registration_status": "revoked",
            "registration_lifecycle": "REVOKED",
            "revoked_at": _now(),
        }
        revoked["configuration_digest"] = canonical_provider_registration_digest(revoked)
        self.store.transition("registrations", identifier, state, "REVOKED", revoked)
        return {"registration": revoked, "registration_id": identifier}

    def _rotate_key(
        self, payload: dict[str, Any], client_sid: str
    ) -> dict[str, Any]:
        _exact(payload, {"confirmation"})
        if payload["confirmation"] != "ROTATE_KEEPER_AUTHORITY_KEY":
            raise PermissionError("authority key rotation confirmation is invalid")
        return self.keys.rotate()

    def _migrate_legacy(
        self, payload: dict[str, Any], client_sid: str
    ) -> dict[str, Any]:
        _exact(payload, {"registrations"})
        registrations = payload["registrations"]
        if not isinstance(registrations, list):
            raise ValueError("legacy registrations must be a list")
        migrated = 0
        created: list[dict[str, Any]] = []
        for old in registrations:
            if not isinstance(old, dict):
                raise ValueError("legacy registration is malformed")
            _exact(
                old,
                {
                    "logical_provider_id",
                    "canonical_executable_path",
                    "executive_capabilities",
                    "project_types",
                    "effort_levels",
                    "pricing_authority",
                },
            )
            provider_id = _choice(old.get("logical_provider_id"), {"codex", "claude"})
            executable = Path(
                _text(old.get("canonical_executable_path"), "legacy executable")
            )
            executive_capabilities = old["executive_capabilities"]
            project_types = old["project_types"]
            effort_levels = old["effort_levels"]
            pricing_authority = old["pricing_authority"]
            matches = [
                value
                for value in self.store.list_records("registrations")
                if value.get("logical_provider_id") == provider_id
                and value.get("canonical_executable_path")
                == str(executable.resolve(strict=True))
            ]
            if len(matches) > 1:
                raise PermissionError(
                    "legacy registration migration is ambiguous"
                )
            if matches:
                existing = dict(matches[0])
                existing.pop("service_state", None)
                created.append(existing)
                continue
            if self.observer is not None and hasattr(
                self.observer, "register_provider"
            ):
                registration = self.observer.register_provider(
                    provider_id,
                    executable,
                    client_sid,
                    executive_capabilities=executive_capabilities,
                    project_types=project_types,
                    effort_levels=effort_levels,
                    pricing_authority=pricing_authority,
                )
            else:
                registration = create_provider_registration(
                    provider_id,
                    executable,
                    authorized_by=client_sid,
                    executive_capabilities=executive_capabilities,
                    project_types=project_types,
                    effort_levels=effort_levels,
                    pricing_authority=pricing_authority,
                )
            self.store.insert(
                "registrations",
                str(registration["trusted_registration_id"]),
                "REGISTERED_UNQUALIFIED",
                registration,
            )
            migrated += 1
            created.append(registration)
        return {
            "migrated_registrations": migrated,
            "registrations": created,
            "legacy_evidence_status": "UNVERIFIABLE",
        }

    def _internal_only(
        self, payload: dict[str, Any], client_sid: str
    ) -> dict[str, Any]:
        raise PermissionError("qualification finalization is service-internal")


def _provider_input_is_required(attempt: dict[str, Any]) -> bool:
    value = attempt.get("provider_input_required")
    if value is None:
        return str(attempt.get("role", "")).casefold() == "reviewer"
    if type(value) is not bool:
        raise PermissionError("provider input requirement is invalid")
    return value


def _exact(payload: dict[str, Any], fields: set[str]) -> None:
    if set(payload) != fields:
        raise ValueError("authority operation payload fields are invalid")


def _text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value or len(value) > 4096:
        raise ValueError(f"authority {label} is invalid")
    return value


def _choice(value: object, choices: set[str]) -> str:
    text = _text(value, "enum")
    if text not in choices:
        raise ValueError("authority enum value is unsupported")
    return text


def _positive_int(value: object, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"authority {label} is invalid")
    return value


def _bounded_int(
    value: object, label: str, minimum: int, maximum: int
) -> int:
    result = _positive_int(value, label)
    if result < minimum or result > maximum:
        raise ValueError(f"authority {label} is out of range")
    return result


def _safe_environment(value: object) -> dict[str, str]:
    if not isinstance(value, dict) or len(value) > 256:
        raise ValueError("authority provider environment is invalid")
    result: dict[str, str] = {}
    sensitive = (
        "TOKEN",
        "SECRET",
        "PASSWORD",
        "PASSWD",
        "API_KEY",
        "PRIVATE_KEY",
        "COOKIE",
        "CREDENTIAL",
    )
    for key, item in value.items():
        if (
            not isinstance(key, str)
            or not key
            or len(key) > 128
            or "=" in key
            or "\0" in key
            or any(marker in key.upper() for marker in sensitive)
            or not isinstance(item, str)
            or len(item) > 32_768
            or "\0" in item
        ):
            raise ValueError("authority provider environment is invalid")
        result[key] = item
    return result


def _canonical_path(value: object, label: str) -> str:
    path = Path(_text(value, label))
    if not path.is_absolute():
        raise ValueError(f"authority {label} must be absolute")
    return str(path.resolve())


def _object_id(result: dict[str, Any]) -> str | None:
    report = result.get("report")
    if isinstance(report, dict) and isinstance(
        report.get("audit_operation_id"), str
    ):
        return str(report["audit_operation_id"])
    for key in ("attempt_id", "registration_id", "qualification_id"):
        value = result.get(key)
        if isinstance(value, str):
            return value
    return None


def _validated_restore_fence_identity(payload: dict[str, Any]) -> dict[str, Any]:
    fields = {
        "restore_operation_id",
        "backup_operation_id",
        "backup_artifact_path",
        "backup_sha256",
        "source_database_id",
        "source_recovery_epoch",
        "source_generation",
        "target_database_id",
        "target_recovery_epoch",
        "target_generation",
        "project_scope",
        "authorization_digest",
    }
    _exact(payload, fields)
    scope = payload["project_scope"]
    if (
        not isinstance(scope, list)
        or not all(isinstance(item, str) and item for item in scope)
        or scope != sorted(set(scope))
    ):
        raise ValueError("Authority restore project scope is invalid")
    return {
        "restore_operation_id": _text(
            payload["restore_operation_id"], "restore operation ID"
        ),
        "backup_operation_id": _text(
            payload["backup_operation_id"], "backup operation ID"
        ),
        "backup_artifact_path": _text(
            payload["backup_artifact_path"], "backup artifact path"
        ),
        "backup_sha256": _sha256_text(
            payload["backup_sha256"], "backup SHA-256"
        ),
        "source_database_id": _text(
            payload["source_database_id"], "source database ID"
        ),
        "source_recovery_epoch": _nonnegative_int(
            payload["source_recovery_epoch"], "source recovery epoch"
        ),
        "source_generation": _nonnegative_int(
            payload["source_generation"], "source generation"
        ),
        "target_database_id": _text(
            payload["target_database_id"], "target database ID"
        ),
        "target_recovery_epoch": _nonnegative_int(
            payload["target_recovery_epoch"], "target recovery epoch"
        ),
        "target_generation": _nonnegative_int(
            payload["target_generation"], "target generation"
        ),
        "project_scope": scope,
        "authorization_digest": _sha256_text(
            payload["authorization_digest"], "authorization digest"
        ),
    }


def _nonnegative_int(value: object, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"authority {label} is invalid")
    return value


def _sha256_text(value: object, label: str) -> str:
    text = _text(value, label)
    if len(text) != 64 or any(item not in "0123456789abcdef" for item in text):
        raise ValueError(f"authority {label} is invalid")
    return text


def _canonical_digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _now() -> str:
    return datetime.now(UTC).isoformat()
