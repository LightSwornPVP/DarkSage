from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path

import pytest

from keeper.executive.enums import TaskStatus
from keeper.executive.models import utc_now
from keeper.executive.runtime import ExecutiveRuntime
from keeper.executive.surfaces import StatusSurface
from tests.keeper.executive.authority_semantics import (
    SemanticAuthorityTransport,
    semantic_gateway,
)
from tests.keeper.executive.test_intake_charters import approved_project


def test_side_effect_then_exception_stays_uncertain_and_is_not_retried(
    tmp_path: Path,
) -> None:
    service, project, _ = approved_project(tmp_path)
    authority = SemanticAuthorityTransport()
    authority.raise_after_side_effect = True
    gateway, _ = semantic_gateway(tmp_path, transport=authority)
    runtime = ExecutiveRuntime(service.repository, gateway)
    runtime.progress(project.project_id)
    blocked = runtime.progress(project.project_id)
    task = service.repository.tasks(project.project_id)[0]
    attempt_id = task.authority_attempt_id
    assert blocked.state == "BLOCKED"
    assert task.status == "UNCERTAIN"
    assert attempt_id is not None
    assert authority.side_effect_count == 1

    reopened_gateway, _ = semantic_gateway(
        tmp_path, transport=authority
    )
    reopened = ExecutiveRuntime(service.repository, reopened_gateway)
    reopened.progress(project.project_id)
    after = service.repository.task(task.task_id)
    assert after.status == "UNCERTAIN"
    assert after.authority_attempt_id == attempt_id
    assert authority.side_effect_count == 1


def test_two_runtime_instances_create_one_claim_and_one_launch(
    tmp_path: Path,
) -> None:
    service, project, _ = approved_project(tmp_path)
    authority = SemanticAuthorityTransport()
    setup_gateway, _ = semantic_gateway(
        tmp_path, transport=authority
    )
    ExecutiveRuntime(service.repository, setup_gateway).progress(
        project.project_id
    )

    def progress() -> str:
        gateway, _ = semantic_gateway(tmp_path, transport=authority)
        runtime = ExecutiveRuntime(service.repository, gateway)
        return runtime.progress(project.project_id).state

    with ThreadPoolExecutor(max_workers=2) as pool:
        states = tuple(pool.map(lambda _: progress(), range(2)))
    first_task = service.repository.tasks(project.project_id)[0]
    assert states
    assert first_task.status == "COMPLETED"
    assert authority.side_effect_count == 1
    assert len(authority.execution_calls) == 1


def test_cancellation_wins_over_late_authenticated_completion(
    tmp_path: Path,
) -> None:
    service, project, _ = approved_project(tmp_path)
    authority = SemanticAuthorityTransport()
    authority.started = threading.Event()
    authority.release = threading.Event()
    authority.ignore_cancel_completion = True
    gateway, _ = semantic_gateway(tmp_path, transport=authority)
    runtime = ExecutiveRuntime(service.repository, gateway)
    runtime.progress(project.project_id)

    errors: list[BaseException] = []

    def worker() -> None:
        try:
            runtime.progress(project.project_id)
        except BaseException as error:
            errors.append(error)

    thread = threading.Thread(target=worker)
    thread.start()
    assert authority.started.wait(timeout=10)
    canceled = runtime.cancel(project.project_id)
    authority.release.set()
    thread.join(timeout=10)
    assert not thread.is_alive()
    assert errors == []
    assert canceled.state == "CANCELED"
    final_project = service.repository.project(project.project_id)
    first_task = service.repository.tasks(project.project_id)[0]
    assert final_project.state == "CANCELED"
    assert first_task.status == "CANCELED"
    assert first_task.late_result is True
    assert service.repository.store.list("executive_late_results")
    view = StatusSurface(service.repository).project(project.project_id)
    assert view.controls == ()
    assert any(
        item.get("history_kind") == "LATE_AUTHORITY_RESULT"
        for item in view.evidence_history
    )


def test_cancellation_before_launch_prevents_authority_execution(
    tmp_path: Path,
) -> None:
    service, project, _ = approved_project(tmp_path)
    gateway, authority = semantic_gateway(tmp_path)
    runtime = ExecutiveRuntime(service.repository, gateway)
    runtime.progress(project.project_id)
    runtime.cancel(project.project_id)
    assert runtime.progress(project.project_id).state == "CANCELED"
    assert authority.execution_calls == []


def test_stale_task_write_is_rejected(tmp_path: Path) -> None:
    service, project, _ = approved_project(tmp_path)
    gateway, _ = semantic_gateway(tmp_path)
    ExecutiveRuntime(service.repository, gateway).progress(project.project_id)
    task = service.repository.tasks(project.project_id)[0]
    ready = replace(
        task,
        status=TaskStatus.READY.value,
        revision=task.revision + 1,
        updated_at=utc_now(),
    )
    service.repository.save_task(ready, expected=task)
    with pytest.raises(PermissionError, match="stale"):
        service.repository.save_task(ready, expected=task)
