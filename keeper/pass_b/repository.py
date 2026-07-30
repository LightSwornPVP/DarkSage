from __future__ import annotations

import builtins
import hashlib
import json
import math
import os
import sqlite3
from dataclasses import replace
from datetime import datetime
from pathlib import Path
from typing import Any, TypeVar, cast

from keeper.app.storage import KeeperStore
from keeper.pass_b.enums import (
    AssignmentRole,
    AssignmentState,
    AttemptState,
    EvidenceState,
    ReservationMode,
    ReservationState,
    ReviewState,
    WorkItemState,
    WorkflowState,
)
from keeper.pass_b.models import (
    AssignmentRecord,
    AttemptRecord,
    EvidenceBundleRecord,
    PassBRecord,
    PauseReasonRecord,
    ProviderAccountRecord,
    ProviderRecord,
    ProviderSessionRecord,
    ResumeCheckpointRecord,
    ReviewRecord,
    UsagePoolRecord,
    WorkflowRecord,
    WorkItemRecord,
    WorkspaceReservationRecord,
    WriteReservationRecord,
)


R = TypeVar("R", bound=PassBRecord)
PASS_B_SCHEMA_VERSION = 3


class PassBRepository:
    """Transactional Pass B records stored inside the existing Keeper database."""

    def __init__(self, store: KeeperStore) -> None:
        self.store = store
        self.migrate()

    def migrate(self) -> None:
        with self.store.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                "CREATE TABLE IF NOT EXISTS pass_b_schema_migrations ("
                "version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL)"
            )
            current = int(
                connection.execute(
                    "SELECT COALESCE(MAX(version),0) FROM pass_b_schema_migrations"
                ).fetchone()[0]
            )
            if current > PASS_B_SCHEMA_VERSION:
                raise RuntimeError("Pass B schema is newer than this application")
            if current < 1:
                connection.execute(
                    "CREATE TABLE pass_b_records ("
                    "kind TEXT NOT NULL, id TEXT NOT NULL, project_id TEXT, "
                    "state TEXT NOT NULL, revision INTEGER NOT NULL CHECK(revision>0), "
                    "created_at TEXT NOT NULL, updated_at TEXT NOT NULL, "
                    "payload TEXT NOT NULL, payload_hash TEXT NOT NULL, "
                    "PRIMARY KEY(kind,id))"
                )
                connection.execute(
                    "CREATE INDEX ix_pass_b_records_project "
                    "ON pass_b_records(project_id,kind,updated_at)"
                )
                connection.execute(
                    "CREATE TABLE pass_b_workspace_claims ("
                    "reservation_id TEXT PRIMARY KEY, canonical_path TEXT NOT NULL, "
                    "assignment_id TEXT NOT NULL, "
                    "mode TEXT NOT NULL CHECK(mode IN ('READ_ONLY','WRITE')), "
                    "state TEXT NOT NULL CHECK(state IN "
                    "('ACTIVE','RELEASED','STALE','UNCERTAIN')), "
                    "lease_expires_at TEXT NOT NULL)"
                )
                connection.execute(
                    "CREATE INDEX ix_pass_b_workspace_claim_path "
                    "ON pass_b_workspace_claims(canonical_path,state)"
                )
                connection.execute(
                    "CREATE TABLE pass_b_write_claims ("
                    "scope_key TEXT PRIMARY KEY, reservation_id TEXT NOT NULL, "
                    "assignment_id TEXT NOT NULL, "
                    "state TEXT NOT NULL CHECK(state IN "
                    "('ACTIVE','RELEASED','STALE','UNCERTAIN')), "
                    "lease_expires_at TEXT NOT NULL)"
                )
                connection.execute(
                    "CREATE TABLE pass_b_usage_reservations ("
                    "reservation_id TEXT PRIMARY KEY, pool_id TEXT NOT NULL, "
                    "assignment_id TEXT NOT NULL, amount REAL NOT NULL CHECK(amount>=0), "
                    "state TEXT NOT NULL CHECK(state IN "
                    "('ACTIVE','CONSUMED','RELEASED')), "
                    "reserved_at TEXT NOT NULL, updated_at TEXT NOT NULL)"
                )
                connection.execute(
                    "CREATE UNIQUE INDEX ux_pass_b_usage_assignment_active "
                    "ON pass_b_usage_reservations(assignment_id) "
                    "WHERE state='ACTIVE'"
                )
                connection.execute(
                    "CREATE TABLE pass_b_launch_claims ("
                    "attempt_id TEXT PRIMARY KEY, assignment_id TEXT NOT NULL, "
                    "launch_token TEXT NOT NULL UNIQUE, "
                    "state TEXT NOT NULL CHECK(state IN "
                    "('RESERVED','LAUNCH_CLAIMED','RUNNING','COMPLETED',"
                    "'CANCELED','FAILED','UNCERTAIN')), "
                    "updated_at TEXT NOT NULL)"
                )
                connection.execute(
                    "CREATE UNIQUE INDEX ux_pass_b_assignment_active_launch "
                    "ON pass_b_launch_claims(assignment_id) "
                    "WHERE state IN "
                    "('RESERVED','LAUNCH_CLAIMED','RUNNING','COMPLETED','UNCERTAIN')"
                )
                connection.execute(
                    "INSERT INTO pass_b_schema_migrations(version,applied_at) "
                    "VALUES(1,?)",
                    (_now(),),
                )
            if current < 2:
                connection.execute(
                    "ALTER TABLE pass_b_usage_reservations "
                    "ADD COLUMN observation_generation INTEGER NOT NULL DEFAULT 1"
                )
                connection.execute(
                    "ALTER TABLE pass_b_launch_claims "
                    "ADD COLUMN authority_attempt_id TEXT NOT NULL DEFAULT ''"
                )
                connection.execute(
                    "UPDATE pass_b_launch_claims "
                    "SET authority_attempt_id='legacy:' || attempt_id "
                    "WHERE authority_attempt_id=''"
                )
                connection.execute(
                    "CREATE UNIQUE INDEX ux_pass_b_authority_attempt "
                    "ON pass_b_launch_claims(authority_attempt_id)"
                )
                connection.execute(
                    "INSERT INTO pass_b_schema_migrations(version,applied_at) "
                    "VALUES(2,?)",
                    (_now(),),
                )
            if current < 3:
                connection.execute(
                    "CREATE TABLE pass_b_usage_reset_observations ("
                    "observation_id TEXT PRIMARY KEY, "
                    "pool_id TEXT NOT NULL, "
                    "observation_generation INTEGER NOT NULL, "
                    "observation_digest TEXT NOT NULL, "
                    "observed_at TEXT NOT NULL, "
                    "UNIQUE(pool_id,observation_generation))"
                )
                connection.execute(
                    "INSERT INTO pass_b_schema_migrations(version,applied_at) "
                    "VALUES(3,?)",
                    (_now(),),
                )

    def insert(self, record: PassBRecord) -> None:
        with self.store.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            self._insert(connection, record)

    def replace(self, record: R, *, expected_revision: int) -> R:
        with self.store.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            self._replace(connection, record, expected_revision)
        return record

    def get(self, record_type: type[R], record_id: str) -> R:
        with self.store.connect() as connection:
            return self._get(connection, record_type, record_id)

    def optional(self, record_type: type[R], record_id: str) -> R | None:
        with self.store.connect() as connection:
            row = connection.execute(
                "SELECT payload,payload_hash FROM pass_b_records "
                "WHERE kind=? AND id=?",
                (record_type.KIND, record_id),
            ).fetchone()
            if row is None:
                return None
            return self._decode(record_type, row)

    def list(
        self, record_type: type[R], *, project_id: str | None = None
    ) -> list[R]:
        query = (
            "SELECT payload,payload_hash FROM pass_b_records WHERE kind=?"
        )
        parameters: tuple[object, ...] = (record_type.KIND,)
        if project_id is not None:
            query += " AND project_id=?"
            parameters += (project_id,)
        query += " ORDER BY created_at,id"
        with self.store.connect() as connection:
            rows = connection.execute(query, parameters).fetchall()
        return [self._decode(record_type, row) for row in rows]

    def insert_workflow(self, record: WorkflowRecord) -> None:
        if record.state != WorkflowState.ACTIVE:
            raise ValueError("new workflows must begin active")
        self.insert(record)

    def insert_work_item_bound(self, record: WorkItemRecord) -> None:
        with self.store.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            workflow = self._get(
                connection, WorkflowRecord, record.workflow_id
            )
            _validate_workflow_work_item(workflow, record)
            for dependency_id in record.dependencies:
                dependency = self._get(
                    connection, WorkItemRecord, dependency_id
                )
                if (
                    dependency.workflow_id != workflow.workflow_id
                    or dependency.project_id != workflow.project_id
                    or dependency.charter_id != workflow.charter_id
                    or dependency.charter_revision != workflow.charter_revision
                ):
                    raise PermissionError(
                        "work item dependency crosses its durable workflow"
                    )
            self._insert(connection, record)

    def insert_assignment_bound(
        self,
        record: AssignmentRecord,
        supplied_work_item: WorkItemRecord,
    ) -> None:
        with self.store.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            work_item = self._get(
                connection, WorkItemRecord, record.work_item_id
            )
            if work_item != supplied_work_item:
                raise PermissionError(
                    "assignment work item differs from durable state"
                )
            workflow = self._get(
                connection, WorkflowRecord, record.workflow_id
            )
            _validate_assignment_binding(workflow, work_item, record)
            self._insert(connection, record)

    def assignment_launch_binding(
        self, assignment_id: str
    ) -> tuple[WorkflowRecord, WorkItemRecord, AssignmentRecord]:
        with self.store.connect() as connection:
            assignment = self._get(
                connection, AssignmentRecord, assignment_id
            )
            work_item = self._get(
                connection, WorkItemRecord, assignment.work_item_id
            )
            workflow = self._get(
                connection, WorkflowRecord, assignment.workflow_id
            )
            _validate_assignment_binding(workflow, work_item, assignment)
            return workflow, work_item, assignment

    def reserve_workspace(self, record: WorkspaceReservationRecord) -> None:
        if record.state != ReservationState.ACTIVE:
            raise ValueError("new workspace reservations must be active")
        canonical_path = canonical_workspace_path(Path(record.canonical_path))
        if canonical_path != record.canonical_path:
            raise PermissionError("workspace reservation path is not canonical")
        with self.store.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            assignment = self._get(
                connection, AssignmentRecord, record.assignment_id
            )
            if assignment.workspace_id != record.workspace_id:
                raise PermissionError("workspace identity differs from assignment")
            if assignment.read_only and record.mode != ReservationMode.READ_ONLY:
                raise PermissionError("read-only assignment cannot reserve a writer")
            claims = connection.execute(
                "SELECT canonical_path,mode,state "
                "FROM pass_b_workspace_claims "
                "WHERE state IN ('ACTIVE','UNCERTAIN')"
            ).fetchall()
            if any(
                _path_overlap(
                    record.canonical_path, str(item["canonical_path"])
                )
                and (
                    record.mode == ReservationMode.WRITE
                    or str(item["mode"]) == ReservationMode.WRITE
                )
                for item in claims
            ):
                raise PermissionError("workspace already has an incompatible owner")
            self._insert(connection, record)
            connection.execute(
                "INSERT INTO pass_b_workspace_claims VALUES(?,?,?,?,?,?)",
                (
                    record.workspace_reservation_id,
                    record.canonical_path,
                    record.assignment_id,
                    record.mode,
                    record.state,
                    record.lease_expires_at,
                ),
            )

    def reserve_write(self, record: WriteReservationRecord) -> None:
        if record.state != ReservationState.ACTIVE:
            raise ValueError("new write reservations must be active")
        with self.store.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            assignment = self._get(
                connection, AssignmentRecord, record.assignment_id
            )
            workspace = self._get(
                connection,
                WorkspaceReservationRecord,
                record.workspace_reservation_id,
            )
            if (
                canonical_workspace_path(Path(workspace.canonical_path))
                != workspace.canonical_path
            ):
                raise PermissionError("writer workspace path is not canonical")
            if tuple(
                canonical_scope(workspace.canonical_path, scope)
                for scope in record.scope
            ) != record.scope_keys:
                raise PermissionError("write reservation scope is not canonical")
            if (
                assignment.read_only
                or workspace.mode != ReservationMode.WRITE
                or workspace.state != ReservationState.ACTIVE
                or workspace.assignment_id != assignment.assignment_id
            ):
                raise PermissionError("assignment has no active writer workspace")
            active = connection.execute(
                "SELECT scope_key FROM pass_b_write_claims "
                "WHERE state IN ('ACTIVE','UNCERTAIN')"
            ).fetchall()
            existing = [str(row["scope_key"]) for row in active]
            if any(
                _scope_overlap(candidate, current)
                for candidate in record.scope_keys
                for current in existing
            ):
                raise PermissionError("protected write scope is already reserved")
            self._insert(connection, record)
            connection.executemany(
                "INSERT OR REPLACE INTO pass_b_write_claims "
                "VALUES(?,?,?,?,?)",
                [
                    (
                        key,
                        record.workspace_reservation_id,
                        record.assignment_id,
                        record.state,
                        record.lease_expires_at,
                    )
                    for key in record.scope_keys
                ],
            )

    def renew_workspace(
        self,
        reservation_id: str,
        owner_token: str,
        lease_expires_at: str,
        updated_at: str,
    ) -> WorkspaceReservationRecord:
        _parse_time(lease_expires_at)
        with self.store.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            current = self._get(
                connection, WorkspaceReservationRecord, reservation_id
            )
            if (
                canonical_workspace_path(Path(current.canonical_path))
                != current.canonical_path
            ):
                raise PermissionError("workspace lease path is no longer safe")
            if (
                current.owner_token != owner_token
                or current.state != ReservationState.ACTIVE
            ):
                raise PermissionError("workspace lease owner or state changed")
            updated = replace(
                current,
                lease_expires_at=lease_expires_at,
                updated_at=updated_at,
                revision=current.revision + 1,
            )
            self._replace(connection, updated, current.revision)
            for write in self._active_writes(connection, reservation_id):
                self._replace(
                    connection,
                    replace(
                        write,
                        lease_expires_at=lease_expires_at,
                        updated_at=updated_at,
                        revision=write.revision + 1,
                    ),
                    write.revision,
                )
            connection.execute(
                "UPDATE pass_b_write_claims SET lease_expires_at=? "
                "WHERE reservation_id=? AND state='ACTIVE'",
                (lease_expires_at, reservation_id),
            )
            connection.execute(
                "UPDATE pass_b_workspace_claims SET lease_expires_at=? "
                "WHERE reservation_id=? AND state='ACTIVE'",
                (lease_expires_at, reservation_id),
            )
        return updated

    def release_workspace(
        self, reservation_id: str, owner_token: str, updated_at: str
    ) -> WorkspaceReservationRecord:
        with self.store.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            current = self._get(
                connection, WorkspaceReservationRecord, reservation_id
            )
            if (
                canonical_workspace_path(Path(current.canonical_path))
                != current.canonical_path
            ):
                raise PermissionError("workspace release path is no longer safe")
            assignment = self._get(
                connection, AssignmentRecord, current.assignment_id
            )
            if current.owner_token != owner_token:
                raise PermissionError("workspace lease owner changed")
            if assignment.state in {
                AssignmentState.LAUNCH_CLAIMED,
                AssignmentState.RUNNING,
                AssignmentState.UNCERTAIN,
            }:
                raise PermissionError("active or uncertain workspace cannot be released")
            updated = replace(
                current,
                state=ReservationState.RELEASED,
                updated_at=updated_at,
                revision=current.revision + 1,
            )
            self._replace(connection, updated, current.revision)
            for write in self._active_writes(connection, reservation_id):
                self._replace(
                    connection,
                    replace(
                        write,
                        state=ReservationState.RELEASED,
                        updated_at=updated_at,
                        revision=write.revision + 1,
                    ),
                    write.revision,
                )
            connection.execute(
                "UPDATE pass_b_workspace_claims SET state='RELEASED' "
                "WHERE reservation_id=? AND state='ACTIVE'",
                (reservation_id,),
            )
            connection.execute(
                "UPDATE pass_b_write_claims SET state='RELEASED' "
                "WHERE reservation_id=? AND state='ACTIVE'",
                (reservation_id,),
            )
        return updated

    def recover_stale_workspace(
        self, reservation_id: str, observed_at: str
    ) -> WorkspaceReservationRecord:
        observed = _parse_time(observed_at)
        with self.store.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            current = self._get(
                connection, WorkspaceReservationRecord, reservation_id
            )
            if (
                canonical_workspace_path(Path(current.canonical_path))
                != current.canonical_path
            ):
                raise PermissionError("workspace release path is no longer safe")
            assignment = self._get(
                connection, AssignmentRecord, current.assignment_id
            )
            if _parse_time(current.lease_expires_at) > observed:
                raise PermissionError("workspace lease has not expired")
            if assignment.state in {
                AssignmentState.LAUNCH_CLAIMED,
                AssignmentState.RUNNING,
                AssignmentState.UNCERTAIN,
            }:
                raise PermissionError("stale active work requires Founder review")
            updated = replace(
                current,
                state=ReservationState.STALE,
                updated_at=observed_at,
                revision=current.revision + 1,
            )
            self._replace(connection, updated, current.revision)
            for write in self._active_writes(connection, reservation_id):
                self._replace(
                    connection,
                    replace(
                        write,
                        state=ReservationState.STALE,
                        updated_at=observed_at,
                        revision=write.revision + 1,
                    ),
                    write.revision,
                )
            connection.execute(
                "UPDATE pass_b_workspace_claims SET state='STALE' "
                "WHERE reservation_id=? AND state='ACTIVE'",
                (reservation_id,),
            )
            connection.execute(
                "UPDATE pass_b_write_claims SET state='STALE' "
                "WHERE reservation_id=? AND state='ACTIVE'",
                (reservation_id,),
            )
        return updated

    def reserve_usage_or_pause(
        self,
        *,
        reservation_id: str,
        pool_id: str,
        assignment_id: str,
        amount: float,
        pause: PauseReasonRecord,
        checkpoint: ResumeCheckpointRecord,
        observed_at: str,
    ) -> bool:
        if not math.isfinite(amount) or amount < 0:
            raise ValueError("usage reservation must be finite and nonnegative")
        with self.store.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            pool = self._get(connection, UsagePoolRecord, pool_id)
            assignment = self._get(
                connection, AssignmentRecord, assignment_id
            )
            account = self._get(
                connection, ProviderAccountRecord, assignment.account_id
            )
            if account.usage_pool_id != pool_id:
                raise PermissionError("assignment account uses another usage pool")
            remaining = pool.remaining
            exhausted = pool.exhausted or (
                remaining is not None and remaining < amount
            )
            if exhausted:
                paused_assignment = replace(
                    assignment,
                    state=AssignmentState.WAITING_FOR_USAGE_RESET,
                    updated_at=observed_at,
                    revision=assignment.revision + 1,
                )
                exhausted_pool = replace(
                    pool,
                    exhausted=True,
                    updated_at=observed_at,
                    last_observed_at=observed_at,
                    revision=pool.revision + 1,
                )
                self._replace(connection, paused_assignment, assignment.revision)
                self._replace(connection, exhausted_pool, pool.revision)
                self._insert(connection, pause)
                self._insert(connection, checkpoint)
                return False
            updated_remaining = (
                None if remaining is None else max(0.0, remaining - amount)
            )
            updated_pool = replace(
                pool,
                reserved=pool.reserved + amount,
                remaining=updated_remaining,
                last_observed_at=observed_at,
                updated_at=observed_at,
                revision=pool.revision + 1,
            )
            self._replace(connection, updated_pool, pool.revision)
            connection.execute(
                "INSERT INTO pass_b_usage_reservations("
                "reservation_id,pool_id,assignment_id,amount,state,"
                "reserved_at,updated_at,observation_generation"
                ") VALUES(?,?,?,?,?,?,?,?)",
                (
                    reservation_id,
                    pool_id,
                    assignment_id,
                    amount,
                    "ACTIVE",
                    observed_at,
                    observed_at,
                    pool.observation_generation,
                ),
            )
            return True

    def observe_usage_reset(
        self,
        *,
        pool_id: str,
        observation_id: str,
        observation_digest: str,
        observed_reset_at: str,
        observation_source: str,
        observation_generation: int,
        observed_capacity: float | None,
        observed_consumed: float,
        observed_remaining: float | None,
        confidence: str,
        observed_at: str,
    ) -> UsagePoolRecord:
        reset = _parse_time(observed_reset_at)
        observation = _parse_time(observed_at)
        if reset > observation:
            raise PermissionError("usage reset observation is in the future")
        if (
            not observation_id
            or len(observation_digest) != 64
            or not observation_source
            or confidence not in {"HIGH", "MEDIUM"}
        ):
            raise PermissionError("usage reset observation is not trustworthy")
        with self.store.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            pool = self._get(connection, UsagePoolRecord, pool_id)
            if (
                pool.reset_at is None
                or reset < _parse_time(pool.reset_at)
                or observation <= _parse_time(pool.last_observed_at)
                or observation_generation != pool.observation_generation + 1
                or observed_capacity != pool.capacity
            ):
                raise PermissionError("usage reset observation is stale")
            active = connection.execute(
                "SELECT COALESCE(SUM(amount),0) "
                "FROM pass_b_usage_reservations "
                "WHERE pool_id=? AND state='ACTIVE'",
                (pool_id,),
            ).fetchone()
            reserved = float(active[0])
            if (
                observed_remaining is not None
                and observed_remaining < reserved
            ):
                raise PermissionError(
                    "usage reset cannot cover active durable reservations"
                )
            remaining = (
                None
                if observed_remaining is None
                else observed_remaining - reserved
            )
            updated = replace(
                pool,
                consumed=observed_consumed,
                reserved=reserved,
                remaining=remaining,
                reset_at=None,
                observation_source=observation_source,
                confidence=confidence,
                exhausted=(
                    remaining is not None and remaining <= 0
                ),
                last_observed_at=observed_at,
                updated_at=observed_at,
                revision=pool.revision + 1,
                observation_generation=pool.observation_generation + 1,
            )
            self._replace(connection, updated, pool.revision)
            try:
                connection.execute(
                    "INSERT INTO pass_b_usage_reset_observations "
                    "VALUES(?,?,?,?,?)",
                    (
                        observation_id,
                        pool_id,
                        updated.observation_generation,
                        observation_digest,
                        observed_at,
                    ),
                )
            except sqlite3.IntegrityError as error:
                raise PermissionError(
                    "usage reset observation was replayed"
                ) from error
        return updated

    def resume_after_usage_reset(
        self,
        *,
        pool_id: str,
        assignment_id: str,
        checkpoint_id: str,
        resumed_at: str,
    ) -> AssignmentRecord:
        resumed = _parse_time(resumed_at)
        with self.store.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            pool = self._get(connection, UsagePoolRecord, pool_id)
            assignment = self._get(
                connection, AssignmentRecord, assignment_id
            )
            checkpoint = self._get(
                connection, ResumeCheckpointRecord, checkpoint_id
            )
            if (
                assignment.state != AssignmentState.WAITING_FOR_USAGE_RESET
                or checkpoint.assignment_id != assignment_id
                or checkpoint.project_id != assignment.project_id
                or checkpoint.charter_id != assignment.charter_id
                or checkpoint.charter_revision != assignment.charter_revision
                or checkpoint.authority_envelope_digest
                != assignment.authority_envelope_digest
                or checkpoint.usage_pool_id != pool_id
                or checkpoint.resumed_at is not None
                or checkpoint.checkpoint_state.get(
                    "usage_observation_generation"
                )
                != pool.observation_generation - 1
                or checkpoint.checkpoint_state.get("provider_id")
                != assignment.provider_id
                or checkpoint.checkpoint_state.get("account_id")
                != assignment.account_id
                or checkpoint.checkpoint_state.get("session_id")
                != assignment.session_id
                or checkpoint.checkpoint_state.get("model_id")
                != assignment.model_id
                or checkpoint.checkpoint_state.get(
                    "assignment_revision"
                )
                != assignment.revision - 1
            ):
                raise PermissionError("resume checkpoint no longer matches assignment")
            if (
                pool.observation_generation < 2
                or _parse_time(pool.last_observed_at) > resumed
                or pool.exhausted
            ):
                raise PermissionError("validated usage reset has not occurred")
            workspace = self._get(
                connection,
                WorkspaceReservationRecord,
                checkpoint.workspace_reservation_id,
            )
            if (
                workspace.assignment_id != assignment_id
                or workspace.state != ReservationState.ACTIVE
                or workspace.workspace_id != assignment.workspace_id
                or (
                    "workspace_id" in checkpoint.checkpoint_state
                    and checkpoint.checkpoint_state["workspace_id"]
                    != workspace.workspace_id
                )
                or (
                    "workspace_canonical_path"
                    in checkpoint.checkpoint_state
                    and checkpoint.checkpoint_state[
                        "workspace_canonical_path"
                    ]
                    != workspace.canonical_path
                )
                or checkpoint.checkpoint_state.get(
                    "workspace_revision"
                )
                != workspace.revision
            ):
                raise PermissionError("resume workspace is unavailable")
            uncertain = connection.execute(
                "SELECT 1 FROM pass_b_launch_claims "
                "WHERE assignment_id=? AND state='UNCERTAIN'",
                (assignment_id,),
            ).fetchone()
            if uncertain is not None:
                raise PermissionError("uncertain attempt cannot resume automatically")
            reset_observation = connection.execute(
                "SELECT 1 FROM pass_b_usage_reset_observations "
                "WHERE pool_id=? AND observation_generation=?",
                (pool_id, pool.observation_generation),
            ).fetchone()
            if reset_observation is None:
                raise PermissionError(
                    "durable usage reset observation is missing"
                )
            updated_assignment = replace(
                assignment,
                state=AssignmentState.READY,
                updated_at=resumed_at,
                revision=assignment.revision + 1,
            )
            updated_checkpoint = replace(
                checkpoint,
                resumed_at=resumed_at,
                revision=checkpoint.revision + 1,
            )
            self._replace(connection, updated_assignment, assignment.revision)
            self._replace(connection, updated_checkpoint, checkpoint.revision)
            pauses = connection.execute(
                "SELECT payload,payload_hash FROM pass_b_records "
                "WHERE kind=? AND state='' ORDER BY created_at",
                (PauseReasonRecord.KIND,),
            ).fetchall()
            for row in pauses:
                pause = self._decode(PauseReasonRecord, row)
                if pause.assignment_id == assignment_id and pause.resolved_at is None:
                    self._replace(
                        connection,
                        replace(
                            pause,
                            resolved_at=resumed_at,
                            revision=pause.revision + 1,
                        ),
                        pause.revision,
                    )
        return updated_assignment

    def reserve_attempt(
        self,
        attempt: AttemptRecord,
        *,
        expected_workflow: WorkflowRecord | None = None,
        expected_work_item: WorkItemRecord | None = None,
        expected_assignment: AssignmentRecord | None = None,
    ) -> None:
        if attempt.state != AttemptState.RESERVED:
            raise ValueError("new attempts must begin reserved")
        with self.store.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            assignment = self._get(
                connection, AssignmentRecord, attempt.assignment_id
            )
            work_item = self._get(
                connection, WorkItemRecord, assignment.work_item_id
            )
            workflow = self._get(
                connection, WorkflowRecord, assignment.workflow_id
            )
            _validate_assignment_binding(workflow, work_item, assignment)
            expected = (
                expected_workflow,
                expected_work_item,
                expected_assignment,
            )
            if any(item is not None for item in expected) and (
                expected_workflow != workflow
                or expected_work_item != work_item
                or expected_assignment != assignment
            ):
                raise PermissionError(
                    "launch binding changed before the transactional claim"
                )
            session = self._get(
                connection, ProviderSessionRecord, assignment.session_id
            )
            workspace = self._active_workspace(connection, assignment.assignment_id)
            usage_row = connection.execute(
                "SELECT reservation_id,pool_id,observation_generation "
                "FROM pass_b_usage_reservations "
                "WHERE assignment_id=? AND state='ACTIVE'",
                (assignment.assignment_id,),
            ).fetchone()
            if (
                assignment.state != AssignmentState.READY
                or session.provider_id != assignment.provider_id
                or session.account_id != assignment.account_id
                or session.active_assignments >= session.concurrency_limit
                or workspace.workspace_id != assignment.workspace_id
                or workspace.workspace_reservation_id
                != attempt.workspace_reservation_id
                or workspace.state != ReservationState.ACTIVE
                or _parse_time(workspace.lease_expires_at)
                <= _parse_time(attempt.created_at)
            ):
                raise PermissionError("assignment is not launch-ready")
            if bool(assignment.usage_policy.get("reservation_required", True)):
                if (
                    usage_row is None
                    or usage_row["reservation_id"]
                    != attempt.usage_reservation_id
                ):
                    raise PermissionError("assignment has no usage reservation")
                pool = self._get(
                    connection,
                    UsagePoolRecord,
                    str(usage_row["pool_id"]),
                )
                if pool.exhausted:
                    raise PermissionError(
                        "usage pool exhausted before provider launch"
                    )
            elif attempt.usage_reservation_id is not None:
                raise PermissionError("unexpected usage reservation binding")
            if not assignment.read_only:
                write = connection.execute(
                    "SELECT 1 FROM pass_b_write_claims "
                    "WHERE reservation_id=? AND assignment_id=? "
                    "AND state='ACTIVE'",
                    (
                        workspace.workspace_reservation_id,
                        assignment.assignment_id,
                    ),
                ).fetchone()
                if write is None:
                    raise PermissionError(
                        "write-capable launch requires a protected write scope"
                    )
            updated_session = replace(
                session,
                active_assignments=session.active_assignments + 1,
                state=(
                    "BUSY"
                    if session.active_assignments + 1
                    >= session.concurrency_limit
                    else session.state
                ),
                last_seen_at=attempt.created_at,
                updated_at=attempt.created_at,
                revision=session.revision + 1,
            )
            self._insert(connection, attempt)
            self._replace(connection, updated_session, session.revision)
            try:
                connection.execute(
                    "INSERT INTO pass_b_launch_claims("
                    "attempt_id,assignment_id,launch_token,state,updated_at,"
                    "authority_attempt_id) VALUES(?,?,?,?,?,?)",
                    (
                        attempt.attempt_id,
                        attempt.assignment_id,
                        attempt.launch_token,
                        attempt.state,
                        attempt.updated_at,
                        attempt.authority_attempt_id,
                    ),
                )
            except sqlite3.IntegrityError as error:
                raise PermissionError(
                    "assignment already has an active or completed launch"
                ) from error

    def decide_review(
        self,
        review_id: str,
        *,
        decided_at: str,
    ) -> tuple[ReviewRecord, AssignmentRecord, WorkItemRecord]:
        with self.store.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            review = self._get(connection, ReviewRecord, review_id)
            assignment = self._get(
                connection, AssignmentRecord, review.assignment_id
            )
            work_item = self._get(
                connection, WorkItemRecord, assignment.work_item_id
            )
            producer_evidence = self._get(
                connection,
                EvidenceBundleRecord,
                review.producer_evidence_bundle_id,
            )
            reviewer_assignment = self._get(
                connection,
                AssignmentRecord,
                review.reviewer_assignment_id,
            )
            reviewer_attempt = self._get(
                connection, AttemptRecord, review.reviewer_attempt_id
            )
            reviewer_evidence = self._get(
                connection,
                EvidenceBundleRecord,
                review.reviewer_evidence_bundle_id,
            )
            if (
                review.state != ReviewState.PENDING
                or review.disposition
                not in {
                    ReviewState.ACCEPTED,
                    ReviewState.REPAIR_REQUIRED,
                }
                or assignment.state != AssignmentState.REVIEW_REQUIRED
                or producer_evidence.state != EvidenceState.VALIDATED
                or producer_evidence.assignment_id
                != assignment.assignment_id
                or producer_evidence.attempt_id != review.attempt_id
                or reviewer_assignment.role != AssignmentRole.REVIEWER
                or not reviewer_assignment.read_only
                or reviewer_assignment.state
                != AssignmentState.REVIEW_REQUIRED
                or reviewer_attempt.assignment_id
                != reviewer_assignment.assignment_id
                or reviewer_attempt.state != AttemptState.COMPLETED
                or reviewer_evidence.assignment_id
                != reviewer_assignment.assignment_id
                or reviewer_evidence.attempt_id
                != reviewer_attempt.attempt_id
                or reviewer_evidence.state != EvidenceState.VALIDATED
                or reviewer_assignment.project_id != assignment.project_id
                or reviewer_assignment.charter_id != assignment.charter_id
                or reviewer_assignment.charter_revision
                != assignment.charter_revision
                or reviewer_assignment.usage_policy.get(
                    "review_of_assignment_id"
                )
                != assignment.assignment_id
                or reviewer_assignment.independence_key
                == assignment.independence_key
                or work_item.project_id != assignment.project_id
                or work_item.charter_id != assignment.charter_id
                or work_item.charter_revision != assignment.charter_revision
            ):
                raise PermissionError("review decision binding changed")
            review_state = ReviewState(review.disposition)
            accepted = review_state == ReviewState.ACCEPTED
            assignment_state = (
                AssignmentState.COMPLETED
                if accepted
                else AssignmentState.REPAIR_REQUIRED
            )
            work_item_state = (
                WorkItemState.COMPLETED
                if accepted
                else WorkItemState.REPAIR_REQUIRED
            )
            updated_review = replace(
                review,
                state=review_state,
                updated_at=decided_at,
                revision=review.revision + 1,
            )
            updated_assignment = replace(
                assignment,
                state=assignment_state,
                updated_at=decided_at,
                revision=assignment.revision + 1,
            )
            updated_work_item = replace(
                work_item,
                state=work_item_state,
                updated_at=decided_at,
                revision=work_item.revision + 1,
            )
            updated_reviewer = replace(
                reviewer_assignment,
                state=AssignmentState.COMPLETED,
                updated_at=decided_at,
                revision=reviewer_assignment.revision + 1,
            )
            self._replace(connection, updated_review, review.revision)
            self._replace(
                connection, updated_assignment, assignment.revision
            )
            self._replace(
                connection, updated_work_item, work_item.revision
            )
            self._replace(
                connection,
                updated_reviewer,
                reviewer_assignment.revision,
            )
        return updated_review, updated_assignment, updated_work_item

    def claim_launch(self, attempt_id: str, claimed_at: str) -> AttemptRecord:
        with self.store.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            attempt = self._get(connection, AttemptRecord, attempt_id)
            assignment = self._get(
                connection, AssignmentRecord, attempt.assignment_id
            )
            if (
                attempt.state != AttemptState.RESERVED
                or assignment.state != AssignmentState.READY
            ):
                raise PermissionError("attempt launch claim was already consumed")
            updated_attempt = replace(
                attempt,
                state=AttemptState.LAUNCH_CLAIMED,
                updated_at=claimed_at,
                revision=attempt.revision + 1,
            )
            updated_assignment = replace(
                assignment,
                state=AssignmentState.LAUNCH_CLAIMED,
                updated_at=claimed_at,
                revision=assignment.revision + 1,
            )
            self._replace(connection, updated_attempt, attempt.revision)
            self._replace(connection, updated_assignment, assignment.revision)
            cursor = connection.execute(
                "UPDATE pass_b_launch_claims SET state='LAUNCH_CLAIMED',updated_at=? "
                "WHERE attempt_id=? AND state='RESERVED'",
                (claimed_at, attempt_id),
            )
            if cursor.rowcount != 1:
                raise PermissionError("durable launch claim changed concurrently")
        return updated_attempt

    def mark_running(
        self, attempt_id: str, external_execution_id: str, started_at: str
    ) -> AttemptRecord:
        with self.store.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            attempt = self._get(connection, AttemptRecord, attempt_id)
            assignment = self._get(
                connection, AssignmentRecord, attempt.assignment_id
            )
            work_item = self._get(
                connection, WorkItemRecord, assignment.work_item_id
            )
            workflow = self._get(
                connection, WorkflowRecord, assignment.workflow_id
            )
            _validate_assignment_binding(workflow, work_item, assignment)
            session = self._get(
                connection, ProviderSessionRecord, assignment.session_id
            )
            if (
                attempt.state != AttemptState.LAUNCH_CLAIMED
                or assignment.state != AssignmentState.LAUNCH_CLAIMED
                or not attempt.session_slot_claimed
                or session.active_assignments < 1
            ):
                raise PermissionError("attempt cannot cross the launch boundary")
            updated_attempt = replace(
                attempt,
                state=AttemptState.RUNNING,
                external_execution_id=external_execution_id,
                started_at=started_at,
                updated_at=started_at,
                revision=attempt.revision + 1,
            )
            updated_assignment = replace(
                assignment,
                state=AssignmentState.RUNNING,
                updated_at=started_at,
                revision=assignment.revision + 1,
            )
            self._replace(connection, updated_attempt, attempt.revision)
            self._replace(connection, updated_assignment, assignment.revision)
            cursor = connection.execute(
                "UPDATE pass_b_launch_claims SET state='RUNNING',updated_at=? "
                "WHERE attempt_id=? AND state='LAUNCH_CLAIMED'",
                (started_at, attempt_id),
            )
            if cursor.rowcount != 1:
                raise PermissionError("launch boundary changed concurrently")
        return updated_attempt

    def claim_cancellation(
        self, assignment_id: str, claimed_at: str
    ) -> AttemptRecord:
        with self.store.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT attempt_id FROM pass_b_launch_claims "
                "WHERE assignment_id=? AND state='RUNNING'",
                (assignment_id,),
            ).fetchone()
            if row is None:
                raise PermissionError("assignment has no cancelable running attempt")
            attempt = self._get(
                connection, AttemptRecord, str(row["attempt_id"])
            )
            assignment = self._get(
                connection, AssignmentRecord, assignment_id
            )
            if (
                attempt.state != AttemptState.RUNNING
                or assignment.state != AssignmentState.RUNNING
                or not attempt.external_execution_id
            ):
                raise PermissionError("running attempt cancellation claim changed")
            updated_attempt = replace(
                attempt,
                state=AttemptState.CANCELLATION_CLAIMED,
                updated_at=claimed_at,
                revision=attempt.revision + 1,
            )
            updated_assignment = replace(
                assignment,
                state=AssignmentState.CANCELLATION_CLAIMED,
                updated_at=claimed_at,
                revision=assignment.revision + 1,
            )
            self._replace(connection, updated_attempt, attempt.revision)
            self._replace(connection, updated_assignment, assignment.revision)
        return updated_attempt

    def complete_cancellation(
        self, attempt_id: str, canceled_at: str
    ) -> AttemptRecord:
        with self.store.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            attempt = self._get(connection, AttemptRecord, attempt_id)
            assignment = self._get(
                connection, AssignmentRecord, attempt.assignment_id
            )
            work_item = self._get(
                connection, WorkItemRecord, assignment.work_item_id
            )
            workflow = self._get(
                connection, WorkflowRecord, assignment.workflow_id
            )
            _validate_assignment_binding(workflow, work_item, assignment)
            session = self._get(
                connection, ProviderSessionRecord, assignment.session_id
            )
            if (
                attempt.state != AttemptState.CANCELLATION_CLAIMED
                or assignment.state != AssignmentState.CANCELLATION_CLAIMED
            ):
                raise PermissionError("cancellation claim changed concurrently")
            remaining = max(0, session.active_assignments - 1)
            updated_attempt = replace(
                attempt,
                state=AttemptState.CANCELED,
                finished_at=canceled_at,
                updated_at=canceled_at,
                revision=attempt.revision + 1,
            )
            updated_assignment = replace(
                assignment,
                state=AssignmentState.CANCELED,
                updated_at=canceled_at,
                revision=assignment.revision + 1,
            )
            updated_session = replace(
                session,
                active_assignments=remaining,
                state="BUSY"
                if remaining >= session.concurrency_limit
                else "READY",
                last_seen_at=canceled_at,
                updated_at=canceled_at,
                revision=session.revision + 1,
            )
            self._replace(connection, updated_attempt, attempt.revision)
            self._replace(connection, updated_assignment, assignment.revision)
            self._replace(connection, updated_session, session.revision)
            cursor = connection.execute(
                "UPDATE pass_b_launch_claims SET state='CANCELED',updated_at=? "
                "WHERE attempt_id=? AND state='RUNNING'",
                (canceled_at, attempt_id),
            )
            if cursor.rowcount != 1:
                raise PermissionError("durable cancellation claim changed")
            self._consume_usage(
                connection, assignment.assignment_id, canceled_at
            )
        return updated_attempt

    def complete_attempt(
        self,
        attempt_id: str,
        evidence: EvidenceBundleRecord,
        completed_at: str,
    ) -> AttemptRecord:
        with self.store.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            attempt = self._get(connection, AttemptRecord, attempt_id)
            assignment = self._get(
                connection, AssignmentRecord, attempt.assignment_id
            )
            work_item = self._get(
                connection, WorkItemRecord, assignment.work_item_id
            )
            workflow = self._get(
                connection, WorkflowRecord, assignment.workflow_id
            )
            _validate_assignment_binding(workflow, work_item, assignment)
            session = self._get(
                connection, ProviderSessionRecord, assignment.session_id
            )
            if (
                attempt.state != AttemptState.RUNNING
                or assignment.state != AssignmentState.RUNNING
                or evidence.attempt_id != attempt_id
                or evidence.assignment_id != assignment.assignment_id
                or evidence.state != EvidenceState.UNTRUSTED
            ):
                raise PermissionError("attempt completion binding is invalid")
            self._insert(connection, evidence)
            updated_attempt = replace(
                attempt,
                state=AttemptState.COMPLETED,
                finished_at=completed_at,
                updated_at=completed_at,
                revision=attempt.revision + 1,
            )
            updated_assignment = replace(
                assignment,
                state=AssignmentState.REVIEW_REQUIRED,
                updated_at=completed_at,
                revision=assignment.revision + 1,
            )
            updated_session = replace(
                session,
                active_assignments=max(0, session.active_assignments - 1),
                state="READY",
                last_seen_at=completed_at,
                updated_at=completed_at,
                revision=session.revision + 1,
            )
            self._replace(connection, updated_attempt, attempt.revision)
            self._replace(connection, updated_assignment, assignment.revision)
            self._replace(connection, updated_session, session.revision)
            connection.execute(
                "UPDATE pass_b_launch_claims SET state='COMPLETED',updated_at=? "
                "WHERE attempt_id=? AND state='RUNNING'",
                (completed_at, attempt_id),
            )
            self._consume_usage(connection, assignment.assignment_id, completed_at)
        return updated_attempt

    def recover_interrupted_attempts(self, recovered_at: str) -> dict[str, int]:
        result = {"prelaunch_released": 0, "uncertain": 0}
        with self.store.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            claims = connection.execute(
                "SELECT attempt_id,state FROM pass_b_launch_claims "
                "WHERE state IN "
                "('RESERVED','LAUNCH_CLAIMED','RUNNING')"
            ).fetchall()
            for claim in claims:
                attempt = self._get(
                    connection, AttemptRecord, str(claim["attempt_id"])
                )
                assignment = self._get(
                    connection, AssignmentRecord, attempt.assignment_id
                )
                state = str(claim["state"])
                if state == AttemptState.RESERVED:
                    session = self._get(
                        connection,
                        ProviderSessionRecord,
                        assignment.session_id,
                    )
                    self._replace(
                        connection,
                        replace(
                            attempt,
                            state=AttemptState.FAILED,
                            finished_at=recovered_at,
                            last_error="recovered before external launch",
                            updated_at=recovered_at,
                            revision=attempt.revision + 1,
                        ),
                        attempt.revision,
                    )
                    if attempt.session_slot_claimed:
                        remaining = max(
                            0, session.active_assignments - 1
                        )
                        self._replace(
                            connection,
                            replace(
                                session,
                                active_assignments=remaining,
                                state=(
                                    "BUSY"
                                    if remaining
                                    >= session.concurrency_limit
                                    else "READY"
                                ),
                                last_seen_at=recovered_at,
                                updated_at=recovered_at,
                                revision=session.revision + 1,
                            ),
                            session.revision,
                        )
                    connection.execute(
                        "UPDATE pass_b_launch_claims "
                        "SET state='FAILED',updated_at=? WHERE attempt_id=?",
                        (recovered_at, attempt.attempt_id),
                    )
                    result["prelaunch_released"] += 1
                    continue
                uncertain_attempt = replace(
                    attempt,
                    state=AttemptState.UNCERTAIN,
                    last_error="external execution outcome is uncertain after restart",
                    updated_at=recovered_at,
                    revision=attempt.revision + 1,
                    session_slot_claimed=(
                        attempt.session_slot_claimed
                        or state == AttemptState.LAUNCH_CLAIMED
                    ),
                )
                uncertain_assignment = replace(
                    assignment,
                    state=AssignmentState.UNCERTAIN,
                    updated_at=recovered_at,
                    revision=assignment.revision + 1,
                )
                self._replace(connection, uncertain_attempt, attempt.revision)
                self._replace(connection, uncertain_assignment, assignment.revision)
                if (
                    state == AttemptState.LAUNCH_CLAIMED
                    and not attempt.session_slot_claimed
                ):
                    session = self._get(
                        connection,
                        ProviderSessionRecord,
                        assignment.session_id,
                    )
                    if session.active_assignments >= session.concurrency_limit:
                        raise RuntimeError(
                            "legacy uncertain launch exceeds session capacity"
                        )
                    self._replace(
                        connection,
                        replace(
                            session,
                            active_assignments=session.active_assignments + 1,
                            state="BUSY",
                            last_seen_at=recovered_at,
                            updated_at=recovered_at,
                            revision=session.revision + 1,
                        ),
                        session.revision,
                    )
                workspace_rows = connection.execute(
                    "SELECT payload,payload_hash FROM pass_b_records "
                    "WHERE kind=? AND state='ACTIVE'",
                    (WorkspaceReservationRecord.KIND,),
                ).fetchall()
                for row in workspace_rows:
                    workspace = self._decode(WorkspaceReservationRecord, row)
                    if workspace.assignment_id == assignment.assignment_id:
                        self._replace(
                            connection,
                            replace(
                                workspace,
                                state=ReservationState.UNCERTAIN,
                                updated_at=recovered_at,
                                revision=workspace.revision + 1,
                            ),
                            workspace.revision,
                        )
                write_rows = connection.execute(
                    "SELECT payload,payload_hash FROM pass_b_records "
                    "WHERE kind=? AND state='ACTIVE'",
                    (WriteReservationRecord.KIND,),
                ).fetchall()
                for row in write_rows:
                    write = self._decode(WriteReservationRecord, row)
                    if write.assignment_id == assignment.assignment_id:
                        self._replace(
                            connection,
                            replace(
                                write,
                                state=ReservationState.UNCERTAIN,
                                updated_at=recovered_at,
                                revision=write.revision + 1,
                            ),
                            write.revision,
                        )
                connection.execute(
                    "UPDATE pass_b_launch_claims "
                    "SET state='UNCERTAIN',updated_at=? WHERE attempt_id=?",
                    (recovered_at, attempt.attempt_id),
                )
                connection.execute(
                    "UPDATE pass_b_workspace_claims SET state='UNCERTAIN' "
                    "WHERE assignment_id=? AND state='ACTIVE'",
                    (assignment.assignment_id,),
                )
                connection.execute(
                    "UPDATE pass_b_write_claims SET state='UNCERTAIN' "
                    "WHERE assignment_id=? AND state='ACTIVE'",
                    (assignment.assignment_id,),
                )
                result["uncertain"] += 1
        return result

    def usage_reservations(
        self, assignment_id: str
    ) -> builtins.list[dict[str, Any]]:
        with self.store.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM pass_b_usage_reservations "
                "WHERE assignment_id=? ORDER BY reserved_at",
                (assignment_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def launch_claim(self, attempt_id: str) -> dict[str, Any]:
        with self.store.connect() as connection:
            row = connection.execute(
                "SELECT * FROM pass_b_launch_claims WHERE attempt_id=?",
                (attempt_id,),
            ).fetchone()
        if row is None:
            raise KeyError(f"launch claim not found: {attempt_id}")
        return dict(row)

    def _active_workspace(
        self, connection: sqlite3.Connection, assignment_id: str
    ) -> WorkspaceReservationRecord:
        rows = connection.execute(
            "SELECT r.payload,r.payload_hash FROM pass_b_workspace_claims AS c "
            "JOIN pass_b_records AS r "
            "ON r.kind=? AND r.id=c.reservation_id "
            "WHERE c.assignment_id=? AND c.state='ACTIVE'",
            (WorkspaceReservationRecord.KIND, assignment_id),
        ).fetchall()
        if len(rows) != 1:
            raise PermissionError("assignment needs one active workspace")
        return self._decode(WorkspaceReservationRecord, rows[0])

    def _consume_usage(
        self,
        connection: sqlite3.Connection,
        assignment_id: str,
        completed_at: str,
    ) -> None:
        row = connection.execute(
            "SELECT reservation_id,pool_id,amount FROM pass_b_usage_reservations "
            "WHERE assignment_id=? AND state='ACTIVE'",
            (assignment_id,),
        ).fetchone()
        if row is None:
            return
        pool = self._get(connection, UsagePoolRecord, str(row["pool_id"]))
        amount = float(row["amount"])
        updated = replace(
            pool,
            reserved=max(0.0, pool.reserved - amount),
            consumed=pool.consumed + amount,
            updated_at=completed_at,
            last_observed_at=completed_at,
            revision=pool.revision + 1,
        )
        self._replace(connection, updated, pool.revision)
        connection.execute(
            "UPDATE pass_b_usage_reservations "
            "SET state='CONSUMED',updated_at=? WHERE reservation_id=?",
            (completed_at, str(row["reservation_id"])),
        )

    def _insert(
        self, connection: sqlite3.Connection, record: PassBRecord
    ) -> None:
        payload = record.to_dict()
        serialized, digest = _serialize(payload)
        created_at = str(payload.get("created_at") or payload["updated_at"])
        updated_at = str(payload.get("updated_at") or created_at)
        project_id = payload.get("project_id")
        state = str(payload.get("state") or "")
        revision = int(payload["revision"])
        try:
            connection.execute(
                "INSERT INTO pass_b_records("
                "kind,id,project_id,state,revision,created_at,updated_at,"
                "payload,payload_hash) VALUES(?,?,?,?,?,?,?,?,?)",
                (
                    record.KIND,
                    record.record_id,
                    project_id,
                    state,
                    revision,
                    created_at,
                    updated_at,
                    serialized,
                    digest,
                ),
            )
        except sqlite3.IntegrityError as error:
            raise PermissionError(
                f"durable {record.KIND} identity already exists"
            ) from error

    def _replace(
        self,
        connection: sqlite3.Connection,
        record: PassBRecord,
        expected_revision: int,
    ) -> None:
        if record.to_dict()["revision"] != expected_revision + 1:
            raise ValueError("replacement revision must advance exactly once")
        current = connection.execute(
            "SELECT payload_hash,revision FROM pass_b_records "
            "WHERE kind=? AND id=?",
            (record.KIND, record.record_id),
        ).fetchone()
        if current is None:
            raise KeyError(f"{record.KIND} not found: {record.record_id}")
        if int(current["revision"]) != expected_revision:
            raise PermissionError("durable record changed concurrently")
        payload = record.to_dict()
        serialized, digest = _serialize(payload)
        state = str(payload.get("state") or "")
        updated_at = str(
            payload.get("updated_at")
            or payload.get("resumed_at")
            or payload.get("resolved_at")
            or payload.get("created_at")
        )
        cursor = connection.execute(
            "UPDATE pass_b_records SET state=?,revision=?,updated_at=?,"
            "payload=?,payload_hash=? "
            "WHERE kind=? AND id=? AND revision=? AND payload_hash=?",
            (
                state,
                expected_revision + 1,
                updated_at,
                serialized,
                digest,
                record.KIND,
                record.record_id,
                expected_revision,
                str(current["payload_hash"]),
            ),
        )
        if cursor.rowcount != 1:
            raise PermissionError("durable record CAS was rejected")

    def _get(
        self, connection: sqlite3.Connection, record_type: type[R], record_id: str
    ) -> R:
        row = connection.execute(
            "SELECT payload,payload_hash FROM pass_b_records "
            "WHERE kind=? AND id=?",
            (record_type.KIND, record_id),
        ).fetchone()
        if row is None:
            raise KeyError(f"{record_type.KIND} not found: {record_id}")
        return self._decode(record_type, row)

    def _active_writes(
        self,
        connection: sqlite3.Connection,
        workspace_reservation_id: str,
    ) -> builtins.list[WriteReservationRecord]:
        rows = connection.execute(
            "SELECT payload,payload_hash FROM pass_b_records "
            "WHERE kind=? AND state='ACTIVE'",
            (WriteReservationRecord.KIND,),
        ).fetchall()
        return [
            record
            for row in rows
            if (
                record := self._decode(WriteReservationRecord, row)
            ).workspace_reservation_id
            == workspace_reservation_id
        ]

    @staticmethod
    def _decode(record_type: type[R], row: sqlite3.Row) -> R:
        serialized = str(row["payload"])
        if hashlib.sha256(serialized.encode("utf-8")).hexdigest() != str(
            row["payload_hash"]
        ):
            raise RuntimeError("Pass B durable record failed integrity validation")
        value = json.loads(serialized)
        if not isinstance(value, dict):
            raise RuntimeError("Pass B durable record is not an object")
        return record_type.from_dict(cast(dict[str, Any], value))


_PROTECTED_TREE_FRAGMENTS = (
    (".ai-workflow", "pilot-invocations"),
    (".ai-workflow", "pw"),
)


def validate_protected_workspace_tree(
    path: Path, *, require_exists: bool = True
) -> Path:
    """Return one safe canonical workspace tree or fail conservatively."""
    try:
        resolved = path.resolve(strict=require_exists)
    except (OSError, RuntimeError) as error:
        raise PermissionError(
            "workspace path identity cannot be safely resolved"
        ) from error
    if require_exists and not resolved.is_dir():
        raise ValueError("workspace path must be an existing directory")
    if _is_protected_tree_path(resolved):
        raise PermissionError(
            "workspace overlaps protected Keeper pilot evidence "
            "or workflow state"
        )
    _reject_primary_repository(resolved)
    if not require_exists and not os.path.lexists(resolved):
        return resolved
    if not resolved.is_dir():
        raise ValueError("workspace path must be a directory")

    visited: set[str] = set()
    pending = [resolved]
    while pending:
        current = pending.pop()
        try:
            canonical_current = current.resolve(strict=True)
        except (OSError, RuntimeError) as error:
            raise PermissionError(
                "workspace tree contains an unresolved path identity"
            ) from error
        key = _path_key(canonical_current)
        if key in visited:
            continue
        visited.add(key)
        if _is_protected_tree_path(canonical_current):
            raise PermissionError(
                "workspace contains protected Keeper pilot evidence "
                "or workflow state"
            )
        try:
            with os.scandir(canonical_current) as entries:
                for entry in entries:
                    candidate = Path(entry.path)
                    try:
                        entry_stat = entry.stat(follow_symlinks=False)
                        is_reparse = bool(
                            getattr(entry_stat, "st_file_attributes", 0)
                            & getattr(os, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
                        )
                        is_alias = entry.is_symlink() or is_reparse
                        is_directory = entry.is_dir(follow_symlinks=False)
                        if not is_directory and not is_alias:
                            continue
                        canonical_candidate = candidate.resolve(strict=True)
                    except (OSError, RuntimeError) as error:
                        raise PermissionError(
                            "workspace tree contains an unresolved alias"
                        ) from error
                    if _is_protected_tree_path(canonical_candidate):
                        raise PermissionError(
                            "workspace contains protected Keeper pilot evidence "
                            "or workflow state"
                        )
                    if (
                        entry.name.casefold() == ".git"
                        and canonical_candidate.is_dir()
                    ):
                        raise PermissionError(
                            "primary repository cannot be a Keeper workspace"
                        )
                    if is_alias:
                        try:
                            canonical_candidate.relative_to(resolved)
                        except ValueError as error:
                            raise PermissionError(
                                "workspace alias escapes its canonical tree"
                            ) from error
                    if canonical_candidate.is_dir():
                        pending.append(canonical_candidate)
        except PermissionError:
            raise
        except OSError as error:
            raise PermissionError(
                "workspace tree cannot be safely inspected"
            ) from error
    return resolved


def canonical_workspace_path(path: Path) -> str:
    return _path_key(validate_protected_workspace_tree(path))


def canonical_evidence_reference_path(path: Path) -> str:
    resolved = path.resolve(strict=True)
    parts = tuple(item.casefold() for item in resolved.parts)
    if _contains_parts(parts, (".ai-workflow", "pw")):
        raise PermissionError("Keeper browser evidence reference is protected")
    if not _contains_parts(
        parts, (".ai-workflow", "pilot-invocations")
    ):
        raise PermissionError(
            "only explicit pilot evidence uses this read-only reference path"
        )
    return _path_key(resolved)


def canonical_scope(workspace_path: str, scope: str) -> str:
    normalized = scope.replace("\\", "/").strip("/")
    if not normalized or normalized == "." or ".." in normalized.split("/"):
        raise ValueError("write scope must be a contained relative path")
    root = validate_protected_workspace_tree(Path(workspace_path))
    candidate = (root / normalized).resolve(strict=False)
    try:
        candidate.relative_to(root)
    except ValueError as error:
        raise PermissionError(
            "write scope resolves outside the assigned workspace"
        ) from error
    if _is_protected_tree_path(candidate):
        raise PermissionError("write scope overlaps protected Keeper state")
    return _path_key(candidate)


def _path_key(path: Path) -> str:
    return str(path).replace("\\", "/").casefold()


def _contains_parts(
    parts: tuple[str, ...], fragment: tuple[str, ...]
) -> bool:
    return any(
        parts[index : index + len(fragment)] == fragment
        for index in range(max(0, len(parts) - len(fragment) + 1))
    )


def is_pilot_evidence_path(path: Path) -> bool:
    resolved = path.resolve(strict=False)
    parts = tuple(item.casefold() for item in resolved.parts)
    return _contains_parts(
        parts, (".ai-workflow", "pilot-invocations")
    )


def contains_pilot_evidence(path: Path) -> bool:
    resolved = path.resolve(strict=False)
    direct = resolved / ".ai-workflow" / "pilot-invocations"
    if direct.exists():
        return True
    if not resolved.is_dir():
        return False
    try:
        return any(
            candidate.exists()
            for candidate in resolved.glob(
                "**/.ai-workflow/pilot-invocations"
            )
        )
    except OSError:
        return True


def _is_protected_tree_path(path: Path) -> bool:
    parts = tuple(item.casefold() for item in path.parts)
    return any(
        _contains_parts(parts, fragment)
        for fragment in _PROTECTED_TREE_FRAGMENTS
    )


def _reject_primary_repository(path: Path) -> None:
    for ancestor in (path, *path.parents):
        marker = ancestor / ".git"
        try:
            if marker.is_dir():
                raise PermissionError(
                    "primary repository cannot be a Keeper workspace"
                )
            if marker.is_file():
                return
        except OSError as error:
            raise PermissionError(
                "repository identity cannot be safely inspected"
            ) from error


def _validate_workflow_work_item(
    workflow: WorkflowRecord, work_item: WorkItemRecord
) -> None:
    if (
        workflow.state != WorkflowState.ACTIVE
        or work_item.state not in {
            WorkItemState.PROPOSED,
            WorkItemState.READY,
            WorkItemState.ASSIGNED,
            WorkItemState.ACTIVE,
            WorkItemState.REVIEW_REQUIRED,
            WorkItemState.REPAIR_REQUIRED,
        }
        or work_item.workflow_id != workflow.workflow_id
        or work_item.project_id != workflow.project_id
        or work_item.charter_id != workflow.charter_id
        or work_item.charter_revision != workflow.charter_revision
    ):
        raise PermissionError(
            "work item is not bound to an active durable workflow"
        )


def _validate_assignment_binding(
    workflow: WorkflowRecord,
    work_item: WorkItemRecord,
    assignment: AssignmentRecord,
) -> None:
    _validate_workflow_work_item(workflow, work_item)
    if (
        assignment.workflow_id != workflow.workflow_id
        or assignment.work_item_id != work_item.work_item_id
        or assignment.project_id != workflow.project_id
        or assignment.charter_id != workflow.charter_id
        or assignment.charter_revision != workflow.charter_revision
        or assignment.authority_envelope_digest
        != workflow.authority_envelope_digest
        or (
            work_item.required_roles
            and assignment.role not in work_item.required_roles
            and not (
                assignment.role == AssignmentRole.REVIEWER
                and assignment.read_only
                and bool(
                    assignment.usage_policy.get("review_of_assignment_id")
                )
            )
        )
    ):
        raise PermissionError(
            "assignment binding mismatch: durable workflow or work item"
        )

def _path_overlap(left: str, right: str) -> bool:
    return (
        left == right
        or left.startswith(right.rstrip("/") + "/")
        or right.startswith(left.rstrip("/") + "/")
    )


def _scope_overlap(left: str, right: str) -> bool:
    return (
        left == right
        or left.startswith(right.rstrip("/") + "/")
        or right.startswith(left.rstrip("/") + "/")
    )


def _serialize(payload: dict[str, Any]) -> tuple[str, str]:
    serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return serialized, hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _parse_time(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        raise ValueError("timestamp must be timezone aware")
    return parsed


def _now() -> str:
    from datetime import UTC

    return datetime.now(UTC).isoformat()
