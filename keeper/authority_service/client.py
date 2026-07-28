from __future__ import annotations

import ctypes
import os
import time
from ctypes import wintypes
from pathlib import Path
from typing import Any, Callable

from keeper.authority_service.protocol import (
    PROTOCOL_VERSION,
    Operation,
    Request,
    decode_frame,
    encode_frame,
    parse_response,
)
from keeper.authority_service.provenance import validate_provenance_report


DEFAULT_PIPE_NAME = r"\\.\pipe\KeeperAuthority-v1"


class AuthorityServiceClient:
    """Fail-closed client for the local Keeper Authority Windows service."""

    def __init__(
        self,
        pipe_name: str = DEFAULT_PIPE_NAME,
        *,
        timeout_seconds: float = 15.0,
        test_transport: Callable[[Request], dict[str, Any]] | None = None,
    ) -> None:
        self.pipe_name = pipe_name
        self.timeout_seconds = timeout_seconds
        self._test_transport = test_transport

    def request(
        self, operation: Operation, payload: dict[str, Any]
    ) -> dict[str, Any]:
        request = Request.create(operation, payload)
        return self._send(request)

    def _send(self, request: Request) -> dict[str, Any]:
        if self._test_transport is not None:
            return self._test_transport(request)
        if os.name != "nt":
            raise RuntimeError("Keeper Authority Service requires Windows")
        handle = _connect(self.pipe_name, self.timeout_seconds)
        try:
            _write_all(handle, encode_frame(request.to_dict()))
            response = decode_frame(lambda length: _read(handle, length))
        finally:
            _close(handle)
        return parse_response(response, request.request_id)

    def diagnostics(self) -> dict[str, Any]:
        return self.request(Operation.DIAGNOSTICS, {})

    def audit_provenance(self) -> dict[str, Any]:
        request = Request.create(Operation.AUDIT_PROVENANCE, {})
        result = self._send(request)
        if set(result) != {"report"}:
            raise RuntimeError(
                "Authority provenance response fields are invalid"
            )
        return validate_provenance_report(result["report"], request)

    def register_provider(self, provider_id: str, executable: Path) -> dict[str, Any]:
        return self.request(
            Operation.REGISTER_PROVIDER,
            {"provider_id": provider_id, "executable": str(executable.resolve())},
        )

    def qualify_provider(self, registration_id: str) -> dict[str, Any]:
        return self.request(
            Operation.BEGIN_QUALIFICATION,
            {"registration_id": registration_id},
        )

    def reserve_attempt(self, **identity: Any) -> dict[str, Any]:
        return self.request(Operation.RESERVE_ATTEMPT, dict(identity))

    def authorize_project_launch(self, **identity: Any) -> dict[str, Any]:
        return self.request(Operation.AUTHORIZE_PROJECT_LAUNCH, dict(identity))

    def revoke_project_launch(
        self, project_id: str, authorization_generation: int
    ) -> dict[str, Any]:
        return self.request(
            Operation.REVOKE_PROJECT_LAUNCH,
            {
                "project_id": project_id,
                "authorization_generation": authorization_generation,
            },
        )

    def record_provider_start(self, attempt_id: str, pid: int) -> dict[str, Any]:
        return self.request(
            Operation.RECORD_PROVIDER_START,
            {"attempt_id": attempt_id, "pid": pid},
        )

    def execute_provider(self, attempt_id: str) -> dict[str, Any]:
        return self.request(
            Operation.EXECUTE_PROVIDER, {"attempt_id": attempt_id}
        )

    def finalize_completion(self, attempt_id: str) -> dict[str, Any]:
        return self.request(
            Operation.FINALIZE_COMPLETION, {"attempt_id": attempt_id}
        )

    def cancel_attempt(self, attempt_id: str) -> dict[str, Any]:
        return self.request(
            Operation.CANCEL_ATTEMPT, {"attempt_id": attempt_id}
        )

    def query_state(self, kind: str, identifier: str) -> dict[str, Any]:
        return self.request(Operation.QUERY_STATE, {"kind": kind, "id": identifier})

    def reconcile_executive_restore(self, **identity: Any) -> dict[str, Any]:
        return self.request(
            Operation.RECONCILE_EXECUTIVE_RESTORE, dict(identity)
        )

    def verify(self, purpose: str, record: object) -> bool:
        return bool(
            self.request(
                Operation.VERIFY_EVIDENCE,
                {"purpose": purpose, "record": record},
            ).get("valid")
        )

    def rotate_key(self, confirmation: str) -> dict[str, Any]:
        return self.request(Operation.ROTATE_KEY, {"confirmation": confirmation})

    def migrate_legacy(
        self, registrations: list[dict[str, Any]]
    ) -> dict[str, Any]:
        return self.request(
            Operation.MIGRATE_LEGACY, {"registrations": registrations}
        )


class ProductionAuthorityServiceClient(AuthorityServiceClient):
    """Structurally production-only client with fixed authenticated IPC transport."""

    __slots__ = ()

    def __init__(
        self,
        pipe_name: str = DEFAULT_PIPE_NAME,
        *,
        timeout_seconds: float = 15.0,
    ) -> None:
        if pipe_name != DEFAULT_PIPE_NAME:
            raise RuntimeError("production Authority endpoint is not canonical")
        super().__init__(pipe_name, timeout_seconds=timeout_seconds)
        del self._test_transport

    def _send(self, request: Request) -> dict[str, Any]:
        if os.name != "nt":
            raise RuntimeError("Keeper Authority Service requires Windows")
        handle = _connect(self.pipe_name, self.timeout_seconds)
        try:
            _write_all(handle, encode_frame(request.to_dict()))
            response = decode_frame(lambda length: _read(handle, length))
        finally:
            _close(handle)
        return parse_response(response, request.request_id)

    def require_live_identity(self) -> dict[str, Any]:
        diagnostics = self.diagnostics()
        if (
            diagnostics.get("protocol_version") != PROTOCOL_VERSION
            or diagnostics.get("observer_available") is not True
            or not isinstance(diagnostics.get("service_root"), str)
            or not isinstance(diagnostics.get("service_key_id"), str)
            or not isinstance(diagnostics.get("service_key_version"), int)
            or not isinstance(diagnostics.get("client_sid"), str)
        ):
            raise RuntimeError("live Keeper Authority identity is invalid")
        return diagnostics


class TestAuthorityServiceClient(AuthorityServiceClient):
    """Explicit test-only injected Authority transport."""

    __test__ = False
    __slots__ = ()

    def __init__(self, test_transport: Callable[[Request], dict[str, Any]]) -> None:
        super().__init__(test_transport=test_transport)


def _connect(pipe_name: str, timeout_seconds: float) -> int:
    kernel32 = _kernel32()
    deadline = time.monotonic() + timeout_seconds
    last_error = 2
    while time.monotonic() < deadline:
        remaining = max(1, int((deadline - time.monotonic()) * 1000))
        if not kernel32.WaitNamedPipeW(pipe_name, min(remaining, 250)):
            last_error = ctypes.get_last_error()
            if last_error in {2, 121, 231}:
                time.sleep(0.01)
                continue
            raise PermissionError(
                f"Keeper Authority Service connection was rejected: {last_error}"
            )
        handle = kernel32.CreateFileW(
            pipe_name,
            0xC0000000,
            0,
            None,
            3,
            0,
            None,
        )
        if handle not in {None, ctypes.c_void_p(-1).value}:
            return int(handle)
        last_error = ctypes.get_last_error()
        if last_error not in {2, 121, 231}:
            raise PermissionError(
                f"Keeper Authority Service connection was rejected: {last_error}"
            )
    raise TimeoutError(f"Keeper Authority Service is unavailable: {last_error}")


def _write_all(handle: int, value: bytes) -> None:
    offset = 0
    kernel32 = _kernel32()
    while offset < len(value):
        written = wintypes.DWORD()
        chunk = value[offset:]
        buffer = ctypes.create_string_buffer(chunk)
        if not kernel32.WriteFile(
            handle, buffer, len(chunk), ctypes.byref(written), None
        ):
            raise OSError(
                ctypes.get_last_error(), "Keeper Authority IPC write failed"
            )
        if written.value <= 0:
            raise OSError("Keeper Authority IPC write stalled")
        offset += int(written.value)


def _read(handle: int, length: int) -> bytes:
    kernel32 = _kernel32()
    buffer = ctypes.create_string_buffer(length)
    read = wintypes.DWORD()
    if not kernel32.ReadFile(
        handle, buffer, length, ctypes.byref(read), None
    ):
        error = ctypes.get_last_error()
        if error == 109:
            return b""
        raise OSError(error, "Keeper Authority IPC read failed")
    return buffer.raw[: read.value]


def _close(handle: int) -> None:
    if not _kernel32().CloseHandle(handle):
        raise OSError(ctypes.get_last_error(), "Keeper Authority IPC close failed")


def _kernel32() -> Any:
    kernel32: Any = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.WaitNamedPipeW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD]
    kernel32.WaitNamedPipeW.restype = wintypes.BOOL
    kernel32.CreateFileW.argtypes = [
        wintypes.LPCWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.LPVOID,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.HANDLE,
    ]
    kernel32.CreateFileW.restype = wintypes.HANDLE
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
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL
    return kernel32
