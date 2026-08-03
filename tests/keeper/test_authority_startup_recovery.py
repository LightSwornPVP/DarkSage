from __future__ import annotations

import json
import sqlite3
import threading
from pathlib import Path
from typing import Any

import pytest

from keeper.authority_service import service_install, service_main
from keeper.authority_service.core import AuthorityServiceCore, SERVICE_VERSION
from keeper.authority_service.protocol import PROTOCOL_VERSION
from keeper.authority_service.store import SERVICE_SCHEMA_VERSION
from keeper.provider_host import signing


SID = "S-1-5-21-1000"


def test_recovery_release_keeps_protocol_and_schema_stable() -> None:
    assert SERVICE_VERSION == "1.7.3"
    assert PROTOCOL_VERSION == 7
    assert SERVICE_SCHEMA_VERSION == 6


def test_provider_host_identity_failure_leaves_core_available_and_fails_closed(
    tmp_path: Path,
) -> None:
    core = AuthorityServiceCore(tmp_path / "authority")

    def fail() -> None:
        raise OSError(5, "synthetic machine CNG access denied")

    worker = service_main._start_provider_host_initialization(core, fail)
    worker.join(timeout=5)

    assert not worker.is_alive()
    diagnostics = core._diagnostics({}, SID)
    assert diagnostics["service_version"] == "1.7.3"
    assert diagnostics["schema_version"] == 6
    assert diagnostics["provider_host"] == {
        "installed": False,
        "online": False,
        "state": "UNAVAILABLE",
        "protocol_compatible": False,
        "provider_state": "UNAVAILABLE",
        "failure_reason": "IDENTITY_INITIALIZATION_FAILED",
        "qualification_reconciliation_required": False,
        "qualification_reconciliation_count": 0,
        "qualification_reconciliation_registration_ids": [],
    }
    with pytest.raises(PermissionError, match="not configured"):
        core._provider_host_enrollment_status({}, SID)


def test_service_reports_running_before_provider_host_cng_worker(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = tmp_path / "service.json"
    config.write_text("{}", encoding="utf-8")
    statuses: list[int] = []
    initialized = threading.Event()
    failed = threading.Event()

    class Core:
        def begin_provider_host_initialization(self) -> None:
            assert statuses[-1] == service_main._SERVICE_RUNNING

        def fail_provider_host_initialization(self, reason: str) -> None:
            assert reason == "IDENTITY_INITIALIZATION_FAILED"
            failed.set()

    class Server:
        core = Core()

        def serve_forever(self) -> None:
            assert initialized.wait(5)
            assert failed.wait(5)

    class Api:
        def RegisterServiceCtrlHandlerExW(self, *_: object) -> int:
            return 1

    def initialize() -> None:
        assert threading.current_thread().name == (
            "keeper-authority-provider-host-init"
        )
        assert statuses[-1] == service_main._SERVICE_RUNNING
        initialized.set()
        raise OSError(5, "synthetic machine CNG access denied")

    monkeypatch.setattr(service_main, "_advapi32", lambda: Api())
    monkeypatch.setattr(
        service_main,
        "_build_service_server",
        lambda _: (Server(), initialize),
    )
    service = service_main.AuthorityWindowsService(config)
    monkeypatch.setattr(
        service,
        "_set_status",
        lambda state, **_: statuses.append(state),
    )

    service._service_main(0, None)

    assert statuses == [
        service_main._SERVICE_START_PENDING,
        service_main._SERVICE_RUNNING,
        service_main._SERVICE_STOPPED,
    ]


def test_schema_five_upgrade_preserves_counts_and_service_key(
    tmp_path: Path,
) -> None:
    root = tmp_path / "authority"
    first = AuthorityServiceCore(root)
    for index in range(8):
        registration_id = f"registration-{index}"
        first.store.insert(
            "registrations",
            registration_id,
            "SYNTHETIC",
            {"synthetic": True, "index": index},
        )
        first.store.insert(
            "qualifications",
            f"qualification-{index}",
            "SYNTHETIC",
            {"synthetic": True, "index": index},
            registration_id=registration_id,
            challenge=f"qualification-challenge-{index}",
        )
    for index in range(2):
        first.store.insert(
            "attempts",
            f"attempt-{index}",
            "SYNTHETIC",
            {
                "synthetic": True,
                "index": index,
                "project_id": f"project-{index}",
            },
            registration_id=f"registration-{index}",
            challenge=f"attempt-challenge-{index}",
            run_id=f"run-{index}",
            attempt_number=1,
        )
    key_id = first.keys.current_key_id
    with sqlite3.connect(root / "authority.db") as connection:
        connection.execute(
            "UPDATE service_meta SET value='5' WHERE key='schema_version'"
        )
        connection.commit()

    recovered = AuthorityServiceCore(root)
    assert recovered.keys.current_key_id == key_id
    assert len(recovered.store.list_records("registrations")) == 8
    assert len(recovered.store.list_records("qualifications")) == 8
    assert len(recovered.store.list_records("attempts")) == 2
    assert recovered.store.schema_identity()["schema_version"] == 6


def test_machine_key_policy_is_exact_and_restricted_first() -> None:
    access = ("S-1-5-18", "S-1-5-32-544", "S-1-5-80-123")
    assert signing._machine_key_security_sddl(access) == (
        "O:BAD:P(D;;GA;;;S-1-5-12)"
        "(A;;GA;;;S-1-5-18)"
        "(A;;GA;;;S-1-5-32-544)"
        "(A;;GA;;;S-1-5-80-123)"
    )
    with pytest.raises(ValueError, match="policy"):
        signing._machine_key_security_sddl(())
    with pytest.raises(ValueError, match="policy"):
        signing._machine_key_security_sddl(("S-1-5-18", "S-1-5-18"))


def test_runtime_machine_key_open_never_creates_missing_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []
    monkeypatch.setattr(
        signing, "_validate_machine_storage_provider", lambda *_: None
    )

    class Api:
        def NCryptOpenStorageProvider(self, *_: object) -> int:
            calls.append("open-provider")
            return 0

        def NCryptOpenKey(self, *_: object) -> int:
            calls.append("open-key")
            return 0x80090016

        def NCryptCreatePersistedKey(self, *_: object) -> int:
            calls.append("create-key")
            return 0

        def NCryptFreeObject(self, *_: object) -> int:
            calls.append("free")
            return 0

    with pytest.raises(PermissionError, match="not provisioned"):
        signing._open_key(
            Api(),
            "DarkSage.KeeperAuthority.ProviderHost.v1",
            machine_key=True,
            owner_sid=None,
            create_if_missing=False,
        )
    assert calls == ["open-provider", "open-key", "free"]


def test_elevated_provisioning_is_durable_idempotent_and_mismatch_safe(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    persisted: list[dict[str, Any]] = []
    signer_calls: list[dict[str, object]] = []

    class Signer:
        key_id = "keeper-provider-host-rsa:synthetic"

        def __init__(self, **values: object) -> None:
            signer_calls.append(dict(values))
            assert values["identity"] == (
                "keeper-authority-provider-host:provisioned"
            )
            assert values["key_name"] == (
                service_install.PROVIDER_HOST_AUTHORITY_KEY_NAME
            )
            assert values["machine_key"] is True

        def public_configuration(self) -> dict[str, object]:
            return {
                "schema_version": 1,
                "identity": "keeper-authority-provider-host:provisioned",
                "key_id": self.key_id,
                "algorithm": "RSA-PKCS1-SHA256",
                "exponent": "AQAB",
                "modulus": "synthetic",
            }

    monkeypatch.setattr(service_install, "account_sid", lambda _: "S-1-5-80-123")
    monkeypatch.setattr(service_install, "WindowsCngEnvelopeIdentity", Signer)
    monkeypatch.setattr(
        service_install,
        "_persist_manifest",
        lambda value: persisted.append(json.loads(json.dumps(value))),
    )
    manifest: dict[str, Any] = {}

    first = service_install._provision_provider_host_authority_identity(manifest)
    second = service_install._provision_provider_host_authority_identity(manifest)

    assert first == second
    assert len(persisted) == 2
    assert signer_calls[0]["create_if_missing"] is True
    assert signer_calls[0]["machine_access_sids"] == (
        "S-1-5-18",
        "S-1-5-32-544",
        "S-1-5-80-123",
    )
    assert signer_calls[1]["create_if_missing"] is False
    assert signer_calls[1]["machine_access_sids"] == (
        "S-1-5-18",
        "S-1-5-32-544",
        "S-1-5-80-123",
    )
    manifest["provider_host_authority_identity"] = {"changed": True}
    with pytest.raises(PermissionError, match="differs"):
        service_install._provision_provider_host_authority_identity(manifest)
    assert len(signer_calls) == 2


def test_recovery_preimage_is_exclusive_hashed_and_rerun_safe(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    service_root = tmp_path / "service"
    data = service_root / "data"
    data.mkdir(parents=True)
    (data / "authority.db").write_bytes(b"synthetic-authority-state")
    (data / "keys").mkdir()
    (data / "keys" / "key-ring.json").write_text(
        '{"schema_version":1}', encoding="utf-8"
    )
    manifest_path = service_root / "audit" / "machine-artifacts.json"
    manifest_path.parent.mkdir()
    manifest_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "service_name": service_main.SERVICE_NAME,
                "installation_completed_at": "2026-08-02T00:00:00+00:00",
                "artifacts": [],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(service_install, "SERVICE_ROOT", service_root)
    monkeypatch.setattr(service_install, "MANIFEST_PATH", manifest_path)
    monkeypatch.setattr(service_install, "_require_admin", lambda: None)
    monkeypatch.setattr(
        service_install, "_require_service_stopped", lambda _: None
    )
    applied_security: list[dict[str, Any]] = []
    monkeypatch.setattr(service_install, "account_sid", lambda _: "S-1-5-80-123")
    monkeypatch.setattr(
        service_install,
        "apply_path_security",
        lambda path, policy: applied_security.append(policy),
    )
    destination = tmp_path / "preimage"

    with pytest.raises(PermissionError, match="disjoint"):
        service_install.verified_recovery_backup(data / "nested-preimage")

    denied_destination = tmp_path / "denied-preimage"
    monkeypatch.setattr(
        service_install,
        "apply_path_security",
        lambda *_: (_ for _ in ()).throw(
            PermissionError("synthetic recovery ACL rejection")
        ),
    )
    with pytest.raises(PermissionError, match="ACL rejection"):
        service_install.verified_recovery_backup(denied_destination)
    assert not denied_destination.exists()
    monkeypatch.setattr(
        service_install,
        "apply_path_security",
        lambda path, policy: applied_security.append(policy),
    )

    result = service_install.verified_recovery_backup(destination)

    assert len(applied_security) == 1
    applied_aces = applied_security[0]["aces"]
    assert isinstance(applied_aces, list)
    assert [
        item["trustee_sid"] for item in applied_aces
    ] == ["S-1-5-18", "S-1-5-32-544", "S-1-5-80-123"]
    assert len(result["tree_sha256"]) == 64
    assert Path(str(result["manifest"])).is_file()
    assert (destination / "authority.db").read_bytes() == (
        b"synthetic-authority-state"
    )
    with pytest.raises(PermissionError, match="already exists"):
        service_install.verified_recovery_backup(destination)
    persisted = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert persisted["recovery_preimages"] == [result]
    (data / "authority.db").write_bytes(b"changed-after-preimage")
    with pytest.raises(PermissionError, match="no longer matches"):
        service_install._verified_recovery_preimage(
            persisted, Path(str(result["manifest"]))
        )
