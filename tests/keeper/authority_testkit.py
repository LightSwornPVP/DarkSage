from __future__ import annotations

import hashlib
import json
import os
import subprocess
import threading
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable

from keeper.authority_service.client import AuthorityServiceClient
from keeper.authority_service.core import (
    AuthorityServiceCore,
    CompletionObservation,
    ExecutionObservation,
    ProcessObservation,
    QualificationObservation,
)
from keeper.authority_service.protocol import Request
from keeper.providers.adapters import _domain_schema
from keeper.providers.adapters import create_provider_registration


class _TestObserver:
    """Explicit non-production observer used by the repository test suite."""

    def __init__(self, exchange_root: Path) -> None:
        self.exchange_root = exchange_root.resolve()
        self.allowed_evidence_root = self.exchange_root / "evidence"
        for directory in (
            self.allowed_evidence_root,
            self.exchange_root / "worktrees",
            self.exchange_root / "provider-work",
        ):
            directory.mkdir(parents=True, exist_ok=True)
        self._active_lock = threading.Lock()
        self._active_processes: dict[str, subprocess.Popen[str]] = {}
        self._cancelled_attempts: set[str] = set()

    def qualify(
        self, registration: dict[str, Any], challenge: str
    ) -> QualificationObservation:
        started = _now()
        command, executable = _qualification_command(registration)
        result = subprocess.run(
            command,
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=False,
            timeout=15,
        )
        return QualificationObservation(
            f"test-qualification:{uuid.uuid4().hex}",
            {
                "pid": 1,
                "launch_nonce": challenge,
                "restricted": True,
                "integrity_level": "low",
                "job_confined": True,
                "executable": str(executable),
                "executable_sha256": hashlib.sha256(
                    executable.read_bytes()
                ).hexdigest(),
            },
            started,
            _now(),
            result.returncode,
            result.stdout.strip(),
            result.stderr.strip() or None,
        )

    def register_provider(
        self, provider_id: str, executable: Path, client_sid: str
    ) -> dict[str, Any]:
        return create_provider_registration(
            provider_id, executable, authorized_by=client_sid
        )

    def execute_provider(
        self,
        registration: dict[str, Any],
        attempt: dict[str, Any],
        on_started: Callable[[ProcessObservation], None],
    ) -> ExecutionObservation:
        attempt_id = str(attempt["id"])
        executable = Path(str(registration["launcher_path"])).resolve(strict=True)
        prompt = Path(str(attempt["prompt_path"])).read_text(encoding="utf-8")
        stdout_path = Path(str(attempt["stdout_path"]))
        stderr_path = Path(str(attempt["stderr_path"]))
        stdout_path.parent.mkdir(parents=True, exist_ok=True)
        base = _provider_base(registration)
        provider_id = str(registration["logical_provider_id"])
        if provider_id == "codex":
            schema = stdout_path.parent / "provider-output-schema.json"
            schema.write_text(
                json.dumps(_domain_schema(str(attempt["role"]))),
                encoding="utf-8",
            )
            command = [
                *base,
                "exec",
                "--ephemeral",
                "--sandbox",
                "workspace-write",
                "--output-schema",
                str(schema),
                prompt,
            ]
        else:
            command = [
                *base,
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
        process_stdout_path = (
            stdout_path.with_suffix(".envelope.json")
            if provider_id == "claude"
            else stdout_path
        )
        with (
            process_stdout_path.open("w", encoding="utf-8") as stdout,
            stderr_path.open("w", encoding="utf-8") as stderr,
        ):
            process = subprocess.Popen(
                command,
                cwd=str(attempt["workspace"]),
                env={str(k): str(v) for k, v in attempt["environment"].items()},
                stdin=subprocess.DEVNULL,
                stdout=stdout,
                stderr=stderr,
                text=True,
                shell=False,
            )
            with self._active_lock:
                if attempt_id in self._cancelled_attempts:
                    process.kill()
                self._active_processes[attempt_id] = process
            on_started(
                ProcessObservation(
                    process.pid,
                    _now(),
                    str(executable),
                    hashlib.sha256(executable.read_bytes()).hexdigest(),
                    True,
                    "low",
                    True,
                )
            )
            timed_out = False
            deadline = time.monotonic() + float(attempt["timeout_seconds"])
            try:
                while process.poll() is None:
                    if time.monotonic() >= deadline:
                        timed_out = True
                        process.kill()
                        break
                    time.sleep(0.02)
                exit_status = process.wait(timeout=10)
            finally:
                with self._active_lock:
                    self._active_processes.pop(attempt_id, None)
                    self._cancelled_attempts.discard(attempt_id)
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
            process.pid,
            exit_status,
            timed_out,
            str(stdout_path),
            str(stderr_path),
            hashlib.sha256(
                json.dumps(
                    {
                        "stdout_sha256": hashlib.sha256(
                            stdout_path.read_bytes()
                            if stdout_path.exists()
                            else b""
                        ).hexdigest(),
                        "stderr_sha256": hashlib.sha256(
                            stderr_path.read_bytes()
                            if stderr_path.exists()
                            else b""
                        ).hexdigest(),
                    },
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode("utf-8")
            ).hexdigest(),
            _now(),
        )

    def cancel_provider(self, attempt_id: str) -> None:
        with self._active_lock:
            self._cancelled_attempts.add(attempt_id)
            process = self._active_processes.get(attempt_id)
            if process is not None:
                process.kill()

    def observe_process(
        self, attempt: dict[str, Any], pid: int
    ) -> ProcessObservation:
        registration_path = Path(
            str(attempt.get("process_executable") or os.environ.get("COMSPEC"))
        ).resolve(strict=True)
        return ProcessObservation(
            pid,
            _now(),
            str(registration_path),
            hashlib.sha256(registration_path.read_bytes()).hexdigest(),
            True,
            "low",
            True,
        )

    def observe_completion(
        self, attempt: dict[str, Any]
    ) -> CompletionObservation:
        evidence = Path(str(attempt["evidence_path"])).resolve(strict=True)
        content = evidence.read_bytes()
        value = json.loads(content.decode("utf-8"))
        return CompletionObservation(
            hashlib.sha256(content).hexdigest(),
            int(value["process_exit_code"]),
            str(value["status"]),
            _now(),
        )


class TestAuthorityClient(AuthorityServiceClient):
    """Semantic in-process transport explicitly injected only by pytest."""

    __test__ = False

    def __init__(self, data_directory: Path) -> None:
        root = data_directory.resolve()
        observer = _TestObserver(root / "test-authority-exchange")
        self.core = AuthorityServiceCore(
            root / "test-authority-service", observer=observer
        )
        super().__init__(
            test_transport=lambda request: self.core.dispatch(
                request, "S-1-5-21-KEEPER-TEST"
            )
        )

    def sign(self, purpose: str, record: dict[str, Any]) -> dict[str, Any]:
        return self.core.keys.sign(purpose, record)

    def reserve_attempt(self, **identity: Any) -> dict[str, Any]:
        if "launch_authorization_id" not in identity:
            project_id = f"test-project:{identity['keeper_run_id']}"
            expires_at = "2099-01-01T00:00:00+00:00"
            authorized = self.authorize_project_launch(
                project_id=project_id,
                charter_id="test-charter",
                charter_revision=1,
                delegation_id="test-delegation",
                founder_approval_event_id=f"test-event:{project_id}",
                founder_approval_event_digest=hashlib.sha256(
                    f"test-event:{project_id}".encode()
                ).hexdigest(),
                founder_authenticated_session_id="test-session",
                founder_principal_sid="S-1-5-21-KEEPER-TEST",
                authorization_generation=1,
                expires_at=expires_at,
            )["authorization"]
            identity.update(
                {
                    "launch_authorization_id": authorized["id"],
                    "authorization_generation": 1,
                    "delegation_id": "test-delegation",
                    "founder_approval_event_id": authorized[
                        "founder_approval_event_id"
                    ],
                    "founder_approval_event_digest": authorized[
                        "founder_approval_event_digest"
                    ],
                    "founder_authenticated_session_id": authorized[
                        "founder_authenticated_session_id"
                    ],
                    "founder_principal_sid": authorized[
                        "founder_principal_sid"
                    ],
                    "authorization_expires_at": authorized["expires_at"],
                    "project_id": project_id,
                    "charter_id": "test-charter",
                    "charter_revision": 1,
                    "task_revision": 1,
                }
            )
        return super().reserve_attempt(**identity)


def _qualification_command(
    registration: dict[str, Any],
) -> tuple[list[str], Path]:
    executable = Path(str(registration["launcher_path"])).resolve(strict=True)
    return [*_provider_base(registration), "--version"], executable


def _provider_base(registration: dict[str, Any]) -> list[str]:
    executable = Path(str(registration["launcher_path"])).resolve(strict=True)
    script = registration.get("script_path")
    return (
        [str(executable), "/d", "/c", str(script)]
        if script is not None
        else [str(executable)]
    )


def _now() -> str:
    return datetime.now(UTC).isoformat()
