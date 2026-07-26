from __future__ import annotations

import json
import shutil
import sqlite3
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterator


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
