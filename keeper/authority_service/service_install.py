from __future__ import annotations

import argparse
import hashlib
import json
import os
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
from keeper.authority_service.windows_identity import current_process_sid
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
        keeper_root = self.source_root / "keeper"
        if not keeper_root.is_dir():
            raise FileNotFoundError("Keeper package source is unavailable")
        with zipfile.ZipFile(
            destination, "w", compression=zipfile.ZIP_DEFLATED
        ) as archive:
            _write_deterministic_zip_entry(
                archive,
                "__main__.py",
                "from keeper.authority_service.service_main import main\n"
                "raise SystemExit(main())\n",
            )
            for path in sorted(keeper_root.rglob("*.py")):
                _write_deterministic_zip_entry(
                    archive,
                    (Path("keeper") / path.relative_to(keeper_root)).as_posix(),
                    path.read_bytes(),
                )


def _write_deterministic_zip_entry(
    archive: zipfile.ZipFile, name: str, content: str | bytes
) -> None:
    info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
    info.compress_type = zipfile.ZIP_DEFLATED
    info.create_system = 3
    info.external_attr = (0o100644 & 0xFFFF) << 16
    archive.writestr(info, content)


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


def upgrade_package(source_root: Path) -> dict[str, Any]:
    _require_admin()
    installer = AuthorityServiceInstaller(source_root)
    manifest = _load_completed_manifest()
    query = _run(["sc.exe", "query", SERVICE_NAME], check=False)
    if "RUNNING" in query.stdout or "START_PENDING" in query.stdout:
        raise PermissionError(
            "KeeperAuthority must be stopped before package upgrade"
        )
    package = SERVICE_ROOT / "bin" / "keeper-authority.pyz"
    if not package.is_file() or not _recorded_file_matches(manifest, package):
        raise PermissionError(
            "installed Authority Service package does not match its manifest"
        )
    old_digest = hashlib.sha256(package.read_bytes()).hexdigest()
    backup_path = (
        SERVICE_ROOT / "backups" / f"keeper-authority-{old_digest}.pyz"
    )
    if not backup_path.exists():
        shutil.copy2(package, backup_path)
        _record_file(manifest, backup_path)
    temporary = package.with_suffix(".pyz.upgrade")
    if temporary.exists():
        raise PermissionError(
            "Authority Service upgrade staging file already exists"
        )
    try:
        installer._build_package(temporary)
        new_digest = hashlib.sha256(temporary.read_bytes()).hexdigest()
        os.replace(temporary, package)
    finally:
        if temporary.exists():
            temporary.unlink()
    _record_file(manifest, package)
    source_commit = _git_head(installer.source_root)
    manifest.setdefault("upgrades", []).append(
        {
            "upgraded_at": _now(),
            "previous_package_sha256": old_digest,
            "package_sha256": new_digest,
            "source_commit": source_commit,
            "backup_path": str(backup_path),
        }
    )
    manifest["source_commit"] = source_commit
    _persist_manifest(manifest)
    # The new package deliberately accepts schema 2 in fail-closed mode, so
    # a configuration-migration failure cannot make the stopped service
    # unstartable. Launch authorization remains disabled until schema 3 lands.
    founder_verifier = _migrate_founder_capability_configuration(manifest)
    return {
        "package": str(package),
        "package_sha256": new_digest,
        "backup": str(backup_path),
        "source_commit": source_commit,
        "founder_issuer_key_id": founder_verifier["key_id"],
    }


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
    commands.add_parser("upgrade-package")
    commands.add_parser("provision-provider-identity")
    commands.add_parser("repair-permissions")
    commands.add_parser("start")
    commands.add_parser("stop")
    commands.add_parser("restart")
    commands.add_parser("status")
    commands.add_parser("diagnostics")
    backup_parser = commands.add_parser("backup")
    backup_parser.add_argument("destination", type=Path)
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
            value = upgrade_package(options.source_root)
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
