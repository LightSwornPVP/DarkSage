from __future__ import annotations

import json
import os
import hashlib
import tempfile
import ctypes
from ctypes import wintypes
from pathlib import Path
from typing import Any


def atomic_write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(value, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except BaseException:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def process_exists(pid: int | None) -> bool:
    if not pid or pid <= 0:
        return False
    if os.name == "nt":
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.OpenProcess.argtypes = (ctypes.c_uint32, ctypes.c_int, ctypes.c_uint32)
        kernel32.OpenProcess.restype = ctypes.c_void_p
        kernel32.GetExitCodeProcess.argtypes = (
            ctypes.c_void_p,
            ctypes.POINTER(ctypes.c_uint32),
        )
        kernel32.GetExitCodeProcess.restype = ctypes.c_int
        kernel32.CloseHandle.argtypes = (ctypes.c_void_p,)
        kernel32.CloseHandle.restype = ctypes.c_int
        handle = kernel32.OpenProcess(0x1000, False, pid)
        if not handle:
            return False
        try:
            exit_code = ctypes.c_uint32()
            return bool(kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code))) and (
                exit_code.value == 259
            )
        finally:
            kernel32.CloseHandle(handle)
    try:
        os.kill(pid, 0)
    except (OSError, PermissionError):
        return False
    return True


def process_identity(pid: int) -> dict[str, object] | None:
    if pid <= 0 or not process_exists(pid):
        return None
    if os.name == "nt":
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        ntdll = ctypes.WinDLL("ntdll", use_last_error=True)
        kernel32.OpenProcess.argtypes = (
            wintypes.DWORD,
            wintypes.BOOL,
            wintypes.DWORD,
        )
        kernel32.OpenProcess.restype = wintypes.HANDLE
        kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
        kernel32.CloseHandle.restype = wintypes.BOOL
        kernel32.QueryFullProcessImageNameW.argtypes = (
            wintypes.HANDLE,
            wintypes.DWORD,
            wintypes.LPWSTR,
            ctypes.POINTER(wintypes.DWORD),
        )
        kernel32.QueryFullProcessImageNameW.restype = wintypes.BOOL
        kernel32.GetProcessTimes.argtypes = (
            wintypes.HANDLE,
            ctypes.POINTER(wintypes.FILETIME),
            ctypes.POINTER(wintypes.FILETIME),
            ctypes.POINTER(wintypes.FILETIME),
            ctypes.POINTER(wintypes.FILETIME),
        )
        kernel32.GetProcessTimes.restype = wintypes.BOOL
        ntdll.NtQueryInformationProcess.argtypes = (
            wintypes.HANDLE,
            wintypes.ULONG,
            wintypes.LPVOID,
            wintypes.ULONG,
            ctypes.POINTER(wintypes.ULONG),
        )
        ntdll.NtQueryInformationProcess.restype = wintypes.LONG
        handle = kernel32.OpenProcess(0x1000, False, pid)
        if not handle:
            return None
        try:
            image_buffer = ctypes.create_unicode_buffer(32768)
            image_size = wintypes.DWORD(len(image_buffer))
            if not kernel32.QueryFullProcessImageNameW(
                handle, 0, image_buffer, ctypes.byref(image_size)
            ):
                return None
            creation = wintypes.FILETIME()
            exit_time = wintypes.FILETIME()
            kernel_time = wintypes.FILETIME()
            user_time = wintypes.FILETIME()
            if not kernel32.GetProcessTimes(
                handle,
                ctypes.byref(creation),
                ctypes.byref(exit_time),
                ctypes.byref(kernel_time),
                ctypes.byref(user_time),
            ):
                return None

            class ProcessBasicInformation(ctypes.Structure):
                _fields_ = [
                    ("Reserved1", wintypes.LPVOID),
                    ("PebBaseAddress", wintypes.LPVOID),
                    ("Reserved2_0", wintypes.LPVOID),
                    ("Reserved2_1", wintypes.LPVOID),
                    ("UniqueProcessId", ctypes.c_size_t),
                    ("InheritedFromUniqueProcessId", ctypes.c_size_t),
                ]

            basic = ProcessBasicInformation()
            returned = wintypes.ULONG()
            if ntdll.NtQueryInformationProcess(
                handle,
                0,
                ctypes.byref(basic),
                ctypes.sizeof(basic),
                ctypes.byref(returned),
            ) != 0:
                return None
            required = wintypes.ULONG()
            status = ntdll.NtQueryInformationProcess(
                handle, 60, None, 0, ctypes.byref(required)
            )
            if status not in {-1073741820, -1073741789} or required.value <= 2:
                return None
            command_buffer = ctypes.create_string_buffer(required.value)
            if ntdll.NtQueryInformationProcess(
                handle,
                60,
                command_buffer,
                required.value,
                ctypes.byref(returned),
            ) != 0:
                return None
            command_length = ctypes.cast(
                command_buffer, ctypes.POINTER(wintypes.USHORT)
            ).contents.value
            pointer_offset = 8 if ctypes.sizeof(ctypes.c_void_p) == 8 else 4
            command_pointer = ctypes.c_void_p.from_buffer(
                command_buffer, pointer_offset
            ).value
            if not command_pointer or not command_length:
                return None
            command_line = ctypes.wstring_at(command_pointer, command_length // 2)
            creation_ticks = (creation.dwHighDateTime << 32) | creation.dwLowDateTime
            return {
                "pid": pid,
                "creation_time": str(creation_ticks),
                "executable": str(Path(image_buffer.value).resolve()),
                "command_line_hash": hashlib.sha256(
                    command_line.strip().casefold().encode("utf-8")
                ).hexdigest(),
                "parent_pid": int(basic.InheritedFromUniqueProcessId),
            }
        finally:
            kernel32.CloseHandle(handle)
    proc = Path("/proc") / str(pid)
    try:
        executable = proc.joinpath("exe").resolve(strict=True)
        command = proc.joinpath("cmdline").read_bytes()
        stat = proc.joinpath("stat").read_text(encoding="utf-8").split()
    except OSError:
        return None
    if len(stat) < 22 or not command:
        return None
    return {
        "pid": pid,
        "creation_time": stat[21],
        "executable": str(executable),
        "command_line_hash": hashlib.sha256(command).hexdigest(),
        "parent_pid": int(stat[3]),
    }


def process_identity_matches(
    ownership: object, current: dict[str, object] | None
) -> bool:
    if not isinstance(ownership, dict) or current is None:
        return False
    required = (
        "pid",
        "creation_time",
        "executable",
        "command_line_hash",
        "parent_pid",
        "launch_nonce",
        "ownership_token",
        "keeper_run_id",
        "task_id",
        "stage_id",
        "provider_run_id",
        "provider_name",
        "provider_instance_id",
        "role",
        "evidence_path",
        "job_or_group_identity",
    )
    if any(ownership.get(key) in {None, ""} for key in required):
        return False
    return all(
        ownership.get(key) == current.get(key)
        for key in (
            "pid",
            "creation_time",
            "executable",
            "command_line_hash",
            "parent_pid",
        )
    )


def ownership_records_match(
    authority: object, evidence: object
) -> bool:
    if not isinstance(authority, dict) or not isinstance(evidence, dict):
        return False
    required = (
        "keeper_run_id",
        "task_id",
        "stage_id",
        "provider_name",
        "provider_instance_id",
        "provider_run_id",
        "role",
        "ownership_token",
        "launch_nonce",
        "evidence_path",
        "pid",
        "creation_time",
        "executable",
        "command_line_hash",
        "parent_pid",
        "job_or_group_identity",
        "started_at",
    )
    if any(
        authority.get(key) in {None, ""} or evidence.get(key) in {None, ""}
        for key in required
    ):
        return False
    return all(authority.get(key) == evidence.get(key) for key in required)
