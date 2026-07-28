from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Protocol

from keeper.authority_service.client import AuthorityServiceClient
from keeper.executive.models import (
    ExecutiveTask,
    ProjectCharter,
    SpecialistProfile,
)
from keeper.executive.specialists import GuidanceBuilder


class AuthorityOperations(Protocol):
    """Narrow executive view of the approved Authority Service contract."""

    def diagnostics(self) -> dict[str, Any]: ...
    def query_state(self, kind: str, identifier: str) -> dict[str, Any]: ...
    def reserve_attempt(self, **identity: Any) -> dict[str, Any]: ...
    def execute_provider(self, attempt_id: str) -> dict[str, Any]: ...
    def finalize_completion(self, attempt_id: str) -> dict[str, Any]: ...
    def cancel_attempt(self, attempt_id: str) -> dict[str, Any]: ...
    def verify(self, purpose: str, record: object) -> bool: ...


@dataclass(frozen=True, slots=True)
class AuthorityProviderBinding:
    registration_id: str
    qualification_id: str


@dataclass(frozen=True, slots=True)
class AuthorityExecutionPlan:
    authority_attempt_id: str
    project_id: str
    charter_id: str
    charter_revision: int
    workflow_id: str
    task_id: str
    task_revision: int
    stage_id: str
    role: str
    provider_id: str
    model_id: str
    session_id: str
    registration_id: str
    qualification_id: str
    registration_digest: str
    executable: str
    executable_digest: str
    workspace: str
    instructions_digest: str
    expected_outputs_digest: str
    expected_evidence_digest: str
    artifact_revision_digest: str | None
    reservation_payload: dict[str, Any]

    def binding(self) -> dict[str, Any]:
        value = asdict(self)
        value.pop("reservation_payload")
        return value


@dataclass(frozen=True, slots=True)
class AuthenticatedExecutionResult:
    authority_attempt_id: str
    task_id: str
    stage_id: str
    role: str
    provider_id: str
    model_id: str
    session_id: str
    registration_id: str
    executable_digest: str
    normalized_result: str
    artifact_digest: str
    completion_digest: str
    authenticated: bool


def authority_operations(client: AuthorityServiceClient) -> AuthorityOperations:
    """Dependency-inversion seam; no signing or protected state enters Executive."""
    return client


class AuthorityBackedSpecialistGateway:
    """Production boundary for all Executive author and reviewer execution."""

    __slots__ = ("_authority", "_bindings", "_exchange_root", "_resolved")

    def __init__(
        self,
        authority: AuthorityOperations,
        bindings: tuple[AuthorityProviderBinding, ...],
        exchange_root: Path,
    ) -> None:
        if not bindings:
            raise RuntimeError(
                "production Executive startup requires Authority provider bindings"
            )
        self._authority = authority
        self._bindings = bindings
        self._exchange_root = exchange_root.resolve()
        self._resolved: dict[
            tuple[str, str, str], tuple[AuthorityProviderBinding, dict[str, Any]]
        ] = {}

    def specialists(
        self,
        charter: ProjectCharter,
    ) -> tuple[SpecialistProfile, ...]:
        profiles: list[SpecialistProfile] = []
        self._resolved.clear()
        for binding in self._bindings:
            registration_state = self._authority.query_state(
                "registrations", binding.registration_id
            )
            qualification_state = self._authority.query_state(
                "qualifications", binding.qualification_id
            )
            registration = _record(registration_state, "registration")
            qualification_container = _record(
                qualification_state, "qualification"
            )
            qualification = qualification_container.get("evidence")
            if not isinstance(qualification, dict):
                continue
            if (
                registration.get("service_state") != "QUALIFIED"
                or qualification_container.get("service_state") != "QUALIFIED"
                or qualification.get("registration_id")
                != binding.registration_id
                or qualification.get("id") != binding.qualification_id
                or qualification.get("qualification_result") != "qualified"
                or not self._authority.verify(
                    "provider-qualification", qualification
                )
            ):
                continue
            provider_id = str(registration.get("logical_provider_id", ""))
            session_id = str(qualification.get("provider_instance_id", ""))
            executable = str(
                registration.get("canonical_executable_path", "")
            )
            executable_digest = str(
                registration.get("executable_sha256", "")
            )
            if (
                not provider_id
                or not session_id
                or not executable
                or not executable_digest
                or provider_id not in charter.approved_providers
            ):
                continue
            capabilities = registration.get("capability_set")
            project_types = registration.get("role_eligibility")
            model_id = registration.get("model_or_service_identity")
            independence = registration.get("independence_classification")
            effort_levels = registration.get("effort_levels")
            pricing = registration.get("pricing_authority")
            if (
                not isinstance(capabilities, list)
                or not capabilities
                or not all(isinstance(item, str) for item in capabilities)
                or not isinstance(project_types, list)
                or not project_types
                or not all(isinstance(item, str) for item in project_types)
                or not isinstance(model_id, str)
                or not model_id
                or not isinstance(independence, str)
                or not independence
                or not isinstance(effort_levels, list)
                or not effort_levels
                or not isinstance(pricing, dict)
            ):
                continue
            profile = SpecialistProfile(
                provider_id,
                model_id,
                session_id,
                tuple(capabilities),
                tuple(project_types),
                True,
                True,
                f"{independence}:{binding.registration_id}:{session_id}",
                int(pricing.get("cost_tier", -1)),
                tuple(str(item) for item in effort_levels),
                True,
                1.0,
                str(pricing["pricing_identity"]) if pricing.get("pricing_identity") else None,
                str(pricing["pricing_version"]) if pricing.get("pricing_version") else None,
                str(pricing["currency"]) if pricing.get("currency") else None,
                float(pricing["estimated_cost"]) if isinstance(pricing.get("estimated_cost"), (int, float)) else None,
                float(pricing["maximum_cost"]) if isinstance(pricing.get("maximum_cost"), (int, float)) else None,
                str(pricing["billing_unit"]) if pricing.get("billing_unit") else None,
                pricing.get("included_plan") is True,
                pricing.get("marginally_free") is True,
                str(pricing["quoted_at"]) if pricing.get("quoted_at") else None,
                str(pricing["expires_at"]) if pricing.get("expires_at") else None,
                str(pricing["source"]) if pricing.get("source") else None,
            )
            key = (profile.provider_id, profile.model_id, profile.session_id)
            self._resolved[key] = (binding, registration)
            profiles.append(profile)
        return tuple(profiles)

    def prepare(
        self,
        task: ExecutiveTask,
        charter: ProjectCharter,
        specialist: SpecialistProfile,
        *,
        task_id: str | None = None,
        role: str | None = None,
        artifact_revision_digest: str | None = None,
        review_instructions: tuple[str, ...] = (),
    ) -> AuthorityExecutionPlan:
        key = (
            specialist.provider_id,
            specialist.model_id,
            specialist.session_id,
        )
        resolved = self._resolved.get(key)
        if resolved is None:
            raise PermissionError(
                "specialist identity did not come from current Authority state"
            )
        binding, registration = resolved
        launch_task_id = task_id or task.task_id
        launch_role = role or task.role
        prompt = {
            "global_brief": GuidanceBuilder.global_brief(charter).to_dict(),
            "task_guidance": GuidanceBuilder.task_guidance(
                task, charter
            ).to_dict(),
            "review_instructions": review_instructions,
            "artifact_revision_digest": artifact_revision_digest,
            "provider_registration_id": binding.registration_id,
            "provider_qualification_id": binding.qualification_id,
        }
        instructions_digest = _digest(prompt)
        expected_outputs_digest = _digest(task.expected_outputs)
        expected_evidence_digest = _digest(task.evidence_requirements)
        binding_material = {
            "project_id": task.project_id,
            "charter_id": task.charter_id,
            "charter_revision": task.charter_revision,
            "workflow_id": task.workflow_id,
            "task_id": launch_task_id,
            "task_revision": task.revision,
            "stage_id": task.stage_id,
            "role": launch_role,
            "registration_id": binding.registration_id,
            "qualification_id": binding.qualification_id,
            "workspace": charter.workspaces[0],
            "instructions_digest": instructions_digest,
            "expected_outputs_digest": expected_outputs_digest,
            "expected_evidence_digest": expected_evidence_digest,
            "artifact_revision_digest": artifact_revision_digest,
        }
        provider_run_id = f"executive-{_digest(binding_material)[:32]}"
        keeper_run_id = (
            f"executive:{task.project_id}:{task.charter_id}:"
            f"r{task.charter_revision}:{task.workflow_id}"
        )
        attempt_id = f"provider-attempt:{keeper_run_id}:{provider_run_id}"
        attempt_root = (
            self._exchange_root
            / _digest(task.project_id)[:12]
            / _digest(launch_task_id)[:12]
            / _digest(provider_run_id)[:12]
        )
        attempt_root.mkdir(parents=True, exist_ok=True)
        prompt_path = attempt_root / "prompt.json"
        evidence_path = attempt_root / "evidence.json"
        stdout_path = attempt_root / "stdout.txt"
        stderr_path = attempt_root / "stderr.txt"
        prompt_path.write_text(
            json.dumps(prompt, sort_keys=True, separators=(",", ":")),
            encoding="utf-8",
        )
        reservation_payload: dict[str, Any] = {
            "registration_id": binding.registration_id,
            "keeper_run_id": keeper_run_id,
            "task_id": launch_task_id,
            "stage_id": task.stage_id,
            "role": launch_role,
            "attempt_number": task.retry_count + 1,
            "provider_run_id": provider_run_id,
            "provider_instance_id": specialist.session_id,
            "evidence_path": str(evidence_path),
            "prompt_path": str(prompt_path),
            "stdout_path": str(stdout_path),
            "stderr_path": str(stderr_path),
            "workspace": charter.workspaces[0],
            "timeout_seconds": 3600,
            "reasoning_level": "high",
            "environment": {
                "KEEPER_EXECUTIVE_BINDING_DIGEST": _digest(binding_material)
            },
        }
        return AuthorityExecutionPlan(
            attempt_id,
            task.project_id,
            task.charter_id,
            task.charter_revision,
            task.workflow_id,
            launch_task_id,
            task.revision,
            task.stage_id,
            launch_role,
            specialist.provider_id,
            specialist.model_id,
            specialist.session_id,
            binding.registration_id,
            binding.qualification_id,
            str(registration["configuration_digest"]),
            str(registration["canonical_executable_path"]),
            str(registration["executable_sha256"]),
            charter.workspaces[0],
            instructions_digest,
            expected_outputs_digest,
            expected_evidence_digest,
            artifact_revision_digest,
            reservation_payload,
        )

    def reserve(self, plan: AuthorityExecutionPlan) -> None:
        result = self._authority.reserve_attempt(**plan.reservation_payload)
        attempt = result.get("attempt")
        if (
            result.get("attempt_id") != plan.authority_attempt_id
            or not isinstance(attempt, dict)
            or not self._authority.verify(
                "provider-launch-authorization", attempt
            )
            or attempt.get("registration_id") != plan.registration_id
            or attempt.get("registration_digest")
            != plan.registration_digest
            or attempt.get("task_id") != plan.task_id
            or attempt.get("stage_id") != plan.stage_id
            or attempt.get("role") != plan.role
            or attempt.get("workspace") != str(Path(plan.workspace).resolve())
        ):
            raise PermissionError(
                "Authority attempt reservation binding is invalid"
            )

    def execute(
        self,
        plan: AuthorityExecutionPlan,
    ) -> AuthenticatedExecutionResult:
        self._revalidate_provider(plan)
        launched = self._authority.execute_provider(
            plan.authority_attempt_id
        )
        completion = launched.get("completion")
        if not isinstance(completion, dict):
            finalized = self._authority.finalize_completion(
                plan.authority_attempt_id
            )
            completion = finalized.get("completion")
        return self._authenticated_result(plan, completion)

    def reconcile(
        self,
        plan: AuthorityExecutionPlan,
    ) -> AuthenticatedExecutionResult | None:
        state = self._authority.query_state(
            "attempts", plan.authority_attempt_id
        )
        record = state.get("record")
        if not state.get("found") or not isinstance(record, dict):
            return None
        if record.get("service_state") not in {"COMPLETED", "FAILED"}:
            return None
        completion = dict(record)
        completion.pop("service_state", None)
        return self._authenticated_result(plan, completion)

    def attempt_state(self, attempt_id: str) -> str | None:
        state = self._authority.query_state("attempts", attempt_id)
        record = state.get("record")
        if not state.get("found") or not isinstance(record, dict):
            return None
        value = record.get("service_state")
        return str(value) if value is not None else None

    def cancel(self, attempt_id: str) -> None:
        self._authority.cancel_attempt(attempt_id)

    @staticmethod
    def plan_from_record(record: dict[str, Any]) -> AuthorityExecutionPlan:
        fields = AuthorityExecutionPlan.__dataclass_fields__
        return AuthorityExecutionPlan(
            **{name: record[name] for name in fields}
        )

    def _authenticated_result(
        self,
        plan: AuthorityExecutionPlan,
        completion: object,
    ) -> AuthenticatedExecutionResult:
        if not isinstance(completion, dict):
            raise PermissionError("Authority completion is missing")
        if (
            not self._authority.verify("provider-completion", completion)
            or completion.get("attempt_id") != plan.authority_attempt_id
            or completion.get("task_id") != plan.task_id
            or completion.get("stage_id") != plan.stage_id
            or completion.get("role") != plan.role
            or completion.get("registration_id") != plan.registration_id
            or completion.get("provider_instance_id") != plan.session_id
            or not isinstance(
                completion.get("provider_evidence_digest"), str
            )
        ):
            raise PermissionError(
                "Authority completion authentication or binding is invalid"
            )
        evidence_digest = str(completion["provider_evidence_digest"])
        if (
            len(evidence_digest) != 64
            or any(character not in "0123456789abcdef" for character in evidence_digest)
        ):
            raise PermissionError(
                "Authority evidence digest is not canonical SHA-256"
            )
        return AuthenticatedExecutionResult(
            plan.authority_attempt_id,
            plan.task_id,
            plan.stage_id,
            plan.role,
            plan.provider_id,
            plan.model_id,
            plan.session_id,
            plan.registration_id,
            plan.executable_digest,
            str(completion.get("normalized_result", "")),
            evidence_digest,
            _digest(completion),
            True,
        )

    def _revalidate_provider(self, plan: AuthorityExecutionPlan) -> None:
        registration = _record(
            self._authority.query_state(
                "registrations", plan.registration_id
            ),
            "registration",
        )
        if (
            registration.get("service_state") != "QUALIFIED"
            or registration.get("configuration_digest")
            != plan.registration_digest
            or registration.get("canonical_executable_path")
            != plan.executable
            or registration.get("executable_sha256")
            != plan.executable_digest
        ):
            raise PermissionError(
                "Authority provider registration changed before launch"
            )


def _record(state: dict[str, Any], name: str) -> dict[str, Any]:
    record = state.get("record")
    if not state.get("found") or not isinstance(record, dict):
        raise PermissionError(f"Authority {name} record is unavailable")
    return record


def _digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        ).encode("utf-8")
    ).hexdigest()
