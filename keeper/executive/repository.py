from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from keeper.app.storage import SCHEMA_VERSION, KeeperStore
from keeper.executive.enums import (
    ActionCategory,
    ApprovalKind,
    CharterStatus,
    ExecutiveState,
    TaskStatus,
)
from keeper.executive.models import (
    ApprovalRecord,
    AssumptionRecord,
    DecisionRecord,
    ExecutiveTask,
    MemoryRecord,
    ProjectCharter,
    ProjectRecord,
    ProposedAction,
    WorkflowRecord,
    utc_now,
)
from keeper.executive.state import PROJECT_TRANSITIONS, TASK_TRANSITIONS


class ExecutiveRepository:
    def __init__(self, store: KeeperStore) -> None:
        self.store = store

    def save_project(
        self,
        project: ProjectRecord,
        *,
        expected: ProjectRecord | None = None,
    ) -> None:
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
            prior = ProjectRecord.from_dict(existing)
            if expected is None or prior != expected:
                raise PermissionError(
                    "project write is stale or lacks exact CAS"
                )
            current = ExecutiveState(prior.state)
            if (
                (target == ExecutiveState.ACTIVE and current != target)
                or project.name != prior.name
                or project.project_type != prior.project_type
                or project.created_at != prior.created_at
                or project.active_charter_id != prior.active_charter_id
                or project.active_charter_revision
                != prior.active_charter_revision
            ):
                raise PermissionError(
                    "project identity and charter binding are trusted-state only"
                )
            if target != current and target not in PROJECT_TRANSITIONS[current]:
                raise PermissionError(
                    f"repository rejected executive transition: {current} -> {target}"
                )
            self._cas_entity(
                "executive_projects",
                project.project_id,
                expected.to_dict(),
                project.to_dict(),
            )
            return
        self.store.insert_immutable(
            "executive_projects", project.project_id, project.to_dict()
        )

    def project(self, project_id: str) -> ProjectRecord:
        return ProjectRecord.from_dict(self._required("executive_projects", project_id))

    def save_charter(
        self,
        charter: ProjectCharter,
        *,
        expected: ProjectCharter | None = None,
    ) -> None:
        existing = self.store.get("project_charters", charter.charter_id)
        if existing is None:
            if charter.status != CharterStatus.DRAFT:
                raise PermissionError("new charters must begin as drafts")
            if self.store.get("executive_projects", charter.project_id) is None:
                raise PermissionError("charter project does not exist")
            self.store.insert_immutable(
                "project_charters", charter.charter_id, charter.to_dict()
            )
            self._relate(
                charter.project_id,
                "project",
                charter.project_id,
                "charter",
                charter.charter_id,
            )
            return
        prior = ProjectCharter.from_dict(existing)
        if expected is None or prior != expected:
            raise PermissionError("charter write is stale or lacks an exact CAS record")
        if (
            prior.project_id != charter.project_id
            or prior.charter_id != charter.charter_id
            or prior.revision != charter.revision
            or charter_approval_digest(prior) != charter_approval_digest(charter)
        ):
            raise PermissionError("charter identity and approved content are immutable")
        if (
            prior.status != CharterStatus.DRAFT
            or charter.status != CharterStatus.PROPOSED
        ):
            raise PermissionError(
                f"repository rejected charter transition: "
                f"{prior.status} -> {charter.status}"
            )
        self._cas_entity(
            "project_charters",
            charter.charter_id,
            expected.to_dict(),
            charter.to_dict(),
        )

    def insert_approved_charter(self, charter: ProjectCharter) -> None:
        del charter
        raise PermissionError(
            "approved charters may only be created by the trusted approval transaction"
        )

    def approve_charter(
        self,
        *,
        project_id: str,
        charter_id: str,
        charter_revision: int,
        approver: str,
        source_interaction_id: str,
    ) -> tuple[ProjectCharter, ApprovalRecord]:
        """Authenticate and approve the exact durable proposed charter atomically."""
        if approver != "Founder":
            raise PermissionError("the authenticated Founder identity is required")
        timestamp = utc_now()
        with self.store.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            charter_payload, charter_hash = self._entity_in_transaction(
                connection, "project_charters", charter_id
            )
            charter = ProjectCharter.from_dict(charter_payload)
            if (
                charter.project_id != project_id
                or charter.revision != charter_revision
                or charter.status != CharterStatus.PROPOSED
            ):
                raise PermissionError(
                    "approval does not identify the current proposed charter"
                )
            self._require_no_newer_charter(
                connection, project_id, charter_revision
            )
            interaction_payload, _ = self._entity_in_transaction(
                connection, "project_conversations", source_interaction_id
            )
            if (
                interaction_payload.get("project_id") != project_id
                or interaction_payload.get("speaker") != "Founder"
            ):
                raise PermissionError(
                    "approval source is not an authenticated Founder interaction"
                )
            approval_id = new_id("approval")
            charter_digest = charter_approval_digest(charter)
            interaction_digest = canonical_digest(interaction_payload)
            approval = ApprovalRecord(
                approval_id,
                project_id,
                charter_id,
                charter_revision,
                "CHARTER_DURATION",
                None,
                approver,
                charter.deliverables,
                {
                    "authentication_method": "trusted-founder-interaction",
                    "source_interaction_digest": interaction_digest,
                    "delegation_mode": charter.delegation_mode,
                    "maximum_cost": charter.budget_limit,
                },
                timestamp,
                charter.authority_envelope.expires_at,
                None,
                None,
                charter_digest,
                source_interaction_id,
            )
            approved = replace(
                charter,
                status=CharterStatus.APPROVED.value,
                founder_approval_identity=approver,
                founder_approval_record_id=approval_id,
                updated_at=timestamp,
            )
            self._insert_entity(
                connection,
                "executive_approvals",
                approval_id,
                approval.to_dict(),
            )
            self._insert_relation(
                connection,
                project_id,
                "charter",
                charter_id,
                "approval",
                approval_id,
            )
            self._update_entity_cas(
                connection,
                "project_charters",
                charter_id,
                charter_hash,
                approved.to_dict(),
            )
        return approved, approval

    def activate_charter(
        self,
        *,
        project_id: str,
        charter_id: str,
        charter_revision: int,
    ) -> tuple[ProjectRecord, ProjectCharter, ApprovalRecord]:
        """Reload and activate one exactly approved durable charter revision."""
        timestamp = utc_now()
        with self.store.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            project_payload, project_hash = self._entity_in_transaction(
                connection, "executive_projects", project_id
            )
            project = ProjectRecord.from_dict(project_payload)
            charter_payload, charter_hash = self._entity_in_transaction(
                connection, "project_charters", charter_id
            )
            charter = ProjectCharter.from_dict(charter_payload)
            if (
                charter.project_id != project_id
                or charter.revision != charter_revision
                or charter.status != CharterStatus.APPROVED
            ):
                raise PermissionError(
                    "activation does not identify the durable approved charter"
                )
            if charter.unresolved_questions:
                raise PermissionError(
                    "material unresolved questions block charter activation"
                )
            self._require_no_newer_charter(
                connection, project_id, charter_revision
            )
            approval_id = charter.founder_approval_record_id
            if approval_id is None:
                raise PermissionError("charter approval record is missing")
            approval_payload, _ = self._entity_in_transaction(
                connection, "executive_approvals", approval_id
            )
            approval = ApprovalRecord.from_dict(approval_payload)
            interaction_payload, _ = self._entity_in_transaction(
                connection,
                "project_conversations",
                approval.source_interaction_id,
            )
            self._validate_charter_approval(
                charter, approval, interaction_payload, timestamp
            )
            current_state = ExecutiveState(project.state)
            if ExecutiveState.ACTIVE not in PROJECT_TRANSITIONS[current_state]:
                raise PermissionError(
                    f"project state {current_state} cannot activate a charter"
                )
            active_charter = replace(
                charter,
                status=CharterStatus.ACTIVE.value,
                updated_at=timestamp,
            )
            active_project = replace(
                project,
                state=ExecutiveState.ACTIVE.value,
                active_charter_id=charter_id,
                active_charter_revision=charter_revision,
                pause_reason=None,
                updated_at=timestamp,
            )
            self._update_entity_cas(
                connection,
                "project_charters",
                charter_id,
                charter_hash,
                active_charter.to_dict(),
            )
            self._update_entity_cas(
                connection,
                "executive_projects",
                project_id,
                project_hash,
                active_project.to_dict(),
            )
        return active_project, active_charter, approval

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
        project = self.project(workflow.project_id)
        charter = self.charter(workflow.charter_id)
        if (
            charter.project_id != workflow.project_id
            or charter.revision != workflow.charter_revision
            or project.active_charter_id != workflow.charter_id
            or project.active_charter_revision != workflow.charter_revision
        ):
            raise PermissionError("workflow parent-child ownership is invalid")
        self.store.insert_immutable(
            "executive_workflows", workflow.workflow_id, workflow.to_dict()
        )
        self._relate(workflow.project_id, "charter", workflow.charter_id, "workflow", workflow.workflow_id)

    def workflows(self, project_id: str) -> list[WorkflowRecord]:
        return [
            WorkflowRecord.from_dict(item)
            for item in self.store.list("executive_workflows")
            if item.get("project_id") == project_id
        ]

    def save_task(
        self,
        task: ExecutiveTask,
        *,
        expected: ExecutiveTask | None = None,
    ) -> None:
        existing = self.store.get("executive_tasks", task.task_id)
        if existing is None:
            if task.status != TaskStatus.PROPOSED or task.revision != 1:
                raise PermissionError(
                    "new tasks must begin proposed at revision one"
                )
            self._validate_task_parentage(task)
            self.store.insert_immutable(
                "executive_tasks", task.task_id, task.to_dict()
            )
            self._relate(
                task.project_id,
                "workflow",
                task.workflow_id,
                "task",
                task.task_id,
            )
            return
        prior = ExecutiveTask.from_dict(existing)
        if expected is None or prior != expected:
            raise PermissionError("task write is stale or lacks exact CAS")
        current = TaskStatus(prior.status)
        target = TaskStatus(task.status)
        if (
            task.revision != prior.revision + 1
            or target not in TASK_TRANSITIONS[current]
            or task.project_id != prior.project_id
            or task.charter_id != prior.charter_id
            or task.charter_revision != prior.charter_revision
            or task.workflow_id != prior.workflow_id
            or task_definition_digest(task)
            != task_definition_digest(prior)
        ):
            raise PermissionError(
                f"repository rejected task transition: {current} -> {target}"
            )
        self._cas_entity(
            "executive_tasks",
            task.task_id,
            expected.to_dict(),
            task.to_dict(),
        )

    def claim_execution(
        self,
        task_id: str,
        *,
        expected_revision: int,
        plan: dict[str, Any],
        action: ProposedAction,
        approval_id: str | None,
    ) -> ExecutiveTask:
        """Give one worker a durable attempt binding before Authority launch."""
        attempt_id = str(plan["authority_attempt_id"])
        timestamp = utc_now()
        with self.store.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            task_payload, task_hash = self._entity_in_transaction(
                connection, "executive_tasks", task_id
            )
            task = ExecutiveTask.from_dict(task_payload)
            if (
                task.revision != expected_revision
                or task.status
                not in {TaskStatus.READY, TaskStatus.REPAIR_REQUIRED}
                or task.authority_attempt_id is not None
                or plan.get("project_id") != task.project_id
                or plan.get("charter_id") != task.charter_id
                or plan.get("charter_revision") != task.charter_revision
                or plan.get("workflow_id") != task.workflow_id
                or plan.get("task_id") != task.task_id
                or plan.get("task_revision") != task.revision
            ):
                raise PermissionError("task execution claim is stale or misbound")
            project_payload, _ = self._entity_in_transaction(
                connection, "executive_projects", task.project_id
            )
            project = ProjectRecord.from_dict(project_payload)
            charter_payload, _ = self._entity_in_transaction(
                connection, "project_charters", task.charter_id
            )
            charter = ProjectCharter.from_dict(charter_payload)
            if (
                project.state != ExecutiveState.EXECUTING
                or project.active_charter_id != task.charter_id
                or project.active_charter_revision != task.charter_revision
                or charter.status != CharterStatus.ACTIVE
            ):
                raise PermissionError("project is not launchable")
            if (
                action.project_id != task.project_id
                or action.charter_revision != task.charter_revision
                or action.trusted_source != "DURABLE_WORKFLOW_TASK"
            ):
                raise PermissionError(
                    "execution claim action facts are misbound"
                )
            budget_reservation_id: str | None = None
            if approval_id is not None:
                _, budget_reservation_id = (
                    self._consume_action_authority_in_transaction(
                        connection,
                        action,
                        approval_id,
                        task.task_id,
                        timestamp,
                    )
                )
            elif (
                action.spending
                or action.cost is None
                or (action.cost or 0) > 0
            ):
                raise PermissionError(
                    "spending claim lacks a bound action approval"
                )
            claimed = replace(
                task,
                provider_id=str(plan["provider_id"]),
                model_id=str(plan["model_id"]),
                session_id=str(plan["session_id"]),
                status=TaskStatus.LAUNCH_CLAIMED.value,
                authority_attempt_id=attempt_id,
                revision=task.revision + 1,
                attempt_history=task.attempt_history
                + (
                    {
                        "authority_attempt_id": attempt_id,
                        "state": "LAUNCH_CLAIMED",
                        "recorded_at": timestamp,
                    },
                ),
                updated_at=timestamp,
            )
            attempt_record = {
                **plan,
                "state": "LAUNCH_CLAIMED",
                "created_at": timestamp,
                "updated_at": timestamp,
                "completion_digest": None,
                "artifact_digest": None,
                "action_id": action.action_id,
                "approval_id": approval_id,
                "budget_reservation_id": budget_reservation_id,
            }
            self._insert_entity(
                connection,
                "executive_execution_attempts",
                attempt_id,
                attempt_record,
            )
            self._insert_relation(
                connection,
                task.project_id,
                "task",
                task.task_id,
                "authority_attempt",
                attempt_id,
            )
            self._update_entity_cas(
                connection,
                "executive_tasks",
                task.task_id,
                task_hash,
                claimed.to_dict(),
            )
        return claimed

    def transition_execution(
        self,
        task_id: str,
        *,
        expected_revision: int,
        expected_status: TaskStatus,
        target_status: TaskStatus,
        attempt_state: str,
    ) -> ExecutiveTask:
        timestamp = utc_now()
        with self.store.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            task_payload, task_hash = self._entity_in_transaction(
                connection, "executive_tasks", task_id
            )
            task = ExecutiveTask.from_dict(task_payload)
            if (
                task.revision != expected_revision
                or task.status != expected_status
                or target_status not in TASK_TRANSITIONS[expected_status]
                or task.authority_attempt_id is None
            ):
                raise PermissionError("execution transition is stale")
            attempt_payload, attempt_hash = self._entity_in_transaction(
                connection,
                "executive_execution_attempts",
                task.authority_attempt_id,
            )
            updated_task = replace(
                task,
                status=target_status.value,
                revision=task.revision + 1,
                updated_at=timestamp,
            )
            updated_attempt = {
                **attempt_payload,
                "state": attempt_state,
                "updated_at": timestamp,
            }
            self._update_entity_cas(
                connection,
                "executive_tasks",
                task.task_id,
                task_hash,
                updated_task.to_dict(),
            )
            self._update_entity_cas(
                connection,
                "executive_execution_attempts",
                task.authority_attempt_id,
                attempt_hash,
                updated_attempt,
            )
        return updated_task

    def accept_author_completion(
        self,
        task_id: str,
        *,
        expected_revision: int,
        result: dict[str, Any],
    ) -> ExecutiveTask:
        """Import one authenticated Authority completion without reviving cancel."""
        timestamp = utc_now()
        with self.store.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            task_payload, task_hash = self._entity_in_transaction(
                connection, "executive_tasks", task_id
            )
            task = ExecutiveTask.from_dict(task_payload)
            project_payload, _ = self._entity_in_transaction(
                connection, "executive_projects", task.project_id
            )
            project = ProjectRecord.from_dict(project_payload)
            attempt_id = str(result.get("authority_attempt_id", ""))
            if (
                task.authority_attempt_id != attempt_id
                or result.get("task_id") != task.task_id
                or result.get("authenticated") is not True
            ):
                raise PermissionError("completion does not bind to the task attempt")
            attempt_payload, attempt_hash = self._entity_in_transaction(
                connection, "executive_execution_attempts", attempt_id
            )
            late = (
                project.state == ExecutiveState.CANCELED
                or task.status == TaskStatus.CANCELED
            )
            if late:
                late_id = f"late-result:{attempt_id}"
                late_payload = {
                    **result,
                    "project_id": task.project_id,
                    "original_task_id": task.task_id,
                    "recorded_at": timestamp,
                    "task_state": task.status,
                    "project_state": project.state,
                }
                try:
                    self._insert_entity(
                        connection,
                        "executive_late_results",
                        late_id,
                        late_payload,
                    )
                except PermissionError:
                    pass
                recorded = replace(
                    task,
                    late_result=True,
                    revision=task.revision + 1,
                    updated_at=timestamp,
                )
                self._update_entity_cas(
                    connection,
                    "executive_tasks",
                    task.task_id,
                    task_hash,
                    recorded.to_dict(),
                )
                return recorded
            if (
                task.revision != expected_revision
                or task.status
                not in {
                    TaskStatus.EXECUTION_STARTED,
                    TaskStatus.RUNNING,
                    TaskStatus.COMPLETION_PENDING,
                    TaskStatus.UNCERTAIN,
                }
            ):
                raise PermissionError("completion import is stale")
            artifact_digest = str(result["artifact_digest"])
            completed_attempt = {
                **attempt_payload,
                "state": "COMPLETED",
                "completion_digest": result["completion_digest"],
                "artifact_digest": artifact_digest,
                "updated_at": timestamp,
            }
            imported = replace(
                task,
                status=TaskStatus.REVIEW_REQUIRED.value,
                artifact_digest=artifact_digest,
                revision=task.revision + 1,
                result_disposition="AUTHORITY_COMPLETED",
                attempt_history=task.attempt_history
                + (
                    {
                        "authority_attempt_id": attempt_id,
                        "state": "COMPLETED",
                        "artifact_digest": artifact_digest,
                        "completion_digest": result["completion_digest"],
                        "recorded_at": timestamp,
                    },
                ),
                updated_at=timestamp,
            )
            self._update_entity_cas(
                connection,
                "executive_execution_attempts",
                attempt_id,
                attempt_hash,
                completed_attempt,
            )
            self._update_entity_cas(
                connection,
                "executive_tasks",
                task.task_id,
                task_hash,
                imported.to_dict(),
            )
        return imported

    def mark_execution_uncertain(
        self,
        task_id: str,
        *,
        expected_revision: int,
        reason: str,
    ) -> ExecutiveTask:
        task = self.task(task_id)
        if task.revision != expected_revision:
            raise PermissionError("uncertain execution write is stale")
        if TaskStatus.UNCERTAIN not in TASK_TRANSITIONS[TaskStatus(task.status)]:
            raise PermissionError("task cannot become uncertain")
        uncertain = replace(
            task,
            status=TaskStatus.UNCERTAIN.value,
            result_disposition=reason,
            revision=task.revision + 1,
            updated_at=utc_now(),
        )
        self.save_task(uncertain, expected=task)
        return uncertain

    def execution_attempt(self, attempt_id: str) -> dict[str, Any]:
        return self._required("executive_execution_attempts", attempt_id)

    def claim_review(
        self,
        task_id: str,
        *,
        expected_revision: int,
        plan: dict[str, Any],
    ) -> ExecutiveTask:
        timestamp = utc_now()
        review_attempt_id = str(plan["authority_attempt_id"])
        with self.store.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            task_payload, task_hash = self._entity_in_transaction(
                connection, "executive_tasks", task_id
            )
            task = ExecutiveTask.from_dict(task_payload)
            if (
                task.revision != expected_revision
                or task.status != TaskStatus.REVIEW_REQUIRED
                or task.artifact_digest is None
                or task.review_attempt_id is not None
                or plan.get("artifact_revision_digest")
                != task.artifact_digest
                or plan.get("project_id") != task.project_id
                or plan.get("charter_id") != task.charter_id
                or plan.get("charter_revision") != task.charter_revision
                or plan.get("workflow_id") != task.workflow_id
                or plan.get("session_id") == task.session_id
                or review_attempt_id == task.authority_attempt_id
            ):
                raise PermissionError("review claim is stale or not independent")
            review_record = {
                "review_attempt_id": review_attempt_id,
                "review_task_id": plan["task_id"],
                "project_id": task.project_id,
                "charter_id": task.charter_id,
                "charter_revision": task.charter_revision,
                "workflow_id": task.workflow_id,
                "task_id": task.task_id,
                "task_revision": task.revision,
                "artifact_revision_digest": task.artifact_digest,
                "author_attempt_id": task.authority_attempt_id,
                "author_provider_id": task.provider_id,
                "author_session_id": task.session_id,
                "reviewer_provider_id": plan["provider_id"],
                "reviewer_model_id": plan["model_id"],
                "reviewer_session_id": plan["session_id"],
                "reviewer_registration_id": plan["registration_id"],
                "reviewer_qualification_id": plan["qualification_id"],
                "state": "LAUNCH_CLAIMED",
                "findings_digest": None,
                "disposition": None,
                "created_at": timestamp,
                "updated_at": timestamp,
                "plan": plan,
            }
            claimed = replace(
                task,
                review_attempt_id=review_attempt_id,
                revision=task.revision + 1,
                updated_at=timestamp,
            )
            self._insert_entity(
                connection,
                "executive_reviews",
                review_attempt_id,
                review_record,
            )
            self._insert_relation(
                connection,
                task.project_id,
                "task",
                task.task_id,
                "review_attempt",
                review_attempt_id,
            )
            self._update_entity_cas(
                connection,
                "executive_tasks",
                task.task_id,
                task_hash,
                claimed.to_dict(),
            )
        return claimed

    def transition_review(
        self,
        review_attempt_id: str,
        *,
        expected_state: str,
        target_state: str,
    ) -> None:
        with self.store.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            payload, payload_hash = self._entity_in_transaction(
                connection, "executive_reviews", review_attempt_id
            )
            if payload.get("state") != expected_state:
                raise PermissionError("review transition is stale")
            self._update_entity_cas(
                connection,
                "executive_reviews",
                review_attempt_id,
                payload_hash,
                {
                    **payload,
                    "state": target_state,
                    "updated_at": utc_now(),
                },
            )

    def accept_review_completion(
        self,
        task_id: str,
        *,
        expected_revision: int,
        result: dict[str, Any],
    ) -> ExecutiveTask:
        timestamp = utc_now()
        with self.store.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            task_payload, task_hash = self._entity_in_transaction(
                connection, "executive_tasks", task_id
            )
            task = ExecutiveTask.from_dict(task_payload)
            project_payload, _ = self._entity_in_transaction(
                connection, "executive_projects", task.project_id
            )
            project = ProjectRecord.from_dict(project_payload)
            if (
                (
                    project.state == ExecutiveState.CANCELED
                    or task.status == TaskStatus.CANCELED
                )
                and task.review_attempt_id is not None
                and result.get("authority_attempt_id")
                == task.review_attempt_id
                and result.get("authenticated") is True
            ):
                late_id = f"late-review:{task.review_attempt_id}"
                try:
                    self._insert_entity(
                        connection,
                        "executive_late_results",
                        late_id,
                        {
                            **result,
                            "project_id": task.project_id,
                            "original_task_id": task.task_id,
                            "history_kind": "LATE_REVIEW_RESULT",
                            "recorded_at": timestamp,
                        },
                    )
                except PermissionError:
                    pass
                recorded = replace(
                    task,
                    late_result=True,
                    revision=task.revision + 1,
                    updated_at=timestamp,
                )
                self._update_entity_cas(
                    connection,
                    "executive_tasks",
                    task.task_id,
                    task_hash,
                    recorded.to_dict(),
                )
                return recorded
            if (
                task.revision != expected_revision
                or task.status != TaskStatus.REVIEW_REQUIRED
                or task.review_attempt_id is None
                or result.get("authority_attempt_id")
                != task.review_attempt_id
                or result.get("authenticated") is not True
            ):
                raise PermissionError("review completion import is stale")
            review_payload, review_hash = self._entity_in_transaction(
                connection,
                "executive_reviews",
                task.review_attempt_id,
            )
            if (
                review_payload.get("state")
                not in {"EXECUTION_STARTED", "COMPLETION_PENDING", "UNCERTAIN"}
                or result.get("task_id")
                != review_payload.get("review_task_id")
                or result.get("session_id")
                != review_payload.get("reviewer_session_id")
                or result.get("registration_id")
                != review_payload.get("reviewer_registration_id")
                or review_payload.get("reviewer_session_id")
                == review_payload.get("author_session_id")
                or review_payload.get("review_attempt_id")
                == review_payload.get("author_attempt_id")
                or review_payload.get("artifact_revision_digest")
                != task.artifact_digest
            ):
                raise PermissionError(
                    "review completion independence or artifact binding is invalid"
                )
            accepted = result.get("normalized_result") == "completed"
            review_updated = {
                **review_payload,
                "state": "COMPLETED",
                "findings_digest": result["artifact_digest"],
                "completion_digest": result["completion_digest"],
                "disposition": "ACCEPTED" if accepted else "REPAIR_REQUIRED",
                "updated_at": timestamp,
            }
            if accepted:
                disposition = replace(
                    task,
                    status=TaskStatus.COMPLETED.value,
                    result_disposition="INDEPENDENT_REVIEW_ACCEPTED",
                    revision=task.revision + 1,
                    updated_at=timestamp,
                )
            elif task.retry_count >= task.max_retries:
                disposition = replace(
                    task,
                    status=TaskStatus.FAILED.value,
                    result_disposition="RETRY_LIMIT_EXCEEDED",
                    revision=task.revision + 1,
                    updated_at=timestamp,
                )
            else:
                disposition = replace(
                    task,
                    status=TaskStatus.REPAIR_REQUIRED.value,
                    provider_id=None,
                    model_id=None,
                    session_id=None,
                    authority_attempt_id=None,
                    artifact_digest=None,
                    review_attempt_id=None,
                    retry_count=task.retry_count + 1,
                    result_disposition="INDEPENDENT_REVIEW_REPAIR_REQUIRED",
                    revision=task.revision + 1,
                    updated_at=timestamp,
                )
            self._update_entity_cas(
                connection,
                "executive_reviews",
                task.review_attempt_id,
                review_hash,
                review_updated,
            )
            self._update_entity_cas(
                connection,
                "executive_tasks",
                task.task_id,
                task_hash,
                disposition.to_dict(),
            )
        return disposition

    def complete_automated_review(
        self,
        task_id: str,
        *,
        expected_revision: int,
    ) -> ExecutiveTask:
        task = self.task(task_id)
        if (
            task.revision != expected_revision
            or task.status != TaskStatus.REVIEW_REQUIRED
            or task.artifact_digest is None
            or any(
                "independent" in item.casefold()
                for item in task.review_requirements
            )
        ):
            raise PermissionError("local review cannot complete this task")
        completed = replace(
            task,
            status=TaskStatus.COMPLETED.value,
            result_disposition="AUTHORITY_EVIDENCE_ACCEPTED",
            revision=task.revision + 1,
            updated_at=utc_now(),
        )
        self.save_task(completed, expected=task)
        return completed

    def review(self, review_attempt_id: str) -> dict[str, Any]:
        return self._required("executive_reviews", review_attempt_id)

    def reviews(self, project_id: str) -> list[dict[str, Any]]:
        return [
            item
            for item in self.store.list("executive_reviews")
            if item.get("project_id") == project_id
        ]

    def late_results(self, project_id: str) -> list[dict[str, Any]]:
        return [
            item
            for item in self.store.list("executive_late_results")
            if item.get("project_id") == project_id
        ]

    def cancel_project_execution(
        self, project_id: str
    ) -> tuple[ProjectRecord, tuple[str, ...]]:
        timestamp = utc_now()
        attempt_ids: list[str] = []
        with self.store.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            project_payload, project_hash = self._entity_in_transaction(
                connection, "executive_projects", project_id
            )
            project = ProjectRecord.from_dict(project_payload)
            if ExecutiveState.CANCELED not in PROJECT_TRANSITIONS[
                ExecutiveState(project.state)
            ]:
                raise PermissionError("project cannot be canceled")
            canceled_project = replace(
                project,
                state=ExecutiveState.CANCELED.value,
                pause_reason=None,
                updated_at=timestamp,
            )
            self._update_entity_cas(
                connection,
                "executive_projects",
                project_id,
                project_hash,
                canceled_project.to_dict(),
            )
            rows = connection.execute(
                'SELECT id, payload, payload_hash FROM "executive_tasks"'
            ).fetchall()
            for row in rows:
                serialized = str(row["payload"])
                if _digest_serialized(serialized) != row["payload_hash"]:
                    raise RuntimeError(
                        "stored executive task failed integrity validation"
                    )
                payload = json.loads(serialized)
                if not isinstance(payload, dict) or payload.get(
                    "project_id"
                ) != project_id:
                    continue
                task = ExecutiveTask.from_dict(payload)
                if task.status in {
                    TaskStatus.COMPLETED,
                    TaskStatus.FAILED,
                    TaskStatus.CANCELED,
                    TaskStatus.SKIPPED,
                }:
                    continue
                canceled_task = replace(
                    task,
                    status=TaskStatus.CANCELED.value,
                    revision=task.revision + 1,
                    updated_at=timestamp,
                )
                self._update_entity_cas(
                    connection,
                    "executive_tasks",
                    task.task_id,
                    str(row["payload_hash"]),
                    canceled_task.to_dict(),
                )
                if task.authority_attempt_id:
                    attempt_ids.append(task.authority_attempt_id)
                if task.review_attempt_id:
                    attempt_ids.append(task.review_attempt_id)
        return canceled_project, tuple(attempt_ids)

    def task(self, task_id: str) -> ExecutiveTask:
        return ExecutiveTask.from_dict(self._required("executive_tasks", task_id))

    def tasks(self, project_id: str) -> list[ExecutiveTask]:
        return [
            ExecutiveTask.from_dict(item)
            for item in self.store.list("executive_tasks")
            if item.get("project_id") == project_id
        ]

    def insert_approval(self, approval: ApprovalRecord) -> None:
        del approval
        raise PermissionError(
            "approvals may only be created by trusted approval operations"
        )

    def grant_action_approval(
        self,
        *,
        project_id: str,
        charter_id: str,
        charter_revision: int,
        kind: ApprovalKind,
        action_category: ActionCategory,
        scope: tuple[str, ...],
        limits: dict[str, Any],
        approver: str,
        source_interaction_id: str,
        expires_at: str | None = None,
    ) -> ApprovalRecord:
        """Create a Founder-authenticated action approval from durable state."""
        if approver != "Founder" or kind is ApprovalKind.CHARTER_DURATION:
            raise PermissionError("a valid Founder action approval is required")
        timestamp = utc_now()
        with self.store.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            charter_payload, _ = self._entity_in_transaction(
                connection, "project_charters", charter_id
            )
            charter = ProjectCharter.from_dict(charter_payload)
            if (
                charter.project_id != project_id
                or charter.revision != charter_revision
                or charter.status != CharterStatus.ACTIVE
                or not set(scope).issubset(set(charter.deliverables))
            ):
                raise PermissionError(
                    "action approval is outside the active charter"
                )
            interaction, _ = self._entity_in_transaction(
                connection,
                "project_conversations",
                source_interaction_id,
            )
            if (
                interaction.get("project_id") != project_id
                or interaction.get("speaker") != "Founder"
            ):
                raise PermissionError(
                    "action approval source is not a Founder interaction"
                )
            if expires_at is not None:
                expiration = datetime.fromisoformat(expires_at)
                if expiration.tzinfo is None or expiration <= datetime.now(UTC):
                    raise PermissionError("action approval expiration is invalid")
            normalized_limits = dict(limits)
            normalized_limits.update(
                {
                    "authentication_method": "trusted-founder-interaction",
                    "source_interaction_digest": canonical_digest(interaction),
                }
            )
            binding = {
                "project_id": project_id,
                "charter_id": charter_id,
                "charter_revision": charter_revision,
                "kind": kind.value,
                "action_category": action_category.value,
                "scope": scope,
                "limits": normalized_limits,
                "source_interaction_id": source_interaction_id,
            }
            approval = ApprovalRecord(
                new_id("approval"),
                project_id,
                charter_id,
                charter_revision,
                kind.value,
                action_category.value,
                approver,
                scope,
                normalized_limits,
                timestamp,
                expires_at,
                None,
                None,
                canonical_digest(binding),
                source_interaction_id,
            )
            self._insert_entity(
                connection,
                "executive_approvals",
                approval.approval_id,
                approval.to_dict(),
            )
            self._insert_relation(
                connection,
                project_id,
                "charter",
                charter_id,
                "approval",
                approval.approval_id,
            )
        return approval

    def reserve_action_authority(
        self,
        action: ProposedAction,
        *,
        approval_id: str,
        task_id: str | None = None,
    ) -> tuple[ApprovalRecord, str | None]:
        """Atomically consume one-time authority and reserve cumulative spend."""
        if action.trusted_source != "DURABLE_WORKFLOW_TASK":
            raise PermissionError("caller-classified action facts are not consumable")
        timestamp = utc_now()
        with self.store.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            consumed, reservation_id = self._consume_action_authority_in_transaction(
                connection,
                action,
                approval_id,
                task_id,
                timestamp,
            )
        return consumed, reservation_id

    def mark_budget_boundary(self, reservation_id: str) -> None:
        with self.store.connect() as connection:
            cursor = connection.execute(
                "UPDATE executive_budget_reservations SET state='CROSSED' "
                "WHERE reservation_id=? AND state='RESERVED'",
                (reservation_id,),
            )
            if cursor.rowcount != 1:
                raise PermissionError("budget reservation is not crossable")

    def release_budget_reservation(self, reservation_id: str) -> None:
        with self.store.connect() as connection:
            cursor = connection.execute(
                "UPDATE executive_budget_reservations SET state='RELEASED' "
                "WHERE reservation_id=? AND state='RESERVED'",
                (reservation_id,),
            )
            if cursor.rowcount != 1:
                raise PermissionError(
                    "crossed or missing budget reservation cannot be released"
                )

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
        if approval.revoked_at is not None:
            raise PermissionError("approval is already revoked")
        updated = replace(approval, revoked_at=revoked_at)
        self._cas_entity(
            "executive_approvals",
            approval_id,
            approval.to_dict(),
            updated.to_dict(),
        )
        return updated

    def insert_decision(self, record: DecisionRecord) -> None:
        project = self.project(record.project_id)
        if (
            project.active_charter_revision is not None
            and record.charter_revision > project.active_charter_revision
        ):
            raise PermissionError("decision charter ownership is invalid")
        self.store.insert_immutable("project_decisions", record.decision_id, record.to_dict())
        self._relate(record.project_id, "project", record.project_id, "decision", record.decision_id)

    def insert_assumption(self, record: AssumptionRecord) -> None:
        self.project(record.project_id)
        self.store.insert_immutable("project_assumptions", record.assumption_id, record.to_dict())
        self._relate(record.project_id, "project", record.project_id, "assumption", record.assumption_id)

    def insert_memory(self, record: MemoryRecord) -> None:
        project = self.project(record.project_id)
        if (
            project.active_charter_revision is not None
            and record.charter_revision > project.active_charter_revision
        ):
            raise PermissionError("memory charter ownership is invalid")
        if record.task_id is not None:
            task = self.task(record.task_id)
            if (
                task.project_id != record.project_id
                or task.charter_revision != record.charter_revision
                or (
                    record.stage_id is not None
                    and task.stage_id != record.stage_id
                )
            ):
                raise PermissionError("memory task ownership is invalid")
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
        with self.store.connect() as connection:
            self._insert_relation(
                connection,
                project_id,
                parent_kind,
                parent_id,
                child_kind,
                child_id,
            )

    def _cas_entity(
        self,
        table: str,
        identifier: str,
        expected: dict[str, Any],
        updated: dict[str, Any],
    ) -> None:
        expected_serialized = _serialize(expected)
        expected_hash = _digest_serialized(expected_serialized)
        with self.store.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            self._update_entity_cas(
                connection, table, identifier, expected_hash, updated
            )

    def _validate_task_parentage(self, task: ExecutiveTask) -> None:
        project = self.project(task.project_id)
        workflows = {
            item.workflow_id: item for item in self.workflows(task.project_id)
        }
        workflow = workflows.get(task.workflow_id)
        if (
            workflow is None
            or workflow.project_id != task.project_id
            or workflow.charter_id != task.charter_id
            or workflow.charter_revision != task.charter_revision
            or project.active_charter_id != task.charter_id
            or project.active_charter_revision != task.charter_revision
            or task.stage_id
            not in {stage.stage_id for stage in workflow.stages}
        ):
            raise PermissionError("task parent-child ownership is invalid")

    @staticmethod
    def _entity_in_transaction(
        connection: sqlite3.Connection,
        table: str,
        identifier: str,
    ) -> tuple[dict[str, Any], str]:
        row = connection.execute(
            f'SELECT payload, payload_hash FROM "{table}" WHERE id=?',
            (identifier,),
        ).fetchone()
        if row is None:
            raise KeyError(f"{table} record not found: {identifier}")
        serialized = str(row["payload"])
        digest = _digest_serialized(serialized)
        if digest != row["payload_hash"]:
            raise RuntimeError(
                f"stored {table} record failed integrity validation"
            )
        payload = json.loads(serialized)
        if not isinstance(payload, dict):
            raise RuntimeError(f"stored {table} record is not an object")
        return payload, str(row["payload_hash"])

    @staticmethod
    def _insert_entity(
        connection: sqlite3.Connection,
        table: str,
        identifier: str,
        payload: dict[str, Any],
    ) -> None:
        serialized = _serialize(payload)
        timestamp = utc_now()
        try:
            connection.execute(
                f'INSERT INTO "{table}" '
                "(id, schema_version, created_at, updated_at, payload, payload_hash) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (
                    identifier,
                    SCHEMA_VERSION,
                    timestamp,
                    timestamp,
                    serialized,
                    _digest_serialized(serialized),
                ),
            )
        except sqlite3.IntegrityError as error:
            raise PermissionError(
                f"immutable {table} record already exists: {identifier}"
            ) from error

    @staticmethod
    def _update_entity_cas(
        connection: sqlite3.Connection,
        table: str,
        identifier: str,
        expected_hash: str,
        payload: dict[str, Any],
    ) -> None:
        serialized = _serialize(payload)
        cursor = connection.execute(
            f'UPDATE "{table}" SET updated_at=?, payload=?, payload_hash=? '
            "WHERE id=? AND payload_hash=?",
            (
                utc_now(),
                serialized,
                _digest_serialized(serialized),
                identifier,
                expected_hash,
            ),
        )
        if cursor.rowcount != 1:
            raise PermissionError(f"stale {table} write was rejected")

    @staticmethod
    def _insert_relation(
        connection: sqlite3.Connection,
        project_id: str,
        parent_kind: str,
        parent_id: str,
        child_kind: str,
        child_id: str,
    ) -> None:
        material = f"{parent_kind}:{parent_id}:{child_kind}:{child_id}"
        relationship_id = hashlib.sha256(material.encode("utf-8")).hexdigest()
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

    @staticmethod
    def _require_no_newer_charter(
        connection: sqlite3.Connection,
        project_id: str,
        revision: int,
    ) -> None:
        rows = connection.execute(
            'SELECT payload, payload_hash FROM "project_charters"'
        ).fetchall()
        for row in rows:
            serialized = str(row["payload"])
            if _digest_serialized(serialized) != row["payload_hash"]:
                raise RuntimeError(
                    "stored project_charters record failed integrity validation"
                )
            payload = json.loads(serialized)
            if (
                isinstance(payload, dict)
                and payload.get("project_id") == project_id
                and int(payload.get("revision", 0)) > revision
            ):
                raise PermissionError(
                    "a newer charter revision supersedes this approval"
                )

    @staticmethod
    def _validate_charter_approval(
        charter: ProjectCharter,
        approval: ApprovalRecord,
        interaction: dict[str, Any],
        now: str,
    ) -> None:
        if (
            approval.approval_id != charter.founder_approval_record_id
            or approval.project_id != charter.project_id
            or approval.charter_id != charter.charter_id
            or approval.charter_revision != charter.revision
            or approval.approver != "Founder"
            or charter.founder_approval_identity != "Founder"
            or approval.evidence_digest != charter_approval_digest(charter)
            or approval.revoked_at is not None
            or approval.consumed_at is not None
            or interaction.get("interaction_id")
            != approval.source_interaction_id
            or interaction.get("project_id") != charter.project_id
            or interaction.get("speaker") != "Founder"
            or approval.limits.get("authentication_method")
            != "trusted-founder-interaction"
            or approval.limits.get("source_interaction_digest")
            != canonical_digest(interaction)
        ):
            raise PermissionError(
                "charter approval authentication or binding is invalid"
            )
        if (
            approval.expires_at is not None
            and datetime.fromisoformat(approval.expires_at)
            <= datetime.fromisoformat(now).astimezone(UTC)
        ):
            raise PermissionError("charter approval is expired")

    @staticmethod
    def _validate_action_approval(
        approval: ApprovalRecord,
        charter: ProjectCharter,
        interaction: dict[str, Any],
        action: ProposedAction,
        now: str,
    ) -> None:
        binding = {
            "project_id": approval.project_id,
            "charter_id": approval.charter_id,
            "charter_revision": approval.charter_revision,
            "kind": approval.kind,
            "action_category": approval.action_category,
            "scope": approval.scope,
            "limits": approval.limits,
            "source_interaction_id": approval.source_interaction_id,
        }
        if (
            approval.project_id != action.project_id
            or approval.charter_id != charter.charter_id
            or approval.charter_revision != action.charter_revision
            or charter.revision != action.charter_revision
            or charter.status != CharterStatus.ACTIVE
            or approval.approver != "Founder"
            or approval.action_category not in {None, action.category}
            or not set(action.scope).issubset(set(approval.scope))
            or approval.revoked_at is not None
            or approval.consumed_at is not None
            or interaction.get("interaction_id")
            != approval.source_interaction_id
            or interaction.get("project_id") != action.project_id
            or interaction.get("speaker") != "Founder"
            or approval.limits.get("authentication_method")
            != "trusted-founder-interaction"
            or approval.limits.get("source_interaction_digest")
            != canonical_digest(interaction)
            or approval.evidence_digest != canonical_digest(binding)
        ):
            raise PermissionError("action approval binding is invalid")
        if (
            approval.expires_at is not None
            and datetime.fromisoformat(approval.expires_at)
            <= datetime.fromisoformat(now).astimezone(UTC)
        ):
            raise PermissionError("action approval is expired")
        provider = approval.limits.get("provider")
        workspace = approval.limits.get("workspace")
        action_id = approval.limits.get("action_id")
        if (
            (provider is not None and action.provider != provider)
            or (workspace is not None and action.workspace != workspace)
            or (action_id is not None and action.action_id != action_id)
        ):
            raise PermissionError("action approval limits do not match")

    def _consume_action_authority_in_transaction(
        self,
        connection: sqlite3.Connection,
        action: ProposedAction,
        approval_id: str,
        task_id: str | None,
        timestamp: str,
    ) -> tuple[ApprovalRecord, str | None]:
        approval_payload, approval_hash = self._entity_in_transaction(
            connection, "executive_approvals", approval_id
        )
        approval = ApprovalRecord.from_dict(approval_payload)
        charter_payload, _ = self._entity_in_transaction(
            connection, "project_charters", approval.charter_id
        )
        charter = ProjectCharter.from_dict(charter_payload)
        interaction, _ = self._entity_in_transaction(
            connection,
            "project_conversations",
            approval.source_interaction_id,
        )
        self._validate_action_approval(
            approval, charter, interaction, action, timestamp
        )
        consumed = approval
        if approval.kind == ApprovalKind.ONE_TIME:
            consumed = replace(approval, consumed_at=timestamp)
            self._update_entity_cas(
                connection,
                "executive_approvals",
                approval.approval_id,
                approval_hash,
                consumed.to_dict(),
            )
            try:
                connection.execute(
                    "INSERT INTO executive_approval_consumptions "
                    "VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (
                        approval.approval_id,
                        action.project_id,
                        approval.charter_id,
                        action.charter_revision,
                        action.action_id,
                        task_id,
                        timestamp,
                    ),
                )
            except sqlite3.IntegrityError as error:
                raise PermissionError(
                    "one-time approval was already consumed"
                ) from error
        reservation_id = self._reserve_budget_in_transaction(
            connection,
            charter,
            approval,
            action,
            task_id,
            timestamp,
        )
        return consumed, reservation_id

    @staticmethod
    def _reserve_budget_in_transaction(
        connection: sqlite3.Connection,
        charter: ProjectCharter,
        approval: ApprovalRecord,
        action: ProposedAction,
        task_id: str | None,
        timestamp: str,
    ) -> str | None:
        spending = action.spending or action.cost is None or (action.cost or 0) > 0
        if not spending:
            return None
        if action.cost is None:
            raise PermissionError("unknown action cost fails closed")
        currency = action.currency
        approved_currency = approval.limits.get("currency")
        if (
            currency is None
            or currency != charter.authority_envelope.currency
            or currency != approved_currency
        ):
            raise PermissionError("spending currency is not explicitly approved")
        try:
            amount = Decimal(str(action.cost))
            amount_minor_decimal = amount * 100
            if amount_minor_decimal != amount_minor_decimal.to_integral_value():
                raise PermissionError("spending amount has unsupported precision")
            amount_minor = int(amount_minor_decimal)
            approval_limit = Decimal(str(approval.limits["maximum_cost"]))
        except (InvalidOperation, KeyError, TypeError, ValueError) as error:
            raise PermissionError("spending approval limit is invalid") from error
        if amount_minor <= 0:
            raise PermissionError("spending reservation must be positive")
        charter_limit = min(
            Decimal(str(charter.budget_limit)),
            Decimal(str(charter.authority_envelope.maximum_cost)),
            approval_limit,
        )
        limit_minor = int(charter_limit * 100)
        reserved = int(
            connection.execute(
                "SELECT COALESCE(SUM(amount_minor), 0) "
                "FROM executive_budget_reservations "
                "WHERE project_id=? AND charter_id=? AND charter_revision=? "
                "AND currency=? AND state IN ('RESERVED', 'CROSSED')",
                (
                    action.project_id,
                    charter.charter_id,
                    charter.revision,
                    currency,
                ),
            ).fetchone()[0]
        )
        if reserved + amount_minor > limit_minor:
            raise PermissionError(
                "cumulative spending would exceed the approved limit"
            )
        reservation_id = new_id("budget")
        try:
            connection.execute(
                "INSERT INTO executive_budget_reservations "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    reservation_id,
                    action.project_id,
                    charter.charter_id,
                    charter.revision,
                    approval.approval_id,
                    action.action_id,
                    task_id,
                    amount_minor,
                    currency,
                    "RESERVED",
                    timestamp,
                ),
            )
        except sqlite3.IntegrityError as error:
            raise PermissionError(
                "spending action already has a reservation"
            ) from error
        return reservation_id


def canonical_digest(value: dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def charter_approval_digest(charter: ProjectCharter) -> str:
    """Digest immutable identity and content, excluding lifecycle metadata."""
    payload = charter.to_dict()
    for field_name in (
        "status",
        "founder_approval_identity",
        "founder_approval_record_id",
        "updated_at",
    ):
        payload.pop(field_name)
    return canonical_digest(payload)


def task_definition_digest(task: ExecutiveTask) -> str:
    payload = task.to_dict()
    for field_name in (
        "provider_id",
        "model_id",
        "session_id",
        "status",
        "retry_count",
        "attempt_history",
        "result_disposition",
        "updated_at",
        "revision",
        "authority_attempt_id",
        "artifact_digest",
        "review_attempt_id",
        "late_result",
    ):
        payload.pop(field_name)
    return canonical_digest(payload)


def new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex}"


def _now() -> str:
    return utc_now()


def _serialize(value: dict[str, Any]) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _digest_serialized(serialized: str) -> str:
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()
