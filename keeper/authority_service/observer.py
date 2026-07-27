from __future__ import annotations

import hashlib
import json
import os
import threading
import uuid
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable, Iterator, cast

from keeper.authority_service.core import (
    CompletionObservation,
    ExecutionObservation,
    ProcessObservation,
    QualificationObservation,
)
from keeper.authority_service.provider_identity import (
    restricted_provider_identity_token,
)
from keeper.authority_service.restricted_process import (
    authenticated_named_pipe_client_token,
    impersonate_token,
    run_restricted_process,
)
from keeper.authority_service.windows_identity import process_image
from keeper.policies import filtered_environment
from keeper.providers.adapters import create_provider_registration


class ServiceProviderObserver:
    """OS-backed observations available only inside the Authority Service host."""

    def __init__(
        self,
        provider_root: Path,
        allowed_evidence_root: Path,
        provider_account_name: str,
        provider_credential_path: Path,
    ) -> None:
        self.provider_root = provider_root.resolve()
        self.allowed_evidence_root = allowed_evidence_root.resolve()
        self.provider_account_name = provider_account_name
        self.provider_credential_path = provider_credential_path.resolve(
            strict=True
        )
        self.provider_root.mkdir(parents=True, exist_ok=True)
        self._local = threading.local()
        self._active_lock = threading.Lock()
        self._active_cancellations: dict[str, threading.Event] = {}
        self._cancelled_attempts: set[str] = set()

    @contextmanager
    def bind_client(self, pipe: int) -> Iterator[None]:
        if getattr(self._local, "token", None) is not None:
            raise RuntimeError("authority observer token is already bound")
        with authenticated_named_pipe_client_token(pipe) as client_token:
            with restricted_provider_identity_token(
                self.provider_account_name,
                self.provider_credential_path,
            ) as restricted_token:
                self._local.client_token = client_token
                self._local.token = restricted_token
                try:
                    yield
                finally:
                    self._local.client_token = None
                    self._local.token = None

    def qualify(
        self, registration: dict[str, Any], challenge: str
    ) -> QualificationObservation:
        token = self._token()
        transaction = self.provider_root / f"qualification-{uuid.uuid4().hex}"
        transaction.mkdir(parents=True, exist_ok=False)
        executable = Path(str(registration["launcher_path"])).resolve(strict=True)
        configured = Path(
            str(registration["canonical_executable_path"])
        ).resolve(strict=True)
        if registration.get("script_path") is not None:
            command = [
                str(executable),
                "/d",
                "/c",
                str(configured),
                "--version",
            ]
        else:
            command = [str(executable), "--version"]
        environment = filtered_environment(dict(os.environ))
        environment["PATH"] = (
            str(executable.parent)
            + os.pathsep
            + environment.get("PATH", "")
        )
        started_at = _now()
        failure_reason: str | None = None
        try:
            result = run_restricted_process(
                token,
                command,
                executable,
                transaction,
                environment,
                transaction / "stdout.log",
                transaction / "stderr.log",
                15,
            )
            raw = result.stdout.strip()
            exit_status = result.exit_code
            ownership = {
                "pid": result.process_id,
                "launch_nonce": challenge,
                "restricted": result.restricted,
                "integrity_level": result.integrity_level,
                "job_confined": result.job_confined,
                "executable": result.executable,
                "executable_sha256": result.executable_sha256,
            }
            provider_instance_id = f"qualification:{result.process_id}:{challenge[:16]}"
        except (OSError, PermissionError, RuntimeError, ValueError) as error:
            raw = ""
            exit_status = 70
            failure_reason = f"{type(error).__name__}: {error}"
            ownership = {
                "launch_nonce": challenge,
                "restricted": False,
                "integrity_level": "unknown",
                "job_confined": False,
            }
            provider_instance_id = f"qualification-failed:{challenge[:16]}"
        return QualificationObservation(
            provider_instance_id,
            ownership,
            started_at,
            _now(),
            exit_status,
            raw,
            failure_reason,
        )

    def register_provider(
        self, provider_id: str, executable: Path, client_sid: str
    ) -> dict[str, Any]:
        with impersonate_token(self._client_token()):
            return create_provider_registration(
                provider_id, executable, authorized_by=client_sid
            )

    def execute_provider(
        self,
        registration: dict[str, Any],
        attempt: dict[str, Any],
        on_started: Callable[[ProcessObservation], None],
    ) -> ExecutionObservation:
        token = self._token()
        attempt_id = str(attempt["id"])
        cancellation = threading.Event()
        with self._active_lock:
            if attempt_id in self._active_cancellations:
                raise PermissionError("provider attempt is already executing")
            if attempt_id in self._cancelled_attempts:
                cancellation.set()
            self._active_cancellations[attempt_id] = cancellation
        prompt_path = self._exchange_path(attempt["prompt_path"], "prompt")
        stdout_path = self._exchange_path(attempt["stdout_path"], "stdout")
        stderr_path = self._exchange_path(attempt["stderr_path"], "stderr")
        workspace = self._exchange_path(attempt["workspace"], "workspace")
        executable = Path(str(registration["launcher_path"])).resolve(strict=True)
        launcher_content = executable.read_bytes()
        if (
            hashlib.sha256(launcher_content).hexdigest()
            != registration["launcher_sha256"]
            or len(launcher_content) != registration["launcher_size"]
        ):
            raise PermissionError("registered provider launcher identity changed")
        provider_id = str(registration["logical_provider_id"])
        prompt = prompt_path.read_text(encoding="utf-8")
        base_command = (
            [
                str(executable),
                "/d",
                "/c",
                str(registration["script_path"]),
            ]
            if registration.get("script_path") is not None
            else [str(executable)]
        )
        if provider_id == "codex":
            from keeper.providers.adapters import _domain_schema

            schema_path = stdout_path.parent / "provider-output-schema.json"
            schema_path.write_text(
                json.dumps(_domain_schema(str(attempt["role"]))),
                encoding="utf-8",
            )
            command = [
                *base_command,
                "exec",
                "--ephemeral",
                "--sandbox",
                "workspace-write",
                "--output-schema",
                str(schema_path),
                prompt,
            ]
        elif provider_id == "claude":
            from keeper.providers.adapters import _domain_schema

            command = [
                *base_command,
                "--output-format",
                "json",
                "--json-schema",
                json.dumps(
                    _domain_schema(str(attempt["role"])),
                    separators=(",", ":"),
                ),
                "-p",
                prompt,
            ]
        else:
            raise PermissionError("provider execution adapter is unsupported")
        process_stdout_path = (
            stdout_path.with_suffix(".envelope.json")
            if provider_id == "claude"
            else stdout_path
        )
        environment = attempt.get("environment")
        if not isinstance(environment, dict):
            raise PermissionError("provider environment is unavailable")
        safe_environment = {
            str(key): str(value) for key, value in environment.items()
        }

        def started(value: dict[str, object]) -> None:
            on_started(
                ProcessObservation(
                    cast(int, value["pid"]),
                    str(value["creation_time"]),
                    str(value["executable"]),
                    str(value["executable_sha256"]),
                    value["restricted"] is True,
                    str(value["integrity_level"]),
                    value["job_confined"] is True,
                )
            )

        try:
            result = run_restricted_process(
                token,
                command,
                executable,
                workspace,
                safe_environment,
                process_stdout_path,
                stderr_path,
                float(attempt["timeout_seconds"]),
                started,
                cancellation,
            )
        finally:
            with self._active_lock:
                self._active_cancellations.pop(attempt_id, None)
                self._cancelled_attempts.discard(attempt_id)
        exit_status = result.exit_code
        if provider_id == "claude" and exit_status == 0:
            try:
                envelope = json.loads(
                    process_stdout_path.read_text(encoding="utf-8")
                )
                domain = envelope.get(
                    "structured_output", envelope.get("result")
                )
                if isinstance(domain, str):
                    domain = json.loads(domain)
                if not isinstance(domain, dict):
                    raise ValueError(
                        "Claude envelope contains no domain result"
                    )
                stdout_path.write_text(
                    json.dumps(domain), encoding="utf-8"
                )
            except (json.JSONDecodeError, OSError, ValueError) as error:
                stdout_path.write_text("", encoding="utf-8")
                stderr_path.write_text(
                    f"invalid Claude result envelope: {error}",
                    encoding="utf-8",
                )
                exit_status = 65
        return ExecutionObservation(
            result.process_id,
            exit_status,
            result.timed_out,
            str(stdout_path),
            str(stderr_path),
            _execution_evidence_digest(stdout_path, stderr_path),
            _now(),
        )

    def cancel_provider(self, attempt_id: str) -> None:
        with self._active_lock:
            self._cancelled_attempts.add(attempt_id)
            cancellation = self._active_cancellations.get(attempt_id)
            if cancellation is not None:
                cancellation.set()

    def observe_process(
        self, attempt: dict[str, Any], pid: int
    ) -> ProcessObservation:
        image = process_image(pid)
        content = image.read_bytes()
        # Desktop-owned processes are deliberately not promoted to trusted
        # restricted execution. Production attempts must be broker-launched.
        raise PermissionError(
            "desktop-owned provider processes are not service-authoritative; "
            f"observed image {image} ({hashlib.sha256(content).hexdigest()[:16]})"
        )

    def observe_completion(
        self, attempt: dict[str, Any]
    ) -> CompletionObservation:
        path = Path(str(attempt["evidence_path"])).resolve(strict=True)
        if not path.is_relative_to(self.allowed_evidence_root):
            raise PermissionError("provider evidence path is outside the configured root")
        content = path.read_bytes()
        try:
            value = json.loads(content.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise PermissionError("provider evidence is malformed") from error
        if not isinstance(value, dict):
            raise PermissionError("provider evidence is malformed")
        exit_status = value.get("process_exit_code")
        result = value.get("status")
        if (
            isinstance(exit_status, bool)
            or not isinstance(exit_status, int)
            or result not in {"completed", "failed"}
        ):
            raise PermissionError("provider completion fields are malformed")
        return CompletionObservation(
            hashlib.sha256(content).hexdigest(),
            exit_status,
            str(result),
            _now(),
        )

    def _token(self) -> int:
        value = getattr(self._local, "token", None)
        if not isinstance(value, int) or value <= 0:
            raise PermissionError("authority client restricted token is unavailable")
        return value

    def _client_token(self) -> int:
        value = getattr(self._local, "client_token", None)
        if not isinstance(value, int) or value <= 0:
            raise PermissionError(
                "authority authenticated client token is unavailable"
            )
        return value

    def _exchange_path(self, value: object, label: str) -> Path:
        path = Path(str(value)).resolve()
        exchange_root = self.allowed_evidence_root.parent
        if not path.is_relative_to(exchange_root):
            raise PermissionError(
                f"provider {label} path is outside the client exchange"
            )
        return path


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _execution_evidence_digest(stdout_path: Path, stderr_path: Path) -> str:
    evidence = {
        "stdout_sha256": hashlib.sha256(
            stdout_path.read_bytes() if stdout_path.exists() else b""
        ).hexdigest(),
        "stderr_sha256": hashlib.sha256(
            stderr_path.read_bytes() if stderr_path.exists() else b""
        ).hexdigest(),
    }
    return hashlib.sha256(
        json.dumps(evidence, sort_keys=True, separators=(",", ":")).encode(
            "utf-8"
        )
    ).hexdigest()
