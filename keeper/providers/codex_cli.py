from __future__ import annotations

import ctypes
import hashlib
import os
import re
import signal
import shutil
import subprocess
import threading
import uuid
from pathlib import Path
from typing import Any, TextIO

from keeper.policies import filtered_environment
from keeper.providers.base import AgentProvider, AgentRequest, ProcessResult
from keeper.recovery import process_identity


class CliProvider(AgentProvider):
    """Runs a configurable local development-agent command."""

    def __init__(
        self,
        command_template: tuple[str, ...],
        provider_name: str = "primary",
        *,
        expected_executable_sha256: str | None = None,
    ) -> None:
        self.command_template = command_template
        self.provider_name = provider_name
        self.expected_executable_sha256 = expected_executable_sha256
        self.instance_id = uuid.uuid4().hex
        self._active_process: subprocess.Popen[str] | None = None
        self._active_job: int | None = None

    def build_command(self, request: AgentRequest) -> list[str]:
        substitutions = {
            "{prompt}": str(request.prompt_path),
            "{workspace}": str(request.workspace),
            "{role}": request.role,
            "{reasoning}": request.reasoning_level,
        }
        return [substitutions.get(part, part) for part in self.command_template]

    def validate(self) -> None:
        if not self.command_template:
            raise RuntimeError(
                "agent provider command is not configured; set provider_command "
                "in .ai-workflow/config.json"
            )
        executable = self.command_template[0]
        if not Path(executable).exists() and shutil.which(executable) is None:
            raise RuntimeError(f"configured agent provider executable was not found: {executable}")
        if self.expected_executable_sha256 is not None:
            resolved = Path(executable).resolve(strict=True)
            actual = hashlib.sha256(resolved.read_bytes()).hexdigest()
            if actual != self.expected_executable_sha256:
                raise PermissionError(
                    "provider executable content changed after registration"
                )
        if "{prompt}" not in self.command_template:
            raise RuntimeError("provider_command must include the {prompt} argument placeholder")

    def run(self, request: AgentRequest) -> ProcessResult:
        self.validate()
        request.stdout_path.parent.mkdir(parents=True, exist_ok=True)
        environment = filtered_environment(dict(os.environ))
        environment["KEEPER_PROVIDER_ROLE"] = request.role
        with (
            request.stdout_path.open("w", encoding="utf-8") as stdout,
            request.stderr_path.open("w", encoding="utf-8") as stderr,
        ):
            process = subprocess.Popen(
                self.build_command(request),
                cwd=request.workspace,
                env=environment,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                shell=False,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0,
                start_new_session=os.name != "nt",
            )
            if process.stdout is None or process.stderr is None:
                process.kill()
                process.wait()
                raise RuntimeError("provider output streams were not created")
            pumps = [
                threading.Thread(
                    target=self._pump_stream,
                    args=(process.stdout, stdout),
                    daemon=True,
                ),
                threading.Thread(
                    target=self._pump_stream,
                    args=(process.stderr, stderr),
                    daemon=True,
                ),
            ]
            for pump in pumps:
                pump.start()
            job: int | None = None
            if os.name == "nt":
                kernel32: Any = ctypes.windll.kernel32
                job = int(kernel32.CreateJobObjectW(None, None))
                if not job or not kernel32.AssignProcessToJobObject(
                    job, int(process._handle)  # type: ignore[attr-defined]
                ):
                    if job:
                        kernel32.CloseHandle(job)
                    process.kill()
                    process.wait()
                    raise RuntimeError("unable to place provider in an isolated Windows Job Object")
                self._active_job = job
            self._active_process = process
            try:
                if request.on_process_started is not None:
                    request.on_process_started(process.pid)
                if request.on_process_owned is not None:
                    identity = process_identity(process.pid)
                    if identity is None:
                        raise RuntimeError("provider process ownership could not be established")
                    request.on_process_owned(
                        {
                            **identity,
                            "launch_nonce": uuid.uuid4().hex,
                            "ownership_token": uuid.uuid4().hex,
                            "job_or_group_identity": (
                                f"windows-job:{job}"
                                if os.name == "nt"
                                else f"process-group:{process.pid}"
                            ),
                            "started_at": identity.get("creation_time"),
                        }
                    )
                exit_code = process.wait(timeout=request.timeout_seconds)
                self._terminate_remaining_group(process, job)
                return ProcessResult(exit_code, request.stdout_path, request.stderr_path, process.pid)
            except subprocess.TimeoutExpired:
                self._terminate_tree(process, job)
                return ProcessResult(124, request.stdout_path, request.stderr_path, process.pid, True)
            except BaseException:
                self._terminate_tree(process, job)
                raise
            finally:
                for pump in pumps:
                    pump.join(timeout=5)
                self._active_process = None
                if job and self._active_job == job:
                    ctypes.windll.kernel32.CloseHandle(job)
                    self._active_job = None

    def cancel(self) -> None:
        if self._active_process and self._active_process.poll() is None:
            self._terminate_tree(self._active_process, self._active_job)

    @staticmethod
    def _pump_stream(source: TextIO, destination: TextIO) -> None:
        for line in source:
            destination.write(
                re.sub(
                    r"(?i)(token|secret|password|passwd|api[_-]?key|credential)"
                    r"(\s*[:=]\s*)\S+",
                    r"\1\2[REDACTED]",
                    line,
                )
            )
            destination.flush()

    @staticmethod
    def _terminate_remaining_group(
        process: subprocess.Popen[str], job: int | None = None
    ) -> None:
        if os.name == "nt":
            if not job or not ctypes.windll.kernel32.TerminateJobObject(job, 0):
                raise RuntimeError("unable to confirm provider descendant termination")
            return
        killpg = getattr(os, "killpg")
        try:
            killpg(process.pid, signal.SIGTERM)
            killpg(process.pid, getattr(signal, "SIGKILL"))
        except ProcessLookupError:
            return

    @staticmethod
    def _terminate_tree(process: subprocess.Popen[str], job: int | None = None) -> None:
        if process.poll() is not None:
            return
        if os.name == "nt":
            if not job or not ctypes.windll.kernel32.TerminateJobObject(job, 124):
                raise RuntimeError("unable to terminate provider Windows Job Object")
        else:
            killpg = getattr(os, "killpg")
            killpg(process.pid, signal.SIGTERM)
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            if os.name != "nt":
                killpg = getattr(os, "killpg")
                killpg(process.pid, getattr(signal, "SIGKILL"))
            else:
                process.kill()
            process.wait(timeout=10)
