from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from keeper.app.git_safety import GitSafetyService
from keeper.app.lifecycle import RunLifecycle, RunStage
from keeper.app.notifications import deliver_local_notification
from keeper.app.reporting import finalize_evidence
from keeper.app.security import redact_text
from keeper.app.storage import KeeperStore, default_data_directory
from keeper.app.workflow import WorkflowCoordinator
from keeper.providers.adapters import ProviderDiscovery
from keeper.recovery import atomic_write_json, load_json
from keeper.version import VERSION


class KeeperApplication:
    def __init__(self, data_directory: Path | None = None) -> None:
        self.data_directory = (data_directory or default_data_directory()).resolve()
        self.store = KeeperStore(self.data_directory / "keeper.db")
        self.store.migrate()
        self.git = GitSafetyService()
        self.lifecycle = RunLifecycle(self.store)
        self.workflow = WorkflowCoordinator(self.store, self.data_directory, self.notify)

    def diagnostics(self) -> dict[str, Any]:
        providers = [item.to_dict() for item in ProviderDiscovery(self.provider_paths()).discover()]
        writable = _writable(self.data_directory)
        return {
            "keeper_version": VERSION,
            "python": sys.version.split()[0],
            "python_supported": sys.version_info >= (3, 12),
            "git": shutil.which("git"),
            "git_available": shutil.which("git") is not None,
            "data_directory": str(self.data_directory),
            "data_directory_writable": writable,
            "providers": providers,
            "local_only": True,
        }

    def setup_complete(self) -> bool:
        value = self.store.get("settings", "application")
        return bool(value and value.get("setup_complete"))

    def finish_setup(self, evidence_directory: Path | None = None) -> None:
        settings = self.store.get("settings", "application") or {}
        settings.update(
            {
                "setup_complete": True,
                "evidence_directory": str(
                    (evidence_directory or self.data_directory / "evidence").resolve()
                ),
                "theme": settings.get("theme", "dark"),
                "log_retention_days": settings.get("log_retention_days", 90),
                "default_timeout_seconds": settings.get("default_timeout_seconds", 1800),
            }
        )
        self.store.upsert("settings", "application", settings)

    def provider_paths(self) -> dict[str, str]:
        value = self.store.get("settings", "providers") or {}
        return {
            str(key): str(path)
            for key, path in value.items()
            if isinstance(key, str) and isinstance(path, str)
        }

    def save_provider_paths(self, paths: dict[str, str]) -> None:
        self.store.upsert("settings", "providers", paths)

    def add_project(self, repository: Path, name: str | None = None) -> dict[str, Any]:
        inspection = self.git.inspect(repository)
        identifier = uuid.uuid5(uuid.NAMESPACE_URL, inspection.root).hex
        project = {
            "id": identifier,
            "name": name or Path(inspection.root).name,
            "repository": inspection.root,
            "protected_original": True,
            "branch": inspection.branch,
            "head": inspection.head,
            "dirty": inspection.dirty,
            "detached": inspection.detached,
            "worktrees": inspection.worktrees,
            "added_at": _now(),
        }
        self.store.upsert("projects", identifier, project)
        self.store.upsert("settings", "active_project", {"project_id": identifier})
        return project

    def projects(self) -> list[dict[str, Any]]:
        return self.store.list("projects")

    def active_project(self) -> dict[str, Any] | None:
        setting = self.store.get("settings", "active_project")
        return (
            self.store.get("projects", str(setting["project_id"]))
            if setting and setting.get("project_id")
            else None
        )

    def create_task(self, values: dict[str, Any]) -> dict[str, Any]:
        required = ("title", "objective", "baseline", "target_branch")
        missing = [field for field in required if not str(values.get(field, "")).strip()]
        if missing:
            raise ValueError(f"task is missing required fields: {missing}")
        task_id = str(values.get("id") or f"task-{uuid.uuid4().hex[:12]}")
        active = self.active_project()
        repository = str(values.get("repository") or (active or {}).get("repository", ""))
        if not repository:
            raise ValueError("task requires an active repository")
        task: dict[str, Any] = {
            "id": task_id,
            "title": str(values["title"]),
            "objective": str(values["objective"]),
            "included_paths": list(values.get("included_paths", ["keeper/"])),
            "excluded_paths": list(values.get("excluded_paths", [])),
            "baseline": str(values["baseline"]),
            "target_branch": str(values["target_branch"]),
            "risk": str(values.get("risk", "low")),
            "allowed_actions": list(values.get("allowed_actions", [])),
            "prohibited_actions": list(values.get("prohibited_actions", [])),
            "required_validations": list(values.get("required_validations", [])),
            "verification_waivers": list(values.get("verification_waivers", [])),
            "required_reviewers": list(values.get("required_reviewers", ["independent"])),
            "completion_criteria": list(values.get("completion_criteria", [])),
            "delegation_mode": bool(values.get("delegation_mode", False)),
            "repository": str(Path(repository).resolve()),
            "provider_policy": str(values.get("provider_policy", "mock")),
            "mock_scenario": str(values.get("mock_scenario", "repair")),
            "requires_manual_approval": bool(
                values.get("requires_manual_approval", False)
            ),
            "commit_requested": bool(values.get("commit_requested", False)),
            "push_requested": bool(values.get("push_requested", False)),
            "commit_message": str(values.get("commit_message", values["title"])),
            "push_remote": str(values.get("push_remote", "origin")),
            "push_destination": str(values.get("push_destination", "")),
            "status": "INTAKE",
            "created_at": _now(),
        }
        self.store.upsert("tasks", task_id, task)
        for waiver in task["verification_waivers"]:
            if isinstance(waiver, dict) and waiver.get("waiver_id"):
                stored_waiver = {
                    **waiver,
                    "id": str(waiver["waiver_id"]),
                    "capability": "verification_waiver",
                    "task_id": task_id,
                    "run_id": waiver.get("run_id"),
                    "issued_at": str(waiver.get("issued_at") or _now()),
                    "consumed_at": waiver.get("consumed_at"),
                    "revoked_at": waiver.get("revoked_at"),
                }
                self.store.upsert(
                    "authorizations", str(waiver["waiver_id"]), stored_waiver
                )
        return task

    def tasks(self) -> list[dict[str, Any]]:
        return self.store.list("tasks")

    def pause_run(self, run_id: str) -> None:
        self.workflow.pause(run_id)

    def resume_run(self, run_id: str) -> None:
        self.workflow.resume(run_id)

    def cancel_run(self, run_id: str) -> None:
        self.workflow.cancel(run_id)

    def approve_run(self, run_id: str, authority: str) -> None:
        self.workflow.approve(run_id, authority)

    def reject_run(self, run_id: str, authority: str, reason: str) -> None:
        self.workflow.reject(run_id, authority, reason)

    def run_status(self, run_id: str) -> dict[str, Any]:
        run = self.store.get("runs", run_id)
        if run is None:
            raise LookupError("run not found")
        evidence = run.get("evidence_root")
        latest = ""
        if isinstance(evidence, str):
            logs = sorted(Path(evidence).glob(".ai-workflow/runs/*/*.log"))
            if logs:
                try:
                    latest = redact_text(logs[-1].read_text(encoding="utf-8"), 20_000)
                except OSError:
                    latest = ""
        verification = [
            item
            for item in self.store.list("verification_records")
            if item.get("run_id") == run_id
        ]
        waivers = [
            item
            for item in self.store.list("authorizations")
            if item.get("capability") == "verification_waiver"
            and item.get("run_id") in {None, run_id}
            and item.get("task_id") == run.get("task_id")
        ]
        return {
            **run,
            "latest_log": latest,
            "verification_records": verification,
            "verification_waivers": waivers,
        }

    def evidence_details(self, run_id: str, category: str) -> dict[str, Any]:
        run = self.run_status(run_id)
        root_value = run.get("evidence_root")
        if not isinstance(root_value, str):
            raise ValueError("run has no evidence root")
        root = Path(root_value).resolve()
        allowed = (self.data_directory / "evidence").resolve()
        if not root.is_relative_to(allowed):
            raise PermissionError("evidence path is outside Keeper storage")
        provider_records: list[dict[str, Any]] = []
        for path in sorted(root.glob(".ai-workflow/runs/*/run.json")):
            resolved = path.resolve()
            if not resolved.is_relative_to(root):
                raise PermissionError("provider evidence escapes the run root")
            try:
                value = json.loads(resolved.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if isinstance(value, dict):
                provider_records.append(value)
        authorizations = [
            item
            for item in self.store.list("authorizations")
            if item.get("task_id") == run.get("task_id")
            and item.get("run_id") in {None, run_id}
        ]
        findings = [
            {
                "provider_run_id": item.get("run_id"),
                "role": item.get("role"),
                "findings": item.get("review_findings", []),
                "accepted": item.get("accepted_findings", []),
                "rejected": item.get("rejected_findings", []),
            }
            for item in provider_records
            if item.get("review_findings")
            or item.get("accepted_findings")
            or item.get("rejected_findings")
        ]
        logs: list[dict[str, Any]] = []
        for path in sorted(root.glob(".ai-workflow/runs/*/*.log")):
            resolved = path.resolve()
            if not resolved.is_relative_to(root):
                raise PermissionError("log evidence escapes the run root")
            content = resolved.read_bytes()
            logs.append(
                {
                    "path": resolved.relative_to(root).as_posix(),
                    "size": len(content),
                    "sha256": hashlib.sha256(content).hexdigest(),
                    "recent_output": redact_text(
                        content.decode("utf-8", errors="replace"), 20_000
                    ),
                }
            )
        index_path = root / "evidence-index.json"
        hashes: list[dict[str, Any]] = []
        if index_path.is_file():
            index = json.loads(index_path.read_text(encoding="utf-8"))
            if isinstance(index, dict) and isinstance(index.get("files"), list):
                hashes = [
                    item for item in index["files"] if isinstance(item, dict)
                ]
        categories: dict[str, Any] = {
            "routing": {
                "routing_rationale": run.get("routing_decisions", []),
                "provider_identities": run.get("providers", {}),
            },
            "verification": {
                "categories": run.get("verification_records", []),
                "commands": [
                    item
                    for item in provider_records
                    if item.get("verification_result") is not None
                ],
            },
            "waivers": run.get("verification_waivers", []),
            "authorizations": authorizations,
            "findings": findings,
            "logs": logs,
            "hashes": hashes,
            "git": run.get("git_result", {}),
        }
        if category not in categories:
            raise ValueError("unsupported evidence detail category")
        return {
            "run_id": run_id,
            "category": category,
            "details": categories[category],
        }

    def revoke_waiver(self, authorization_id: str) -> None:
        value = self.store.get("authorizations", authorization_id)
        if value is None or value.get("capability") != "verification_waiver":
            raise LookupError("verification waiver not found")
        if value.get("revoked_at") is not None or value.get("consumed_at") is not None:
            raise PermissionError("only an active waiver may be revoked")
        try:
            expires_at = datetime.fromisoformat(str(value["expires_at"]))
        except (KeyError, TypeError, ValueError) as error:
            raise PermissionError("waiver expiration is invalid") from error
        if expires_at.tzinfo is None or expires_at <= datetime.now(UTC):
            raise PermissionError("only an active waiver may be revoked")
        self.revoke_authorization(authorization_id)
        revoked = self.store.get("authorizations", authorization_id)
        if revoked is None:
            raise RuntimeError("revoked waiver could not be reloaded")
        task_id = str(revoked.get("task_id", ""))
        task = self.store.get("tasks", task_id)
        if task is not None:
            task["verification_waivers"] = [
                (
                    {**item, "revoked_at": revoked["revoked_at"]}
                    if isinstance(item, dict)
                    and item.get("waiver_id") == authorization_id
                    else item
                )
                for item in task.get("verification_waivers", [])
            ]
            self.store.upsert("tasks", task_id, task)
        for run in self.store.list("runs"):
            if run.get("task_id") != task_id or run.get("status") in {
                "COMPLETED",
                "REJECTED",
            }:
                continue
            evidence = run.get("evidence_root")
            if not isinstance(evidence, str):
                continue
            task_path = Path(evidence) / ".ai-workflow" / "tasks" / f"{task_id}.json"
            if not task_path.is_file():
                continue
            domain_task = load_json(task_path, {})
            if not isinstance(domain_task, dict):
                continue
            domain_task["verification_waivers"] = [
                (
                    {**item, "revoked_at": revoked["revoked_at"]}
                    if isinstance(item, dict)
                    and item.get("waiver_id") == authorization_id
                    else item
                )
                for item in domain_task.get("verification_waivers", [])
            ]
            atomic_write_json(task_path, domain_task)

    def start_task(self, task_id: str) -> dict[str, Any]:
        return self.workflow.start(task_id)

    def execute_task(self, task_id: str) -> dict[str, Any]:
        return self.workflow.execute(task_id)

    def wait_for_run(self, run_id: str, timeout: float | None = None) -> dict[str, Any]:
        self.workflow.wait(run_id, timeout)
        run = self.store.get("runs", run_id)
        if run is None:
            raise LookupError("run not found")
        return run

    def recover_runs(self) -> list[dict[str, Any]]:
        return self.workflow.recover_interrupted_runs()

    def retry_run(
        self,
        run_id: str,
        reason: str,
        stage: str | None = None,
        authorizer: str = "local-user",
    ) -> dict[str, Any]:
        return self.workflow.retry(run_id, reason, stage, authorizer)

    def filtered_runs(
        self,
        *,
        repository: str = "",
        branch: str = "",
        provider: str = "",
        outcome: str = "",
        task_id: str = "",
        date_from: str = "",
        date_to: str = "",
    ) -> list[dict[str, Any]]:
        values = self.store.list("runs")
        filters = {
            "repository": repository,
            "branch": branch,
            "provider": provider,
            "status": outcome,
            "task_id": task_id,
        }
        return [
            item
            for item in values
            if all(
                not expected or str(item.get(key, "")) == expected
                for key, expected in filters.items()
            )
            and (not date_from or str(item.get("started_at", "")) >= date_from)
            and (not date_to or str(item.get("started_at", "")) <= date_to)
        ]

    def evidence_path(self, run_id: str, kind: str = "folder") -> Path:
        run = self.store.get("runs", run_id)
        if run is None:
            raise LookupError("run not found")
        root_value = run.get("evidence_root")
        if not isinstance(root_value, str):
            raise ValueError("run has no finalized evidence")
        root = Path(root_value).resolve()
        allowed_root = (self.data_directory / "evidence").resolve()
        if not root.is_relative_to(allowed_root):
            raise PermissionError("evidence path is outside Keeper storage")
        choices = {
            "folder": root,
            "markdown": root / "final-report.md",
            "json": root / "final-report.json",
        }
        if kind not in choices or not choices[kind].exists():
            raise ValueError("requested evidence target is unavailable")
        return choices[kind]

    def open_evidence(self, run_id: str, kind: str = "folder") -> Path:
        target = self.evidence_path(run_id, kind)
        subprocess.Popen(
            ["explorer.exe", str(target)],
            cwd=self.data_directory,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return target

    def save_template(self, name: str, task: dict[str, Any]) -> None:
        self.store.upsert("policies", f"template:{name}", {"name": name, "task": task})

    def create_authorization(
        self,
        capability: str,
        task_id: str,
        repository: str,
        approving_authority: str,
        minutes: int,
        reusable: bool = False,
        scope: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if minutes < 1 or minutes > 1440:
            raise ValueError("authorization duration must be between 1 and 1440 minutes")
        identifier = f"authorization-{uuid.uuid4().hex}"
        authorization = {
            "id": identifier,
            "capability": capability,
            "task_id": task_id,
            "repository": str(Path(repository).resolve()),
            "approving_authority": approving_authority,
            "issued_at": _now(),
            "expires_at": (datetime.now(UTC) + timedelta(minutes=minutes)).isoformat(),
            "reusable": reusable,
            "consumed_at": None,
            "revoked_at": None,
            **(scope or {}),
        }
        self.store.upsert("authorizations", identifier, authorization)
        return authorization

    def revoke_authorization(self, identifier: str) -> None:
        value = self.store.get("authorizations", identifier)
        if value is None:
            raise LookupError("authorization not found")
        value["revoked_at"] = _now()
        self.store.upsert("authorizations", identifier, value)

    def run_mock_demo(self) -> dict[str, Any]:
        repository = self._demo_repository()
        project = self.add_project(repository, "Keeper demonstration")
        task = self.create_task(
            {
                "title": "Keeper deterministic demonstration",
                "objective": "Exercise the unified production orchestration path.",
                "baseline": project["head"],
                "target_branch": "keeper/demo",
                "included_paths": [".keeper-workflow/"],
                "required_validations": ["task"],
                "mock_scenario": "repair",
            }
        )
        return self.execute_task(str(task["id"]))

    def notify(self, event: str, title: str, detail: str) -> dict[str, Any]:
        identifier = f"notification-{uuid.uuid4().hex}"
        value: dict[str, Any] = {
            "id": identifier,
            "event": event,
            "title": redact_text(title, 120),
            "detail": redact_text(detail, 1000),
            "created_at": _now(),
            "read_at": None,
        }
        self.store.upsert("notifications", identifier, value)
        settings = self.store.get("settings", "application") or {}
        if bool(settings.get("os_notifications", False)):
            delivery = deliver_local_notification(event, value["title"], value["detail"])
            value["delivery"] = {
                "delivered": delivery.delivered,
                "channel": delivery.channel,
                "detail": delivery.detail,
            }
            self.store.upsert("notifications", identifier, value)
        return value

    def dashboard(self) -> dict[str, Any]:
        runs = self.store.list("runs")
        findings = self.store.list("findings")
        authorizations = self.store.list("authorizations")
        return {
            "status": "ready" if self.setup_complete() else "setup required",
            "active_project": self.active_project(),
            "running_workflow": next(
                (run for run in runs if run.get("status") == "running"), None
            ),
            "recent_runs": runs[:10],
            "pending_approvals": [
                item for item in authorizations
                if item.get("consumed_at") is None and item.get("revoked_at") is None
            ],
            "unresolved_findings": [
                item for item in findings if item.get("status", "open") == "open"
            ],
            "providers": self.diagnostics()["providers"],
        }

    def export_run_report(self, run_id: str, destination: Path) -> Path:
        run = self.store.get("runs", run_id)
        if run is None:
            raise LookupError("run not found")
        report = {
            "objective": run.get("objective"),
            "repository": run.get("repository"),
            "worktree": run.get("workspace"),
            "branch": run.get("branch"),
            "baseline": run.get("baseline"),
            "scope": run.get("scope"),
            "providers": run.get("providers"),
            "routing_decisions": run.get("routing_decisions"),
            "authorizations": run.get("authorizations"),
            "commands": run.get("commands"),
            "findings": run.get("findings"),
            "repairs": run.get("repairs"),
            "verification_results": run.get("verification_results"),
            "test_totals": run.get("test_totals"),
            "approval_result": run.get("approval_result"),
            "git_result": run.get("git_result"),
            "unresolved_observations": run.get("unresolved_observations"),
            "evidence_paths": run.get("evidence_root"),
            "start_time": run.get("start_time"),
            "end_time": run.get("end_time"),
            "terminal_status": run.get("status"),
        }
        finalize_evidence(destination, report)
        return destination

    def _demo_repository(self) -> Path:
        root = self.data_directory / "demonstrations" / f"demo-{uuid.uuid4().hex}"
        repository = root / "repository"
        repository.mkdir(parents=True)
        commands = (
            ("init",),
            ("config", "user.email", "keeper@example.invalid"),
            ("config", "user.name", "Keeper Demonstration"),
        )
        for command in commands:
            _git(repository, *command)
        (repository / "README.md").write_text(
            "Keeper demonstration\n", encoding="utf-8"
        )
        _git(repository, "add", "README.md")
        _git(repository, "commit", "-m", "demonstration baseline")
        return repository


def _writable(directory: Path) -> bool:
    try:
        directory.mkdir(parents=True, exist_ok=True)
        probe = directory / f".write-probe-{uuid.uuid4().hex}"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        return True
    except OSError:
        return False


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _git(repository: Path, *arguments: str) -> None:
    result = subprocess.run(
        ["git", *arguments],
        cwd=repository,
        capture_output=True,
        text=True,
        shell=False,
        timeout=30,
        check=False,
    )
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or "unable to prepare demonstration")
