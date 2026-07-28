from __future__ import annotations

import hashlib
import json
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from keeper.authority_service.client import TestAuthorityServiceClient
from keeper.authority_service.protocol import Operation, Request
from keeper.executive.authority_gateway import (
    AuthorityBackedSpecialistGateway,
    AuthorityProviderBinding,
    SemanticAuthorityTestGateway,
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
        self.normalized_result_override: str | None = None
        self.review_normalized_result_override: str | None = None
        self.review_disposition = "ACCEPTED"
        self.malformed_review = False
        self.omit_author_artifact = False
        self.wrong_review_artifact = False
        self.mutate_artifact_during_review = False
        self.started: threading.Event | None = None
        self.release: threading.Event | None = None
        self._lock = threading.RLock()
        self._install_provider("registration-codex", "qualification-codex", "codex")
        self._install_provider(
            "registration-reviewer",
            "qualification-reviewer",
            "reviewer-provider",
        )

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
            "capability_set": list(ALL_CAPABILITIES),
            "role_eligibility": ["software", "research", "general"],
            "model_or_service_identity": f"{provider_id}-test",
            "independence_classification": provider_id,
            "effort_levels": ["medium", "high"],
            "pricing_authority": {
                "pricing_identity": f"pricing:{registration_id}",
                "pricing_version": "2026-07",
                "currency": "USD",
                "estimated_cost": 0.0,
                "maximum_cost": 0.0,
                "billing_unit": "included-session",
                "included_plan": True,
                "marginally_free": True,
                "quoted_at": "2026-07-01T00:00:00+00:00",
                "expires_at": "2099-01-01T00:00:00+00:00",
                "source": "AUTHORITY_REGISTRATION",
                "cost_tier": 0,
            },
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
            normalized_result = (
                self.review_normalized_result_override
                if attempt["role"] == "reviewer"
                and self.review_normalized_result_override is not None
                else self.normalized_result_override or "completed"
            )
            if normalized_result == "completed":
                prompt = json.loads(
                    Path(str(attempt["prompt_path"])).read_text(encoding="utf-8")
                )
                stdout = Path(str(attempt["stdout_path"]))
                stderr = Path(str(attempt["stderr_path"]))
                stderr.write_text("", encoding="utf-8")
                if attempt["role"] == "reviewer":
                    disposition = (
                        "REPAIR_REQUIRED"
                        if self.fail_review_once
                        else self.review_disposition
                    )
                    review = {
                        "schema_version": 1,
                        "review_id": f"review:{attempt_id}",
                        "review_attempt_id": attempt_id,
                        "reviewer_registration": attempt["registration_id"],
                        "reviewer_qualification": prompt[
                            "provider_qualification_id"
                        ],
                        "reviewer_independence_identity": attempt[
                            "provider_instance_id"
                        ],
                        "project_id": prompt["global_brief"]["project_id"],
                        "charter_revision": prompt["global_brief"][
                            "charter_revision"
                        ],
                        "workflow_id": attempt["keeper_run_id"].split(":")[-1],
                        "task_id": prompt["task_guidance"]["task_id"],
                        "author_attempt_id": prompt["author_attempt_id"],
                        "artifact_identity": (
                            f"file-set:{prompt['task_guidance']['task_id']}"
                        ),
                        "artifact_digest": (
                            "0" * 64
                            if self.wrong_review_artifact
                            else prompt["artifact_revision_digest"]
                        ),
                        "evidence_digest": hashlib.sha256(
                            f"review:{attempt_id}".encode()
                        ).hexdigest(),
                        "review_criteria_version": "keeper-review-v1",
                        "review_criteria_digest": prompt[
                            "review_criteria_digest"
                        ],
                        "review_disposition": disposition,
                        "findings": (
                            []
                            if disposition == "ACCEPTED"
                            else [
                                {
                                    "finding_id": "finding-1",
                                    "severity": "High",
                                    "title": "repair required",
                                    "description": "deterministic review fixture",
                                }
                            ]
                        ),
                        "failed_criteria": (
                            [] if disposition == "ACCEPTED" else ["criterion-1"]
                        ),
                        "required_repairs": (
                            [] if disposition == "ACCEPTED" else ["repair-1"]
                        ),
                        "timestamp": datetime.now(UTC).isoformat(),
                    }
                    if self.malformed_review:
                        review.pop("review_disposition")
                    stdout.write_text(json.dumps(review), encoding="utf-8")
                    if self.mutate_artifact_during_review:
                        artifacts = sorted(
                            Path(str(attempt["workspace"]))
                            .joinpath(".keeper-artifacts")
                            .glob("*.json")
                        )
                        if artifacts:
                            artifacts[-1].write_text(
                                "mutated during review", encoding="utf-8"
                            )
                else:
                    relative = (
                        Path(".keeper-artifacts")
                        / f"{hashlib.sha256(attempt_id.encode()).hexdigest()}.json"
                    )
                    artifact = Path(str(attempt["workspace"])) / relative
                    if not self.omit_author_artifact:
                        artifact.parent.mkdir(parents=True, exist_ok=True)
                        artifact.write_text(
                            json.dumps(
                                {
                                    "attempt_id": attempt_id,
                                    "task_id": attempt["task_id"],
                                },
                                sort_keys=True,
                            ),
                            encoding="utf-8",
                        )
                    stdout.write_text(
                        json.dumps(
                            {
                                "status": "completed",
                                "files_changed": [relative.as_posix()],
                            }
                        ),
                        encoding="utf-8",
                    )
            else:
                Path(str(attempt["stdout_path"])).write_text("", encoding="utf-8")
                Path(str(attempt["stderr_path"])).write_text(
                    normalized_result, encoding="utf-8"
                )
            stdout_bytes = Path(str(attempt["stdout_path"])).read_bytes()
            stderr_bytes = Path(str(attempt["stderr_path"])).read_bytes()
            evidence_digest = hashlib.sha256(
                json.dumps(
                    {
                        "stdout_sha256": hashlib.sha256(stdout_bytes).hexdigest(),
                        "stderr_sha256": hashlib.sha256(stderr_bytes).hexdigest(),
                    },
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode()
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
                    "normalized_result": normalized_result,
                    "provider_evidence_digest": evidence_digest,
                },
            )
            if (
                self.fail_review_once
                and attempt["role"] == "reviewer"
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
) -> tuple[SemanticAuthorityTestGateway, SemanticAuthorityTransport]:
    semantic = transport or SemanticAuthorityTransport()
    client = TestAuthorityServiceClient(semantic)
    configured = bindings or (
        AuthorityProviderBinding(
            "registration-codex",
            "qualification-codex",
        ),
        AuthorityProviderBinding(
            "registration-reviewer",
            "qualification-reviewer",
        ),
    )
    return (
        SemanticAuthorityTestGateway(
            authority_operations(client),
            configured,
            tmp_path / "authority-exchange",
        ),
        semantic,
    )
