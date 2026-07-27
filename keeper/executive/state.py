from __future__ import annotations

from dataclasses import replace

from keeper.executive.enums import ExecutiveState, TaskStatus
from keeper.executive.models import ExecutiveTask, ProjectRecord, utc_now


PROJECT_TRANSITIONS: dict[ExecutiveState, frozenset[ExecutiveState]] = {
    ExecutiveState.INTAKE: frozenset(
        {ExecutiveState.CLARIFICATION_REQUIRED, ExecutiveState.CHARTER_DRAFT, ExecutiveState.CANCELED}
    ),
    ExecutiveState.CLARIFICATION_REQUIRED: frozenset(
        {ExecutiveState.INTAKE, ExecutiveState.CHARTER_DRAFT, ExecutiveState.CANCELED}
    ),
    ExecutiveState.CHARTER_DRAFT: frozenset(
        {ExecutiveState.AWAITING_CHARTER_APPROVAL, ExecutiveState.INTAKE, ExecutiveState.CANCELED}
    ),
    ExecutiveState.AWAITING_CHARTER_APPROVAL: frozenset(
        {ExecutiveState.CHARTER_DRAFT, ExecutiveState.ACTIVE, ExecutiveState.CANCELED}
    ),
    ExecutiveState.ACTIVE: frozenset(
        {ExecutiveState.PLANNING, ExecutiveState.PAUSED, ExecutiveState.CANCELED}
    ),
    ExecutiveState.PLANNING: frozenset(
        {
            ExecutiveState.EXECUTING, ExecutiveState.BLOCKED, ExecutiveState.PAUSED,
            ExecutiveState.WAITING_FOR_PROVIDER, ExecutiveState.WAITING_FOR_CREDENTIAL,
            ExecutiveState.CANCELED, ExecutiveState.FAILED,
        }
    ),
    ExecutiveState.EXECUTING: frozenset(
        {
            ExecutiveState.REVIEWING, ExecutiveState.BLOCKED, ExecutiveState.PAUSED,
            ExecutiveState.WAITING_FOR_PROVIDER, ExecutiveState.WAITING_FOR_USAGE_RESET,
            ExecutiveState.WAITING_FOR_FOUNDER, ExecutiveState.WAITING_FOR_CREDENTIAL,
            ExecutiveState.WAITING_FOR_EXTERNAL_SYSTEM, ExecutiveState.COMPLETED,
            ExecutiveState.CANCELED, ExecutiveState.FAILED,
        }
    ),
    ExecutiveState.REVIEWING: frozenset(
        {
            ExecutiveState.EXECUTING, ExecutiveState.BLOCKED, ExecutiveState.PAUSED,
            ExecutiveState.WAITING_FOR_FOUNDER, ExecutiveState.COMPLETED,
            ExecutiveState.CANCELED, ExecutiveState.FAILED,
        }
    ),
    ExecutiveState.BLOCKED: frozenset(
        {ExecutiveState.PLANNING, ExecutiveState.EXECUTING, ExecutiveState.PAUSED, ExecutiveState.CANCELED}
    ),
    ExecutiveState.PAUSED: frozenset(
        {ExecutiveState.ACTIVE, ExecutiveState.PLANNING, ExecutiveState.EXECUTING, ExecutiveState.CANCELED}
    ),
    ExecutiveState.WAITING_FOR_PROVIDER: frozenset(
        {ExecutiveState.EXECUTING, ExecutiveState.PAUSED, ExecutiveState.CANCELED}
    ),
    ExecutiveState.WAITING_FOR_USAGE_RESET: frozenset(
        {ExecutiveState.EXECUTING, ExecutiveState.PAUSED, ExecutiveState.CANCELED}
    ),
    ExecutiveState.WAITING_FOR_FOUNDER: frozenset(
        {ExecutiveState.CHARTER_DRAFT, ExecutiveState.ACTIVE, ExecutiveState.EXECUTING, ExecutiveState.PAUSED, ExecutiveState.CANCELED}
    ),
    ExecutiveState.WAITING_FOR_CREDENTIAL: frozenset(
        {ExecutiveState.EXECUTING, ExecutiveState.PAUSED, ExecutiveState.CANCELED}
    ),
    ExecutiveState.WAITING_FOR_EXTERNAL_SYSTEM: frozenset(
        {ExecutiveState.EXECUTING, ExecutiveState.PAUSED, ExecutiveState.CANCELED}
    ),
    ExecutiveState.COMPLETED: frozenset(),
    ExecutiveState.CANCELED: frozenset(),
    ExecutiveState.FAILED: frozenset(),
}


TASK_TRANSITIONS: dict[TaskStatus, frozenset[TaskStatus]] = {
    TaskStatus.PROPOSED: frozenset({TaskStatus.READY, TaskStatus.BLOCKED, TaskStatus.CANCELED, TaskStatus.SKIPPED}),
    TaskStatus.READY: frozenset({TaskStatus.ASSIGNED, TaskStatus.BLOCKED, TaskStatus.CANCELED}),
    TaskStatus.ASSIGNED: frozenset({TaskStatus.RUNNING, TaskStatus.WAITING, TaskStatus.BLOCKED, TaskStatus.CANCELED}),
    TaskStatus.RUNNING: frozenset({TaskStatus.REVIEW_REQUIRED, TaskStatus.WAITING, TaskStatus.BLOCKED, TaskStatus.FAILED}),
    TaskStatus.WAITING: frozenset({TaskStatus.READY, TaskStatus.ASSIGNED, TaskStatus.RUNNING, TaskStatus.BLOCKED, TaskStatus.CANCELED}),
    TaskStatus.REVIEW_REQUIRED: frozenset({TaskStatus.COMPLETED, TaskStatus.REPAIR_REQUIRED, TaskStatus.BLOCKED, TaskStatus.FAILED}),
    TaskStatus.REPAIR_REQUIRED: frozenset({TaskStatus.ASSIGNED, TaskStatus.RUNNING, TaskStatus.BLOCKED, TaskStatus.FAILED}),
    TaskStatus.COMPLETED: frozenset(),
    TaskStatus.BLOCKED: frozenset({TaskStatus.READY, TaskStatus.CANCELED, TaskStatus.FAILED}),
    TaskStatus.FAILED: frozenset(),
    TaskStatus.CANCELED: frozenset(),
    TaskStatus.SKIPPED: frozenset(),
}


def transition_project(
    project: ProjectRecord, target: ExecutiveState, reason: str | None = None
) -> ProjectRecord:
    current = ExecutiveState(project.state)
    if target not in PROJECT_TRANSITIONS[current]:
        raise PermissionError(f"invalid executive transition: {current} -> {target}")
    return replace(
        project,
        state=target.value,
        pause_reason=reason if target in {
            ExecutiveState.BLOCKED,
            ExecutiveState.PAUSED,
            ExecutiveState.WAITING_FOR_PROVIDER,
            ExecutiveState.WAITING_FOR_USAGE_RESET,
            ExecutiveState.WAITING_FOR_FOUNDER,
            ExecutiveState.WAITING_FOR_CREDENTIAL,
            ExecutiveState.WAITING_FOR_EXTERNAL_SYSTEM,
        } else None,
        updated_at=utc_now(),
    )


def transition_task(task: ExecutiveTask, target: TaskStatus) -> ExecutiveTask:
    current = TaskStatus(task.status)
    if target not in TASK_TRANSITIONS[current]:
        raise PermissionError(f"invalid task transition: {current} -> {target}")
    return replace(task, status=target.value, updated_at=utc_now())
