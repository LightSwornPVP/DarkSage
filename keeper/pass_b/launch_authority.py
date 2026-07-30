from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable, Protocol, cast

from keeper.authority_service.client import (
    AuthorityServiceClient,
    ProductionAuthorityServiceClient,
    TestAuthorityServiceClient,
)
from keeper.executive.service import KeeperExecutive
from keeper.pass_b.models import (
    AssignmentRecord,
    ProviderRecord,
    WorkflowRecord,
    WorkItemRecord,
    WorkspaceReservationRecord,
)
from keeper.pass_b.providers import (
    AdapterAssignment,
    AdapterResult,
    ProviderAdapter,
)
from keeper.pass_b.repository import canonical_workspace_path


class ProjectStatusReader(Protocol):
    def __call__(self, project_id: str) -> dict[str, Any]: ...


@dataclass(frozen=True, slots=True)
class LaunchAuthorization:
    authority_attempt_id: str
    launch_token: str
    launch_plan_digest: str
    launch_authorization_id: str
    authorization_generation: int
    stdout_path: str
    stderr_path: str


class LaunchAuthority(Protocol):
    def authorize(
        self,
        workflow: WorkflowRecord,
        work_item: WorkItemRecord,
        assignment: AssignmentRecord,
        provider: ProviderRecord,
        workspace: WorkspaceReservationRecord,
        authority_attempt_id: str,
    ) -> LaunchAuthorization: ...

    def launch(
        self,
        authorization: LaunchAuthorization,
        request: AdapterAssignment,
        adapter: ProviderAdapter,
    ) -> AdapterResult: ...


class UnavailableLaunchAuthority:
    """Fail-closed launch authority used when production is not configured."""

    def authorize(
        self,
        workflow: WorkflowRecord,
        work_item: WorkItemRecord,
        assignment: AssignmentRecord,
        provider: ProviderRecord,
        workspace: WorkspaceReservationRecord,
        authority_attempt_id: str,
    ) -> LaunchAuthorization:
        del workflow, work_item, assignment, provider, workspace, authority_attempt_id
        raise PermissionError(
            "Pass B launch requires active Executive and KeeperAuthority binding"
        )

    def launch(
        self,
        authorization: LaunchAuthorization,
        request: AdapterAssignment,
        adapter: ProviderAdapter,
    ) -> AdapterResult:
        del authorization, request, adapter
        raise PermissionError("Pass B launch authority is unavailable")


class ExecutiveAuthorityLaunchGate:
    """Validates one Executive charter and signed Authority attempt per launch."""

    def __init__(
        self,
        authority: AuthorityServiceClient,
        project_status: ProjectStatusReader,
        *,
        production: bool,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        if production and not isinstance(
            authority, ProductionAuthorityServiceClient
        ):
            raise TypeError("production launch gate requires the production client")
        if not production and not isinstance(
            authority, TestAuthorityServiceClient
        ):
            raise TypeError("test launch gate requires an explicit test client")
        self._authority = authority
        self._project_status = project_status
        self._production = production
        self._clock = clock or (lambda: datetime.now(UTC))

    @classmethod
    def production(
        cls,
        executive: KeeperExecutive,
        authority: ProductionAuthorityServiceClient,
    ) -> ExecutiveAuthorityLaunchGate:
        authority.require_live_identity()
        return cls(
            authority,
            lambda project_id: _status_dict(executive, project_id),
            production=True,
        )

    @classmethod
    def test(
        cls,
        authority: TestAuthorityServiceClient,
        project_status: ProjectStatusReader,
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> ExecutiveAuthorityLaunchGate:
        return cls(
            authority,
            project_status,
            production=False,
            clock=clock,
        )

    def authorize(
        self,
        workflow: WorkflowRecord,
        work_item: WorkItemRecord,
        assignment: AssignmentRecord,
        provider: ProviderRecord,
        workspace: WorkspaceReservationRecord,
        authority_attempt_id: str,
    ) -> LaunchAuthorization:
        if not provider.authority_registration_id:
            raise PermissionError(
                "provider has no durable KeeperAuthority registration"
            )
        _validate_durable_binding(workflow, work_item, assignment)
        charter = self._active_charter(assignment)
        self._validate_charter_scope(charter, assignment, workspace)
        state = self._authority.query_state("attempts", authority_attempt_id)
        record = _queried_record(state, "Authority attempt")
        service_state = record.pop("service_state", None)
        if service_state != "RESERVED" or not self._authority.verify(
            "provider-launch-authorization", record
        ):
            raise PermissionError("Authority attempt is not valid and reserved")
        expected: dict[str, object] = {
            "id": authority_attempt_id,
            "registration_id": provider.authority_registration_id,
            "task_id": assignment.assignment_id,
            "stage_id": assignment.work_item_id,
            "role": assignment.role.casefold(),
            "provider_instance_id": assignment.session_id,
            "workspace": canonical_workspace_path(
                Path(workspace.canonical_path),
            ),
            "project_id": assignment.project_id,
            "charter_id": assignment.charter_id,
            "charter_revision": assignment.charter_revision,
            "task_revision": assignment.revision,
        }
        mismatches = [
            name
            for name, value in expected.items()
            if _comparable(record.get(name)) != _comparable(value)
        ]
        if mismatches:
            raise PermissionError(
                "Authority attempt binding mismatch: "
                + ", ".join(sorted(mismatches))
            )
        expires_at = _parse_time(
            str(record.get("authorization_expires_at"))
        )
        if expires_at <= self._clock():
            raise PermissionError("Authority launch authorization expired")
        authorization_id = str(record.get("launch_authorization_id") or "")
        generation = record.get("authorization_generation")
        if not authorization_id or not isinstance(generation, int):
            raise PermissionError("Authority launch generation is invalid")
        launch_state = self._authority.query_state(
            "launch_authorizations", authorization_id
        )
        launch_record = _queried_record(
            launch_state, "Authority launch authorization"
        )
        if (
            launch_record.get("service_state") != "ACTIVE"
            or launch_record.get("project_id") != assignment.project_id
            or launch_record.get("charter_id") != assignment.charter_id
            or launch_record.get("charter_revision")
            != assignment.charter_revision
            or launch_record.get("authorization_generation") != generation
            or launch_record.get("id") != authorization_id
        ):
            raise PermissionError(
                "Authority launch authorization is inactive or mismatched"
            )
        launch_token = str(record.get("provider_run_id") or "")
        if not launch_token:
            raise PermissionError("Authority attempt has no launch identity")
        plan = {
            **expected,
            "provider_run_id": launch_token,
            "launch_authorization_id": authorization_id,
            "authorization_generation": generation,
            "authority_envelope_digest": assignment.authority_envelope_digest,
            "workflow_id": workflow.workflow_id,
            "workflow_record_digest": _digest(workflow.to_dict()),
            "work_item_id": work_item.work_item_id,
            "work_item_record_digest": _digest(work_item.to_dict()),
            "workspace_reservation_id": workspace.workspace_reservation_id,
        }
        return LaunchAuthorization(
            authority_attempt_id=authority_attempt_id,
            launch_token=launch_token,
            launch_plan_digest=_digest(plan),
            launch_authorization_id=authorization_id,
            authorization_generation=generation,
            stdout_path=str(record.get("stdout_path") or ""),
            stderr_path=str(record.get("stderr_path") or ""),
        )

    def launch(
        self,
        authorization: LaunchAuthorization,
        request: AdapterAssignment,
        adapter: ProviderAdapter,
    ) -> AdapterResult:
        del adapter
        result = self._authority.execute_provider(
            authorization.authority_attempt_id
        )
        completion = result.get("completion")
        process_result = result.get("process_result")
        if (
            not isinstance(completion, dict)
            or not isinstance(process_result, dict)
            or not self._authority.verify(
                "provider-completion", completion
            )
            or completion.get("attempt_id")
            != authorization.authority_attempt_id
            or completion.get("project_id") != request.project_id
            or completion.get("charter_id") != request.charter_id
            or completion.get("charter_revision")
            != request.charter_revision
            or completion.get("task_id") != request.assignment_id
            or completion.get("role") != request.role.casefold()
            or completion.get("provider_instance_id")
            != request.session_id
            or completion.get("normalized_result") != "completed"
        ):
            raise PermissionError(
                "Authority provider completion is invalid or failed"
            )
        stdout_path = Path(authorization.stdout_path).resolve()
        stderr_path = Path(authorization.stderr_path).resolve()
        if (
            Path(str(process_result.get("stdout_path"))).resolve()
            != stdout_path
            or Path(str(process_result.get("stderr_path"))).resolve()
            != stderr_path
            or not stdout_path.is_file()
            or not stderr_path.is_file()
            or stdout_path.stat().st_size > 10_000_000
            or completion.get("provider_evidence_digest")
            != _execution_evidence_digest(stdout_path, stderr_path)
        ):
            raise PermissionError(
                "Authority provider output identity is invalid"
            )
        try:
            output = json.loads(stdout_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as error:
            raise PermissionError(
                "Authority provider output is malformed"
            ) from error
        if not isinstance(output, dict):
            raise PermissionError(
                "Authority provider output must be structured data"
            )
        artifact: dict[str, Any] = {
            "kind": "structured-report",
            "path": None,
            "digest": hashlib.sha256(
                stdout_path.read_bytes()
            ).hexdigest(),
            "execution_requested": False,
        }
        if request.role == "REVIEWER":
            disposition = output.get("review_disposition")
            findings = output.get("findings")
            if (
                disposition not in {"ACCEPTED", "REPAIR_REQUIRED"}
                or not isinstance(findings, list)
                or any(not isinstance(item, dict) for item in findings)
            ):
                raise PermissionError(
                    "Authority review output is invalid"
                )
            artifact.update(
                {
                    "review_disposition": disposition,
                    "findings": findings,
                }
            )
        return AdapterResult(
            external_execution_id=authorization.authority_attempt_id,
            summary=f"Authority completed {request.role.casefold()} assignment.",
            artifacts=(artifact,),
            usage=None,
            session_resume_token=None,
        )

    def _active_charter(
        self, assignment: AssignmentRecord
    ) -> dict[str, Any]:
        status = self._project_status(assignment.project_id)
        project = status.get("project_summary")
        charter = status.get("active_charter")
        if not isinstance(project, dict) or not isinstance(charter, dict):
            raise PermissionError("project has no durable active charter")
        if (
            project.get("project_id") != assignment.project_id
            or project.get("active_charter_id") != assignment.charter_id
            or project.get("active_charter_revision")
            != assignment.charter_revision
            or charter.get("project_id") != assignment.project_id
            or charter.get("charter_id") != assignment.charter_id
            or charter.get("revision") != assignment.charter_revision
            or charter.get("status") != "ACTIVE"
            or not charter.get("founder_approval_record_id")
            or not charter.get("founder_authorization_capability_digest")
        ):
            raise PermissionError(
                "assignment is not bound to the active Founder-approved charter"
            )
        envelope = charter.get("authority_envelope")
        if (
            not isinstance(envelope, dict)
            or _digest(envelope) != assignment.authority_envelope_digest
        ):
            raise PermissionError("assignment authority envelope is stale")
        return charter

    @staticmethod
    def _validate_charter_scope(
        charter: dict[str, Any],
        assignment: AssignmentRecord,
        workspace: WorkspaceReservationRecord,
    ) -> None:
        providers = charter.get("approved_providers")
        if isinstance(providers, (list, tuple)) and providers and (
            assignment.provider_id not in providers
        ):
            raise PermissionError("provider is outside the active charter")
        workspaces = charter.get("workspaces")
        if isinstance(workspaces, (list, tuple)) and workspaces:
            candidate = canonical_workspace_path(
                Path(workspace.canonical_path),
            )
            if not any(
                _path_contains(
                    canonical_workspace_path(
                        Path(item)
                    ),
                    candidate,
                )
                for item in workspaces
                if isinstance(item, str) and item
            ):
                raise PermissionError("workspace is outside the active charter")


class TestLaunchAuthority:
    """Explicit deterministic unit-test authority; never used by production."""

    __test__ = False

    def __init__(self) -> None:
        self._authorizations: dict[str, tuple[dict[str, object], str]] = {}

    def reserve(
        self,
        workflow: WorkflowRecord,
        work_item: WorkItemRecord,
        assignment: AssignmentRecord,
        provider: ProviderRecord,
        workspace: WorkspaceReservationRecord,
        authority_attempt_id: str,
        *,
        launch_token: str | None = None,
    ) -> str:
        token = launch_token or f"launch:{authority_attempt_id}"
        expected = _test_expectation(workflow, work_item, assignment, provider, workspace)
        self._authorizations[authority_attempt_id] = (expected, token)
        return authority_attempt_id

    def authorize(
        self,
        workflow: WorkflowRecord,
        work_item: WorkItemRecord,
        assignment: AssignmentRecord,
        provider: ProviderRecord,
        workspace: WorkspaceReservationRecord,
        authority_attempt_id: str,
    ) -> LaunchAuthorization:
        registered = self._authorizations.get(authority_attempt_id)
        if registered is None:
            raise PermissionError("test Authority attempt was not reserved")
        expected, launch_token = registered
        actual = _test_expectation(workflow, work_item, assignment, provider, workspace)
        if actual != expected:
            raise PermissionError("test Authority attempt binding mismatch")
        plan = {
            **actual,
            "provider_run_id": launch_token,
            "launch_authorization_id": f"test-launch:{assignment.project_id}",
            "authorization_generation": assignment.charter_revision,
        }
        return LaunchAuthorization(
            authority_attempt_id=authority_attempt_id,
            launch_token=launch_token,
            launch_plan_digest=_digest(plan),
            launch_authorization_id=str(plan["launch_authorization_id"]),
            authorization_generation=assignment.charter_revision,
            stdout_path="",
            stderr_path="",
        )

    def launch(
        self,
        authorization: LaunchAuthorization,
        request: AdapterAssignment,
        adapter: ProviderAdapter,
    ) -> AdapterResult:
        del authorization
        return adapter.launch(request)


def _validate_durable_binding(
    workflow: WorkflowRecord,
    work_item: WorkItemRecord,
    assignment: AssignmentRecord,
) -> None:
    if (
        workflow.state != "ACTIVE"
        or work_item.workflow_id != workflow.workflow_id
        or assignment.workflow_id != workflow.workflow_id
        or assignment.work_item_id != work_item.work_item_id
        or workflow.project_id != assignment.project_id
        or work_item.project_id != assignment.project_id
        or workflow.charter_id != assignment.charter_id
        or work_item.charter_id != assignment.charter_id
        or workflow.charter_revision != assignment.charter_revision
        or work_item.charter_revision != assignment.charter_revision
        or workflow.authority_envelope_digest
        != assignment.authority_envelope_digest
    ):
        raise PermissionError(
            "launch is not bound to exact durable workflow and work item"
        )

def _status_dict(
    executive: KeeperExecutive, project_id: str
) -> dict[str, Any]:
    status = executive.status(project_id)
    return {
        "project_summary": dict(status.project_summary),
        "active_charter": (
            dict(status.active_charter)
            if status.active_charter is not None
            else None
        ),
    }


def _test_expectation(
    workflow: WorkflowRecord,
    work_item: WorkItemRecord,
    assignment: AssignmentRecord,
    provider: ProviderRecord,
    workspace: WorkspaceReservationRecord,
) -> dict[str, object]:
    return {
        "registration_id": provider.authority_registration_id,
        "project_id": assignment.project_id,
        "charter_id": assignment.charter_id,
        "charter_revision": assignment.charter_revision,
        "task_id": assignment.assignment_id,
        "task_revision": assignment.revision,
        "stage_id": assignment.work_item_id,
        "workflow_id": workflow.workflow_id,
        "workflow_record_digest": _digest(workflow.to_dict()),
        "work_item_id": work_item.work_item_id,
        "work_item_record_digest": _digest(work_item.to_dict()),
        "role": assignment.role,
        "provider_instance_id": assignment.session_id,
        "workspace": canonical_workspace_path(
            Path(workspace.canonical_path)
        ),
        "workspace_reservation_id": workspace.workspace_reservation_id,
        "authority_envelope_digest": assignment.authority_envelope_digest,
    }


def _queried_record(value: dict[str, Any], name: str) -> dict[str, Any]:
    record = value.get("record")
    if value.get("found") is not True or not isinstance(record, dict):
        raise PermissionError(f"{name} was not found")
    return dict(record)


def _parse_time(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        raise PermissionError("Authority timestamp is not timezone aware")
    return parsed


def _comparable(value: object) -> object:
    if isinstance(value, str):
        return value.replace("\\", "/").casefold()
    return value


def _path_contains(root: str, candidate: str) -> bool:
    normalized_root = root.rstrip("/")
    return (
        candidate == normalized_root
        or candidate.startswith(normalized_root + "/")
    )


def _digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(
            cast(Any, value),
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


def _execution_evidence_digest(
    stdout_path: Path, stderr_path: Path
) -> str:
    return hashlib.sha256(
        json.dumps(
            {
                "stdout_sha256": hashlib.sha256(
                    stdout_path.read_bytes()
                ).hexdigest(),
                "stderr_sha256": hashlib.sha256(
                    stderr_path.read_bytes()
                ).hexdigest(),
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
