from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Sequence

from keeper.authority_service.client import AuthorityServiceClient
from keeper.authority_service.provider_identity import (
    AUTHORITY_SERVICE_PROCESS_RIGHTS,
    PROVIDER_ACCOUNT_NAME,
    PROVIDER_ACCOUNT_RIGHTS,
    account_sid,
    account_rights,
    create_provider_account,
    generate_provider_password,
    grant_account_rights,
    grant_provider_account_rights,
    protect_provider_password,
    provider_account_sid,
    restricted_provider_identity_token,
    unprotect_provider_password,
)
from keeper.authority_service.service_main import SERVICE_NAME
from keeper.authority_service.service_package import (
    VerifiedRollbackPackage,
    build_service_package,
    verify_rollback_package,
    verify_service_package,
)
from keeper.authority_service.windows_identity import current_process_sid
from keeper.provider_host.signing import WindowsCngEnvelopeIdentity
from keeper.executive.founder_capability import (
    ProductionFounderCapabilityIssuer,
    ProductionFounderCapabilityVerifier,
)
from keeper.authority_service.windows_security import (
    apply_path_security,
    enforce_authority_security,
    exact_path_policy,
)
from keeper.recovery import atomic_write_json


INSTALL_ROOT = Path(os.environ.get("ProgramData", r"C:\ProgramData")) / "Keeper"
SERVICE_ROOT = INSTALL_ROOT / "AuthorityService"
MANIFEST_PATH = SERVICE_ROOT / "audit" / "machine-artifacts.json"
PROVIDER_CREDENTIAL_PATH = SERVICE_ROOT / "config" / "provider-identity.bin"
PROVIDER_HOST_AUTHORITY_KEY_NAME = "DarkSage.KeeperAuthority.ProviderHost.v1"


class AuthorityServiceInstaller:
    def __init__(self, source_root: Path) -> None:
        self.source_root = source_root.resolve(strict=True)

    def install(self, *, resume: bool = False) -> dict[str, Any]:
        _require_admin()
        service_exists = _service_exists()
        if resume:
            manifest = _load_incomplete_manifest()
            if service_exists and not _successful_service_create(manifest):
                raise PermissionError(
                    "KeeperAuthority service registration is not recorded "
                    "by the incomplete install"
                )
            _validate_resume_artifacts(manifest)
            source_commit = _git_head(self.source_root)
            manifest.setdefault("installation_attempts", []).append(
                {
                    "resumed_at": _now(),
                    "previous_source_commit": manifest.get("source_commit"),
                    "source_commit": source_commit,
                }
            )
            manifest["source_commit"] = source_commit
            client_sid = str(manifest["authorized_client_sid"])
        elif SERVICE_ROOT.exists() or service_exists:
            raise PermissionError(
                "KeeperAuthority already exists; use status/repair/upgrade, not install"
            )
        else:
            client_sid = current_process_sid()
            manifest = {
                "schema_version": 1,
                "service_name": SERVICE_NAME,
                "service_account": rf"NT SERVICE\{SERVICE_NAME}",
                "authorized_client_sid": client_sid,
                "created_at": _now(),
                "source_commit": _git_head(self.source_root),
                "artifacts": [],
                "commands": [],
                "runtime_artifacts": [
                    {
                        "kind": "named_pipe",
                        "name": r"\\.\pipe\KeeperAuthority-v1",
                        "persistent": False,
                    }
                ],
                "uninstall_policy": (
                    "service registration may be removed; protected data, keys, "
                    "audit history, backups, and this manifest are preserved"
                ),
            }
        exchange_root = INSTALL_ROOT / "ClientExchange" / _sid_directory(client_sid)
        directories = (
            SERVICE_ROOT,
            SERVICE_ROOT / "bin",
            SERVICE_ROOT / "config",
            SERVICE_ROOT / "data",
            SERVICE_ROOT / "backups",
            SERVICE_ROOT / "audit",
            exchange_root,
            exchange_root / "provider-work",
            exchange_root / "evidence",
            exchange_root / "worktrees",
        )
        for directory in directories:
            if directory.exists():
                if not (
                    resume
                    or directory == MANIFEST_PATH.parent
                ):
                    raise FileExistsError(directory)
                if not directory.is_dir():
                    raise PermissionError(
                        f"Authority Service directory is not a directory: {directory}"
                    )
            else:
                directory.mkdir(parents=True, exist_ok=False)
            if not _artifact_recorded(manifest, directory):
                _record(manifest, "directory", directory)
            _persist_manifest(manifest)

        bootstrap_grants = [
            ("S-1-5-18", "full"),
            ("S-1-5-32-544", "full"),
        ]
        if service_exists:
            bootstrap_grants.append(
                (account_sid(rf"NT SERVICE\{SERVICE_NAME}"), "full")
            )
        apply_path_security(
            SERVICE_ROOT,
            exact_path_policy(
                SERVICE_ROOT,
                bootstrap_grants,
                integrity="medium",
            ),
        )
        provider_sid = _ensure_provider_identity(manifest)
        runtime = SERVICE_ROOT / "bin" / "runtime"
        self._copy_runtime(runtime, manifest, resume=resume)
        package = SERVICE_ROOT / "bin" / "keeper-authority.pyz"
        if package.exists():
            if not resume or not _recorded_file_matches(manifest, package):
                raise PermissionError(
                    "Authority Service package cannot be safely reused"
                )
        else:
            self._build_package(package)
            _record_file(manifest, package)

        config = SERVICE_ROOT / "config" / "service.json"
        if config.exists():
            if not resume or not _recorded_file_matches(manifest, config):
                raise PermissionError(
                    "Authority Service configuration cannot be safely reused"
                )
        else:
            atomic_write_json(
                config,
                {
                    "schema_version": 3,
                    "service_name": SERVICE_NAME,
                    "service_root": str(SERVICE_ROOT / "data"),
                    "provider_root": str(exchange_root / "provider-work"),
                    "allowed_evidence_root": str(exchange_root / "evidence"),
                    "authorized_client_sid": client_sid,
                    "provider_account_name": PROVIDER_ACCOUNT_NAME,
                    "provider_credential_path": str(PROVIDER_CREDENTIAL_PATH),
                    "pipe_name": r"\\.\pipe\KeeperAuthority-v1",
                    "founder_capability_verifier": (
                        _founder_verifier_configuration()
                    ),
                },
            )
            _record_file(manifest, config)
        _persist_manifest(manifest)

        service_account = rf"NT SERVICE\{SERVICE_NAME}"
        image_path = (
            f'"{runtime / "python.exe"}" "{package}" service '
            f'--config "{config}"'
        )
        if not service_exists:
            _run_recorded(
                [
                    "sc.exe",
                    "create",
                    SERVICE_NAME,
                    "binPath=",
                    image_path,
                    "obj=",
                    service_account,
                    "start=",
                    "demand",
                    "DisplayName=",
                    "Keeper Authority Service",
                ],
                manifest,
            )
        _ensure_service_process_rights(manifest)
        security_attestation = enforce_authority_security(
            service_root=SERVICE_ROOT,
            exchange_root=exchange_root,
            service_sid=account_sid(service_account),
            client_sid=client_sid,
            provider_sid=provider_sid,
        )
        manifest.setdefault("security_descriptor_repairs", []).append(
            _security_repair_record(security_attestation)
        )
        _persist_manifest(manifest)

        _run_recorded(
            ["sc.exe", "description", SERVICE_NAME, "Keeper security authority"],
            manifest,
        )
        _run_recorded(
            ["sc.exe", "sidtype", SERVICE_NAME, "restricted"], manifest
        )
        _run_recorded(
            [
                "sc.exe",
                "failure",
                SERVICE_NAME,
                "reset=",
                "86400",
                "actions=",
                "restart/5000/restart/15000/none/0",
            ],
            manifest,
        )
        manifest["service_image_path"] = image_path
        manifest["installation_completed_at"] = _now()
        _persist_manifest(manifest)
        return manifest

    def _copy_runtime(
        self,
        destination: Path,
        manifest: dict[str, Any],
        *,
        resume: bool = False,
    ) -> None:
        if destination.exists():
            if not resume:
                raise FileExistsError(destination)
            _verify_recorded_tree(destination, manifest)
            return
        base = Path(sys.base_prefix).resolve(strict=True)
        destination.mkdir(parents=True, exist_ok=False)
        _record(manifest, "directory", destination)
        for name in (
            "python.exe",
            "python3.dll",
            f"python{sys.version_info.major}{sys.version_info.minor}.dll",
            "vcruntime140.dll",
            "vcruntime140_1.dll",
            "LICENSE.txt",
        ):
            source = base / name
            if source.exists():
                target = destination / name
                shutil.copy2(source, target)
                _record_file(manifest, target)
        dlls = destination / "DLLs"
        shutil.copytree(base / "DLLs", dlls)
        _record(manifest, "directory", dlls)
        for path in sorted(item for item in dlls.rglob("*") if item.is_file()):
            _record_file(manifest, path)
        standard_library = destination / (
            f"python{sys.version_info.major}{sys.version_info.minor}.zip"
        )
        with zipfile.ZipFile(
            standard_library, "w", compression=zipfile.ZIP_DEFLATED
        ) as archive:
            library = base / "Lib"
            for path in sorted(library.rglob("*.py")):
                relative = path.relative_to(library)
                if relative.parts[0] in {
                    "site-packages",
                    "test",
                    "tests",
                    "tkinter",
                    "idlelib",
                    "turtledemo",
                    "ensurepip",
                }:
                    continue
                archive.write(path, relative.as_posix())
        _record_file(manifest, standard_library)
        _persist_manifest(manifest)

    def _build_package(self, destination: Path) -> None:
        build_service_package(self.source_root, destination)


def start() -> None:
    _require_admin()
    _run(["sc.exe", "start", SERVICE_NAME])


def stop() -> None:
    _require_admin()
    _run(["sc.exe", "stop", SERVICE_NAME])


def restart() -> None:
    stop()
    start()


def status() -> dict[str, Any]:
    service = _run(["sc.exe", "query", SERVICE_NAME], check=False)
    manifest = (
        json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        if MANIFEST_PATH.exists()
        else None
    )
    return {
        "service_query_exit_code": service.returncode,
        "service_query": service.stdout,
        "manifest_present": manifest is not None,
        "manifest": manifest,
    }


def diagnostics() -> dict[str, Any]:
    result = status()
    result["ipc"] = AuthorityServiceClient().diagnostics()
    return result


def backup(destination: Path) -> Path:
    _require_admin()
    if destination.exists():
        raise PermissionError("backup destination already exists")
    source = SERVICE_ROOT / "data"
    if not source.is_dir():
        raise FileNotFoundError("Authority Service protected data is unavailable")
    shutil.copytree(source, destination)
    return destination


def verified_recovery_backup(destination: Path) -> dict[str, Any]:
    """Capture a new immutable, hashed preimage while the service is stopped."""
    _require_admin()
    _require_service_stopped("recovery backup")
    manifest = _load_completed_manifest()
    source = SERVICE_ROOT / "data"
    if not source.is_dir():
        raise FileNotFoundError(
            "Authority Service protected data is unavailable"
        )
    destination = destination.resolve()
    evidence_path = destination.with_name(destination.name + "-manifest.json")
    protected_root = SERVICE_ROOT.resolve()
    if _paths_overlap(destination, protected_root) or _paths_overlap(
        evidence_path, protected_root
    ):
        raise PermissionError(
            "recovery preimage must be disjoint from protected service state"
        )
    if destination.exists() or evidence_path.exists():
        raise PermissionError("recovery preimage destination already exists")
    source_files = _recovery_tree_files(source)
    shutil.copytree(source, destination)
    copied_files = _recovery_tree_files(destination)
    if copied_files != source_files:
        raise PermissionError("recovery preimage differs from protected state")
    tree_sha256 = _canonical_sha256(copied_files)
    evidence = {
        "schema_version": 1,
        "captured_at": _now(),
        "source": str(source.resolve()),
        "destination": str(destination),
        "files": copied_files,
        "tree_sha256": tree_sha256,
    }
    atomic_write_json(evidence_path, evidence)
    persisted_evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    if persisted_evidence != evidence:
        raise PermissionError("recovery preimage manifest did not persist exactly")
    event = {
        "captured_at": evidence["captured_at"],
        "destination": str(destination),
        "manifest": str(evidence_path),
        "manifest_sha256": hashlib.sha256(evidence_path.read_bytes()).hexdigest().upper(),
        "tree_sha256": tree_sha256,
    }
    manifest.setdefault("recovery_preimages", []).append(event)
    _persist_manifest(manifest)
    return event


def _recovery_tree_files(root: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for path in sorted(root.rglob("*"), key=lambda item: item.as_posix()):
        attributes = int(getattr(path.lstat(), "st_file_attributes", 0))
        if path.is_symlink() or attributes & 0x400:
            raise PermissionError("recovery preimage contains a reparse point")
        if path.is_dir():
            continue
        if not path.is_file():
            raise PermissionError("recovery preimage contains an unsupported entry")
        records.append(
            {
                "path": path.relative_to(root).as_posix(),
                "size": path.stat().st_size,
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest().upper(),
            }
        )
    if not records:
        raise PermissionError("recovery preimage is empty")
    return records


def _canonical_sha256(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest().upper()


def _paths_overlap(first: Path, second: Path) -> bool:
    first = first.resolve()
    second = second.resolve()
    return (
        first == second
        or first.is_relative_to(second)
        or second.is_relative_to(first)
    )


def _verified_recovery_preimage(
    manifest: dict[str, Any], evidence_path: Path
) -> dict[str, str]:
    """Revalidate the exact stopped-state preimage bound to an upgrade."""
    evidence_path = evidence_path.resolve(strict=True)
    attributes = int(getattr(evidence_path.lstat(), "st_file_attributes", 0))
    if evidence_path.is_symlink() or attributes & 0x400 or not evidence_path.is_file():
        raise PermissionError("recovery preimage manifest is not a regular file")
    protected_root = SERVICE_ROOT.resolve(strict=True)
    if _paths_overlap(evidence_path, protected_root):
        raise PermissionError(
            "recovery preimage manifest must be disjoint from protected service state"
        )
    recorded = manifest.get("recovery_preimages")
    if not isinstance(recorded, list):
        raise PermissionError("recovery preimage is not lifecycle-recorded")
    matches = [
        item
        for item in recorded
        if isinstance(item, dict)
        and Path(str(item.get("manifest", ""))).resolve() == evidence_path
    ]
    if len(matches) != 1:
        raise PermissionError("recovery preimage identity is not unique")
    event = matches[0]
    manifest_sha256 = hashlib.sha256(evidence_path.read_bytes()).hexdigest().upper()
    if str(event.get("manifest_sha256", "")).upper() != manifest_sha256:
        raise PermissionError("recovery preimage manifest digest differs")
    try:
        evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise PermissionError("recovery preimage manifest is invalid") from error
    if not isinstance(evidence, dict) or evidence.get("schema_version") != 1:
        raise PermissionError("recovery preimage manifest schema is invalid")
    source = Path(str(evidence.get("source", ""))).resolve(strict=True)
    expected_source = (SERVICE_ROOT / "data").resolve(strict=True)
    destination = Path(str(evidence.get("destination", ""))).resolve(strict=True)
    if source != expected_source or _paths_overlap(destination, protected_root):
        raise PermissionError("recovery preimage path identity differs")
    if str(event.get("destination", "")) != str(destination):
        raise PermissionError("recovery preimage destination differs")
    copied_files = _recovery_tree_files(destination)
    source_files = _recovery_tree_files(source)
    evidence_files = evidence.get("files")
    tree_sha256 = _canonical_sha256(copied_files)
    if (
        evidence_files != copied_files
        or source_files != copied_files
        or str(evidence.get("tree_sha256", "")).upper() != tree_sha256
        or str(event.get("tree_sha256", "")).upper() != tree_sha256
    ):
        raise PermissionError("recovery preimage no longer matches protected state")
    return {
        "destination": str(destination),
        "manifest": str(evidence_path),
        "manifest_sha256": manifest_sha256,
        "tree_sha256": tree_sha256,
    }


def upgrade_package(
    package_source: Path,
    expected_package_sha256: str,
    expected_current_sha256: str,
    recovery_preimage_manifest: Path,
) -> dict[str, Any]:
    _require_admin()
    candidate = verify_service_package(package_source, expected_package_sha256)
    if candidate.path.is_relative_to(SERVICE_ROOT.resolve()):
        raise PermissionError("Authority upgrade candidate must be outside protected service state")
    manifest = _load_completed_manifest()
    _require_service_stopped("upgrade")
    preimage = _verified_recovery_preimage(manifest, recovery_preimage_manifest)
    package = SERVICE_ROOT / "bin" / "keeper-authority.pyz"
    if not package.is_file():
        raise PermissionError("installed Authority Service package is unavailable")
    current_digest = hashlib.sha256(package.read_bytes()).hexdigest().upper()
    expected_current_sha256 = expected_current_sha256.upper()
    completed = _completed_upgrade(
        manifest,
        package,
        candidate.package_sha256,
        expected_current_sha256,
        preimage,
    )
    if completed is not None:
        founder_verifier = _migrate_founder_capability_configuration(manifest)
        return _upgrade_result(manifest, completed, founder_verifier)
    claim = manifest.get("package_upgrade_claim")
    if claim is None:
        if (
            current_digest != expected_current_sha256
            or not _recorded_file_matches(manifest, package)
        ):
            raise PermissionError(
                "installed Authority Service package does not match its manifest"
            )
        current = verify_rollback_package(package, expected_current_sha256)
        old_digest = current.package_sha256
    else:
        old_digest = expected_current_sha256
    expected_backup_path = (
        SERVICE_ROOT / "backups" / f"keeper-authority-{old_digest}.pyz"
    )
    preliminary_claim = {
        "schema_version": 1,
        "previous_package_sha256": old_digest,
        "package_sha256": candidate.package_sha256,
        "source_tree_sha256": candidate.manifest["source_tree_sha256"],
        "service_version": candidate.manifest["service_version"],
        "protocol_version": candidate.manifest["protocol_version"],
        "schema_version_target": candidate.manifest["service_schema_version"],
        "backup_path": str(expected_backup_path),
        "recovery_preimage": preimage,
    }
    if claim is not None and (
        not isinstance(claim, dict)
        or any(claim.get(key) != value for key, value in preliminary_claim.items())
        or not isinstance(claim.get("claimed_at"), str)
    ):
        raise PermissionError("Authority package upgrade claim differs")
    backup_path = expected_backup_path
    if not backup_path.exists():
        shutil.copy2(package, backup_path)
        _record_file(manifest, backup_path)
        _persist_manifest(manifest)
    elif not _artifact_recorded(manifest, backup_path):
        verify_rollback_package(backup_path, old_digest)
        _record_file(manifest, backup_path)
        _persist_manifest(manifest)
    elif not _recorded_file_matches(manifest, backup_path):
        raise PermissionError(
            "Authority package rollback artifact differs from its manifest"
        )
    rollback = verify_rollback_package(backup_path, old_digest)
    provider_host_identity: dict[str, Any] | None = None
    if (
        candidate.manifest["protocol_version"] >= 7
        and candidate.manifest["service_schema_version"] >= 6
    ):
        provider_host_identity = _provision_provider_host_authority_identity(
            manifest
        )
    if _verified_recovery_preimage(
        manifest, recovery_preimage_manifest
    ) != preimage:
        raise PermissionError("recovery preimage changed during upgrade preparation")
    expected_claim = {
        **preliminary_claim,
        "provider_host_authority_key_id": (
            provider_host_identity["key_id"]
            if provider_host_identity is not None
            else None
        ),
        "recovery_preimage": preimage,
    }
    if claim is None:
        claim = dict(expected_claim)
        claim["claimed_at"] = _now()
        manifest["package_upgrade_claim"] = claim
        _persist_manifest(manifest)
    elif (
        not isinstance(claim, dict)
        or any(claim.get(key) != value for key, value in expected_claim.items())
        or not isinstance(claim.get("claimed_at"), str)
    ):
        raise PermissionError("Authority package upgrade claim differs")
    current_digest = hashlib.sha256(package.read_bytes()).hexdigest().upper()
    if current_digest not in {old_digest, candidate.package_sha256}:
        raise PermissionError("Authority package upgrade state is uncertain")
    temporary = package.with_suffix(".pyz.upgrade")
    try:
        if current_digest == old_digest:
            if temporary.exists():
                attributes = int(
                    getattr(temporary.lstat(), "st_file_attributes", 0)
                )
                if temporary.is_symlink() or attributes & 0x400 or not temporary.is_file():
                    raise PermissionError(
                        "Authority Service upgrade staging path is unsafe"
                    )
                temporary.unlink()
            shutil.copy2(candidate.path, temporary)
            staged = verify_service_package(temporary, candidate.package_sha256)
            os.replace(temporary, package)
            current_digest = staged.package_sha256
    finally:
        if temporary.exists():
            temporary.unlink()
    if current_digest != candidate.package_sha256:
        raise PermissionError("installed Authority package digest differs")
    founder_verifier = _migrate_founder_capability_configuration(manifest)
    event = _complete_package_upgrade(manifest, package, claim)
    return _upgrade_result(manifest, event, founder_verifier)


def _completed_upgrade(
    manifest: dict[str, Any],
    package: Path,
    candidate_sha256: str,
    previous_sha256: str,
    preimage: dict[str, str],
) -> dict[str, Any] | None:
    recorded = manifest.get("upgrades")
    if not isinstance(recorded, list) or not recorded:
        return None
    latest = recorded[-1]
    if not isinstance(latest, dict):
        return None
    if (
        latest.get("package_sha256") != candidate_sha256
        or latest.get("previous_package_sha256") != previous_sha256
        or latest.get("recovery_preimage") != preimage
    ):
        return None
    if not _recorded_file_matches(manifest, package):
        raise PermissionError("completed Authority package differs from its manifest")
    return latest


def _complete_package_upgrade(
    manifest: dict[str, Any], package: Path, claim: dict[str, Any]
) -> dict[str, Any]:
    _record_file(manifest, package)
    event = {
        "upgraded_at": _now(),
        "upgrade_claimed_at": claim["claimed_at"],
        "previous_package_sha256": claim["previous_package_sha256"],
        "package_sha256": claim["package_sha256"],
        "source_tree_sha256": claim["source_tree_sha256"],
        "service_version": claim["service_version"],
        "protocol_version": claim["protocol_version"],
        "schema_version": claim["schema_version_target"],
        "backup_path": claim["backup_path"],
        "provider_host_authority_key_id": claim[
            "provider_host_authority_key_id"
        ],
        "recovery_preimage": claim["recovery_preimage"],
    }
    manifest.setdefault("upgrades", []).append(event)
    manifest["package_source_tree_sha256"] = claim["source_tree_sha256"]
    manifest.pop("package_upgrade_claim", None)
    _persist_manifest(manifest)
    return event


def _upgrade_result(
    manifest: dict[str, Any],
    event: dict[str, Any],
    founder_verifier: dict[str, object],
) -> dict[str, Any]:
    backup = verify_rollback_package(
        Path(str(event["backup_path"])),
        str(event["previous_package_sha256"]),
    )
    return {
        "package": str(SERVICE_ROOT / "bin" / "keeper-authority.pyz"),
        "package_sha256": event["package_sha256"],
        "backup": str(backup.path),
        "backup_sha256": backup.package_sha256,
        "source_tree_sha256": event["source_tree_sha256"],
        "service_version": event["service_version"],
        "protocol_version": event["protocol_version"],
        "schema_version": event["schema_version"],
        "founder_issuer_key_id": founder_verifier["key_id"],
        "provider_host_authority_identity": manifest.get(
            "provider_host_authority_identity"
        ),
        "recovery_preimage": event["recovery_preimage"],
    }


def _provision_provider_host_authority_identity(
    manifest: dict[str, Any],
) -> dict[str, Any]:
    """Create or verify the exact machine signer outside ServiceMain."""
    service_sid = account_sid(rf"NT SERVICE\{SERVICE_NAME}")
    access_sids = (
        "S-1-5-18",
        "S-1-5-32-544",
        service_sid,
    )
    existing = manifest.get("provider_host_authority_identity")
    if existing is not None and (
        not isinstance(existing, dict)
        or existing.get("schema_version") != 1
        or existing.get("key_name") != PROVIDER_HOST_AUTHORITY_KEY_NAME
        or existing.get("access_sids") != list(access_sids)
    ):
        raise PermissionError(
            "Provider Host Authority identity differs from its lifecycle record"
        )
    identity_arguments: dict[str, Any] = {
        "identity": "keeper-authority-provider-host:provisioned",
        "key_name": PROVIDER_HOST_AUTHORITY_KEY_NAME,
        "machine_key": True,
    }
    signer = WindowsCngEnvelopeIdentity(
        **identity_arguments,
        create_if_missing=existing is None,
        machine_access_sids=access_sids if existing is None else (),
    )
    public = signer.public_configuration()
    record = {
        "schema_version": 1,
        "key_name": PROVIDER_HOST_AUTHORITY_KEY_NAME,
        "key_id": signer.key_id,
        "public_identity": public,
        "access_sids": list(access_sids),
    }
    if existing is not None and existing != record:
        raise PermissionError(
            "Provider Host Authority identity differs from its lifecycle record"
        )
    if existing is not None:
        WindowsCngEnvelopeIdentity(
            **identity_arguments,
            create_if_missing=False,
            machine_access_sids=access_sids,
        )
    manifest["provider_host_authority_identity"] = record
    _persist_manifest(manifest)
    return record


def rollback_package(package_source: Path, expected_package_sha256: str) -> dict[str, Any]:
    _require_admin()
    rollback = verify_rollback_package(package_source, expected_package_sha256)
    manifest = _load_completed_manifest()
    _require_service_stopped("rollback")
    recorded = manifest.get("upgrades")
    latest = recorded[-1] if isinstance(recorded, list) and recorded else None
    upgrade_claim = manifest.get("package_upgrade_claim")
    if isinstance(latest, dict):
        rollback_identity = latest
        upgraded_digest = str(latest.get("package_sha256", "")).upper()
        interrupted_upgrade = False
    elif isinstance(upgrade_claim, dict):
        rollback_identity = upgrade_claim
        upgraded_digest = str(
            upgrade_claim.get("package_sha256", "")
        ).upper()
        interrupted_upgrade = True
    else:
        raise PermissionError("Authority package rollback is not recorded")
    if (
        rollback_identity.get("backup_path") != str(rollback.path)
        or str(rollback_identity.get("previous_package_sha256", "")).upper()
        != rollback.package_sha256
    ):
        raise PermissionError("Authority package rollback identity differs")
    if not _recorded_file_matches(manifest, rollback.path):
        raise PermissionError("Authority package rollback is not manifest-recorded")
    package = SERVICE_ROOT / "bin" / "keeper-authority.pyz"
    if not package.is_file():
        raise PermissionError("installed Authority Service package is unavailable")
    current_digest = hashlib.sha256(package.read_bytes()).hexdigest().upper()
    claim = manifest.get("package_rollback_claim")
    expected_claim = {
        "replaced_package_sha256": upgraded_digest,
        "restored_package_sha256": rollback.package_sha256,
        "source_backup_path": str(rollback.path),
    }
    if claim is None:
        supported_digests = (
            {upgraded_digest, rollback.package_sha256}
            if interrupted_upgrade
            else {upgraded_digest}
        )
        if current_digest not in supported_digests or (
            not interrupted_upgrade
            and not _recorded_file_matches(manifest, package)
        ):
            raise PermissionError(
                "installed Authority package is not the recorded upgrade"
            )
        claim = dict(expected_claim)
        claim["claimed_at"] = _now()
        manifest["package_rollback_claim"] = claim
        _persist_manifest(manifest)
    elif (
        not isinstance(claim, dict)
        or any(claim.get(key) != value for key, value in expected_claim.items())
        or not isinstance(claim.get("claimed_at"), str)
    ):
        raise PermissionError("Authority package rollback claim differs")
    if current_digest == rollback.package_sha256:
        return _complete_package_rollback(manifest, package, rollback, claim)
    if current_digest != upgraded_digest:
        raise PermissionError("Authority package rollback state is uncertain")
    temporary = package.with_suffix(".pyz.rollback")
    try:
        if temporary.exists():
            verify_rollback_package(temporary, rollback.package_sha256)
        else:
            shutil.copy2(rollback.path, temporary)
        staged = verify_rollback_package(temporary, rollback.package_sha256)
        os.replace(temporary, package)
    finally:
        if temporary.exists():
            temporary.unlink()
    if hashlib.sha256(package.read_bytes()).hexdigest().upper() != staged.package_sha256:
        raise PermissionError("restored Authority package digest differs")
    return _complete_package_rollback(manifest, package, rollback, claim)


def _complete_package_rollback(
    manifest: dict[str, Any],
    package: Path,
    rollback: VerifiedRollbackPackage,
    claim: dict[str, Any],
) -> dict[str, Any]:
    _record_file(manifest, package)
    event = {
        "rolled_back_at": _now(),
        "rollback_claimed_at": claim["claimed_at"],
        "replaced_package_sha256": claim["replaced_package_sha256"],
        "restored_package_sha256": rollback.package_sha256,
        "source_backup_path": str(rollback.path),
    }
    manifest.setdefault("rollbacks", []).append(event)
    manifest.pop("package_rollback_claim", None)
    manifest.pop("package_upgrade_claim", None)
    _persist_manifest(manifest)
    return {
        "package": str(package),
        "package_sha256": rollback.package_sha256,
        "replaced_package_sha256": claim["replaced_package_sha256"],
        "source_backup": str(rollback.path),
    }


def _require_service_stopped(operation: str) -> None:
    query = _run(["sc.exe", "query", SERVICE_NAME], check=False)
    stopped = re.search(
        r"(?m)^\s*STATE\s*:\s*(?:\d+\s+)?STOPPED\s*$", query.stdout
    )
    if query.returncode != 0 or stopped is None:
        raise PermissionError(
            f"KeeperAuthority must be confirmed stopped before package {operation}"
        )


def _founder_verifier_configuration() -> dict[str, object]:
    return ProductionFounderCapabilityIssuer(
        current_process_sid()
    ).verifier_configuration()


def _migrate_founder_capability_configuration(
    manifest: dict[str, Any],
) -> dict[str, object]:
    config = SERVICE_ROOT / "config" / "service.json"
    if not config.is_file() or not _recorded_file_matches(manifest, config):
        raise PermissionError(
            "Authority Service configuration does not match its manifest"
        )
    try:
        value = json.loads(config.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise PermissionError(
            "Authority Service configuration is invalid"
        ) from error
    if not isinstance(value, dict) or value.get("schema_version") not in {2, 3}:
        raise PermissionError(
            "Authority Founder verifier configuration cannot be safely migrated"
        )
    if value["schema_version"] == 3:
        verifier = value.get("founder_capability_verifier")
        if not isinstance(verifier, dict):
            raise PermissionError("Authority Founder verifier is missing")
        ProductionFounderCapabilityVerifier(verifier)
        return verifier
    old_digest = hashlib.sha256(config.read_bytes()).hexdigest()
    backup_path = SERVICE_ROOT / "backups" / f"service-{old_digest}.json"
    if backup_path.exists():
        if not _recorded_file_matches(manifest, backup_path):
            raise PermissionError(
                "Authority Service configuration backup is untrusted"
            )
    else:
        shutil.copy2(config, backup_path)
        _record_file(manifest, backup_path)
    verifier = _founder_verifier_configuration()
    value["schema_version"] = 3
    value["founder_capability_verifier"] = verifier
    atomic_write_json(config, value)
    _record_file(manifest, config)
    manifest.setdefault("configuration_migrations", []).append(
        {
            "migrated_at": _now(),
            "from_schema": 2,
            "to_schema": 3,
            "backup_path": str(backup_path),
            "founder_issuer_key_id": verifier["key_id"],
        }
    )
    _persist_manifest(manifest)
    return verifier


def provision_provider_identity() -> dict[str, Any]:
    _require_admin()
    manifest = _load_completed_manifest()
    query = _run(["sc.exe", "query", SERVICE_NAME], check=False)
    if "RUNNING" in query.stdout or "START_PENDING" in query.stdout:
        raise PermissionError(
            "KeeperAuthority must be stopped before provider identity migration"
        )
    provider_sid = _ensure_provider_identity(manifest)
    service_rights = _ensure_service_process_rights(manifest)
    config = SERVICE_ROOT / "config" / "service.json"
    if not config.is_file() or not _recorded_file_matches(manifest, config):
        raise PermissionError(
            "Authority Service configuration does not match its manifest"
        )
    try:
        value = json.loads(config.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise PermissionError(
            "Authority Service configuration is invalid"
        ) from error
    expected_v1 = {
        "schema_version",
        "service_name",
        "service_root",
        "provider_root",
        "allowed_evidence_root",
        "authorized_client_sid",
        "pipe_name",
    }
    expected_v2 = expected_v1 | {
        "provider_account_name",
        "provider_credential_path",
    }
    expected_v3 = expected_v2 | {"founder_capability_verifier"}
    if (
        not isinstance(value, dict)
        or frozenset(value)
        not in {
            frozenset(expected_v1), frozenset(expected_v2),
            frozenset(expected_v3),
        }
        or value.get("schema_version") not in {1, 2, 3}
        or value.get("service_name") != SERVICE_NAME
    ):
        raise PermissionError(
            "Authority Service configuration cannot be safely migrated"
        )
    if value["schema_version"] == 1:
        old_digest = hashlib.sha256(config.read_bytes()).hexdigest()
        backup_path = (
            SERVICE_ROOT / "backups" / f"service-{old_digest}.json"
        )
        if backup_path.exists():
            if not _recorded_file_matches(manifest, backup_path):
                raise PermissionError(
                    "Authority Service configuration backup is untrusted"
                )
        else:
            shutil.copy2(config, backup_path)
            _record_file(manifest, backup_path)
        value.update(
            {
                "schema_version": 2,
                "provider_account_name": PROVIDER_ACCOUNT_NAME,
                "provider_credential_path": str(PROVIDER_CREDENTIAL_PATH),
            }
        )
        atomic_write_json(config, value)
        _record_file(manifest, config)
        manifest.setdefault("configuration_migrations", []).append(
            {
                "migrated_at": _now(),
                "from_schema": 1,
                "to_schema": 2,
                "backup_path": str(backup_path),
            }
        )
        _persist_manifest(manifest)
    elif value["schema_version"] in {2, 3} and (
        value.get("provider_account_name") != PROVIDER_ACCOUNT_NAME
        or value.get("provider_credential_path")
        != str(PROVIDER_CREDENTIAL_PATH)
    ):
        raise PermissionError(
            "Authority Service provider identity configuration differs"
        )
    founder_verifier = _migrate_founder_capability_configuration(manifest)
    result = repair_permissions()
    return {
        "provider_account_name": PROVIDER_ACCOUNT_NAME,
        "provider_account_sid": provider_sid,
        "provider_account_rights": list(PROVIDER_ACCOUNT_RIGHTS),
        "provider_credential_path": str(PROVIDER_CREDENTIAL_PATH),
        "configuration_schema": 3,
        "founder_issuer_key_id": founder_verifier["key_id"],
        "service_process_rights": list(service_rights),
        "permissions": result,
    }


def repair_permissions() -> dict[str, Any]:
    _require_admin()
    manifest = _load_completed_manifest()
    if not _service_exists():
        raise PermissionError(
            "KeeperAuthority service registration is unavailable"
        )
    client_sid = str(manifest["authorized_client_sid"])
    exchange_root = (
        INSTALL_ROOT / "ClientExchange" / _sid_directory(client_sid)
    )
    service_account = rf"NT SERVICE\{SERVICE_NAME}"
    identity = manifest.get("provider_identity")
    provider_sid = (
        str(identity["sid"])
        if isinstance(identity, dict)
        and identity.get("state") == "PROVISIONED"
        and isinstance(identity.get("sid"), str)
        else None
    )
    if provider_sid is None:
        raise PermissionError(
            "provisioned provider identity is required for exact ACL repair"
        )
    security_attestation = enforce_authority_security(
        service_root=SERVICE_ROOT,
        exchange_root=exchange_root,
        service_sid=account_sid(service_account),
        client_sid=client_sid,
        provider_sid=provider_sid,
    )
    _record_diagnostic_artifacts(manifest, exchange_root)
    _record_runtime_artifacts(manifest)
    manifest.setdefault("permission_repairs", []).append(
        {
            "repaired_at": _now(),
            "restricted_provider_sid": "S-1-5-12",
            "provider_account_sid": provider_sid,
            "live_security_result": security_attestation["result"],
            "expected_policy_sha256": security_attestation[
                "expected_policy_sha256"
            ],
            "live_policy_sha256": security_attestation[
                "live_policy_sha256"
            ],
        }
    )
    manifest.setdefault("security_descriptor_repairs", []).append(
        _security_repair_record(security_attestation)
    )
    _persist_manifest(manifest)
    return {
        "service_root": str(SERVICE_ROOT),
        "exchange_root": str(exchange_root),
        "restricted_provider_sid": "S-1-5-12",
        "provider_account_sid": provider_sid,
        "live_security_result": security_attestation["result"],
        "expected_policy_sha256": security_attestation[
            "expected_policy_sha256"
        ],
        "live_policy_sha256": security_attestation[
            "live_policy_sha256"
        ],
    }


def uninstall_preserving_history() -> dict[str, Any]:
    _require_admin()
    if not MANIFEST_PATH.exists():
        raise PermissionError("machine-artifact manifest is missing; uninstall failed closed")
    query = _run(["sc.exe", "query", SERVICE_NAME], check=False)
    if "RUNNING" in query.stdout:
        _run(["sc.exe", "stop", SERVICE_NAME])
    _run(["sc.exe", "delete", SERVICE_NAME])
    # Nothing on disk is deleted. This is intentionally recoverable and auditable.
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    manifest["service_registration_removed_at"] = _now()
    manifest["protected_artifacts_preserved"] = True
    _persist_manifest(manifest)
    return {
        "service_registration_removed": True,
        "protected_artifacts_preserved": True,
        "service_root": str(SERVICE_ROOT),
    }


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(prog="keeper-authority-service")
    result.add_argument(
        "--source-root", type=Path, default=Path(__file__).resolve().parents[2]
    )
    commands = result.add_subparsers(dest="command", required=True)
    commands.add_parser("install")
    commands.add_parser("resume-install")
    upgrade = commands.add_parser("upgrade-package")
    upgrade.add_argument("--package", type=Path, required=True)
    upgrade.add_argument("--expected-sha256", required=True)
    upgrade.add_argument("--expected-current-sha256", required=True)
    upgrade.add_argument(
        "--recovery-preimage-manifest", type=Path, required=True
    )
    rollback_package_command = commands.add_parser("rollback-package")
    rollback_package_command.add_argument("--package", type=Path, required=True)
    rollback_package_command.add_argument("--expected-sha256", required=True)
    verify_package = commands.add_parser("verify-package")
    verify_package.add_argument("--package", type=Path, required=True)
    verify_package.add_argument("--expected-sha256", required=True)
    verify_rollback = commands.add_parser("verify-rollback-package")
    verify_rollback.add_argument("--package", type=Path, required=True)
    verify_rollback.add_argument("--expected-sha256", required=True)
    commands.add_parser("provision-provider-identity")
    commands.add_parser("repair-permissions")
    commands.add_parser("start")
    commands.add_parser("stop")
    commands.add_parser("restart")
    commands.add_parser("status")
    commands.add_parser("diagnostics")
    backup_parser = commands.add_parser("backup")
    backup_parser.add_argument("destination", type=Path)
    verified_backup_parser = commands.add_parser("backup-recovery-preimage")
    verified_backup_parser.add_argument("destination", type=Path)
    commands.add_parser("uninstall-preserve")
    rotate = commands.add_parser("rotate-key")
    rotate.add_argument("confirmation")
    return result


def main(arguments: Sequence[str] | None = None) -> int:
    options = parser().parse_args(arguments)
    try:
        if options.command == "install":
            value: object = AuthorityServiceInstaller(options.source_root).install()
        elif options.command == "resume-install":
            value = AuthorityServiceInstaller(options.source_root).install(
                resume=True
            )
        elif options.command == "upgrade-package":
            value = upgrade_package(
                options.package,
                options.expected_sha256,
                options.expected_current_sha256,
                options.recovery_preimage_manifest,
            )
        elif options.command == "rollback-package":
            value = rollback_package(options.package, options.expected_sha256)
        elif options.command == "verify-package":
            verified = verify_service_package(options.package, options.expected_sha256)
            value = {
                "package": str(verified.path),
                "package_sha256": verified.package_sha256,
                "package_size": verified.package_size,
                "manifest": verified.manifest,
            }
        elif options.command == "verify-rollback-package":
            verified_rollback = verify_rollback_package(
                options.package, options.expected_sha256
            )
            value = {
                "package": str(verified_rollback.path),
                "package_sha256": verified_rollback.package_sha256,
                "package_size": verified_rollback.package_size,
                "rollback": True,
            }
        elif options.command == "provision-provider-identity":
            value = provision_provider_identity()
        elif options.command == "repair-permissions":
            value = repair_permissions()
        elif options.command == "start":
            start()
            value = {"started": True}
        elif options.command == "stop":
            stop()
            value = {"stopped": True}
        elif options.command == "restart":
            restart()
            value = {"restarted": True}
        elif options.command == "status":
            value = status()
        elif options.command == "diagnostics":
            value = diagnostics()
        elif options.command == "backup":
            value = {"backup": str(backup(options.destination.resolve()))}
        elif options.command == "backup-recovery-preimage":
            value = verified_recovery_backup(options.destination)
        elif options.command == "uninstall-preserve":
            value = uninstall_preserving_history()
        elif options.command == "rotate-key":
            value = AuthorityServiceClient().rotate_key(options.confirmation)
        else:
            raise ValueError("unsupported Authority Service operation")
        print(json.dumps(value, indent=2, sort_keys=True))
        return 0
    except (
        FileNotFoundError,
        OSError,
        PermissionError,
        RuntimeError,
        ValueError,
    ) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2


def _run(
    command: list[str], *, check: bool = True
) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        command,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        shell=False,
        timeout=60,
    )
    if check and result.returncode:
        raise OSError(f"command failed ({result.returncode}): {result.stdout.strip()}")
    return result


def _run_recorded(command: list[str], manifest: dict[str, Any]) -> None:
    result = _run(command, check=False)
    manifest["commands"].append(
        {
            "arguments": command,
            "exit_code": result.returncode,
            "output": result.stdout[-4096:],
            "recorded_at": _now(),
        }
    )
    _persist_manifest(manifest)
    if result.returncode:
        raise OSError(
            f"machine configuration failed ({result.returncode}): "
            f"{result.stdout.strip()}"
        )


def _record(manifest: dict[str, Any], kind: str, path: Path) -> None:
    manifest["artifacts"].append(
        {"kind": kind, "path": str(path.resolve()), "recorded_at": _now()}
    )


def _record_file(manifest: dict[str, Any], path: Path) -> None:
    content = path.read_bytes()
    manifest["artifacts"].append(
        {
            "kind": "file",
            "path": str(path.resolve()),
            "size": len(content),
            "sha256": hashlib.sha256(content).hexdigest(),
            "recorded_at": _now(),
        }
    )


def _artifact_recorded(manifest: dict[str, Any], path: Path) -> bool:
    expected = str(path.resolve())
    return any(
        isinstance(item, dict) and item.get("path") == expected
        for item in manifest.get("artifacts", [])
    )


def _recorded_file_matches(
    manifest: dict[str, Any], path: Path
) -> bool:
    content = path.read_bytes()
    expected_path = str(path.resolve())
    expected_hash = hashlib.sha256(content).hexdigest()
    return any(
        isinstance(item, dict)
        and item.get("kind") == "file"
        and item.get("path") == expected_path
        and item.get("size") == len(content)
        and item.get("sha256") == expected_hash
        for item in manifest.get("artifacts", [])
    )


def _verify_recorded_tree(
    directory: Path, manifest: dict[str, Any]
) -> None:
    for path in directory.rglob("*"):
        if path.is_dir():
            continue
        elif not _recorded_file_matches(manifest, path):
            raise PermissionError(
                f"runtime file differs from install manifest: {path}"
            )


def _successful_service_create(manifest: dict[str, Any]) -> bool:
    return any(
        isinstance(item, dict)
        and item.get("exit_code") == 0
        and isinstance(item.get("arguments"), list)
        and item["arguments"][:3]
        == ["sc.exe", "create", SERVICE_NAME]
        for item in manifest.get("commands", [])
    )


def _record_diagnostic_artifacts(
    manifest: dict[str, Any], exchange_root: Path
) -> None:
    evidence_root = exchange_root / "evidence"
    for root in sorted(evidence_root.glob("restricted-*")):
        if not root.is_dir() or not root.resolve().is_relative_to(
            evidence_root.resolve()
        ):
            continue
        for path in (root, *sorted(root.rglob("*"))):
            if _artifact_recorded(manifest, path):
                continue
            if path.is_dir():
                _record(manifest, "diagnostic-directory", path)
            elif path.is_file():
                _record_file(manifest, path)


def _record_runtime_artifacts(manifest: dict[str, Any]) -> None:
    data_root = SERVICE_ROOT / "data"
    if not data_root.is_dir():
        return
    immutable_suffixes = {".bin"}
    for path in (data_root, *sorted(data_root.rglob("*"))):
        if _artifact_recorded(manifest, path):
            continue
        if path.is_dir():
            _record(manifest, "protected-runtime-directory", path)
        elif path.is_file() and path.suffix.casefold() in immutable_suffixes:
            _record_file(manifest, path)
        elif path.is_file():
            manifest["artifacts"].append(
                {
                    "kind": "protected-mutable-runtime-file",
                    "path": str(path.resolve()),
                    "recorded_at": _now(),
                }
            )


def _security_repair_record(
    attestation: dict[str, Any],
) -> dict[str, Any]:
    if attestation.get("result") != "PASS":
        raise PermissionError(
            "security descriptor repair cannot be recorded without live equality"
        )
    return {
        "verified_at": _now(),
        "result": "PASS",
        "expected_policy_sha256": attestation["expected_policy_sha256"],
        "live_policy_sha256": attestation["live_policy_sha256"],
        "paths": sorted(
            str(item["expected"]["path"])
            for item in attestation["paths"].values()
        ),
    }


def _ensure_provider_identity(manifest: dict[str, Any]) -> str:
    identity = manifest.get("provider_identity")
    if identity is not None and not isinstance(identity, dict):
        raise PermissionError("provider identity manifest is malformed")
    actual_sid = provider_account_sid(PROVIDER_ACCOUNT_NAME)
    if identity is None:
        if actual_sid is not None:
            raise PermissionError(
                "unrecorded Keeper provider account already exists"
            )
        if PROVIDER_CREDENTIAL_PATH.exists():
            raise PermissionError(
                "unrecorded Keeper provider credential already exists"
            )
        password = generate_provider_password()
        protect_provider_password(password, PROVIDER_CREDENTIAL_PATH)
        _record_file(manifest, PROVIDER_CREDENTIAL_PATH)
        identity = {
            "account_name": PROVIDER_ACCOUNT_NAME,
            "credential_path": str(PROVIDER_CREDENTIAL_PATH),
            "credential_sha256": hashlib.sha256(
                PROVIDER_CREDENTIAL_PATH.read_bytes()
            ).hexdigest(),
            "state": "CREDENTIAL_PROTECTED",
            "created_at": _now(),
        }
        manifest["provider_identity"] = identity
        _persist_manifest(manifest)
    if (
        identity.get("account_name") != PROVIDER_ACCOUNT_NAME
        or identity.get("credential_path") != str(PROVIDER_CREDENTIAL_PATH)
        or identity.get("credential_sha256")
        != hashlib.sha256(PROVIDER_CREDENTIAL_PATH.read_bytes()).hexdigest()
        or not _recorded_file_matches(manifest, PROVIDER_CREDENTIAL_PATH)
        or identity.get("state")
        not in {"CREDENTIAL_PROTECTED", "ACCOUNT_CREATED", "PROVISIONED"}
    ):
        raise PermissionError("provider identity manifest cannot be trusted")
    password = unprotect_provider_password(PROVIDER_CREDENTIAL_PATH)
    account_created = actual_sid is None
    if actual_sid is None:
        actual_sid = create_provider_account(
            password, PROVIDER_ACCOUNT_NAME
        )
        identity.update(
            {
                "sid": actual_sid,
                "state": "ACCOUNT_CREATED",
                "account_created_at": _now(),
            }
        )
        _persist_manifest(manifest)
    rights = grant_provider_account_rights(PROVIDER_ACCOUNT_NAME)
    verified_rights = account_rights(PROVIDER_ACCOUNT_NAME)
    if not set(rights).issubset(verified_rights):
        raise PermissionError("provider account rights could not be verified")
    if not account_created and (
        identity.get("state") == "CREDENTIAL_PROTECTED"
        or identity.get("sid") != actual_sid
    ):
        # A crash may occur after NetUserAdd and before the manifest update.
        # Prove the recorded credential belongs to that exact account before
        # adopting the recovered state.
        with restricted_provider_identity_token(
            PROVIDER_ACCOUNT_NAME, PROVIDER_CREDENTIAL_PATH
        ):
            pass
        identity.update(
            {
                "sid": actual_sid,
                "state": "ACCOUNT_CREATED",
                "account_recovered_at": _now(),
            }
        )
        _persist_manifest(manifest)
    with restricted_provider_identity_token(
        PROVIDER_ACCOUNT_NAME, PROVIDER_CREDENTIAL_PATH
    ):
        pass
    identity.update(
        {
            "sid": actual_sid,
            "state": "PROVISIONED",
            "rights": list(rights),
            "rights_verified_at": _now(),
        }
    )
    _persist_manifest(manifest)
    password = "\0" * len(password)
    return actual_sid


def _ensure_service_process_rights(
    manifest: dict[str, Any],
) -> tuple[str, ...]:
    if not _service_exists():
        raise PermissionError(
            "KeeperAuthority service registration is unavailable"
        )
    account_name = rf"NT SERVICE\{SERVICE_NAME}"
    rights = grant_account_rights(
        account_name, AUTHORITY_SERVICE_PROCESS_RIGHTS
    )
    verified_rights = account_rights(account_name)
    if not set(rights).issubset(verified_rights):
        raise PermissionError(
            "KeeperAuthority process rights could not be verified"
        )
    manifest["service_process_rights"] = {
        "account_name": account_name,
        "rights": list(rights),
        "verified_rights": list(verified_rights),
        "applied_at": _now(),
    }
    _persist_manifest(manifest)
    return rights


def _load_incomplete_manifest() -> dict[str, Any]:
    if not MANIFEST_PATH.is_file():
        raise PermissionError(
            "incomplete-install manifest is unavailable; resume failed closed"
        )
    try:
        manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise PermissionError(
            "incomplete-install manifest is invalid"
        ) from error
    if (
        not isinstance(manifest, dict)
        or manifest.get("schema_version") != 1
        or manifest.get("service_name") != SERVICE_NAME
        or manifest.get("installation_completed_at") is not None
        or not isinstance(manifest.get("artifacts"), list)
        or not isinstance(manifest.get("commands"), list)
        or not isinstance(manifest.get("authorized_client_sid"), str)
    ):
        raise PermissionError(
            "Authority Service install is not safely resumable"
        )
    return manifest


def _load_completed_manifest() -> dict[str, Any]:
    if not MANIFEST_PATH.is_file():
        raise PermissionError(
            "Authority Service manifest is unavailable"
        )
    try:
        manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise PermissionError(
            "Authority Service manifest is invalid"
        ) from error
    if (
        not isinstance(manifest, dict)
        or manifest.get("schema_version") != 1
        or manifest.get("service_name") != SERVICE_NAME
        or not isinstance(manifest.get("installation_completed_at"), str)
        or not isinstance(manifest.get("artifacts"), list)
    ):
        raise PermissionError(
            "Authority Service installation is not complete"
        )
    return manifest


def _validate_resume_artifacts(manifest: dict[str, Any]) -> None:
    recorded = {
        str(Path(str(item["path"])).resolve())
        for item in manifest["artifacts"]
        if isinstance(item, dict) and isinstance(item.get("path"), str)
    }
    recorded_parents = {
        str(parent.resolve())
        for value in tuple(recorded)
        for parent in Path(value).parents
        if parent == SERVICE_ROOT or parent.is_relative_to(SERVICE_ROOT)
    }
    allowed = recorded | {
        str(MANIFEST_PATH.resolve()),
        str(MANIFEST_PATH.parent.resolve()),
    } | recorded_parents
    existing = {
        str(path.resolve())
        for path in SERVICE_ROOT.rglob("*")
    } | {str(SERVICE_ROOT.resolve())}
    unexpected = sorted(existing - allowed)
    if unexpected:
        raise PermissionError(
            "incomplete install contains unrecorded artifacts: "
            + ", ".join(unexpected)
        )


def _persist_manifest(manifest: dict[str, Any]) -> None:
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_json(MANIFEST_PATH, manifest)


def _require_admin() -> None:
    shell32 = __import__("ctypes").windll.shell32
    if not shell32.IsUserAnAdmin():
        raise PermissionError("Authority Service operation requires elevation")


def _service_exists() -> bool:
    result = _run(["sc.exe", "query", SERVICE_NAME], check=False)
    return result.returncode == 0


def _sid_directory(sid: str) -> str:
    return sid.replace("-", "_")


def _git_head(root: Path) -> str:
    result = _run(
        [
            "git",
            "-c",
            f"safe.directory={root.as_posix()}",
            "-C",
            str(root),
            "rev-parse",
            "HEAD",
        ]
    )
    return result.stdout.strip()


def _now() -> str:
    return datetime.now(UTC).isoformat()


if __name__ == "__main__":
    raise SystemExit(main())
