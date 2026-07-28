from __future__ import annotations

import json
import os
import shutil
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable, Iterator, cast


SCHEMA_VERSION = 7
LINEAGE_VERSION = 1
LINEAGE_ZERO_HASH = '0' * 64
ENTITY_TABLES = (
    "projects",
    "worktrees",
    "tasks",
    "policies",
    "providers",
    "runs",
    "stages",
    "commands",
    "authorizations",
    "findings",
    "dispositions",
    "artifacts",
    "verification_records",
    "approvals",
    "notifications",
    "settings",
    "executive_projects",
    "project_charters",
    "executive_workflows",
    "executive_tasks",
    "executive_approvals",
    "project_memories",
    "project_decisions",
    "project_assumptions",
    "project_conversations",
    "specialist_assignments",
    "executive_execution_attempts",
    "executive_reviews",
    "executive_late_results",
    "executive_founder_approval_challenges",
    "executive_founder_approval_events",
    "executive_founder_authenticated_sessions",
    "executive_founder_authorization_capabilities",
)
EXECUTIVE_LIFECYCLE_TABLES = frozenset(
    {
        "executive_projects", "project_charters", "executive_workflows",
        "executive_tasks", "executive_approvals", "project_memories",
        "project_decisions", "project_assumptions", "project_conversations",
        "specialist_assignments", "executive_execution_attempts",
        "executive_reviews", "executive_late_results",
        "executive_founder_approval_challenges",
        "executive_founder_approval_events",
        "executive_founder_authenticated_sessions",
        "executive_founder_authorization_capabilities",
    }
)


class KeeperStore:
    def __init__(self, path: Path) -> None:
        self.path = path.resolve()

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA journal_mode=WAL")
        pending_lineage: dict[str, Any] | None = None
        try:
            self._validate_production_lineage(connection)
            initial_changes = connection.total_changes
            yield connection
            if connection.total_changes > initial_changes:
                pending_lineage = self._advance_production_lineage(connection)
            connection.commit()
            if pending_lineage is not None:
                self._append_lineage_record(pending_lineage)
        except BaseException:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _canonical_database_path(self) -> str:
        return os.path.normcase(str(self.path.resolve()))

    def _lineage_journal_path(self) -> Path:
        path_digest = _sha256(
            self._canonical_database_path().encode("utf-8")
        )
        return self.path.parent / ".keeper-lineage" / f"{path_digest}.jsonl"

    def _database_file_identity(self) -> tuple[str, str]:
        stat = self.path.stat()
        return str(int(stat.st_dev)), str(int(stat.st_ino))

    @staticmethod
    def _table_exists(connection: sqlite3.Connection, table: str) -> bool:
        return (
            connection.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
                (table,),
            ).fetchone()
            is not None
        )

    def _production_lineage_row(
        self, connection: sqlite3.Connection
    ) -> sqlite3.Row | None:
        if not self._table_exists(connection, "executive_repository_mode"):
            return None
        mode = connection.execute(
            "SELECT mode FROM executive_repository_mode WHERE singleton=1"
        ).fetchone()
        if mode is None or mode["mode"] != "PRODUCTION":
            return None
        if not self._table_exists(
            connection, "executive_repository_lineage"
        ):
            return None
        row = connection.execute(
            "SELECT database_id, epoch, previous_hash, head_hash, "
            "canonical_path, file_dev, file_ino, updated_at "
            "FROM executive_repository_lineage WHERE singleton=1"
        ).fetchone()
        if row is None:
            raise PermissionError(
                "production Executive database has no lineage binding"
            )
        return cast(sqlite3.Row | None, row)

    @staticmethod
    def _lineage_record_hash(record: dict[str, Any]) -> str:
        material = dict(record)
        material.pop("head_hash", None)
        serialized = json.dumps(
            material, sort_keys=True, separators=(",", ":")
        )
        return _sha256(serialized.encode("utf-8"))

    def _last_lineage_record(self) -> dict[str, Any]:
        journal = self._lineage_journal_path()
        try:
            with journal.open("rb") as handle:
                handle.seek(0, os.SEEK_END)
                position = handle.tell()
                if position <= 0:
                    raise PermissionError(
                        "production Executive lineage journal is empty"
                    )
                data = b""
                while position > 0 and b"\n" not in data.rstrip(b"\n"):
                    amount = min(4096, position)
                    position -= amount
                    handle.seek(position)
                    data = handle.read(amount) + data
                lines = data.splitlines()
                if not lines:
                    raise PermissionError(
                        "production Executive lineage journal is empty"
                    )
                value = json.loads(lines[-1].decode("utf-8"))
        except (FileNotFoundError, OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
            raise PermissionError(
                "production Executive lineage journal is unavailable"
            ) from error
        if not isinstance(value, dict):
            raise PermissionError(
                "production Executive lineage journal is invalid"
            )
        return value

    def _validate_lineage_record(self, record: dict[str, Any]) -> None:
        expected_fields = {
            "version", "database_id", "epoch", "previous_hash",
            "head_hash", "canonical_path", "file_dev", "file_ino",
            "recorded_at",
        }
        if (
            set(record) != expected_fields
            or record.get("version") != LINEAGE_VERSION
            or record.get("canonical_path") != self._canonical_database_path()
            or not isinstance(record.get("database_id"), str)
            or not record.get("database_id")
            or type(record.get("epoch")) is not int
            or int(record["epoch"]) <= 0
            or not isinstance(record.get("previous_hash"), str)
            or not isinstance(record.get("head_hash"), str)
            or len(str(record["previous_hash"])) != 64
            or len(str(record["head_hash"])) != 64
            or not isinstance(record.get("file_dev"), str)
            or not isinstance(record.get("file_ino"), str)
            or not isinstance(record.get("recorded_at"), str)
            or record["head_hash"] != self._lineage_record_hash(record)
        ):
            raise PermissionError(
                "production Executive lineage record is invalid"
            )

    def _validate_production_lineage(
        self, connection: sqlite3.Connection
    ) -> None:
        row = self._production_lineage_row(connection)
        if row is None:
            return
        record = self._last_lineage_record()
        self._validate_lineage_record(record)
        file_dev, file_ino = self._database_file_identity()
        if (
            record["database_id"] != row["database_id"]
            or record["epoch"] != row["epoch"]
            or record["previous_hash"] != row["previous_hash"]
            or record["head_hash"] != row["head_hash"]
            or record["canonical_path"] != row["canonical_path"]
            or record["file_dev"] != row["file_dev"]
            or record["file_ino"] != row["file_ino"]
            or record["recorded_at"] != row["updated_at"]
            or row["canonical_path"] != self._canonical_database_path()
            or str(row["file_dev"]) != file_dev
            or str(row["file_ino"]) != file_ino
        ):
            raise PermissionError(
                "production Executive database lineage changed or rolled back"
            )

    def _advance_production_lineage(
        self, connection: sqlite3.Connection
    ) -> dict[str, Any] | None:
        if not self._table_exists(connection, "executive_repository_mode"):
            return None
        mode = connection.execute(
            "SELECT mode FROM executive_repository_mode WHERE singleton=1"
        ).fetchone()
        if mode is None or mode["mode"] != "PRODUCTION":
            return None
        if not self._table_exists(
            connection, "executive_repository_lineage"
        ):
            raise PermissionError(
                "production Executive database lineage schema is unavailable"
            )
        row = connection.execute(
            "SELECT database_id, epoch, head_hash "
            "FROM executive_repository_lineage WHERE singleton=1"
        ).fetchone()
        if row is None:
            database_id = uuid.uuid4().hex
            epoch = 1
            previous_hash = LINEAGE_ZERO_HASH
        else:
            database_id = str(row["database_id"])
            epoch = int(row["epoch"]) + 1
            previous_hash = str(row["head_hash"])
        file_dev, file_ino = self._database_file_identity()
        record: dict[str, Any] = {
            "version": LINEAGE_VERSION,
            "database_id": database_id,
            "epoch": epoch,
            "previous_hash": previous_hash,
            "canonical_path": self._canonical_database_path(),
            "file_dev": file_dev,
            "file_ino": file_ino,
            "recorded_at": _now(),
        }
        record["head_hash"] = self._lineage_record_hash(record)
        connection.execute(
            "INSERT INTO executive_repository_lineage("
            "singleton,database_id,epoch,previous_hash,head_hash,"
            "canonical_path,file_dev,file_ino,updated_at) "
            "VALUES(1,?,?,?,?,?,?,?,?) "
            "ON CONFLICT(singleton) DO UPDATE SET "
            "database_id=excluded.database_id,epoch=excluded.epoch,"
            "previous_hash=excluded.previous_hash,head_hash=excluded.head_hash,"
            "canonical_path=excluded.canonical_path,file_dev=excluded.file_dev,"
            "file_ino=excluded.file_ino,updated_at=excluded.updated_at",
            (
                record["database_id"], record["epoch"],
                record["previous_hash"], record["head_hash"],
                record["canonical_path"], record["file_dev"],
                record["file_ino"], record["recorded_at"],
            ),
        )
        return record

    def _append_lineage_record(self, record: dict[str, Any]) -> None:
        self._validate_lineage_record(record)
        journal = self._lineage_journal_path()
        journal.parent.mkdir(parents=True, exist_ok=True)
        if journal.exists() and journal.stat().st_size > 0:
            prior = self._last_lineage_record()
            self._validate_lineage_record(prior)
            if (
                prior["database_id"] != record["database_id"]
                or prior["epoch"] + 1 != record["epoch"]
                or prior["head_hash"] != record["previous_hash"]
            ):
                raise PermissionError(
                    "production Executive lineage journal cannot advance"
                )
        elif record["epoch"] != 1 or record["previous_hash"] != LINEAGE_ZERO_HASH:
            raise PermissionError(
                "production Executive lineage journal cannot be recreated"
            )
        serialized = json.dumps(
            record, sort_keys=True, separators=(",", ":")
        )
        with journal.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(serialized + "\n")
            handle.flush()
            os.fsync(handle.fileno())
    def migrate(self) -> None:
        with self.connect() as connection:
            connection.execute(
                "CREATE TABLE IF NOT EXISTS schema_migrations "
                "(version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL)"
            )
            current = connection.execute(
                "SELECT COALESCE(MAX(version), 0) FROM schema_migrations"
            ).fetchone()[0]
            if current > SCHEMA_VERSION:
                raise RuntimeError("Keeper database schema is newer than this application")
            if current < 1:
                for table in ENTITY_TABLES:
                    connection.execute(
                        f'CREATE TABLE "{table}" ('
                        "id TEXT PRIMARY KEY, schema_version INTEGER NOT NULL, "
                        "created_at TEXT NOT NULL, updated_at TEXT NOT NULL, "
                        "payload TEXT NOT NULL, payload_hash TEXT NOT NULL)"
                    )
                connection.execute(
                    "INSERT INTO schema_migrations(version, applied_at) VALUES (?, ?)",
                    (1, _now()),
                )
                current = 1
            if current < 2:
                for table in ENTITY_TABLES:
                    connection.execute(
                        f'CREATE TABLE IF NOT EXISTS "{table}" ('
                        "id TEXT PRIMARY KEY, schema_version INTEGER NOT NULL, "
                        "created_at TEXT NOT NULL, updated_at TEXT NOT NULL, "
                        "payload TEXT NOT NULL, payload_hash TEXT NOT NULL)"
                    )
                connection.execute(
                    "CREATE TABLE IF NOT EXISTS executive_relationships ("
                    "relationship_id TEXT PRIMARY KEY, project_id TEXT NOT NULL, "
                    "parent_kind TEXT NOT NULL, parent_id TEXT NOT NULL, "
                    "child_kind TEXT NOT NULL, child_id TEXT NOT NULL, "
                    "created_at TEXT NOT NULL, "
                    "FOREIGN KEY(project_id) REFERENCES executive_projects(id), "
                    "UNIQUE(parent_kind, parent_id, child_kind, child_id))"
                )
                connection.execute(
                    "CREATE INDEX IF NOT EXISTS ix_executive_relationship_project "
                    "ON executive_relationships(project_id)"
                )
                connection.execute(
                    "INSERT INTO schema_migrations(version, applied_at) VALUES (?, ?)",
                    (2, _now()),
                )
            if current < 3:
                for table in ENTITY_TABLES:
                    connection.execute(
                        f'CREATE TABLE IF NOT EXISTS "{table}" ('
                        "id TEXT PRIMARY KEY, schema_version INTEGER NOT NULL, "
                        "created_at TEXT NOT NULL, updated_at TEXT NOT NULL, "
                        "payload TEXT NOT NULL, payload_hash TEXT NOT NULL)"
                    )
                connection.execute(
                    "CREATE TABLE IF NOT EXISTS executive_approval_consumptions ("
                    "approval_id TEXT PRIMARY KEY, project_id TEXT NOT NULL, "
                    "charter_id TEXT NOT NULL, charter_revision INTEGER NOT NULL, "
                    "action_id TEXT NOT NULL UNIQUE, task_id TEXT, "
                    "consumed_at TEXT NOT NULL, "
                    "FOREIGN KEY(approval_id) REFERENCES executive_approvals(id), "
                    "FOREIGN KEY(project_id) REFERENCES executive_projects(id))"
                )
                connection.execute(
                    "CREATE TABLE IF NOT EXISTS executive_budget_reservations ("
                    "reservation_id TEXT PRIMARY KEY, project_id TEXT NOT NULL, "
                    "charter_id TEXT NOT NULL, charter_revision INTEGER NOT NULL, "
                    "approval_id TEXT NOT NULL, action_id TEXT NOT NULL UNIQUE, "
                    "task_id TEXT, amount_minor INTEGER NOT NULL, "
                    "currency TEXT NOT NULL, state TEXT NOT NULL, "
                    "reserved_at TEXT NOT NULL, "
                    "FOREIGN KEY(approval_id) REFERENCES executive_approvals(id), "
                    "FOREIGN KEY(project_id) REFERENCES executive_projects(id))"
                )
                connection.execute(
                    "CREATE INDEX IF NOT EXISTS ix_executive_budget_scope "
                    "ON executive_budget_reservations("
                    "project_id, charter_id, charter_revision, currency, state)"
                )
                connection.execute(
                    "INSERT INTO schema_migrations(version, applied_at) VALUES (?, ?)",
                    (3, _now()),
                )
                current = 3
            if current < 4:
                for table in ENTITY_TABLES:
                    connection.execute(
                        f'CREATE TABLE IF NOT EXISTS "{table}" ('
                        "id TEXT PRIMARY KEY, schema_version INTEGER NOT NULL, "
                        "created_at TEXT NOT NULL, updated_at TEXT NOT NULL, "
                        "payload TEXT NOT NULL, payload_hash TEXT NOT NULL)"
                    )
                connection.execute(
                    "INSERT INTO schema_migrations(version, applied_at) VALUES (?, ?)",
                    (4, _now()),
                )
                current = 4
            if current < 5:
                for table in ENTITY_TABLES:
                    connection.execute(
                        f'CREATE TABLE IF NOT EXISTS "{table}" ('
                        "id TEXT PRIMARY KEY, schema_version INTEGER NOT NULL, "
                        "created_at TEXT NOT NULL, updated_at TEXT NOT NULL, "
                        "payload TEXT NOT NULL, payload_hash TEXT NOT NULL)"
                    )
                connection.execute(
                    "INSERT INTO schema_migrations(version, applied_at) VALUES (?, ?)",
                    (5, _now()),
                )
                current = 5
            if current < 6:
                for table in ENTITY_TABLES:
                    connection.execute(
                        f'CREATE TABLE IF NOT EXISTS "{table}" ('
                        "id TEXT PRIMARY KEY, schema_version INTEGER NOT NULL, "
                        "created_at TEXT NOT NULL, updated_at TEXT NOT NULL, "
                        "payload TEXT NOT NULL, payload_hash TEXT NOT NULL)"
                    )
                connection.execute(
                    "CREATE TABLE IF NOT EXISTS executive_repository_mode ("
                    "singleton INTEGER PRIMARY KEY CHECK(singleton=1), "
                    "mode TEXT NOT NULL CHECK(mode IN ('PRODUCTION','TEST')), "
                    "bound_at TEXT NOT NULL)"
                )
                connection.execute(
                    "INSERT INTO schema_migrations(version, applied_at) VALUES (?, ?)",
                    (6, _now()),
                )
            connection.execute(
                "CREATE TABLE IF NOT EXISTS executive_repository_mode ("
                "singleton INTEGER PRIMARY KEY CHECK(singleton=1), "
                "mode TEXT NOT NULL CHECK(mode IN ('PRODUCTION','TEST')), "
                "bound_at TEXT NOT NULL)"
            )
            if current < 7:
                connection.execute(
                    "CREATE TABLE IF NOT EXISTS executive_repository_lineage ("
                    "singleton INTEGER PRIMARY KEY CHECK(singleton=1), "
                    "database_id TEXT NOT NULL, "
                    "epoch INTEGER NOT NULL CHECK(epoch>0), "
                    "previous_hash TEXT NOT NULL, head_hash TEXT NOT NULL, "
                    "canonical_path TEXT NOT NULL, file_dev TEXT NOT NULL, "
                    "file_ino TEXT NOT NULL, updated_at TEXT NOT NULL)"
                )
                connection.execute(
                    "INSERT INTO schema_migrations(version, applied_at) "
                    "VALUES (?, ?)",
                    (7, _now()),
                )
            connection.execute(
                "CREATE TABLE IF NOT EXISTS executive_repository_lineage ("
                "singleton INTEGER PRIMARY KEY CHECK(singleton=1), "
                "database_id TEXT NOT NULL, "
                "epoch INTEGER NOT NULL CHECK(epoch>0), "
                "previous_hash TEXT NOT NULL, head_hash TEXT NOT NULL, "
                "canonical_path TEXT NOT NULL, file_dev TEXT NOT NULL, "
                "file_ino TEXT NOT NULL, updated_at TEXT NOT NULL)"
            )
            connection.execute(
                "CREATE TABLE IF NOT EXISTS reroute_reservations ("
                "authorization_id TEXT PRIMARY KEY, run_id TEXT NOT NULL, "
                "task_id TEXT NOT NULL, stage_id TEXT NOT NULL, "
                "source_attempt_id TEXT NOT NULL, "
                "destination_attempt INTEGER NOT NULL, "
                "routing_from TEXT NOT NULL, routing_to TEXT NOT NULL, "
                "consumer_id TEXT NOT NULL, state TEXT NOT NULL, "
                "reserved_at TEXT NOT NULL, "
                "UNIQUE(run_id, destination_attempt))"
            )
    def bind_executive_repository_mode(self, mode: str) -> None:
        if mode not in {"PRODUCTION", "TEST"}:
            raise ValueError("Executive repository mode is invalid")
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT mode FROM executive_repository_mode WHERE singleton=1"
            ).fetchone()
            if row is None:
                populated = any(
                    connection.execute(
                        f'SELECT 1 FROM "{table}" LIMIT 1'
                    ).fetchone()
                    is not None
                    for table in EXECUTIVE_LIFECYCLE_TABLES
                )
                if populated:
                    raise PermissionError(
                        "populated Executive database has no trusted repository mode"
                    )
                connection.execute(
                    "INSERT INTO executive_repository_mode VALUES(1,?,?)",
                    (mode, _now()),
                )
            elif row["mode"] != mode:
                raise PermissionError(
                    "Executive database is bound to a different repository mode"
                )

    def executive_repository_mode(self) -> str | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT mode FROM executive_repository_mode WHERE singleton=1"
            ).fetchone()
        return None if row is None else str(row["mode"])

    def executive_repository_binding(
        self,
    ) -> tuple[str, str, str, str, str, str, str, str]:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT m.mode, m.bound_at, l.database_id "
                "FROM executive_repository_mode AS m "
                "LEFT JOIN executive_repository_lineage AS l ON l.singleton=m.singleton "
                "WHERE m.singleton=1"
            ).fetchone()
        if row is None:
            raise PermissionError(
                "Executive database has no trusted repository mode binding"
            )
        if row["mode"] == "PRODUCTION" and not row["database_id"]:
            raise PermissionError(
                "production Executive database has no lineage identity"
            )
        database_id = str(row["database_id"] or "TEST")
        file_dev, file_ino = self._database_file_identity()
        if row["mode"] == "PRODUCTION":
            journal_stat = self._lineage_journal_path().stat()
            journal_dev = str(int(journal_stat.st_dev))
            journal_ino = str(int(journal_stat.st_ino))
        else:
            journal_dev = "TEST"
            journal_ino = "TEST"
        return (
            self._canonical_database_path(),
            str(row["mode"]),
            str(row["bound_at"]),
            database_id,
            file_dev,
            file_ino,
            journal_dev,
            journal_ino,
        )
    def consume_reroute_authorization(
        self,
        authorization_id: str,
        expected: dict[str, Any],
        *,
        consumer_id: str | None = None,
        before_commit: Callable[[], None] | None = None,
    ) -> dict[str, Any]:
        """Atomically consume an authorization and reserve its destination attempt."""
        consumer = consumer_id or uuid.uuid4().hex
        timestamp = _now()
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                'SELECT payload, payload_hash FROM "authorizations" WHERE id=?',
                (authorization_id,),
            ).fetchone()
            if row is None:
                raise PermissionError("reroute authorization is missing")
            serialized = str(row["payload"])
            if _sha256(serialized.encode("utf-8")) != row["payload_hash"]:
                raise RuntimeError("stored authorization failed integrity validation")
            authorization = json.loads(serialized)
            if not isinstance(authorization, dict):
                raise PermissionError("reroute authorization is malformed")
            try:
                expires = datetime.fromisoformat(str(authorization["expires_at"]))
            except (KeyError, TypeError, ValueError) as error:
                raise PermissionError("reroute authorization expiration is invalid") from error
            if (
                expires.tzinfo is None
                or expires <= datetime.now(UTC)
                or authorization.get("revoked_at") is not None
                or authorization.get("consumed_at") is not None
                or any(authorization.get(key) != value for key, value in expected.items())
            ):
                raise PermissionError("reroute authorization does not match this retry")
            authorization.update(
                {
                    "consumed_at": timestamp,
                    "consumer_id": consumer,
                    "consumption_state": "RESERVED",
                }
            )
            updated = json.dumps(authorization, sort_keys=True, separators=(",", ":"))
            digest = _sha256(updated.encode("utf-8"))
            cursor = connection.execute(
                'UPDATE "authorizations" SET updated_at=?, payload=?, payload_hash=? '
                "WHERE id=? AND payload_hash=?",
                (timestamp, updated, digest, authorization_id, row["payload_hash"]),
            )
            if cursor.rowcount != 1:
                raise PermissionError("reroute authorization was already consumed")
            try:
                connection.execute(
                    "INSERT INTO reroute_reservations VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        authorization_id,
                        expected["run_id"],
                        expected["task_id"],
                        expected["retry_stage"],
                        expected["source_attempt_id"],
                        expected["destination_attempt_number"],
                        expected["from_routing_digest"],
                        expected["to_routing_digest"],
                        consumer,
                        "RESERVED",
                        timestamp,
                    ),
                )
            except sqlite3.IntegrityError as error:
                raise PermissionError(
                    "reroute authorization or destination transition is already reserved"
                ) from error
            if before_commit is not None:
                before_commit()
        return authorization

    def reroute_reservation(
        self, authorization_id: str
    ) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM reroute_reservations WHERE authorization_id=?",
                (authorization_id,),
            ).fetchone()
        return dict(row) if row is not None else None

    def reroute_reservations_for_run(
        self, run_id: str
    ) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM reroute_reservations WHERE run_id=? "
                "ORDER BY destination_attempt",
                (run_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def transition_reroute_reservation(
        self,
        authorization_id: str,
        expected_state: str,
        state: str,
    ) -> None:
        with self.connect() as connection:
            cursor = connection.execute(
                "UPDATE reroute_reservations SET state=? "
                "WHERE authorization_id=? AND state=?",
                (state, authorization_id, expected_state),
            )
            if cursor.rowcount != 1:
                raise PermissionError(
                    "reroute reservation state transition was not authorized"
                )

    def upsert(self, table: str, identifier: str, payload: dict[str, Any]) -> None:
        _require_table(table)
        if table in EXECUTIVE_LIFECYCLE_TABLES:
            raise PermissionError(
                "Executive lifecycle tables require specialized repository operations"
            )
        serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        digest = _sha256(serialized.encode("utf-8"))
        timestamp = _now()
        with self.connect() as connection:
            connection.execute(
                f'INSERT INTO "{table}" '
                "(id, schema_version, created_at, updated_at, payload, payload_hash) "
                "VALUES (?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(id) DO UPDATE SET updated_at=excluded.updated_at, "
                "payload=excluded.payload, payload_hash=excluded.payload_hash",
                (identifier, SCHEMA_VERSION, timestamp, timestamp, serialized, digest),
            )

    def insert_immutable(
        self, table: str, identifier: str, payload: dict[str, Any]
    ) -> None:
        _require_table(table)
        if table in EXECUTIVE_LIFECYCLE_TABLES:
            raise PermissionError(
                "Executive lifecycle tables require specialized repository operations"
            )
        serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        digest = _sha256(serialized.encode("utf-8"))
        timestamp = _now()
        try:
            with self.connect() as connection:
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
                        digest,
                    ),
                )
        except sqlite3.IntegrityError as error:
            raise PermissionError(
                f"immutable {table} record already exists: {identifier}"
            ) from error

    def get(self, table: str, identifier: str) -> dict[str, Any] | None:
        _require_table(table)
        with self.connect() as connection:
            row = connection.execute(
                f'SELECT payload, payload_hash FROM "{table}" WHERE id=?', (identifier,)
            ).fetchone()
        if row is None:
            return None
        serialized = str(row["payload"])
        if _sha256(serialized.encode("utf-8")) != row["payload_hash"]:
            raise RuntimeError(f"stored {table} record failed integrity validation")
        value = json.loads(serialized)
        if not isinstance(value, dict):
            raise RuntimeError(f"stored {table} record is not an object")
        return value

    def list(self, table: str) -> list[dict[str, Any]]:
        _require_table(table)
        with self.connect() as connection:
            identifiers = [
                str(row[0])
                for row in connection.execute(
                    f'SELECT id FROM "{table}" ORDER BY updated_at DESC'
                ).fetchall()
            ]
        return [value for identifier in identifiers if (value := self.get(table, identifier))]

    def delete(self, table: str, identifier: str) -> None:
        _require_table(table)
        if table in EXECUTIVE_LIFECYCLE_TABLES:
            raise PermissionError(
                "Executive lifecycle tables require specialized repository operations"
            )
        with self.connect() as connection:
            connection.execute(f'DELETE FROM "{table}" WHERE id=?', (identifier,))

    def backup(self, destination: Path) -> Path:
        destination.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as source, sqlite3.connect(destination) as target:
            source.backup(target)
        return destination

    def export_json(self, destination: Path) -> Path:
        document = {
            "schema_version": SCHEMA_VERSION,
            "exported_at": _now(),
            "entities": {table: self.list(table) for table in ENTITY_TABLES},
        }
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(json.dumps(document, indent=2), encoding="utf-8")
        return destination

    def import_legacy_evidence(self, root: Path) -> int:
        imported = 0
        for path in sorted(root.glob("runs/*/run.json")):
            value = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(value, dict) and value.get("run_id"):
                value["legacy_source"] = str(path.resolve())
                self.upsert("runs", str(value["run_id"]), value)
                imported += 1
        return imported


def default_data_directory() -> Path:
    import os

    base = os.environ.get("LOCALAPPDATA")
    return (Path(base) if base else Path.home() / ".local" / "share") / "Keeper"


def safe_copy_database(source: Path, destination: Path) -> None:
    if source.resolve() == destination.resolve():
        raise ValueError("backup destination must differ from source")
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)


def _require_table(table: str) -> None:
    if table not in ENTITY_TABLES:
        raise ValueError(f"unsupported Keeper entity table: {table}")


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _sha256(value: bytes) -> str:
    import hashlib

    return hashlib.sha256(value).hexdigest()
