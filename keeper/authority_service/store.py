from __future__ import annotations

import hashlib
import json
import sqlite3
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterator


SERVICE_SCHEMA_VERSION = 4
_EXPECTED_TABLES = {
    "attempts",
    "audit_log",
    "qualifications",
    "registrations",
    "replay_guard",
    "service_meta",
    "launch_authorizations",
    "founder_capability_consumptions",
}


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
                CREATE TABLE IF NOT EXISTS launch_authorizations(
                    id TEXT PRIMARY KEY,
                    state TEXT NOT NULL,
                    generation INTEGER NOT NULL,
                    client_sid TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    payload_hash TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS founder_capability_consumptions(
                    capability_id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL,
                    approval_record_id TEXT NOT NULL,
                    approval_event_id TEXT NOT NULL,
                    founder_session_id TEXT NOT NULL,
                    challenge_id TEXT NOT NULL,
                    approval_digest TEXT NOT NULL,
                    challenge_proof_digest TEXT NOT NULL,
                    capability_digest TEXT NOT NULL UNIQUE,
                    signature_digest TEXT NOT NULL UNIQUE,
                    generation INTEGER NOT NULL,
                    authorization_id TEXT NOT NULL UNIQUE,
                    consumed_at TEXT NOT NULL,
                    UNIQUE(project_id, approval_record_id),
                    UNIQUE(project_id, approval_event_id),
                    UNIQUE(project_id, founder_session_id),
                    UNIQUE(project_id, challenge_id),
                    UNIQUE(project_id, approval_digest),
                    UNIQUE(project_id, challenge_proof_digest)
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
                    CREATE TABLE IF NOT EXISTS launch_authorizations(
                        id TEXT PRIMARY KEY,
                        state TEXT NOT NULL,
                        generation INTEGER NOT NULL,
                        client_sid TEXT NOT NULL,
                        payload TEXT NOT NULL,
                        payload_hash TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    );
                    UPDATE service_meta SET value='4' WHERE key='schema_version';
                    """
                )
            elif int(row["value"]) == 2:
                connection.executescript(
                    """
                    CREATE TABLE IF NOT EXISTS launch_authorizations(
                        id TEXT PRIMARY KEY,
                        state TEXT NOT NULL,
                        generation INTEGER NOT NULL,
                        client_sid TEXT NOT NULL,
                        payload TEXT NOT NULL,
                        payload_hash TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    );
                    UPDATE service_meta SET value='4' WHERE key='schema_version';
                    """
                )
            elif int(row["value"]) == 3:
                connection.execute(
                    "UPDATE service_meta SET value='4' WHERE key='schema_version'"
                )
            elif int(row["value"]) != SERVICE_SCHEMA_VERSION:
                raise RuntimeError("authority service schema is incompatible")
            self._backfill_founder_capability_consumptions(connection)

    @staticmethod
    def _backfill_founder_capability_consumptions(
        connection: sqlite3.Connection,
    ) -> None:
        rows = connection.execute(
            "SELECT id,generation,payload,payload_hash FROM launch_authorizations"
        ).fetchall()
        for row in rows:
            serialized = str(row["payload"])
            if hashlib.sha256(serialized.encode("utf-8")).hexdigest() != row["payload_hash"]:
                raise RuntimeError(
                    "stored launch authorization failed integrity validation"
                )
            payload = json.loads(serialized)
            if not isinstance(payload, dict):
                raise RuntimeError("stored launch authorization is malformed")
            authorization_id = str(row["id"])
            project_id = str(payload["project_id"])
            legacy = {
                "capability_id": str(
                    payload.get("founder_capability_id")
                    or f"legacy-capability:{authorization_id}"
                ),
                "project_id": project_id,
                "approval_record_id": str(payload["delegation_id"]),
                "approval_event_id": str(payload["founder_approval_event_id"]),
                "founder_session_id": str(
                    payload["founder_authenticated_session_id"]
                ),
                "challenge_id": str(
                    payload.get("founder_challenge_id")
                    or f"legacy-challenge:{authorization_id}"
                ),
                "approval_digest": str(
                    payload.get("founder_approval_digest")
                    or payload["founder_approval_event_digest"]
                ),
                "challenge_proof_digest": str(
                    payload.get("founder_challenge_proof_digest")
                    or f"legacy-proof:{authorization_id}"
                ),
                "capability_digest": str(
                    payload.get("founder_capability_digest")
                    or hashlib.sha256(
                        f"legacy-capability:{authorization_id}".encode("utf-8")
                    ).hexdigest()
                ),
                "signature_digest": str(
                    payload.get("founder_capability_signature_digest")
                    or hashlib.sha256(
                        f"legacy-signature:{authorization_id}".encode("utf-8")
                    ).hexdigest()
                ),
                "generation": int(row["generation"]),
                "authorization_id": authorization_id,
                "consumed_at": str(
                    payload.get("authorized_at") or _now()
                ),
            }
            existing = connection.execute(
                "SELECT authorization_id FROM founder_capability_consumptions "
                "WHERE authorization_id=?",
                (authorization_id,),
            ).fetchone()
            if existing is not None:
                continue
            try:
                connection.execute(
                    "INSERT INTO founder_capability_consumptions VALUES("
                    ":capability_id,:project_id,:approval_record_id,"
                    ":approval_event_id,:founder_session_id,:challenge_id,"
                    ":approval_digest,:challenge_proof_digest,"
                    ":capability_digest,:signature_digest,:generation,"
                    ":authorization_id,:consumed_at)",
                    legacy,
                )
            except sqlite3.IntegrityError as error:
                raise RuntimeError(
                    "legacy Founder approval identities are not project-unique"
                ) from error

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
                elif table == "launch_authorizations":
                    connection.execute(
                        "INSERT INTO launch_authorizations VALUES(?,?,?,?,?,?,?,?)",
                        (
                            identifier,
                            state,
                            attempt_number,
                            run_id,
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
        if table not in {
            "registrations", "qualifications", "attempts",
            "launch_authorizations",
        }:
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
        if table not in {
            "registrations", "qualifications", "attempts",
            "launch_authorizations",
        }:
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
        if table not in {
            "registrations", "qualifications", "attempts",
            "launch_authorizations",
        }:
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

    def create_launch_authorization(
        self,
        identifier: str,
        generation: int,
        client_sid: str,
        payload: dict[str, Any],
        consumption: dict[str, Any],
    ) -> dict[str, Any]:
        serialized, digest = _serialize(payload)
        timestamp = _now()
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT state,generation,client_sid,payload,payload_hash "
                "FROM launch_authorizations WHERE id=?",
                (identifier,),
            ).fetchone()
            if row is not None:
                existing_serialized = str(row["payload"])
                if (
                    hashlib.sha256(existing_serialized.encode("utf-8")).hexdigest()
                    != row["payload_hash"]
                ):
                    raise RuntimeError(
                        "stored launch authorization failed integrity validation"
                    )
                existing = json.loads(existing_serialized)
                if (
                    row["state"] == "ACTIVE"
                    and int(row["generation"]) == generation
                    and row["client_sid"] == client_sid
                    and existing == payload
                ):
                    return payload
                raise PermissionError(
                    "launch authorization generation is revoked or stale"
                )
            prior_rows = connection.execute(
                "SELECT state,generation,client_sid,payload,payload_hash "
                "FROM launch_authorizations"
            ).fetchall()
            prior: list[tuple[sqlite3.Row, dict[str, Any]]] = []
            for prior_row in prior_rows:
                prior_serialized = str(prior_row["payload"])
                if (
                    hashlib.sha256(prior_serialized.encode("utf-8")).hexdigest()
                    != prior_row["payload_hash"]
                ):
                    raise RuntimeError(
                        "stored launch authorization failed integrity validation"
                    )
                prior_payload = json.loads(prior_serialized)
                if (
                    isinstance(prior_payload, dict)
                    and prior_payload.get("project_id") == payload.get("project_id")
                ):
                    prior.append((prior_row, prior_payload))
            if prior:
                latest_row, _latest_payload = max(
                    prior, key=lambda item: int(item[0]["generation"])
                )
                if (
                    generation != int(latest_row["generation"]) + 1
                    or latest_row["state"] != "REVOKED"
                    or latest_row["client_sid"] != client_sid
                    or payload.get("revocation_epoch")
                    != int(latest_row["generation"])
                ):
                    raise PermissionError(
                        "higher launch generation requires the exact next revoked epoch"
                    )
            elif generation != 1 or payload.get("revocation_epoch") != 0:
                raise PermissionError(
                    "initial launch authorization generation must be one"
                )
            expected_consumption = {
                "capability_id", "project_id", "approval_record_id",
                "approval_event_id", "founder_session_id", "challenge_id",
                "approval_digest", "challenge_proof_digest",
                "capability_digest", "signature_digest", "generation",
                "authorization_id",
            }
            if set(consumption) != expected_consumption:
                raise PermissionError(
                    "Founder capability consumption fields are invalid"
                )
            try:
                connection.execute(
                    "INSERT INTO founder_capability_consumptions VALUES("
                    ":capability_id,:project_id,:approval_record_id,"
                    ":approval_event_id,:founder_session_id,:challenge_id,"
                    ":approval_digest,:challenge_proof_digest,"
                    ":capability_digest,:signature_digest,:generation,"
                    ":authorization_id,:consumed_at)",
                    {**consumption, "consumed_at": timestamp},
                )
                connection.execute(
                    "INSERT INTO launch_authorizations VALUES(?,?,?,?,?,?,?,?)",
                    (
                        identifier, "ACTIVE", generation, client_sid,
                        serialized, digest, timestamp, timestamp,
                    ),
                )
            except sqlite3.IntegrityError as error:
                raise PermissionError(
                    "Founder capability or approval identity was already used"
                ) from error
        return payload

    def revoke_launch_authorization(
        self,
        identifier: str,
        generation: int,
        client_sid: str,
        payload: dict[str, Any],
    ) -> tuple[str, ...]:
        serialized, digest = _serialize(payload)
        timestamp = _now()
        canceled: list[str] = []
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            cursor = connection.execute(
                "UPDATE launch_authorizations SET state='REVOKED',payload=?,"
                "payload_hash=?,updated_at=? WHERE id=? AND state='ACTIVE' "
                "AND generation=? AND client_sid=?",
                (
                    serialized, digest, timestamp, identifier, generation,
                    client_sid,
                ),
            )
            if cursor.rowcount != 1:
                raise PermissionError("launch authorization revocation is stale")
            rows = connection.execute(
                "SELECT id,payload,payload_hash FROM attempts "
                "WHERE state IN ('RESERVED','LAUNCH_CLAIMED')"
            ).fetchall()
            for row in rows:
                attempt = json.loads(str(row["payload"]))
                if (
                    isinstance(attempt, dict)
                    and attempt.get("launch_authorization_id") == identifier
                    and attempt.get("authorization_generation") == generation
                ):
                    connection.execute(
                        "UPDATE attempts SET state='CANCELLED',updated_at=? "
                        "WHERE id=? AND payload_hash=?",
                        (timestamp, row["id"], row["payload_hash"]),
                    )
                    canceled.append(str(row["id"]))
        return tuple(canceled)

    def claim_attempt_with_launch_authority(
        self,
        attempt_id: str,
        authorization_id: str,
        generation: int,
        client_sid: str,
        claim: dict[str, Any],
    ) -> None:
        serialized, digest = _serialize(claim)
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            authorization = connection.execute(
                "SELECT state,generation,client_sid,payload FROM "
                "launch_authorizations WHERE id=?",
                (authorization_id,),
            ).fetchone()
            if (
                authorization is None
                or authorization["state"] != "ACTIVE"
                or int(authorization["generation"]) != generation
                or authorization["client_sid"] != client_sid
            ):
                raise PermissionError(
                    "authoritative launch generation is revoked or stale"
                )
            authorization_payload = json.loads(str(authorization["payload"]))
            if datetime.fromisoformat(
                str(authorization_payload["expires_at"])
            ) <= datetime.now(UTC):
                raise PermissionError("authoritative launch lease expired")
            cursor = connection.execute(
                "UPDATE attempts SET state='LAUNCH_CLAIMED',payload=?,"
                "payload_hash=?,updated_at=? WHERE id=? AND state='RESERVED'",
                (serialized, digest, _now(), attempt_id),
            )
            if cursor.rowcount != 1:
                raise PermissionError("provider launch is not reserved")

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

    def schema_identity(self) -> dict[str, Any]:
        if not self.path.is_file():
            raise FileNotFoundError("authority database is unavailable")
        connection = sqlite3.connect(
            f"{self.path.resolve().as_uri()}?mode=ro",
            uri=True,
            timeout=30,
        )
        connection.row_factory = sqlite3.Row
        try:
            row = connection.execute(
                "SELECT value FROM service_meta WHERE key='schema_version'"
            ).fetchone()
            if row is None:
                raise RuntimeError("authority database schema version is missing")
            version = int(row["value"])
            definitions = [
                {
                    "type": str(item["type"]),
                    "name": str(item["name"]),
                    "table": str(item["tbl_name"]),
                    "sql": " ".join(str(item["sql"]).split()),
                }
                for item in connection.execute(
                    "SELECT type,name,tbl_name,sql FROM sqlite_master "
                    "WHERE sql IS NOT NULL ORDER BY type,name"
                ).fetchall()
            ]
            tables = {
                str(item["name"])
                for item in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
                if not str(item["name"]).startswith("sqlite_")
            }
            journal_mode = str(
                connection.execute("PRAGMA journal_mode").fetchone()[0]
            ).casefold()
        finally:
            connection.close()
        serialized = json.dumps(
            definitions, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        return {
            "schema_version": version,
            "schema_sha256": hashlib.sha256(serialized).hexdigest(),
            "journal_mode": journal_mode,
            "table_names_sha256": hashlib.sha256(
                json.dumps(sorted(tables), separators=(",", ":")).encode(
                    "utf-8"
                )
            ).hexdigest(),
            "schema_matches_expected": (
                version == SERVICE_SCHEMA_VERSION
                and tables == _EXPECTED_TABLES
                and journal_mode == "wal"
            ),
        }

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
