from __future__ import annotations

import hashlib
import json
import multiprocessing
import os
import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from keeper.app.service import KeeperApplication
from keeper.app.storage import KeeperStore
from keeper.cli import main
from keeper.providers.base import AgentRequest
from keeper.providers.codex_cli import CliProvider
from keeper.recovery import ProcessState, _classify_windows_open_failure


def _authorization(expected: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": "authorization",
        **expected,
        "expires_at": (datetime.now(UTC) + timedelta(minutes=5)).isoformat(),
        "revoked_at": None,
        "consumed_at": None,
    }


def _expected() -> dict[str, Any]:
    return {
        "capability": "provider_reroute",
        "task_id": "task",
        "run_id": "run",
        "retry_stage": "author_execution",
        "provider_policy": "independent",
        "from_routing_digest": "a" * 64,
        "to_routing_digest": "b" * 64,
        "source_attempt_id": "source",
        "destination_attempt_number": 2,
        "capability_requirements": {"builder": "author"},
        "independence_requirements": {"builder": "independent"},
    }


def _race_worker(
    database: str,
    expected: dict[str, Any],
    start: Any,
    results: Any,
    consumer: str,
    launch_marker: str,
) -> None:
    store = KeeperStore(Path(database))
    start.wait(10)
    try:
        store.consume_reroute_authorization(
            "authorization", expected, consumer_id=consumer
        )
    except PermissionError as error:
        results.put(("lost", consumer, str(error)))
        return
    with Path(launch_marker).open("a", encoding="utf-8") as handle:
        handle.write(f"{consumer}\n")
    results.put(("won", consumer, "reserved"))


def _crash_after_reservation_worker(
    database: str, expected: dict[str, Any]
) -> None:
    KeeperStore(Path(database)).consume_reroute_authorization(
        "authorization", expected, consumer_id="crashed-reserver"
    )
    os._exit(91)


def _crash_after_execution_start_worker(data_directory: str) -> None:
    app = KeeperApplication(Path(data_directory))
    app.workflow._record_provider_execution(
        "run",
        {
            "event": "started",
            "provider_run_id": "provider-run",
            "task_id": "task",
            "stage_id": "author_execution",
            "role": "builder",
            "retry_count": 1,
            "provider_name": "test-provider",
            "provider_instance_id": "instance",
            "start_time": datetime.now(UTC).isoformat(),
            "evidence_path": str(
                Path(data_directory) / "evidence" / "provider-run" / "run.json"
            ),
        },
    )
    os._exit(92)


def _registered_script_provider(
    script: Path,
    *,
    before_process_create: Any = None,
) -> CliProvider:
    return CliProvider(
        (str(script), "{prompt}"),
        "controlled-command",
        expected_executable_sha256=hashlib.sha256(script.read_bytes()).hexdigest(),
        expected_executable_size=script.stat().st_size,
        registration_id="controlled-command",
        registration_version="1",
        configuration_digest="c" * 64,
        before_process_create=before_process_create,
    )


@pytest.mark.parametrize("error", [5, 1314, 12345])
def test_process_open_access_and_unknown_failures_are_indeterminate(
    error: int,
) -> None:
    probe = _classify_windows_open_failure(error)
    assert probe.state is ProcessState.INDETERMINATE
    assert probe.os_error == error
    assert "absent" not in probe.diagnostic


def test_invalid_pid_error_is_the_only_confirmed_absent_open_failure() -> None:
    probe = _classify_windows_open_failure(87)
    assert probe.state is ProcessState.CONFIRMED_ABSENT


@pytest.mark.skipif(os.name != "nt", reason="Windows retained-launch integration")
def test_same_path_same_size_replacement_is_blocked_after_validation(
    tmp_path: Path,
) -> None:
    marker = tmp_path / "marker.txt"
    original = tmp_path / "provider.cmd"
    replacement = tmp_path / "replacement.cmd"
    original_text = f'@echo original>"{marker}"\r\n'
    replacement_text = f'@echo replaced>"{marker}"\r\n'
    width = max(len(original_text), len(replacement_text))
    original.write_text(original_text.ljust(width), encoding="ascii", newline="")
    replacement.write_text(replacement_text.ljust(width), encoding="ascii", newline="")
    assert original.stat().st_size == replacement.stat().st_size
    replacement_errors: list[OSError] = []

    def attack() -> None:
        try:
            os.replace(replacement, original)
        except OSError as error:
            replacement_errors.append(error)

    provider = _registered_script_provider(
        original, before_process_create=attack
    )
    prompt = tmp_path / "prompt.md"
    prompt.write_text("controlled", encoding="utf-8")
    ownership: list[dict[str, Any]] = []
    result = provider.run(
        AgentRequest(
            "builder",
            prompt,
            tmp_path,
            10,
            tmp_path / "stdout.log",
            tmp_path / "stderr.log",
            on_process_owned=lambda value: ownership.append(value),
        )
    )
    assert result.exit_code == 0
    assert replacement_errors
    assert marker.read_text(encoding="utf-8").strip() == "original"
    assert ownership
    evidence = ownership[0]
    assert Path(str(evidence["registered_executable"])).resolve() == Path(
        os.environ["COMSPEC"]
    ).resolve()
    assert evidence["launched_executable_sha256"] == provider.expected_executable_sha256
    assert evidence["launched_executable_size"] == provider.expected_executable_size
    assert evidence["registration_id"] == "controlled-command"
    assert evidence["registration_version"] == "1"
    assert evidence["configuration_digest"] == provider.configuration_digest


@pytest.mark.skipif(os.name != "nt", reason="Windows reparse integration")
def test_reparse_retarget_after_validation_cannot_change_resolved_script(
    tmp_path: Path,
) -> None:
    marker = tmp_path / "reparse-marker.txt"
    original_dir = tmp_path / "original"
    replacement_dir = tmp_path / "replacement"
    original_dir.mkdir()
    replacement_dir.mkdir()
    name = "provider.cmd"
    (original_dir / name).write_text(
        f'@echo original>"{marker}"\r\n', encoding="ascii"
    )
    (replacement_dir / name).write_text(
        f'@echo replaced>"{marker}"\r\n', encoding="ascii"
    )
    link = tmp_path / "current"
    link_kind = "symlink"
    try:
        os.symlink(original_dir, link, target_is_directory=True)
    except OSError as symlink_error:
        link_kind = "junction"
        created = subprocess.run(
            [
                os.environ["COMSPEC"],
                "/d",
                "/c",
                "mklink",
                "/J",
                str(link),
                str(original_dir),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if created.returncode:
            pytest.skip(
                "Windows token cannot create a symlink and junction creation "
                f"also failed: {symlink_error}; {created.stderr}"
            )

    def retarget() -> None:
        if link_kind == "junction":
            os.rmdir(link)
            result = subprocess.run(
                [
                    os.environ["COMSPEC"],
                    "/d",
                    "/c",
                    "mklink",
                    "/J",
                    str(link),
                    str(replacement_dir),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            assert result.returncode == 0, result.stderr
        else:
            link.unlink()
            os.symlink(replacement_dir, link, target_is_directory=True)

    provider = _registered_script_provider(
        link / name, before_process_create=retarget
    )
    assert provider.command_script == (original_dir / name).resolve()
    prompt = tmp_path / "prompt.md"
    prompt.write_text("controlled", encoding="utf-8")
    result = provider.run(
        AgentRequest(
            "builder",
            prompt,
            tmp_path,
            10,
            tmp_path / "stdout.log",
            tmp_path / "stderr.log",
        )
    )
    assert result.exit_code == 0
    assert marker.read_text(encoding="utf-8").strip() == "original"


@pytest.mark.parametrize("command", ["start", "run-next"])
def test_standalone_commands_reject_incomplete_registration(
    tmp_path: Path, command: str
) -> None:
    workflow = tmp_path / ".ai-workflow"
    workflow.mkdir()
    (workflow / "config.json").write_text(
        json.dumps({"provider_command": [os.environ.get("COMSPEC", "cmd.exe"), "{prompt}"]}),
        encoding="utf-8",
    )
    assert main(["--root", str(tmp_path), command]) == 2


@pytest.mark.parametrize("command", ["start", "run-next"])
def test_standalone_commands_accept_complete_current_registration(
    tmp_path: Path, command: str
) -> None:
    executable = Path(os.environ.get("COMSPEC", "cmd.exe")).resolve(strict=True)
    workflow = tmp_path / ".ai-workflow"
    workflow.mkdir()
    provider_command = [str(executable), "/d", "/c", "exit", "0", "{prompt}"]
    (workflow / "config.json").write_text(
        json.dumps(
            {
                "provider_command": provider_command,
                "provider_registration": {
                    "id": "standalone-test",
                    "version": "1",
                    "executable_sha256": hashlib.sha256(
                        executable.read_bytes()
                    ).hexdigest(),
                    "executable_size": executable.stat().st_size,
                    "configuration_digest": hashlib.sha256(
                        json.dumps(provider_command).encode("utf-8")
                    ).hexdigest(),
                },
            }
        ),
        encoding="utf-8",
    )
    assert main(["--root", str(tmp_path), command]) == 0


@pytest.mark.parametrize("command", ["start", "run-next"])
def test_standalone_commands_reject_stale_registration(
    tmp_path: Path, command: str
) -> None:
    executable = Path(os.environ.get("COMSPEC", "cmd.exe")).resolve(strict=True)
    workflow = tmp_path / ".ai-workflow"
    workflow.mkdir()
    (workflow / "config.json").write_text(
        json.dumps(
            {
                "provider_command": [str(executable), "{prompt}"],
                "provider_registration": {
                    "id": "standalone-test",
                    "version": "1",
                    "executable_sha256": "0" * 64,
                    "executable_size": executable.stat().st_size,
                    "configuration_digest": "c" * 64,
                },
            }
        ),
        encoding="utf-8",
    )
    assert main(["--root", str(tmp_path), command]) == 2


def test_spawned_processes_consume_and_launch_exactly_once(
    tmp_path: Path,
) -> None:
    store = KeeperStore(tmp_path / "keeper.db")
    store.migrate()
    expected = _expected()
    store.upsert("authorizations", "authorization", _authorization(expected))
    context = multiprocessing.get_context("spawn")
    start = context.Event()
    results = context.Queue()
    marker = tmp_path / "launches.txt"
    workers = [
        context.Process(
            target=_race_worker,
            args=(
                str(store.path),
                expected,
                start,
                results,
                consumer,
                str(marker),
            ),
        )
        for consumer in ("consumer-one", "consumer-two")
    ]
    for worker in workers:
        worker.start()
    start.set()
    for worker in workers:
        worker.join(20)
        if worker.is_alive():
            worker.terminate()
            worker.join(5)
            pytest.fail("reroute race worker deadlocked")
    outcomes = [results.get(timeout=5) for _ in workers]
    assert sorted(item[0] for item in outcomes) == ["lost", "won"]
    winner = next(item[1] for item in outcomes if item[0] == "won")
    authorization = store.get("authorizations", "authorization")
    reservation = store.reroute_reservation("authorization")
    assert authorization is not None and reservation is not None
    assert authorization["consumer_id"] == winner
    assert authorization["consumed_at"]
    assert reservation["consumer_id"] == winner
    assert reservation["destination_attempt"] == 2
    assert marker.read_text(encoding="utf-8").splitlines() == [winner]
    with pytest.raises(PermissionError):
        store.consume_reroute_authorization("authorization", expected)


def test_crash_after_reservation_is_durable_and_non_reusable(
    tmp_path: Path,
) -> None:
    store = KeeperStore(tmp_path / "keeper.db")
    store.migrate()
    expected = _expected()
    store.upsert("authorizations", "authorization", _authorization(expected))
    context = multiprocessing.get_context("spawn")
    worker = context.Process(
        target=_crash_after_reservation_worker,
        args=(str(store.path), expected),
    )
    worker.start()
    worker.join(20)
    assert worker.exitcode == 91
    authorization = store.get("authorizations", "authorization")
    reservation = store.reroute_reservation("authorization")
    assert authorization is not None and authorization["consumed_at"]
    assert reservation is not None and reservation["state"] == "RESERVED"
    with pytest.raises(PermissionError):
        store.consume_reroute_authorization("authorization", expected)


def test_crash_after_execution_start_preserves_uncertain_attempt(
    tmp_path: Path,
) -> None:
    data = tmp_path / "data"
    app = KeeperApplication(data)
    expected = _expected()
    app.store.upsert("authorizations", "authorization", _authorization(expected))
    app.store.consume_reroute_authorization(
        "authorization", expected, consumer_id="execution-consumer"
    )
    app.store.upsert(
        "runs",
        "run",
        {
            "id": "run",
            "task_id": "task",
            "routing_attempts": [
                {
                    "attempt_id": "destination",
                    "attempt_number": 2,
                    "retry_of": "source",
                    "reroute_authorization_id": "authorization",
                    "decisions": [
                        {
                            "role": "builder",
                            "provider_instance_id": "instance",
                            "stable_registration_digest": "d" * 64,
                            "stable_registration": {"registration_id": "test"},
                            "executable": "provider.exe",
                            "executable_sha256": "e" * 64,
                        }
                    ],
                }
            ],
        },
    )
    context = multiprocessing.get_context("spawn")
    worker = context.Process(
        target=_crash_after_execution_start_worker, args=(str(data),)
    )
    worker.start()
    worker.join(20)
    assert worker.exitcode == 92
    run = app.store.get("runs", "run")
    reservation = app.store.reroute_reservation("authorization")
    assert run is not None
    attempts = run["provider_execution_attempts"]
    assert len(attempts) == 1
    assert attempts[0]["status"] == "EXECUTION_STARTED"
    assert reservation is not None
    assert reservation["state"] == "EXECUTION_STARTED"
    with pytest.raises(PermissionError):
        app.store.consume_reroute_authorization("authorization", expected)


def test_transaction_failure_rolls_back_consumption_and_reservation(
    tmp_path: Path,
) -> None:
    store = KeeperStore(tmp_path / "keeper.db")
    store.migrate()
    expected = _expected()
    store.upsert("authorizations", "authorization", _authorization(expected))
    with pytest.raises(RuntimeError, match="injected rollback"):
        store.consume_reroute_authorization(
            "authorization",
            expected,
            before_commit=lambda: (_ for _ in ()).throw(
                RuntimeError("injected rollback")
            ),
        )
    authorization = store.get("authorizations", "authorization")
    assert authorization is not None and authorization["consumed_at"] is None
    assert store.reroute_reservation("authorization") is None
    store.consume_reroute_authorization(
        "authorization", expected, consumer_id="later-consumer"
    )
    assert store.reroute_reservation("authorization") is not None
