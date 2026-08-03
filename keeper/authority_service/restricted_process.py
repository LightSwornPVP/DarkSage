from __future__ import annotations

import ctypes
import hashlib
import os
import subprocess
import threading
import time
from contextlib import ExitStack, contextmanager
from ctypes import wintypes
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Iterator

from keeper.authority_service.windows_identity import (
    NamedPipeClientProcessBinding,
    authenticated_named_pipe_client_process,
)
from keeper.providers.codex_contract import (
    validate_codex_authenticode_binding,
    validate_executable_file_identity,
)


_TOKEN_ALL_ACCESS = 0x000F01FF
_TOKEN_DUPLICATE = 0x0002
_TOKEN_IMPERSONATE = 0x0004
_TOKEN_QUERY = 0x0008
_DISABLE_MAX_PRIVILEGE = 0x1
_TOKEN_INTEGRITY_LEVEL = 25
_TOKEN_GROUPS = 2
_TOKEN_USER = 1
_TOKEN_SESSION_ID = 12
_TOKEN_IMPERSONATION_LEVEL = 9
_SE_GROUP_INTEGRITY = 0x20
_SE_GROUP_ENABLED = 0x00000004
_SECURITY_IMPERSONATION = 2
_TOKEN_PRIMARY = 1
_PROFILE_PRIMARY_TOKEN_ACCESS = _TOKEN_DUPLICATE | _TOKEN_QUERY
_NAMED_PIPE_CLIENT_TOKEN_ACCESS = (
    _TOKEN_DUPLICATE | _TOKEN_IMPERSONATE | _TOKEN_QUERY
)
_CREATE_SUSPENDED = 0x00000004
_CREATE_UNICODE_ENVIRONMENT = 0x00000400
_CREATE_NEW_PROCESS_GROUP = 0x00000200
_CREATE_NO_WINDOW = 0x08000000
_EXTENDED_STARTUPINFO_PRESENT = 0x00080000
_STARTF_USESTDHANDLES = 0x00000100
_PROC_THREAD_ATTRIBUTE_HANDLE_LIST = 0x00020002
_JOB_OBJECT_EXTENDED_LIMIT_INFORMATION = 9
_JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x00002000
_JOB_OBJECT_LIMIT_ACTIVE_PROCESS = 0x00000008
_JOB_OBJECT_LIMIT_JOB_MEMORY = 0x00000200
_WAIT_OBJECT_0 = 0
_WAIT_TIMEOUT = 258
_INFINITE = 0xFFFFFFFF
_ERROR_NO_TOKEN = 1008
_ERROR_ACCESS_DENIED = 5
_ERROR_INVALID_DATA = 13
_WTS_CONNECT_STATE = 8
_WTS_ACTIVE = 0
_WTS_VALID_CONNECT_STATES = frozenset(range(10))


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


class WindowsSessionQueryStatus(str, Enum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    QUERY_FAILED = "QUERY_FAILED"


@dataclass(frozen=True, slots=True)
class WindowsSessionQueryResult:
    status: WindowsSessionQueryStatus
    state: int | None = None
    win32_error: int | None = None

    def __post_init__(self) -> None:
        if self.status is WindowsSessionQueryStatus.ACTIVE:
            valid = self.state == _WTS_ACTIVE and self.win32_error is None
        elif self.status is WindowsSessionQueryStatus.INACTIVE:
            valid = (
                self.state in _WTS_VALID_CONNECT_STATES
                and self.state != _WTS_ACTIVE
                and self.win32_error is None
            )
        else:
            valid = (
                self.state is None
                and isinstance(self.win32_error, int)
                and not isinstance(self.win32_error, bool)
                and self.win32_error >= 0
            )
        if not valid:
            raise ValueError("Windows session query result is inconsistent")

    @property
    def is_active(self) -> bool:
        return self.status is WindowsSessionQueryStatus.ACTIVE


class ProviderLaunchIdentityUncertain(PermissionError):
    """The dedicated launch worker could not prove it reverted identity."""


class ProviderServiceIdentityUncertain(SystemExit):
    """Fail-stop because the Authority caller thread identity is uncertain."""


@contextmanager
def current_process_token() -> Iterator[int]:
    """Open the current process token without inspecting credential material."""
    token = wintypes.HANDLE()
    if not _advapi32().OpenProcessToken(
        _kernel32().GetCurrentProcess(), _TOKEN_ALL_ACCESS, ctypes.byref(token)
    ):
        raise PermissionError(
            f"current process token cannot be opened: {ctypes.get_last_error()}"
        )
    try:
        yield _handle_value(token)
    finally:
        _kernel32().CloseHandle(token)


@contextmanager
def restricted_current_process_token() -> Iterator[int]:
    """Create a low-integrity, privilege-stripped primary token for tests/host use."""
    with current_process_token() as token:
        restricted = create_restricted_primary_token(token)
        try:
            yield restricted
        finally:
            _kernel32().CloseHandle(restricted)


@contextmanager
def authenticated_named_pipe_client_token(pipe: int) -> Iterator[int]:
    """Capture the authenticated pipe client's impersonation token."""
    if not _advapi32().ImpersonateNamedPipeClient(pipe):
        raise PermissionError(
            f"authority client impersonation failed: {ctypes.get_last_error()}"
        )
    token = wintypes.HANDLE()
    try:
        try:
            if not _advapi32().OpenThreadToken(
                _kernel32().GetCurrentThread(),
                _NAMED_PIPE_CLIENT_TOKEN_ACCESS,
                True,
                ctypes.byref(token),
            ):
                raise PermissionError(
                    "authority client token cannot be opened: "
                    f"{ctypes.get_last_error()}"
                )
            require_impersonation_level(_handle_value(token))
        finally:
            if not _advapi32().RevertToSelf():
                raise PermissionError(
                    "authority client impersonation could not be reverted: "
                    f"{ctypes.get_last_error()}"
                )
    except BaseException:
        if token.value:
            _kernel32().CloseHandle(token)
        raise
    try:
        yield _handle_value(token)
    finally:
        if token.value:
            _kernel32().CloseHandle(token)


@contextmanager
def authenticated_named_pipe_client(
    pipe: int,
) -> Iterator[tuple[int, NamedPipeClientProcessBinding]]:
    """Capture one pipe token and its exact retained client-process token.

    Process and process-token handles are opened while the server is briefly
    impersonating the authenticated pipe peer. Reversion is verified before
    the caller can perform provider, persistence, or Authority work.
    """
    if not _advapi32().ImpersonateNamedPipeClient(pipe):
        raise PermissionError(
            f"authority client impersonation failed: {ctypes.get_last_error()}"
        )
    token = wintypes.HANDLE()
    bindings = ExitStack()
    setup_error: BaseException | None = None
    binding: NamedPipeClientProcessBinding | None = None
    try:
        if not _advapi32().OpenThreadToken(
            _kernel32().GetCurrentThread(),
            _NAMED_PIPE_CLIENT_TOKEN_ACCESS,
            True,
            ctypes.byref(token),
        ):
            raise PermissionError(
                "authority client token cannot be opened: "
                f"{ctypes.get_last_error()}"
            )
        token_value = _handle_value(token)
        require_impersonation_level(token_value)
        binding = bindings.enter_context(
            authenticated_named_pipe_client_process(
                pipe, token_user_sid_string(token_value)
            )
        )
    except BaseException as error:
        setup_error = error
    finally:
        if not _advapi32().RevertToSelf():
            setup_error = PermissionError(
                "authority client impersonation could not be reverted: "
                f"{ctypes.get_last_error()}"
            )
    if setup_error is not None or binding is None:
        try:
            bindings.close()
        finally:
            if token.value and not _kernel32().CloseHandle(token):
                raise PermissionError(
                    "authority client token cleanup failed: "
                    f"{ctypes.get_last_error()}"
                )
        if setup_error is not None:
            raise setup_error
        raise PermissionError("authority client process binding is unavailable")
    try:
        yield _handle_value(token), binding
    finally:
        try:
            bindings.close()
        finally:
            if token.value and not _kernel32().CloseHandle(token):
                raise PermissionError(
                    "authority client token cleanup failed: "
                    f"{ctypes.get_last_error()}"
                )


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


def _assert_thread_not_impersonating() -> None:
    """Prove the current thread has no impersonation token."""
    thread_token = wintypes.HANDLE()
    ctypes.set_last_error(0)
    if _advapi32().OpenThreadToken(
        _kernel32().GetCurrentThread(),
        _TOKEN_QUERY,
        True,
        ctypes.byref(thread_token),
    ):
        try:
            raise ProviderLaunchIdentityUncertain(
                "provider launch thread still has an impersonation token"
            )
        finally:
            if thread_token.value:
                _kernel32().CloseHandle(thread_token)
    error = ctypes.get_last_error()
    if error != _ERROR_NO_TOKEN:
        raise ProviderLaunchIdentityUncertain(
            "provider launch thread identity could not be verified "
            f"(win32_error={error}, symbolic={_win32_error_name(error)})"
        )


def _terminate_suspended_process(process: _ProcessInformation) -> None:
    """Best-effort cleanup used only by an identity-uncertain launch worker."""
    process_handle = int(process.hProcess or 0)
    thread_handle = int(process.hThread or 0)
    if process_handle:
        _kernel32().TerminateProcess(process_handle, 125)
        _kernel32().WaitForSingleObject(process_handle, 10_000)
    if thread_handle:
        _kernel32().CloseHandle(thread_handle)
    if process_handle:
        _kernel32().CloseHandle(process_handle)
    process.hThread = 0
    process.hProcess = 0


def _create_process_with_bounded_restricted_impersonation(
    token: int,
    process: _ProcessInformation,
    create_process: Callable[[], bool],
) -> None:
    """Run one suspended CreateProcessAsUser call on a disposable thread.

    The caller/service thread never impersonates.  The dedicated worker enters
    the already restricted provider identity immediately before the supplied
    CreateProcessAsUser call and must both revert and prove ERROR_NO_TOKEN
    before the caller is allowed to perform any subsequent service work.
    """
    try:
        _assert_thread_not_impersonating()
    except BaseException as error:
        raise ProviderServiceIdentityUncertain(
            "Authority service thread identity is not clean before launch"
        ) from error
    completed = threading.Event()
    outcome: list[BaseException] = []

    def worker() -> None:
        created = False
        try:
            _assert_thread_not_impersonating()
            if not _advapi32().ImpersonateLoggedOnUser(token):
                error = ctypes.get_last_error()
                try:
                    _assert_thread_not_impersonating()
                except BaseException as verification_error:
                    outcome.append(verification_error)
                else:
                    outcome.append(
                        PermissionError(
                            "restricted provider launch impersonation failed "
                            f"(win32_error={error}, "
                            f"symbolic={_win32_error_name(error)})"
                        )
                    )
                return
            create_error = 0
            try:
                created = create_process()
                if not created:
                    create_error = ctypes.get_last_error()
            finally:
                reverted = bool(_advapi32().RevertToSelf())
                revert_error = 0 if reverted else ctypes.get_last_error()
            try:
                _assert_thread_not_impersonating()
            except BaseException as verification_error:
                if created:
                    _terminate_suspended_process(process)
                outcome.append(
                    ProviderLaunchIdentityUncertain(
                        "restricted provider launch identity reversion "
                        "could not be verified"
                    )
                )
                outcome.append(verification_error)
                return
            if not reverted:
                if process.hProcess:
                    _terminate_suspended_process(process)
                outcome.append(
                    ProviderLaunchIdentityUncertain(
                        "restricted provider launch identity could not be "
                        "reverted "
                        f"(win32_error={revert_error}, "
                        f"symbolic={_win32_error_name(revert_error)})"
                    )
                )
                return
            if not created:
                if process.hProcess:
                    _terminate_suspended_process(process)
                outcome.append(
                    PermissionError(
                        "restricted provider creation failed "
                        f"(win32_error={create_error}, "
                        f"symbolic={_win32_error_name(create_error)})"
                    )
                )
        except BaseException as error:
            if process.hProcess:
                _terminate_suspended_process(process)
            outcome.append(error)
        finally:
            completed.set()

    launch_thread = threading.Thread(
        target=worker,
        name="KeeperRestrictedProviderLaunch",
        daemon=True,
    )
    launch_thread.start()
    completed.wait()
    launch_thread.join()
    # The service thread was never impersonated. Prove that before it assigns
    # a Job, invokes callbacks, resumes the process, or returns to Authority.
    try:
        _assert_thread_not_impersonating()
    except BaseException as error:
        if process.hProcess:
            _terminate_suspended_process(process)
        raise ProviderServiceIdentityUncertain(
            "Authority service thread identity is not clean after launch"
        ) from error
    if outcome:
        raise outcome[0]


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


def create_profile_restricted_primary_token(token: int) -> int:
    """Create a privilege-stripped primary token that retains user-profile access."""
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
            "restricted-code SID creation failed: "
            f"{ctypes.get_last_error()}"
        )
    disabled_sids = (_SidAndAttributes * 1)(
        _SidAndAttributes(administrators_sid, 0)
    )
    restricting_sids = (_SidAndAttributes * (len(enabled_groups) + 2))(
        _SidAndAttributes(user_sid, 0),
        *(_SidAndAttributes(sid, 0) for sid in enabled_groups),
        _SidAndAttributes(restricted_code_sid, 0),
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
                "profile provider restricted token creation failed: "
                f"{ctypes.get_last_error()}"
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
                "profile provider primary token duplication failed: "
                f"{ctypes.get_last_error()}"
            )
        if not _advapi32().IsTokenRestricted(restricted):
            raise PermissionError("profile provider token is not restricted")
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


@contextmanager
def profile_restricted_primary_token(token: int) -> Iterator[int]:
    restricted = create_profile_restricted_primary_token(token)
    try:
        yield restricted
    finally:
        _kernel32().CloseHandle(restricted)


@contextmanager
def authenticated_profile_primary_token(
    token: int,
) -> Iterator[int]:
    """Create a minimally accessible primary duplicate for profile APIs.

    Named-pipe authentication retains the exact client-process token. Windows
    permits converting it to a primary token with ``DuplicateTokenEx``. The
    duplicate is used only for profile discovery and restricted-token
    derivation; provider execution continues to use the separately restricted
    token.
    """
    primary = wintypes.HANDLE()
    if not _advapi32().DuplicateTokenEx(
        wintypes.HANDLE(token),
        _PROFILE_PRIMARY_TOKEN_ACCESS,
        None,
        _SECURITY_IMPERSONATION,
        _TOKEN_PRIMARY,
        ctypes.byref(primary),
    ):
        error = ctypes.get_last_error()
        raise PermissionError(
            "provider profile primary-token duplication failed "
            f"(api=DuplicateTokenEx, win32_error={error}, "
            f"symbolic={_win32_error_name(error)}, "
            "required_access=TOKEN_DUPLICATE|TOKEN_QUERY)"
        )
    try:
        yield _handle_value(primary)
    finally:
        _kernel32().CloseHandle(primary)


def token_user_sid_string(token: int) -> str:
    sid, _buffer = _token_user_sid(token)
    value = wintypes.LPWSTR()
    if not _advapi32().ConvertSidToStringSidW(
        wintypes.LPVOID(sid), ctypes.byref(value)
    ):
        raise PermissionError(
            f"provider SID conversion failed: {ctypes.get_last_error()}"
        )
    try:
        result = value.value
        if not result:
            raise PermissionError("provider SID is unavailable")
        return result
    finally:
        _kernel32().LocalFree(value)


def token_session_id(token: int) -> int:
    value = wintypes.DWORD()
    needed = wintypes.DWORD()
    if not _advapi32().GetTokenInformation(
        token,
        _TOKEN_SESSION_ID,
        ctypes.byref(value),
        ctypes.sizeof(value),
        ctypes.byref(needed),
    ):
        raise PermissionError(
            f"provider Windows session is unavailable: {ctypes.get_last_error()}"
        )
    return int(value.value)


def token_impersonation_level(token: int) -> int:
    value = wintypes.DWORD()
    needed = wintypes.DWORD()
    if not _advapi32().GetTokenInformation(
        token,
        _TOKEN_IMPERSONATION_LEVEL,
        ctypes.byref(value),
        ctypes.sizeof(value),
        ctypes.byref(needed),
    ):
        raise PermissionError(
            "authority client impersonation level is unavailable: "
            f"{ctypes.get_last_error()}"
        )
    return int(value.value)


def require_impersonation_level(token: int) -> int:
    level = token_impersonation_level(token)
    if level < _SECURITY_IMPERSONATION:
        raise PermissionError(
            "authority client token has insufficient impersonation level"
        )
    return level


def token_integrity_level(token: int) -> str:
    needed = wintypes.DWORD()
    _advapi32().GetTokenInformation(
        token, _TOKEN_INTEGRITY_LEVEL, None, 0, ctypes.byref(needed)
    )
    if not needed.value:
        raise PermissionError("provider token integrity is unavailable")
    buffer = ctypes.create_string_buffer(needed.value)
    if not _advapi32().GetTokenInformation(
        token,
        _TOKEN_INTEGRITY_LEVEL,
        buffer,
        needed,
        ctypes.byref(needed),
    ):
        raise PermissionError(
            f"provider token integrity failed: {ctypes.get_last_error()}"
        )
    label = ctypes.cast(
        buffer, ctypes.POINTER(_TokenMandatoryLabel)
    ).contents
    count_pointer = _advapi32().GetSidSubAuthorityCount(label.Label.Sid)
    if not count_pointer:
        raise PermissionError("provider token integrity SID is malformed")
    count = int(count_pointer.contents.value)
    if count < 1:
        raise PermissionError("provider token integrity SID is malformed")
    rid_pointer = _advapi32().GetSidSubAuthority(
        label.Label.Sid, count - 1
    )
    if not rid_pointer:
        raise PermissionError("provider token integrity RID is unavailable")
    rid = int(rid_pointer.contents.value)
    if rid < 0x2000:
        return "low"
    if rid < 0x3000:
        return "medium"
    if rid < 0x4000:
        return "high"
    return "system"


def _query_windows_session_state(
    wtsapi32: Any, session_id: int
) -> WindowsSessionQueryResult:
    """Query one exact session without collapsing API failure into inactivity."""
    buffer = wintypes.LPWSTR()
    size = wintypes.DWORD()
    ctypes.set_last_error(0)
    succeeded = bool(
        wtsapi32.WTSQuerySessionInformationW(
        wintypes.HANDLE(0),
        session_id,
        _WTS_CONNECT_STATE,
        ctypes.byref(buffer),
        ctypes.byref(size),
        )
    )
    query_error = 0 if succeeded else ctypes.get_last_error()
    result: WindowsSessionQueryResult
    try:
        if not succeeded:
            result = WindowsSessionQueryResult(
                WindowsSessionQueryStatus.QUERY_FAILED,
                win32_error=query_error,
            )
        elif not ctypes.cast(buffer, wintypes.LPVOID).value:
            result = WindowsSessionQueryResult(
                WindowsSessionQueryStatus.QUERY_FAILED,
                win32_error=_ERROR_INVALID_DATA,
            )
        elif size.value != ctypes.sizeof(wintypes.DWORD):
            result = WindowsSessionQueryResult(
                WindowsSessionQueryStatus.QUERY_FAILED,
                win32_error=_ERROR_INVALID_DATA,
            )
        else:
            state = int(
                ctypes.cast(buffer, ctypes.POINTER(wintypes.DWORD)).contents.value
            )
            if state not in _WTS_VALID_CONNECT_STATES:
                result = WindowsSessionQueryResult(
                    WindowsSessionQueryStatus.QUERY_FAILED,
                    win32_error=_ERROR_INVALID_DATA,
                )
            elif state == _WTS_ACTIVE:
                result = WindowsSessionQueryResult(
                    WindowsSessionQueryStatus.ACTIVE,
                    state=state,
                )
            else:
                result = WindowsSessionQueryResult(
                    WindowsSessionQueryStatus.INACTIVE,
                    state=state,
                )
    finally:
        if ctypes.cast(buffer, wintypes.LPVOID).value:
            try:
                wtsapi32.WTSFreeMemory(buffer)
            except OSError:
                result = WindowsSessionQueryResult(
                    WindowsSessionQueryStatus.QUERY_FAILED,
                    win32_error=_ERROR_INVALID_DATA,
                )
    return result


def windows_session_is_active(session_id: int) -> WindowsSessionQueryResult:
    """Return ACTIVE, INACTIVE(state), or QUERY_FAILED(win32_error)."""
    return _query_windows_session_state(_wtsapi32(), session_id)


def authenticated_client_windows_session_state(
    pipe: int, session_id: int
) -> WindowsSessionQueryResult:
    """Run one WTS query as the authenticated pipe client on a disposable worker.

    The WTS DLL is loaded before impersonation.  While impersonating, the worker
    performs only the single session query and its required buffer cleanup.
    Reversion is positively verified before the clean service thread consumes
    the result.
    """
    try:
        _assert_thread_not_impersonating()
    except BaseException as error:
        raise ProviderServiceIdentityUncertain(
            "Authority service thread identity is not clean before WTS validation"
        ) from error
    wtsapi32 = _wtsapi32()
    completed = threading.Event()
    outcome: list[WindowsSessionQueryResult | BaseException] = []

    def worker() -> None:
        try:
            _assert_thread_not_impersonating()
            ctypes.set_last_error(0)
            if not _advapi32().ImpersonateNamedPipeClient(pipe):
                error = ctypes.get_last_error()
                try:
                    _assert_thread_not_impersonating()
                except BaseException as verification_error:
                    outcome.append(verification_error)
                else:
                    outcome.append(
                        PermissionError(
                            "authenticated-client WTS impersonation failed "
                            f"(win32_error={error}, "
                            f"symbolic={_win32_error_name(error)})"
                        )
                    )
                return
            query_result: WindowsSessionQueryResult | None = None
            try:
                query_result = _query_windows_session_state(wtsapi32, session_id)
            finally:
                reverted = bool(_advapi32().RevertToSelf())
                revert_error = 0 if reverted else ctypes.get_last_error()
            try:
                _assert_thread_not_impersonating()
            except BaseException as verification_error:
                outcome.append(
                    ProviderLaunchIdentityUncertain(
                        "authenticated-client WTS identity reversion "
                        "could not be verified"
                    )
                )
                outcome.append(verification_error)
                return
            if not reverted:
                outcome.append(
                    ProviderLaunchIdentityUncertain(
                        "authenticated-client WTS identity could not be reverted "
                        f"(win32_error={revert_error}, "
                        f"symbolic={_win32_error_name(revert_error)})"
                    )
                )
                return
            if query_result is None:
                outcome.append(
                    PermissionError("authenticated-client WTS query produced no result")
                )
                return
            outcome.append(query_result)
        except BaseException as error:
            outcome.append(error)
        finally:
            completed.set()

    validation_thread = threading.Thread(
        target=worker,
        name="KeeperAuthenticatedClientWtsValidation",
        daemon=True,
    )
    validation_thread.start()
    completed.wait()
    validation_thread.join()
    try:
        _assert_thread_not_impersonating()
    except BaseException as error:
        raise ProviderServiceIdentityUncertain(
            "Authority service thread identity is not clean after WTS validation"
        ) from error
    if not outcome:
        raise PermissionError("authenticated-client WTS validation produced no outcome")
    first = outcome[0]
    if isinstance(first, BaseException):
        raise first
    return first


def authenticated_client_environment(token: int) -> dict[str, str]:
    """Build a user environment from the exact authenticated pipe token.

    ``CreateEnvironmentBlock`` supports an impersonation token with
    ``TOKEN_QUERY`` access.  Keeping the environment lookup on the captured
    named-pipe token avoids converting the process token to a primary token
    for a read-only profile lookup.  The service thread does not impersonate
    the client while this API is called.
    """
    require_impersonation_level(token)
    return _token_environment(
        token,
        token_type="authenticated-impersonation",
        required_access="TOKEN_QUERY",
    )


def token_environment(token: int) -> dict[str, str]:
    """Build a user environment from a profile primary token."""
    return _token_environment(
        token,
        token_type="primary",
        required_access="TOKEN_QUERY|TOKEN_DUPLICATE",
    )


def _token_environment(
    token: int,
    *,
    token_type: str,
    required_access: str,
) -> dict[str, str]:
    block = wintypes.LPVOID()
    if not _userenv().CreateEnvironmentBlock(ctypes.byref(block), token, False):
        error = ctypes.get_last_error()
        raise PermissionError(
            "provider profile environment is unavailable "
            f"(api=CreateEnvironmentBlock, token_type={token_type}, "
            f"required_access={required_access}, "
            f"win32_error={error}, symbolic={_win32_error_name(error)})"
        )
    try:
        pointer = ctypes.cast(block, ctypes.POINTER(ctypes.c_wchar))
        characters: list[str] = []
        index = 0
        while True:
            character = pointer[index]
            if character == "\0" and pointer[index + 1] == "\0":
                break
            characters.append(character)
            index += 1
        result: dict[str, str] = {}
        for entry in "".join(characters).split("\0"):
            if not entry or "=" not in entry:
                continue
            name, value = entry.split("=", 1)
            if name:
                result[name] = value
        return result
    finally:
        _userenv().DestroyEnvironmentBlock(block)


def _win32_error_name(error: int) -> str:
    return {
        5: "ERROR_ACCESS_DENIED",
        6: "ERROR_INVALID_HANDLE",
        87: "ERROR_INVALID_PARAMETER",
        1314: "ERROR_PRIVILEGE_NOT_HELD",
    }.get(error, "WIN32_ERROR")


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
    *,
    on_resumed: Callable[[dict[str, object]], None] | None = None,
    stdin_path: Path | None = None,
    integrity_level: str = "low",
    validated_executable_identity: dict[str, Any] | None = None,
    active_process_limit: int | None = None,
    memory_bytes: int | None = None,
    stdout_bytes: int | None = None,
    stderr_bytes: int | None = None,
) -> RestrictedProcessResult:
    if os.name != "nt":
        raise RuntimeError("restricted provider execution requires Windows")
    observed_integrity = token_integrity_level(token)
    if observed_integrity != integrity_level:
        raise PermissionError(
            "provider token integrity differs from the requested launch: "
            f"expected {integrity_level}, observed {observed_integrity}"
        )
    if validated_executable_identity is None:
        executable = executable.resolve(strict=True)
        executable_digest: str | None = None
    else:
        fields = {
            "canonical_path",
            "sha256",
            "size",
            "file_identity",
            "authenticode_binding",
        }
        canonical_path = validated_executable_identity.get("canonical_path")
        executable_digest = validated_executable_identity.get("sha256")
        executable_size = validated_executable_identity.get("size")
        if (
            set(validated_executable_identity) != fields
            or not isinstance(canonical_path, str)
            or not Path(canonical_path).is_absolute()
            or os.path.normcase(os.path.abspath(str(executable)))
            != os.path.normcase(canonical_path)
            or not isinstance(executable_digest, str)
            or len(executable_digest) != 64
            or any(
                character not in "0123456789abcdef"
                for character in executable_digest
            )
            or isinstance(executable_size, bool)
            or not isinstance(executable_size, int)
            or executable_size <= 0
        ):
            raise PermissionError(
                "provider validated executable identity is invalid"
            )
        try:
            file_identity = validate_executable_file_identity(
                validated_executable_identity.get("file_identity")
            )
            validate_codex_authenticode_binding(
                validated_executable_identity.get("authenticode_binding")
            )
        except ValueError as error:
            raise PermissionError(
                "provider validated executable identity is invalid"
            ) from error
        if file_identity["size"] != executable_size:
            raise PermissionError(
                "provider validated executable identity is invalid"
            )
        executable = Path(canonical_path)
    workspace = workspace.resolve(strict=True)
    stdout_path.parent.mkdir(parents=True, exist_ok=True)
    stderr_path.parent.mkdir(parents=True, exist_ok=True)
    handles: list[int] = []
    process = _ProcessInformation()
    job = 0
    attribute_buffer: ctypes.Array[ctypes.c_char] | None = None
    # UpdateProcThreadAttribute stores a pointer to this backing HANDLE array;
    # retaining only the attribute-list buffer permits the array to be garbage
    # collected before CreateProcessAsUserW and intermittently yields Win32 87.
    attribute_handles: ctypes.Array[ctypes.c_void_p] | None = None
    stdout_handle = _open_inheritable_output(stdout_path)
    stderr_handle = _open_inheritable_output(stderr_path)
    stdin_handle = _open_inheritable_input(stdin_path or Path(os.devnull))
    handles.extend((stdin_handle, stdout_handle, stderr_handle))
    try:
        job = _create_job(
            active_process_limit=active_process_limit,
            memory_bytes=memory_bytes,
        )
        attribute_buffer, attribute_list, attribute_handles = _handle_allowlist(
            handles
        )
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
        def create_process() -> bool:
            if attribute_handles is None or len(attribute_handles) != len(handles):
                raise RuntimeError("provider handle allowlist lifetime is uncertain")
            return bool(
                _advapi32().CreateProcessAsUserW(
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
                )
            )

        if validated_executable_identity is not None:
            if integrity_level != "medium" or not _advapi32().IsTokenRestricted(
                token
            ):
                raise PermissionError(
                    "validated provider launch token is not restricted Medium"
                )
            _create_process_with_bounded_restricted_impersonation(
                token, process, create_process
            )
        elif not create_process():
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
                if executable_digest is None:
                    executable_digest = hashlib.sha256(
                        executable.read_bytes()
                    ).hexdigest()
                on_started(
                    {
                        "pid": int(process.dwProcessId),
                        "creation_time": _process_creation_time(process.hProcess),
                        "executable": str(executable),
                        "executable_sha256": executable_digest,
                        "restricted": True,
                        "integrity_level": observed_integrity,
                        "job_confined": True,
                    }
                )
            if _kernel32().ResumeThread(process.hThread) != 1:
                raise PermissionError(
                    "restricted provider primary thread did not resume exactly once"
                )
            if on_resumed is not None:
                on_resumed({"pid": int(process.dwProcessId)})
            deadline = time.monotonic() + timeout_seconds
            timed_out = False
            cancelled = False
            while True:
                if (
                    stdout_bytes is not None
                    and stdout_path.exists()
                    and stdout_path.stat().st_size > stdout_bytes
                ) or (
                    stderr_bytes is not None
                    and stderr_path.exists()
                    and stderr_path.stat().st_size > stderr_bytes
                ):
                    if not _kernel32().TerminateJobObject(job, 122):
                        raise RuntimeError(
                            "restricted provider output-limit cleanup failed"
                        )
                    raise PermissionError(
                        "restricted provider output exceeded the signed limit"
                    )
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
    if executable_digest is None:
        executable_digest = hashlib.sha256(executable.read_bytes()).hexdigest()
    return RestrictedProcessResult(
        int(process.dwProcessId),
        int(exit_code.value),
        stdout_path.read_text(encoding="utf-8", errors="replace")[:1_048_576],
        stderr_path.read_text(encoding="utf-8", errors="replace")[:1_048_576],
        str(executable),
        executable_digest,
        True,
        observed_integrity,
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
) -> tuple[
    ctypes.Array[ctypes.c_char],
    int,
    ctypes.Array[ctypes.c_void_p],
]:
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
    return (
        buffer,
        int(ctypes.cast(pointer, ctypes.c_void_p).value or 0),
        handle_array,
    )


def _environment_block(environment: dict[str, str]) -> str:
    values = [
        f"{key}={value}"
        for key, value in sorted(environment.items(), key=lambda item: item[0].casefold())
        if "\0" not in key and "\0" not in value and "=" not in key
    ]
    return "\0".join(values) + "\0\0"


def _create_job(
    *,
    active_process_limit: int | None = None,
    memory_bytes: int | None = None,
) -> int:
    job = _kernel32().CreateJobObjectW(None, None)
    if not job:
        raise OSError(
            ctypes.get_last_error(), "restricted provider Job creation failed"
        )
    information = _JobExtendedLimitInformation()
    information.BasicLimitInformation.LimitFlags = (
        _JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
    )
    if active_process_limit is not None:
        if active_process_limit <= 0:
            _kernel32().CloseHandle(job)
            raise ValueError("provider active-process limit is invalid")
        information.BasicLimitInformation.LimitFlags |= (
            _JOB_OBJECT_LIMIT_ACTIVE_PROCESS
        )
        information.BasicLimitInformation.ActiveProcessLimit = (
            active_process_limit
        )
    if memory_bytes is not None:
        if memory_bytes <= 0:
            _kernel32().CloseHandle(job)
            raise ValueError("provider memory limit is invalid")
        information.BasicLimitInformation.LimitFlags |= (
            _JOB_OBJECT_LIMIT_JOB_MEMORY
        )
        information.JobMemoryLimit = memory_bytes
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
    kernel32.TerminateProcess.argtypes = [wintypes.HANDLE, wintypes.UINT]
    kernel32.TerminateProcess.restype = wintypes.BOOL
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
    advapi32.ConvertSidToStringSidW.argtypes = [
        wintypes.LPVOID,
        ctypes.POINTER(wintypes.LPWSTR),
    ]
    advapi32.ConvertSidToStringSidW.restype = wintypes.BOOL
    advapi32.GetLengthSid.argtypes = [wintypes.LPVOID]
    advapi32.GetLengthSid.restype = wintypes.DWORD
    advapi32.GetSidSubAuthorityCount.argtypes = [wintypes.LPVOID]
    advapi32.GetSidSubAuthorityCount.restype = ctypes.POINTER(ctypes.c_ubyte)
    advapi32.GetSidSubAuthority.argtypes = [wintypes.LPVOID, wintypes.DWORD]
    advapi32.GetSidSubAuthority.restype = ctypes.POINTER(wintypes.DWORD)
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


def _userenv() -> Any:
    userenv: Any = ctypes.WinDLL("userenv", use_last_error=True)
    userenv.CreateEnvironmentBlock.argtypes = [
        ctypes.POINTER(wintypes.LPVOID),
        wintypes.HANDLE,
        wintypes.BOOL,
    ]
    userenv.CreateEnvironmentBlock.restype = wintypes.BOOL
    userenv.DestroyEnvironmentBlock.argtypes = [wintypes.LPVOID]
    userenv.DestroyEnvironmentBlock.restype = wintypes.BOOL
    return userenv


def _wtsapi32() -> Any:
    wtsapi32: Any = ctypes.WinDLL("wtsapi32", use_last_error=True)
    wtsapi32.WTSQuerySessionInformationW.argtypes = [
        wintypes.HANDLE,
        wintypes.DWORD,
        ctypes.c_int,
        ctypes.POINTER(wintypes.LPWSTR),
        ctypes.POINTER(wintypes.DWORD),
    ]
    wtsapi32.WTSQuerySessionInformationW.restype = wintypes.BOOL
    wtsapi32.WTSFreeMemory.argtypes = [wintypes.LPVOID]
    wtsapi32.WTSFreeMemory.restype = None
    return wtsapi32


def _handle_value(handle: object) -> int:
    value = getattr(handle, "value", handle)
    if not isinstance(value, int) or value <= 0:
        raise OSError("Windows handle is invalid")
    return value
