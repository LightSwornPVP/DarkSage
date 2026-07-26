from __future__ import annotations

from pathlib import Path

import pytest

from keeper.app.lifecycle import RunStage
from keeper.app.service import KeeperApplication
from keeper.recovery import ownership_records_match, process_identity_matches


def _ownership(**overrides: object) -> dict[str, object]:
    value: dict[str, object] = {
        "pid": 4242,
        "creation_time": "20260726120000.000000-240",
        "executable": "C:\\trusted\\provider.exe",
        "command_line_hash": "a" * 64,
        "parent_pid": 101,
        "launch_nonce": "nonce",
        "ownership_token": "token",
        "keeper_run_id": "run-reused-pid",
        "task_id": "task",
        "stage_id": "BUILDING",
        "provider_run_id": "provider-run",
        "provider_name": "provider",
        "provider_instance_id": "provider-instance",
        "role": "builder",
        "evidence_path": "C:\\evidence",
        "job_or_group_identity": "windows-job:1",
        "started_at": "2026-07-26T12:00:00+00:00",
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
    assert ownership_records_match(recorded, dict(recorded))


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
    ownership = _ownership(evidence_path=str(provider.resolve()))
    (provider / "run.json").write_text(
        __import__("json").dumps(
            {
                "run_id": "provider-run",
                "task_id": "task",
                "role": "builder",
                "status": "running",
                "process_id": 4242,
                "process_ownership": ownership,
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
    first.store.insert_immutable(
        "artifacts",
        "process-ownership:run-reused-pid:provider-run",
        {
            **ownership,
            "id": "process-ownership:run-reused-pid:provider-run",
            "kind": "process_ownership",
        },
    )
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


@pytest.mark.parametrize(
    ("field", "forged"),
    [
        ("ownership_token", "forged-token"),
        ("provider_run_id", "other-provider-run"),
        ("stage_id", "REVIEWING"),
        ("provider_name", "other-provider"),
        ("provider_instance_id", "other-instance"),
        ("evidence_path", "C:\\forged-evidence"),
        ("launch_nonce", "forged-nonce"),
        ("task_id", "other-task"),
        ("keeper_run_id", "other-run"),
    ],
)
def test_forged_provider_ownership_never_authorizes_termination(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    field: str,
    forged: str,
) -> None:
    data = tmp_path / "data"
    first = KeeperApplication(data)
    run_id = "run-forged"
    first.lifecycle.create(run_id, "task")
    first.lifecycle.transition(run_id, RunStage.SCOPE_VALIDATION)
    evidence = data / "evidence" / run_id
    provider = evidence / ".ai-workflow" / "runs" / "provider-run"
    provider.mkdir(parents=True)
    authority = _ownership(
        keeper_run_id=run_id,
        evidence_path=str(provider.resolve()),
    )
    forged_ownership = {**authority, field: forged}
    (provider / "run.json").write_text(
        __import__("json").dumps(
            {
                "run_id": "provider-run",
                "status": "running",
                "process_id": 4242,
                "process_ownership": forged_ownership,
            }
        ),
        encoding="utf-8",
    )
    record = first.store.get("runs", run_id)
    assert record is not None
    record.update(
        {"status": "running", "evidence_root": str(evidence), "process_id": 4242}
    )
    first.store.upsert("runs", run_id, record)
    first.store.insert_immutable(
        "artifacts",
        f"process-ownership:{run_id}:provider-run",
        {
            **authority,
            "id": f"process-ownership:{run_id}:provider-run",
            "kind": "process_ownership",
        },
    )
    monkeypatch.setattr("keeper.app.workflow.process_exists", lambda pid: True)
    monkeypatch.setattr(
        "keeper.app.workflow.process_identity",
        lambda pid: {
            key: authority[key]
            for key in (
                "pid",
                "creation_time",
                "executable",
                "command_line_hash",
                "parent_pid",
            )
        },
    )
    terminated: list[int] = []

    def terminate(pid: int) -> bool:
        terminated.append(pid)
        return True

    monkeypatch.setattr(
        "keeper.app.workflow._terminate_attributable_tree",
        terminate,
    )
    recovered = KeeperApplication(data).workflow.startup_recovery[0]
    assert terminated == []
    assert recovered["recovery"]["classification"] == "uncertain"
    assert recovered["recovery"]["ownership_binding_verified"] is False
    assert recovered["recovery"]["retry_safe"] is False


@pytest.mark.parametrize("authority_count", [0, 2])
def test_missing_or_duplicate_protected_ownership_is_uncertain(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    authority_count: int,
) -> None:
    data = tmp_path / "data"
    first = KeeperApplication(data)
    run_id = "run-authority-count"
    first.lifecycle.create(run_id, "task")
    first.lifecycle.transition(run_id, RunStage.SCOPE_VALIDATION)
    evidence = data / "evidence" / run_id
    provider = evidence / ".ai-workflow" / "runs" / "provider-run"
    provider.mkdir(parents=True)
    ownership = _ownership(
        keeper_run_id=run_id,
        evidence_path=str(provider.resolve()),
    )
    (provider / "run.json").write_text(
        __import__("json").dumps(
            {
                "run_id": "provider-run",
                "status": "running",
                "process_id": 4242,
                "process_ownership": ownership,
            }
        ),
        encoding="utf-8",
    )
    record = first.store.get("runs", run_id)
    assert record is not None
    record.update(
        {"status": "running", "evidence_root": str(evidence), "process_id": 4242}
    )
    first.store.upsert("runs", run_id, record)
    for index in range(authority_count):
        first.store.insert_immutable(
            "artifacts",
            f"process-ownership:{run_id}:provider-run:{index}",
            {
                **ownership,
                "id": f"process-ownership:{run_id}:provider-run:{index}",
                "kind": "process_ownership",
            },
        )
    monkeypatch.setattr("keeper.app.workflow.process_exists", lambda pid: True)
    monkeypatch.setattr(
        "keeper.app.workflow.process_identity",
        lambda pid: {
            key: ownership[key]
            for key in (
                "pid",
                "creation_time",
                "executable",
                "command_line_hash",
                "parent_pid",
            )
        },
    )
    terminated: list[int] = []

    def terminate(pid: int) -> bool:
        terminated.append(pid)
        return True

    monkeypatch.setattr(
        "keeper.app.workflow._terminate_attributable_tree",
        terminate,
    )
    recovered = KeeperApplication(data).workflow.startup_recovery[0]
    assert terminated == []
    assert recovered["recovery"]["classification"] == "uncertain"
    assert recovered["recovery"]["authoritative_ownership_record_count"] == (
        authority_count
    )


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
