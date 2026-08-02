from __future__ import annotations

import argparse
import hashlib
import json
import secrets
import sys
from pathlib import Path
from typing import Any, Sequence

from keeper.provider_host.identity import PipePeerIdentity, UserBinding, current_user_binding
from keeper.provider_host.install import ProviderHostInstaller
from keeper.provider_host.replay_store import ProviderHostStore
from keeper.provider_host.runtime import HostIdentity, KeeperProviderHost, ProviderBinding
from keeper.provider_host.server import ProviderHostServer
from keeper.provider_host.signing import RsaPublicIdentity, WindowsCngEnvelopeIdentity
from keeper.provider_host.windows_process import (
    CodexSetupRunner,
    ProviderProcessLauncher,
)


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
    return result


def main(arguments: Sequence[str] | None = None) -> int:
    options = parser().parse_args(arguments)
    try:
        command = str(options.provider_host_command)
        if command in {"run", "status"}:
            runtime, server = _build_runtime(options.config.resolve(strict=True))
            recovered = runtime.start()
            if command == "status":
                print(json.dumps({**runtime.status(), "recovered_uncertain": recovered}, indent=2, sort_keys=True))
                return 0
            server.serve_forever()
            runtime.logoff()
            return 0
        installer = ProviderHostInstaller(
            options.install_root, options.startup_root
        )
        if command == "install":
            value: object = installer.install(
                options.artifact,
                version=options.version,
                expected_package_sha256=options.package_sha256,
            )
        elif command == "repair":
            value = installer.repair(
                options.artifact,
                expected_package_sha256=options.package_sha256,
            )
        elif command == "update":
            value = installer.update(
                options.artifact,
                version=options.version,
                expected_package_sha256=options.package_sha256,
                drain=lambda: None,
            )
        elif command == "rollback":
            value = installer.rollback(drain=lambda: None)
        elif command == "uninstall-preserve":
            value = installer.uninstall_preserving_data(drain=lambda: None)
        else:
            raise ValueError("Provider Host command is unsupported")
        print(json.dumps(_json_value(value), indent=2, sort_keys=True))
        return 0
    except (FileNotFoundError, OSError, PermissionError, RuntimeError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2


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
    provider_value = _object(config["provider_binding"], "provider binding")
    provider = ProviderBinding(
        provider_id=str(provider_value["provider_id"]),
        account_id=str(provider_value["account_id"]),
        session_id=str(provider_value["session_id"]),
        registration_id=str(provider_value["registration_id"]),
        qualification_id=str(provider_value["qualification_id"]),
        executable_path=str(Path(str(provider_value["executable_path"])).resolve(strict=True)),
        executable_sha256=str(provider_value["executable_sha256"]),
        executable_size=int(provider_value["executable_size"]),
        file_identity=_object(provider_value["file_identity"], "file identity"),
        authenticode_binding=_object(provider_value["authenticode_binding"], "Authenticode binding"),
        publisher=str(provider_value["publisher"]),
        version=str(provider_value["version"]),
        models=tuple(str(item) for item in _list(provider_value["models"], "models")),
        efforts=tuple(str(item) for item in _list(provider_value["efforts"], "efforts")),
    )
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
    if authority_digest != authority_peer_value["executable_sha256"]:
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
    expected = {
        "schema_version",
        "authority_id",
        "authority_peer",
        "authority_public_identity",
        "host_id",
        "host_key_name",
        "host_public_identity",
        "output_root",
        "pipe_name",
        "provider_binding",
        "state_root",
        "user_binding",
    }
    if not isinstance(value, dict) or set(value) != expected or value.get("schema_version") != 1:
        raise PermissionError("Provider Host configuration is invalid")
    return value


def _object(value: object, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise PermissionError(f"Provider Host {label} is invalid")
    return dict(value)


def _list(value: object, label: str) -> list[object]:
    if not isinstance(value, list) or not value:
        raise PermissionError(f"Provider Host {label} is invalid")
    return list(value)


def _json_value(value: object) -> object:
    if hasattr(value, "__dataclass_fields__"):
        return {
            name: getattr(value, name)
            for name in value.__dataclass_fields__
        }
    return value


if __name__ == "__main__":
    raise SystemExit(main())
