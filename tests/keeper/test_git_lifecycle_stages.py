from __future__ import annotations

import subprocess
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

from keeper.app.git_safety import GitSafetyService
from keeper.app.service import KeeperApplication


def git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=root, check=True, capture_output=True, text=True
    ).stdout.strip()


def wait(app: KeeperApplication, run_id: str, status: str) -> dict[str, object]:
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline:
        value = app.run_status(run_id)
        if value.get("status") == status:
            return value
        time.sleep(0.05)
    raise AssertionError(f"run did not reach {status}: {app.run_status(run_id)}")


def test_authorized_commit_and_push_are_lifecycle_stages(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init")
    git(repo, "config", "user.email", "keeper@example.invalid")
    git(repo, "config", "user.name", "Keeper")
    (repo / "README.md").write_text("baseline\n", encoding="utf-8")
    git(repo, "add", "README.md")
    git(repo, "commit", "-m", "baseline")
    remote = tmp_path / "remote.git"
    subprocess.run(["git", "init", "--bare", str(remote)], check=True, capture_output=True)
    git(repo, "remote", "add", "local", str(remote))

    app = KeeperApplication(tmp_path / "data")
    project = app.add_project(repo)
    task = app.create_task(
        {
            "title": "Authorized lifecycle Git",
            "objective": "Commit and push only with exact authority",
            "baseline": project["head"],
            "target_branch": "keeper/git",
            "included_paths": [".keeper-workflow/"],
            "is_demo": True,
            "provider_policy": "mock",
            "mock_scenario": "no-repair",
            "requires_manual_approval": True,
            "commit_requested": True,
            "push_requested": True,
            "push_remote": "local",
        }
    )
    run_id = str(app.start_task(str(task["id"]))["id"])
    ready = wait(app, run_id, "awaiting_approval")
    worktree = Path(str(ready["worktree"]))
    inspection = GitSafetyService().inspect(worktree)
    expires = (datetime.now(UTC) + timedelta(minutes=5)).isoformat()
    app.create_authorization(
        "commit",
        str(task["id"]),
        str(repo),
        "Founder",
        5,
        scope={
            "run_id": run_id,
            "worktree": str(worktree),
            "branch": inspection.branch,
            "head": inspection.head,
            "staged_paths": inspection.staged,
            "expires_at": expires,
        },
    )
    app.approve_run(run_id, "Founder")
    pushed = wait(app, run_id, "awaiting_push_authorization")
    commit_hash = str(pushed["commit_hash"])
    app.create_authorization(
        "push",
        str(task["id"]),
        str(repo),
        "Founder",
        5,
        scope={
            "run_id": run_id,
            "worktree": str(worktree),
            "branch": inspection.branch,
            "head": commit_hash,
            "remote": "local",
            "remote_url": str(remote),
            "source_ref": inspection.branch,
            "destination_ref": f"refs/heads/{inspection.branch}",
            "expected_commit": commit_hash,
            "force": False,
            "expires_at": expires,
        },
    )
    completed = app.wait_for_run(run_id, 30)
    assert completed["status"] == "COMPLETED"
    transitions = [item["to"] for item in completed["history"]]
    assert "authorized_commit" in transitions
    assert "authorized_push" in transitions
    assert git(remote, "rev-parse", f"refs/heads/{inspection.branch}") == commit_hash
