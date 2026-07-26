from __future__ import annotations

import json
import threading
import time
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable

from keeper.agent_runner import AgentRunner
from keeper.app.lifecycle import RunLifecycle, RunStage
from keeper.app.git_safety import GitSafetyService
from keeper.app.reporting import finalize_evidence
from keeper.app.storage import KeeperStore
from keeper.config import KeeperConfig
from keeper.models.task import Task
from keeper.orchestrator import Keeper
from keeper.providers.mock import MockProvider
from keeper.providers.base import AgentProvider
from keeper.providers.routing import ProviderRouter
from keeper.providers.adapters import (
    ClaudeCommandAdapter,
    CodexCommandAdapter,
    ProviderDiagnostic,
    ProviderDiscovery,
    RoutingRequest,
    route_provider,
)
from keeper.providers.ollama import OllamaProvider
from keeper.workspace import WorkspaceManager
from keeper.recovery import process_exists


@dataclass(slots=True)
class ActiveRun:
    thread: threading.Thread
    cancel_requested: threading.Event
    pause_requested: threading.Event
    approval_ready: threading.Event
    approval_decision: str | None = None


class WorkflowCoordinator:
    """Connect persisted desktop tasks to the production Keeper orchestrator."""

    def __init__(
        self,
        store: KeeperStore,
        data_directory: Path,
        notify: Callable[[str, str, str], dict[str, Any]],
    ) -> None:
        self.store = store
        self.data_directory = data_directory
        self.lifecycle = RunLifecycle(store)
        self.notify = notify
        self._active: dict[str, ActiveRun] = {}
        self._lock = threading.Lock()
        self.recover_interrupted_runs()

    def start(self, task_id: str) -> dict[str, Any]:
        task = self._task(task_id)
        run_id = f"run-{uuid.uuid4().hex}"
        run = self.lifecycle.create(run_id, task_id)
        run.update(
            {
                "repository": task["repository"],
                "branch": task["target_branch"],
                "baseline": task["baseline"],
                "objective": task["objective"],
                "started_at": _now(),
                "provider": None,
                "latest_log": None,
                "evidence_root": str(self.data_directory / "evidence" / run_id),
                "attempt": 1,
            }
        )
        self.store.upsert("runs", run_id, run)
        cancel = threading.Event()
        pause = threading.Event()
        approval = threading.Event()
        thread = threading.Thread(
            target=self._execute_guarded,
            args=(run_id, task, cancel, pause, approval),
            name=f"keeper-{run_id}",
            daemon=True,
        )
        with self._lock:
            self._active[run_id] = ActiveRun(thread, cancel, pause, approval)
        thread.start()
        return self._run(run_id)

    def recover_interrupted_runs(self) -> list[dict[str, Any]]:
        recovered: list[dict[str, Any]] = []
        terminal = {"COMPLETED", "REJECTED", "blocked", "cancelled"}
        for record in self.store.list("runs"):
            if record.get("status") in terminal:
                continue
            run_id = str(record.get("id", ""))
            if not run_id:
                continue
            stage = str(record.get("stage", ""))
            pid = record.get("process_id")
            running = isinstance(pid, int) and process_exists(pid)
            if stage != RunStage.INTERRUPTED.value:
                try:
                    self.lifecycle.transition(run_id, RunStage.INTERRUPTED)
                except (RuntimeError, ValueError):
                    continue
            current = self._run(run_id)
            current.update(
                {
                    "status": "interrupted",
                    "recovery": {
                        "classification": "uncertain" if running else "recoverable",
                        "previous_process_running": running,
                        "retry_safe": stage
                        not in {
                            RunStage.AUTHORIZED_COMMIT.value,
                            RunStage.AUTHORIZED_PUSH.value,
                            RunStage.EVIDENCE_FINALIZATION.value,
                        },
                        "detected_at": _now(),
                    },
                }
            )
            self.store.upsert("runs", run_id, current)
            recovered.append(current)
        return recovered

    def retry(self, run_id: str, reason: str) -> dict[str, Any]:
        if not reason.strip():
            raise ValueError("retry reason is required")
        previous = self._run(run_id)
        recovery = previous.get("recovery")
        if (
            previous.get("status") not in {"blocked", "interrupted"}
            or not isinstance(recovery, dict)
            or not recovery.get("retry_safe")
        ):
            raise PermissionError("run is not eligible for persisted retry")
        if recovery.get("previous_process_running"):
            raise PermissionError("uncertain running provider must be resolved before retry")
        retried = self.start(str(previous["task_id"]))
        current = self._run(str(retried["id"]))
        current.update(
            {
                "retry_of": run_id,
                "attempt": int(previous.get("attempt", 1)) + 1,
                "retry_reason": reason,
            }
        )
        self.store.upsert("runs", str(current["id"]), current)
        previous["superseded_by"] = current["id"]
        previous["retry_history"] = [
            *list(previous.get("retry_history", [])),
            {"run_id": current["id"], "reason": reason, "timestamp": _now()},
        ]
        self.store.upsert("runs", run_id, previous)
        return current

    def execute(self, task_id: str) -> dict[str, Any]:
        run = self.start(task_id)
        self.wait(str(run["id"]), timeout=120)
        return self._run(str(run["id"]))

    def wait(self, run_id: str, timeout: float | None = None) -> None:
        with self._lock:
            active = self._active.get(run_id)
        if active is not None:
            active.thread.join(timeout)

    def cancel(self, run_id: str) -> None:
        with self._lock:
            active = self._active.get(run_id)
        if active is None or not active.thread.is_alive():
            raise ValueError("run is not active")
        active.cancel_requested.set()
        active.approval_ready.set()
        self.lifecycle.transition(run_id, RunStage.CANCELLED)
        self.notify("run_cancelled", "Run cancelled", f"Run {run_id}")

    def pause(self, run_id: str) -> None:
        active = self._active_run(run_id)
        if not active.pause_requested.is_set():
            active.pause_requested.set()
            self.lifecycle.transition(run_id, RunStage.INTERRUPTED)
            self.notify("workflow_blocked", "Workflow paused", f"Run {run_id}")

    def resume(self, run_id: str) -> None:
        active = self._active_run(run_id)
        record = self._run(run_id)
        interrupted = record.get("interrupted_from")
        if not interrupted:
            raise ValueError("run is not paused")
        self.lifecycle.transition(run_id, RunStage(str(interrupted)))
        active.pause_requested.clear()

    def approve(self, run_id: str, authority: str) -> None:
        self._decide(run_id, authority, "approved", "")

    def reject(self, run_id: str, authority: str, reason: str) -> None:
        self._decide(run_id, authority, "rejected", reason)

    def _decide(
        self, run_id: str, authority: str, decision: str, reason: str
    ) -> None:
        if not authority.strip() or (decision == "rejected" and not reason.strip()):
            raise ValueError("approval identity and rejection reason are required")
        active = self._active_run(run_id)
        record = self._run(run_id)
        if record.get("stage") != RunStage.APPROVAL_DECISION.value:
            raise ValueError("run is not awaiting approval")
        active.approval_decision = decision
        record["approval"] = {
            "decision": decision,
            "approving_authority": authority,
            "reason": reason,
            "timestamp": _now(),
        }
        self.store.upsert("runs", run_id, record)
        active.approval_ready.set()

    def _execute_guarded(
        self,
        run_id: str,
        task: dict[str, Any],
        cancel: threading.Event,
        pause: threading.Event,
        approval: threading.Event,
    ) -> None:
        try:
            self._execute(run_id, task, cancel, pause, approval)
        except Exception as error:
            record = self._run(run_id)
            if record.get("stage") not in {
                RunStage.CANCELLED.value,
                RunStage.BLOCKED.value,
            }:
                self.lifecycle.transition(run_id, RunStage.BLOCKED)
            record = self._run(run_id)
            record["failure_reason"] = str(error)
            record["ended_at"] = _now()
            self.store.upsert("runs", run_id, record)
            self.notify("provider_failure", "Workflow blocked", f"Run {run_id}")
        finally:
            with self._lock:
                self._active.pop(run_id, None)

    def _execute(
        self,
        run_id: str,
        stored: dict[str, Any],
        cancel: threading.Event,
        pause: threading.Event,
        approval: threading.Event,
    ) -> None:
        repository = Path(str(stored["repository"])).resolve()
        self._advance(run_id, RunStage.SCOPE_VALIDATION)
        _validate_task_scope(stored, repository)
        self._advance(run_id, RunStage.RISK_CLASSIFICATION)
        self._advance(run_id, RunStage.AUTHORIZATION_RESOLUTION)
        self._advance(run_id, RunStage.PROVIDER_SELECTION)
        providers, routes, routing = _select_routes(
            stored,
            self.store.get("settings", "providers") or {},
        )
        record = self._run(run_id)
        record["providers"] = {
            role: {
                "provider_name": provider.provider_name,
                "provider_instance_id": provider.instance_id,
            }
            for role, provider in providers.items()
        }
        record["routing_decisions"] = routing
        self.store.upsert("runs", run_id, record)
        if cancel.is_set():
            return
        self._advance(run_id, RunStage.WORKTREE_PREPARATION)
        evidence = self.data_directory / "evidence" / run_id
        evidence.mkdir(parents=True, exist_ok=True)
        state = evidence / ".ai-workflow"
        config = KeeperConfig(
            repository,
            state,
            self.data_directory / "worktrees" / run_id,
            (),
            provider_routes=tuple(routes.items()),
            process_timeout_seconds=int(stored.get("timeout_seconds", 30)),
        )
        domain_task = _domain_task(stored, run_id)
        routed_providers: dict[str, AgentProvider] = dict(providers)
        router = ProviderRouter(routed_providers, routes)
        observer = _LifecycleObserver(
            self.lifecycle, run_id, cancel, pause, self.notify
        )
        engine = Keeper(
            config,
            AgentRunner(providers["builder"], state / "runs", 30),
            WorkspaceManager(repository, config.workspace_root, state / "ownership"),
            router,
            observer,
        )
        result = engine.run_task(domain_task)
        if cancel.is_set():
            return
        if result.status.value != "COMPLETED":
            self.lifecycle.transition(run_id, RunStage.BLOCKED)
            self.notify("workflow_blocked", "Workflow blocked", f"Run {run_id}")
            return
        observer.finish_validation()
        workspace_path = Path(str(result.workspace_path)).resolve()
        git = GitSafetyService()
        changed_paths = engine.workspace_manager.changed_files(workspace_path)
        record = self._run(run_id)
        record.update(
            {
                "worktree": str(workspace_path),
                "worktree_branch": result.branch_name,
                "worktree_head": git.inspect(workspace_path).head,
                "changed_paths": changed_paths,
            }
        )
        self.store.upsert("runs", run_id, record)
        if bool(stored.get("commit_requested", False)):
            git.stage_allowlisted(
                workspace_path,
                changed_paths,
                [".keeper-workflow/"],
                [],
            )
            record = self._run(run_id)
            record["staged_paths"] = git.inspect(workspace_path).staged
            self.store.upsert("runs", run_id, record)
        semantic_records = self._persist_semantic_evidence(
            run_id, str(stored["id"]), state
        )
        if bool(stored.get("requires_manual_approval", False)):
            record = self._run(run_id)
            record["status"] = "awaiting_approval"
            self.store.upsert("runs", run_id, record)
            self.notify("authorization_required", "Approval required", f"Run {run_id}")
            while not approval.wait(0.1):
                if cancel.is_set():
                    return
            if cancel.is_set():
                return
            active = self._active_run(run_id)
            if active.approval_decision != "approved":
                self.lifecycle.transition(run_id, RunStage.BLOCKED)
                record = self._run(run_id)
                record.update(
                    {"status": "REJECTED", "outcome": "rejected", "ended_at": _now()}
                )
                self.store.upsert("runs", run_id, record)
                self.notify("run_rejected", "Run rejected", f"Run {run_id}")
                return
            self.notify("run_approved", "Run approved", f"Run {run_id}")
        git_result: dict[str, Any] = {}
        if bool(stored.get("commit_requested", False)):
            self.lifecycle.transition(run_id, RunStage.AUTHORIZED_COMMIT)
            authorization = self._authorization("commit", run_id, str(stored["id"]))
            git.commit(
                repository,
                str(stored.get("commit_message", stored["title"])),
                authorization,
                task_id=str(stored["id"]),
                run_id=run_id,
                worktree=workspace_path,
                branch=str(result.branch_name),
            )
            self.store.upsert(
                "authorizations", str(authorization["id"]), authorization
            )
            commit_hash = git.inspect(workspace_path).head
            git_result["commit_hash"] = commit_hash
            if bool(stored.get("push_requested", False)):
                record = self._run(run_id)
                record.update(
                    {
                        "status": "awaiting_push_authorization",
                        "commit_hash": commit_hash,
                    }
                )
                self.store.upsert("runs", run_id, record)
                authorization = self._wait_for_authorization(
                    "push", run_id, str(stored["id"]), cancel
                )
                self.lifecycle.transition(run_id, RunStage.AUTHORIZED_PUSH)
                remote = str(stored.get("push_remote", "origin"))
                source = str(result.branch_name)
                destination = str(
                    stored.get("push_destination") or f"refs/heads/{source}"
                )
                push_result = git.push(
                    repository,
                    remote,
                    source,
                    destination,
                    authorization,
                    task_id=str(stored["id"]),
                    run_id=run_id,
                    worktree=workspace_path,
                )
                self.store.upsert(
                    "authorizations", str(authorization["id"]), authorization
                )
                git_result.update(
                    {"push_result": push_result, "remote_hash": commit_hash}
                )
        report = {
            **self._run(run_id),
            "task": stored,
            "orchestrator_task": result.to_dict(),
            "terminal_status": "COMPLETED",
            "end_time": _now(),
            "evidence_paths": str(evidence),
            "verification_records": semantic_records,
            "verification_waivers": [
                item
                for item in self.store.list("authorizations")
                if item.get("capability") == "verification_waiver"
                and item.get("task_id") == stored["id"]
                and item.get("run_id") in {None, run_id}
            ],
            "git_result": git_result,
        }
        finalize_evidence(evidence, report)
        self._advance(run_id, RunStage.EVIDENCE_FINALIZATION)
        self._advance(run_id, RunStage.CLOSED)
        record = self._run(run_id)
        record.update(
            {
                "status": "COMPLETED",
                "outcome": "approved",
                "ended_at": _now(),
                "evidence_root": str(evidence),
                "report_markdown": str(evidence / "final-report.md"),
                "report_json": str(evidence / "final-report.json"),
                "git_result": git_result,
            }
        )
        self.store.upsert("runs", run_id, record)
        self.notify("run_completed", "Run completed", f"Run {run_id}")

    def _persist_semantic_evidence(
        self, run_id: str, task_id: str, state: Path
    ) -> list[dict[str, Any]]:
        persisted: list[dict[str, Any]] = []
        for path in sorted(state.glob("runs/*/run.json")):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            verification = payload.get("verification_result")
            if not isinstance(verification, dict):
                continue
            commands = verification.get("semantic_commands", [])
            if not isinstance(commands, list):
                continue
            for item in commands:
                if not isinstance(item, dict) or not item.get("command_id"):
                    continue
                record = {
                    **item,
                    "run_id": run_id,
                    "task_id": task_id,
                    "provider_run_id": payload.get("run_id"),
                    "stage": verification.get("stage"),
                }
                identifier = str(item["command_id"])
                self.store.upsert("verification_records", identifier, record)
                self.store.upsert("commands", identifier, record)
                persisted.append(record)
        return persisted

    def _authorization(
        self, capability: str, run_id: str, task_id: str
    ) -> dict[str, Any]:
        matches = [
            item
            for item in self.store.list("authorizations")
            if item.get("capability") == capability
            and item.get("run_id") == run_id
            and item.get("task_id") == task_id
            and item.get("consumed_at") is None
            and item.get("revoked_at") is None
        ]
        if len(matches) != 1:
            raise PermissionError(
                f"exactly one scoped {capability} authorization is required"
            )
        return matches[0]

    def _wait_for_authorization(
        self,
        capability: str,
        run_id: str,
        task_id: str,
        cancel: threading.Event,
    ) -> dict[str, Any]:
        deadline = time.monotonic() + 60
        self.notify(
            "authorization_required",
            f"{capability.title()} authorization required",
            f"Run {run_id}",
        )
        while time.monotonic() < deadline:
            if cancel.is_set():
                raise RuntimeError("run cancellation requested")
            try:
                return self._authorization(capability, run_id, task_id)
            except PermissionError:
                time.sleep(0.1)
        raise PermissionError(f"{capability} authorization was not provided")

    def _advance(self, run_id: str, stage: RunStage) -> None:
        self.lifecycle.transition(run_id, stage)

    def _task(self, task_id: str) -> dict[str, Any]:
        task = self.store.get("tasks", task_id)
        if task is None:
            raise LookupError("task not found")
        return task

    def _run(self, run_id: str) -> dict[str, Any]:
        run = self.store.get("runs", run_id)
        if run is None:
            raise LookupError("run not found")
        return run

    def _active_run(self, run_id: str) -> ActiveRun:
        with self._lock:
            active = self._active.get(run_id)
        if active is None:
            raise ValueError("run is not active")
        return active


class _LifecycleObserver:
    def __init__(
        self,
        lifecycle: RunLifecycle,
        run_id: str,
        cancel: threading.Event,
        pause: threading.Event,
        notify: Callable[[str, str, str], dict[str, Any]],
    ) -> None:
        self.lifecycle = lifecycle
        self.run_id = run_id
        self.cancel = cancel
        self.pause = pause
        self.notify = notify

    def __call__(self, value: str) -> None:
        if self.cancel.is_set():
            raise RuntimeError("run cancellation requested")
        while self.pause.is_set():
            if self.cancel.is_set():
                raise RuntimeError("run cancellation requested")
            time.sleep(0.05)
        mapping = {
            "BUILDING": RunStage.AUTHOR_EXECUTION,
            "SELF_VERIFYING": RunStage.AUTHOR_SELF_VERIFICATION,
            "INDEPENDENT_AUDIT": RunStage.INDEPENDENT_AUDIT,
            "REPAIRING": RunStage.REPAIR_EXECUTION,
            "POST_REPAIR_REVIEWING": RunStage.POST_REPAIR_VERIFICATION,
            "FINAL_VERIFY": RunStage.FINAL_VALIDATION,
        }
        target = mapping.get(value)
        if target is None:
            return
        if target == RunStage.REPAIR_EXECUTION:
            self.notify(
                "blocking_finding", "Critical/High finding", f"Run {self.run_id}"
            )
        if target == RunStage.POST_REPAIR_VERIFICATION:
            self.notify("repair_completed", "Repair completed", f"Run {self.run_id}")
        current = RunStage(str(self.lifecycle.store.get("runs", self.run_id)["stage"]))  # type: ignore[index]
        if target == RunStage.FINAL_VALIDATION and current == RunStage.POST_REPAIR_VERIFICATION:
            self.lifecycle.transition(self.run_id, RunStage.INDEPENDENT_AUDIT)
        self.lifecycle.transition(self.run_id, target)

    def finish_validation(self) -> None:
        record = self.lifecycle.store.get("runs", self.run_id)
        if record is None:
            raise LookupError("run not found")
        current = RunStage(str(record["stage"]))
        if current != RunStage.FINAL_VALIDATION:
            raise RuntimeError("orchestrator completed without final validation")
        self.lifecycle.transition(self.run_id, RunStage.APPROVAL_DECISION)


def _validate_task_scope(task: dict[str, Any], repository: Path) -> None:
    if not (repository / ".git").exists():
        # Worktrees use a .git file.
        if not (repository / ".git").is_file():
            raise ValueError("task repository is not a Git repository")
    included = task.get("included_paths")
    if not isinstance(included, list) or not included:
        raise ValueError("task requires included paths")
    if any(".." in Path(str(value)).parts for value in included):
        raise PermissionError("task scope contains traversal")


def _domain_task(stored: dict[str, Any], run_id: str) -> Task:
    scenario = str(stored.get("mock_scenario", "repair"))
    final = "repaired\n" if scenario == "repair" else "built\n"
    return Task(
        str(stored["id"]),
        str(stored["title"]),
        str(stored["objective"]),
        "desktop",
        1,
        risk=str(stored.get("risk", "low")),
        verification_commands=[
            ["keeper:file-equals", ".keeper-workflow/result.txt", "built\n"]
        ],
        final_verification_commands=[
            ["keeper:file-equals", ".keeper-workflow/result.txt", final]
        ],
        verification_specs=[
            {
                "category": "task",
                "arguments": ["keeper:file-equals", ".keeper-workflow/result.txt", "built\n"],
                "validator": "file-equals",
                "required": True,
            }
        ],
        final_verification_specs=[
            {
                "category": "task",
                "arguments": ["keeper:file-equals", ".keeper-workflow/result.txt", final],
                "validator": "file-equals",
                "required": True,
            }
        ],
        allowed_paths=[".keeper-workflow/"],
        capabilities=["repository_write", "run_verification"],
        provider="mock",
    )


def _select_routes(
    stored: dict[str, Any], configured_paths: dict[str, Any]
) -> tuple[dict[str, AgentProvider], dict[str, str], list[dict[str, Any]]]:
    policy = str(stored.get("provider_policy", "mock"))
    if policy == "mock":
        return _mock_routes(str(stored.get("mock_scenario", "repair")))
    diagnostics = ProviderDiscovery(
        {str(key): str(value) for key, value in configured_paths.items()}
    ).discover()
    if policy not in {"automatic", "strongest"}:
        diagnostics = [
            item for item in diagnostics if item.provider_id in {policy, "mock"}
        ]
    author = route_provider(
        RoutingRequest("builder", str(stored.get("risk", "low")), "keeper"),
        diagnostics,
    )
    reviewer = route_provider(
        RoutingRequest(
            "reviewer",
            str(stored.get("risk", "low")),
            "keeper",
            frozenset({author.provider_id}),
            author.provider_id == "ollama",
        ),
        diagnostics,
    )
    repairer = route_provider(
        RoutingRequest("repairer", str(stored.get("risk", "low")), "keeper"),
        diagnostics,
    )
    selected = {author.provider_id, reviewer.provider_id, repairer.provider_id}
    instances = {
        provider_id: _adapter(
            next(item for item in diagnostics if item.provider_id == provider_id)
        )
        for provider_id in selected
    }
    providers: dict[str, AgentProvider] = {
        "builder": instances[author.provider_id],
        "reviewer": instances[reviewer.provider_id],
        "repairer": instances[repairer.provider_id],
        "post-reviewer": instances[reviewer.provider_id],
    }
    routes = {
        "builder": "builder",
        "reviewer": "reviewer",
        "repairer": "repairer",
        "post_repair_reviewer": "post-reviewer",
    }
    decisions = [
        {
            "role": role,
            "provider": providers[target].provider_name,
            "provider_instance_id": providers[target].instance_id,
            "reasons": (
                author.reasons
                if role == "builder"
                else reviewer.reasons
                if role in {"reviewer", "post_repair_reviewer"}
                else repairer.reasons
            ),
            "policy": policy,
        }
        for role, target in routes.items()
    ]
    return providers, routes, decisions


def _adapter(diagnostic: ProviderDiagnostic) -> AgentProvider:
    if diagnostic.provider_id == "codex" and diagnostic.executable:
        return CodexCommandAdapter(diagnostic.executable)
    if diagnostic.provider_id == "claude" and diagnostic.executable:
        return ClaudeCommandAdapter(diagnostic.executable)
    if diagnostic.provider_id == "ollama":
        return OllamaProvider()
    if diagnostic.provider_id == "mock":
        return MockProvider(provider_name="mock")
    raise RuntimeError(f"provider adapter is unavailable: {diagnostic.provider_id}")


def _mock_routes(
    scenario: str,
) -> tuple[dict[str, AgentProvider], dict[str, str], list[dict[str, Any]]]:
    finding: list[dict[str, object]] = []
    if scenario == "repair":
        finding = [
            {
                "finding_id": "MOCK-H-1",
                "severity": "High",
                "title": "Deterministic repair",
                "description": "The acceptance scenario requires repair.",
            }
        ]
    providers: dict[str, AgentProvider] = {
        "builder": MockProvider(
            provider_name="mock-author",
            output={"status": "completed", "files_changed": [".keeper-workflow/result.txt"]},
            file_writes={".keeper-workflow/result.txt": "built\n"},
        ),
        "reviewer": MockProvider(
            provider_name="mock-reviewer",
            output={"status": "completed", "files_changed": [], "findings": finding},
        ),
        "repairer": MockProvider(
            provider_name="mock-repairer",
            output={"status": "completed", "files_changed": [".keeper-workflow/result.txt"]},
            file_writes={".keeper-workflow/result.txt": "repaired\n"},
        ),
        "post-reviewer": MockProvider(
            provider_name="mock-post-reviewer",
            output={
                "status": "completed",
                "files_changed": [],
                "findings": [],
                "dispositions": (
                    [
                        {
                            "finding_id": "MOCK-H-1",
                            "status": "resolved",
                            "justification": "Deterministic repair verified.",
                        }
                    ]
                    if finding
                    else []
                ),
            },
        ),
    }
    if scenario == "blocked-reviewer":
        providers["reviewer"] = providers["builder"]
    routes = {
        "builder": "builder",
        "reviewer": "reviewer",
        "repairer": "repairer",
        "post_repair_reviewer": "post-reviewer",
    }
    rationale = [
        {
            "role": role,
            "provider": providers[provider_id].provider_name,
            "provider_instance_id": providers[provider_id].instance_id,
            "reason": "deterministic capability match with independent identity",
        }
        for role, provider_id in routes.items()
    ]
    return providers, routes, rationale


def _now() -> str:
    return datetime.now(UTC).isoformat()
