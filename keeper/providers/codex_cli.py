from __future__ import annotations

import os
import shutil
import subprocess
import uuid
import signal
import ctypes
from typing import Any
from pathlib import Path

from keeper.policies import filtered_environment
from keeper.providers.base import AgentProvider, AgentRequest, ProcessResult


class CliProvider(AgentProvider):
    """Runs a configurable local development-agent command."""

    def __init__(self, command_template: tuple[str, ...], provider_name: str = "primary") -> None:
        self.command_template = command_template
        self.provider_name = provider_name
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
        if "{prompt}" not in self.command_template:
            raise RuntimeError("provider_command must include the {prompt} argument placeholder")

    def run(self, request: AgentRequest) -> ProcessResult:
        self.validate()
        request.stdout_path.parent.mkdir(parents=True, exist_ok=True)
        environment = filtered_environment(dict(os.environ))
        with (
            request.stdout_path.open("w", encoding="utf-8") as stdout,
            request.stderr_path.open("w", encoding="utf-8") as stderr,
        ):
            process = subprocess.Popen(
                self.build_command(request),
                cwd=request.workspace,
                env=environment,
                stdin=subprocess.DEVNULL,
                stdout=stdout,
                stderr=stderr,
                text=True,
                shell=False,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0,
                start_new_session=os.name != "nt",
            )
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
                exit_code = process.wait(timeout=request.timeout_seconds)
                self._terminate_remaining_group(process, job)
                return ProcessResult(exit_code, request.stdout_path, request.stderr_path, process.pid)
            except subprocess.TimeoutExpired:
                self._terminate_tree(process, job)
                return ProcessResult(124, request.stdout_path, request.stderr_path, process.pid, True)
            finally:
                self._active_process = None
                if job and self._active_job == job:
                    ctypes.windll.kernel32.CloseHandle(job)
                    self._active_job = None

    def cancel(self) -> None:
        if self._active_process and self._active_process.poll() is None:
            self._terminate_tree(self._active_process, self._active_job)

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
