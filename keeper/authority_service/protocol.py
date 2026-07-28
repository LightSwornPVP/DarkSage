from __future__ import annotations

import json
import struct
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any, Callable


PROTOCOL_VERSION = 1
MAX_MESSAGE_BYTES = 1_048_576
REQUEST_FIELDS = frozenset(
    {
        "protocol_version",
        "request_id",
        "operation_id",
        "nonce",
        "issued_at",
        "operation",
        "payload",
    }
)
RESPONSE_FIELDS = frozenset(
    {"protocol_version", "request_id", "ok", "result", "error"}
)


class Operation(StrEnum):
    DIAGNOSTICS = "diagnostics"
    AUDIT_PROVENANCE = "audit_provenance"
    REGISTER_PROVIDER = "register_provider"
    BEGIN_QUALIFICATION = "begin_qualification"
    FINALIZE_QUALIFICATION = "finalize_qualification"
    RESERVE_ATTEMPT = "reserve_attempt"
    AUTHORIZE_PROJECT_LAUNCH = "authorize_project_launch"
    REVOKE_PROJECT_LAUNCH = "revoke_project_launch"
    EXECUTE_PROVIDER = "execute_provider"
    RECORD_PROVIDER_START = "record_provider_start"
    FINALIZE_COMPLETION = "finalize_completion"
    QUERY_STATE = "query_state"
    VERIFY_EVIDENCE = "verify_evidence"
    PAUSE_ATTEMPT = "pause_attempt"
    RESUME_ATTEMPT = "resume_attempt"
    CANCEL_ATTEMPT = "cancel_attempt"
    REVOKE_REGISTRATION = "revoke_registration"
    ROTATE_KEY = "rotate_key"
    MIGRATE_LEGACY = "migrate_legacy"


@dataclass(frozen=True, slots=True)
class Request:
    request_id: str
    operation_id: str
    nonce: str
    issued_at: str
    operation: Operation
    payload: dict[str, Any]

    @classmethod
    def create(cls, operation: Operation, payload: dict[str, Any]) -> Request:
        return cls(
            uuid.uuid4().hex,
            uuid.uuid4().hex,
            uuid.uuid4().hex + uuid.uuid4().hex,
            datetime.now(UTC).isoformat(),
            operation,
            payload,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "protocol_version": PROTOCOL_VERSION,
            "request_id": self.request_id,
            "operation_id": self.operation_id,
            "nonce": self.nonce,
            "issued_at": self.issued_at,
            "operation": self.operation.value,
            "payload": self.payload,
        }


def parse_request(value: object) -> Request:
    if not isinstance(value, dict) or frozenset(value) != REQUEST_FIELDS:
        raise ValueError("authority request fields are invalid")
    if value.get("protocol_version") != PROTOCOL_VERSION:
        raise ValueError("authority protocol version is incompatible")
    request_id = _hex_identifier(value.get("request_id"), 32, "request ID")
    operation_id = _hex_identifier(value.get("operation_id"), 32, "operation ID")
    nonce = _hex_identifier(value.get("nonce"), 64, "nonce")
    issued_at = _fresh_timestamp(value.get("issued_at"))
    try:
        operation = Operation(str(value.get("operation")))
    except ValueError as error:
        raise ValueError("authority operation is unsupported") from error
    payload = value.get("payload")
    if not isinstance(payload, dict):
        raise ValueError("authority request payload must be an object")
    return Request(request_id, operation_id, nonce, issued_at, operation, payload)


def encode_frame(value: dict[str, Any]) -> bytes:
    payload = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    if not payload or len(payload) > MAX_MESSAGE_BYTES:
        raise ValueError("authority message size is invalid")
    return struct.pack("<I", len(payload)) + payload


def decode_frame(read: Callable[[int], bytes]) -> dict[str, Any]:
    length = struct.unpack("<I", _read_exact(read, 4))[0]
    if length <= 0 or length > MAX_MESSAGE_BYTES:
        raise ValueError("authority message size is invalid")
    try:
        value = json.loads(_read_exact(read, length).decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("authority message encoding is invalid") from error
    if not isinstance(value, dict):
        raise ValueError("authority message must be an object")
    return value


def success_response(request_id: str, result: dict[str, Any]) -> dict[str, Any]:
    return {
        "protocol_version": PROTOCOL_VERSION,
        "request_id": request_id,
        "ok": True,
        "result": result,
        "error": None,
    }


def error_response(request_id: str, message: str) -> dict[str, Any]:
    return {
        "protocol_version": PROTOCOL_VERSION,
        "request_id": request_id,
        "ok": False,
        "result": None,
        "error": message,
    }


def parse_response(value: object, request_id: str) -> dict[str, Any]:
    if not isinstance(value, dict) or frozenset(value) != RESPONSE_FIELDS:
        raise RuntimeError("authority response fields are invalid")
    if (
        value.get("protocol_version") != PROTOCOL_VERSION
        or value.get("request_id") != request_id
        or not isinstance(value.get("ok"), bool)
    ):
        raise RuntimeError("authority response identity is invalid")
    if value["ok"]:
        result = value.get("result")
        if not isinstance(result, dict) or value.get("error") is not None:
            raise RuntimeError("authority success response is malformed")
        return result
    error = value.get("error")
    if not isinstance(error, str) or not error or value.get("result") is not None:
        raise RuntimeError("authority error response is malformed")
    raise PermissionError(error)


def _read_exact(read: Callable[[int], bytes], length: int) -> bytes:
    chunks: list[bytes] = []
    remaining = length
    while remaining:
        chunk = read(remaining)
        if not chunk:
            raise EOFError("authority IPC connection closed")
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


def _hex_identifier(value: object, length: int, label: str) -> str:
    if not isinstance(value, str) or len(value) != length:
        raise ValueError(f"authority {label} is invalid")
    try:
        bytes.fromhex(value)
    except ValueError as error:
        raise ValueError(f"authority {label} is invalid") from error
    return value


def _fresh_timestamp(value: object) -> str:
    if not isinstance(value, str):
        raise ValueError("authority request timestamp is invalid")
    try:
        issued = datetime.fromisoformat(value)
    except ValueError as error:
        raise ValueError("authority request timestamp is invalid") from error
    now = datetime.now(UTC)
    if (
        issued.tzinfo is None
        or issued < now - timedelta(seconds=60)
        or issued > now + timedelta(seconds=10)
    ):
        raise ValueError("authority request timestamp is stale")
    return issued.isoformat()
