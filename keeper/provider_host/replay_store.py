from __future__ import annotations

import hashlib
import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Iterator

from keeper.provider_host.protocol import parse_utc


_ACTIVE_STATES = {"CLAIMED", "STARTED", "RUNNING", "UNCERTAIN"}
_TERMINAL_STATES = {"COMPLETED", "FAILED", "CANCELLED"}
_TRANSITIONS = {
    "CLAIMED": {"STARTED", "FAILED", "UNCERTAIN"},
    "STARTED": {"RUNNING", "FAILED", "CANCELLED", "UNCERTAIN"},
    "RUNNING": {"COMPLETED", "FAILED", "CANCELLED", "UNCERTAIN"},
    "UNCERTAIN": set(),
    "COMPLETED": set(),
    "FAILED": set(),
    "CANCELLED": set(),
}


class ProviderHostStore:
    """Durable replay, endpoint, launch, and workspace journal."""

    def __init__(self, path: Path) -> None:
        self.path = path.resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._migrate()

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path, timeout=5)
        connection.row_factory = sqlite3.Row
        try:
            connection.execute("PRAGMA foreign_keys=ON")
            connection.execute("PRAGMA journal_mode=WAL")
            yield connection
        finally:
            connection.close()

    def claim_launch(
        self,
        *,
        authority_id: str,
        nonce: str,
        sequence: int,
        issued_at: str,
        expires_at: str,
        now: datetime,
        maximum_ttl: timedelta,
        maximum_future_skew: timedelta,
        launch_id: str,
        authority_attempt_id: str,
        envelope_digest: str,
        workspace_path: str,
    ) -> None:
        observed_now = now.astimezone(UTC)
        issued = parse_utc(issued_at)
        expires = parse_utc(expires_at)
        if issued > observed_now + maximum_future_skew:
            raise PermissionError("Provider Host launch was issued in the future")
        if expires <= observed_now:
            raise PermissionError("Provider Host launch is expired")
        if expires - issued > maximum_ttl:
            raise PermissionError("Provider Host launch TTL exceeds policy")
        canonical_workspace = _canonical_workspace(workspace_path)
        with self.connect() as connection:
            try:
                connection.execute("BEGIN IMMEDIATE")
                if connection.execute(
                    "SELECT 1 FROM replay WHERE nonce = ?", (nonce,)
                ).fetchone() is not None:
                    raise PermissionError("Provider Host nonce is replayed")
                prior = connection.execute(
                    "SELECT MAX(sequence) FROM replay WHERE authority_id = ?",
                    (authority_id,),
                ).fetchone()[0]
                if prior is not None and sequence <= int(prior):
                    raise PermissionError("Provider Host sequence is stale")
                if connection.execute(
                    "SELECT 1 FROM launches WHERE launch_id = ? OR authority_attempt_id = ?",
                    (launch_id, authority_attempt_id),
                ).fetchone() is not None:
                    raise PermissionError("Provider Host launch is duplicated")
                for row in connection.execute(
                    "SELECT workspace_path FROM launches WHERE state IN "
                    "('CLAIMED','STARTED','RUNNING','UNCERTAIN')"
                ).fetchall():
                    if _paths_overlap(str(row[0]), canonical_workspace):
                        raise PermissionError("Provider Host workspace overlaps")
                connection.execute(
                    "INSERT INTO replay(authority_id,nonce,sequence,expires_at) "
                    "VALUES(?,?,?,?)",
                    (authority_id, nonce, sequence, expires_at),
                )
                connection.execute(
                    "INSERT INTO launches(launch_id,authority_attempt_id,envelope_digest,"
                    "workspace_path,state,detail,updated_at) VALUES(?,?,?,?,?,?,?)",
                    (
                        launch_id,
                        authority_attempt_id,
                        envelope_digest,
                        canonical_workspace,
                        "CLAIMED",
                        "",
                        _now(),
                    ),
                )
                connection.commit()
            except BaseException:
                connection.rollback()
                raise

    def claim_peer_message(
        self,
        *,
        channel: str,
        authority_id: str,
        nonce: str,
        sequence: int,
        issued_at: str,
        expires_at: str,
        now: datetime,
        maximum_ttl: timedelta,
        maximum_future_skew: timedelta,
    ) -> None:
        if not channel or not nonce or sequence <= 0:
            raise PermissionError("Provider Host peer message is invalid")
        observed_now = now.astimezone(UTC)
        issued = parse_utc(issued_at)
        expires = parse_utc(expires_at)
        if issued > observed_now + maximum_future_skew:
            raise PermissionError("Provider Host peer message is future-issued")
        if expires <= observed_now or expires - issued > maximum_ttl:
            raise PermissionError("Provider Host peer message lifetime is invalid")
        with self.connect() as connection:
            try:
                connection.execute("BEGIN IMMEDIATE")
                prior = connection.execute(
                    "SELECT MAX(sequence) FROM message_replay "
                    "WHERE channel=? AND authority_id=?",
                    (channel, authority_id),
                ).fetchone()[0]
                if prior is not None and sequence <= int(prior):
                    raise PermissionError("Provider Host peer message is stale")
                connection.execute(
                    "INSERT INTO message_replay(channel,authority_id,nonce,sequence,expires_at) "
                    "VALUES(?,?,?,?,?)",
                    (channel, authority_id, nonce, sequence, expires_at),
                )
                connection.commit()
            except sqlite3.IntegrityError as error:
                connection.rollback()
                raise PermissionError("Provider Host peer message is replayed") from error
            except BaseException:
                connection.rollback()
                raise

    def transition(
        self,
        launch_id: str,
        expected: str | tuple[str, ...],
        state: str,
        *,
        detail: str = "",
    ) -> None:
        expected_states = (expected,) if isinstance(expected, str) else expected
        allowed = _ACTIVE_STATES | _TERMINAL_STATES
        if state not in allowed or any(item not in allowed for item in expected_states):
            raise ValueError("Provider Host launch state is invalid")
        if any(state not in _TRANSITIONS[item] for item in expected_states):
            raise ValueError("Provider Host launch state transition is invalid")
        placeholders = ",".join("?" for _ in expected_states)
        with self.connect() as connection:
            try:
                connection.execute("BEGIN IMMEDIATE")
                result = connection.execute(
                    f"UPDATE launches SET state=?, detail=?, updated_at=? "
                    f"WHERE launch_id=? AND state IN ({placeholders})",
                    (state, detail[:500], _now(), launch_id, *expected_states),
                )
                if result.rowcount != 1:
                    raise PermissionError("Provider Host state transition rejected")
                connection.commit()
            except BaseException:
                connection.rollback()
                raise

    def recover_uncertain(self, reason: str) -> int:
        with self.connect() as connection:
            try:
                connection.execute("BEGIN IMMEDIATE")
                result = connection.execute(
                    "UPDATE launches SET state='UNCERTAIN',detail=?,updated_at=? "
                    "WHERE state IN ('CLAIMED','STARTED','RUNNING')",
                    (reason[:500], _now()),
                )
                connection.commit()
                return int(result.rowcount)
            except BaseException:
                connection.rollback()
                raise

    def set_host_state(self, state: str, detail: str = "") -> None:
        allowed = {
            "STARTING",
            "READY",
            "PREPARING",
            "CLAIMED",
            "STARTED",
            "RUNNING",
            "LOCKED",
            "DRAINING",
            "STOPPED",
            "STALE",
        }
        if state not in allowed:
            raise ValueError("Provider Host lifecycle state is invalid")
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                "INSERT INTO host_state(singleton,state,detail,updated_at) VALUES(1,?,?,?) "
                "ON CONFLICT(singleton) DO UPDATE SET state=excluded.state,"
                "detail=excluded.detail,updated_at=excluded.updated_at",
                (state, detail[:500], _now()),
            )
            connection.commit()

    def get_launch(self, launch_id: str) -> dict[str, object]:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM launches WHERE launch_id=?", (launch_id,)
            ).fetchone()
            if row is None:
                raise KeyError(launch_id)
            return dict(row)

    def list_active(self) -> list[dict[str, object]]:
        with self.connect() as connection:
            return [
                dict(row)
                for row in connection.execute(
                    "SELECT * FROM launches WHERE state IN "
                    "('CLAIMED','STARTED','RUNNING','UNCERTAIN') ORDER BY launch_id"
                ).fetchall()
            ]

    def bind_provider(self, value: dict[str, object]) -> None:
        serialized = json.dumps(
            value, sort_keys=True, separators=(",", ":"), allow_nan=False
        )
        digest = hashlib.sha256(serialized.encode("utf-8")).hexdigest()
        with self.connect() as connection:
            try:
                connection.execute("BEGIN IMMEDIATE")
                row = connection.execute(
                    "SELECT payload,payload_hash FROM provider_binding WHERE singleton=1"
                ).fetchone()
                if row is not None:
                    current = str(row["payload"])
                    if hashlib.sha256(current.encode("utf-8")).hexdigest() != row["payload_hash"]:
                        raise RuntimeError("Provider Host provider binding integrity failed")
                    if current != serialized:
                        raise PermissionError("Provider Host provider binding conflicts")
                    connection.commit()
                    return
                connection.execute(
                    "INSERT INTO provider_binding(singleton,payload,payload_hash,updated_at) "
                    "VALUES(1,?,?,?)",
                    (serialized, digest, _now()),
                )
                connection.commit()
            except BaseException:
                connection.rollback()
                raise

    def provider_binding(self) -> dict[str, object] | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT payload,payload_hash FROM provider_binding WHERE singleton=1"
            ).fetchone()
        if row is None:
            return None
        serialized = str(row["payload"])
        if hashlib.sha256(serialized.encode("utf-8")).hexdigest() != row["payload_hash"]:
            raise RuntimeError("Provider Host provider binding integrity failed")
        value = json.loads(serialized)
        if not isinstance(value, dict):
            raise RuntimeError("Provider Host provider binding is malformed")
        return value

    def _migrate(self) -> None:
        with self.connect() as connection:
            connection.executescript(
                "CREATE TABLE IF NOT EXISTS replay("
                "authority_id TEXT NOT NULL,nonce TEXT NOT NULL UNIQUE,"
                "sequence INTEGER NOT NULL,expires_at TEXT NOT NULL,"
                "PRIMARY KEY(authority_id,sequence));"
                "CREATE TABLE IF NOT EXISTS launches("
                "launch_id TEXT PRIMARY KEY,authority_attempt_id TEXT NOT NULL UNIQUE,"
                "envelope_digest TEXT NOT NULL,workspace_path TEXT NOT NULL,"
                "state TEXT NOT NULL,detail TEXT NOT NULL,updated_at TEXT NOT NULL);"
                "CREATE TABLE IF NOT EXISTS message_replay("
                "channel TEXT NOT NULL,authority_id TEXT NOT NULL,"
                "nonce TEXT NOT NULL UNIQUE,sequence INTEGER NOT NULL,"
                "expires_at TEXT NOT NULL,PRIMARY KEY(channel,authority_id,sequence));"
                "CREATE TABLE IF NOT EXISTS host_state("
                "singleton INTEGER PRIMARY KEY CHECK(singleton=1),"
                "state TEXT NOT NULL,detail TEXT NOT NULL,updated_at TEXT NOT NULL);"
                "CREATE TABLE IF NOT EXISTS metadata(key TEXT PRIMARY KEY,value TEXT NOT NULL);"
                "CREATE TABLE IF NOT EXISTS provider_binding("
                "singleton INTEGER PRIMARY KEY CHECK(singleton=1),"
                "payload TEXT NOT NULL,payload_hash TEXT NOT NULL,updated_at TEXT NOT NULL);"
            )
            row = connection.execute(
                "SELECT value FROM metadata WHERE key='schema_version'"
            ).fetchone()
            if row is None:
                connection.execute(
                    "INSERT INTO metadata(key,value) VALUES('schema_version','2')"
                )
            elif str(row[0]) == "1":
                connection.execute(
                    "UPDATE metadata SET value='2' WHERE key='schema_version'"
                )
            elif str(row[0]) != "2":
                raise RuntimeError("Provider Host store schema is incompatible")
            connection.commit()


def _canonical_workspace(value: str) -> str:
    if not value or "\x00" in value:
        raise PermissionError("Provider Host workspace is invalid")
    path = Path(value)
    if not path.is_absolute():
        raise PermissionError("Provider Host workspace is not absolute")
    try:
        resolved = path.resolve(strict=True)
    except (OSError, RuntimeError) as error:
        raise PermissionError("Provider Host workspace cannot be resolved") from error
    if os.path.normcase(os.path.abspath(value)) != os.path.normcase(str(resolved)):
        raise PermissionError("Provider Host workspace is not canonical")
    return str(resolved)


def _paths_overlap(left: str, right: str) -> bool:
    left_path = os.path.normcase(os.path.abspath(left))
    right_path = os.path.normcase(os.path.abspath(right))
    try:
        common = os.path.commonpath((left_path, right_path))
    except ValueError:
        return False
    return common in {left_path, right_path}


def _now() -> str:
    return datetime.now(UTC).isoformat()
