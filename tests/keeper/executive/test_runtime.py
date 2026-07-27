from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from keeper.app.storage import KeeperStore
from keeper.executive.models import SpecialistProfile
from keeper.executive.repository import ExecutiveRepository
from keeper.executive.runtime import ExecutiveRuntime
from keeper.executive.specialists import (
    GlobalProjectBrief,
    SpecialistResult,
    TaskGuidance,
)
from keeper.executive.surfaces import StatusSurface
from tests.keeper.executive.test_intake_charters import approved_project


class RuntimeGateway:
    def __init__(self) -> None:
        self.calls: list[str] = []
        self.fail_once = True

    def execute(
        self,
        specialist: SpecialistProfile,
        brief: GlobalProjectBrief,
        guidance: TaskGuidance,
    ) -> SpecialistResult:
        self.calls.append(guidance.task_id)
        verification = (
            ("failed",)
            if "Implementation" in guidance.allowed_scope and self.fail_once
            else ("passed",)
        )
        if verification == ("failed",):
            self.fail_once = False
        return SpecialistResult(
            guidance.task_id,
            specialist.provider_id,
            specialist.model_id,
            specialist.session_id,
            "COMPLETED",
            guidance.required_outputs,
            (f"evidence:{len(self.calls)}",),
            {},
            (guidance.allowed_scope[0],),
            guidance.role,
            verification,
        )


def profiles() -> tuple[SpecialistProfile, ...]:
    capabilities = (
        "requirements", "architecture", "implementation", "testing",
        "security", "packaging", "acceptance",
    )
    return tuple(
        SpecialistProfile(
            "mock", f"model-{identity}-{capability}", f"session-{identity}-{capability}",
            (capability,), ("software", "general"), True, True, identity, 0,
            ("medium",), True, 1.0,
        )
        for capability in capabilities
        for identity in ("author", "reviewer")
    )


def test_unattended_progress_repairs_and_completes_without_duplicates(tmp_path: Path) -> None:
    service, project, _ = approved_project(tmp_path)
    gateway = RuntimeGateway()
    runtime = ExecutiveRuntime(service.repository, gateway, profiles())
    for _ in range(20):
        state = runtime.progress(project.project_id)
        if state.state == "COMPLETED":
            break
    assert state.state == "COMPLETED"
    tasks = service.repository.tasks(project.project_id)
    assert all(task.status == "COMPLETED" for task in tasks)
    implementation = next(task for task in tasks if task.title == "Implementation")
    assert implementation.retry_count == 1
    calls = list(gateway.calls)
    assert runtime.progress(project.project_id).state == "COMPLETED"
    assert gateway.calls == calls


def test_restart_resumes_durable_state(tmp_path: Path) -> None:
    service, project, _ = approved_project(tmp_path)
    gateway = RuntimeGateway()
    first = ExecutiveRuntime(service.repository, gateway, profiles())
    first.progress(project.project_id)
    first.progress(project.project_id)
    reopened_store = KeeperStore(service.repository.store.path)
    reopened_store.migrate()
    resumed = ExecutiveRuntime(ExecutiveRepository(reopened_store), gateway, profiles())
    prior_calls = len(gateway.calls)
    resumed.progress(project.project_id)
    assert len(gateway.calls) == prior_calls + 1
    completed = [
        task for task in resumed.repository.tasks(project.project_id)
        if task.status == "COMPLETED"
    ]
    assert len({task.task_id for task in completed}) == len(completed)


def test_revocation_prevents_new_task_launch_and_resume(tmp_path: Path) -> None:
    service, project, _ = approved_project(tmp_path)
    gateway = RuntimeGateway()
    runtime = ExecutiveRuntime(service.repository, gateway, profiles())
    runtime.progress(project.project_id)
    runtime.revoke_delegation(project.project_id)
    before = list(gateway.calls)
    assert runtime.progress(project.project_id).state == "PAUSED"
    assert gateway.calls == before
    with pytest.raises(PermissionError, match="revoked"):
        runtime.resume(project.project_id)


def test_missing_provider_and_credential_wait_safely(tmp_path: Path) -> None:
    service, project, _ = approved_project(tmp_path)
    runtime = ExecutiveRuntime(service.repository, RuntimeGateway(), ())
    runtime.progress(project.project_id)
    assert runtime.progress(project.project_id).state == "WAITING_FOR_PROVIDER"

    service2, project2, _ = approved_project(tmp_path / "credential")
    unavailable = replace(profiles()[0], credential_available=False)
    runtime2 = ExecutiveRuntime(service2.repository, RuntimeGateway(), (unavailable,))
    runtime2.progress(project2.project_id)
    assert runtime2.progress(project2.project_id).state == "WAITING_FOR_CREDENTIAL"


def test_status_surface_exposes_control_room_model(tmp_path: Path) -> None:
    service, project, _ = approved_project(tmp_path)
    runtime = ExecutiveRuntime(service.repository, RuntimeGateway(), profiles())
    runtime.progress(project.project_id)
    view = StatusSurface(service.repository).project(project.project_id)
    assert view.active_charter is not None
    assert view.delegation_mode == "FULL_DELEGATION"
    assert view.workflow is not None
    assert view.controls == ("pause", "resume", "cancel")
