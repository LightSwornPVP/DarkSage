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
from contextlib import AbstractContextManager, nullcontext
from pathlib import Path
from typing import Any, Callable, TextIO

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
        expected_script_sha256: str | None = None,
        expected_script_size: int | None = None,
        script_registration_id: str | None = None,
        script_registration_version: str | None = None,
        before_process_create: Callable[[Path], None] | None = None,
        require_prompt_placeholder: bool = True,
        launch_guard: Callable[[], AbstractContextManager[None]] | None = None,
    ) -> None:
        self.command_script: Path | None = None
        if (
            os.name == "nt"
            and command_template
            and Path(command_template[0]).suffix.casefold() in {".cmd", ".bat"}
        ):
            self.command_script = Path(command_template[0]).resolve(strict=True)
            launcher = Path(os.environ.get("COMSPEC", r"C:\Windows\System32\cmd.exe"))
            command_template = (str(launcher), *command_template[1:])
        self.command_template = command_template
        self.provider_name = provider_name
        self.expected_executable_sha256 = expected_executable_sha256
        self.expected_executable_size = expected_executable_size
        self.registration_id = registration_id
        self.registration_version = registration_version
        self.configuration_digest = configuration_digest
        self.expected_script_sha256 = expected_script_sha256
        self.expected_script_size = expected_script_size
        self.script_registration_id = script_registration_id
        self.script_registration_version = script_registration_version
        self.before_process_create = before_process_create
        self.require_prompt_placeholder = require_prompt_placeholder
        self.launch_guard = launch_guard
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
        if self.command_script is not None:
            if (
                self.expected_script_sha256 is None
                or self.expected_script_size is None
                or not self.script_registration_id
                or not self.script_registration_version
            ):
                raise PermissionError(
                    "immutable batch-script registration is incomplete"
                )
            script_content = self.command_script.read_bytes()
            if (
                hashlib.sha256(script_content).hexdigest()
                != self.expected_script_sha256
                or len(script_content) != self.expected_script_size
            ):
                raise PermissionError(
                    "provider batch script changed after registration"
                )
        if self.require_prompt_placeholder and "{prompt}" not in self.command_template:
            raise RuntimeError("provider_command must include the {prompt} argument placeholder")
        return resolved, content

    def run(self, request: AgentRequest) -> ProcessResult:
        guard = self.launch_guard() if self.launch_guard is not None else nullcontext()
        with guard:
            return self._run_guarded(request)

    def _run_guarded(self, request: AgentRequest) -> ProcessResult:
        registered_path, registered_content = self._validated_executable()
        request.stdout_path.parent.mkdir(parents=True, exist_ok=True)
        retained_executable_handles: list[int] = []
        protected_executable_fd: int | None = None
        protected_path = registered_path
        if os.name == "nt":
            retained_executable_handles.append(
                _retain_windows_file(registered_path, "registered executable")
            )
            if self.command_script is not None:
                retained_executable_handles.append(
                    _retain_windows_file(self.command_script, "registered command script")
                )
            if hashlib.sha256(registered_path.read_bytes()).hexdigest() != (
                self.expected_executable_sha256
            ):
                for handle in retained_executable_handles:
                    _close_windows_handle(handle)
                raise PermissionError(
                    "retained provider executable failed identity verification"
                )
            if self.command_script is not None and hashlib.sha256(
                self.command_script.read_bytes()
            ).hexdigest() != self.expected_script_sha256:
                for handle in retained_executable_handles:
                    _close_windows_handle(handle)
                raise PermissionError(
                    "retained provider batch script failed identity verification"
                )
        else:
            protected_executable_fd, protected_path = _sealed_executable(
                registered_content
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
            if self.before_process_create is not None:
                self.before_process_create(protected_path)
            popen_options: dict[str, Any] = {}
            if protected_executable_fd is not None:
                popen_options["pass_fds"] = (protected_executable_fd,)
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
                **popen_options,
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
                            "batch_script": (
                                str(self.command_script)
                                if self.command_script is not None
                                else None
                            ),
                            "batch_script_sha256": self.expected_script_sha256,
                            "batch_script_size": self.expected_script_size,
                            "script_registration_id": self.script_registration_id,
                            "script_registration_version": (
                                self.script_registration_version
                            ),
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
                for handle in retained_executable_handles:
                    _close_windows_handle(handle)
                if protected_executable_fd is not None:
                    os.close(protected_executable_fd)
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


def _retain_windows_file(path: Path, label: str) -> int:
    kernel32: Any = ctypes.windll.kernel32
    kernel32.CreateFileW.restype = ctypes.c_void_p
    handle = kernel32.CreateFileW(
        str(path),
        0x80000000,
        0x00000001,
        None,
        3,
        0x00000080,
        None,
    )
    if not handle or int(handle) == -1:
        raise PermissionError(f"{label} could not be retained against replacement")
    return int(handle)


def _close_windows_handle(handle: int) -> None:
    kernel32: Any = ctypes.windll.kernel32
    kernel32.CloseHandle.argtypes = (ctypes.c_void_p,)
    kernel32.CloseHandle.restype = ctypes.c_int
    if not kernel32.CloseHandle(ctypes.c_void_p(handle)):
        raise OSError(ctypes.get_last_error(), "unable to close retained file handle")


def _sealed_executable(content: bytes) -> tuple[int, Path]:
    if not hasattr(os, "memfd_create") or not Path("/proc/self/fd").is_dir():
        raise RuntimeError(
            "secure protected executable launch is unavailable on this platform"
        )
    import importlib

    fcntl: Any = importlib.import_module("fcntl")
    memfd_create: Any = getattr(os, "memfd_create")

    descriptor = memfd_create(
        "keeper-provider",
        int(getattr(os, "MFD_CLOEXEC", 1))
        | int(getattr(os, "MFD_ALLOW_SEALING", 2)),
    )
    try:
        view = memoryview(content)
        written = 0
        while written < len(view):
            written += os.write(descriptor, view[written:])
        os.fchmod(descriptor, 0o500)
        os.fsync(descriptor)
        fcntl.fcntl(
            descriptor,
            int(getattr(fcntl, "F_ADD_SEALS", 1033)),
            int(getattr(fcntl, "F_SEAL_SEAL", 1))
            | int(getattr(fcntl, "F_SEAL_SHRINK", 2))
            | int(getattr(fcntl, "F_SEAL_GROW", 4))
            | int(getattr(fcntl, "F_SEAL_WRITE", 8)),
        )
        path = Path(f"/proc/self/fd/{descriptor}")
        if hashlib.sha256(path.read_bytes()).digest() != hashlib.sha256(content).digest():
            raise PermissionError("sealed provider executable digest mismatch")
        return descriptor, path
    except BaseException:
        os.close(descriptor)
        raise
