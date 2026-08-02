from __future__ import annotations

import ctypes
import os
import time
from contextlib import contextmanager
from ctypes import wintypes
from typing import Any, Iterator, Mapping

from keeper.provider_host.protocol import decode_frame, encode_frame


_PIPE_ACCESS_DUPLEX = 0x00000003
_FILE_FLAG_FIRST_PIPE_INSTANCE = 0x00080000
_PIPE_TYPE_BYTE = 0x00000000
_PIPE_READMODE_BYTE = 0x00000000
_PIPE_WAIT = 0x00000000
_PIPE_REJECT_REMOTE_CLIENTS = 0x00000008
_PIPE_UNLIMITED_INSTANCES = 255
_GENERIC_READ = 0x80000000
_GENERIC_WRITE = 0x40000000
_OPEN_EXISTING = 3
_ERROR_PIPE_CONNECTED = 535
_ERROR_PIPE_BUSY = 231
_INVALID_HANDLE = ctypes.c_void_p(-1).value
_SDDL_REVISION_1 = 1
_RESTRICTED_CODE_SID = "S-1-5-12"


class _SecurityAttributes(ctypes.Structure):
    _fields_ = [
        ("nLength", wintypes.DWORD),
        ("lpSecurityDescriptor", wintypes.LPVOID),
        ("bInheritHandle", wintypes.BOOL),
    ]


@contextmanager
def connected_server_pipe(
    pipe_name: str,
    *,
    user_sid: str,
    first_instance: bool,
) -> Iterator[int]:
    if os.name != "nt" or not pipe_name.startswith("\\\\.\\pipe\\"):
        raise RuntimeError("Provider Host named pipe requires Windows")
    if not user_sid.startswith("S-1-"):
        raise PermissionError("Provider Host user SID is invalid")
    kernel32 = _kernel32()
    with _security_attributes(user_sid) as security:
        access = _PIPE_ACCESS_DUPLEX | (
            _FILE_FLAG_FIRST_PIPE_INSTANCE if first_instance else 0
        )
        handle = kernel32.CreateNamedPipeW(
            pipe_name,
            access,
            _PIPE_TYPE_BYTE
            | _PIPE_READMODE_BYTE
            | _PIPE_WAIT
            | _PIPE_REJECT_REMOTE_CLIENTS,
            _PIPE_UNLIMITED_INSTANCES,
            2 * 1024 * 1024,
            2 * 1024 * 1024,
            0,
            ctypes.byref(security),
        )
    if handle in {None, _INVALID_HANDLE}:
        raise OSError(ctypes.get_last_error(), "Provider Host pipe creation failed")
    try:
        if not kernel32.ConnectNamedPipe(handle, None):
            error = ctypes.get_last_error()
            if error != _ERROR_PIPE_CONNECTED:
                raise OSError(error, "Provider Host pipe connection failed")
        yield int(handle)
    finally:
        kernel32.FlushFileBuffers(handle)
        kernel32.DisconnectNamedPipe(handle)
        if not kernel32.CloseHandle(handle):
            raise OSError(ctypes.get_last_error(), "Provider Host pipe did not close")


@contextmanager
def connected_client_pipe(
    pipe_name: str, *, timeout_seconds: float
) -> Iterator[int]:
    if os.name != "nt" or not pipe_name.startswith("\\\\.\\pipe\\"):
        raise RuntimeError("Provider Host named pipe requires Windows")
    kernel32 = _kernel32()
    deadline = time.monotonic() + timeout_seconds
    handle: int | None = None
    while time.monotonic() < deadline:
        raw = kernel32.CreateFileW(
            pipe_name,
            _GENERIC_READ | _GENERIC_WRITE,
            0,
            None,
            _OPEN_EXISTING,
            0,
            None,
        )
        if raw not in {None, _INVALID_HANDLE}:
            handle = int(raw)
            break
        error = ctypes.get_last_error()
        if error != _ERROR_PIPE_BUSY:
            raise OSError(error, "Provider Host pipe open failed")
        remaining = max(1, int((deadline - time.monotonic()) * 1000))
        kernel32.WaitNamedPipeW(pipe_name, min(remaining, 250))
    if handle is None:
        raise TimeoutError("Provider Host pipe was unavailable")
    try:
        yield handle
    finally:
        if not kernel32.CloseHandle(handle):
            raise OSError(ctypes.get_last_error(), "Provider Host pipe did not close")


def write_frame(handle: int, value: Mapping[str, object]) -> None:
    content = encode_frame(value)
    offset = 0
    kernel32 = _kernel32()
    while offset < len(content):
        written = wintypes.DWORD()
        buffer = ctypes.create_string_buffer(content[offset:])
        if not kernel32.WriteFile(
            wintypes.HANDLE(handle),
            buffer,
            len(content) - offset,
            ctypes.byref(written),
            None,
        ):
            raise OSError(ctypes.get_last_error(), "Provider Host pipe write failed")
        if written.value <= 0:
            raise EOFError("Provider Host pipe write ended early")
        offset += int(written.value)


def read_frame(handle: int) -> dict[str, object]:
    kernel32 = _kernel32()

    def read(length: int) -> bytes:
        buffer = ctypes.create_string_buffer(length)
        observed = wintypes.DWORD()
        if not kernel32.ReadFile(
            wintypes.HANDLE(handle),
            buffer,
            length,
            ctypes.byref(observed),
            None,
        ):
            raise OSError(ctypes.get_last_error(), "Provider Host pipe read failed")
        return buffer.raw[: observed.value]

    return decode_frame(read)


@contextmanager
def _security_attributes(user_sid: str) -> Iterator[_SecurityAttributes]:
    advapi32 = _advapi32()
    kernel32 = _kernel32()
    descriptor = wintypes.LPVOID()
    # The supported provider token deliberately retains user-profile access,
    # so the current-user allow ACE alone is not a Host/provider boundary.
    # Every provider token carries the Restricted Code SID; deny it before the
    # user grant so a compromised provider cannot open or create this endpoint.
    sddl = _pipe_security_sddl(user_sid)
    if not advapi32.ConvertStringSecurityDescriptorToSecurityDescriptorW(
        sddl,
        _SDDL_REVISION_1,
        ctypes.byref(descriptor),
        None,
    ):
        raise OSError(
            ctypes.get_last_error(), "Provider Host pipe DACL creation failed"
        )
    try:
        yield _SecurityAttributes(
            ctypes.sizeof(_SecurityAttributes), descriptor, False
        )
    finally:
        kernel32.LocalFree(descriptor)


def _pipe_security_sddl(user_sid: str) -> str:
    if not user_sid.startswith("S-1-"):
        raise ValueError("Provider Host pipe user SID is invalid")
    return (
        f"D:P(D;;GA;;;{_RESTRICTED_CODE_SID})"
        f"(A;;GA;;;SY)(A;;GA;;;{user_sid})"
    )


def _kernel32() -> Any:
    api = ctypes.WinDLL("kernel32", use_last_error=True)
    api.CreateNamedPipeW.restype = wintypes.HANDLE
    api.CreateFileW.restype = wintypes.HANDLE
    api.ConnectNamedPipe.restype = wintypes.BOOL
    api.DisconnectNamedPipe.restype = wintypes.BOOL
    api.FlushFileBuffers.restype = wintypes.BOOL
    api.CloseHandle.restype = wintypes.BOOL
    api.ReadFile.restype = wintypes.BOOL
    api.WriteFile.restype = wintypes.BOOL
    api.WaitNamedPipeW.restype = wintypes.BOOL
    api.LocalFree.restype = wintypes.HLOCAL
    return api


def _advapi32() -> Any:
    api = ctypes.WinDLL("advapi32", use_last_error=True)
    api.ConvertStringSecurityDescriptorToSecurityDescriptorW.argtypes = [
        wintypes.LPCWSTR,
        wintypes.DWORD,
        ctypes.POINTER(wintypes.LPVOID),
        ctypes.POINTER(wintypes.DWORD),
    ]
    api.ConvertStringSecurityDescriptorToSecurityDescriptorW.restype = wintypes.BOOL
    return api
