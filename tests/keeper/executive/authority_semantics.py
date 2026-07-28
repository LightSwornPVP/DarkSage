from __future__ import annotations

import hashlib
import threading
from pathlib import Path
from typing import Any

from keeper.authority_service.client import AuthorityServiceClient
from keeper.authority_service.protocol import Operation, Request
from keeper.executive.authority_gateway import (
    AuthorityBackedSpecialistGateway,
    AuthorityProviderBinding,
    authority_operations,
)


ALL_CAPABILITIES = (
    "requirements",
    "architecture",
    "implementation",
    "testing",
    "security",
    "packaging",
    "acceptance",
    "research design",
    "source collection",
    "source review",
    "synthesis",
    "critical analysis",
    "report writing",
    "planning",
    "production",
    "review",
)


class SemanticAuthorityTransport:
    """Test-only Authority transport preserving reservation/completion semantics."""

    def __init__(self) -> None:
        self.registrations: dict[str, dict[str, Any]] = {}
        self.qualifications: dict[str, dict[str, Any]] = {}
        self.attempts: dict[str, dict[str, Any]] = {}
        self.execution_calls: list[str] = []
        self.side_effect_count = 0
        self.raise_after_side_effect = False
        self.raise_after_reservation = False
        self.unsigned_completion = False
        self.wrong_completion_field: tuple[str, str] | None = None
        self.ignore_cancel_completion = False
        self.fail_review_once = False
        self.started: threading.Event | None = None
        self.release: threading.Event | None = None
        self._lock = threading.RLock()
        self._install_provider("registration-codex", "qualification-codex", "codex")
        self._install_provider("registration-claude", "qualification-claude", "claude")

    def _install_provider(
        self,
        registration_id: str,
        qualification_id: str,
        provider_id: str,
    ) -> None:
        executable = f"C:/Authority/{provider_id}.exe"
        executable_digest = hashlib.sha256(executable.encode()).hexdigest()
        qualification = self._sign(
            "provider-qualification",
            {
                "id": qualification_id,
                "kind": "provider_qualification",
                "registration_id": registration_id,
                "provider_id": provider_id,
                "provider_instance_id": f"session-{provider_id}",
                "qualification_result": "qualified",
            },
        )
        self.registrations[registration_id] = {
            "service_state": "QUALIFIED",
            "trusted_registration_id": registration_id,
            "logical_provider_id": provider_id,
            "canonical_executable_path": executable,
            "executable_sha256": executable_digest,
            "configuration_digest": hashlib.sha256(
                f"registration:{registration_id}:{executable_digest}".encode()
            ).hexdigest(),
        }
        self.qualifications[qualification_id] = {
            "service_state": "QUALIFIED",
            "evidence": qualification,
        }

    def __call__(self, request: Request) -> dict[str, Any]:
        operation = request.operation
        payload = request.payload
        with self._lock:
            if operation is Operation.QUERY_STATE:
                table = {
                    "registrations": self.registrations,
                    "qualifications": self.qualifications,
                    "attempts": self.attempts,
                }[str(payload["kind"])]
                record = table.get(str(payload["id"]))
                return {
                    "found": record is not None,
                    "record": dict(record) if record is not None else None,
                }
            if operation is Operation.VERIFY_EVIDENCE:
                record = payload.get("record")
                return {
                    "valid": isinstance(record, dict)
                    and record.get("_purpose") == payload.get("purpose")
                    and record.get("_signature") == "authority-test-signature"
                }
            if operation is Operation.RESERVE_ATTEMPT:
                attempt_id = (
                    f"provider-attempt:{payload['keeper_run_id']}:"
                    f"{payload['provider_run_id']}"
                )
                if attempt_id in self.attempts:
                    raise PermissionError("provider attempt already exists")
                attempt = self._sign(
                    "provider-launch-authorization",
                    {
                        "id": attempt_id,
                        "kind": "provider_launch_authorization",
                        **payload,
                        "registration_digest": self.registrations[
                            str(payload["registration_id"])
                        ]["configuration_digest"],
                        "workspace": str(Path(str(payload["workspace"])).resolve()),
                    },
                )
                self.attempts[attempt_id] = {
                    **attempt,
                    "service_state": "RESERVED",
                }
                if self.raise_after_reservation:
                    self.raise_after_reservation = False
                    raise RuntimeError(
                        "reservation response lost after durable reserve"
                    )
                return {"attempt": attempt, "attempt_id": attempt_id}
            if operation is Operation.CANCEL_ATTEMPT:
                attempt_id = str(payload["attempt_id"])
                attempt = self.attempts[attempt_id]
                if attempt["service_state"] not in {
                    "RESERVED",
                    "EXECUTION_STARTED",
                }:
                    raise PermissionError("attempt is not cancelable")
                attempt["service_state"] = "CANCELLED"
                return {"attempt_id": attempt_id, "state": "CANCELLED"}
            if operation is Operation.EXECUTE_PROVIDER:
                attempt_id = str(payload["attempt_id"])
                attempt = self.attempts[attempt_id]
                if attempt["service_state"] != "RESERVED":
                    raise PermissionError("attempt is not reserved")
                attempt["service_state"] = "EXECUTION_STARTED"
                self.execution_calls.append(attempt_id)
                self.side_effect_count += 1
                started = self.started
                release = self.release
            elif operation is Operation.FINALIZE_COMPLETION:
                attempt_id = str(payload["attempt_id"])
                attempt = self.attempts[attempt_id]
                if attempt["service_state"] == "COMPLETED":
                    completion = dict(attempt)
                    completion.pop("service_state")
                    return {
                        "attempt_id": attempt_id,
                        "completion": completion,
                    }
                raise PermissionError("attempt is not finalizable")
            elif operation is Operation.DIAGNOSTICS:
                return {"status": "RUNNING"}
            else:
                raise AssertionError(f"unsupported test operation: {operation}")
        if started is not None:
            started.set()
        if release is not None:
            release.wait(timeout=10)
        with self._lock:
            attempt = self.attempts[attempt_id]
            if (
                attempt["service_state"] == "CANCELLED"
                and not self.ignore_cancel_completion
            ):
                return {"attempt_id": attempt_id, "cancelled": True}
            if self.raise_after_side_effect:
                raise RuntimeError("provider response lost after side effect")
            evidence_digest = hashlib.sha256(
                f"evidence:{attempt_id}".encode()
            ).hexdigest()
            completion = self._sign(
                "provider-completion",
                {
                    "id": f"completion:{attempt_id}",
                    "kind": "provider_completion",
                    "attempt_id": attempt_id,
                    "task_id": attempt["task_id"],
                    "stage_id": attempt["stage_id"],
                    "role": attempt["role"],
                    "registration_id": attempt["registration_id"],
                    "provider_instance_id": attempt["provider_instance_id"],
                    "normalized_result": (
                        "failed"
                        if self.fail_review_once
                        and attempt["role"] == "independent reviewer"
                        else "completed"
                    ),
                    "provider_evidence_digest": evidence_digest,
                },
            )
            if (
                self.fail_review_once
                and attempt["role"] == "independent reviewer"
            ):
                self.fail_review_once = False
            if self.unsigned_completion:
                completion.pop("_signature")
            if self.wrong_completion_field is not None:
                field, value = self.wrong_completion_field
                completion[field] = value
            self.attempts[attempt_id] = {
                **completion,
                "service_state": "COMPLETED",
            }
            return {
                "attempt_id": attempt_id,
                "completion": completion,
            }

    @staticmethod
    def _sign(purpose: str, record: dict[str, Any]) -> dict[str, Any]:
        return {
            **record,
            "_purpose": purpose,
            "_signature": "authority-test-signature",
        }


def semantic_gateway(
    tmp_path: Path,
    *,
    transport: SemanticAuthorityTransport | None = None,
    bindings: tuple[AuthorityProviderBinding, ...] | None = None,
) -> tuple[AuthorityBackedSpecialistGateway, SemanticAuthorityTransport]:
    semantic = transport or SemanticAuthorityTransport()
    client = AuthorityServiceClient(test_transport=semantic)
    configured = bindings or (
        AuthorityProviderBinding(
            "registration-codex",
            "qualification-codex",
            ALL_CAPABILITIES,
            ("software", "research", "general"),
            "codex-test",
        ),
        AuthorityProviderBinding(
            "registration-claude",
            "qualification-claude",
            ALL_CAPABILITIES,
            ("software", "research", "general"),
            "claude-test",
        ),
    )
    return (
        AuthorityBackedSpecialistGateway(
            authority_operations(client),
            configured,
            tmp_path / "authority-exchange",
        ),
        semantic,
    )
