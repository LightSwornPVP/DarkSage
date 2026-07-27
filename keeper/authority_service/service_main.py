from __future__ import annotations

import argparse
import ctypes
import json
import threading
from ctypes import wintypes
from pathlib import Path
from typing import Any, Sequence

from keeper.authority_service.client import DEFAULT_PIPE_NAME
from keeper.authority_service.core import AuthorityServiceCore
from keeper.authority_service.ipc_server import NamedPipeAuthorityServer
from keeper.authority_service.observer import ServiceProviderObserver


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
    observer = ServiceProviderObserver(
        Path(config["provider_root"]),
        Path(config["allowed_evidence_root"]),
    )
    core = AuthorityServiceCore(Path(config["service_root"]), observer=observer)
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
    required = {
        "schema_version",
        "service_name",
        "service_root",
        "provider_root",
        "allowed_evidence_root",
        "authorized_client_sid",
        "pipe_name",
    }
    if (
        not isinstance(value, dict)
        or set(value) != required
        or value.get("schema_version") != 1
        or value.get("service_name") != SERVICE_NAME
        or any(
            not isinstance(value.get(key), str) or not value[key]
            for key in required - {"schema_version"}
        )
    ):
        raise PermissionError("Authority Service configuration is invalid")
    return value


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
    options = parser().parse_args(arguments)
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
