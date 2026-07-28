from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Iterator, cast

from keeper.authority_service.client import (
    ProductionAuthorityServiceClient,
    TestAuthorityServiceClient,
)
from keeper.authority_service.protocol import PROTOCOL_VERSION
from keeper.app.database_lock import DatabaseFileLock
from keeper.app.restore import (
    RESTORE_APPROVAL_ACTION,
    RESTORE_SCHEMA_VERSION,
    ProductionRestoreAuthorization,
    RestoreRequest,
    TestRestoreAuthorization,
    TestRestoreHooks,
    restore_authorization_digest,
    restore_request_digest,
    sha256_file,
)
from keeper.executive.founder_auth import (
    ProductionFounderAuthenticator,
    TestFounderAuthenticator,
)

if TYPE_CHECKING:
    from keeper.app.storage import KeeperStore


AUTHORITY_RECONCILIATION_PURPOSE = "executive-restore-reconciliation"
AUTHORITY_RECONCILIATION_SCHEMA_VERSION = 1
TERMINAL_AUTHORITY_STATES = frozenset({"COMPLETED", "FAILED", "CANCELLED"})


def restore_production_backup(
    store: KeeperStore,
    backup: Path,
    *,
    reason: str,
    authorization: ProductionRestoreAuthorization,
    founder_authenticator: ProductionFounderAuthenticator,
    authority: ProductionAuthorityServiceClient,
) -> int:
    if (
        type(authorization) is not ProductionRestoreAuthorization
        or type(founder_authenticator) is not ProductionFounderAuthenticator
        or type(authority) is not ProductionAuthorityServiceClient
    ):
        raise TypeError("production restore requires exact production trust boundaries")
    session = founder_authenticator.verify(
        authorization.challenge, authorization.confirmation
    )
    return _restore(
        store,
        backup,
        reason=reason,
        authorization=authorization,
        founder_identity=session.principal_sid,
        authority=authority,
        hooks=None,
        production=True,
    )


def restore_test_backup(
    store: KeeperStore,
    backup: Path,
    *,
    reason: str,
    authorization: TestRestoreAuthorization,
    founder_authenticator: TestFounderAuthenticator,
    authority: TestAuthorityServiceClient,
    hooks: TestRestoreHooks | None = None,
) -> int:
    if (
        type(authorization) is not TestRestoreAuthorization
        or type(founder_authenticator) is not TestFounderAuthenticator
        or type(authority) is not TestAuthorityServiceClient
        or (hooks is not None and type(hooks) is not TestRestoreHooks)
    ):
        raise TypeError("test restore requires exact test-only trust boundaries")
    session = founder_authenticator.verify(
        authorization.challenge, authorization.confirmation
    )
    return _restore(
        store,
        backup,
        reason=reason,
        authorization=authorization,
        founder_identity=session.principal_sid,
        authority=authority,
        hooks=hooks,
        production=False,
    )


def recover_stale_restore(store: KeeperStore, operation_id: str) -> None:
    if not operation_id:
        raise ValueError("restore operation ID is required")
    with DatabaseFileLock(store.path, "exclusive", timeout_seconds=5):
        store.verify_integrity()
        with _connection(store.path) as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT operation_id,state,expected_generation "
                "FROM executive_restore_maintenance WHERE singleton=1"
            ).fetchone()
            generation = _generation(connection)
            if (
                row is None
                or row["state"] != "ACTIVE"
                or row["operation_id"] != operation_id
                or int(row["expected_generation"]) != generation
            ):
                raise PermissionError(
                    "stale restore recovery identity or generation is invalid"
                )
            connection.execute(
                "UPDATE executive_restore_maintenance "
                "SET state='FAILED',finished_at=? "
                "WHERE singleton=1 AND operation_id=? AND state='ACTIVE'",
                (_now(), operation_id),
            )


def _restore(
    store: KeeperStore,
    backup: Path,
    *,
    reason: str,
    authorization: ProductionRestoreAuthorization | TestRestoreAuthorization,
    founder_identity: str,
    authority: ProductionAuthorityServiceClient | TestAuthorityServiceClient,
    hooks: TestRestoreHooks | None,
    production: bool,
) -> int:
    source = backup.resolve()
    if source == store.path:
        raise ValueError("restore source must differ from live database")
    if not source.is_file():
        raise FileNotFoundError(source)
    request = authorization.request
    _validate_authorization_shape(
        store, source, reason, authorization, founder_identity
    )
    staged_path = store.path.with_name(
        f".{store.path.name}.{uuid.uuid4().hex}.restore"
    )
    staged = type(store)(staged_path)
    replaced = False
    maintenance_started = False
    with DatabaseFileLock(store.path, "exclusive", timeout_seconds=5):
        try:
            with _connection(store.path) as live:
                live.execute("BEGIN IMMEDIATE")
                current = _live_identity(live)
                _validate_target_identity(request, store.path, current)
                if live.execute(
                    "SELECT 1 FROM executive_restore_authorizations "
                    "WHERE operation_id=? OR authorization_digest=?",
                    (
                        request.operation_id,
                        restore_authorization_digest(authorization),
                    ),
                ).fetchone():
                    raise PermissionError("restore authorization was already consumed")
                active = live.execute(
                    "SELECT operation_id,state FROM executive_restore_maintenance "
                    "WHERE singleton=1"
                ).fetchone()
                if active is not None and active["state"] == "ACTIVE":
                    raise RuntimeError(
                        "an active or interrupted restore requires explicit recovery"
                    )
                live.execute(
                    "INSERT INTO executive_restore_maintenance("
                    "singleton,operation_id,state,source_backup_sha256,"
                    "expected_generation,started_at,finished_at"
                    ") VALUES(1,?,'ACTIVE',?,?,?,NULL) "
                    "ON CONFLICT(singleton) DO UPDATE SET "
                    "operation_id=excluded.operation_id,state='ACTIVE',"
                    "source_backup_sha256=excluded.source_backup_sha256,"
                    "expected_generation=excluded.expected_generation,"
                    "started_at=excluded.started_at,finished_at=NULL",
                    (
                        request.operation_id,
                        request.backup_sha256,
                        request.target_generation,
                        _now(),
                    ),
                )
            maintenance_started = True
            if hooks is not None and hooks.after_maintenance_acquired is not None:
                hooks.after_maintenance_acquired()

            before_hash = sha256_file(source)
            if before_hash != request.backup_sha256:
                raise PermissionError("restore backup identity changed after authorization")
            store._sqlite_backup(source, staged_path)
            if sha256_file(source) != before_hash:
                raise PermissionError("restore backup changed while it was staged")
            staged.migrate()

            diagnostics = authority.diagnostics()
            if production:
                diagnostics = cast(
                    ProductionAuthorityServiceClient, authority
                ).require_live_identity()
            first = _authority_reconciliation(authority, diagnostics, request)
            safety = _reconcile_staged(staged_path, request, first)

            if hooks is not None and hooks.before_final_generation_check is not None:
                hooks.before_final_generation_check()
            second = _authority_reconciliation(authority, diagnostics, request)
            if first["state_digest"] != second["state_digest"]:
                raise RuntimeError(
                    "Authority state changed during restore reconciliation"
                )

            with _connection(store.path) as live:
                _validate_live_boundary(live, request)

            reconciled_at = str(second["reconciled_at"])
            receipt_digest = _digest(second)
            authorization_digest = restore_authorization_digest(authorization)
            recovery_epoch = request.target_recovery_epoch + 1
            with _connection(staged_path) as connection:
                connection.execute("BEGIN IMMEDIATE")
                _validate_source_identity(connection, request)
                store._pause_projects_for_restore(connection, reconciled_at)
                reconciliation_payload = {
                    "authority_receipt": second,
                    "executive_safety": safety,
                }
                serialized = _serialized(reconciliation_payload)
                connection.execute(
                    "INSERT INTO executive_restore_reconciliations VALUES(?,?,?,?,?,?,?)",
                    (
                        request.operation_id,
                        receipt_digest,
                        second["service_key_id"],
                        second["service_key_version"],
                        reconciled_at,
                        serialized,
                        _sha256(serialized.encode("utf-8")),
                    ),
                )
                connection.execute(
                    "INSERT INTO executive_restore_authorizations VALUES(?,?,?,?)",
                    (
                        request.operation_id,
                        authorization_digest,
                        founder_identity,
                        reconciled_at,
                    ),
                )
                cursor = connection.execute(
                    "UPDATE executive_recovery_state SET "
                    "database_id=?,canonical_path=?,recovery_epoch=?,restored_at=?,"
                    "restore_reason=?,authority_reconciled_at=?,updated_at=?,"
                    "restore_operation_id=?,authority_receipt_digest=? "
                    "WHERE singleton=1",
                    (
                        request.target_database_id,
                        os.path.normcase(str(store.path.resolve())),
                        recovery_epoch,
                        reconciled_at,
                        request.reason,
                        reconciled_at,
                        reconciled_at,
                        request.operation_id,
                        receipt_digest,
                    ),
                )
                if cursor.rowcount != 1:
                    raise RuntimeError("staged recovery identity is missing")
                connection.execute(
                    "UPDATE executive_write_state SET generation=?,updated_at=? "
                    "WHERE singleton=1",
                    (request.target_generation + 1, reconciled_at),
                )
                connection.execute(
                    "INSERT INTO executive_restore_maintenance("
                    "singleton,operation_id,state,source_backup_sha256,"
                    "expected_generation,started_at,finished_at"
                    ") VALUES(1,?,'COMPLETED',?,?,?,?) "
                    "ON CONFLICT(singleton) DO UPDATE SET "
                    "operation_id=excluded.operation_id,state='COMPLETED',"
                    "source_backup_sha256=excluded.source_backup_sha256,"
                    "expected_generation=excluded.expected_generation,"
                    "started_at=excluded.started_at,finished_at=excluded.finished_at",
                    (
                        request.operation_id,
                        request.backup_sha256,
                        request.target_generation,
                        request.requested_at,
                        reconciled_at,
                    ),
                )
            staged.verify_integrity()
            if hooks is not None and hooks.before_live_replacement is not None:
                hooks.before_live_replacement()
            with _connection(store.path) as live:
                _validate_live_boundary(live, request)
            store._sqlite_backup(staged_path, store.path)
            replaced = True
            store.verify_integrity()
            return recovery_epoch
        except BaseException:
            if maintenance_started and not replaced:
                _mark_restore_failed(store.path, request.operation_id)
            raise
        finally:
            for candidate in (
                staged_path,
                Path(f"{staged_path}-wal"),
                Path(f"{staged_path}-shm"),
                staged_path.with_name(f"{staged_path.name}.keeper-lock"),
                staged_path.with_suffix(".verified"),
            ):
                candidate.unlink(missing_ok=True)


def _validate_authorization_shape(
    store: KeeperStore,
    backup: Path,
    reason: str,
    authorization: ProductionRestoreAuthorization | TestRestoreAuthorization,
    founder_identity: str,
) -> None:
    request = authorization.request
    challenge = authorization.challenge
    now = datetime.now(UTC)
    if request.backup_sha256 != sha256_file(backup):
        raise PermissionError("restore backup identity changed after authorization")
    if (
        request.schema_version != RESTORE_SCHEMA_VERSION
        or len(request.operation_id) != 32
        or request.target_canonical_path
        != os.path.normcase(str(store.path.resolve()))
        or request.reason != reason.strip()
        or not request.reason
        or tuple(sorted(set(request.project_scope))) != request.project_scope
        or datetime.fromisoformat(request.requested_at) > now
        or datetime.fromisoformat(request.expires_at) <= now
        or challenge.approval_action != RESTORE_APPROVAL_ACTION
        or challenge.charter_digest != restore_request_digest(request)
        or challenge.approval_binding != request.to_dict()
        or authorization.confirmation.principal_sid != founder_identity
    ):
        raise PermissionError("restore authorization binding is invalid or stale")


def _validate_target_identity(
    request: RestoreRequest,
    path: Path,
    current: tuple[str, int, int, str],
) -> None:
    if (
        current[0] != request.target_database_id
        or current[1] != request.target_recovery_epoch
        or current[2] != request.target_generation
        or current[3] != "PRODUCTION"
        or request.target_canonical_path
        != os.path.normcase(str(path.resolve()))
    ):
        raise PermissionError("restore target recovery identity is stale")


def _authority_reconciliation(
    authority: ProductionAuthorityServiceClient | TestAuthorityServiceClient,
    diagnostics: dict[str, Any],
    request: RestoreRequest,
) -> dict[str, Any]:
    result = authority.reconcile_executive_restore(
        restore_operation_id=request.operation_id,
        backup_sha256=request.backup_sha256,
        source_database_id=request.source_database_id,
        source_recovery_epoch=request.source_recovery_epoch,
        target_database_id=request.target_database_id,
        target_recovery_epoch=request.target_recovery_epoch,
        target_generation=request.target_generation,
        project_scope=list(request.project_scope),
    )
    receipt = result.get("reconciliation")
    fields = {
        "schema_version",
        "kind",
        "restore_operation_id",
        "backup_sha256",
        "source_database_id",
        "source_recovery_epoch",
        "target_database_id",
        "target_recovery_epoch",
        "target_generation",
        "project_scope",
        "protocol_version",
        "service_key_id",
        "service_key_version",
        "authorized_client_sid",
        "attempts",
        "launch_authorizations",
        "state_digest",
        "reconciled_at",
        "authority_schema_version",
        "authority_key_id",
        "authenticated_writer_proof",
    }
    if (
        not isinstance(receipt, dict)
        or set(receipt) != fields
        or receipt.get("schema_version")
        != AUTHORITY_RECONCILIATION_SCHEMA_VERSION
        or receipt.get("kind") != AUTHORITY_RECONCILIATION_PURPOSE
        or receipt.get("restore_operation_id") != request.operation_id
        or receipt.get("backup_sha256") != request.backup_sha256
        or receipt.get("source_database_id") != request.source_database_id
        or receipt.get("source_recovery_epoch") != request.source_recovery_epoch
        or receipt.get("target_database_id") != request.target_database_id
        or receipt.get("target_recovery_epoch") != request.target_recovery_epoch
        or receipt.get("target_generation") != request.target_generation
        or receipt.get("project_scope") != list(request.project_scope)
        or receipt.get("protocol_version") != PROTOCOL_VERSION
        or receipt.get("service_key_id") != diagnostics.get("service_key_id")
        or receipt.get("service_key_version")
        != diagnostics.get("service_key_version")
        or receipt.get("authorized_client_sid") != diagnostics.get("client_sid")
        or not isinstance(receipt.get("attempts"), list)
        or not isinstance(receipt.get("launch_authorizations"), list)
        or receipt.get("state_digest")
        != _digest(
            {
                "attempts": receipt.get("attempts"),
                "launch_authorizations": receipt.get("launch_authorizations"),
            }
        )
        or datetime.fromisoformat(str(receipt.get("reconciled_at")))
        > datetime.now(UTC)
        or not authority.verify(AUTHORITY_RECONCILIATION_PURPOSE, receipt)
    ):
        raise PermissionError("Authority restore reconciliation evidence is invalid")
    return receipt


def _reconcile_staged(
    path: Path,
    request: RestoreRequest,
    receipt: dict[str, Any],
) -> dict[str, Any]:
    checked_attempts: list[dict[str, Any]] = []
    with _connection(path) as connection:
        connection.execute("BEGIN IMMEDIATE")
        _validate_source_identity(connection, request)
        projects = _project_scope(connection)
        if not projects.issubset(set(request.project_scope)):
            raise PermissionError("restored project scope exceeds Founder authorization")
        launch_authorizations = _authority_launch_authorizations(receipt, request)
        for authority_attempt in receipt["attempts"]:
            if not isinstance(authority_attempt, dict):
                raise PermissionError("Authority attempt evidence is malformed")
            attempt_id = authority_attempt.get("id")
            service_state = authority_attempt.get("service_state")
            project_id = authority_attempt.get("project_id")
            if (
                not isinstance(attempt_id, str)
                or service_state
                not in {
                    "RESERVED",
                    "LAUNCH_CLAIMED",
                    "EXECUTION_STARTED",
                    "PAUSED",
                    "COMPLETED",
                    "FAILED",
                    "CANCELLED",
                }
                or project_id not in request.project_scope
            ):
                raise PermissionError("Authority attempt reconciliation is invalid")
            launch_authorization_id = authority_attempt.get(
                "launch_authorization_id"
            )
            launch_authorization = launch_authorizations.get(
                launch_authorization_id
            ) if isinstance(launch_authorization_id, str) else None
            if (
                launch_authorization is None
                or launch_authorization.get("project_id") != project_id
                or launch_authorization.get("authorization_generation")
                != authority_attempt.get("authorization_generation")
            ):
                raise PermissionError(
                    "Authority attempt omits its launch authorization state"
                )
            executive = _entity(connection, "executive_execution_attempts", attempt_id)
            if executive is None:
                raise PermissionError(
                    "restored Executive state omits an Authority attempt"
                )
            for field in (
                "project_id",
                "charter_id",
                "charter_revision",
                "task_id",
                "stage_id",
                "role",
                "registration_id",
                "provider_run_id",
                "provider_instance_id",
                "launch_authorization_id",
                "authorization_generation",
            ):
                if executive.get(field) != authority_attempt.get(field):
                    raise PermissionError(
                        "restored attempt is misbound to Authority evidence"
                    )
            safety = _validate_attempt_safety(
                connection, executive, authority_attempt
            )
            authority_digest = _digest(
                {
                    key: value
                    for key, value in authority_attempt.items()
                    if key != "service_state"
                }
            )
            if service_state in TERMINAL_AUTHORITY_STATES:
                current_digest = executive.get("completion_digest")
                if current_digest not in {None, authority_digest}:
                    raise PermissionError(
                        "restored completion conflicts with newer Authority truth"
                    )
                if current_digest is None:
                    updated = {
                        **executive,
                        "state": "UNCERTAIN",
                        "completion_digest": authority_digest,
                        "authority_terminal_state": service_state,
                        "authority_reconciled_at": receipt["reconciled_at"],
                        "updated_at": receipt["reconciled_at"],
                    }
                    _update_entity(
                        connection,
                        "executive_execution_attempts",
                        attempt_id,
                        updated,
                    )
                    _mark_task_uncertain(
                        connection,
                        str(authority_attempt["task_id"]),
                        attempt_id,
                        receipt["reconciled_at"],
                    )
            checked_attempts.append(
                {
                    "attempt_id": attempt_id,
                    "authority_state": service_state,
                    **safety,
                }
            )
        return {
            "attempts": checked_attempts,
            "project_scope": list(request.project_scope),
            "launch_authorization_count": len(receipt["launch_authorizations"]),
        }


def _authority_launch_authorizations(
    receipt: dict[str, Any], request: RestoreRequest
) -> dict[str, dict[str, Any]]:
    authorizations: dict[str, dict[str, Any]] = {}
    for value in receipt["launch_authorizations"]:
        if not isinstance(value, dict):
            raise PermissionError("Authority launch authorization is malformed")
        identifier = value.get("id")
        project_id = value.get("project_id")
        generation = value.get("authorization_generation")
        if (
            not isinstance(identifier, str)
            or not identifier
            or identifier in authorizations
            or project_id not in request.project_scope
            or type(generation) is not int
            or generation <= 0
            or value.get("service_state") not in {"ACTIVE", "REVOKED"}
        ):
            raise PermissionError(
                "Authority launch authorization reconciliation is invalid"
            )
        authorizations[identifier] = value
    return authorizations


def _validate_attempt_safety(
    connection: sqlite3.Connection,
    executive: dict[str, Any],
    authority: dict[str, Any],
) -> dict[str, Any]:
    approval_id = executive.get("approval_id")
    approval_state = "NOT_REQUIRED"
    if isinstance(approval_id, str):
        approval = _entity(connection, "executive_approvals", approval_id)
        if approval is None:
            raise PermissionError("restored attempt omits its approval")
        approval_state = "PRESERVED"
        if approval.get("kind") == "ONE_TIME":
            consumption = connection.execute(
                "SELECT project_id,action_id,task_id "
                "FROM executive_approval_consumptions WHERE approval_id=?",
                (approval_id,),
            ).fetchone()
            if (
                approval.get("consumed_at") is None
                or consumption is None
                or consumption["project_id"] != executive.get("project_id")
                or consumption["action_id"] != executive.get("action_id")
                or consumption["task_id"] != executive.get("task_id")
            ):
                raise PermissionError(
                    "restored one-time approval consumption is incomplete"
                )
            approval_state = "ONE_TIME_CONSUMED"

    reservation_id = executive.get("budget_reservation_id")
    budget_state = "NOT_REQUIRED"
    if isinstance(reservation_id, str):
        reservation = connection.execute(
            "SELECT project_id,approval_id,action_id,task_id,state "
            "FROM executive_budget_reservations WHERE reservation_id=?",
            (reservation_id,),
        ).fetchone()
        if (
            reservation is None
            or reservation["project_id"] != executive.get("project_id")
            or reservation["approval_id"] != approval_id
            or reservation["action_id"] != executive.get("action_id")
            or reservation["task_id"] != executive.get("task_id")
            or reservation["state"] not in {"RESERVED", "CROSSED"}
        ):
            raise PermissionError("restored budget reservation is incomplete")
        budget_state = str(reservation["state"])
        if authority.get("service_state") not in {"RESERVED", "LAUNCH_CLAIMED"}:
            connection.execute(
                "UPDATE executive_budget_reservations SET state='CROSSED' "
                "WHERE reservation_id=? AND state='RESERVED'",
                (reservation_id,),
            )
            budget_state = "CROSSED"
    return {
        "approval_state": approval_state,
        "budget_state": budget_state,
    }


def _mark_task_uncertain(
    connection: sqlite3.Connection,
    task_id: str,
    attempt_id: str,
    timestamp: str,
) -> None:
    task = _entity(connection, "executive_tasks", task_id)
    if task is None or task.get("authority_attempt_id") != attempt_id:
        raise PermissionError("restored Authority attempt has no bound task")
    if task.get("status") in {"COMPLETED", "FAILED", "CANCELED"}:
        return
    updated = {
        **task,
        "status": "UNCERTAIN",
        "revision": int(task.get("revision", 0)) + 1,
        "result_disposition": "RESTORE_AUTHORITY_RECONCILIATION_REQUIRED",
        "updated_at": timestamp,
    }
    _update_entity(connection, "executive_tasks", task_id, updated)


def _validate_source_identity(
    connection: sqlite3.Connection, request: RestoreRequest
) -> None:
    row = connection.execute(
        "SELECT database_id,recovery_epoch FROM executive_recovery_state "
        "WHERE singleton=1"
    ).fetchone()
    mode = connection.execute(
        "SELECT mode FROM executive_repository_mode WHERE singleton=1"
    ).fetchone()
    if (
        row is None
        or mode is None
        or mode["mode"] != "PRODUCTION"
        or row["database_id"] != request.source_database_id
        or int(row["recovery_epoch"]) != request.source_recovery_epoch
    ):
        raise PermissionError("staged backup recovery identity is invalid")


def _validate_live_boundary(
    connection: sqlite3.Connection, request: RestoreRequest
) -> None:
    current = _live_identity(connection)
    _validate_target_identity(request, Path(request.target_canonical_path), current)
    lease = connection.execute(
        "SELECT operation_id,state,source_backup_sha256,expected_generation "
        "FROM executive_restore_maintenance WHERE singleton=1"
    ).fetchone()
    if (
        lease is None
        or lease["operation_id"] != request.operation_id
        or lease["state"] != "ACTIVE"
        or lease["source_backup_sha256"] != request.backup_sha256
        or int(lease["expected_generation"]) != request.target_generation
    ):
        raise RuntimeError("restore maintenance lease changed before replacement")


def _live_identity(connection: sqlite3.Connection) -> tuple[str, int, int, str]:
    row = connection.execute(
        "SELECT r.database_id,r.recovery_epoch,w.generation,m.mode "
        "FROM executive_recovery_state AS r "
        "JOIN executive_write_state AS w ON w.singleton=r.singleton "
        "JOIN executive_repository_mode AS m ON m.singleton=r.singleton "
        "WHERE r.singleton=1"
    ).fetchone()
    if row is None:
        raise PermissionError("live Executive recovery identity is missing")
    return (
        str(row["database_id"]),
        int(row["recovery_epoch"]),
        int(row["generation"]),
        str(row["mode"]),
    )


def _generation(connection: sqlite3.Connection) -> int:
    row = connection.execute(
        "SELECT generation FROM executive_write_state WHERE singleton=1"
    ).fetchone()
    if row is None:
        raise PermissionError("Executive write generation is missing")
    return int(row["generation"])


def _project_scope(connection: sqlite3.Connection) -> set[str]:
    values: set[str] = set()
    for row in connection.execute(
        'SELECT payload,payload_hash FROM "executive_projects"'
    ).fetchall():
        payload = str(row["payload"])
        if _sha256(payload.encode("utf-8")) != row["payload_hash"]:
            raise RuntimeError("restored project failed integrity validation")
        value = json.loads(payload)
        if not isinstance(value, dict) or not isinstance(
            value.get("project_id"), str
        ):
            raise RuntimeError("restored project scope is invalid")
        values.add(value["project_id"])
    return values


def _entity(
    connection: sqlite3.Connection, table: str, identifier: str
) -> dict[str, Any] | None:
    row = connection.execute(
        f'SELECT payload,payload_hash FROM "{table}" WHERE id=?',
        (identifier,),
    ).fetchone()
    if row is None:
        return None
    payload = str(row["payload"])
    if _sha256(payload.encode("utf-8")) != row["payload_hash"]:
        raise RuntimeError(f"restored {table} record failed integrity validation")
    value = json.loads(payload)
    if not isinstance(value, dict):
        raise RuntimeError(f"restored {table} record is malformed")
    return value


def _update_entity(
    connection: sqlite3.Connection,
    table: str,
    identifier: str,
    value: dict[str, Any],
) -> None:
    serialized = _serialized(value)
    cursor = connection.execute(
        f'UPDATE "{table}" SET updated_at=?,payload=?,payload_hash=? WHERE id=?',
        (
            str(value.get("updated_at", _now())),
            serialized,
            _sha256(serialized.encode("utf-8")),
            identifier,
        ),
    )
    if cursor.rowcount != 1:
        raise RuntimeError(f"restored {table} update was lost")


def _mark_restore_failed(path: Path, operation_id: str) -> None:
    with _connection(path) as connection:
        connection.execute("BEGIN IMMEDIATE")
        connection.execute(
            "UPDATE executive_restore_maintenance "
            "SET state='FAILED',finished_at=? "
            "WHERE singleton=1 AND operation_id=? AND state='ACTIVE'",
            (_now(), operation_id),
        )


@contextmanager
def _connection(path: Path) -> Iterator[sqlite3.Connection]:
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys=ON")
    connection.execute("PRAGMA busy_timeout=5000")
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute("PRAGMA synchronous=FULL")
    try:
        yield connection
        connection.commit()
    except BaseException:
        connection.rollback()
        raise
    finally:
        connection.close()


def _serialized(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _digest(value: object) -> str:
    return _sha256(_serialized(value).encode("utf-8"))


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _now() -> str:
    return datetime.now(UTC).isoformat()
