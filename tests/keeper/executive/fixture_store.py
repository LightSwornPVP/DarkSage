from __future__ import annotations

import hashlib
import json

from keeper.app.storage import KeeperStore


def replace_executive_fixture(
    store: KeeperStore,
    table: str,
    identifier: str,
    payload: dict[str, object],
) -> None:
    """Test-only corruption fixture; never imported by production code."""
    serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(serialized.encode("utf-8")).hexdigest()
    with store.connect() as connection:
        cursor = connection.execute(
            f'UPDATE "{table}" SET payload=?,payload_hash=? WHERE id=?',
            (serialized, digest, identifier),
        )
        if cursor.rowcount != 1:
            raise AssertionError("fixture target does not exist")


def delete_executive_fixture(
    store: KeeperStore,
    table: str,
    identifier: str,
) -> None:
    """Test-only deletion fixture; never imported by production code."""
    with store.connect() as connection:
        connection.execute(
            f'DELETE FROM "{table}" WHERE id=?',
            (identifier,),
        )
