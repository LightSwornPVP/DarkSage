from __future__ import annotations

import subprocess
from pathlib import Path

from keeper.app.service import KeeperApplication


def git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=root, check=True, capture_output=True, text=True
    ).stdout.strip()


def fake_provider(path: Path, envelope: bool) -> None:
    prefix = '{"result":' if envelope else ""
    suffix = "}" if envelope else ""
    script = f"""@echo off
if "%~1"=="--version" echo controlled-provider 1.0& exit /b 0
set schema=
if "{str(envelope).lower()}"=="true" set schema=%~2
if "{str(envelope).lower()}"=="false" (
  :args
  if "%~1"=="" goto output
  if "%~1"=="--output-schema" set schema=%~2& goto output
  shift
  goto args
)
:output
if not exist .keeper-workflow mkdir .keeper-workflow
if "%KEEPER_PROVIDER_ROLE%"=="post_repair_reviewer" (
  echo {prefix}{{"status":"completed","files_changed":[],"findings":[],"dispositions":[{{"finding_id":"FAKE-H-1","status":"resolved","justification":"controlled repair verified"}}]}}{suffix}
  exit /b 0
)
if "%KEEPER_PROVIDER_ROLE%"=="reviewer" (
  echo {prefix}{{"status":"completed","files_changed":[],"findings":[{{"finding_id":"FAKE-H-1","severity":"High","title":"controlled repair","description":"exercise repair"}}]}}{suffix}
  exit /b 0
)
if "%KEEPER_PROVIDER_ROLE%"=="repairer" (
  >.keeper-workflow\\result.txt echo repaired
  echo {prefix}{{"status":"completed","files_changed":[".keeper-workflow/result.txt"]}}{suffix}
  exit /b 0
)
>.keeper-workflow\\result.txt echo built
echo {prefix}{{"status":"completed","files_changed":[".keeper-workflow/result.txt"]}}{suffix}
"""
    path.write_text(script, encoding="ascii")


def test_controlled_command_adapters_complete_full_repair_workflow(
    tmp_path: Path,
) -> None:
    codex = tmp_path / "controlled-codex.cmd"
    claude = tmp_path / "controlled-claude.cmd"
    fake_provider(codex, False)
    fake_provider(claude, True)
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init")
    git(repo, "config", "user.email", "keeper@example.invalid")
    git(repo, "config", "user.name", "Keeper")
    (repo / "README.md").write_text("baseline\n", encoding="utf-8")
    git(repo, "add", "README.md")
    git(repo, "commit", "-m", "baseline")

    app = KeeperApplication(tmp_path / "data")
    app.save_provider_paths({"codex": str(codex), "claude": str(claude)})
    project = app.add_project(repo)
    task = app.create_task(
        {
            "title": "Controlled command workflow",
            "objective": "Exercise command adapters without credentials",
            "baseline": project["head"],
            "target_branch": "keeper/controlled",
            "included_paths": [".keeper-workflow/"],
            "provider_policy": "automatic",
        }
    )
    run = app.execute_task(str(task["id"]))
    assert run["status"] == "COMPLETED", run
    providers = {item["provider"] for item in run["routing_decisions"]}
    assert providers == {"codex-command", "claude-command"}
    assert "repair_execution" in [item["to"] for item in run["history"]]
    logs = list(Path(str(run["evidence_root"])).glob(".ai-workflow/runs/*/*"))
    assert any(path.name == "run.json" for path in logs)
