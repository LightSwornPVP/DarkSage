from __future__ import annotations

import hashlib
import json
import sys
import tempfile
from pathlib import Path
from typing import Any

REPOSITORY = Path(__file__).resolve().parents[1]
if str(REPOSITORY) not in sys.path:
    sys.path.insert(0, str(REPOSITORY))

from keeper.executive.authority_gateway import (
    AuthorityBackedSpecialistGateway,
    AuthorityProviderBinding,
)
from keeper.executive.enums import FounderApprovalIntent
from keeper.executive.runtime import ExecutiveRuntime
from keeper.executive.service import KeeperExecutive


CAPABILITIES = (
    "requirements",
    "architecture",
    "implementation",
    "testing",
    "security",
    "packaging",
    "acceptance",
)


class PilotAuthorityTransport:
    """Injected Authority-semantic pilot transport; never production authority."""

    def __init__(self) -> None:
        self.registrations: dict[str, dict[str, Any]] = {}
        self.qualifications: dict[str, dict[str, Any]] = {}
        self.attempts: dict[str, dict[str, Any]] = {}
        self.execution_count = 0
        for provider_id in ("codex", "reviewer-provider"):
            registration_id = f"pilot-registration-{provider_id}"
            qualification_id = f"pilot-qualification-{provider_id}"
            executable = f"C:/Pilot/{provider_id}.exe"
            executable_digest = self._digest(executable)
            registration_digest = self._digest(
                f"{registration_id}:{executable_digest}"
            )
            self.registrations[registration_id] = {
                "service_state": "QUALIFIED",
                "logical_provider_id": provider_id,
                "canonical_executable_path": executable,
                "executable_sha256": executable_digest,
                "configuration_digest": registration_digest,
                "capability_set": list(CAPABILITIES),
                "role_eligibility": ["software"],
                "model_or_service_identity": f"pilot-{provider_id}",
                "independence_classification": provider_id,
                "effort_levels": ["medium", "high"],
                "pricing_authority": {
                    "pricing_identity": f"pilot-pricing:{registration_id}",
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
                "evidence": self._sign(
                    "provider-qualification",
                    {
                        "id": qualification_id,
                        "registration_id": registration_id,
                        "provider_instance_id": f"pilot-session-{provider_id}",
                        "qualification_result": "qualified",
                    },
                ),
            }

    def diagnostics(self) -> dict[str, Any]:
        return {"status": "PILOT_INJECTED_TRANSPORT"}

    def query_state(
        self, kind: str, identifier: str
    ) -> dict[str, Any]:
        values = {
            "registrations": self.registrations,
            "qualifications": self.qualifications,
            "attempts": self.attempts,
        }[kind]
        record = values.get(identifier)
        return {
            "found": record is not None,
            "record": dict(record) if record is not None else None,
        }

    def reserve_attempt(self, **identity: Any) -> dict[str, Any]:
        attempt_id = (
            f"provider-attempt:{identity['keeper_run_id']}:"
            f"{identity['provider_run_id']}"
        )
        if attempt_id in self.attempts:
            raise PermissionError("pilot Authority attempt already exists")
        registration = self.registrations[
            str(identity["registration_id"])
        ]
        attempt = self._sign(
            "provider-launch-authorization",
            {
                "id": attempt_id,
                **identity,
                "workspace": str(
                    Path(str(identity["workspace"])).resolve()
                ),
                "registration_digest": registration[
                    "configuration_digest"
                ],
            },
        )
        self.attempts[attempt_id] = {
            **attempt,
            "service_state": "RESERVED",
        }
        return {"attempt_id": attempt_id, "attempt": attempt}

    def execute_provider(self, attempt_id: str) -> dict[str, Any]:
        attempt = self.attempts[attempt_id]
        if attempt["service_state"] != "RESERVED":
            raise PermissionError("pilot Authority attempt is not reserved")
        self.execution_count += 1
        completion = self._sign(
            "provider-completion",
            {
                "id": f"pilot-completion:{attempt_id}",
                "attempt_id": attempt_id,
                "task_id": attempt["task_id"],
                "stage_id": attempt["stage_id"],
                "role": attempt["role"],
                "registration_id": attempt["registration_id"],
                "provider_instance_id": attempt["provider_instance_id"],
                "normalized_result": "completed",
                "provider_evidence_digest": self._digest(
                    f"pilot-evidence:{attempt_id}"
                ),
            },
        )
        self.attempts[attempt_id] = {
            **completion,
            "service_state": "COMPLETED",
        }
        return {"attempt_id": attempt_id, "completion": completion}

    def finalize_completion(self, attempt_id: str) -> dict[str, Any]:
        record = dict(self.attempts[attempt_id])
        if record.pop("service_state") != "COMPLETED":
            raise PermissionError("pilot completion is unavailable")
        return {"attempt_id": attempt_id, "completion": record}

    def cancel_attempt(self, attempt_id: str) -> dict[str, Any]:
        self.attempts[attempt_id]["service_state"] = "CANCELLED"
        return {"attempt_id": attempt_id, "state": "CANCELLED"}

    @staticmethod
    def verify(purpose: str, record: object) -> bool:
        return (
            isinstance(record, dict)
            and record.get("_purpose") == purpose
            and record.get("_signature") == "pilot-authority-signature"
        )

    @staticmethod
    def _sign(
        purpose: str, record: dict[str, Any]
    ) -> dict[str, Any]:
        return {
            **record,
            "_purpose": purpose,
            "_signature": "pilot-authority-signature",
        }

    @staticmethod
    def _digest(value: str) -> str:
        return hashlib.sha256(value.encode("utf-8")).hexdigest()


def main() -> int:
    with tempfile.TemporaryDirectory(
        prefix="keeper-executive-pilot-"
    ) as directory:
        root = Path(directory)
        executive = KeeperExecutive(root / "keeper.db")
        project, intake = executive.begin(
            f"I want a small application called Pilot List in {root}. "
            "Use full delegation and no spending."
        )
        draft = executive.draft(
            project.project_id,
            intake,
            founder_revisions={
                "success_criteria": ("all pilot checks pass",),
                "target_audience": "pilot user",
                "approved_providers": ("codex", "reviewer-provider"),
                "approved_tools": ("filesystem",),
            },
        )
        proposed = executive.charters.propose(draft)
        challenge = executive.charters.request_approval(proposed)
        approved, _, _ = executive.charters.confirm_approval(
            challenge.challenge_id,
            intent=FounderApprovalIntent.APPROVE_CHARTER,
        )
        active = executive.charters.activate(approved)
        authority = PilotAuthorityTransport()
        bindings = tuple(
            AuthorityProviderBinding(
                f"pilot-registration-{provider_id}",
                f"pilot-qualification-{provider_id}",
            )
            for provider_id in ("codex", "reviewer-provider")
        )
        runtime = ExecutiveRuntime(
            executive.repository,
            AuthorityBackedSpecialistGateway(
                authority,
                bindings,
                root / "authority-exchange",
            ),
        )
        for _ in range(20):
            active = runtime.progress(active.project_id)
            if active.state == "COMPLETED":
                break
        print(
            json.dumps(
                {
                    "project_id": active.project_id,
                    "status": active.state,
                    "tasks": len(
                        executive.repository.tasks(active.project_id)
                    ),
                    "evidence": len(
                        executive.repository.memories(active.project_id)
                    ),
                    "authority_attempts_executed": authority.execution_count,
                    "execution_mode": "authority-semantic-injected-transport",
                    "production_authoritative": False,
                },
                sort_keys=True,
            )
        )
        return 0 if active.state == "COMPLETED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
