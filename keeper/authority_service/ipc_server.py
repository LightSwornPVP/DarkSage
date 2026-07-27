from __future__ import annotations

import ctypes
import threading
import time
from collections import defaultdict, deque
from ctypes import wintypes
from typing import Any

from keeper.authority_service.client import DEFAULT_PIPE_NAME
from keeper.authority_service.core import AuthorityServiceCore
from keeper.authority_service.protocol import (
    decode_frame,
    encode_frame,
    error_response,
    parse_request,
    success_response,
)
from keeper.authority_service.windows_identity import process_sid


_PIPE_ACCESS_DUPLEX = 0x00000003
_FILE_FLAG_FIRST_PIPE_INSTANCE = 0x00080000
_PIPE_TYPE_BYTE = 0x00000000
_PIPE_READMODE_BYTE = 0x00000000
_PIPE_WAIT = 0x00000000
_PIPE_REJECT_REMOTE_CLIENTS = 0x00000008
_PIPE_UNLIMITED_INSTANCES = 255
_ERROR_PIPE_CONNECTED = 535
_ERROR_BROKEN_PIPE = 109


class _SecurityAttributes(ctypes.Structure):
    _fields_ = [
        ("nLength", wintypes.DWORD),
        ("lpSecurityDescriptor", wintypes.LPVOID),
        ("bInheritHandle", wintypes.BOOL),
    ]


class NamedPipeAuthorityServer:
    def __init__(
        self,
        core: AuthorityServiceCore,
        authorized_client_sid: str,
        *,
        pipe_name: str = DEFAULT_PIPE_NAME,
        maximum_concurrency: int = 4,
        requests_per_minute: int = 120,
    ) -> None:
        if not authorized_client_sid.startswith("S-1-"):
            raise ValueError("authorized Keeper client SID is invalid")
        self.core = core
        self.authorized_client_sid = authorized_client_sid
        self.pipe_name = pipe_name
        self.maximum_concurrency = maximum_concurrency
        self.requests_per_minute = requests_per_minute
        self._stop = threading.Event()
        self._slots = threading.BoundedSemaphore(maximum_concurrency)
        self._rate_lock = threading.Lock()
        self._request_times: dict[str, deque[float]] = defaultdict(deque)
        self._threads: set[threading.Thread] = set()

    def serve_forever(self) -> None:
        first = True
        while not self._stop.is_set():
            pipe = self._create_pipe(first)
            first = False
            kernel32 = _kernel32()
            connected = bool(kernel32.ConnectNamedPipe(pipe, None))
            error = ctypes.get_last_error()
            if not connected and error != _ERROR_PIPE_CONNECTED:
                kernel32.CloseHandle(pipe)
                if self._stop.is_set():
                    break
                raise OSError(error, "Keeper Authority named-pipe accept failed")
            thread = threading.Thread(
                target=self._serve_connection,
                args=(int(pipe),),
                name="keeper-authority-ipc",
                daemon=True,
            )
            self._threads.add(thread)
            thread.start()

    def stop(self) -> None:
        self._stop.set()
        # The service host may terminate after SCM stop timeout; active requests are
        # bounded by provider/request timeouts and never receive a partially signed result.
        for thread in tuple(self._threads):
            thread.join(timeout=5)

    def _serve_connection(self, pipe: int) -> None:
        request_id = "0" * 32
        try:
            client_sid = self._authenticated_client_sid(pipe)
            self._rate_limit(client_sid)
            if not self._slots.acquire(timeout=5):
                raise PermissionError("authority service concurrency limit reached")
            try:
                request = parse_request(
                    decode_frame(lambda length: _read(pipe, length))
                )
                request_id = request.request_id
                result = self.core.dispatch(request, client_sid)
                response = success_response(request_id, result)
            finally:
                self._slots.release()
        except (
            EOFError,
            OSError,
            PermissionError,
            RuntimeError,
            TypeError,
            ValueError,
        ) as error:
            response = error_response(request_id, str(error))
        try:
            _write(pipe, encode_frame(response))
            _kernel32().FlushFileBuffers(pipe)
        except OSError:
            pass
        finally:
            kernel32 = _kernel32()
            kernel32.DisconnectNamedPipe(pipe)
            kernel32.CloseHandle(pipe)
            self._threads.discard(threading.current_thread())

    def _authenticated_client_sid(self, pipe: int) -> str:
        process_id = wintypes.ULONG()
        if not _kernel32().GetNamedPipeClientProcessId(
            pipe, ctypes.byref(process_id)
        ):
            raise PermissionError(
                f"authority client process identity unavailable: {ctypes.get_last_error()}"
            )
        sid = process_sid(int(process_id.value))
        if sid != self.authorized_client_sid:
            raise PermissionError("authority client identity is unauthorized")
        return sid

    def _rate_limit(self, client_sid: str) -> None:
        now = time.monotonic()
        with self._rate_lock:
            requests = self._request_times[client_sid]
            while requests and requests[0] < now - 60:
                requests.popleft()
            if len(requests) >= self.requests_per_minute:
                raise PermissionError("authority service request rate limit reached")
            requests.append(now)

    def _create_pipe(self, first: bool) -> int:
        descriptor = wintypes.LPVOID()
        # Owner/SYSTEM and the configured desktop SID can use the pipe. The
        # mandatory medium label rejects low-integrity restricted providers.
        sddl = (
            "D:P(A;;GA;;;SY)(A;;GA;;;OW)"
            f"(A;;GRGW;;;{self.authorized_client_sid})"
            "S:(ML;;NW;;;ME)"
        )
        if not _advapi32().ConvertStringSecurityDescriptorToSecurityDescriptorW(
            sddl, 1, ctypes.byref(descriptor), None
        ):
            raise PermissionError(
                f"authority IPC security descriptor failed: {ctypes.get_last_error()}"
            )
        attributes = _SecurityAttributes(
            ctypes.sizeof(_SecurityAttributes), descriptor, False
        )
        try:
            open_mode = _PIPE_ACCESS_DUPLEX
            if first:
                open_mode |= _FILE_FLAG_FIRST_PIPE_INSTANCE
            handle = _kernel32().CreateNamedPipeW(
                self.pipe_name,
                open_mode,
                _PIPE_TYPE_BYTE
                | _PIPE_READMODE_BYTE
                | _PIPE_WAIT
                | _PIPE_REJECT_REMOTE_CLIENTS,
                _PIPE_UNLIMITED_INSTANCES,
                1_048_580,
                1_048_580,
                15_000,
                ctypes.byref(attributes),
            )
            if handle in {None, ctypes.c_void_p(-1).value}:
                raise PermissionError(
                    f"authority named pipe creation failed: {ctypes.get_last_error()}"
                )
            return int(handle)
        finally:
            _kernel32().LocalFree(descriptor)


def _read(handle: int, length: int) -> bytes:
    buffer = ctypes.create_string_buffer(length)
    read = wintypes.DWORD()
    if not _kernel32().ReadFile(
        handle, buffer, length, ctypes.byref(read), None
    ):
        error = ctypes.get_last_error()
        if error == _ERROR_BROKEN_PIPE:
            return b""
        raise OSError(error, "authority named-pipe read failed")
    return buffer.raw[: read.value]


def _write(handle: int, value: bytes) -> None:
    offset = 0
    while offset < len(value):
        buffer = ctypes.create_string_buffer(value[offset:])
        written = wintypes.DWORD()
        if not _kernel32().WriteFile(
            handle,
            buffer,
            len(value) - offset,
            ctypes.byref(written),
            None,
        ):
            raise OSError(
                ctypes.get_last_error(), "authority named-pipe write failed"
            )
        if not written.value:
            raise OSError("authority named-pipe write stalled")
        offset += int(written.value)


def _kernel32() -> Any:
    kernel32: Any = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateNamedPipeW.argtypes = [
        wintypes.LPCWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.DWORD,
        ctypes.POINTER(_SecurityAttributes),
    ]
    kernel32.CreateNamedPipeW.restype = wintypes.HANDLE
    kernel32.ConnectNamedPipe.argtypes = [wintypes.HANDLE, wintypes.LPVOID]
    kernel32.ConnectNamedPipe.restype = wintypes.BOOL
    kernel32.DisconnectNamedPipe.argtypes = [wintypes.HANDLE]
    kernel32.DisconnectNamedPipe.restype = wintypes.BOOL
    kernel32.GetNamedPipeClientProcessId.argtypes = [
        wintypes.HANDLE,
        ctypes.POINTER(wintypes.ULONG),
    ]
    kernel32.GetNamedPipeClientProcessId.restype = wintypes.BOOL
    kernel32.ReadFile.argtypes = [
        wintypes.HANDLE,
        wintypes.LPVOID,
        wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD),
        wintypes.LPVOID,
    ]
    kernel32.ReadFile.restype = wintypes.BOOL
    kernel32.WriteFile.argtypes = kernel32.ReadFile.argtypes
    kernel32.WriteFile.restype = wintypes.BOOL
    kernel32.FlushFileBuffers.argtypes = [wintypes.HANDLE]
    kernel32.FlushFileBuffers.restype = wintypes.BOOL
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL
    kernel32.LocalFree.argtypes = [wintypes.HLOCAL]
    kernel32.LocalFree.restype = wintypes.HLOCAL
    return kernel32


def _advapi32() -> Any:
    advapi32: Any = ctypes.WinDLL("advapi32", use_last_error=True)
    advapi32.ConvertStringSecurityDescriptorToSecurityDescriptorW.argtypes = [
        wintypes.LPCWSTR,
        wintypes.DWORD,
        ctypes.POINTER(wintypes.LPVOID),
        ctypes.POINTER(wintypes.DWORD),
    ]
    advapi32.ConvertStringSecurityDescriptorToSecurityDescriptorW.restype = (
        wintypes.BOOL
    )
    return advapi32
