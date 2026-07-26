from __future__ import annotations

from pathlib import Path

import pytest

from keeper.app.lifecycle import RunStage
from keeper.app.service import KeeperApplication
from keeper.recovery import process_identity_matches


def _ownership(**overrides: object) -> dict[str, object]:
    value: dict[str, object] = {
        "pid": 4242,
        "creation_time": "20260726120000.000000-240",
        "executable": "C:\\trusted\\provider.exe",
        "command_line_hash": "a" * 64,
        "parent_pid": 101,
        "launch_nonce": "nonce",
        "provider_run_id": "provider-run",
        "provider_name": "provider",
        "role": "builder",
        "evidence_path": "C:\\evidence",
    }
    value.update(overrides)
    return value


def test_process_identity_requires_creation_executable_command_and_parent() -> None:
    recorded = _ownership()
    current = {
        key: recorded[key]
        for key in (
            "pid",
            "creation_time",
            "executable",
            "command_line_hash",
            "parent_pid",
        )
    }
    assert process_identity_matches(recorded, current)
    for key, wrong in (
        ("creation_time", "different"),
        ("executable", "C:\\other.exe"),
        ("command_line_hash", "b" * 64),
        ("parent_pid", 202),
    ):
        assert not process_identity_matches(recorded, {**current, key: wrong})
    assert not process_identity_matches({"pid": 4242}, current)
    assert not process_identity_matches(recorded, None)


def test_reused_pid_is_uncertain_and_never_terminated(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    data = tmp_path / "data"
    first = KeeperApplication(data)
    run_id = "run-reused-pid"
    first.lifecycle.create(run_id, "task")
    for stage in (
        RunStage.SCOPE_VALIDATION,
        RunStage.RISK_CLASSIFICATION,
        RunStage.AUTHORIZATION_RESOLUTION,
        RunStage.PROVIDER_SELECTION,
        RunStage.WORKTREE_PREPARATION,
        RunStage.AUTHOR_EXECUTION,
    ):
        first.lifecycle.transition(run_id, stage)
    evidence = data / "evidence" / run_id
    provider = evidence / ".ai-workflow" / "runs" / "provider-run"
    provider.mkdir(parents=True)
    (provider / "run.json").write_text(
        __import__("json").dumps(
            {
                "status": "running",
                "process_id": 4242,
                "process_ownership": _ownership(),
            }
        ),
        encoding="utf-8",
    )
    record = first.store.get("runs", run_id)
    assert record is not None
    record.update(
        {
            "status": "running",
            "evidence_root": str(evidence),
            "process_id": 4242,
        }
    )
    first.store.upsert("runs", run_id, record)
    monkeypatch.setattr("keeper.app.workflow.process_exists", lambda pid: True)
    monkeypatch.setattr(
        "keeper.app.workflow.process_identity",
        lambda pid: {
            "pid": 4242,
            "creation_time": "reused",
            "executable": "C:\\unrelated.exe",
            "command_line_hash": "b" * 64,
            "parent_pid": 999,
        },
    )
    terminated: list[int] = []

    def record_termination(pid: int) -> bool:
        terminated.append(pid)
        return True

    monkeypatch.setattr(
        "keeper.app.workflow._terminate_attributable_tree",
        record_termination,
    )
    restarted = KeeperApplication(data)
    recovered = next(
        item for item in restarted.workflow.startup_recovery if item["id"] == run_id
    )
    assert terminated == []
    assert recovered["recovery"]["classification"] == "uncertain"
    assert recovered["recovery"]["identity_verified"] is False
    assert recovered["recovery"]["retry_safe"] is False


def test_missing_process_is_recoverable_without_termination(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    data = tmp_path / "data"
    first = KeeperApplication(data)
    first.lifecycle.create("run-missing", "task")
    first.lifecycle.transition("run-missing", RunStage.SCOPE_VALIDATION)
    record = first.store.get("runs", "run-missing")
    assert record is not None
    record.update({"status": "running", "process_id": 999999})
    first.store.upsert("runs", "run-missing", record)
    monkeypatch.setattr("keeper.app.workflow.process_exists", lambda pid: False)
    restarted = KeeperApplication(data)
    recovered = next(
        item
        for item in restarted.workflow.startup_recovery
        if item["id"] == "run-missing"
    )
    assert recovered["recovery"]["classification"] == "recoverable"
    assert recovered["recovery"]["retry_safe"] is True
