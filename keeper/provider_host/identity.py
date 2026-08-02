from __future__ import annotations

import ctypes
import hashlib
import os
from ctypes import wintypes
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from keeper.authority_service.windows_identity import current_process_sid, process_sid


_PROCESS_QUERY_LIMITED_INFORMATION = 0x1000


@dataclass(frozen=True, slots=True)
class UserBinding:
    user_sid: str
    session_id: int
    profile_path: str

    def as_dict(self) -> dict[str, object]:
        return {
            "profile_path": self.profile_path,
            "session_id": self.session_id,
            "user_sid": self.user_sid,
        }


@dataclass(frozen=True, slots=True)
class PipePeerIdentity:
    process_id: int
    session_id: int
    user_sid: str
    executable_path: str
    executable_sha256: str


def current_user_binding() -> UserBinding:
    if os.name != "nt":
        raise RuntimeError("Provider Host identity requires Windows")
    session = wintypes.DWORD()
    kernel32 = _kernel32()
    process_id = int(kernel32.GetCurrentProcessId())
    if not kernel32.ProcessIdToSessionId(process_id, ctypes.byref(session)):
        raise PermissionError("Provider Host Windows session is unavailable")
    profile = Path(os.environ["USERPROFILE"]).resolve(strict=True)
    return UserBinding(current_process_sid(), int(session.value), str(profile))


def require_same_binding(expected: UserBinding, observed: UserBinding) -> None:
    if (
        expected.user_sid.casefold() != observed.user_sid.casefold()
        or expected.session_id != observed.session_id
        or os.path.normcase(expected.profile_path)
        != os.path.normcase(observed.profile_path)
    ):
        raise PermissionError("Provider Host SID/session/profile binding differs")


def named_pipe_server_identity(pipe: int) -> PipePeerIdentity:
    """Authenticate the local process serving a connected host pipe."""

    return _named_pipe_peer_identity(pipe, server=True)


def named_pipe_client_identity(pipe: int) -> PipePeerIdentity:
    """Authenticate the local process connected to a host pipe server."""

    return _named_pipe_peer_identity(pipe, server=False)


def require_peer_identity(
    observed: PipePeerIdentity,
    *,
    process_id: int | None = None,
    session_id: int,
    user_sid: str,
    executable_path: Path,
    executable_sha256: str,
) -> None:
    canonical = executable_path.resolve(strict=True)
    if (
        (process_id is not None and observed.process_id != process_id)
        or observed.session_id != session_id
        or observed.user_sid.casefold() != user_sid.casefold()
        or os.path.normcase(observed.executable_path)
        != os.path.normcase(str(canonical))
        or observed.executable_sha256 != executable_sha256
    ):
        raise PermissionError("Provider Host pipe peer identity differs")


def measured_process_identity(process_id: int) -> PipePeerIdentity:
    if os.name != "nt" or process_id <= 0:
        raise PermissionError("Provider Host peer process is invalid")
    kernel32 = _kernel32()
    process = kernel32.OpenProcess(
        _PROCESS_QUERY_LIMITED_INFORMATION, False, process_id
    )
    if not process:
        raise PermissionError(
            "Provider Host peer process cannot be opened: "
            f"{ctypes.get_last_error()}"
        )
    try:
        session = wintypes.DWORD()
        if not kernel32.ProcessIdToSessionId(process_id, ctypes.byref(session)):
            raise PermissionError("Provider Host peer session is unavailable")
        capacity = wintypes.DWORD(32768)
        buffer = ctypes.create_unicode_buffer(capacity.value)
        if not kernel32.QueryFullProcessImageNameW(
            process, 0, buffer, ctypes.byref(capacity)
        ):
            raise PermissionError("Provider Host peer executable is unavailable")
        executable = Path(buffer.value).resolve(strict=True)
        digest = hashlib.sha256(executable.read_bytes()).hexdigest()
        return PipePeerIdentity(
            process_id=process_id,
            session_id=int(session.value),
            user_sid=process_sid(process_id),
            executable_path=str(executable),
            executable_sha256=digest,
        )
    finally:
        if not kernel32.CloseHandle(process):
            raise PermissionError("Provider Host peer process handle did not close")


def _named_pipe_peer_identity(pipe: int, *, server: bool) -> PipePeerIdentity:
    if os.name != "nt" or pipe <= 0:
        raise PermissionError("Provider Host pipe handle is invalid")
    kernel32 = _kernel32()
    process_id = wintypes.ULONG()
    operation = (
        kernel32.GetNamedPipeServerProcessId
        if server
        else kernel32.GetNamedPipeClientProcessId
    )
    if not operation(wintypes.HANDLE(pipe), ctypes.byref(process_id)):
        raise PermissionError(
            "Provider Host pipe peer process is unavailable: "
            f"{ctypes.get_last_error()}"
        )
    first = int(process_id.value)
    observed = measured_process_identity(first)
    check = wintypes.ULONG()
    if not operation(wintypes.HANDLE(pipe), ctypes.byref(check)) or int(
        check.value
    ) != first:
        raise PermissionError("Provider Host pipe peer changed during validation")
    return observed


def _kernel32() -> Any:
    if os.name != "nt":
        raise RuntimeError("Provider Host identity requires Windows")
    api = ctypes.WinDLL("kernel32", use_last_error=True)
    api.GetCurrentProcessId.restype = wintypes.DWORD
    api.ProcessIdToSessionId.argtypes = [
        wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD),
    ]
    api.ProcessIdToSessionId.restype = wintypes.BOOL
    api.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    api.OpenProcess.restype = wintypes.HANDLE
    api.QueryFullProcessImageNameW.argtypes = [
        wintypes.HANDLE,
        wintypes.DWORD,
        wintypes.LPWSTR,
        ctypes.POINTER(wintypes.DWORD),
    ]
    api.QueryFullProcessImageNameW.restype = wintypes.BOOL
    api.GetNamedPipeServerProcessId.argtypes = [
        wintypes.HANDLE,
        ctypes.POINTER(wintypes.ULONG),
    ]
    api.GetNamedPipeServerProcessId.restype = wintypes.BOOL
    api.GetNamedPipeClientProcessId.argtypes = [
        wintypes.HANDLE,
        ctypes.POINTER(wintypes.ULONG),
    ]
    api.GetNamedPipeClientProcessId.restype = wintypes.BOOL
    api.CloseHandle.argtypes = [wintypes.HANDLE]
    api.CloseHandle.restype = wintypes.BOOL
    return api
