from __future__ import annotations

from pathlib import Path

import pytest

from keeper.app.storage import KeeperStore
from keeper.executive.authority_gateway import (
    AuthorityBackedSpecialistGateway,
)
from keeper.executive.repository import ExecutiveRepository
from keeper.executive.runtime import ExecutiveRuntime
from keeper.executive.surfaces import StatusSurface
from tests.keeper.executive.authority_semantics import (
    SemanticAuthorityTransport,
    semantic_gateway,
)
from tests.keeper.executive.test_intake_charters import approved_project


def test_unattended_authority_execution_and_review_complete_once(
    tmp_path: Path,
) -> None:
    service, project, _ = approved_project(tmp_path)
    gateway, authority = semantic_gateway(tmp_path)
    runtime = ExecutiveRuntime(service.repository, gateway)
    for _ in range(20):
        state = runtime.progress(project.project_id)
        if state.state == "COMPLETED":
            break
    assert state.state == "COMPLETED"
    tasks = service.repository.tasks(project.project_id)
    assert all(task.status == "COMPLETED" for task in tasks)
    assert all(task.authority_attempt_id for task in tasks)
    independent = [
        task
        for task in tasks
        if any(
            "independent" in item.casefold()
            for item in task.review_requirements
        )
    ]
    assert all(task.review_attempt_id for task in independent)
    assert len(authority.execution_calls) == len(tasks) + len(independent)
    calls = list(authority.execution_calls)
    assert runtime.progress(project.project_id).state == "COMPLETED"
    assert authority.execution_calls == calls


def test_restart_resumes_only_durable_authority_state(
    tmp_path: Path,
) -> None:
    service, project, _ = approved_project(tmp_path)
    authority = SemanticAuthorityTransport()
    gateway, _ = semantic_gateway(tmp_path, transport=authority)
    first = ExecutiveRuntime(service.repository, gateway)
    first.progress(project.project_id)
    first.progress(project.project_id)
    reopened_store = KeeperStore(service.repository.store.path)
    reopened_store.migrate()
    resumed_gateway, _ = semantic_gateway(
        tmp_path, transport=authority
    )
    resumed = ExecutiveRuntime(
        ExecutiveRepository(reopened_store), resumed_gateway
    )
    prior_calls = len(authority.execution_calls)
    resumed.progress(project.project_id)
    assert len(authority.execution_calls) > prior_calls
    assert len(authority.execution_calls) == len(
        set(authority.execution_calls)
    )


def test_revocation_prevents_new_authority_attempt(tmp_path: Path) -> None:
    service, project, _ = approved_project(tmp_path)
    gateway, authority = semantic_gateway(tmp_path)
    runtime = ExecutiveRuntime(service.repository, gateway)
    runtime.progress(project.project_id)
    runtime.revoke_delegation(project.project_id)
    before = list(authority.execution_calls)
    assert runtime.progress(project.project_id).state == "PAUSED"
    assert authority.execution_calls == before
    with pytest.raises(PermissionError, match="revoked"):
        runtime.resume(project.project_id)


def test_production_runtime_rejects_mock_or_missing_authority(
    tmp_path: Path,
) -> None:
    service, _, _ = approved_project(tmp_path)
    with pytest.raises(RuntimeError, match="Authority-backed"):
        ExecutiveRuntime(service.repository, object())  # type: ignore[arg-type]
    client_gateway, _ = semantic_gateway(tmp_path)
    assert type(client_gateway) is AuthorityBackedSpecialistGateway


def test_unqualified_authority_registration_waits_safely(
    tmp_path: Path,
) -> None:
    service, project, _ = approved_project(tmp_path)
    authority = SemanticAuthorityTransport()
    for registration in authority.registrations.values():
        registration["service_state"] = "REVOKED"
    gateway, _ = semantic_gateway(tmp_path, transport=authority)
    runtime = ExecutiveRuntime(service.repository, gateway)
    runtime.progress(project.project_id)
    assert (
        runtime.progress(project.project_id).state
        == "WAITING_FOR_PROVIDER"
    )
    assert authority.execution_calls == []


def test_status_surface_exposes_authority_attempts(tmp_path: Path) -> None:
    service, project, _ = approved_project(tmp_path)
    gateway, _ = semantic_gateway(tmp_path)
    runtime = ExecutiveRuntime(service.repository, gateway)
    runtime.progress(project.project_id)
    runtime.progress(project.project_id)
    view = StatusSurface(service.repository).project(project.project_id)
    assert view.active_charter is not None
    assert view.delegation_mode == "FULL_DELEGATION"
    assert view.workflow is not None
    assert any(
        task["authority_attempt_id"] for task in view.task_status
    )
