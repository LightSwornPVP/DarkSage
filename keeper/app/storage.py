from __future__ import annotations

import json
import shutil
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable, Iterator


SCHEMA_VERSION = 1
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
        try:
            yield connection
            connection.commit()
        except BaseException:
            connection.rollback()
            raise
        finally:
            connection.close()

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
            connection.execute(
                "CREATE TABLE IF NOT EXISTS reroute_reservations ("
                "authorization_id TEXT PRIMARY KEY, run_id TEXT NOT NULL, "
                "task_id TEXT NOT NULL, stage_id TEXT NOT NULL, "
                "source_attempt_id TEXT NOT NULL, destination_attempt INTEGER NOT NULL, "
                "routing_from TEXT NOT NULL, routing_to TEXT NOT NULL, "
                "consumer_id TEXT NOT NULL, state TEXT NOT NULL, reserved_at TEXT NOT NULL, "
                "UNIQUE(run_id, destination_attempt))"
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
