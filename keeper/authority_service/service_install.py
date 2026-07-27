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

    def install(self) -> dict[str, Any]:
        _require_admin()
        if SERVICE_ROOT.exists() or _service_exists():
            raise PermissionError(
                "KeeperAuthority already exists; use status/repair/upgrade, not install"
            )
        client_sid = current_process_sid()
        exchange_root = INSTALL_ROOT / "ClientExchange" / _sid_directory(client_sid)
        manifest: dict[str, Any] = {
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
            directory.mkdir(parents=True, exist_ok=False)
            _record(manifest, "directory", directory)
            _persist_manifest(manifest)

        runtime = SERVICE_ROOT / "bin" / "runtime"
        self._copy_runtime(runtime, manifest)
        package = SERVICE_ROOT / "bin" / "keeper-authority.pyz"
        self._build_package(package)
        _record_file(manifest, package)

        config = SERVICE_ROOT / "config" / "service.json"
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

        image_path = (
            f'"{runtime / "python.exe"}" "{package}" service '
            f'--config "{config}"'
        )
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
        self, destination: Path, manifest: dict[str, Any]
    ) -> None:
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
