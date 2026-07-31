from __future__ import annotations

import ctypes
import os
from ctypes import wintypes
from dataclasses import dataclass
from pathlib import Path
from typing import Any


TOKEN_QUERY = 0x0008
TOKEN_USER = 1
TOKEN_INTEGRITY_LEVEL = 25
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000


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
