from __future__ import annotations

import ctypes
import hashlib
import os
import subprocess
from contextlib import contextmanager
from ctypes import wintypes
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator


_TOKEN_ALL_ACCESS = 0x000F01FF
_DISABLE_MAX_PRIVILEGE = 0x1
_TOKEN_INTEGRITY_LEVEL = 25
_SE_GROUP_INTEGRITY = 0x20
_SECURITY_IMPERSONATION = 2
_TOKEN_PRIMARY = 1
_CREATE_SUSPENDED = 0x00000004
_CREATE_UNICODE_ENVIRONMENT = 0x00000400
_CREATE_NEW_PROCESS_GROUP = 0x00000200
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
def restricted_named_pipe_client_token(pipe: int) -> Iterator[int]:
    """Capture the authenticated pipe client and derive a restricted primary token."""
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
    restricted = 0
    try:
        restricted = create_restricted_primary_token(_handle_value(token))
        yield restricted
    finally:
        if restricted:
            _kernel32().CloseHandle(restricted)
        if token.value:
            _kernel32().CloseHandle(token)


def create_restricted_primary_token(token: int) -> int:
    restricted_source = wintypes.HANDLE()
    restricted_code_sid = wintypes.LPVOID()
    if not _advapi32().ConvertStringSidToSidW(
        "S-1-5-12", ctypes.byref(restricted_code_sid)
    ):
        raise PermissionError(
            f"restricted-code SID creation failed: {ctypes.get_last_error()}"
        )
    restricting_sids = (_SidAndAttributes * 1)(
        _SidAndAttributes(restricted_code_sid, 0)
    )
    try:
        if not _advapi32().CreateRestrictedToken(
            wintypes.HANDLE(token),
            _DISABLE_MAX_PRIVILEGE,
            0,
            None,
            0,
            None,
            1,
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
        _kernel32().LocalFree(restricted_code_sid)


def run_restricted_process(
    token: int,
    command: list[str],
    executable: Path,
    workspace: Path,
    environment: dict[str, str],
    stdout_path: Path,
    stderr_path: Path,
    timeout_seconds: float,
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
            if _kernel32().ResumeThread(process.hThread) != 1:
                raise PermissionError(
                    "restricted provider primary thread did not resume exactly once"
                )
            wait_ms = max(1, int(timeout_seconds * 1000))
            wait_result = _kernel32().WaitForSingleObject(
                process.hProcess, wait_ms
            )
            timed_out = wait_result == _WAIT_TIMEOUT
            if timed_out:
                if not _kernel32().TerminateJobObject(job, 124):
                    raise RuntimeError("restricted provider timeout cleanup failed")
                if (
                    _kernel32().WaitForSingleObject(process.hProcess, 10_000)
                    != _WAIT_OBJECT_0
                ):
                    raise RuntimeError("restricted provider did not terminate")
            elif wait_result != _WAIT_OBJECT_0:
                raise OSError(
                    ctypes.get_last_error(), "restricted provider wait failed"
                )
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
