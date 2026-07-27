from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from keeper.authority_service.client import AuthorityServiceClient
from keeper.authority_service.core import (
    AuthorityServiceCore,
    CompletionObservation,
    ProcessObservation,
    QualificationObservation,
)
from keeper.authority_service.protocol import (
    MAX_MESSAGE_BYTES,
    Operation,
    Request,
    decode_frame,
    encode_frame,
    parse_request,
)


class _Observer:
    def __init__(self, executable: Path) -> None:
        self.executable = executable.resolve()
        self.evidence_digest = hashlib.sha256(b"evidence").hexdigest()

    def qualify(
        self, registration: dict[str, Any], challenge: str
    ) -> QualificationObservation:
        timestamp = datetime.now(UTC).isoformat()
        return QualificationObservation(
            "qualified-instance",
            {
                "pid": 4411,
                "launch_nonce": challenge,
                "restricted": True,
                "job_confined": True,
                "integrity_level": "low",
            },
            timestamp,
            timestamp,
            0,
            "controlled-provider 1.2.3",
        )

    def observe_process(
        self, attempt: dict[str, Any], pid: int
    ) -> ProcessObservation:
        content = self.executable.read_bytes()
        return ProcessObservation(
            pid,
            "2026-07-27T00:00:00+00:00",
            str(self.executable),
            hashlib.sha256(content).hexdigest(),
            True,
            "low",
            True,
        )

    def observe_completion(
        self, attempt: dict[str, Any]
    ) -> CompletionObservation:
        return CompletionObservation(
            self.evidence_digest,
            0,
            "completed",
            datetime.now(UTC).isoformat(),
        )


def _service(tmp_path: Path) -> tuple[AuthorityServiceCore, AuthorityServiceClient]:
    executable = tmp_path / "controlled-provider.exe"
    executable.write_bytes(b"safe-test-provider")
    core = AuthorityServiceCore(
        tmp_path / "service", observer=_Observer(executable)
    )
    client = AuthorityServiceClient(
        test_transport=lambda request: core.dispatch(request, "S-1-5-21-1000")
    )
    return core, client


def test_service_constructs_qualification_and_completion_records(
    tmp_path: Path,
) -> None:
    core, client = _service(tmp_path)
    executable = tmp_path / "controlled-provider.exe"
    registered = client.register_provider("codex", executable)
    registration_id = str(registered["registration_id"])

    qualified = client.qualify_provider(registration_id)
    registration = qualified["registration"]
    qualification = qualified["qualification"]
    assert registration["registration_lifecycle"] == "QUALIFIED"
    assert core.keys.verify("provider-qualification", qualification)

    reserved = client.reserve_attempt(
        registration_id=registration_id,
        keeper_run_id="keeper-run-1",
        task_id="task-1",
        stage_id="author_execution",
        role="builder",
        attempt_number=1,
        provider_run_id="provider-run-1",
        provider_instance_id="instance-1",
        evidence_path=str((tmp_path / "evidence" / "run.json").resolve()),
    )
    attempt_id = str(reserved["attempt_id"])
    assert core.keys.verify(
        "provider-launch-authorization", reserved["attempt"]
    )
    started = client.record_provider_start(attempt_id, 4411)
    assert started["attempt"]["restricted_token"] is True
    finalized = client.finalize_completion(attempt_id)
    assert finalized["completion"]["terminal_disposition"] == "COMPLETED"
    assert core.keys.verify("provider-completion", finalized["completion"])


def test_service_rejects_arbitrary_signing_and_duplicate_launch(
    tmp_path: Path,
) -> None:
    core, client = _service(tmp_path)
    executable = tmp_path / "controlled-provider.exe"
    registered = client.register_provider("codex", executable)
    registration_id = str(registered["registration_id"])
    client.qualify_provider(registration_id)
    reserved = client.reserve_attempt(
        registration_id=registration_id,
        keeper_run_id="keeper-run-2",
        task_id="task-2",
        stage_id="author_execution",
        role="builder",
        attempt_number=1,
        provider_run_id="provider-run-2",
        provider_instance_id="instance-2",
        evidence_path=str((tmp_path / "evidence" / "run.json").resolve()),
    )
    attempt_id = str(reserved["attempt_id"])
    client.record_provider_start(attempt_id, 5511)
    with pytest.raises(PermissionError, match="not reserved"):
        client.record_provider_start(attempt_id, 5512)
    with pytest.raises(PermissionError, match="service-internal"):
        core.dispatch(
            Request.create(
                Operation.FINALIZE_QUALIFICATION,
                {"record": {"fabricated": True}},
            ),
            "S-1-5-21-1000",
        )


def test_request_replay_and_stale_timestamp_fail_closed(tmp_path: Path) -> None:
    core, _client = _service(tmp_path)
    request = Request.create(Operation.DIAGNOSTICS, {})
    core.dispatch(request, "S-1-5-21-1000")
    with pytest.raises(PermissionError, match="replay"):
        core.dispatch(request, "S-1-5-21-1000")

    value = request.to_dict()
    value["request_id"] = "1" * 32
    value["operation_id"] = "2" * 32
    value["nonce"] = "3" * 64
    value["issued_at"] = "2020-01-01T00:00:00+00:00"
    with pytest.raises(ValueError, match="stale"):
        parse_request(value)


def test_protocol_rejects_unknown_oversized_and_malformed_messages() -> None:
    request = Request.create(Operation.DIAGNOSTICS, {}).to_dict()
    request["unexpected"] = True
    with pytest.raises(ValueError, match="fields"):
        parse_request(request)

    with pytest.raises(ValueError, match="size"):
        encode_frame({"value": "x" * MAX_MESSAGE_BYTES})

    raw = b"\x05\x00\x00\x00nope!"
    offset = 0

    def read(length: int) -> bytes:
        nonlocal offset
        value = raw[offset : offset + length]
        offset += len(value)
        return value

    with pytest.raises(ValueError, match="encoding"):
        decode_frame(read)


def test_key_rotation_keeps_historical_verification(tmp_path: Path) -> None:
    core, client = _service(tmp_path)
    before = core.keys.sign("provider-start", {"id": "old"})
    rotated = client.rotate_key("ROTATE_KEEPER_AUTHORITY_KEY")
    after = core.keys.sign("provider-start", {"id": "new"})

    assert rotated["key_version"] == 2
    assert core.keys.verify("provider-start", before)
    assert core.keys.verify("provider-start", after)
    assert json.dumps(before) != json.dumps(after)
