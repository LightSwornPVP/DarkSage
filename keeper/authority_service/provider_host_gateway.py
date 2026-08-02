from __future__ import annotations

import sqlite3
import hashlib
import os
import uuid
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Callable, Iterator, Mapping, cast

from keeper.provider_host.identity import (
    PipePeerIdentity,
    named_pipe_server_identity,
    require_peer_identity,
)
from keeper.provider_host.pipe import connected_client_pipe, read_frame, write_frame
from keeper.provider_host.protocol import (
    HOST_PROTOCOL,
    HELLO_PURPOSE,
    LAUNCH_PURPOSE,
    SETUP_PURPOSE,
    SETUP_RESULT_PURPOSE,
    EnvelopeSigner,
    EnvelopeVerifier,
    require_production_identity,
    structured_digest,
    validate_completion,
    validate_launch_envelope,
    validate_setup_envelope,
    validate_setup_result,
)
from keeper.provider_host.server import (
    REQUEST_PURPOSE,
    RESPONSE_PURPOSE,
    STARTED_ACK_PURPOSE,
    STARTED_PURPOSE,
)


class ProviderHostGateway:
    """Authority-side mutually authenticated client for the user Provider Host."""

    def __init__(
        self,
        *,
        pipe_name: str,
        authority_id: str,
        host_id: str,
        authority_signer: EnvelopeSigner,
        host_verifier: EnvelopeVerifier,
        expected_host_sid: str,
        expected_host_session_id: int,
        expected_host_executable: Path,
        expected_host_executable_sha256: str,
        expected_host_profile_path: Path,
        sequence_store: Path,
        timeout_seconds: float = 15.0,
        now: Callable[[], datetime] | None = None,
        production: bool = True,
    ) -> None:
        if production:
            require_production_identity(authority_signer)
            require_production_identity(host_verifier)
        self.pipe_name = pipe_name
        self.authority_id = authority_id
        self.host_id = host_id
        self.authority_signer = authority_signer
        self.host_verifier = host_verifier
        self.expected_host_sid = expected_host_sid
        self.expected_host_session_id = expected_host_session_id
        self.expected_host_executable = expected_host_executable.resolve(strict=True)
        self.expected_host_executable_sha256 = expected_host_executable_sha256
        if (
            self.expected_host_executable.name.casefold()
            != "keeperproviderhost.exe"
            or self.expected_host_executable.read_bytes()[:2] != b"MZ"
            or len(expected_host_executable_sha256) != 64
            or any(
                character not in "0123456789abcdefABCDEF"
                for character in expected_host_executable_sha256
            )
            or hashlib.sha256(
                self.expected_host_executable.read_bytes()
            ).hexdigest().casefold()
            != expected_host_executable_sha256.casefold()
        ):
            raise PermissionError(
                "Authority requires a dedicated measured Provider Host executable"
            )
        self.expected_host_profile_path = expected_host_profile_path.resolve(
            strict=True
        )
        self.timeout_seconds = timeout_seconds
        self.now = now or (lambda: datetime.now(UTC))
        self._sequences = _GatewaySequenceStore(sequence_store)

    def enrollment_record(self) -> dict[str, Any]:
        """Return the exact protected-config-backed host enrollment identity."""
        return {
            "authority_id": self.authority_id,
            "authority_key_id": self.authority_signer.key_id,
            "enrollment_id": self.host_id,
            "host_executable": str(self.expected_host_executable),
            "host_executable_sha256": self.expected_host_executable_sha256,
            "host_id": self.host_id,
            "host_key_id": self.host_verifier.key_id,
            "host_profile_path": str(self.expected_host_profile_path),
            "host_protocol": HOST_PROTOCOL,
            "host_session_id": self.expected_host_session_id,
            "host_user_sid": self.expected_host_sid,
            "state": "ACTIVE",
        }

    def prepare_environment(self, preparation_nonce: str) -> dict[str, Any]:
        result = self._rpc(
            "prepare_environment",
            {"preparation_nonce": preparation_nonce},
        )
        if not isinstance(result, dict):
            raise PermissionError("Provider Host environment response is invalid")
        record = cast(dict[str, Any], result)
        payload = self.host_verifier.verify(
            record, purpose="keeper-provider-host-environment"
        )
        if (
            payload.get("host_id") != self.host_id
            or payload.get("preparation_nonce") != preparation_nonce
        ):
            raise PermissionError("Provider Host environment response differs")
        return record

    def execute(
        self,
        envelope: Mapping[str, Any],
        *,
        on_started: Callable[[dict[str, object]], None],
    ) -> dict[str, Any]:
        validated = validate_launch_envelope(envelope)
        if (
            validated["authority_id"] != self.authority_id
            or validated["host_id"] != self.host_id
        ):
            raise PermissionError("Provider Host gateway launch identity differs")
        signed = self.authority_signer.sign(LAUNCH_PURPOSE, validated)
        result = self._rpc(
            "execute",
            {
                "authority_attempt_id": validated["authority_attempt_id"],
                "launch_id": validated["launch_id"],
                "signed_envelope": signed,
            },
            on_started=on_started,
        )
        if not isinstance(result, dict):
            raise PermissionError("Provider Host completion is unavailable")
        completion_record = cast(dict[str, Any], result)
        completion = validate_completion(
            self.host_verifier.verify(
                completion_record, purpose="keeper-provider-host-completion"
            )
        )
        if (
            completion["authority_attempt_id"]
            != validated["authority_attempt_id"]
            or completion["launch_id"] != validated["launch_id"]
            or completion["envelope_digest"] != structured_digest(validated)
            or completion["provider_input_digest"]
            != validated["provider_input_digest"]
        ):
            raise PermissionError("Provider Host completion binding differs")
        return {
            "completion": completion,
            "signed_completion": completion_record,
        }

    def execute_setup(
        self,
        envelope: Mapping[str, Any],
        *,
        on_started: Callable[[dict[str, object]], None],
    ) -> dict[str, Any]:
        validated = validate_setup_envelope(envelope)
        if (
            validated["authority_id"] != self.authority_id
            or validated["host_id"] != self.host_id
        ):
            raise PermissionError("Provider Host gateway setup identity differs")
        signed = self.authority_signer.sign(SETUP_PURPOSE, validated)
        result = self._rpc(
            "setup",
            {
                "authority_attempt_id": validated["setup_id"],
                "launch_id": validated["setup_id"],
                "signed_envelope": signed,
            },
            on_started=on_started,
        )
        if not isinstance(result, dict):
            raise PermissionError("Provider Host setup result is unavailable")
        signed_result = cast(dict[str, Any], result)
        setup_result = validate_setup_result(
            self.host_verifier.verify(
                signed_result, purpose=SETUP_RESULT_PURPOSE
            )
        )
        if (
            setup_result["authority_id"] != self.authority_id
            or setup_result["host_id"] != self.host_id
            or setup_result["setup_id"] != validated["setup_id"]
            or setup_result["challenge"] != validated["challenge"]
            or setup_result["operation"] != validated["operation"]
            or setup_result["provider_registration_id"]
            != validated["provider_registration_id"]
            or setup_result["setup_envelope_digest"]
            != structured_digest(validated)
            or setup_result["environment_digest"]
            != validated["environment"]["digest"]
        ):
            raise PermissionError("Provider Host setup result binding differs")
        return {
            "observation": setup_result["observation"],
            "signed_result": signed_result,
            "setup_envelope_digest": structured_digest(validated),
            "setup_result_digest": structured_digest(signed_result),
        }

    def build_setup_envelope(
        self,
        *,
        operation: str,
        registration: Mapping[str, Any],
        provider_registration_id: str,
        challenge: str,
        setup_id: str,
        workspace: Path,
        environment_attestation: Mapping[str, Any],
    ) -> dict[str, Any]:
        binding = registration.get("windows_authentication_binding")
        executable_identity = registration.get("executable_file_identity")
        authenticode = registration.get("authenticode_binding")
        account_binding = registration.get("subscription_account_binding")
        usage_policy = registration.get("usage_policy")
        if not all(
            isinstance(value, dict)
            for value in (
                binding,
                executable_identity,
                authenticode,
                account_binding,
                usage_policy,
            )
        ):
            raise PermissionError("Provider Host setup registration is incomplete")
        binding = cast(dict[str, Any], binding)
        executable_identity = cast(dict[str, Any], executable_identity)
        authenticode = cast(dict[str, Any], authenticode)
        account_binding = cast(dict[str, Any], account_binding)
        usage_policy = cast(dict[str, Any], usage_policy)
        profile = Path(str(binding["profile_identity"])).resolve(strict=True)
        if (
            str(binding["principal_sid"]).casefold()
            != self.expected_host_sid.casefold()
            or int(binding["windows_session_id"])
            != self.expected_host_session_id
            or profile != self.expected_host_profile_path
        ):
            raise PermissionError("Provider Host setup user binding differs")
        environment = self.host_verifier.verify(
            environment_attestation,
            purpose="keeper-provider-host-environment",
        )
        if (
            set(environment)
            != {
                "allowlist",
                "digest",
                "host_id",
                "preparation_nonce",
                "recorded_at",
                "scrubbed_names",
            }
            or environment.get("host_id") != self.host_id
        ):
            raise PermissionError(
                "Provider Host setup environment attestation is invalid"
            )
        canonical_workspace = workspace.resolve(strict=False)
        model_allowlist = registration.get("model_allowlist")
        if not isinstance(model_allowlist, list) or len(model_allowlist) != 1:
            raise PermissionError("Provider Host setup model binding is invalid")
        now = self.now().astimezone(UTC)
        return validate_setup_envelope(
            {
                "account_binding": {
                    "account_identity_digest": account_binding[
                        "account_identity_digest"
                    ],
                    "authentication_method": account_binding[
                        "authentication_method"
                    ],
                    "plan_type": account_binding["plan_type"],
                },
                "authority_id": self.authority_id,
                "challenge": challenge,
                "composition_identity": "PRODUCTION",
                "environment": {
                    name: environment[name]
                    for name in (
                        "allowlist",
                        "digest",
                        "preparation_nonce",
                        "scrubbed_names",
                    )
                },
                "executable": {
                    "authenticode_binding": dict(authenticode),
                    "file_identity": dict(executable_identity),
                    "path": str(registration["canonical_executable_path"]),
                    "publisher": str(authenticode["publisher_subject"]),
                    "sha256": str(registration["executable_sha256"]),
                    "size": int(registration["executable_size"]),
                    "version": str(registration["expected_version"]),
                },
                "expires_at": (now + timedelta(minutes=1)).isoformat(),
                "host_id": self.host_id,
                "issued_at": now.isoformat(),
                "model_id": str(model_allowlist[0]),
                "nonce": uuid.uuid4().hex,
                "operation": operation,
                "provider_id": "codex",
                "provider_registration_id": provider_registration_id,
                "resource_limits": {
                    "active_process_limit": 8,
                    "memory_bytes": 2 * 1024 * 1024 * 1024,
                    "stderr_bytes": 8 * 1024 * 1024,
                    "stdout_bytes": 16 * 1024 * 1024,
                    "timeout_seconds": 180,
                },
                "sequence": self._sequences.next(self.authority_id),
                "setup_id": setup_id,
                "usage_policy_digest": structured_digest(usage_policy),
                "user_binding": {
                    "profile_path": str(profile),
                    "session_id": int(binding["windows_session_id"]),
                    "user_sid": str(binding["principal_sid"]),
                },
                "workspace": {
                    "canonical_path": str(canonical_workspace),
                    "identity": hashlib.sha256(
                        str(canonical_workspace).casefold().encode("utf-8")
                    ).hexdigest(),
                    "reservation_id": setup_id,
                },
            }
        )

    def build_launch_envelope(
        self,
        *,
        registration: Mapping[str, Any],
        attempt: Mapping[str, Any],
        argv: list[str],
        environment_attestation: Mapping[str, Any],
    ) -> dict[str, Any]:
        binding = registration.get("windows_authentication_binding")
        executable_identity = registration.get("executable_file_identity")
        authenticode = registration.get("authenticode_binding")
        usage_policy = registration.get("usage_policy")
        account_binding = registration.get("subscription_account_binding")
        qualification_id = registration.get("qualification_evidence_id")
        if not all(
            isinstance(value, dict)
            for value in (
                binding,
                executable_identity,
                authenticode,
                usage_policy,
                account_binding,
            )
        ) or not isinstance(qualification_id, str):
            raise PermissionError("Provider Host registration binding is incomplete")
        binding = cast(dict[str, Any], binding)
        executable_identity = cast(dict[str, Any], executable_identity)
        authenticode = cast(dict[str, Any], authenticode)
        usage_policy = cast(dict[str, Any], usage_policy)
        account_binding = cast(dict[str, Any], account_binding)
        profile = Path(str(binding["profile_identity"])).resolve(strict=True)
        if (
            str(binding["principal_sid"]).casefold()
            != self.expected_host_sid.casefold()
            or int(binding["windows_session_id"])
            != self.expected_host_session_id
            or profile != self.expected_host_profile_path
        ):
            raise PermissionError("Provider Host registration user binding differs")
        environment = self.host_verifier.verify(
            environment_attestation,
            purpose="keeper-provider-host-environment",
        )
        required_environment = {
            "allowlist",
            "digest",
            "host_id",
            "preparation_nonce",
            "recorded_at",
            "scrubbed_names",
        }
        if set(environment) != required_environment or environment.get(
            "host_id"
        ) != self.host_id:
            raise PermissionError("Provider Host environment attestation is invalid")
        now = self.now().astimezone(UTC)
        provider_input_digest = attempt.get("provider_input_digest")
        if not isinstance(provider_input_digest, str):
            provider_input_digest = str(attempt.get("prompt_digest", ""))
        provider_input = attempt.get("provider_input")
        input_record = provider_input if isinstance(provider_input, dict) else {}
        for input_name, attempt_name in (
            ("reviewer_assignment_id", "assignment_id"),
            ("work_item_id", "work_item_id"),
            ("workflow_id", "workflow_id"),
            ("project_id", "project_id"),
            ("charter_id", "charter_id"),
            ("charter_revision", "charter_revision"),
        ):
            if input_name in input_record and (
                input_record[input_name] != attempt.get(attempt_name)
            ):
                raise PermissionError(
                    "Provider Host typed-input lineage differs from launch"
                )
        usage_observation = attempt.get("usage_observation")
        usage = usage_observation if isinstance(usage_observation, dict) else {}
        account_digest = str(account_binding["account_identity_digest"])
        expected_account_id = "chatgpt-subscription:" + account_digest
        if attempt.get("provider_account_id") != expected_account_id:
            raise PermissionError("Provider Host provider-account binding differs")
        executable_path = str(registration["canonical_executable_path"])
        executable_size = int(registration["executable_size"])
        return validate_launch_envelope(
            {
                "account_id": expected_account_id,
                "argv": list(argv),
                "assignment_id": str(
                    input_record.get("reviewer_assignment_id")
                    or attempt.get("assignment_id")
                    or attempt["task_id"]
                ),
                "authority_attempt_id": str(attempt["id"]),
                "authority_id": self.authority_id,
                "cancellation": {
                    "on_lock": "CANCEL_EXISTING",
                    "on_logoff": "CANCEL_AND_EXIT",
                    "token_digest": hashlib.sha256(
                        str(attempt["launch_challenge"]).encode("utf-8")
                    ).hexdigest(),
                },
                "charter_id": str(attempt["charter_id"]),
                "charter_revision_id": (
                    f"{attempt['charter_id']}:r{attempt['charter_revision']}"
                ),
                "composition_identity": "PRODUCTION",
                "effort": str(attempt["reasoning_level"]),
                "environment": {
                    name: environment[name]
                    for name in (
                        "allowlist",
                        "digest",
                        "preparation_nonce",
                        "scrubbed_names",
                    )
                },
                "executable": {
                    "authenticode_binding": dict(authenticode),
                    "file_identity": dict(executable_identity),
                    "path": executable_path,
                    "publisher": str(authenticode["publisher_subject"]),
                    "sha256": str(registration["executable_sha256"]),
                    "size": executable_size,
                    "version": str(registration["expected_version"]),
                },
                "expires_at": (now + timedelta(minutes=1)).isoformat(),
                "host_id": self.host_id,
                "issued_at": now.isoformat(),
                "launch_claim_digest": structured_digest(attempt),
                "launch_id": str(attempt["claim_transaction_id"]),
                "model_id": str(attempt["model_id"]),
                "network_policy": {
                    "allow_external": True,
                    "policy_id": "codex-chatgpt-subscription-only",
                },
                "nonce": uuid.uuid4().hex,
                "project_id": str(attempt["project_id"]),
                "provider_id": "codex",
                "provider_input_digest": provider_input_digest,
                "provider_qualification_id": qualification_id,
                "provider_registration_id": str(attempt["registration_id"]),
                "provider_session_id": str(attempt["provider_instance_id"]),
                "resource_limits": {
                    "active_process_limit": 8,
                    "memory_bytes": 2 * 1024 * 1024 * 1024,
                    "stderr_bytes": 8 * 1024 * 1024,
                    "stdout_bytes": 16 * 1024 * 1024,
                    "timeout_seconds": int(attempt["timeout_seconds"]),
                },
                "sequence": self._sequences.next(self.authority_id),
                "usage": {
                    "generation": int(usage.get("generation", 1)),
                    "max_units": int(usage_policy["keeper_launch_budget"]),
                    "pool_id": "codex:" + account_digest,
                    "reservation_id": str(attempt["claim_transaction_id"]),
                },
                "user_binding": {
                    "profile_path": str(profile),
                    "session_id": int(binding["windows_session_id"]),
                    "user_sid": str(binding["principal_sid"]),
                },
                "work_item_id": str(
                    input_record.get("work_item_id")
                    or attempt.get("work_item_id")
                    or attempt["task_id"]
                ),
                "workflow_id": str(
                    input_record.get("workflow_id")
                    or attempt.get("workflow_id")
                    or attempt["keeper_run_id"]
                ),
                "workspace": {
                    "canonical_path": str(Path(str(attempt["workspace"])).resolve(strict=True)),
                    "identity": str(attempt["workspace_identity"]),
                    "reservation_id": str(attempt["workspace_reservation_id"]),
                },
            }
        )

    def cancel(self, authority_attempt_id: str, launch_id: str) -> bool:
        result = self._rpc(
            "cancel",
            {
                "authority_attempt_id": authority_attempt_id,
                "launch_id": launch_id,
            },
        )
        return isinstance(result, dict) and result.get("cancel_requested") is True

    def status(self) -> dict[str, Any]:
        result = self._rpc("status", {})
        if not isinstance(result, dict):
            raise PermissionError("Provider Host status is invalid")
        return dict(result)

    def _rpc(
        self,
        operation: str,
        body: Mapping[str, Any],
        *,
        on_started: Callable[[dict[str, object]], None] | None = None,
    ) -> object:
        with connected_client_pipe(
            self.pipe_name, timeout_seconds=self.timeout_seconds
        ) as pipe:
            observed = named_pipe_server_identity(pipe)
            require_peer_identity(
                observed,
                session_id=self.expected_host_session_id,
                user_sid=self.expected_host_sid,
                executable_path=self.expected_host_executable,
                executable_sha256=self.expected_host_executable_sha256,
            )
            hello = self._message(
                {
                    "authority_id": self.authority_id,
                    "authority_process_id": os.getpid(),
                    "host_id": self.host_id,
                }
            )
            write_frame(
                pipe, self.authority_signer.sign(HELLO_PURPOSE, hello)
            )
            hello_record = read_frame(pipe)
            host_hello = self.host_verifier.verify(
                hello_record, purpose=HELLO_PURPOSE
            )
            if (
                set(host_hello)
                != {
                    "authority_nonce",
                    "host_id",
                    "host_nonce",
                    "host_process_id",
                    "state",
                    "user_binding",
                }
                or host_hello.get("authority_nonce") != hello["nonce"]
                or host_hello.get("host_id") != self.host_id
                or host_hello.get("host_process_id") != observed.process_id
            ):
                raise PermissionError("Provider Host hello response differs")
            request = self._message(
                {
                    "authority_id": self.authority_id,
                    "authority_nonce": hello["nonce"],
                    "body": dict(body),
                    "body_digest": structured_digest(body),
                    "host_nonce": host_hello["host_nonce"],
                    "operation": operation,
                }
            )
            request_record = self.authority_signer.sign(
                REQUEST_PURPOSE, request
            )
            write_frame(pipe, request_record)
            while True:
                frame = read_frame(pipe)
                if frame.get("event") == "STARTED":
                    record = frame.get("record")
                    if not isinstance(record, dict) or on_started is None:
                        raise PermissionError("Provider Host STARTED event is unexpected")
                    event = self.host_verifier.verify(
                        record, purpose=STARTED_PURPOSE
                    )
                    if (
                        event.get("authority_attempt_id")
                        != body.get("authority_attempt_id")
                        or event.get("launch_id") != body.get("launch_id")
                        or not isinstance(event.get("observation"), dict)
                    ):
                        raise PermissionError("Provider Host STARTED event differs")
                    on_started(dict(event["observation"]))
                    ack = self._message(
                        {
                            "authority_attempt_id": event["authority_attempt_id"],
                            "event_digest": structured_digest(record),
                            "launch_id": event["launch_id"],
                        }
                    )
                    write_frame(
                        pipe,
                        self.authority_signer.sign(STARTED_ACK_PURPOSE, ack),
                    )
                    continue
                response = self.host_verifier.verify(
                    frame, purpose=RESPONSE_PURPOSE
                )
                if (
                    set(response)
                    != {
                        "authority_nonce",
                        "host_nonce",
                        "operation",
                        "request_digest",
                        "result",
                    }
                    or response.get("authority_nonce") != hello["nonce"]
                    or response.get("host_nonce") != host_hello["host_nonce"]
                    or response.get("operation") != operation
                    or response.get("request_digest")
                    != structured_digest(request_record)
                ):
                    raise PermissionError("Provider Host response binding differs")
                return response["result"]

    def _message(self, value: Mapping[str, Any]) -> dict[str, Any]:
        now = self.now().astimezone(UTC)
        return {
            **dict(value),
            "expires_at": (now + timedelta(minutes=1)).isoformat(),
            "issued_at": now.isoformat(),
            "nonce": uuid.uuid4().hex,
            "sequence": self._sequences.next(self.authority_id),
        }


class _GatewaySequenceStore:
    def __init__(self, path: Path) -> None:
        self.path = path.resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as connection:
            connection.execute(
                "CREATE TABLE IF NOT EXISTS sequences("
                "authority_id TEXT PRIMARY KEY,value INTEGER NOT NULL)"
            )
            connection.commit()

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path, timeout=5)
        try:
            connection.execute("PRAGMA journal_mode=WAL")
            yield connection
        finally:
            connection.close()

    def next(self, authority_id: str) -> int:
        with self.connect() as connection:
            try:
                connection.execute("BEGIN IMMEDIATE")
                row = connection.execute(
                    "SELECT value FROM sequences WHERE authority_id=?",
                    (authority_id,),
                ).fetchone()
                value = 1 if row is None else int(row[0]) + 1
                connection.execute(
                    "INSERT INTO sequences(authority_id,value) VALUES(?,?) "
                    "ON CONFLICT(authority_id) DO UPDATE SET value=excluded.value",
                    (authority_id, value),
                )
                connection.commit()
                return value
            except BaseException:
                connection.rollback()
                raise
