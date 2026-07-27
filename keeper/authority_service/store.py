from __future__ import annotations

import hashlib
import json
import sqlite3
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterator


SERVICE_SCHEMA_VERSION = 2


class AuthorityStore:
    def __init__(self, path: Path) -> None:
        self.path = path.resolve()

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
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

    def migrate(self) -> None:
        with self.connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS service_meta(
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS replay_guard(
                    request_id TEXT PRIMARY KEY,
                    operation_id TEXT NOT NULL UNIQUE,
                    nonce TEXT NOT NULL UNIQUE,
                    client_sid TEXT NOT NULL,
                    received_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS registrations(
                    id TEXT PRIMARY KEY,
                    state TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    payload_hash TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS qualifications(
                    id TEXT PRIMARY KEY,
                    registration_id TEXT NOT NULL,
                    state TEXT NOT NULL,
                    challenge TEXT NOT NULL UNIQUE,
                    payload TEXT NOT NULL,
                    payload_hash TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(registration_id) REFERENCES registrations(id)
                );
                CREATE TABLE IF NOT EXISTS attempts(
                    id TEXT PRIMARY KEY,
                    registration_id TEXT NOT NULL,
                    state TEXT NOT NULL,
                    challenge TEXT NOT NULL UNIQUE,
                    run_id TEXT NOT NULL,
                    attempt_number INTEGER NOT NULL,
                    payload TEXT NOT NULL,
                    payload_hash TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(registration_id) REFERENCES registrations(id)
                );
                CREATE TABLE IF NOT EXISTS audit_log(
                    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_id TEXT NOT NULL UNIQUE,
                    event_type TEXT NOT NULL,
                    client_sid TEXT NOT NULL,
                    object_id TEXT,
                    detail TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                """
            )
            row = connection.execute(
                "SELECT value FROM service_meta WHERE key='schema_version'"
            ).fetchone()
            if row is None:
                connection.execute(
                    "INSERT INTO service_meta(key,value) VALUES('schema_version',?)",
                    (str(SERVICE_SCHEMA_VERSION),),
                )
            elif int(row["value"]) == 1:
                connection.executescript(
                    """
                    ALTER TABLE attempts RENAME TO attempts_v1;
                    CREATE TABLE attempts(
                        id TEXT PRIMARY KEY,
                        registration_id TEXT NOT NULL,
                        state TEXT NOT NULL,
                        challenge TEXT NOT NULL UNIQUE,
                        run_id TEXT NOT NULL,
                        attempt_number INTEGER NOT NULL,
                        payload TEXT NOT NULL,
                        payload_hash TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL,
                        FOREIGN KEY(registration_id) REFERENCES registrations(id)
                    );
                    INSERT INTO attempts SELECT * FROM attempts_v1;
                    DROP TABLE attempts_v1;
                    UPDATE service_meta SET value='2' WHERE key='schema_version';
                    """
                )
            elif int(row["value"]) != SERVICE_SCHEMA_VERSION:
                raise RuntimeError("authority service schema is incompatible")

    def consume_request(
        self,
        request_id: str,
        operation_id: str,
        nonce: str,
        client_sid: str,
    ) -> None:
        try:
            with self.connect() as connection:
                connection.execute("BEGIN IMMEDIATE")
                connection.execute(
                    "INSERT INTO replay_guard VALUES(?,?,?,?,?)",
                    (request_id, operation_id, nonce, client_sid, _now()),
                )
        except sqlite3.IntegrityError as error:
            raise PermissionError("authority request replay was rejected") from error

    def insert(
        self,
        table: str,
        identifier: str,
        state: str,
        payload: dict[str, Any],
        *,
        registration_id: str | None = None,
        run_id: str | None = None,
        attempt_number: int | None = None,
        challenge: str | None = None,
    ) -> None:
        serialized, digest = _serialize(payload)
        timestamp = _now()
        try:
            with self.connect() as connection:
                connection.execute("BEGIN IMMEDIATE")
                if table == "registrations":
                    connection.execute(
                        "INSERT INTO registrations VALUES(?,?,?,?,?,?)",
                        (identifier, state, serialized, digest, timestamp, timestamp),
                    )
                elif table == "qualifications":
                    connection.execute(
                        "INSERT INTO qualifications VALUES(?,?,?,?,?,?,?,?)",
                        (
                            identifier,
                            registration_id,
                            state,
                            challenge,
                            serialized,
                            digest,
                            timestamp,
                            timestamp,
                        ),
                    )
                elif table == "attempts":
                    connection.execute(
                        "INSERT INTO attempts VALUES(?,?,?,?,?,?,?,?,?,?)",
                        (
                            identifier,
                            registration_id,
                            state,
                            challenge,
                            run_id,
                            attempt_number,
                            serialized,
                            digest,
                            timestamp,
                            timestamp,
                        ),
                    )
                else:
                    raise ValueError("unsupported authority table")
        except sqlite3.IntegrityError as error:
            raise PermissionError(
                f"authority {table} identity is already reserved"
            ) from error

    def get(self, table: str, identifier: str) -> dict[str, Any] | None:
        if table not in {"registrations", "qualifications", "attempts"}:
            raise ValueError("unsupported authority table")
        with self.connect() as connection:
            row = connection.execute(
                f"SELECT state,payload,payload_hash FROM {table} WHERE id=?",
                (identifier,),
            ).fetchone()
        if row is None:
            return None
        payload = str(row["payload"])
        if hashlib.sha256(payload.encode("utf-8")).hexdigest() != row["payload_hash"]:
            raise RuntimeError(f"authority {table} record integrity failed")
        value = json.loads(payload)
        if not isinstance(value, dict):
            raise RuntimeError(f"authority {table} record is malformed")
        return {**value, "service_state": str(row["state"])}

    def transition(
        self,
        table: str,
        identifier: str,
        expected_state: str,
        state: str,
        payload: dict[str, Any],
    ) -> None:
        if table not in {"registrations", "qualifications", "attempts"}:
            raise ValueError("unsupported authority table")
        serialized, digest = _serialize(payload)
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            cursor = connection.execute(
                f"UPDATE {table} SET state=?,payload=?,payload_hash=?,updated_at=? "
                "WHERE id=? AND state=?",
                (state, serialized, digest, _now(), identifier, expected_state),
            )
            if cursor.rowcount != 1:
                raise PermissionError(
                    f"authority {table} lifecycle transition was rejected"
                )

    def list_records(self, table: str) -> list[dict[str, Any]]:
        if table not in {"registrations", "qualifications", "attempts"}:
            raise ValueError("unsupported authority table")
        with self.connect() as connection:
            identifiers = [
                str(row["id"])
                for row in connection.execute(
                    f"SELECT id FROM {table} ORDER BY created_at"
                ).fetchall()
            ]
        return [
            value
            for identifier in identifiers
            if (value := self.get(table, identifier)) is not None
        ]

    def audit(
        self,
        event_id: str,
        event_type: str,
        client_sid: str,
        object_id: str | None,
        detail: dict[str, Any],
    ) -> None:
        safe_detail = json.dumps(
            detail, sort_keys=True, separators=(",", ":"), ensure_ascii=True
        )
        with self.connect() as connection:
            connection.execute(
                "INSERT INTO audit_log(event_id,event_type,client_sid,object_id,"
                "detail,created_at) VALUES(?,?,?,?,?,?)",
                (event_id, event_type, client_sid, object_id, safe_detail, _now()),
            )

    def backup(self, destination: Path) -> Path:
        destination.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as source, sqlite3.connect(destination) as target:
            source.backup(target)
        return destination


def _serialize(payload: dict[str, Any]) -> tuple[str, str]:
    serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return serialized, hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _now() -> str:
    return datetime.now(UTC).isoformat()
