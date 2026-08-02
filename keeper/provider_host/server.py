from __future__ import annotations

import hashlib
import os
import threading
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Callable, Mapping, cast

from keeper.provider_host.identity import (
    PipePeerIdentity,
    named_pipe_client_identity,
    require_peer_identity,
)
from keeper.provider_host.pipe import (
    connected_client_pipe,
    connected_server_pipe,
    read_frame,
    write_frame,
)
from keeper.provider_host.protocol import (
    HELLO_PURPOSE,
    EnvelopeSigner,
    EnvelopeVerifier,
    canonical_json,
    parse_utc,
    structured_digest,
)
from keeper.provider_host.replay_store import ProviderHostStore
from keeper.provider_host.runtime import KeeperProviderHost, Launcher, SetupRunner


REQUEST_PURPOSE = "keeper-provider-host-request"
RESPONSE_PURPOSE = "keeper-provider-host-response"
STARTED_PURPOSE = "keeper-provider-host-started"
STARTED_ACK_PURPOSE = "keeper-provider-host-started-ack"


class ProviderHostServer:
    """Local-only authenticated Provider Host named-pipe server."""

    def __init__(
        self,
        *,
        pipe_name: str,
        runtime: KeeperProviderHost,
        launcher: Launcher,
        setup_runner: SetupRunner,
        authority_verifier: EnvelopeVerifier,
        host_signer: EnvelopeSigner,
        store: ProviderHostStore,
        authority_peer: PipePeerIdentity,
        authority_executable: Path,
        authority_executable_sha256: str,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self.pipe_name = pipe_name
        self.runtime = runtime
        self.launcher = launcher
        self.setup_runner = setup_runner
        self.authority_verifier = authority_verifier
        self.host_signer = host_signer
        self.store = store
        self.authority_peer = authority_peer
        self.authority_executable = authority_executable.resolve(strict=True)
        self.authority_executable_sha256 = authority_executable_sha256
        self.now = now or (lambda: datetime.now(UTC))
        self._stop = threading.Event()
        self._first = True
        self._workers: list[threading.Thread] = []

    def serve_forever(self) -> None:
        first = threading.Thread(
            target=self._accept_once,
            args=(True,),
            name="KeeperProviderHostAccept",
            daemon=True,
        )
        self._workers.append(first)
        first.start()
        while not self._stop.wait(0.25):
            self._workers = [worker for worker in self._workers if worker.is_alive()]

    def stop(self) -> None:
        self._stop.set()
        self.runtime.drain()
        try:
            with connected_client_pipe(self.pipe_name, timeout_seconds=0.25):
                pass
        except (OSError, TimeoutError):
            pass

    def _accept_once(self, first_instance: bool) -> None:
        with connected_server_pipe(
            self.pipe_name,
            user_sid=self.runtime.identity.binding.user_sid,
            first_instance=first_instance,
        ) as pipe:
            if self._stop.is_set():
                return
            successor = threading.Thread(
                target=self._accept_once,
                args=(False,),
                name="KeeperProviderHostAccept",
                daemon=True,
            )
            self._workers.append(successor)
            successor.start()
            self._serve_connection(pipe)

    def _serve_connection(self, pipe: int) -> None:
        observed = named_pipe_client_identity(pipe)
        require_peer_identity(
            observed,
            session_id=self.authority_peer.session_id,
            user_sid=self.authority_peer.user_sid,
            executable_path=self.authority_executable,
            executable_sha256=self.authority_executable_sha256,
        )
        hello_record = read_frame(pipe)
        hello = self.authority_verifier.verify(
            hello_record, purpose=HELLO_PURPOSE
        )
        self._claim_message("hello", hello)
        if (
            set(hello)
            != {
                "authority_id",
                "authority_process_id",
                "expires_at",
                "host_id",
                "issued_at",
                "nonce",
                "sequence",
            }
            or hello.get("authority_id") != self.runtime.identity.authority_id
            or hello.get("host_id") != self.runtime.identity.host_id
            or hello.get("authority_process_id") != observed.process_id
        ):
            raise PermissionError("Provider Host hello binding is invalid")
        host_nonce = uuid.uuid4().hex
        write_frame(
            pipe,
            self.host_signer.sign(
                HELLO_PURPOSE,
                {
                    "authority_nonce": hello["nonce"],
                    "host_id": self.runtime.identity.host_id,
                    "host_nonce": host_nonce,
                    "host_process_id": os.getpid(),
                    "state": self.runtime.state.value,
                    "user_binding": self.runtime.identity.binding.as_dict(),
                },
            ),
        )
        request_record = read_frame(pipe)
        request = self.authority_verifier.verify(
            request_record, purpose=REQUEST_PURPOSE
        )
        self._claim_message("request", request)
        operation, body = _validated_request(request, hello, host_nonce)
        if operation == "prepare_environment":
            result = self.runtime.prepare_environment(
                preparation_nonce=str(body["preparation_nonce"]),
                provider_bin=self.runtime.provider_bin,
            )
        elif operation in {"execute", "setup"}:
            signed_envelope = body.get("signed_envelope")
            if not isinstance(signed_envelope, dict):
                raise PermissionError("Provider Host signed envelope is absent")

            def started(observation: dict[str, object]) -> None:
                event = self.host_signer.sign(
                    STARTED_PURPOSE,
                    {
                        "authority_attempt_id": body["authority_attempt_id"],
                        "launch_id": body["launch_id"],
                        "observation": observation,
                    },
                )
                write_frame(pipe, {"event": "STARTED", "record": event})
                ack_record = read_frame(pipe)
                ack = self.authority_verifier.verify(
                    ack_record, purpose=STARTED_ACK_PURPOSE
                )
                if (
                    set(ack)
                    != {
                        "authority_attempt_id",
                        "event_digest",
                        "expires_at",
                        "issued_at",
                        "launch_id",
                        "nonce",
                        "sequence",
                    }
                    or ack.get("authority_attempt_id")
                    != body["authority_attempt_id"]
                    or ack.get("launch_id") != body["launch_id"]
                    or ack.get("event_digest") != structured_digest(event)
                ):
                    raise PermissionError("Provider Host STARTED acknowledgement differs")
                self._claim_message("started-ack", ack)

            if operation == "execute":
                result = self.runtime.execute(
                    signed_envelope,
                    self.launcher,
                    started_observer=started,
                )
            else:
                result = self.runtime.execute_setup(
                    signed_envelope,
                    self.setup_runner,
                    started_observer=started,
                )
        elif operation == "cancel":
            result = {
                "cancel_requested": self.runtime.cancel_active(
                    str(body.get("authority_attempt_id", "")),
                    str(body.get("launch_id", "")),
                )
            }
        elif operation == "status":
            result = self.runtime.status()
        elif operation == "lock":
            self.runtime.lock_workstation()
            result = self.runtime.status()
        elif operation == "drain":
            self.runtime.drain()
            result = self.runtime.status()
        else:
            raise PermissionError("Provider Host operation is unsupported")
        write_frame(
            pipe,
            self.host_signer.sign(
                RESPONSE_PURPOSE,
                {
                    "authority_nonce": hello["nonce"],
                    "host_nonce": host_nonce,
                    "operation": operation,
                    "request_digest": structured_digest(request_record),
                    "result": result,
                },
            ),
        )

    def _claim_message(self, channel: str, value: Mapping[str, Any]) -> None:
        required = {"authority_id", "expires_at", "issued_at", "nonce", "sequence"}
        if not required.issubset(value):
            raise PermissionError("Provider Host peer message lifetime is absent")
        self.store.claim_peer_message(
            channel=channel,
            authority_id=str(value["authority_id"]),
            nonce=str(value["nonce"]),
            sequence=int(value["sequence"]),
            issued_at=str(value["issued_at"]),
            expires_at=str(value["expires_at"]),
            now=self.now(),
            maximum_ttl=timedelta(minutes=2),
            maximum_future_skew=timedelta(seconds=5),
        )


def _validated_request(
    value: Mapping[str, Any], hello: Mapping[str, Any], host_nonce: str
) -> tuple[str, dict[str, Any]]:
    expected = {
        "authority_id",
        "authority_nonce",
        "body",
        "body_digest",
        "expires_at",
        "host_nonce",
        "issued_at",
        "nonce",
        "operation",
        "sequence",
    }
    if set(value) != expected or not isinstance(value.get("body"), dict):
        raise PermissionError("Provider Host request fields are invalid")
    if (
        value.get("authority_id") != hello.get("authority_id")
        or value.get("authority_nonce") != hello.get("nonce")
        or value.get("host_nonce") != host_nonce
        or value.get("body_digest") != structured_digest(value["body"])
        or value.get("operation")
        not in {
            "prepare_environment",
            "execute",
            "setup",
            "cancel",
            "status",
            "lock",
            "drain",
        }
    ):
        raise PermissionError("Provider Host request binding is invalid")
    return str(value["operation"]), dict(cast(dict[str, Any], value["body"]))
