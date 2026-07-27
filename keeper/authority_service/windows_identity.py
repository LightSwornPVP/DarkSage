from __future__ import annotations

import ctypes
import os
from ctypes import wintypes
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
        return _process_sid(int(process))
    finally:
        kernel32.CloseHandle(process)


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
        needed = wintypes.DWORD()
        advapi32.GetTokenInformation(token, TOKEN_USER, None, 0, ctypes.byref(needed))
        if not needed.value:
            raise PermissionError("Windows process token identity is unavailable")
        buffer = ctypes.create_string_buffer(needed.value)
        if not advapi32.GetTokenInformation(
            token, TOKEN_USER, buffer, needed, ctypes.byref(needed)
        ):
            raise PermissionError(
                f"Windows process identity cannot be read: {ctypes.get_last_error()}"
            )
        user = ctypes.cast(buffer, ctypes.POINTER(_TokenUser)).contents
        return _sid_string(user.User.Sid)
    finally:
        _kernel32().CloseHandle(token)


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
    advapi32.GetTokenInformation.argtypes = [
        wintypes.HANDLE,
        ctypes.c_int,
        wintypes.LPVOID,
        wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD),
    ]
    advapi32.GetTokenInformation.restype = wintypes.BOOL
    advapi32.ConvertSidToStringSidW.argtypes = [
        wintypes.LPVOID,
        ctypes.POINTER(wintypes.LPWSTR),
    ]
    advapi32.ConvertSidToStringSidW.restype = wintypes.BOOL
    return advapi32
