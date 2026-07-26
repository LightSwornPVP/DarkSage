from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from keeper.app.lifecycle import RunStage
from keeper.app.service import KeeperApplication


def repository(root: Path) -> tuple[Path, str]:
    root.mkdir()
    for args in (
        ("init",),
        ("config", "user.email", "keeper@example.invalid"),
        ("config", "user.name", "Keeper"),
    ):
        subprocess.run(["git", *args], cwd=root, check=True, capture_output=True)
    (root / "README.md").write_text("baseline\n", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"], cwd=root, check=True)
    subprocess.run(["git", "commit", "-m", "baseline"], cwd=root, check=True, capture_output=True)
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=root, check=True, capture_output=True, text=True
    ).stdout.strip()
    return root, head


def create_task(app: KeeperApplication, root: Path) -> str:
    repo, head = repository(root)
    app.add_project(repo)
    return str(
        app.create_task(
            {
                "title": "Recovery",
                "objective": "Recover safely",
                "baseline": head,
                "target_branch": "keeper/recovery",
                "included_paths": [".keeper-workflow/"],
                "mock_scenario": "no-repair",
            }
        )["id"]
    )


def test_restart_classifies_interrupted_run_and_explicit_retry_completes(
    tmp_path: Path,
) -> None:
    data = tmp_path / "data"
    first = KeeperApplication(data)
    task_id = create_task(first, tmp_path / "repo")
    first.lifecycle.create("run-crashed", task_id)
    first.lifecycle.transition("run-crashed", RunStage.SCOPE_VALIDATION)
    record = first.store.get("runs", "run-crashed")
    assert record is not None
    record.update({"status": "running", "attempt": 1, "process_id": 999999})
    first.store.upsert("runs", "run-crashed", record)

    restarted = KeeperApplication(data)
    recovered = restarted.store.get("runs", "run-crashed")
    assert recovered is not None
    assert recovered["status"] == "interrupted"
    assert recovered["recovery"]["retry_safe"] is True
    retried = restarted.retry_run("run-crashed", "provider process disappeared")
    completed = restarted.wait_for_run(str(retried["id"]), 20)
    assert completed["status"] == "COMPLETED"
    assert completed["retry_of"] == "run-crashed"
    assert completed["attempt"] == 2


def test_retry_rejects_completed_and_irreversible_runs(tmp_path: Path) -> None:
    app = KeeperApplication(tmp_path / "data")
    app.lifecycle.create("completed", "task")
    record = app.store.get("runs", "completed")
    assert record is not None
    record["status"] = "COMPLETED"
    app.store.upsert("runs", "completed", record)
    with pytest.raises(PermissionError):
        app.retry_run("completed", "not allowed")

    app.lifecycle.create("push", "task")
    record = app.store.get("runs", "push")
    assert record is not None
    record.update(
        {
            "status": "interrupted",
            "stage": "interrupted",
            "interrupted_from": "authorized_push",
            "recovery": {"retry_safe": False, "previous_process_running": False},
        }
    )
    app.store.upsert("runs", "push", record)
    with pytest.raises(PermissionError):
        app.retry_run("push", "never repeat push")
