from __future__ import annotations

import ctypes
import os
from contextlib import contextmanager
from ctypes import wintypes
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator


TOKEN_QUERY = 0x0008
TOKEN_DUPLICATE = 0x0002
TOKEN_USER = 1
TOKEN_INTEGRITY_LEVEL = 25
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
STILL_ACTIVE = 259
ERROR_ACCESS_DENIED = 5
ERROR_PIPE_LOCAL = 229


class _SidAndAttributes(ctypes.Structure):
    _fields_ = [("Sid", wintypes.LPVOID), ("Attributes", wintypes.DWORD)]


class _TokenUser(ctypes.Structure):
    _fields_ = [("User", _SidAndAttributes)]


class _TokenMandatoryLabel(ctypes.Structure):
    _fields_ = [("Label", _SidAndAttributes)]


@dataclass(frozen=True, slots=True)
class WindowsTokenIdentity:
    sid: str
    restricted: bool
    integrity_rid: int


@dataclass(frozen=True, slots=True)
class NamedPipeClientProcessIdentity:
    process_id: int
    session_id: int
    sid: str
    computer_name: str


class NamedPipeClientProcessBinding:
    """Retain and repeatedly authenticate the process behind one pipe instance."""

    def __init__(
        self,
        pipe: int,
        process: int,
        process_token: int,
        identity: NamedPipeClientProcessIdentity,
    ) -> None:
        self.pipe = pipe
        self.process = process
        self.process_token = process_token
        self.identity = identity
        self._released = False

    @property
    def profile_token(self) -> int:
        if self._released or self.process_token <= 0:
            raise PermissionError("authority client process token is released")
        return self.process_token

    def revalidate(self, expected_sid: str) -> NamedPipeClientProcessIdentity:
        if self._released:
            raise PermissionError("authority client process binding is released")
        current = _inspect_bound_named_pipe_client(
            self.pipe, self.process, self.process_token
        )
        if current != self.identity:
            raise PermissionError("authority client process identity changed")
        if current.sid.casefold() != expected_sid.casefold():
            raise PermissionError("authority client process SID is mismatched")
        return current

    def release(self) -> None:
        if self._released:
            return
        failures: list[str] = []
        kernel32 = _kernel32()
        for label, handle in (
            ("process-token", self.process_token),
            ("process", self.process),
        ):
            if handle > 0 and not kernel32.CloseHandle(wintypes.HANDLE(handle)):
                failures.append(f"{label}:{ctypes.get_last_error()}")
        self.process_token = 0
        self.process = 0
        self._released = True
        if failures:
            raise PermissionError(
                "authority client process binding cleanup failed: "
                + ",".join(failures)
            )


@contextmanager
def authenticated_named_pipe_client_process(
    pipe: int, expected_sid: str
) -> Iterator[NamedPipeClientProcessBinding]:
    """Bind a local pipe peer to a retained process handle and token identity."""
    if os.name != "nt":
        raise RuntimeError("Windows identity is unavailable")
    process_id = _named_pipe_client_process_id(pipe)
    process = _kernel32().OpenProcess(
        PROCESS_QUERY_LIMITED_INFORMATION, False, process_id
    )
    if not process:
        raise PermissionError(
            "authority client process cannot be inspected: "
            f"{ctypes.get_last_error()}"
        )
    process_token = 0
    binding: NamedPipeClientProcessBinding | None = None
    try:
        process_value = _handle_value(process)
        process_token = _open_process_token(
            process_value, TOKEN_QUERY | TOKEN_DUPLICATE
        )
        identity = _inspect_bound_named_pipe_client(
            pipe, process_value, process_token
        )
        if identity.process_id != process_id:
            raise PermissionError("authority client process ID changed")
        if identity.sid.casefold() != expected_sid.casefold():
            raise PermissionError("authority client process SID is mismatched")
        binding = NamedPipeClientProcessBinding(
            pipe, process_value, process_token, identity
        )
        binding.revalidate(expected_sid)
        yield binding
    finally:
        if binding is None:
            failures: list[str] = []
            kernel32 = _kernel32()
            if process_token > 0 and not kernel32.CloseHandle(
                wintypes.HANDLE(process_token)
            ):
                failures.append(f"process-token:{ctypes.get_last_error()}")
            if not kernel32.CloseHandle(process):
                failures.append(f"process:{ctypes.get_last_error()}")
            if failures:
                raise PermissionError(
                    "authority client process binding cleanup failed: "
                    + ",".join(failures)
                )
        else:
            binding.release()


def current_process_sid() -> str:
    if os.name != "nt":
        raise RuntimeError("Windows identity is unavailable")
    kernel32 = _kernel32()
    return _process_sid(int(kernel32.GetCurrentProcess()))


def process_sid(process_id: int) -> str:
    if os.name != "nt":
        raise RuntimeError("Windows identity is unavailable")
    kernel32 = _kernel32()
    process = kernel32.OpenProcess(
        PROCESS_QUERY_LIMITED_INFORMATION, False, process_id
    )
    if not process:
        raise PermissionError(
            f"authority client process cannot be inspected: {ctypes.get_last_error()}"
        )
    try:
        return _process_sid(_handle_value(process))
    finally:
        kernel32.CloseHandle(process)


def _inspect_named_pipe_client(
    pipe: int, process: int
) -> NamedPipeClientProcessIdentity:
    token_sid, token_session = _process_token_sid_and_session(process)
    return _inspect_named_pipe_client_identity(
        pipe, process, token_sid, token_session
    )


def _inspect_bound_named_pipe_client(
    pipe: int, process: int, process_token: int
) -> NamedPipeClientProcessIdentity:
    token_sid, token_session = _token_sid_and_session(process_token)
    return _inspect_named_pipe_client_identity(
        pipe, process, token_sid, token_session
    )


def _inspect_named_pipe_client_identity(
    pipe: int,
    process: int,
    token_sid: str,
    token_session: int,
) -> NamedPipeClientProcessIdentity:
    process_id = _named_pipe_client_process_id(pipe)
    if _process_handle_id(process) != process_id:
        raise PermissionError("authority client process handle is mismatched")
    direct_session = _named_pipe_client_session_id(pipe)
    pid_session = _process_id_session(process_id)
    if direct_session != token_session:
        raise PermissionError("authority client Windows session is mismatched")
    if pid_session is not None and pid_session != direct_session:
        raise PermissionError("authority client Windows session is mismatched")
    if not _process_is_active(process):
        raise PermissionError("authority client process is not active")
    computer_name = _named_pipe_client_computer_name(pipe)
    local_name = _local_computer_name()
    normalized_computer_name = computer_name.lstrip("\\")
    if (
        normalized_computer_name.casefold()
        not in {local_name.casefold(), "."}
    ):
        raise PermissionError("remote authority clients are unauthorized")
    return NamedPipeClientProcessIdentity(
        process_id=process_id,
        session_id=direct_session,
        sid=token_sid,
        computer_name=computer_name,
    )


def _named_pipe_client_process_id(pipe: int) -> int:
    value = wintypes.ULONG()
    if not _kernel32().GetNamedPipeClientProcessId(
        wintypes.HANDLE(pipe), ctypes.byref(value)
    ):
        raise PermissionError(
            "authority named-pipe client process is unavailable: "
            f"{ctypes.get_last_error()}"
        )
    if value.value <= 0:
        raise PermissionError("authority named-pipe client process is invalid")
    return int(value.value)


def _named_pipe_client_session_id(pipe: int) -> int:
    value = wintypes.ULONG()
    if not _kernel32().GetNamedPipeClientSessionId(
        wintypes.HANDLE(pipe), ctypes.byref(value)
    ):
        raise PermissionError(
            "authority named-pipe client session is unavailable: "
            f"{ctypes.get_last_error()}"
        )
    return int(value.value)


def _named_pipe_client_computer_name(pipe: int) -> str:
    size = 256
    buffer = ctypes.create_unicode_buffer(size)
    if not _kernel32().GetNamedPipeClientComputerNameW(
        wintypes.HANDLE(pipe), buffer, size
    ):
        error = ctypes.get_last_error()
        if error == ERROR_PIPE_LOCAL:
            return _local_computer_name()
        raise PermissionError(
            "authority named-pipe client computer is unavailable: "
            f"{error}"
        )
    value = buffer.value.strip()
    if not value:
        raise PermissionError("authority named-pipe client computer is invalid")
    return value


def _local_computer_name() -> str:
    size = wintypes.DWORD(256)
    buffer = ctypes.create_unicode_buffer(size.value)
    if not _kernel32().GetComputerNameW(buffer, ctypes.byref(size)):
        raise PermissionError(
            "authority local computer identity is unavailable: "
            f"{ctypes.get_last_error()}"
        )
    value = buffer.value.strip()
    if not value:
        raise PermissionError("authority local computer identity is invalid")
    return value


def _process_id_session(process_id: int) -> int | None:
    """Return optional PID/session corroboration without broader process rights."""
    value = wintypes.DWORD()
    if not _kernel32().ProcessIdToSessionId(process_id, ctypes.byref(value)):
        error = ctypes.get_last_error()
        if error == ERROR_ACCESS_DENIED:
            return None
        raise PermissionError(
            "authority client process session is unavailable: "
            f"{error}"
        )
    return int(value.value)


def _process_handle_id(process: int) -> int:
    process_id = int(_kernel32().GetProcessId(wintypes.HANDLE(process)))
    if process_id <= 0:
        raise PermissionError(
            "authority client process handle identity is unavailable: "
            f"{ctypes.get_last_error()}"
        )
    return process_id


def _process_token_sid_and_session(process: int) -> tuple[str, int]:
    token = _open_process_token(process, TOKEN_QUERY)
    try:
        return _token_sid_and_session(token)
    finally:
        if not _kernel32().CloseHandle(wintypes.HANDLE(token)):
            raise PermissionError(
                "authority client process-token handle cleanup failed: "
                f"{ctypes.get_last_error()}"
            )


def _open_process_token(process: int, access: int) -> int:
    token = wintypes.HANDLE()
    if not _advapi32().OpenProcessToken(
        wintypes.HANDLE(process), access, ctypes.byref(token)
    ):
        raise PermissionError(
            "authority client process token cannot be opened: "
            f"{ctypes.get_last_error()}"
        )
    return _handle_value(token)


def _token_sid_and_session(token: int) -> tuple[str, int]:
    return _token_sid(token), _token_session_id(token)


def _process_is_active(process: int) -> bool:
    exit_code = wintypes.DWORD()
    if not _kernel32().GetExitCodeProcess(
        wintypes.HANDLE(process), ctypes.byref(exit_code)
    ):
        raise PermissionError(
            "authority client process state is unavailable: "
            f"{ctypes.get_last_error()}"
        )
    return int(exit_code.value) == STILL_ACTIVE


def named_pipe_client_sid(pipe: int) -> str:
    return named_pipe_client_identity(pipe).sid


def named_pipe_client_identity(pipe: int) -> WindowsTokenIdentity:
    if os.name != "nt":
        raise RuntimeError("Windows identity is unavailable")
    advapi32 = _advapi32()
    if not advapi32.ImpersonateNamedPipeClient(pipe):
        raise PermissionError(
            f"authority client impersonation failed: {ctypes.get_last_error()}"
        )
    token = wintypes.HANDLE()
    try:
        if not advapi32.OpenThreadToken(
            _kernel32().GetCurrentThread(),
            TOKEN_QUERY,
            True,
            ctypes.byref(token),
        ):
            raise PermissionError(
                "authority client token cannot be opened: "
                f"{ctypes.get_last_error()}"
            )
        token_value = _handle_value(token)
        return WindowsTokenIdentity(
            _token_sid(token_value),
            bool(advapi32.IsTokenRestricted(token)),
            _token_integrity_rid(token_value),
        )
    finally:
        if token.value:
            _kernel32().CloseHandle(token)
        if not advapi32.RevertToSelf():
            raise PermissionError(
                "authority client impersonation could not be reverted: "
                f"{ctypes.get_last_error()}"
            )


def process_image(process_id: int) -> Path:
    kernel32 = _kernel32()
    process = kernel32.OpenProcess(
        PROCESS_QUERY_LIMITED_INFORMATION, False, process_id
    )
    if not process:
        raise PermissionError(
            f"provider process cannot be inspected: {ctypes.get_last_error()}"
        )
    try:
        size = wintypes.DWORD(32768)
        buffer = ctypes.create_unicode_buffer(size.value)
        if not kernel32.QueryFullProcessImageNameW(
            process, 0, buffer, ctypes.byref(size)
        ):
            raise PermissionError(
                f"provider process image cannot be inspected: {ctypes.get_last_error()}"
            )
        return Path(buffer.value).resolve(strict=True)
    finally:
        kernel32.CloseHandle(process)


def _process_sid(process: int) -> str:
    advapi32 = _advapi32()
    token = wintypes.HANDLE()
    if not advapi32.OpenProcessToken(process, TOKEN_QUERY, ctypes.byref(token)):
        raise PermissionError(
            f"Windows process token cannot be opened: {ctypes.get_last_error()}"
        )
    try:
        return _token_sid(_handle_value(token))
    finally:
        _kernel32().CloseHandle(token)


def _token_sid(token: int) -> str:
    advapi32 = _advapi32()
    needed = wintypes.DWORD()
    advapi32.GetTokenInformation(
        token, TOKEN_USER, None, 0, ctypes.byref(needed)
    )
    if not needed.value:
        raise PermissionError("Windows token identity is unavailable")
    buffer = ctypes.create_string_buffer(needed.value)
    if not advapi32.GetTokenInformation(
        token, TOKEN_USER, buffer, needed, ctypes.byref(needed)
    ):
        raise PermissionError(
            f"Windows token identity cannot be read: {ctypes.get_last_error()}"
        )
    user = ctypes.cast(buffer, ctypes.POINTER(_TokenUser)).contents
    return _sid_string(user.User.Sid)


def _token_session_id(token: int) -> int:
    value = wintypes.DWORD()
    needed = wintypes.DWORD()
    if not _advapi32().GetTokenInformation(
        wintypes.HANDLE(token),
        12,
        ctypes.byref(value),
        ctypes.sizeof(value),
        ctypes.byref(needed),
    ):
        raise PermissionError(
            "authority client process-token session is unavailable: "
            f"{ctypes.get_last_error()}"
        )
    return int(value.value)


def _token_integrity_rid(token: int) -> int:
    advapi32 = _advapi32()
    needed = wintypes.DWORD()
    advapi32.GetTokenInformation(
        token, TOKEN_INTEGRITY_LEVEL, None, 0, ctypes.byref(needed)
    )
    if not needed.value:
        raise PermissionError("Windows token integrity is unavailable")
    buffer = ctypes.create_string_buffer(needed.value)
    if not advapi32.GetTokenInformation(
        token,
        TOKEN_INTEGRITY_LEVEL,
        buffer,
        needed,
        ctypes.byref(needed),
    ):
        raise PermissionError(
            f"Windows token integrity cannot be read: {ctypes.get_last_error()}"
        )
    label = ctypes.cast(
        buffer, ctypes.POINTER(_TokenMandatoryLabel)
    ).contents
    count = int(advapi32.GetSidSubAuthorityCount(label.Label.Sid)[0])
    if count <= 0:
        raise PermissionError("Windows token integrity SID is invalid")
    return int(
        advapi32.GetSidSubAuthority(label.Label.Sid, count - 1)[0]
    )


def _sid_string(sid: int) -> str:
    advapi32 = _advapi32()
    value = wintypes.LPWSTR()
    if not advapi32.ConvertSidToStringSidW(sid, ctypes.byref(value)):
        raise PermissionError(
            f"Windows SID conversion failed: {ctypes.get_last_error()}"
        )
    try:
        return str(value.value)
    finally:
        _kernel32().LocalFree(value)


def _kernel32() -> Any:
    kernel32: Any = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.GetCurrentProcess.restype = wintypes.HANDLE
    kernel32.GetCurrentThread.restype = wintypes.HANDLE
    kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.GetNamedPipeClientProcessId.argtypes = [
        wintypes.HANDLE,
        ctypes.POINTER(wintypes.ULONG),
    ]
    kernel32.GetNamedPipeClientProcessId.restype = wintypes.BOOL
    kernel32.GetNamedPipeClientSessionId.argtypes = [
        wintypes.HANDLE,
        ctypes.POINTER(wintypes.ULONG),
    ]
    kernel32.GetNamedPipeClientSessionId.restype = wintypes.BOOL
    kernel32.GetNamedPipeClientComputerNameW.argtypes = [
        wintypes.HANDLE,
        wintypes.LPWSTR,
        wintypes.ULONG,
    ]
    kernel32.GetNamedPipeClientComputerNameW.restype = wintypes.BOOL
    kernel32.GetComputerNameW.argtypes = [
        wintypes.LPWSTR,
        ctypes.POINTER(wintypes.DWORD),
    ]
    kernel32.GetComputerNameW.restype = wintypes.BOOL
    kernel32.ProcessIdToSessionId.argtypes = [
        wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD),
    ]
    kernel32.ProcessIdToSessionId.restype = wintypes.BOOL
    kernel32.GetExitCodeProcess.argtypes = [
        wintypes.HANDLE,
        ctypes.POINTER(wintypes.DWORD),
    ]
    kernel32.GetExitCodeProcess.restype = wintypes.BOOL
    kernel32.GetProcessId.argtypes = [wintypes.HANDLE]
    kernel32.GetProcessId.restype = wintypes.DWORD
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL
    kernel32.QueryFullProcessImageNameW.argtypes = [
        wintypes.HANDLE,
        wintypes.DWORD,
        wintypes.LPWSTR,
        ctypes.POINTER(wintypes.DWORD),
    ]
    kernel32.QueryFullProcessImageNameW.restype = wintypes.BOOL
    kernel32.LocalFree.argtypes = [wintypes.HLOCAL]
    kernel32.LocalFree.restype = wintypes.HLOCAL
    return kernel32


def _advapi32() -> Any:
    advapi32: Any = ctypes.WinDLL("advapi32", use_last_error=True)
    advapi32.OpenProcessToken.argtypes = [
        wintypes.HANDLE,
        wintypes.DWORD,
        ctypes.POINTER(wintypes.HANDLE),
    ]
    advapi32.OpenProcessToken.restype = wintypes.BOOL
    advapi32.OpenThreadToken.argtypes = [
        wintypes.HANDLE,
        wintypes.DWORD,
        wintypes.BOOL,
        ctypes.POINTER(wintypes.HANDLE),
    ]
    advapi32.OpenThreadToken.restype = wintypes.BOOL
    advapi32.ImpersonateNamedPipeClient.argtypes = [wintypes.HANDLE]
    advapi32.ImpersonateNamedPipeClient.restype = wintypes.BOOL
    advapi32.RevertToSelf.restype = wintypes.BOOL
    advapi32.GetTokenInformation.argtypes = [
        wintypes.HANDLE,
        ctypes.c_int,
        wintypes.LPVOID,
        wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD),
    ]
    advapi32.GetTokenInformation.restype = wintypes.BOOL
    advapi32.IsTokenRestricted.argtypes = [wintypes.HANDLE]
    advapi32.IsTokenRestricted.restype = wintypes.BOOL
    advapi32.GetSidSubAuthorityCount.argtypes = [wintypes.LPVOID]
    advapi32.GetSidSubAuthorityCount.restype = ctypes.POINTER(
        ctypes.c_ubyte
    )
    advapi32.GetSidSubAuthority.argtypes = [
        wintypes.LPVOID,
        wintypes.DWORD,
    ]
    advapi32.GetSidSubAuthority.restype = ctypes.POINTER(wintypes.DWORD)
    advapi32.ConvertSidToStringSidW.argtypes = [
        wintypes.LPVOID,
        ctypes.POINTER(wintypes.LPWSTR),
    ]
    advapi32.ConvertSidToStringSidW.restype = wintypes.BOOL
    return advapi32


def _handle_value(handle: object) -> int:
    value = getattr(handle, "value", handle)
    if not isinstance(value, int) or value <= 0:
        raise OSError("Windows handle is invalid")
    return value
