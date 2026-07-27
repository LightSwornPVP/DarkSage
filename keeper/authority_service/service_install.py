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
from keeper.authority_service.service_main import SERVICE_NAME
from keeper.authority_service.windows_identity import current_process_sid
from keeper.recovery import atomic_write_json


INSTALL_ROOT = Path(os.environ.get("ProgramData", r"C:\ProgramData")) / "Keeper"
SERVICE_ROOT = INSTALL_ROOT / "AuthorityService"
MANIFEST_PATH = SERVICE_ROOT / "audit" / "machine-artifacts.json"


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
                    "schema_version": 1,
                    "service_name": SERVICE_NAME,
                    "service_root": str(SERVICE_ROOT / "data"),
                    "provider_root": str(exchange_root / "provider-work"),
                    "allowed_evidence_root": str(exchange_root / "evidence"),
                    "authorized_client_sid": client_sid,
                    "pipe_name": r"\\.\pipe\KeeperAuthority-v1",
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
        protected_acl = [
            "icacls",
            str(SERVICE_ROOT),
            "/inheritance:r",
            "/grant:r",
            "SYSTEM:(OI)(CI)F",
            "BUILTIN\\Administrators:(OI)(CI)F",
            f"{service_account}:(OI)(CI)F",
        ]
        _run_recorded(protected_acl, manifest)
        exchange_acl = [
            "icacls",
            str(exchange_root),
            "/inheritance:r",
            "/grant:r",
            "SYSTEM:(OI)(CI)F",
            "BUILTIN\\Administrators:(OI)(CI)F",
            f"{service_account}:(OI)(CI)M",
            f"*{client_sid}:(OI)(CI)M",
        ]
        _run_recorded(exchange_acl, manifest)
        _run_recorded(
            [
                "icacls",
                str(exchange_root),
                "/setintegritylevel",
                "(OI)(CI)L",
            ],
            manifest,
        )

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
            archive.writestr(
                "__main__.py",
                "from keeper.authority_service.service_main import main\n"
                "raise SystemExit(main())\n",
            )
            for path in sorted(keeper_root.rglob("*.py")):
                archive.write(
                    path, (Path("keeper") / path.relative_to(keeper_root)).as_posix()
                )


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
