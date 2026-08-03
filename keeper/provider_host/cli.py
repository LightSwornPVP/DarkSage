from __future__ import annotations

import argparse
import hashlib
import json
import secrets
import sys
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from keeper.authority_service.client import ProductionAuthorityServiceClient
from keeper.authority_service.core import SERVICE_VERSION
from keeper.authority_service.protocol import PROTOCOL_VERSION
from keeper.authority_service.store import SERVICE_SCHEMA_VERSION
from keeper.executive.founder_auth import ProductionFounderAuthenticator
from keeper.provider_host.bootstrap import build_production_bootstrap
from keeper.provider_host.enrollment_client import ProviderHostEnrollmentClient
from keeper.provider_host.identity import PipePeerIdentity, UserBinding, current_user_binding
from keeper.provider_host.enrollment import (
    validate_enrollment_receipt,
    validate_enrollment_revocation,
)
from keeper.provider_host.install import ProviderHostInstaller
from keeper.provider_host.protocol import structured_digest
from keeper.provider_host.replay_store import ProviderHostStore
from keeper.provider_host.runtime import HostIdentity, KeeperProviderHost, ProviderBinding
from keeper.provider_host.server import ProviderHostServer
from keeper.provider_host.signing import RsaPublicIdentity, WindowsCngEnvelopeIdentity
from keeper.provider_host.windows_process import (
    CodexSetupRunner,
    ProviderProcessLauncher,
)


_enrollment_client_factory: Callable[[], ProviderHostEnrollmentClient] | None = None


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(prog="keeper provider-host")
    commands = result.add_subparsers(dest="provider_host_command", required=True)
    run = commands.add_parser("run")
    run.add_argument("--config", type=Path, required=True)
    status = commands.add_parser("status")
    status.add_argument("--config", type=Path, required=True)
    for name in ("install", "repair", "update"):
        command = commands.add_parser(name)
        command.add_argument("--install-root", type=Path, required=True)
        command.add_argument("--startup-root", type=Path, required=True)
        command.add_argument("--artifact", type=Path, required=True)
        command.add_argument("--version", required=True)
        command.add_argument("--package-sha256", required=True)
    rollback = commands.add_parser("rollback")
    rollback.add_argument("--install-root", type=Path, required=True)
    rollback.add_argument("--startup-root", type=Path, required=True)
    uninstall = commands.add_parser("uninstall-preserve")
    uninstall.add_argument("--install-root", type=Path, required=True)
    uninstall.add_argument("--startup-root", type=Path, required=True)
    commands.add_parser("enrollment-status")
    enroll = commands.add_parser("enroll")
    enroll.add_argument("--generation", type=int, required=True)
    commands.add_parser("resume-enrollment")
    commands.add_parser("reconcile-enrollment")
    expired = commands.add_parser("reconcile-expired-enrollment")
    expired.add_argument("--enrollment-id", required=True)
    revoke = commands.add_parser("revoke-enrollment")
    revoke.add_argument("--enrollment-id", required=True)
    revoke.add_argument("--receipt-digest", required=True)
    revoke.add_argument("--generation", type=int, required=True)
    return result


def main(arguments: Sequence[str] | None = None) -> int:
    options = parser().parse_args(arguments)
    try:
        command = str(options.provider_host_command)
        if command in {"run", "status"}:
            config_path = options.config.resolve()
            if not config_path.is_file():
                print(
                    json.dumps(
                        {
                            "installed": True,
                            "online": False,
                            "state": "INSTALLED_UNENROLLED",
                            "provider_state": "NO_QUALIFIED_PROVIDERS",
                            "founder_action_required": "ENROLL_PROVIDER_HOST",
                        },
                        indent=2,
                        sort_keys=True,
                    )
                )
                return 0
            revoked = _revoked_status(config_path)
            if revoked is not None:
                print(json.dumps(revoked, indent=2, sort_keys=True))
                return 0
            runtime, server = _build_runtime(config_path.resolve(strict=True))
            recovered = runtime.start()
            if command == "status":
                print(json.dumps({**runtime.status(), "recovered_uncertain": recovered}, indent=2, sort_keys=True))
                return 0
            server.serve_forever()
            runtime.logoff()
            return 0
        if command == "enrollment-status":
            authority = ProductionAuthorityServiceClient()
            identity = authority.require_live_identity()
            status_value = {
                "authority_identity": {
                    "protocol_version": identity["protocol_version"],
                    "schema_version": identity["schema_version"],
                    "service_key_id": identity["service_key_id"],
                    "service_version": identity["service_version"],
                },
                "enrollment": authority.provider_host_enrollment_status(),
            }
            print(json.dumps(status_value, indent=2, sort_keys=True))
            return 0
        if command in {
            "enroll",
            "resume-enrollment",
            "reconcile-enrollment",
            "reconcile-expired-enrollment",
            "revoke-enrollment",
        }:
            client = _production_enrollment_client()
            if command == "enroll":
                enrollment_value = client.enroll(generation=options.generation)
            elif command == "resume-enrollment":
                enrollment_value = client.resume_authorization()
            elif command == "reconcile-enrollment":
                enrollment_value = client.reconcile()
            elif command == "reconcile-expired-enrollment":
                enrollment_value = client.reconcile_expired(options.enrollment_id)
            else:
                enrollment_value = client.revoke(
                    enrollment_id=options.enrollment_id,
                    receipt_digest=options.receipt_digest,
                    generation=options.generation,
                )
            print(json.dumps(enrollment_value, indent=2, sort_keys=True))
            return 0
        installer = ProviderHostInstaller(
            options.install_root, options.startup_root
        )
        if command == "install":
            lifecycle_value: object = installer.install(
                options.artifact,
                version=options.version,
                expected_package_sha256=options.package_sha256,
            )
        elif command == "repair":
            lifecycle_value = installer.repair(
                options.artifact,
                expected_package_sha256=options.package_sha256,
            )
        elif command == "update":
            lifecycle_value = installer.update(
                options.artifact,
                version=options.version,
                expected_package_sha256=options.package_sha256,
                drain=lambda: None,
            )
        elif command == "rollback":
            lifecycle_value = installer.rollback(drain=lambda: None)
        elif command == "uninstall-preserve":
            lifecycle_value = installer.uninstall_preserving_data(drain=lambda: None)
        else:
            raise ValueError("Provider Host command is unsupported")
        print(json.dumps(_json_value(lifecycle_value), indent=2, sort_keys=True))
        return 0
    except (FileNotFoundError, OSError, PermissionError, RuntimeError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2


def _production_enrollment_client() -> ProviderHostEnrollmentClient:
    if _enrollment_client_factory is not None:
        return _enrollment_client_factory()
    authority = ProductionAuthorityServiceClient()
    diagnostics = authority.require_live_identity()
    _validate_authority_compatibility(diagnostics)
    binding = current_user_binding()
    if str(diagnostics.get("client_sid", "")).casefold() != binding.user_sid.casefold():
        raise PermissionError("Provider Host enrollment client identity differs")
    profile = Path(binding.profile_path).resolve(strict=True)
    installer = ProviderHostInstaller(
        profile
        / "AppData"
        / "Local"
        / "Programs"
        / "DarkSage"
        / "KeeperProviderHost",
        profile
        / "AppData"
        / "Roaming"
        / "Microsoft"
        / "Windows"
        / "Start Menu"
        / "Programs"
        / "Startup",
        owner_sid=binding.user_sid,
    )
    bootstrap = build_production_bootstrap(installer, diagnostics)
    authenticator = ProductionFounderAuthenticator(
        installer.state / "founder-auth" / "proof-key.dpapi"
    )
    return ProviderHostEnrollmentClient(
        authority=authority,
        authenticator=authenticator,
        bootstrap=bootstrap,
    )


def _validate_authority_compatibility(
    diagnostics: Mapping[str, object],
) -> None:
    if (
        diagnostics.get("service_version") != SERVICE_VERSION
        or diagnostics.get("protocol_version") != PROTOCOL_VERSION
        or diagnostics.get("schema_version") != SERVICE_SCHEMA_VERSION
    ):
        raise PermissionError(
            "Provider Host enrollment requires the exact matching KeeperAuthority"
        )


def _build_runtime(config_path: Path) -> tuple[KeeperProviderHost, ProviderHostServer]:
    config = _config(config_path)
    binding_value = _object(config["user_binding"], "user binding")
    binding = UserBinding(
        str(binding_value["user_sid"]),
        int(binding_value["session_id"]),
        str(Path(str(binding_value["profile_path"])).resolve(strict=True)),
    )
    if current_user_binding() != binding:
        raise PermissionError("Provider Host configured user binding differs")
    state_root = Path(str(config["state_root"])).resolve()
    output_root = Path(str(config["output_root"])).resolve()
    provider: ProviderBinding | None = None
    provider_value = config.get("provider_binding")
    if provider_value is not None:
        provider_mapping = _object(provider_value, "provider binding")
        provider = ProviderBinding.from_mapping(provider_mapping)
    host_signer = WindowsCngEnvelopeIdentity(
        identity=str(config["host_id"]),
        key_name=str(config["host_key_name"]),
        machine_key=False,
        owner_sid=binding.user_sid,
    )
    if host_signer.public_configuration() != _object(
        config["host_public_identity"], "host public identity"
    ):
        raise PermissionError("Provider Host enrolled key identity differs")
    authority_verifier = RsaPublicIdentity.from_configuration(
        _object(config["authority_public_identity"], "Authority public identity")
    ).verifier()
    store = ProviderHostStore(state_root / "provider-host.db")
    runtime = KeeperProviderHost(
        identity=HostIdentity(
            str(config["host_id"]), str(config["authority_id"]), binding
        ),
        observed_binding=current_user_binding,
        authority_verifier=authority_verifier,
        host_signer=host_signer,
        store=store,
        provider_binding=provider,
        environment_attestation_key=secrets.token_bytes(32),
    )
    authority_peer_value = _object(config["authority_peer"], "Authority peer")
    authority_path = Path(str(authority_peer_value["executable_path"])).resolve(strict=True)
    authority_digest = hashlib.sha256(authority_path.read_bytes()).hexdigest()
    authority_stat = authority_path.stat()
    authority_identity = {
        "device_id": int(authority_stat.st_dev),
        "file_id": int(authority_stat.st_ino),
        "modified_ns": int(authority_stat.st_mtime_ns),
        "schema_version": 1,
        "size": int(authority_stat.st_size),
    }
    if (
        authority_digest != authority_peer_value["executable_sha256"]
        or authority_identity
        != _object(
            authority_peer_value["executable_file_identity"],
            "Authority executable file identity",
        )
    ):
        raise PermissionError("Provider Host Authority executable changed")
    server = ProviderHostServer(
        pipe_name=str(config["pipe_name"]),
        runtime=runtime,
        launcher=ProviderProcessLauncher(output_root),
        setup_runner=CodexSetupRunner(output_root / "setup"),
        authority_verifier=authority_verifier,
        host_signer=host_signer,
        store=store,
        authority_peer=PipePeerIdentity(
            0,
            int(authority_peer_value["session_id"]),
            str(authority_peer_value["user_sid"]),
            str(authority_path),
            authority_digest,
        ),
        authority_executable=authority_path,
        authority_executable_sha256=authority_digest,
    )
    return runtime, server


def _config(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise PermissionError("Provider Host configuration is unavailable") from error
    signed_receipt = isinstance(value, dict) and "signature" in value
    if signed_receipt:
        unsigned = _object(value.get("payload"), "enrollment receipt payload")
        runtime_value = _object(
            unsigned.get("runtime_configuration"), "runtime configuration"
        )
        public = _object(
            runtime_value.get("authority_public_identity"),
            "Authority public identity",
        )
        verifier = RsaPublicIdentity.from_configuration(public).verifier()
        receipt = validate_enrollment_receipt(
            value,
            verifier,
            expected_enrollment_id=str(unsigned.get("enrollment_id", "")),
        )
        value = _object(receipt["runtime_configuration"], "runtime configuration")
    common = {
        "schema_version",
        "authority_id",
        "authority_peer",
        "authority_public_identity",
        "enrollment_id",
        "host_id",
        "host_key_name",
        "host_public_identity",
        "output_root",
        "pipe_name",
        "state_root",
        "user_binding",
    }
    schema = value.get("schema_version") if isinstance(value, dict) else None
    expected = common
    if (
        not isinstance(value, dict)
        or set(value) != expected
        or schema != 2
        or not signed_receipt
    ):
        raise PermissionError("Provider Host configuration is invalid")
    return value


def _revoked_status(receipt_path: Path) -> dict[str, Any] | None:
    revocation_path = receipt_path.parent / "provider-host-enrollment-revoked.json"
    if not revocation_path.is_file():
        return None
    try:
        receipt_record = _object(
            json.loads(receipt_path.read_text(encoding="utf-8")),
            "enrollment receipt",
        )
        receipt_payload = _object(
            receipt_record.get("payload"), "enrollment receipt payload"
        )
        runtime = _object(
            receipt_payload.get("runtime_configuration"),
            "runtime configuration",
        )
        public = _object(
            runtime.get("authority_public_identity"), "Authority public identity"
        )
        revocation_record = _object(
            json.loads(revocation_path.read_text(encoding="utf-8")),
            "enrollment revocation",
        )
    except (OSError, json.JSONDecodeError) as error:
        raise PermissionError(
            "Provider Host revocation state is unavailable"
        ) from error
    verifier = RsaPublicIdentity.from_configuration(public).verifier()
    revocation = validate_enrollment_revocation(
        revocation_record,
        verifier,
        expected_enrollment_id=str(receipt_payload.get("enrollment_id", "")),
        expected_receipt_digest=structured_digest(receipt_record),
    )
    return {
        "enrollment_id": revocation["enrollment_id"],
        "founder_action_required": "CREATE_NEW_PROVIDER_HOST_ENROLLMENT",
        "installed": True,
        "online": False,
        "provider_state": "UNAVAILABLE",
        "state": "REVOKED",
    }


def _object(value: object, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise PermissionError(f"Provider Host {label} is invalid")
    return dict(value)


def _json_value(value: object) -> object:
    if hasattr(value, "__dataclass_fields__"):
        return {
            name: getattr(value, name)
            for name in value.__dataclass_fields__
        }
    return value


if __name__ == "__main__":
    raise SystemExit(main())
