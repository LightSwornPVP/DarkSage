from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Sequence

from keeper.authority_service.provider_identity import account_rights


SERVICE_ROOT = Path(r"C:\ProgramData\Keeper\AuthorityService")
DEFAULT_EVIDENCE_ROOT = Path(
    r"C:\ProgramData\Keeper\ClientExchange"
    r"\S_1_5_21_2426456460_2159068531_2397302861_1001\evidence"
)


def audit(
    expected_source_commit: str,
    evidence_root: Path,
    excluded_evidence_root: Path | None,
) -> dict[str, Any]:
    manifest_path = SERVICE_ROOT / "audit" / "machine-artifacts.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest["source_commit"] != expected_source_commit:
        raise PermissionError("installed source commit differs")
    identity = manifest["provider_identity"]
    if (
        identity["state"] != "PROVISIONED"
        or identity["account_name"] != "KeeperAuthorityPvd"
    ):
        raise PermissionError("provider identity is not provisioned")
    expected_provider_rights = {
        "SeBatchLogonRight",
        "SeDenyInteractiveLogonRight",
        "SeDenyRemoteInteractiveLogonRight",
    }
    provider_rights = set(account_rights("KeeperAuthorityPvd"))
    if not expected_provider_rights.issubset(provider_rights):
        raise PermissionError("provider account rights differ")
    expected_service_rights = {
        "SeAssignPrimaryTokenPrivilege",
        "SeIncreaseQuotaPrivilege",
    }
    service_rights = set(
        account_rights(r"NT SERVICE\KeeperAuthority")
    )
    if not expected_service_rights.issubset(service_rights):
        raise PermissionError("service process rights differ")
    config_path = SERVICE_ROOT / "config" / "service.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    if (
        config["schema_version"] != 2
        or config["provider_account_name"] != "KeeperAuthorityPvd"
    ):
        raise PermissionError("Authority Service configuration differs")
    credential = Path(config["provider_credential_path"])
    if (
        hashlib.sha256(credential.read_bytes()).hexdigest()
        != identity["credential_sha256"]
    ):
        raise PermissionError("provider credential digest differs")
    artifacts = manifest["artifacts"]

    def recorded(path: Path) -> None:
        resolved = str(path.resolve())
        matches = [
            item for item in artifacts if item.get("path") == resolved
        ]
        if not matches:
            raise PermissionError(f"unrecorded machine artifact: {resolved}")
        if path.is_file():
            content = path.read_bytes()
            digest = hashlib.sha256(content).hexdigest()
            if not any(
                item.get("sha256") == digest
                and item.get("size") == len(content)
                for item in matches
            ):
                raise PermissionError(
                    f"machine artifact digest differs: {resolved}"
                )

    package = SERVICE_ROOT / "bin" / "keeper-authority.pyz"
    recorded(package)
    if (
        manifest["upgrades"][-1]["source_commit"]
        != manifest["source_commit"]
    ):
        raise PermissionError("latest package upgrade provenance differs")
    excluded = (
        excluded_evidence_root.resolve()
        if excluded_evidence_root is not None
        else None
    )
    recorded_roots = 0
    recorded_paths = 0
    for root in evidence_root.glob("restricted-*"):
        if excluded is not None and root.resolve() == excluded:
            continue
        recorded_roots += 1
        for path in (root, *root.rglob("*")):
            recorded(path)
            recorded_paths += 1
    key_path = (
        SERVICE_ROOT
        / "data"
        / "keys"
        / "key-v1"
        / "authority"
        / "authority-key-v1.bin"
    )
    recorded(key_path)
    if not key_path.is_file():
        raise PermissionError("Authority Service key is unavailable")
    return {
        "source_commit": manifest["source_commit"],
        "package_sha256": hashlib.sha256(package.read_bytes()).hexdigest(),
        "provider_account_sid": identity["sid"],
        "provider_rights": sorted(provider_rights),
        "service_rights": sorted(service_rights),
        "configuration_schema": config["schema_version"],
        "service_key_preserved": True,
        "recorded_restricted_roots": recorded_roots,
        "recorded_restricted_paths": recorded_paths,
        "status": "PASS",
    }


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser()
    result.add_argument("--expected-source-commit", required=True)
    result.add_argument(
        "--evidence-root", type=Path, default=DEFAULT_EVIDENCE_ROOT
    )
    result.add_argument("--exclude-evidence-root", type=Path)
    return result


def main(arguments: Sequence[str] | None = None) -> int:
    options = parser().parse_args(arguments)
    try:
        result = audit(
            options.expected_source_commit,
            options.evidence_root.resolve(strict=True),
            (
                options.exclude_evidence_root.resolve(strict=True)
                if options.exclude_evidence_root is not None
                else None
            ),
        )
    except (
        FileNotFoundError,
        KeyError,
        OSError,
        PermissionError,
        TypeError,
        ValueError,
    ) as error:
        print(f"FAIL: {error}")
        return 2
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
