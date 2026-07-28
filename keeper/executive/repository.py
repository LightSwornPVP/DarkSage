from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from dataclasses import replace
from datetime import UTC, datetime
from typing import Any

from keeper.app.storage import SCHEMA_VERSION, KeeperStore
from keeper.executive.enums import CharterStatus, ExecutiveState
from keeper.executive.models import (
    ApprovalRecord,
    AssumptionRecord,
    DecisionRecord,
    ExecutiveTask,
    MemoryRecord,
    ProjectCharter,
    ProjectRecord,
    WorkflowRecord,
    utc_now,
)
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


def new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex}"


def _now() -> str:
    return utc_now()


def _serialize(value: dict[str, Any]) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _digest_serialized(serialized: str) -> str:
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()
