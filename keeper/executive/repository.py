from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import replace
from typing import Any

from keeper.app.storage import KeeperStore
from keeper.executive.models import (
    ApprovalRecord,
    AssumptionRecord,
    DecisionRecord,
    ExecutiveTask,
    MemoryRecord,
    ProjectCharter,
    ProjectRecord,
    WorkflowRecord,
)
from keeper.executive.enums import ExecutiveState
from keeper.executive.state import PROJECT_TRANSITIONS


class ExecutiveRepository:
    def __init__(self, store: KeeperStore) -> None:
        self.store = store

    def save_project(self, project: ProjectRecord) -> None:
        existing = self.store.get("executive_projects", project.project_id)
        target = ExecutiveState(project.state)
        if existing is None:
            if target not in {
                ExecutiveState.INTAKE,
                ExecutiveState.CLARIFICATION_REQUIRED,
            }:
                raise PermissionError(
                    "new projects must begin in intake or clarification"
                )
        else:
            current = ExecutiveState(ProjectRecord.from_dict(existing).state)
            if target != current and target not in PROJECT_TRANSITIONS[current]:
                raise PermissionError(
                    f"repository rejected executive transition: {current} -> {target}"
                )
        self.store.upsert("executive_projects", project.project_id, project.to_dict())

    def project(self, project_id: str) -> ProjectRecord:
        return ProjectRecord.from_dict(self._required("executive_projects", project_id))

    def save_charter(self, charter: ProjectCharter) -> None:
        existing = self.store.get("project_charters", charter.charter_id)
        if existing is not None:
            prior = ProjectCharter.from_dict(existing)
            if prior.status in {"APPROVED", "ACTIVE", "SUPERSEDED", "COMPLETED", "CANCELED"}:
                raise PermissionError("approved charter history is immutable")
        self.store.upsert("project_charters", charter.charter_id, charter.to_dict())
        self._relate(charter.project_id, "project", charter.project_id, "charter", charter.charter_id)

    def insert_approved_charter(self, charter: ProjectCharter) -> None:
        if charter.status not in {"APPROVED", "ACTIVE"}:
            raise ValueError("immutable insertion requires an approved charter")
        self.store.insert_immutable("project_charters", charter.charter_id, charter.to_dict())
        self._relate(charter.project_id, "project", charter.project_id, "charter", charter.charter_id)

    def charter(self, charter_id: str) -> ProjectCharter:
        return ProjectCharter.from_dict(self._required("project_charters", charter_id))

    def charters(self, project_id: str) -> list[ProjectCharter]:
        values = [
            ProjectCharter.from_dict(item)
            for item in self.store.list("project_charters")
            if item.get("project_id") == project_id
        ]
        return sorted(values, key=lambda item: item.revision)

    def save_workflow(self, workflow: WorkflowRecord) -> None:
        self.store.upsert("executive_workflows", workflow.workflow_id, workflow.to_dict())
        self._relate(workflow.project_id, "charter", workflow.charter_id, "workflow", workflow.workflow_id)

    def workflows(self, project_id: str) -> list[WorkflowRecord]:
        return [
            WorkflowRecord.from_dict(item)
            for item in self.store.list("executive_workflows")
            if item.get("project_id") == project_id
        ]

    def save_task(self, task: ExecutiveTask) -> None:
        self.store.upsert("executive_tasks", task.task_id, task.to_dict())
        self._relate(task.project_id, "workflow", task.workflow_id, "task", task.task_id)

    def task(self, task_id: str) -> ExecutiveTask:
        return ExecutiveTask.from_dict(self._required("executive_tasks", task_id))

    def tasks(self, project_id: str) -> list[ExecutiveTask]:
        return [
            ExecutiveTask.from_dict(item)
            for item in self.store.list("executive_tasks")
            if item.get("project_id") == project_id
        ]

    def insert_approval(self, approval: ApprovalRecord) -> None:
        self.store.insert_immutable("executive_approvals", approval.approval_id, approval.to_dict())
        self._relate(approval.project_id, "charter", approval.charter_id, "approval", approval.approval_id)

    def approvals(self, project_id: str, charter_revision: int | None = None) -> list[ApprovalRecord]:
        values = [
            ApprovalRecord.from_dict(item)
            for item in self.store.list("executive_approvals")
            if item.get("project_id") == project_id
        ]
        return [
            item for item in values
            if charter_revision is None or item.charter_revision == charter_revision
        ]

    def revoke_approval(self, approval_id: str, revoked_at: str) -> ApprovalRecord:
        approval = ApprovalRecord.from_dict(self._required("executive_approvals", approval_id))
        updated = replace(approval, revoked_at=revoked_at)
        self.store.upsert("executive_approvals", approval_id, updated.to_dict())
        return updated

    def insert_decision(self, record: DecisionRecord) -> None:
        self.store.insert_immutable("project_decisions", record.decision_id, record.to_dict())
        self._relate(record.project_id, "project", record.project_id, "decision", record.decision_id)

    def insert_assumption(self, record: AssumptionRecord) -> None:
        self.store.insert_immutable("project_assumptions", record.assumption_id, record.to_dict())
        self._relate(record.project_id, "project", record.project_id, "assumption", record.assumption_id)

    def insert_memory(self, record: MemoryRecord) -> None:
        self.store.insert_immutable("project_memories", record.memory_id, record.to_dict())
        self._relate(record.project_id, "project", record.project_id, "memory", record.memory_id)

    def memories(
        self,
        project_id: str,
        *,
        charter_revision: int | None = None,
        task_id: str | None = None,
        stage_id: str | None = None,
        category: str | None = None,
        authority_relevant: bool | None = None,
    ) -> list[MemoryRecord]:
        values = [
            MemoryRecord.from_dict(item)
            for item in self.store.list("project_memories")
            if item.get("project_id") == project_id
        ]
        return [
            item for item in values
            if (charter_revision is None or item.charter_revision == charter_revision)
            and (task_id is None or item.task_id == task_id)
            and (stage_id is None or item.stage_id == stage_id)
            and (category is None or item.category == category)
            and (authority_relevant is None or item.authority_relevant == authority_relevant)
        ]

    def decisions(self, project_id: str) -> list[DecisionRecord]:
        return [
            DecisionRecord.from_dict(item)
            for item in self.store.list("project_decisions")
            if item.get("project_id") == project_id
        ]

    def assumptions(self, project_id: str) -> list[AssumptionRecord]:
        return [
            AssumptionRecord.from_dict(item)
            for item in self.store.list("project_assumptions")
            if item.get("project_id") == project_id
        ]

    def save_conversation(self, interaction_id: str, payload: dict[str, Any]) -> None:
        required = {"interaction_id", "project_id", "speaker", "message", "created_at"}
        if set(payload) != required:
            raise ValueError("conversation record fields are invalid")
        self.store.insert_immutable("project_conversations", interaction_id, payload)

    def conversations(self, project_id: str) -> list[dict[str, Any]]:
        return [
            item
            for item in self.store.list("project_conversations")
            if item.get("project_id") == project_id
        ]

    def _required(self, table: str, identifier: str) -> dict[str, Any]:
        value = self.store.get(table, identifier)
        if value is None:
            raise KeyError(f"{table} record not found: {identifier}")
        return value

    def _relate(
        self,
        project_id: str,
        parent_kind: str,
        parent_id: str,
        child_kind: str,
        child_id: str,
    ) -> None:
        material = f"{parent_kind}:{parent_id}:{child_kind}:{child_id}"
        relationship_id = hashlib.sha256(material.encode("utf-8")).hexdigest()
        with self.store.connect() as connection:
            connection.execute(
                "INSERT OR IGNORE INTO executive_relationships VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    relationship_id,
                    project_id,
                    parent_kind,
                    parent_id,
                    child_kind,
                    child_id,
                    _now(),
                ),
            )


def canonical_digest(value: dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex}"


def _now() -> str:
    from keeper.executive.models import utc_now

    return utc_now()
