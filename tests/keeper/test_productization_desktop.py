from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from keeper.app.service import KeeperApplication
from keeper.desktop import KeeperViewModel, main, parser


def _repo(root: Path) -> Path:
    root.mkdir()
    subprocess.run(["git", "init"], cwd=root, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "keeper@example.invalid"], cwd=root, check=True
    )
    subprocess.run(["git", "config", "user.name", "Keeper"], cwd=root, check=True)
    (root / "file.txt").write_text("one\n", encoding="utf-8")
    subprocess.run(["git", "add", "file.txt"], cwd=root, check=True)
    subprocess.run(["git", "commit", "-m", "initial"], cwd=root, check=True, capture_output=True)
    return root


def test_view_model_first_run_project_task_authorization_and_demo(tmp_path: Path) -> None:
    app = KeeperApplication(tmp_path / "data")
    model = KeeperViewModel(app)
    assert not app.setup_complete()
    assert any(item["provider_id"] == "mock" for item in model.diagnostics()["providers"])
    model.complete_setup(str(tmp_path / "evidence"))
    project = model.add_project(str(_repo(tmp_path / "repo")))
    task = model.create_task(
        {
            "title": "Desktop task",
            "objective": "Test display-independent workflows",
            "baseline": project["head"],
            "target_branch": "test/desktop",
        }
    )
    authorization = model.create_authorization(
        {
            "capability": "commit",
            "task_id": task["id"],
            "repository": project["repository"],
            "approving_authority": "founder",
            "minutes": 5,
        }
    )
    assert authorization["consumed_at"] is None
    assert model.run_demo()["status"] == "COMPLETED"


def test_headless_diagnostics_entrypoint(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert parser().parse_args(["--diagnostics"]).diagnostics
    assert main(["--data-dir", str(tmp_path / "data"), "--diagnostics"]) == 0
    assert '"local_only": true' in capsys.readouterr().out
