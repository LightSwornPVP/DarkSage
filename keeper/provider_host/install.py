from __future__ import annotations

import hashlib
import json
import os
import shutil
import stat
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Callable

from keeper.authority_service.windows_security import apply_path_security
from keeper.provider_host.identity import current_user_binding
from keeper.recovery import atomic_write_json


_RESTRICTED_CODE_SID = "S-1-5-12"
_FILE_ALL_ACCESS = 0x001F01FF
_PACKAGE_MANIFEST = "keeper-provider-host-package-manifest.json"
_PACKAGE_SCHEMA_VERSION = 1
_PACKAGE_PRODUCT = "KeeperProviderHost"
_FILE_ATTRIBUTE_REPARSE_POINT = 0x400


@dataclass(frozen=True, slots=True)
class HostInstallResult:
    version: str
    artifact_path: str
    artifact_sha256: str
    package_sha256: str
    previous_version: str | None
    startup_path: str


@dataclass(frozen=True, slots=True)
class _VerifiedPackage:
    root: Path
    executable: Path
    executable_sha256: str
    manifest_sha256: str
    manifest: dict[str, object]


class ProviderHostInstaller:
    """Crash-safe per-user lifecycle with one verified rollback generation."""

    def __init__(
        self,
        install_root: Path,
        startup_root: Path,
        *,
        owner_sid: str | None = None,
    ) -> None:
        self.root = install_root.resolve()
        self.startup_root = startup_root.resolve()
        self.versions = self.root / "versions"
        self.state = self.root / "state"
        self.logs = self.root / "logs"
        self.current_path = self.root / "current.json"
        self.transaction_path = self.root / "lifecycle-transaction.json"
        self.startup_path = self.startup_root / "KeeperProviderHost.cmd"
        self.owner_sid = owner_sid or (
            current_user_binding().user_sid if os.name == "nt" else None
        )

    def install(
        self,
        artifact: Path,
        *,
        version: str,
        expected_package_sha256: str,
    ) -> HostInstallResult:
        _validate_version(version)
        package = _verify_package(
            artifact, version=version, expected_manifest_sha256=expected_package_sha256
        )
        self._ensure_roots()
        current = self._load_current(required=False)
        previous = str(current["version"]) if current is not None else None
        transaction_id = uuid.uuid4().hex
        destination_root = self.versions / version
        staging_root = self.versions / f".{version}.{transaction_id}.staging"
        backup_root = self.versions / f".{version}.{transaction_id}.backup"
        transaction = {
            "schema_version": 2,
            "operation": "install" if current is None else "update",
            "version": version,
            "artifact_sha256": package.executable_sha256,
            "package_sha256": package.manifest_sha256,
            "previous_version": previous,
            "staging_path": str(staging_root),
            "backup_path": str(backup_root),
            "started_at": _now(),
        }
        atomic_write_json(self.transaction_path, transaction)
        try:
            self._copy_package(package, staging_root)
            _verify_package(
                staging_root / "KeeperProviderHost.exe",
                version=version,
                expected_manifest_sha256=package.manifest_sha256,
            )
            if destination_root.exists():
                if _unsafe_tree(destination_root, self.versions):
                    raise PermissionError("Provider Host version path is unsafe")
                os.replace(destination_root, backup_root)
            os.replace(staging_root, destination_root)
            installed = _verify_package(
                destination_root / "KeeperProviderHost.exe",
                version=version,
                expected_manifest_sha256=package.manifest_sha256,
            )
            self._secure_tree(destination_root)
            self._commit_selection(
                installed,
                version=version,
                previous_version=(
                    previous
                    if previous != version
                    else (
                        str(current.get("previous_version"))
                        if current is not None
                        and isinstance(current.get("previous_version"), str)
                        else None
                    )
                ),
            )
        except Exception:
            if not destination_root.exists() and backup_root.exists():
                os.replace(backup_root, destination_root)
            raise
        finally:
            if staging_root.exists() and not _unsafe_tree(staging_root, self.versions):
                shutil.rmtree(staging_root)
        if backup_root.exists():
            if _unsafe_tree(backup_root, self.versions):
                raise PermissionError("Provider Host backup path is unsafe")
            shutil.rmtree(backup_root)
        self.transaction_path.unlink(missing_ok=True)
        retained = {version}
        if previous is not None:
            retained.add(previous)
        self._prune_versions(retained)
        return self._result(installed, version, previous)

    def repair(
        self, artifact: Path, *, expected_package_sha256: str
    ) -> HostInstallResult:
        current = self._load_current(required=True)
        assert current is not None
        return self.install(
            artifact,
            version=str(current["version"]),
            expected_package_sha256=expected_package_sha256,
        )

    def update(
        self,
        artifact: Path,
        *,
        version: str,
        expected_package_sha256: str,
        drain: Callable[[], None],
    ) -> HostInstallResult:
        current = self._load_current(required=True)
        assert current is not None
        if current["version"] == version:
            raise ValueError("Provider Host update version is unchanged")
        drain()
        return self.install(
            artifact,
            version=version,
            expected_package_sha256=expected_package_sha256,
        )

    def rollback(self, *, drain: Callable[[], None]) -> HostInstallResult:
        current = self._load_current(required=True)
        assert current is not None
        previous = current.get("previous_version")
        if not isinstance(previous, str) or not previous:
            raise PermissionError("Provider Host rollback generation is unavailable")
        package = self._installed_package(previous)
        drain()
        atomic_write_json(
            self.transaction_path,
            {
                "schema_version": 2,
                "operation": "rollback",
                "version": previous,
                "artifact_sha256": package.executable_sha256,
                "package_sha256": package.manifest_sha256,
                "previous_version": str(current["version"]),
                "staging_path": "",
                "backup_path": "",
                "started_at": _now(),
            },
        )
        self._commit_selection(
            package, version=previous, previous_version=str(current["version"])
        )
        self.transaction_path.unlink()
        return self._result(package, previous, str(current["version"]))

    def uninstall_preserving_data(
        self, *, drain: Callable[[], None]
    ) -> dict[str, object]:
        self._load_current(required=True)
        drain()
        atomic_write_json(
            self.transaction_path,
            {
                "schema_version": 2,
                "operation": "uninstall",
                "version": "",
                "artifact_sha256": "",
                "package_sha256": "",
                "previous_version": None,
                "staging_path": "",
                "backup_path": "",
                "started_at": _now(),
            },
        )
        self._finish_program_removal()
        self.transaction_path.unlink(missing_ok=True)
        return {
            "program_removed": True,
            "startup_removed": True,
            "state_preserved": self.state.exists(),
            "logs_preserved": self.logs.exists(),
        }

    def recover(self) -> dict[str, object]:
        if not self.transaction_path.exists():
            current = self._load_current(required=False)
            return {"recovered": False, "current": current}
        transaction = _read_object(self.transaction_path)
        if transaction.get("schema_version") != 2:
            raise PermissionError("Provider Host lifecycle transaction is invalid")
        if transaction.get("operation") == "uninstall":
            self._finish_program_removal()
            self.transaction_path.unlink()
            return {"recovered": True, "current": None}
        version = transaction.get("version")
        package_sha256 = transaction.get("package_sha256")
        previous = transaction.get("previous_version")
        if isinstance(version, str) and isinstance(package_sha256, str):
            try:
                package = _verify_package(
                    self.versions / version / "KeeperProviderHost.exe",
                    version=version,
                    expected_manifest_sha256=package_sha256,
                )
            except (FileNotFoundError, OSError, PermissionError, ValueError):
                package = None
            if package is not None:
                self._commit_selection(
                    package,
                    version=version,
                    previous_version=previous if isinstance(previous, str) else None,
                )
                self._clean_transaction_paths(transaction)
                self.transaction_path.unlink()
                return {"recovered": True, "current": self._load_current(required=True)}
            self._restore_transaction_backup(transaction, version)
        current = self._load_current(required=False)
        if current is not None:
            self._write_startup_launcher(Path(str(current["artifact_path"])))
            self._clean_transaction_paths(transaction)
            self.transaction_path.unlink()
            return {"recovered": True, "current": current}
        raise PermissionError("Provider Host lifecycle recovery is ambiguous")

    def status(self) -> dict[str, object]:
        current = self._load_current(required=False)
        return {
            "installed": current is not None,
            "current": current,
            "startup_registered": self.startup_path.is_file(),
            "transaction_pending": self.transaction_path.is_file(),
        }

    def _ensure_roots(self) -> None:
        for path in (self.root, self.versions, self.state, self.logs, self.startup_root):
            path.mkdir(mode=0o700, parents=True, exist_ok=True)
        for path in (self.root, self.versions, self.state, self.logs, self.startup_root):
            self._secure(path)

    def _load_current(self, *, required: bool) -> dict[str, object] | None:
        if not self.current_path.is_file():
            if required:
                raise PermissionError("Provider Host is not installed")
            return None
        value = _read_object(self.current_path)
        expected = {
            "schema_version",
            "version",
            "artifact_path",
            "artifact_sha256",
            "package_sha256",
            "previous_version",
            "selected_at",
        }
        if set(value) != expected or value.get("schema_version") != 2:
            raise PermissionError("Provider Host current selection is invalid")
        version = str(value["version"])
        _validate_version(version)
        package = self._installed_package(version, str(value["package_sha256"]))
        if package.executable != Path(str(value["artifact_path"])).resolve(strict=True):
            raise PermissionError("Provider Host current artifact path differs")
        if package.executable_sha256 != value["artifact_sha256"]:
            raise PermissionError("Provider Host current executable digest differs")
        return value

    def _installed_package(
        self, version: str, expected_package_sha256: str | None = None
    ) -> _VerifiedPackage:
        manifest_path = self.versions / version / _PACKAGE_MANIFEST
        if expected_package_sha256 is None:
            expected_package_sha256 = _digest_file(manifest_path)
        return _verify_package(
            self.versions / version / "KeeperProviderHost.exe",
            version=version,
            expected_manifest_sha256=expected_package_sha256,
        )

    def _copy_package(self, package: _VerifiedPackage, destination: Path) -> None:
        destination.mkdir(mode=0o700, parents=False, exist_ok=False)
        files = _manifest_files(package.manifest)
        for entry in files:
            relative = Path(*PurePosixPath(str(entry["path"])).parts)
            source = package.root / relative
            target = destination / relative
            target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            _atomic_replace_bytes(target, source.read_bytes())
        _atomic_replace_bytes(
            destination / _PACKAGE_MANIFEST,
            (package.root / _PACKAGE_MANIFEST).read_bytes(),
        )
        self._secure_tree(destination)

    def _secure_tree(self, root: Path) -> None:
        for path in sorted(root.rglob("*"), key=lambda item: len(item.parts)):
            self._secure(path)
        self._secure(root)

    def _commit_selection(
        self,
        package: _VerifiedPackage,
        *,
        version: str,
        previous_version: str | None,
    ) -> None:
        self._write_startup_launcher(package.executable)
        atomic_write_json(
            self.current_path,
            {
                "schema_version": 2,
                "version": version,
                "artifact_path": str(package.executable),
                "artifact_sha256": package.executable_sha256,
                "package_sha256": package.manifest_sha256,
                "previous_version": previous_version,
                "selected_at": _now(),
            },
        )

    def _result(
        self, package: _VerifiedPackage, version: str, previous: str | None
    ) -> HostInstallResult:
        return HostInstallResult(
            version,
            str(package.executable),
            package.executable_sha256,
            package.manifest_sha256,
            previous,
            str(self.startup_path),
        )

    def _write_startup_launcher(self, artifact: Path) -> None:
        self.startup_root.mkdir(parents=True, exist_ok=True)
        content = (
            "@echo off\r\n"
            f'"{artifact.resolve(strict=True)}" run '
            f'--config "{(self.state / "provider-host.json").resolve()}"\r\n'
        ).encode("utf-8")
        _atomic_replace_bytes(self.startup_path, content)
        self._secure(self.startup_path)

    def _secure(self, path: Path) -> None:
        if os.name != "nt":
            path.chmod(0o700)
            return
        if self.owner_sid is None or not self.owner_sid.startswith("S-1-"):
            raise PermissionError("Provider Host owner SID is unavailable")
        inheritance = ["container_inherit", "object_inherit"] if path.is_dir() else []
        apply_path_security(
            path,
            {
                "path": str(path.resolve(strict=True)),
                "dacl_protected": True,
                "aces": [
                    _host_ace("deny", _RESTRICTED_CODE_SID, inheritance),
                    _host_ace("allow", "S-1-5-18", inheritance),
                    _host_ace("allow", self.owner_sid, inheritance),
                ],
                "mandatory_integrity": {
                    "level": "medium",
                    "trustee_sid": "S-1-16-8192",
                    "policy_mask": 1,
                    "policy_flags": ["no_write_up"],
                    "inheritance_flags": inheritance,
                    "propagation_flags": [],
                    "inherited": False,
                },
            },
        )

    def _clean_transaction_paths(self, transaction: dict[str, object]) -> None:
        for key in ("staging_path", "backup_path"):
            value = transaction.get(key)
            if not isinstance(value, str) or not value:
                continue
            path = Path(value)
            if path.exists():
                if _unsafe_tree(path, self.versions):
                    raise PermissionError("Provider Host transaction path is unsafe")
                shutil.rmtree(path)

    def _restore_transaction_backup(
        self, transaction: dict[str, object], version: str
    ) -> None:
        backup_value = transaction.get("backup_path")
        if not isinstance(backup_value, str):
            return
        backup = Path(backup_value)
        destination = self.versions / version
        if not backup.exists() or destination.exists():
            return
        if _unsafe_tree(backup, self.versions):
            raise PermissionError("Provider Host transaction backup path is unsafe")
        manifest_path = backup / _PACKAGE_MANIFEST
        backup_digest = _digest_file(manifest_path)
        _verify_package(
            backup / "KeeperProviderHost.exe",
            version=version,
            expected_manifest_sha256=backup_digest,
        )
        os.replace(backup, destination)

    def _finish_program_removal(self) -> None:
        self.startup_path.unlink(missing_ok=True)
        if self.versions.exists():
            resolved = self.versions.resolve(strict=True)
            if resolved.parent != self.root:
                raise PermissionError("Provider Host versions root is not canonical")
            shutil.rmtree(resolved)
        self.current_path.unlink(missing_ok=True)

    def _prune_versions(self, retained: set[str]) -> None:
        if not self.versions.exists():
            return
        for child in self.versions.iterdir():
            if child.is_dir() and child.name not in retained:
                if _unsafe_tree(child, self.versions):
                    raise PermissionError("Provider Host version path is unsafe")
                shutil.rmtree(child)


def _verify_package(
    artifact: Path, *, version: str, expected_manifest_sha256: str
) -> _VerifiedPackage:
    _validate_digest(expected_manifest_sha256)
    source = artifact.resolve(strict=True)
    if source.name.casefold() != "keeperproviderhost.exe" or source.read_bytes()[:2] != b"MZ":
        raise PermissionError("Provider Host requires a dedicated Windows executable")
    root = source.parent.resolve(strict=True)
    manifest_path = root / _PACKAGE_MANIFEST
    if _digest_file(manifest_path) != expected_manifest_sha256.casefold():
        raise PermissionError("Provider Host package manifest digest differs")
    manifest = _read_object(manifest_path)
    if set(manifest) != {"schema_version", "product", "version", "files"}:
        raise PermissionError("Provider Host package manifest is invalid")
    if (
        manifest.get("schema_version") != _PACKAGE_SCHEMA_VERSION
        or manifest.get("product") != _PACKAGE_PRODUCT
        or manifest.get("version") != version
    ):
        raise PermissionError("Provider Host package identity differs")
    files = _manifest_files(manifest)
    expected_paths: set[str] = set()
    executable_sha256: str | None = None
    for entry in files:
        relative_text = str(entry["path"])
        relative = PurePosixPath(relative_text)
        target = root.joinpath(*relative.parts)
        resolved = target.resolve(strict=True)
        if root not in resolved.parents or _is_link_or_reparse(target) or not target.is_file():
            raise PermissionError("Provider Host package path is unsafe")
        if target.stat().st_size != entry["size"] or _digest_file(target) != entry["sha256"]:
            raise PermissionError("Provider Host package file differs")
        expected_paths.add(relative_text)
        if relative_text.casefold() == "keeperproviderhost.exe":
            executable_sha256 = str(entry["sha256"])
    if executable_sha256 is None:
        raise PermissionError("Provider Host package executable is absent")
    actual_paths = _actual_package_paths(root)
    if actual_paths != expected_paths:
        raise PermissionError("Provider Host package file coverage differs")
    return _VerifiedPackage(
        root,
        source,
        executable_sha256,
        expected_manifest_sha256.casefold(),
        manifest,
    )


def _manifest_files(manifest: dict[str, object]) -> list[dict[str, object]]:
    value = manifest.get("files")
    if not isinstance(value, list) or not value:
        raise PermissionError("Provider Host package file manifest is invalid")
    result: list[dict[str, object]] = []
    seen: set[str] = set()
    for item in value:
        if not isinstance(item, dict) or set(item) != {"path", "size", "sha256"}:
            raise PermissionError("Provider Host package file entry is invalid")
        path = item.get("path")
        size = item.get("size")
        digest = item.get("sha256")
        if not isinstance(path, str) or not _safe_relative_path(path):
            raise PermissionError("Provider Host package relative path is invalid")
        if path.casefold() in seen:
            raise PermissionError("Provider Host package path is duplicated")
        if not isinstance(size, int) or isinstance(size, bool) or size < 0:
            raise PermissionError("Provider Host package file size is invalid")
        if not isinstance(digest, str):
            raise PermissionError("Provider Host package file digest is invalid")
        _validate_digest(digest)
        seen.add(path.casefold())
        result.append({"path": path, "size": size, "sha256": digest.casefold()})
    return result


def _actual_package_paths(root: Path) -> set[str]:
    actual: set[str] = set()
    for directory, directories, files in os.walk(root, followlinks=False):
        parent = Path(directory)
        for name in directories:
            candidate = parent / name
            if _is_link_or_reparse(candidate):
                raise PermissionError("Provider Host package directory is unsafe")
        for name in files:
            candidate = parent / name
            if _is_link_or_reparse(candidate):
                raise PermissionError("Provider Host package file is unsafe")
            relative = candidate.relative_to(root).as_posix()
            if relative != _PACKAGE_MANIFEST:
                actual.add(relative)
    return actual


def _safe_relative_path(value: str) -> bool:
    path = PurePosixPath(value)
    return (
        value == path.as_posix()
        and not path.is_absolute()
        and len(path.parts) > 0
        and all(part not in {"", ".", ".."} for part in path.parts)
        and "\\" not in value
        and ":" not in value
        and value != _PACKAGE_MANIFEST
    )


def _is_link_or_reparse(path: Path) -> bool:
    if path.is_symlink():
        return True
    attributes = getattr(path.lstat(), "st_file_attributes", 0)
    return bool(attributes & _FILE_ATTRIBUTE_REPARSE_POINT)


def _unsafe_tree(path: Path, expected_parent: Path) -> bool:
    return (
        _is_link_or_reparse(path)
        or path.resolve(strict=True).parent != expected_parent.resolve(strict=True)
    )


def _atomic_replace_bytes(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.parent / f".{path.name}.{uuid.uuid4().hex}.tmp"
    with temporary.open("xb") as stream:
        stream.write(content)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def _host_ace(ace_type: str, sid: str, inheritance: list[str]) -> dict[str, object]:
    return {
        "ace_type": ace_type,
        "trustee_sid": sid,
        "rights_mask": _FILE_ALL_ACCESS,
        "inheritance_flags": list(inheritance),
        "propagation_flags": [],
        "inherited": False,
    }


def _validate_digest(value: str) -> None:
    if len(value) != 64 or any(character not in "0123456789abcdefABCDEF" for character in value):
        raise PermissionError("Provider Host package digest is invalid")


def _digest_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _read_object(path: Path) -> dict[str, object]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise PermissionError("Provider Host lifecycle metadata is invalid") from error
    if not isinstance(value, dict):
        raise PermissionError("Provider Host lifecycle metadata is invalid")
    return value


def _validate_version(value: str) -> None:
    if (
        not value
        or len(value) > 64
        or any(character not in "0123456789.-_" for character in value)
        or value.startswith(".")
    ):
        raise ValueError("Provider Host version is invalid")


def _now() -> str:
    return datetime.now(UTC).isoformat()
