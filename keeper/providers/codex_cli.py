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
        expected_executable_size: int | None = None,
        registration_id: str | None = None,
        registration_version: str | None = None,
        configuration_digest: str | None = None,
    ) -> None:
        self.command_script: Path | None = None
        if (
            os.name == "nt"
            and command_template
            and Path(command_template[0]).suffix.casefold() in {".cmd", ".bat"}
        ):
            self.command_script = Path(command_template[0]).resolve(strict=True)
            launcher = Path(os.environ.get("COMSPEC", r"C:\Windows\System32\cmd.exe"))
            script_digest = hashlib.sha256(self.command_script.read_bytes()).hexdigest()
            command_template = (str(launcher), *command_template[1:])
            expected_executable_sha256 = hashlib.sha256(launcher.read_bytes()).hexdigest()
            expected_executable_size = launcher.stat().st_size
            configuration_digest = hashlib.sha256(
                f"{configuration_digest or ''}:{script_digest}".encode("utf-8")
            ).hexdigest()
        self.command_template = command_template
        self.provider_name = provider_name
        self.expected_executable_sha256 = expected_executable_sha256
        self.expected_executable_size = expected_executable_size
        self.registration_id = registration_id
        self.registration_version = registration_version
        self.configuration_digest = configuration_digest
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
        self._validated_executable()

    def _validated_executable(self) -> tuple[Path, bytes]:
        if not self.command_template:
            raise RuntimeError(
                "agent provider command is not configured; set provider_command "
                "in .ai-workflow/config.json"
            )
        executable = self.command_template[0]
        if not Path(executable).exists() and shutil.which(executable) is None:
            raise RuntimeError(f"configured agent provider executable was not found: {executable}")
        if (
            self.expected_executable_sha256 is None
            or self.expected_executable_size is None
            or not self.registration_id
            or not self.registration_version
            or not self.configuration_digest
        ):
            raise PermissionError("immutable provider executable registration is incomplete")
        resolved = Path(executable).resolve(strict=True)
        content = resolved.read_bytes()
        actual = hashlib.sha256(content).hexdigest()
        if (
            actual != self.expected_executable_sha256
            or len(content) != self.expected_executable_size
        ):
            raise PermissionError(
                "provider executable content changed after registration"
            )
        if "{prompt}" not in self.command_template:
            raise RuntimeError("provider_command must include the {prompt} argument placeholder")
        return resolved, content

    def run(self, request: AgentRequest) -> ProcessResult:
        registered_path, registered_content = self._validated_executable()
        request.stdout_path.parent.mkdir(parents=True, exist_ok=True)
        retained_executable_handle: int | None = None
        protected_path = registered_path
        if os.name == "nt":
            kernel32: Any = ctypes.windll.kernel32
            kernel32.CreateFileW.restype = ctypes.c_void_p
            handle = kernel32.CreateFileW(
                str(registered_path),
                0x80000000,
                0x00000001,
                None,
                3,
                0x00000080,
                None,
            )
            if not handle or int(handle) == -1:
                raise PermissionError(
                    "registered executable could not be retained against replacement"
                )
            retained_executable_handle = int(handle)
            if hashlib.sha256(registered_path.read_bytes()).hexdigest() != (
                self.expected_executable_sha256
            ):
                kernel32.CloseHandle(retained_executable_handle)
                raise PermissionError(
                    "retained provider executable failed identity verification"
                )
        else:
            protected_directory = request.stdout_path.parent / ".protected-executables"
            protected_directory.mkdir(parents=True, exist_ok=True)
            suffix = registered_path.suffix
            protected_path = (
                protected_directory
                / f"{str(self.expected_executable_sha256)[:16]}-{uuid.uuid4().hex[:8]}{suffix}"
            )
            descriptor = os.open(
                protected_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o500
            )
            try:
                with os.fdopen(descriptor, "wb") as protected:
                    protected.write(registered_content)
                    protected.flush()
                    os.fsync(protected.fileno())
            except BaseException:
                protected_path.unlink(missing_ok=True)
                raise
            os.chmod(protected_path, 0o500)
            if hashlib.sha256(protected_path.read_bytes()).hexdigest() != (
                self.expected_executable_sha256
            ):
                raise PermissionError(
                    "protected provider executable failed identity verification"
                )
        environment = filtered_environment(dict(os.environ))
        environment["KEEPER_PROVIDER_ROLE"] = request.role
        environment["PATH"] = (
            str(registered_path.parent)
            + os.pathsep
            + environment.get("PATH", "")
        )
        with (
            request.stdout_path.open("w", encoding="utf-8") as stdout,
            request.stderr_path.open("w", encoding="utf-8") as stderr,
        ):
            command = self.build_command(request)
            if self.command_script is not None:
                command = [
                    str(protected_path),
                    "/d",
                    "/c",
                    str(self.command_script),
                    *command[1:],
                ]
            else:
                command[0] = str(protected_path)
            process = subprocess.Popen(
                command,
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
                job_kernel32: Any = ctypes.windll.kernel32
                job = int(job_kernel32.CreateJobObjectW(None, None))
                if not job or not job_kernel32.AssignProcessToJobObject(
                    job, int(process._handle)  # type: ignore[attr-defined]
                ):
                    if job:
                        job_kernel32.CloseHandle(job)
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
                    if Path(str(identity["executable"])).resolve() != protected_path.resolve():
                        raise PermissionError(
                            "launched provider image did not match retained registration"
                        )
                    request.on_process_owned(
                        {
                            **identity,
                            "registered_executable": str(registered_path),
                            "launched_executable": str(protected_path),
                            "launched_executable_sha256": self.expected_executable_sha256,
                            "launched_executable_size": self.expected_executable_size,
                            "registration_id": self.registration_id,
                            "registration_version": self.registration_version,
                            "configuration_digest": self.configuration_digest,
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
                if retained_executable_handle is not None:
                    ctypes.windll.kernel32.CloseHandle(retained_executable_handle)

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
