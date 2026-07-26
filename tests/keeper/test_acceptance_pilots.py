from __future__ import annotations

import subprocess
from pathlib import Path

from keeper.app.reporting import verify_evidence
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


def task(app: KeeperApplication, root: Path, scenario: str) -> str:
    repo, head = repository(root)
    project = app.add_project(repo)
    created = app.create_task(
        {
            "title": scenario,
            "objective": f"Acceptance pilot: {scenario}",
            "repository": project["repository"],
            "baseline": head,
            "target_branch": f"keeper/{scenario}",
            "included_paths": [".keeper-workflow/"],
            "mock_scenario": scenario,
        }
    )
    return str(created["id"])


def test_success_repair_and_no_repair_pilots_preserve_evidence(tmp_path: Path) -> None:
    app = KeeperApplication(tmp_path / "data")
    repair = app.execute_task(task(app, tmp_path / "repair", "repair"))
    no_repair = app.execute_task(task(app, tmp_path / "clean", "no-repair"))
    for run in (repair, no_repair):
        assert run["status"] == "COMPLETED"
        root = Path(str(run["evidence_root"]))
        verify_evidence(root)
        assert app.evidence_path(str(run["id"]), "json").is_file()
    assert "repair_execution" in [item["to"] for item in repair["history"]]
    assert "repair_execution" not in [item["to"] for item in no_repair["history"]]


def test_same_identity_reviewer_pilot_blocks_without_approval(tmp_path: Path) -> None:
    app = KeeperApplication(tmp_path / "data")
    run = app.execute_task(task(app, tmp_path / "repo", "blocked-reviewer"))
    assert run["stage"] == "blocked"
    assert run.get("outcome") != "approved"
    assert "evidence_root" not in run


def test_history_filters_use_persisted_authoritative_fields(tmp_path: Path) -> None:
    app = KeeperApplication(tmp_path / "data")
    run = app.execute_task(task(app, tmp_path / "repo", "no-repair"))
    matches = app.filtered_runs(
        repository=str(run["repository"]),
        branch=str(run["branch"]),
        task_id=str(run["task_id"]),
        outcome="COMPLETED",
    )
    assert [item["id"] for item in matches] == [run["id"]]
    assert app.filtered_runs(repository="C:/not-this-repository") == []
