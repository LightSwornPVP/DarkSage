from __future__ import annotations

import ctypes
import hashlib
import os
import subprocess
import threading
import time
from contextlib import contextmanager
from ctypes import wintypes
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Callable, Iterator


_TOKEN_ALL_ACCESS = 0x000F01FF
_DISABLE_MAX_PRIVILEGE = 0x1
_TOKEN_INTEGRITY_LEVEL = 25
_TOKEN_GROUPS = 2
_TOKEN_USER = 1
_SE_GROUP_INTEGRITY = 0x20
_SE_GROUP_ENABLED = 0x00000004
_SECURITY_IMPERSONATION = 2
_TOKEN_PRIMARY = 1
_CREATE_SUSPENDED = 0x00000004
_CREATE_UNICODE_ENVIRONMENT = 0x00000400
_CREATE_NEW_PROCESS_GROUP = 0x00000200
_CREATE_NO_WINDOW = 0x08000000
_EXTENDED_STARTUPINFO_PRESENT = 0x00080000
_STARTF_USESTDHANDLES = 0x00000100
_PROC_THREAD_ATTRIBUTE_HANDLE_LIST = 0x00020002
_JOB_OBJECT_EXTENDED_LIMIT_INFORMATION = 9
_JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x00002000
_WAIT_OBJECT_0 = 0
_WAIT_TIMEOUT = 258
_INFINITE = 0xFFFFFFFF


class _SecurityAttributes(ctypes.Structure):
    _fields_ = [
        ("nLength", wintypes.DWORD),
        ("lpSecurityDescriptor", wintypes.LPVOID),
        ("bInheritHandle", wintypes.BOOL),
    ]


class _StartupInfo(ctypes.Structure):
    _fields_ = [
        ("cb", wintypes.DWORD),
        ("lpReserved", wintypes.LPWSTR),
        ("lpDesktop", wintypes.LPWSTR),
        ("lpTitle", wintypes.LPWSTR),
        ("dwX", wintypes.DWORD),
        ("dwY", wintypes.DWORD),
        ("dwXSize", wintypes.DWORD),
        ("dwYSize", wintypes.DWORD),
        ("dwXCountChars", wintypes.DWORD),
        ("dwYCountChars", wintypes.DWORD),
        ("dwFillAttribute", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("wShowWindow", wintypes.WORD),
        ("cbReserved2", wintypes.WORD),
        ("lpReserved2", ctypes.POINTER(ctypes.c_ubyte)),
        ("hStdInput", wintypes.HANDLE),
        ("hStdOutput", wintypes.HANDLE),
        ("hStdError", wintypes.HANDLE),
    ]


class _StartupInfoEx(ctypes.Structure):
    _fields_ = [
        ("StartupInfo", _StartupInfo),
        ("lpAttributeList", wintypes.LPVOID),
    ]


class _ProcessInformation(ctypes.Structure):
    _fields_ = [
        ("hProcess", wintypes.HANDLE),
        ("hThread", wintypes.HANDLE),
        ("dwProcessId", wintypes.DWORD),
        ("dwThreadId", wintypes.DWORD),
    ]


class _SidAndAttributes(ctypes.Structure):
    _fields_ = [("Sid", wintypes.LPVOID), ("Attributes", wintypes.DWORD)]


class _TokenGroups(ctypes.Structure):
    _fields_ = [
        ("GroupCount", wintypes.DWORD),
        ("Groups", _SidAndAttributes * 1),
    ]


class _TokenUser(ctypes.Structure):
    _fields_ = [("User", _SidAndAttributes)]


class _TokenMandatoryLabel(ctypes.Structure):
    _fields_ = [("Label", _SidAndAttributes)]


class _JobBasicLimitInformation(ctypes.Structure):
    _fields_ = [
        ("PerProcessUserTimeLimit", ctypes.c_longlong),
        ("PerJobUserTimeLimit", ctypes.c_longlong),
        ("LimitFlags", wintypes.DWORD),
        ("MinimumWorkingSetSize", ctypes.c_size_t),
        ("MaximumWorkingSetSize", ctypes.c_size_t),
        ("ActiveProcessLimit", wintypes.DWORD),
        ("Affinity", ctypes.c_size_t),
        ("PriorityClass", wintypes.DWORD),
        ("SchedulingClass", wintypes.DWORD),
    ]


class _IoCounters(ctypes.Structure):
    _fields_ = [
        ("ReadOperationCount", ctypes.c_ulonglong),
        ("WriteOperationCount", ctypes.c_ulonglong),
        ("OtherOperationCount", ctypes.c_ulonglong),
        ("ReadTransferCount", ctypes.c_ulonglong),
        ("WriteTransferCount", ctypes.c_ulonglong),
        ("OtherTransferCount", ctypes.c_ulonglong),
    ]


class _JobExtendedLimitInformation(ctypes.Structure):
    _fields_ = [
        ("BasicLimitInformation", _JobBasicLimitInformation),
        ("IoInfo", _IoCounters),
        ("ProcessMemoryLimit", ctypes.c_size_t),
        ("JobMemoryLimit", ctypes.c_size_t),
        ("PeakProcessMemoryUsed", ctypes.c_size_t),
        ("PeakJobMemoryUsed", ctypes.c_size_t),
    ]


@dataclass(frozen=True, slots=True)
class RestrictedProcessResult:
    process_id: int
    exit_code: int
    stdout: str
    stderr: str
    executable: str
    executable_sha256: str
    restricted: bool
    integrity_level: str
    job_confined: bool
    timed_out: bool


@contextmanager
def restricted_current_process_token() -> Iterator[int]:
    """Create a low-integrity, privilege-stripped primary token for tests/host use."""
    token = wintypes.HANDLE()
    if not _advapi32().OpenProcessToken(
        _kernel32().GetCurrentProcess(), _TOKEN_ALL_ACCESS, ctypes.byref(token)
    ):
        raise PermissionError(
            f"current process token cannot be opened: {ctypes.get_last_error()}"
        )
    restricted = 0
    try:
        restricted = create_restricted_primary_token(_handle_value(token))
        yield restricted
    finally:
        if restricted:
            _kernel32().CloseHandle(restricted)
        _kernel32().CloseHandle(token)


@contextmanager
def authenticated_named_pipe_client_token(pipe: int) -> Iterator[int]:
    """Capture the authenticated pipe client's impersonation token."""
    if not _advapi32().ImpersonateNamedPipeClient(pipe):
        raise PermissionError(
            f"authority client impersonation failed: {ctypes.get_last_error()}"
        )
    token = wintypes.HANDLE()
    try:
        if not _advapi32().OpenThreadToken(
            _kernel32().GetCurrentThread(),
            _TOKEN_ALL_ACCESS,
            True,
            ctypes.byref(token),
        ):
            raise PermissionError(
                f"authority client token cannot be opened: {ctypes.get_last_error()}"
            )
    finally:
        if not _advapi32().RevertToSelf():
            raise PermissionError(
                f"authority client impersonation could not be reverted: {ctypes.get_last_error()}"
            )
    try:
        yield _handle_value(token)
    finally:
        if token.value:
            _kernel32().CloseHandle(token)


@contextmanager
def impersonate_token(token: int) -> Iterator[None]:
    if not _advapi32().ImpersonateLoggedOnUser(token):
        raise PermissionError(
            f"restricted provider impersonation failed: {ctypes.get_last_error()}"
        )
    try:
        yield
    finally:
        if not _advapi32().RevertToSelf():
            raise PermissionError(
                f"restricted provider impersonation could not be reverted: {ctypes.get_last_error()}"
            )


def create_restricted_primary_token(token: int) -> int:
    restricted_source = wintypes.HANDLE()
    administrators_sid = wintypes.LPVOID()
    restricted_code_sid = wintypes.LPVOID()
    enabled_groups, _groups_buffer = _token_enabled_group_sids(token)
    user_sid, _user_buffer = _token_user_sid(token)
    if not _advapi32().ConvertStringSidToSidW(
        "S-1-5-32-544", ctypes.byref(administrators_sid)
    ):
        raise PermissionError(
            f"administrators SID creation failed: {ctypes.get_last_error()}"
        )
    if not _advapi32().ConvertStringSidToSidW(
        "S-1-5-12", ctypes.byref(restricted_code_sid)
    ):
        _kernel32().LocalFree(administrators_sid)
        raise PermissionError(
            f"restricted-code SID creation failed: {ctypes.get_last_error()}"
        )
    disabled_sids = (_SidAndAttributes * 1)(
        _SidAndAttributes(administrators_sid, 0)
    )
    restricting_sids = (_SidAndAttributes * (len(enabled_groups) + 2))(
        _SidAndAttributes(user_sid, 0),
        *(_SidAndAttributes(sid, 0) for sid in enabled_groups),
        _SidAndAttributes(restricted_code_sid, 0)
    )
    try:
        if not _advapi32().CreateRestrictedToken(
            wintypes.HANDLE(token),
            _DISABLE_MAX_PRIVILEGE,
            1,
            ctypes.byref(disabled_sids),
            0,
            None,
            len(restricting_sids),
            ctypes.byref(restricting_sids),
            ctypes.byref(restricted_source),
        ):
            raise PermissionError(
                f"provider restricted token creation failed: {ctypes.get_last_error()}"
            )
        restricted = wintypes.HANDLE()
        if not _advapi32().DuplicateTokenEx(
            restricted_source,
            _TOKEN_ALL_ACCESS,
            None,
            _SECURITY_IMPERSONATION,
            _TOKEN_PRIMARY,
            ctypes.byref(restricted),
        ):
            raise PermissionError(
                f"provider primary token duplication failed: {ctypes.get_last_error()}"
            )
        _set_low_integrity(_handle_value(restricted))
        if not _advapi32().IsTokenRestricted(restricted):
            raise PermissionError("provider token is not restricted")
        return _handle_value(restricted)
    except BaseException:
        value = locals().get("restricted")
        if isinstance(value, wintypes.HANDLE) and value.value:
            _kernel32().CloseHandle(value)
        raise
    finally:
        if restricted_source.value:
            _kernel32().CloseHandle(restricted_source)
        _kernel32().LocalFree(administrators_sid)
        _kernel32().LocalFree(restricted_code_sid)


def _token_enabled_group_sids(
    token: int,
) -> tuple[list[int], ctypes.Array[ctypes.c_char]]:
    needed = wintypes.DWORD()
    _advapi32().GetTokenInformation(
        token, _TOKEN_GROUPS, None, 0, ctypes.byref(needed)
    )
    if not needed.value:
        raise PermissionError("provider token groups are unavailable")
    buffer = ctypes.create_string_buffer(needed.value)
    if not _advapi32().GetTokenInformation(
        token,
        _TOKEN_GROUPS,
        buffer,
        needed,
        ctypes.byref(needed),
    ):
        raise PermissionError(
            f"provider token groups failed: {ctypes.get_last_error()}"
        )
    groups = ctypes.cast(buffer, ctypes.POINTER(_TokenGroups)).contents
    first = ctypes.addressof(groups.Groups)
    values: list[int] = []
    for index in range(int(groups.GroupCount)):
        group = _SidAndAttributes.from_address(
            first + index * ctypes.sizeof(_SidAndAttributes)
        )
        if group.Attributes & _SE_GROUP_ENABLED:
            values.append(int(group.Sid))
    if not values:
        raise PermissionError("provider token has no enabled groups")
    return values, buffer


def _token_user_sid(
    token: int,
) -> tuple[int, ctypes.Array[ctypes.c_char]]:
    needed = wintypes.DWORD()
    _advapi32().GetTokenInformation(
        token, _TOKEN_USER, None, 0, ctypes.byref(needed)
    )
    if not needed.value:
        raise PermissionError("provider token user is unavailable")
    buffer = ctypes.create_string_buffer(needed.value)
    if not _advapi32().GetTokenInformation(
        token,
        _TOKEN_USER,
        buffer,
        needed,
        ctypes.byref(needed),
    ):
        raise PermissionError(
            f"provider token user failed: {ctypes.get_last_error()}"
        )
    user = ctypes.cast(buffer, ctypes.POINTER(_TokenUser)).contents
    return int(user.User.Sid), buffer


def run_restricted_process(
    token: int,
    command: list[str],
    executable: Path,
    workspace: Path,
    environment: dict[str, str],
    stdout_path: Path,
    stderr_path: Path,
    timeout_seconds: float,
    on_started: Callable[[dict[str, object]], None] | None = None,
    cancel_requested: threading.Event | None = None,
) -> RestrictedProcessResult:
    if os.name != "nt":
        raise RuntimeError("restricted provider execution requires Windows")
    executable = executable.resolve(strict=True)
    workspace = workspace.resolve(strict=True)
    stdout_path.parent.mkdir(parents=True, exist_ok=True)
    stderr_path.parent.mkdir(parents=True, exist_ok=True)
    handles: list[int] = []
    process = _ProcessInformation()
    job = 0
    attribute_buffer: ctypes.Array[ctypes.c_char] | None = None
    stdout_handle = _open_inheritable_output(stdout_path)
    stderr_handle = _open_inheritable_output(stderr_path)
    stdin_handle = _open_inheritable_input(Path(os.devnull))
    handles.extend((stdin_handle, stdout_handle, stderr_handle))
    try:
        job = _create_job()
        attribute_buffer, attribute_list = _handle_allowlist(handles)
        startup = _StartupInfoEx()
        startup.StartupInfo.cb = ctypes.sizeof(_StartupInfoEx)
        startup.StartupInfo.dwFlags = _STARTF_USESTDHANDLES
        startup.StartupInfo.hStdInput = stdin_handle
        startup.StartupInfo.hStdOutput = stdout_handle
        startup.StartupInfo.hStdError = stderr_handle
        startup.lpAttributeList = attribute_list
        command_line = ctypes.create_unicode_buffer(
            subprocess.list2cmdline(command)
        )
        environment_block = ctypes.create_unicode_buffer(
            _environment_block(environment)
        )
        flags = (
            _CREATE_SUSPENDED
            | _CREATE_UNICODE_ENVIRONMENT
            | _CREATE_NEW_PROCESS_GROUP
            | _CREATE_NO_WINDOW
            | _EXTENDED_STARTUPINFO_PRESENT
        )
        if not _advapi32().CreateProcessAsUserW(
            token,
            str(executable),
            command_line,
            None,
            None,
            True,
            flags,
            environment_block,
            str(workspace),
            ctypes.byref(startup),
            ctypes.byref(process),
        ):
            raise PermissionError(
                f"restricted provider creation failed: {ctypes.get_last_error()}"
            )
        try:
            if not _kernel32().AssignProcessToJobObject(job, process.hProcess):
                raise PermissionError(
                    f"restricted provider Job assignment failed: {ctypes.get_last_error()}"
                )
            in_job = wintypes.BOOL()
            if not _kernel32().IsProcessInJob(
                process.hProcess, job, ctypes.byref(in_job)
            ) or not in_job.value:
                raise PermissionError("restricted provider Job membership failed")
            if on_started is not None:
                content = executable.read_bytes()
                on_started(
                    {
                        "pid": int(process.dwProcessId),
                        "creation_time": _process_creation_time(process.hProcess),
                        "executable": str(executable),
                        "executable_sha256": hashlib.sha256(content).hexdigest(),
                        "restricted": True,
                        "integrity_level": "low",
                        "job_confined": True,
                    }
                )
            if _kernel32().ResumeThread(process.hThread) != 1:
                raise PermissionError(
                    "restricted provider primary thread did not resume exactly once"
                )
            deadline = time.monotonic() + timeout_seconds
            timed_out = False
            cancelled = False
            while True:
                if cancel_requested is not None and cancel_requested.is_set():
                    cancelled = True
                    if not _kernel32().TerminateJobObject(job, 125):
                        raise RuntimeError(
                            "restricted provider cancellation cleanup failed"
                        )
                    break
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    timed_out = True
                    if not _kernel32().TerminateJobObject(job, 124):
                        raise RuntimeError(
                            "restricted provider timeout cleanup failed"
                        )
                    break
                wait_result = _kernel32().WaitForSingleObject(
                    process.hProcess,
                    max(1, min(100, int(remaining * 1000))),
                )
                if wait_result == _WAIT_OBJECT_0:
                    break
                if wait_result != _WAIT_TIMEOUT:
                    raise OSError(
                        ctypes.get_last_error(), "restricted provider wait failed"
                    )
            if (timed_out or cancelled) and (
                _kernel32().WaitForSingleObject(process.hProcess, 10_000)
                != _WAIT_OBJECT_0
            ):
                raise RuntimeError("restricted provider did not terminate")
            exit_code = wintypes.DWORD()
            if not _kernel32().GetExitCodeProcess(
                process.hProcess, ctypes.byref(exit_code)
            ):
                raise OSError(
                    ctypes.get_last_error(), "restricted provider exit code failed"
                )
            if not _kernel32().TerminateJobObject(job, int(exit_code.value)):
                raise RuntimeError(
                    "restricted provider descendant cleanup could not be confirmed"
                )
        except BaseException:
            _kernel32().TerminateJobObject(job, 125)
            _kernel32().WaitForSingleObject(process.hProcess, 10_000)
            raise
        finally:
            _kernel32().CloseHandle(process.hThread)
            _kernel32().CloseHandle(process.hProcess)
    finally:
        if attribute_buffer is not None:
            _kernel32().DeleteProcThreadAttributeList(
                ctypes.cast(attribute_buffer, wintypes.LPVOID)
            )
        for handle in handles:
            _kernel32().CloseHandle(handle)
        if job:
            _kernel32().CloseHandle(job)
    content = executable.read_bytes()
    return RestrictedProcessResult(
        int(process.dwProcessId),
        int(exit_code.value),
        stdout_path.read_text(encoding="utf-8", errors="replace")[:1_048_576],
        stderr_path.read_text(encoding="utf-8", errors="replace")[:1_048_576],
        str(executable),
        hashlib.sha256(content).hexdigest(),
        True,
        "low",
        True,
        timed_out,
    )


def _set_low_integrity(token: int) -> None:
    sid = wintypes.LPVOID()
    if not _advapi32().ConvertStringSidToSidW(
        "S-1-16-4096", ctypes.byref(sid)
    ):
        raise PermissionError(
            f"low-integrity SID creation failed: {ctypes.get_last_error()}"
        )
    try:
        label = _TokenMandatoryLabel(
            _SidAndAttributes(sid, _SE_GROUP_INTEGRITY)
        )
        size = ctypes.sizeof(label) + int(_advapi32().GetLengthSid(sid))
        if not _advapi32().SetTokenInformation(
            token,
            _TOKEN_INTEGRITY_LEVEL,
            ctypes.byref(label),
            size,
        ):
            raise PermissionError(
                f"provider integrity level could not be restricted: {ctypes.get_last_error()}"
            )
    finally:
        _kernel32().LocalFree(sid)


def _open_inheritable_output(path: Path) -> int:
    attributes = _SecurityAttributes(
        ctypes.sizeof(_SecurityAttributes), None, True
    )
    handle = _kernel32().CreateFileW(
        str(path),
        0x40000000,
        0x00000001,
        ctypes.byref(attributes),
        2,
        0x00000080,
        None,
    )
    if handle in {None, ctypes.c_void_p(-1).value}:
        raise OSError(
            ctypes.get_last_error(), f"provider output cannot be opened: {path}"
        )
    return int(handle)


def _open_inheritable_input(path: Path) -> int:
    attributes = _SecurityAttributes(
        ctypes.sizeof(_SecurityAttributes), None, True
    )
    handle = _kernel32().CreateFileW(
        str(path),
        0x80000000,
        0x00000001,
        ctypes.byref(attributes),
        3,
        0x00000080,
        None,
    )
    if handle in {None, ctypes.c_void_p(-1).value}:
        raise OSError(
            ctypes.get_last_error(), "provider standard input cannot be opened"
        )
    return int(handle)


def _handle_allowlist(
    handles: list[int],
) -> tuple[ctypes.Array[ctypes.c_char], int]:
    size = ctypes.c_size_t()
    _kernel32().InitializeProcThreadAttributeList(None, 1, 0, ctypes.byref(size))
    if not size.value:
        raise OSError("provider process attribute size is unavailable")
    buffer = ctypes.create_string_buffer(size.value)
    pointer = ctypes.cast(buffer, wintypes.LPVOID)
    if not _kernel32().InitializeProcThreadAttributeList(
        pointer, 1, 0, ctypes.byref(size)
    ):
        raise OSError(
            ctypes.get_last_error(), "provider process attributes failed"
        )
    array_type = wintypes.HANDLE * len(handles)
    handle_array = array_type(*handles)
    if not _kernel32().UpdateProcThreadAttribute(
        pointer,
        0,
        _PROC_THREAD_ATTRIBUTE_HANDLE_LIST,
        ctypes.cast(handle_array, wintypes.LPVOID),
        ctypes.sizeof(handle_array),
        None,
        None,
    ):
        _kernel32().DeleteProcThreadAttributeList(pointer)
        raise OSError(
            ctypes.get_last_error(), "provider handle allowlist failed"
        )
    return buffer, int(ctypes.cast(pointer, ctypes.c_void_p).value or 0)


def _environment_block(environment: dict[str, str]) -> str:
    values = [
        f"{key}={value}"
        for key, value in sorted(environment.items(), key=lambda item: item[0].casefold())
        if "\0" not in key and "\0" not in value and "=" not in key
    ]
    return "\0".join(values) + "\0\0"


def _create_job() -> int:
    job = _kernel32().CreateJobObjectW(None, None)
    if not job:
        raise OSError(
            ctypes.get_last_error(), "restricted provider Job creation failed"
        )
    information = _JobExtendedLimitInformation()
    information.BasicLimitInformation.LimitFlags = (
        _JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
    )
    if not _kernel32().SetInformationJobObject(
        job,
        _JOB_OBJECT_EXTENDED_LIMIT_INFORMATION,
        ctypes.byref(information),
        ctypes.sizeof(information),
    ):
        error = ctypes.get_last_error()
        _kernel32().CloseHandle(job)
        raise OSError(error, "restricted provider Job configuration failed")
    return int(job)


def _process_creation_time(process: int) -> str:
    creation = wintypes.FILETIME()
    exit_time = wintypes.FILETIME()
    kernel_time = wintypes.FILETIME()
    user_time = wintypes.FILETIME()
    if not _kernel32().GetProcessTimes(
        process,
        ctypes.byref(creation),
        ctypes.byref(exit_time),
        ctypes.byref(kernel_time),
        ctypes.byref(user_time),
    ):
        raise OSError(
            ctypes.get_last_error(), "provider process creation time failed"
        )
    ticks = (int(creation.dwHighDateTime) << 32) | int(
        creation.dwLowDateTime
    )
    return (
        datetime(1601, 1, 1, tzinfo=UTC)
        + timedelta(microseconds=ticks // 10)
    ).isoformat()


def _kernel32() -> Any:
    kernel32: Any = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.GetCurrentProcess.restype = wintypes.HANDLE
    kernel32.GetCurrentThread.restype = wintypes.HANDLE
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL
    kernel32.LocalFree.argtypes = [wintypes.HLOCAL]
    kernel32.LocalFree.restype = wintypes.HLOCAL
    kernel32.CreateFileW.argtypes = [
        wintypes.LPCWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
        ctypes.POINTER(_SecurityAttributes),
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.HANDLE,
    ]
    kernel32.CreateFileW.restype = wintypes.HANDLE
    kernel32.InitializeProcThreadAttributeList.argtypes = [
        wintypes.LPVOID,
        wintypes.DWORD,
        wintypes.DWORD,
        ctypes.POINTER(ctypes.c_size_t),
    ]
    kernel32.InitializeProcThreadAttributeList.restype = wintypes.BOOL
    kernel32.UpdateProcThreadAttribute.argtypes = [
        wintypes.LPVOID,
        wintypes.DWORD,
        ctypes.c_size_t,
        wintypes.LPVOID,
        ctypes.c_size_t,
        wintypes.LPVOID,
        wintypes.LPVOID,
    ]
    kernel32.UpdateProcThreadAttribute.restype = wintypes.BOOL
    kernel32.DeleteProcThreadAttributeList.argtypes = [wintypes.LPVOID]
    kernel32.CreateJobObjectW.argtypes = [wintypes.LPVOID, wintypes.LPCWSTR]
    kernel32.CreateJobObjectW.restype = wintypes.HANDLE
    kernel32.SetInformationJobObject.argtypes = [
        wintypes.HANDLE,
        ctypes.c_int,
        wintypes.LPVOID,
        wintypes.DWORD,
    ]
    kernel32.SetInformationJobObject.restype = wintypes.BOOL
    kernel32.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
    kernel32.AssignProcessToJobObject.restype = wintypes.BOOL
    kernel32.IsProcessInJob.argtypes = [
        wintypes.HANDLE,
        wintypes.HANDLE,
        ctypes.POINTER(wintypes.BOOL),
    ]
    kernel32.IsProcessInJob.restype = wintypes.BOOL
    kernel32.ResumeThread.argtypes = [wintypes.HANDLE]
    kernel32.ResumeThread.restype = wintypes.DWORD
    kernel32.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    kernel32.WaitForSingleObject.restype = wintypes.DWORD
    kernel32.GetExitCodeProcess.argtypes = [
        wintypes.HANDLE,
        ctypes.POINTER(wintypes.DWORD),
    ]
    kernel32.GetExitCodeProcess.restype = wintypes.BOOL
    kernel32.GetProcessTimes.argtypes = [
        wintypes.HANDLE,
        ctypes.POINTER(wintypes.FILETIME),
        ctypes.POINTER(wintypes.FILETIME),
        ctypes.POINTER(wintypes.FILETIME),
        ctypes.POINTER(wintypes.FILETIME),
    ]
    kernel32.GetProcessTimes.restype = wintypes.BOOL
    kernel32.TerminateJobObject.argtypes = [wintypes.HANDLE, wintypes.UINT]
    kernel32.TerminateJobObject.restype = wintypes.BOOL
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
    advapi32.ImpersonateLoggedOnUser.argtypes = [wintypes.HANDLE]
    advapi32.ImpersonateLoggedOnUser.restype = wintypes.BOOL
    advapi32.RevertToSelf.restype = wintypes.BOOL
    advapi32.DuplicateTokenEx.argtypes = [
        wintypes.HANDLE,
        wintypes.DWORD,
        wintypes.LPVOID,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.POINTER(wintypes.HANDLE),
    ]
    advapi32.DuplicateTokenEx.restype = wintypes.BOOL
    advapi32.CreateRestrictedToken.argtypes = [
        wintypes.HANDLE,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.LPVOID,
        wintypes.DWORD,
        wintypes.LPVOID,
        wintypes.DWORD,
        wintypes.LPVOID,
        ctypes.POINTER(wintypes.HANDLE),
    ]
    advapi32.CreateRestrictedToken.restype = wintypes.BOOL
    advapi32.IsTokenRestricted.argtypes = [wintypes.HANDLE]
    advapi32.IsTokenRestricted.restype = wintypes.BOOL
    advapi32.GetTokenInformation.argtypes = [
        wintypes.HANDLE,
        ctypes.c_int,
        wintypes.LPVOID,
        wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD),
    ]
    advapi32.GetTokenInformation.restype = wintypes.BOOL
    advapi32.ConvertStringSidToSidW.argtypes = [
        wintypes.LPCWSTR,
        ctypes.POINTER(wintypes.LPVOID),
    ]
    advapi32.ConvertStringSidToSidW.restype = wintypes.BOOL
    advapi32.GetLengthSid.argtypes = [wintypes.LPVOID]
    advapi32.GetLengthSid.restype = wintypes.DWORD
    advapi32.SetTokenInformation.argtypes = [
        wintypes.HANDLE,
        ctypes.c_int,
        wintypes.LPVOID,
        wintypes.DWORD,
    ]
    advapi32.SetTokenInformation.restype = wintypes.BOOL
    advapi32.CreateProcessAsUserW.argtypes = [
        wintypes.HANDLE,
        wintypes.LPCWSTR,
        wintypes.LPWSTR,
        wintypes.LPVOID,
        wintypes.LPVOID,
        wintypes.BOOL,
        wintypes.DWORD,
        wintypes.LPVOID,
        wintypes.LPCWSTR,
        ctypes.POINTER(_StartupInfoEx),
        ctypes.POINTER(_ProcessInformation),
    ]
    advapi32.CreateProcessAsUserW.restype = wintypes.BOOL
    return advapi32


def _handle_value(handle: object) -> int:
    value = getattr(handle, "value", handle)
    if not isinstance(value, int) or value <= 0:
        raise OSError("Windows handle is invalid")
    return value
