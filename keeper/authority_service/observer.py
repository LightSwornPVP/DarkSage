from __future__ import annotations

import hashlib
import json
import os
import threading
import uuid
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterator

from keeper.authority_service.core import (
    CompletionObservation,
    ProcessObservation,
    QualificationObservation,
)
from keeper.authority_service.restricted_process import (
    restricted_named_pipe_client_token,
    run_restricted_process,
)
from keeper.authority_service.windows_identity import process_image
from keeper.policies import filtered_environment


class ServiceProviderObserver:
    """OS-backed observations available only inside the Authority Service host."""

    def __init__(self, provider_root: Path, allowed_evidence_root: Path) -> None:
        self.provider_root = provider_root.resolve()
        self.allowed_evidence_root = allowed_evidence_root.resolve()
        self.provider_root.mkdir(parents=True, exist_ok=True)
        self._local = threading.local()

    @contextmanager
    def bind_client(self, pipe: int) -> Iterator[None]:
        if getattr(self._local, "token", None) is not None:
            raise RuntimeError("authority observer token is already bound")
        with restricted_named_pipe_client_token(pipe) as token:
            self._local.token = token
            try:
                yield
            finally:
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


def _now() -> str:
    return datetime.now(UTC).isoformat()
