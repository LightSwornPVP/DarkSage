from __future__ import annotations

import hashlib
import json
import secrets
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

from keeper.authority_service.key_ring import ServiceKeyRing
from keeper.authority_service.protocol import Operation, Request
from keeper.authority_service.store import AuthorityStore
from keeper.providers.adapters import (
    apply_protected_qualification,
    canonical_provider_registration_digest,
    create_provider_registration,
    qualification_evidence_digest,
    qualified_version_is_valid,
)


SERVICE_VERSION = "1.0.0"


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


class TrustedObserver(Protocol):
    def qualify(
        self, registration: dict[str, Any], challenge: str
    ) -> QualificationObservation: ...

    def observe_process(
        self, attempt: dict[str, Any], pid: int
    ) -> ProcessObservation: ...

    def observe_completion(
        self, attempt: dict[str, Any]
    ) -> CompletionObservation: ...


class AuthorityServiceCore:
    """Service-owned lifecycle authority; callers never supply signed records."""

    def __init__(
        self,
        root: Path,
        *,
        observer: TrustedObserver | None = None,
    ) -> None:
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.store = AuthorityStore(self.root / "authority.db")
        self.store.migrate()
        self.keys = ServiceKeyRing(self.root / "keys")
        self.observer = observer

    def dispatch(self, request: Request, client_sid: str) -> dict[str, Any]:
        if not client_sid:
            raise PermissionError("authority client identity is missing")
        self.store.consume_request(
            request.request_id,
            request.operation_id,
            request.nonce,
            client_sid,
        )
        handlers = {
            Operation.DIAGNOSTICS: self._diagnostics,
            Operation.REGISTER_PROVIDER: self._register_provider,
            Operation.BEGIN_QUALIFICATION: self._qualify_provider,
            Operation.FINALIZE_QUALIFICATION: self._internal_only,
            Operation.RESERVE_ATTEMPT: self._reserve_attempt,
            Operation.RECORD_PROVIDER_START: self._record_provider_start,
            Operation.FINALIZE_COMPLETION: self._finalize_completion,
            Operation.QUERY_STATE: self._query_state,
            Operation.VERIFY_EVIDENCE: self._verify_evidence,
            Operation.PAUSE_ATTEMPT: self._pause_attempt,
            Operation.RESUME_ATTEMPT: self._resume_attempt,
            Operation.CANCEL_ATTEMPT: self._cancel_attempt,
            Operation.REVOKE_REGISTRATION: self._revoke_registration,
            Operation.ROTATE_KEY: self._rotate_key,
            Operation.MIGRATE_LEGACY: self._migrate_legacy,
        }
        result = handlers[request.operation](request.payload, client_sid)
        self.store.audit(
            request.operation_id,
            request.operation.value,
            client_sid,
            _object_id(result),
            {"outcome": "accepted"},
        )
        return result

    def _diagnostics(
        self, payload: dict[str, Any], client_sid: str
    ) -> dict[str, Any]:
        _exact(payload, set())
        return {
            "service_version": SERVICE_VERSION,
            "protocol_version": 1,
            "service_root": str(self.root),
            "service_key_id": self.keys.current_key_id,
            "service_key_version": self.keys.current_version,
            "client_sid": client_sid,
            "observer_available": self.observer is not None,
            "registrations": len(self.store.list_records("registrations")),
            "qualifications": len(self.store.list_records("qualifications")),
            "attempts": len(self.store.list_records("attempts")),
        }

    def _register_provider(
        self, payload: dict[str, Any], client_sid: str
    ) -> dict[str, Any]:
        _exact(payload, {"provider_id", "executable"})
        provider_id = _choice(payload["provider_id"], {"codex", "claude"})
        executable = Path(_text(payload["executable"], "provider executable"))
        registration = create_provider_registration(
            provider_id,
            executable,
            authorized_by=client_sid,
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
        }
        _exact(payload, fields)
        registration_id = _text(payload["registration_id"], "registration ID")
        registration = self.store.get("registrations", registration_id)
        if registration is None or registration.pop("service_state", None) != "QUALIFIED":
            raise PermissionError("provider registration is not service-qualified")
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
                "stage_id": _text(payload["stage_id"], "stage ID"),
                "role": _text(payload["role"], "role"),
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
                "launch_challenge": challenge,
                "authorized_client_sid": client_sid,
                "reserved_at": _now(),
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

    def _record_provider_start(
        self, payload: dict[str, Any], client_sid: str
    ) -> dict[str, Any]:
        _exact(payload, {"attempt_id", "pid"})
        if self.observer is None:
            raise RuntimeError("authority provider observer is unavailable")
        attempt_id = _text(payload["attempt_id"], "attempt ID")
        attempt = self.store.get("attempts", attempt_id)
        if attempt is None or attempt.pop("service_state", None) != "RESERVED":
            raise PermissionError("provider launch is not reserved")
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
        self.store.transition("attempts", attempt_id, "RESERVED", "EXECUTION_STARTED", started)
        return {"attempt": started, "attempt_id": attempt_id}

    def _finalize_completion(
        self, payload: dict[str, Any], client_sid: str
    ) -> dict[str, Any]:
        _exact(payload, {"attempt_id"})
        if self.observer is None:
            raise RuntimeError("authority provider observer is unavailable")
        attempt_id = _text(payload["attempt_id"], "attempt ID")
        attempt = self.store.get("attempts", attempt_id)
        if attempt is None or attempt.pop("service_state", None) != "EXECUTION_STARTED":
            raise PermissionError("provider attempt is not finalizable")
        if attempt.get("authorized_client_sid") != client_sid:
            raise PermissionError("provider attempt belongs to another client")
        observed = self.observer.observe_completion(attempt)
        completion = self.keys.sign(
            "provider-completion",
            {
                "id": f"provider-completion:{attempt_id}",
                "kind": "provider_completion",
                "schema_version": 2,
                "attempt_id": attempt_id,
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
                "provider_evidence_digest": observed.evidence_digest,
                "exit_status": observed.exit_status,
                "normalized_result": observed.normalized_result,
                "terminal_disposition": observed.normalized_result.upper(),
                "finished_at": observed.finished_at,
                "transaction_id": uuid.uuid4().hex,
            },
        )
        self.store.transition(
            "attempts",
            attempt_id,
            "EXECUTION_STARTED",
            observed.normalized_result.upper(),
            completion,
        )
        return {"completion": completion, "attempt_id": attempt_id}

    def _query_state(
        self, payload: dict[str, Any], client_sid: str
    ) -> dict[str, Any]:
        _exact(payload, {"kind", "id"})
        table = _choice(payload["kind"], {"registrations", "qualifications", "attempts"})
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
                "provider-registration",
                "provider-qualification-start",
                "provider-qualification",
                "provider-launch-authorization",
                "provider-start",
                "provider-completion",
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
        if state not in {"RESERVED", "EXECUTION_STARTED", "PAUSED"}:
            raise PermissionError("provider attempt cannot be cancelled")
        if value.get("authorized_client_sid") != client_sid:
            raise PermissionError("provider attempt belongs to another client")
        cancelled = {**value, "cancelled_at": _now()}
        self.store.transition("attempts", attempt_id, state, "CANCELLED", cancelled)
        return {"attempt_id": attempt_id, "state": "CANCELLED"}

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
        for old in registrations:
            if not isinstance(old, dict):
                raise ValueError("legacy registration is malformed")
            provider_id = _choice(old.get("logical_provider_id"), {"codex", "claude"})
            executable = Path(
                _text(old.get("canonical_executable_path"), "legacy executable")
            )
            registration = create_provider_registration(
                provider_id, executable, authorized_by=client_sid
            )
            self.store.insert(
                "registrations",
                str(registration["trusted_registration_id"]),
                "REGISTERED_UNQUALIFIED",
                registration,
            )
            migrated += 1
        return {
            "migrated_registrations": migrated,
            "legacy_evidence_status": "UNVERIFIABLE",
        }

    def _internal_only(
        self, payload: dict[str, Any], client_sid: str
    ) -> dict[str, Any]:
        raise PermissionError("qualification finalization is service-internal")


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


def _canonical_path(value: object, label: str) -> str:
    path = Path(_text(value, label))
    if not path.is_absolute():
        raise ValueError(f"authority {label} must be absolute")
    return str(path.resolve())


def _object_id(result: dict[str, Any]) -> str | None:
    for key in ("attempt_id", "registration_id", "qualification_id"):
        value = result.get(key)
        if isinstance(value, str):
            return value
    return None


def _now() -> str:
    return datetime.now(UTC).isoformat()
