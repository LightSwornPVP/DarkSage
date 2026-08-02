from __future__ import annotations

import ctypes
import hashlib
import json
import os
import threading
from contextlib import contextmanager
from ctypes import wintypes
from pathlib import Path
from typing import Any, Callable, Iterator, Mapping

from keeper.authority_service.restricted_process import (
    RestrictedProcessResult,
    current_process_token,
    profile_restricted_primary_token,
    run_restricted_process,
)
from keeper.authority_service.windows_signature import authenticode_identity
from keeper.providers.codex_contract import (
    app_server_probe_input,
    build_codex_exec_command,
    parse_codex_app_server_probe,
)


_GENERIC_READ = 0x80000000
_FILE_SHARE_READ = 0x00000001
_OPEN_EXISTING = 3
_FILE_ATTRIBUTE_NORMAL = 0x00000080
_INVALID_HANDLE = ctypes.c_void_p(-1).value


class ProviderProcessLauncher:
    """Launch a measured provider under the user host's restricted token."""

    def __init__(self, output_root: Path) -> None:
        self.output_root = output_root.resolve()

    def launch(
        self,
        envelope: Mapping[str, Any],
        environment: Mapping[str, str],
        cancel_requested: threading.Event,
        *,
        on_started: Callable[[dict[str, object]], None],
        on_resumed: Callable[[dict[str, object]], None],
    ) -> dict[str, Any]:
        executable = Path(str(envelope["executable"]["path"]))
        workspace = Path(str(envelope["workspace"]["canonical_path"])).resolve(
            strict=True
        )
        limits = envelope["resource_limits"]
        launch_id = str(envelope["launch_id"])
        self.output_root.mkdir(parents=True, exist_ok=True)
        stdout_path = self.output_root / f"{launch_id}.stdout"
        stderr_path = self.output_root / f"{launch_id}.stderr"
        with locked_executable(executable, envelope["executable"]) as measurement:
            with current_process_token() as current_token:
                with profile_restricted_primary_token(current_token) as restricted:
                    result = run_restricted_process(
                        restricted,
                        [str(executable), *list(envelope["argv"])],
                        executable,
                        workspace,
                        dict(environment),
                        stdout_path,
                        stderr_path,
                        float(limits["timeout_seconds"]),
                        on_started,
                        cancel_requested,
                        on_resumed=on_resumed,
                        integrity_level="medium",
                        validated_executable_identity=measurement,
                        active_process_limit=int(limits["active_process_limit"]),
                        memory_bytes=int(limits["memory_bytes"]),
                        stdout_bytes=int(limits["stdout_bytes"]),
                        stderr_bytes=int(limits["stderr_bytes"]),
                    )
        return _public_result(result, stdout_path, stderr_path)


class CodexSetupRunner:
    """Host-side, Authority-bound Codex registration/qualification executor."""

    def __init__(self, output_root: Path) -> None:
        self.output_root = output_root.resolve()

    def run_setup(
        self,
        envelope: Mapping[str, Any],
        environment: Mapping[str, str],
        cancel_requested: threading.Event,
        *,
        on_started: Callable[[dict[str, object]], None],
        on_resumed: Callable[[dict[str, object]], None],
    ) -> dict[str, Any]:
        executable = Path(str(envelope["executable"]["path"]))
        workspace = Path(str(envelope["workspace"]["canonical_path"])).resolve(
            strict=True
        )
        limits = envelope["resource_limits"]
        setup_id = str(envelope["setup_id"])
        setup_root = self.output_root / hashlib.sha256(
            setup_id.encode("utf-8")
        ).hexdigest()
        setup_root.mkdir(parents=True, exist_ok=False)
        model_id = str(envelope["model_id"])
        account_binding = dict(envelope["account_binding"])
        version_stdout = setup_root / "version.stdout"
        version_stderr = setup_root / "version.stderr"
        probe_stdin = setup_root / "probe.stdin"
        probe_stdout = setup_root / "probe.stdout"
        probe_stderr = setup_root / "probe.stderr"
        with probe_stdin.open("xb") as stream:
            stream.write(app_server_probe_input().encode("utf-8"))
            stream.flush()
            os.fsync(stream.fileno())
        failure_reason: str | None = None
        version_text = ""
        authentication_probe: dict[str, Any] | None = None
        structured_output: dict[str, Any] | None = None
        usage_observation: dict[str, Any] | None = None
        production_command: tuple[str, ...] = ()
        prompt_digest: str | None = None
        schema_digest: str | None = None
        ownership: dict[str, Any] = {
            "job_confined": False,
            "restricted": False,
            "integrity_level": "unknown",
            "launch_nonce": str(envelope["challenge"]),
        }
        exit_status = 70
        try:
            with locked_executable(executable, envelope["executable"]) as measurement:
                with current_process_token() as current_token:
                    with profile_restricted_primary_token(current_token) as restricted:
                        version = run_restricted_process(
                            restricted,
                            [str(executable), "--version"],
                            executable,
                            workspace,
                            dict(environment),
                            version_stdout,
                            version_stderr,
                            min(30, float(limits["timeout_seconds"])),
                            on_started,
                            cancel_requested,
                            on_resumed=on_resumed,
                            integrity_level="medium",
                            validated_executable_identity=measurement,
                            active_process_limit=int(limits["active_process_limit"]),
                            memory_bytes=int(limits["memory_bytes"]),
                            stdout_bytes=int(limits["stdout_bytes"]),
                            stderr_bytes=int(limits["stderr_bytes"]),
                        )
                        version_text = version.stdout.strip()
                        lines = version_text.splitlines()
                        if (
                            version.exit_code != 0
                            or not lines
                            or lines[0].strip() != envelope["executable"]["version"]
                        ):
                            raise PermissionError(
                                "Codex setup executable version differs"
                            )
                        probe = run_restricted_process(
                            restricted,
                            [str(executable), "app-server", "--listen", "stdio://"],
                            executable,
                            workspace,
                            dict(environment),
                            probe_stdout,
                            probe_stderr,
                            min(30, float(limits["timeout_seconds"])),
                            cancel_requested=cancel_requested,
                            stdin_path=probe_stdin,
                            integrity_level="medium",
                            validated_executable_identity=measurement,
                            active_process_limit=int(limits["active_process_limit"]),
                            memory_bytes=int(limits["memory_bytes"]),
                            stdout_bytes=int(limits["stdout_bytes"]),
                            stderr_bytes=int(limits["stderr_bytes"]),
                        )
                        if probe.exit_code != 0 or probe.timed_out:
                            raise PermissionError("Codex setup account probe failed")
                        authentication_probe = parse_codex_app_server_probe(
                            probe.stdout.splitlines(),
                            model_allowlist=[model_id],
                        )
                        observed_binding = {
                            name: authentication_probe[name]
                            for name in (
                                "account_identity_digest",
                                "authentication_method",
                                "plan_type",
                            )
                        }
                        if (
                            account_binding["account_identity_digest"]
                            == "DISCOVER"
                        ):
                            expected_discovery = {
                                "account_identity_digest": "DISCOVER",
                                "authentication_method": "chatgpt-subscription",
                                "plan_type": "plus",
                            }
                            if account_binding != expected_discovery:
                                raise PermissionError(
                                    "Codex setup discovery policy is invalid"
                                )
                        elif observed_binding != account_binding:
                            raise PermissionError(
                                "Codex setup authenticated account differs"
                            )
                        usage_observation = dict(
                            authentication_probe["usage_observation"]
                        )
                        final = probe
                        if envelope["operation"] == "QUALIFY":
                            schema = {
                                "type": "object",
                                "additionalProperties": False,
                                "properties": {
                                    "status": {"const": "ok"},
                                    "provider": {"const": "codex"},
                                    "effort": {"const": "medium"},
                                    "nonce": {
                                        "const": "keeper-codex-qualification-v1"
                                    },
                                },
                                "required": [
                                    "status",
                                    "provider",
                                    "effort",
                                    "nonce",
                                ],
                            }
                            prompt = (
                                "Return only the JSON object required by the supplied "
                                "schema. This is a harmless Keeper provider qualification. "
                                "Do not read or write project files, use tools, access "
                                "credentials, or perform any operation beyond this response."
                            )
                            schema_path = setup_root / "qualification-schema.json"
                            output_path = setup_root / "qualification-output.json"
                            events_path = setup_root / "qualification-events.jsonl"
                            error_path = setup_root / "qualification.stderr"
                            schema_bytes = json.dumps(
                                schema, sort_keys=True, separators=(",", ":")
                            ).encode("utf-8")
                            with schema_path.open("xb") as stream:
                                stream.write(schema_bytes)
                                stream.flush()
                                os.fsync(stream.fileno())
                            command = build_codex_exec_command(
                                executable,
                                model_id=model_id,
                                reasoning_level="medium",
                                schema_path=schema_path,
                                output_path=output_path,
                                prompt=prompt,
                            )
                            production_command = tuple(command)
                            prompt_digest = hashlib.sha256(
                                prompt.encode("utf-8")
                            ).hexdigest()
                            schema_digest = hashlib.sha256(schema_bytes).hexdigest()
                            final = run_restricted_process(
                                restricted,
                                command,
                                executable,
                                workspace,
                                dict(environment),
                                events_path,
                                error_path,
                                float(limits["timeout_seconds"]),
                                cancel_requested=cancel_requested,
                                integrity_level="medium",
                                validated_executable_identity=measurement,
                                active_process_limit=int(
                                    limits["active_process_limit"]
                                ),
                                memory_bytes=int(limits["memory_bytes"]),
                                stdout_bytes=int(limits["stdout_bytes"]),
                                stderr_bytes=int(limits["stderr_bytes"]),
                            )
                            if final.exit_code != 0 or final.timed_out:
                                raise PermissionError(
                                    "Codex setup qualification request failed"
                                )
                            try:
                                parsed = json.loads(
                                    output_path.read_text(encoding="utf-8")
                                )
                            except (OSError, json.JSONDecodeError) as error:
                                raise PermissionError(
                                    "Codex setup qualification output is invalid"
                                ) from error
                            expected_output = {
                                "status": "ok",
                                "provider": "codex",
                                "effort": "medium",
                                "nonce": "keeper-codex-qualification-v1",
                            }
                            if parsed != expected_output:
                                raise PermissionError(
                                    "Codex setup qualification output differs"
                                )
                            structured_output = expected_output
                        ownership = {
                            "pid": final.process_id,
                            "launch_nonce": str(envelope["challenge"]),
                            "restricted": final.restricted,
                            "integrity_level": final.integrity_level,
                            "job_confined": final.job_confined,
                            "executable": str(executable),
                            "executable_sha256": str(
                                envelope["executable"]["sha256"]
                            ),
                        }
                        exit_status = 0
        except (OSError, PermissionError, RuntimeError, ValueError) as error:
            failure_reason = f"{type(error).__name__}: {error}"
        return {
            "authentication_probe": authentication_probe,
            "exit_status": exit_status,
            "failure_reason": failure_reason,
            "process_ownership": ownership,
            "production_command": list(production_command),
            "prompt_digest": prompt_digest,
            "provider_instance_id": (
                "codex-session:"
                + str(envelope["provider_registration_id"])
                + ":"
                + str(envelope["user_binding"]["session_id"])
            ),
            "raw_version_output": version_text,
            "schema_digest": schema_digest,
            "structured_output": structured_output,
            "usage_observation": usage_observation,
        }


@contextmanager
def locked_executable(
    executable: Path, declared: Mapping[str, object]
) -> Iterator[dict[str, Any]]:
    """Deny executable write/delete sharing through suspended creation."""

    if os.name != "nt":
        raise RuntimeError("Provider Host process launch requires Windows")
    canonical = executable.resolve(strict=True)
    kernel32 = _kernel32()
    handle = kernel32.CreateFileW(
        str(canonical),
        _GENERIC_READ,
        _FILE_SHARE_READ,
        None,
        _OPEN_EXISTING,
        _FILE_ATTRIBUTE_NORMAL,
        None,
    )
    if handle in {None, _INVALID_HANDLE}:
        raise PermissionError(
            "Provider Host executable cannot be locked: "
            f"{ctypes.get_last_error()}"
        )
    try:
        content = canonical.read_bytes()
        stat = canonical.stat()
        file_identity = {
            "device_id": int(stat.st_dev),
            "file_id": int(stat.st_ino),
            "modified_ns": int(stat.st_mtime_ns),
            "schema_version": 1,
            "size": int(stat.st_size),
        }
        observed = {
            "authenticode_binding": dict(authenticode_identity(canonical)),
            "canonical_path": str(canonical),
            "file_identity": file_identity,
            "sha256": hashlib.sha256(content).hexdigest(),
            "size": len(content),
        }
        expected = {
            "authenticode_binding": declared.get("authenticode_binding"),
            "canonical_path": declared.get("path"),
            "file_identity": declared.get("file_identity"),
            "sha256": declared.get("sha256"),
            "size": declared.get("size"),
        }
        if observed != expected:
            raise PermissionError("Provider Host executable identity changed")
        yield observed
        final = canonical.stat()
        if (
            int(final.st_dev),
            int(final.st_ino),
            int(final.st_mtime_ns),
            int(final.st_size),
        ) != (
            file_identity["device_id"],
            file_identity["file_id"],
            file_identity["modified_ns"],
            file_identity["size"],
        ):
            raise PermissionError("Provider Host executable changed during launch")
    finally:
        if not kernel32.CloseHandle(handle):
            raise PermissionError("Provider Host executable lock did not close")


def _public_result(
    result: RestrictedProcessResult, stdout_path: Path, stderr_path: Path
) -> dict[str, Any]:
    stdout = stdout_path.read_bytes() if stdout_path.exists() else b""
    stderr = stderr_path.read_bytes() if stderr_path.exists() else b""
    return {
        "exit_code": result.exit_code,
        "job_confined": result.job_confined,
        "pid": result.process_id,
        "restricted": result.restricted,
        "stderr_digest": hashlib.sha256(stderr).hexdigest(),
        "stdout_digest": hashlib.sha256(stdout).hexdigest(),
        "timed_out": result.timed_out,
    }


def _kernel32() -> Any:
    api = ctypes.WinDLL("kernel32", use_last_error=True)
    api.CreateFileW.argtypes = [
        wintypes.LPCWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.LPVOID,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.HANDLE,
    ]
    api.CreateFileW.restype = wintypes.HANDLE
    api.CloseHandle.argtypes = [wintypes.HANDLE]
    api.CloseHandle.restype = wintypes.BOOL
    return api
