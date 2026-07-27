from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from keeper.executive.enums import TaskStatus
from keeper.executive.repository import ExecutiveRepository


@dataclass(frozen=True, slots=True)
class ProjectStatusView:
    conversation: tuple[dict[str, Any], ...]
    project_summary: dict[str, Any]
    active_charter: dict[str, Any] | None
    charter_history: tuple[dict[str, Any], ...]
    delegation_mode: str | None
    authority_limits: dict[str, Any]
    unresolved_questions: tuple[str, ...]
    workflow: dict[str, Any] | None
    stage_status: tuple[dict[str, Any], ...]
    task_status: tuple[dict[str, Any], ...]
    active_assignments: tuple[dict[str, Any], ...]
    decisions: tuple[dict[str, Any], ...]
    assumptions: tuple[dict[str, Any], ...]
    pending_approvals: tuple[dict[str, Any], ...]
    blockers: tuple[str, ...]
    evidence_history: tuple[dict[str, Any], ...]
    controls: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class StatusSurface:
    def __init__(self, repository: ExecutiveRepository) -> None:
        self.repository = repository

    def project(self, project_id: str) -> ProjectStatusView:
        project = self.repository.project(project_id)
        charters = self.repository.charters(project_id)
        active = next(
            (item for item in charters if item.charter_id == project.active_charter_id),
            None,
        )
        workflows = self.repository.workflows(project_id)
        workflow = max(workflows, key=lambda item: item.revision) if workflows else None
        tasks = self.repository.tasks(project_id)
        approvals = self.repository.approvals(project_id)
        blockers = tuple(
            item
            for item in (
                project.pause_reason,
                *(
                    task.result_disposition
                    for task in tasks
                    if task.status in {TaskStatus.BLOCKED, TaskStatus.FAILED}
                ),
            )
            if item
        )
        stage_rows = tuple(
            {
                "stage_id": stage.stage_id,
                "title": stage.title,
                "status": _stage_status(stage.stage_id, tasks),
            }
            for stage in (workflow.stages if workflow else ())
        )
        return ProjectStatusView(
            tuple(self.repository.conversations(project_id)),
            project.to_dict(),
            active.to_dict() if active else None,
            tuple(item.to_dict() for item in charters),
            active.delegation_mode if active else None,
            active.authority_envelope.to_dict() if active else {},
            active.unresolved_questions if active else (),
            workflow.to_dict() if workflow else None,
            stage_rows,
            tuple(item.to_dict() for item in tasks),
            tuple(
                {
                    "task_id": item.task_id,
                    "provider_id": item.provider_id,
                    "model_id": item.model_id,
                    "session_id": item.session_id,
                    "status": item.status,
                }
                for item in tasks
                if item.status in {
                    TaskStatus.ASSIGNED,
                    TaskStatus.RUNNING,
                    TaskStatus.REVIEW_REQUIRED,
                    TaskStatus.REPAIR_REQUIRED,
                }
            ),
            tuple(item.to_dict() for item in self.repository.decisions(project_id)),
            tuple(item.to_dict() for item in self.repository.assumptions(project_id)),
            tuple(
                item.to_dict()
                for item in approvals
                if item.revoked_at is None and item.consumed_at is None
            ),
            blockers,
            tuple(
                memory.to_dict()
                for memory in self.repository.memories(project_id)
                if memory.kind in {"EVIDENCE", "OUTCOME"}
            ),
            ("pause", "resume", "cancel"),
        )


def _stage_status(stage_id: str, tasks: list[Any]) -> str:
    statuses = [item.status for item in tasks if item.stage_id == stage_id]
    if not statuses:
        return "EMPTY"
    if all(item == TaskStatus.COMPLETED for item in statuses):
        return "COMPLETED"
    if any(item in {TaskStatus.RUNNING, TaskStatus.REVIEW_REQUIRED, TaskStatus.REPAIR_REQUIRED} for item in statuses):
        return "ACTIVE"
    if any(item in {TaskStatus.BLOCKED, TaskStatus.FAILED} for item in statuses):
        return "BLOCKED"
    return "PENDING"
