from __future__ import annotations

import argparse
import ctypes
import json
import threading
from ctypes import wintypes
from pathlib import Path
from typing import Any, Mapping, Sequence

from keeper.authority_service.client import DEFAULT_PIPE_NAME
from keeper.authority_service.core import AuthorityServiceCore
from keeper.executive.founder_capability import (
    ProductionFounderCapabilityVerifier,
)
from keeper.authority_service.ipc_server import NamedPipeAuthorityServer
from keeper.authority_service.observer import ServiceProviderObserver
from keeper.authority_service.provider_host_gateway import ProviderHostGateway
from keeper.authority_service.provider_host_enrollment import (
    ProviderHostEnrollmentCoordinator,
)
from keeper.authority_service.protocol import PROTOCOL_VERSION
from keeper.authority_service.store import SERVICE_SCHEMA_VERSION
from keeper.provider_host.signing import (
    RsaPublicIdentity,
    WindowsCngEnvelopeIdentity,
)
from keeper.provider_host.enrollment import validate_enrollment_receipt
from keeper.authority_service.provenance import AuthorityProvenanceReporter


SERVICE_NAME = "KeeperAuthority"
_SERVICE_WIN32_OWN_PROCESS = 0x10
_SERVICE_STOPPED = 0x1
_SERVICE_START_PENDING = 0x2
_SERVICE_STOP_PENDING = 0x3
_SERVICE_RUNNING = 0x4
_SERVICE_ACCEPT_STOP = 0x1
_SERVICE_CONTROL_STOP = 0x1


class _ServiceStatus(ctypes.Structure):
    _fields_ = [
        ("dwServiceType", wintypes.DWORD),
        ("dwCurrentState", wintypes.DWORD),
        ("dwControlsAccepted", wintypes.DWORD),
        ("dwWin32ExitCode", wintypes.DWORD),
        ("dwServiceSpecificExitCode", wintypes.DWORD),
        ("dwCheckPoint", wintypes.DWORD),
        ("dwWaitHint", wintypes.DWORD),
    ]


_Handler = ctypes.WINFUNCTYPE(
    wintypes.DWORD,
    wintypes.DWORD,
    wintypes.DWORD,
    wintypes.LPVOID,
    wintypes.LPVOID,
)
_ServiceMain = ctypes.WINFUNCTYPE(
    None, wintypes.DWORD, ctypes.POINTER(wintypes.LPWSTR)
)


class _ServiceTableEntry(ctypes.Structure):
    _fields_ = [
        ("lpServiceName", wintypes.LPWSTR),
        ("lpServiceProc", _ServiceMain),
    ]


class AuthorityWindowsService:
    def __init__(self, config_path: Path) -> None:
        self.config_path = config_path.resolve(strict=True)
        self.status_handle = 0
        self.server: NamedPipeAuthorityServer | None = None
        self._handler_callback = _Handler(self._control_handler)
        self._service_callback = _ServiceMain(self._service_main)

    def run_dispatcher(self) -> None:
        table = (_ServiceTableEntry * 2)(
            _ServiceTableEntry(SERVICE_NAME, self._service_callback),
            _ServiceTableEntry(None, _ServiceMain()),
        )
        if not _advapi32().StartServiceCtrlDispatcherW(table):
            raise OSError(
                ctypes.get_last_error(),
                "Keeper Authority service dispatcher failed",
            )

    def run_console(self) -> None:
        self.server = _build_server(self.config_path)
        self.server.serve_forever()

    def _service_main(
        self, argument_count: int, arguments: Any
    ) -> None:
        self.status_handle = int(
            _advapi32().RegisterServiceCtrlHandlerExW(
                SERVICE_NAME, self._handler_callback, None
            )
            or 0
        )
        if not self.status_handle:
            return
        try:
            self._set_status(_SERVICE_START_PENDING, wait_hint=15_000)
            self.server = _build_server(self.config_path)
            self._set_status(_SERVICE_RUNNING, accepts=_SERVICE_ACCEPT_STOP)
            self.server.serve_forever()
            self._set_status(_SERVICE_STOPPED)
        except BaseException:
            self._set_status(_SERVICE_STOPPED, win32_exit=1064)

    def _control_handler(
        self,
        control: int,
        event_type: int,
        event_data: int,
        context: int,
    ) -> int:
        if control == _SERVICE_CONTROL_STOP and self.server is not None:
            self._set_status(_SERVICE_STOP_PENDING, wait_hint=10_000)
            self.server.stop()
            threading.Thread(
                target=_unblock_pipe_accept,
                name="keeper-authority-stop",
                daemon=True,
            ).start()
        return 0

    def _set_status(
        self,
        state: int,
        *,
        accepts: int = 0,
        win32_exit: int = 0,
        wait_hint: int = 0,
    ) -> None:
        if not self.status_handle:
            return
        status = _ServiceStatus(
            _SERVICE_WIN32_OWN_PROCESS,
            state,
            accepts,
            win32_exit,
            0,
            0,
            wait_hint,
        )
        _advapi32().SetServiceStatus(
            self.status_handle, ctypes.byref(status)
        )


def _build_server(config_path: Path) -> NamedPipeAuthorityServer:
    config = _load_config(config_path)
    provider_host_gateway: ProviderHostGateway | None = None
    provider_host = config.get("provider_host")
    if isinstance(provider_host, dict):
        authority_signer = WindowsCngEnvelopeIdentity(
            identity=str(provider_host["authority_id"]),
            key_name=str(provider_host["authority_key_name"]),
            machine_key=True,
        )
        if authority_signer.public_configuration() != provider_host.get(
            "authority_public_identity"
        ):
            raise PermissionError(
                "Authority Provider Host signing identity differs"
            )
        host_verifier = RsaPublicIdentity.from_configuration(
            provider_host["host_public_identity"]
        ).verifier()
        provider_host_gateway = ProviderHostGateway(
            pipe_name=str(provider_host["pipe_name"]),
            authority_id=str(provider_host["authority_id"]),
            host_id=str(provider_host["host_id"]),
            authority_signer=authority_signer,
            host_verifier=host_verifier,
            expected_host_sid=str(provider_host["host_user_sid"]),
            expected_host_session_id=int(provider_host["host_session_id"]),
            expected_host_executable=Path(
                str(provider_host["host_process_executable"])
            ),
            expected_host_executable_sha256=str(
                provider_host["host_process_executable_sha256"]
            ),
            expected_host_profile_path=Path(
                str(provider_host["host_profile_path"])
            ),
            sequence_store=Path(
                str(provider_host["sequence_store"])
            ),
        )
    observer = ServiceProviderObserver(
        Path(config["provider_root"]),
        Path(config["allowed_evidence_root"]),
        str(config["provider_account_name"]),
        Path(config["provider_credential_path"]),
        str(config["authorized_client_sid"]),
        provider_host_gateway,
    )
    verifier_config = config.get("founder_capability_verifier")
    verifier = (
        ProductionFounderCapabilityVerifier(verifier_config)
        if isinstance(verifier_config, dict)
        else None
    )
    core = AuthorityServiceCore(
        Path(config["service_root"]),
        observer=observer,
        provenance_reporter=AuthorityProvenanceReporter(
            config_path.parent.parent,
            config_path,
        ),
        founder_capability_verifier=verifier,
    )
    if provider_host_gateway is not None:
        enrollment = provider_host_gateway.enrollment_record()
        enrollment_id = str(enrollment["enrollment_id"])
        existing = core.store.get("provider_host_enrollments", enrollment_id)
        if existing is None:
            core.store.insert(
                "provider_host_enrollments",
                enrollment_id,
                "ACTIVE",
                enrollment,
            )
        else:
            existing.pop("service_state", None)
            if existing != enrollment:
                raise PermissionError(
                    "Provider Host protected enrollment differs from durable state"
                )
    elif verifier is not None:
        authority_id = "keeper-authority-provider-host:" + core.keys.current_key_id
        authority_signer = WindowsCngEnvelopeIdentity(
            identity=authority_id,
            key_name="DarkSage.KeeperAuthority.ProviderHost.v1",
            machine_key=True,
        )

        def activate_provider_host(record: Mapping[str, Any]) -> None:
            proposal_record = _mapping(record.get("proposal"), "stored Host proposal")
            proposal = _mapping(proposal_record.get("payload"), "stored Host proposal payload")
            receipt_record = _mapping(record.get("receipt"), "stored Host receipt")
            receipt_unsigned = _mapping(
                receipt_record.get("payload"), "stored Host receipt payload"
            )
            receipt = validate_enrollment_receipt(
                receipt_record,
                authority_signer,
                expected_enrollment_id=str(receipt_unsigned.get("enrollment_id", "")),
            )
            if (
                receipt.get("service_key_id") != core.keys.current_key_id
                or receipt.get("authority_protocol_version") != PROTOCOL_VERSION
                or receipt.get("authority_schema_version") != SERVICE_SCHEMA_VERSION
            ):
                raise PermissionError("Provider Host enrollment service identity differs")
            runtime = _mapping(
                receipt.get("runtime_configuration"), "Host runtime configuration"
            )
            installation = _mapping(
                proposal.get("installation"), "Host installation binding"
            )
            binding = _mapping(proposal.get("user_binding"), "Host user binding")
            host_public = _mapping(
                proposal.get("host_public_identity"), "Host public identity"
            )
            gateway = ProviderHostGateway(
                pipe_name=str(runtime["pipe_name"]),
                authority_id=authority_id,
                host_id=str(proposal["host_id"]),
                authority_signer=authority_signer,
                host_verifier=RsaPublicIdentity.from_configuration(
                    host_public
                ).verifier(),
                expected_host_sid=str(binding["user_sid"]),
                expected_host_session_id=int(binding["session_id"]),
                expected_host_executable=Path(str(installation["executable_path"])),
                expected_host_executable_sha256=str(
                    installation["executable_sha256"]
                ),
                expected_host_profile_path=Path(str(binding["profile_path"])),
                sequence_store=core.root / "provider-host-gateway-sequences.db",
            )
            observer.provider_host_gateway = gateway

        def deactivate_provider_host(record: Mapping[str, Any]) -> None:
            observer.provider_host_gateway = None

        core.configure_provider_host_enrollment(
            ProviderHostEnrollmentCoordinator(
                store=core.store,
                service_key_id=core.keys.current_key_id,
                authority_protocol_version=PROTOCOL_VERSION,
                authority_schema_version=SERVICE_SCHEMA_VERSION,
                founder_verifier=verifier,
                authority_signer=authority_signer,
                authority_public_identity=authority_signer.public_configuration(),
                proposal_observer=observer,
                activate=activate_provider_host,
                deactivate=deactivate_provider_host,
            )
        )
    return NamedPipeAuthorityServer(
        core,
        str(config["authorized_client_sid"]),
        pipe_name=str(config.get("pipe_name", DEFAULT_PIPE_NAME)),
    )


def _load_config(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise PermissionError("Authority Service configuration is unavailable") from error
    common = {
        "schema_version",
        "service_name",
        "service_root",
        "provider_root",
        "allowed_evidence_root",
        "authorized_client_sid",
        "provider_account_name",
        "provider_credential_path",
        "pipe_name",
    }
    schema_version = value.get("schema_version") if isinstance(value, dict) else None
    expected = common | (
        {"founder_capability_verifier"} if schema_version in {3, 4} else set()
    ) | ({"provider_host"} if schema_version == 4 else set())
    if (
        not isinstance(value, dict)
        or schema_version not in {2, 3, 4}
        or set(value) != expected
        or value.get("service_name") != SERVICE_NAME
        or any(
            not isinstance(value.get(key), str) or not value[key]
            for key in common - {"schema_version"}
        )
        or (
            schema_version in {3, 4}
            and not isinstance(value.get("founder_capability_verifier"), dict)
        )
        or (
            schema_version == 4
            and not _valid_provider_host_configuration(
                value.get("provider_host")
            )
        )
    ):
        raise PermissionError("Authority Service configuration is invalid")
    return value


def _valid_provider_host_configuration(value: object) -> bool:
    fields = {
        "schema_version",
        "authority_id",
        "authority_key_name",
        "authority_public_identity",
        "host_id",
        "host_process_executable",
        "host_process_executable_sha256",
        "host_profile_path",
        "host_public_identity",
        "host_session_id",
        "host_user_sid",
        "pipe_name",
        "sequence_store",
    }
    return (
        isinstance(value, dict)
        and set(value) == fields
        and value.get("schema_version") == 1
        and isinstance(value.get("authority_public_identity"), dict)
        and isinstance(value.get("host_public_identity"), dict)
        and isinstance(value.get("host_session_id"), int)
        and not isinstance(value.get("host_session_id"), bool)
        and value["host_session_id"] >= 0
        and all(
            isinstance(value.get(name), str) and value[name]
            for name in fields
            - {
                "schema_version",
                "authority_public_identity",
                "host_public_identity",
                "host_session_id",
            }
        )
    )


def _mapping(value: object, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise PermissionError(f"Provider Host {label} is invalid")
    return dict(value)


def _unblock_pipe_accept() -> None:
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateFileW.restype = wintypes.HANDLE
    handle = kernel32.CreateFileW(
        DEFAULT_PIPE_NAME, 0xC0000000, 0, None, 3, 0, None
    )
    if handle not in {None, ctypes.c_void_p(-1).value}:
        kernel32.CloseHandle(handle)


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(prog="keeper-authority")
    result.add_argument("mode", choices=("service", "console"))
    result.add_argument("--config", type=Path, required=True)
    return result


def main(arguments: Sequence[str] | None = None) -> int:
    values = list(arguments) if arguments is not None else None
    if values is None:
        import sys

        values = sys.argv[1:]
    if values and values[0] == "codex-probe":
        from keeper.authority_service.codex_probe import main as probe_main

        return probe_main(values[1:])
    if values and values[0] == "codex-register-once":
        from keeper.authority_service.codex_registration import (
            main as registration_main,
        )

        return registration_main(values[1:])
    options = parser().parse_args(values)
    host = AuthorityWindowsService(options.config)
    if options.mode == "service":
        host.run_dispatcher()
    else:
        host.run_console()
    return 0


def _advapi32() -> Any:
    advapi32: Any = ctypes.WinDLL("advapi32", use_last_error=True)
    advapi32.StartServiceCtrlDispatcherW.argtypes = [
        ctypes.POINTER(_ServiceTableEntry)
    ]
    advapi32.StartServiceCtrlDispatcherW.restype = wintypes.BOOL
    advapi32.RegisterServiceCtrlHandlerExW.argtypes = [
        wintypes.LPCWSTR,
        _Handler,
        wintypes.LPVOID,
    ]
    advapi32.RegisterServiceCtrlHandlerExW.restype = wintypes.HANDLE
    advapi32.SetServiceStatus.argtypes = [
        wintypes.HANDLE,
        ctypes.POINTER(_ServiceStatus),
    ]
    advapi32.SetServiceStatus.restype = wintypes.BOOL
    return advapi32


if __name__ == "__main__":
    raise SystemExit(main())
