from __future__ import annotations

import ctypes
import hashlib
import json
import os
import signal
import subprocess
import sys
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable

from keeper.agent_runner import AgentRunner
from keeper.app.git_safety import GitSafetyService
from keeper.app.lifecycle import RunLifecycle, RunStage
from keeper.app.reporting import finalize_evidence
from keeper.app.path_safety import validate_path_budget
from keeper.app.verification_policy import trusted_bash_launcher
from keeper.app.storage import KeeperStore
from keeper.config import KeeperConfig
from keeper.models.task import Task
from keeper.orchestrator import Keeper
from keeper.providers.base import AgentProvider
from keeper.providers.adapters import (
    ClaudeCommandAdapter,
    CodexCommandAdapter,
    ProviderDiagnostic,
    ProviderDiscovery,
    RoutingRequest,
    route_provider,
)
from keeper.providers.mock import MockProvider
from keeper.providers.ollama import OllamaProvider
from keeper.providers.routing import ProviderRouter
from keeper.workspace import WorkspaceManager
from keeper.recovery import (
    load_json,
    process_exists,
    process_identity,
    process_identity_matches,
    ownership_records_match,
)


@dataclass(slots=True)
class ActiveRun:
    thread: threading.Thread
    cancel_requested: threading.Event
    pause_requested: threading.Event
    approval_ready: threading.Event
    approval_decision: str | None = None
    cancel_callbacks: list[Callable[[], None]] = field(default_factory=list)


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
        self.startup_recovery = self.recover_interrupted_runs()

    def start(
        self, task_id: str, metadata: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        task = self._task(task_id)
        run_id = f"run-{uuid.uuid4().hex}"
        validate_path_budget(
            self.data_directory
            / "evidence"
            / run_id
            / ".ai-workflow"
            / "runs"
            / "pr-p-00000000"
            / "stderr.log",
            purpose="workflow evidence path",
        )
        validate_path_budget(
            self.data_directory / "worktrees" / run_id / str(task["id"]),
            purpose="workflow worktree path",
        )
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
        run.update(metadata or {})
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
            provider_record = _active_provider_record(record)
            ownership = (
                provider_record.get("process_ownership")
                if isinstance(provider_record, dict)
                else None
            )
            if not isinstance(ownership, dict):
                ownership = None
            authority_records = self._process_ownership_records(
                run_id,
                (
                    str(provider_record.get("run_id"))
                    if isinstance(provider_record, dict)
                    and provider_record.get("run_id")
                    else None
                ),
            )
            authority = authority_records[0] if len(authority_records) == 1 else None
            pid = record.get("process_id")
            if not isinstance(pid, int) and isinstance(ownership, dict):
                pid = ownership.get("pid")
            if not isinstance(pid, int):
                pid = _active_provider_pid(record)
            running = isinstance(pid, int) and process_exists(pid)
            terminated = False
            identity_verified = False
            binding_verified = ownership_records_match(authority, ownership)
            if running and isinstance(pid, int):
                current_identity = process_identity(pid)
                identity_verified = binding_verified and process_identity_matches(
                    authority, current_identity
                )
                if identity_verified:
                    terminated = _terminate_attributable_tree(pid)
                    running = not terminated
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
                        "classification": (
                            "uncertain"
                            if (
                                (running and not identity_verified)
                                or (
                                    isinstance(provider_record, dict)
                                    and not binding_verified
                                )
                            )
                            else "recoverable"
                        ),
                        "previous_process_running": running,
                        "provider_process_id": pid,
                        "attributable_tree_terminated": terminated,
                        "identity_verified": identity_verified,
                        "ownership_binding_verified": binding_verified,
                        "authoritative_ownership": authority,
                        "authoritative_ownership_record_count": len(
                            authority_records
                        ),
                        "recorded_ownership": ownership,
                        "retry_safe": (
                            not running
                            and (
                                not isinstance(provider_record, dict)
                                or binding_verified
                            )
                            and stage
                        not in {
                            RunStage.AUTHORIZED_COMMIT.value,
                            RunStage.AUTHORIZED_PUSH.value,
                            RunStage.EVIDENCE_FINALIZATION.value,
                        }
                        ),
                        "detected_at": _now(),
                    },
                }
            )
            self.store.upsert("runs", run_id, current)
            recovered.append(current)
        return recovered

    def retry(
        self,
        run_id: str,
        reason: str,
        stage: str | None = None,
        authorizer: str = "local-user",
    ) -> dict[str, Any]:
        previous = self._run(run_id)
        expected = (
            previous.get("interrupted_from")
            if previous.get("stage") == RunStage.INTERRUPTED.value
            else previous.get("stopped_from")
        )
        selected = stage or (str(expected) if expected else "")
        if not selected:
            raise PermissionError("failed stage could not be identified")
        current = self.lifecycle.retry_stage(
            run_id,
            RunStage(selected),
            reason=reason,
            authorizer=authorizer,
        )
        cancel = threading.Event()
        pause = threading.Event()
        approval = threading.Event()
        task = self._task(str(previous["task_id"]))
        thread = threading.Thread(
            target=self._execute_guarded,
            args=(run_id, task, cancel, pause, approval, selected),
            name=f"keeper-retry-{run_id}-{selected}",
            daemon=True,
        )
        with self._lock:
            if run_id in self._active:
                raise RuntimeError("stage retry is already active")
            self._active[run_id] = ActiveRun(thread, cancel, pause, approval)
        thread.start()
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
        for callback in active.cancel_callbacks:
            callback()
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
        retry_stage: str | None = None,
    ) -> None:
        try:
            self._execute(run_id, task, cancel, pause, approval, retry_stage)
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
            self._add_recovery(record)
            self.store.upsert("runs", run_id, record)
            self._finalize_report(
                run_id,
                task,
                None,
                "BLOCKED",
                failure_reason=str(error),
            )
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
        retry_stage: str | None = None,
    ) -> None:
        repository = Path(str(stored["repository"])).resolve()
        if retry_stage is None:
            self._advance(run_id, RunStage.SCOPE_VALIDATION)
            _validate_task_scope(stored, repository)
            self._advance(run_id, RunStage.RISK_CLASSIFICATION)
            self._advance(run_id, RunStage.AUTHORIZATION_RESOLUTION)
            self._advance(run_id, RunStage.PROVIDER_SELECTION)
        providers, routes, routing = _select_routes(
            stored,
            self.store.get("settings", "providers") or {},
        )
        with self._lock:
            active = self._active.get(run_id)
            if active is not None:
                unique = {id(provider): provider for provider in providers.values()}
                callbacks: list[Callable[[], None]] = []
                for provider in unique.values():
                    callback = getattr(provider, "cancel", None)
                    if callable(callback):
                        callbacks.append(callback)
                active.cancel_callbacks = callbacks
        if retry_stage is None:
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
        if retry_stage is None:
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
        task_path = state / "tasks" / f"{stored['id']}.json"
        domain_task = (
            Task.from_dict(load_json(task_path, {}))
            if retry_stage is not None and task_path.exists()
            else _domain_task(stored, run_id)
        )
        routed_providers: dict[str, AgentProvider] = dict(providers)
        router = ProviderRouter(routed_providers, routes)
        observer = _LifecycleObserver(
            self.lifecycle, run_id, cancel, pause, self.notify
        )
        engine = Keeper(
            config,
            AgentRunner(
                providers["builder"],
                state / "runs",
                30,
                keeper_run_id=run_id,
                ownership_sink=self._persist_process_ownership,
            ),
            WorkspaceManager(repository, config.workspace_root, state / "ownership"),
            router,
            observer,
        )
        result = engine.run_task(
            domain_task,
            retry_stage=retry_stage,
            stage_attempt_id=(
                str(self._run(run_id).get("active_stage_attempt_id", ""))
                if retry_stage is not None
                else None
            ),
        )
        if cancel.is_set():
            return
        if result.status.value != "COMPLETED":
            self.lifecycle.transition(run_id, RunStage.BLOCKED)
            blocked = self._run(run_id)
            self._add_recovery(blocked)
            blocked["ended_at"] = _now()
            self.store.upsert("runs", run_id, blocked)
            semantic_records = self._persist_semantic_evidence(
                run_id, str(stored["id"]), state
            )
            self._finalize_report(
                run_id,
                stored,
                result,
                "BLOCKED",
                semantic_records=semantic_records,
            )
            if result.status.value == "FAILED":
                self.notify(
                    "verification_failed",
                    "Verification failed",
                    f"Run {run_id}",
                )
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
                self._finalize_report(
                    run_id,
                    stored,
                    result,
                    "REJECTED",
                    semantic_records=semantic_records,
                )
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
                    {
                        "push_result": {
                            "remote": remote,
                            "source_ref": source,
                            "destination_ref": destination,
                            "expected_commit": commit_hash,
                            "output": push_result,
                            "remote_hash": commit_hash,
                        }
                    }
                )
        record = self._run(run_id)
        record["ended_at"] = _now()
        record["git_result"] = git_result
        self.store.upsert("runs", run_id, record)
        self._advance(run_id, RunStage.EVIDENCE_FINALIZATION)
        self._finalize_report(
            run_id,
            stored,
            result,
            "COMPLETED",
            semantic_records=semantic_records,
            git_result=git_result,
        )
        self._advance(run_id, RunStage.CLOSED)
        record = self._run(run_id)
        record.update(
            {
                "status": "COMPLETED",
                "outcome": "approved",
                "ended_at": record.get("ended_at", _now()),
                "evidence_root": str(evidence),
                "report_markdown": str(evidence / "final-report.md"),
                "report_json": str(evidence / "final-report.json"),
                "git_result": git_result,
            }
        )
        self.store.upsert("runs", run_id, record)
        self.notify("run_completed", "Run completed", f"Run {run_id}")

    def _finalize_report(
        self,
        run_id: str,
        stored: dict[str, Any],
        result: Task | None,
        terminal_status: str,
        *,
        semantic_records: list[dict[str, Any]] | None = None,
        git_result: dict[str, Any] | None = None,
        failure_reason: str | None = None,
    ) -> dict[str, Any]:
        evidence = self.data_directory / "evidence" / run_id
        evidence.mkdir(parents=True, exist_ok=True)
        run = self._run(run_id)
        records = _provider_records(evidence)
        authorizations = [
            item
            for item in self.store.list("authorizations")
            if item.get("task_id") == stored.get("id")
            and item.get("run_id") in {None, run_id}
        ]
        waivers = [
            item
            for item in authorizations
            if item.get("capability") == "verification_waiver"
        ]
        verifications = semantic_records
        if verifications is None:
            verifications = [
                item
                for item in self.store.list("verification_records")
                if item.get("run_id") == run_id
            ]
        initial_reviews = [
            item for item in records if item.get("role") == "reviewer"
        ]
        post_reviews = [
            item
            for item in records
            if item.get("role") == "post_repair_reviewer"
        ]
        repairs = [
            {
                "provider_run_id": item.get("run_id"),
                "provider_name": item.get("provider_name"),
                "files_changed": item.get("files_changed", []),
                "status": item.get("status"),
                "start_time": item.get("start_time"),
                "end_time": item.get("end_time"),
            }
            for item in records
            if item.get("role") == "repairer"
        ]
        artifacts = _evidence_artifacts(evidence)
        provider_identities = run.get("providers", {})
        if not isinstance(provider_identities, dict):
            provider_identities = {}
        git_values = dict(git_result or run.get("git_result") or {})
        push_result = git_values.pop("push_result", {})
        approval = run.get("approval")
        if not isinstance(approval, dict):
            approving_records = [
                item for item in records if item.get("final_approval_authority")
            ]
            approval = (
                {
                    "decision": "approved",
                    "authority": approving_records[-1]["final_approval_authority"],
                }
                if approving_records
                else {}
            )
        report: dict[str, Any] = {
            "schema_version": 1,
            "run_id": run_id,
            "task_id": stored.get("id"),
            "objective": stored.get("objective", ""),
            "repository": stored.get("repository", ""),
            "worktree": (
                result.workspace_path
                if result is not None and result.workspace_path
                else run.get("worktree", run.get("workspace", ""))
            ),
            "branch": (
                result.branch_name
                if result is not None and result.branch_name
                else run.get("worktree_branch", run.get("branch", ""))
            ),
            "baseline": stored.get("baseline", ""),
            "scope": {
                "included_paths": list(stored.get("included_paths", [])),
                "excluded_paths": list(stored.get("excluded_paths", [])),
                "completion_criteria": list(
                    stored.get("completion_criteria", [])
                ),
                "required_validations": list(
                    stored.get("required_validations", [])
                ),
                "risk": stored.get("risk", "low"),
                "prohibited_actions": list(
                    stored.get("prohibited_actions", [])
                ),
            },
            "provider_policy": stored.get("provider_policy", "repository-default"),
            "provider_identities": provider_identities,
            "routing_rationale": list(run.get("routing_decisions", [])),
            "lifecycle_stages": list(run.get("history", [])),
            "authorizations": authorizations,
            "waivers": waivers,
            "commands": verifications,
            "verification_results": verifications,
            "findings": [
                finding
                for item in initial_reviews
                for finding in item.get("review_findings", [])
            ],
            "dispositions": [
                disposition
                for item in post_reviews
                for disposition in item.get("accepted_findings", [])
            ],
            "repairs": repairs,
            "post_repair_findings": [
                finding
                for item in post_reviews
                for finding in item.get("review_findings", [])
            ],
            "approval_result": approval,
            "commit_result": git_values,
            "push_result": push_result,
            "logs": [
                item
                for item in artifacts
                if str(item["path"]).endswith((".log", "prompt.md"))
            ],
            "artifacts": artifacts,
            "evidence_paths": [
                str(evidence.resolve()),
                str((evidence / "final-report.json").resolve()),
                str((evidence / "final-report.md").resolve()),
                str((evidence / "evidence-index.json").resolve()),
            ],
            "evidence_hashes": [
                {"path": item["path"], "sha256": item["sha256"]}
                for item in artifacts
            ],
            "unresolved_observations": [
                finding
                for item in records
                for finding in item.get("rejected_findings", [])
            ],
            "start_time": run.get("started_at", ""),
            "end_time": run.get("ended_at", _now()),
            "terminal_status": terminal_status,
            "failure_reason": failure_reason or run.get("failure_reason", ""),
        }
        finalize_evidence(evidence, report)
        return report

    def _persist_process_ownership(self, ownership: dict[str, Any]) -> None:
        keeper_run_id = str(ownership.get("keeper_run_id") or "")
        provider_run_id = str(ownership.get("provider_run_id") or "")
        task_id = str(ownership.get("task_id") or "")
        if not keeper_run_id or not provider_run_id or not task_id:
            raise PermissionError("process ownership binding is incomplete")
        run = self._run(keeper_run_id)
        if run.get("task_id") != task_id:
            raise PermissionError("process ownership task binding is inconsistent")
        evidence_root = Path(str(run.get("evidence_root", ""))).resolve()
        evidence_path = Path(str(ownership.get("evidence_path", ""))).resolve()
        if not evidence_path.is_relative_to(evidence_root):
            raise PermissionError("process ownership evidence path escapes the run")
        value = {
            **ownership,
            "id": f"process-ownership:{keeper_run_id}:{provider_run_id}",
            "kind": "process_ownership",
            "recorded_at": _now(),
        }
        self.store.insert_immutable("artifacts", str(value["id"]), value)

    def _process_ownership_records(
        self, keeper_run_id: str, provider_run_id: str | None
    ) -> list[dict[str, Any]]:
        if not provider_run_id:
            return []
        return [
            item
            for item in self.store.list("artifacts")
            if item.get("kind") == "process_ownership"
            and item.get("keeper_run_id") == keeper_run_id
            and item.get("provider_run_id") == provider_run_id
        ]

    @staticmethod
    def _add_recovery(record: dict[str, Any]) -> None:
        stopped = str(record.get("stopped_from") or "")
        record["recovery"] = {
            "classification": "recoverable",
            "previous_process_running": False,
            "retry_safe": stopped
            not in {
                RunStage.AUTHORIZED_COMMIT.value,
                RunStage.AUTHORIZED_PUSH.value,
                RunStage.EVIDENCE_FINALIZATION.value,
            },
            "detected_at": _now(),
        }

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
    is_demo = bool(stored.get("is_demo", False))
    scenario = str(stored.get("mock_scenario", "repair"))
    final = "repaired\n" if scenario == "repair" else "built\n"
    waivers = [
        item
        for item in stored.get("verification_waivers", [])
        if isinstance(item, dict)
    ]
    waiver_id = str(waivers[0]["waiver_id"]) if waivers else None
    if is_demo:
        commands = [["keeper:file-equals", ".keeper-workflow/result.txt", "built\n"]]
        final_commands = [["keeper:file-equals", ".keeper-workflow/result.txt", final]]
        specs = [
            {
                "category": "task",
                "arguments": commands[0],
                "validator": "file-equals",
                "registration_id": "keeper:demo-file-equals",
                "required": True,
                "waiver_id": waiver_id,
            }
        ]
        final_specs = [
            {
                "category": "task",
                "arguments": final_commands[0],
                "validator": "file-equals",
                "registration_id": "keeper:demo-file-equals",
                "required": True,
                "waiver_id": waiver_id,
            }
        ]
        categories = ["task"]
        allowed_paths = [".keeper-workflow/"]
        blocked_paths: list[str] = []
    else:
        specs = _registered_verification_specs(stored)
        final_specs = [dict(item) for item in specs]
        commands = []
        for item in specs:
            arguments = item.get("arguments")
            if not isinstance(arguments, list) or not arguments:
                raise ValueError("registered verification arguments must be a non-empty list")
            commands.append([str(value) for value in arguments])
        final_commands = [list(item) for item in commands]
        categories = [str(value) for value in stored.get("required_validations", [])]
        allowed_paths = [str(value) for value in stored.get("included_paths", [])]
        blocked_paths = [str(value) for value in stored.get("excluded_paths", [])]
    return Task(
        str(stored["id"]),
        str(stored["title"]),
        str(stored["objective"]),
        "desktop",
        1,
        risk=str(stored.get("risk", "low")),
        acceptance_criteria=[
            str(value) for value in stored.get("completion_criteria", [])
        ],
        verification_commands=commands,
        final_verification_commands=final_commands,
        verification_specs=specs,
        final_verification_specs=final_specs,
        required_verification_categories=categories,
        allowed_paths=allowed_paths,
        blocked_paths=blocked_paths,
        capabilities=["repository_write", "run_verification"],
        provider=str(stored.get("provider_policy", "automatic")),
        verification_waivers=waivers,
    )


def _select_routes(
    stored: dict[str, Any], configured_paths: dict[str, Any]
) -> tuple[dict[str, AgentProvider], dict[str, str], list[dict[str, Any]]]:
    policy = str(stored.get("provider_policy", "mock"))
    if policy == "mock":
        if not bool(stored.get("is_demo", False)):
            raise PermissionError("mock routing is restricted to explicit demonstrations")
        return _mock_routes(str(stored.get("mock_scenario", "repair")))
    diagnostics = ProviderDiscovery(
        {str(key): str(value) for key, value in configured_paths.items()}
    ).discover()
    real_diagnostics = [item for item in diagnostics if item.provider_id != "mock"]
    if policy == "local-only":
        author_pool = [
            item for item in real_diagnostics if item.capabilities.local_only
        ]
    elif policy in {"automatic", "strongest"}:
        author_pool = real_diagnostics
    else:
        author_pool = [
            item for item in real_diagnostics if item.provider_id == policy
        ]
    author = route_provider(
        RoutingRequest("builder", str(stored.get("risk", "low")), "keeper"),
        author_pool,
    )
    reviewer = route_provider(
        RoutingRequest(
            "reviewer",
            str(stored.get("risk", "low")),
            "keeper",
            frozenset({author.provider_id}),
            author.provider_id == "ollama",
        ),
        real_diagnostics,
    )
    repairer = route_provider(
        RoutingRequest("repairer", str(stored.get("risk", "low")), "keeper"),
        real_diagnostics,
    )
    selected = {author.provider_id, reviewer.provider_id, repairer.provider_id}
    instances = {
        provider_id: _adapter(
            next(item for item in real_diagnostics if item.provider_id == provider_id)
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


def _registered_verification_specs(stored: dict[str, Any]) -> list[dict[str, Any]]:
    supplied = stored.get("verification_specs", [])
    if supplied:
        raise PermissionError(
            "normal tasks cannot supply caller-controlled verification specifications"
        )
    repository = Path(str(stored["repository"])).resolve()
    specifications: list[dict[str, Any]] = []
    for category_value in stored.get("required_validations", []):
        category = str(category_value).strip().lower()
        if category == "tests":
            arguments = ["{python}", "-m", "pytest", "-q"]
            validator = "pytest"
        elif category == "typing":
            arguments = [
                "{python}",
                "-m",
                "mypy",
                "--strict",
                "keeper",
                "tests/keeper",
            ]
            validator = "mypy"
        elif category == "compilation":
            arguments = [
                "{python}",
                "-m",
                "compileall",
                "-q",
                "keeper",
                "tests/keeper",
            ]
            validator = "compileall"
        elif category == "foundation":
            script = (repository / "scripts" / "verify-foundation.sh").resolve()
            if (
                not script.is_relative_to(repository)
                or script.is_symlink()
                or not script.is_file()
            ):
                raise PermissionError("foundation validator script is unavailable or unsafe")
            bash = trusted_bash_launcher()
            if bash is None:
                raise RuntimeError("foundation validator requires Git Bash")
            arguments = [str(bash), str(script)]
            validator = "foundation-script"
        else:
            raise ValueError(
                f"validation category requires an explicit registered specification: {category}"
            )
        specification: dict[str, Any] = {
            "category": category,
            "arguments": arguments,
            "validator": validator,
            "registration_id": f"keeper:{category}:v1",
            "required": True,
            "expected_executable_sha256": hashlib.sha256(
                (
                    Path(sys.executable).resolve()
                    if validator in {"pytest", "mypy", "compileall"}
                    else Path(arguments[0]).resolve()
                ).read_bytes()
            ).hexdigest(),
        }
        if validator == "foundation-script":
            specification["expected_sha256"] = hashlib.sha256(
                Path(arguments[-1]).read_bytes()
            ).hexdigest()
        specifications.append(specification)
    if not specifications:
        raise ValueError("normal tasks require registered validation categories")
    return specifications


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


def _provider_records(evidence: Path) -> list[dict[str, Any]]:
    root = evidence.resolve()
    records: list[dict[str, Any]] = []
    for path in sorted(root.glob(".ai-workflow/runs/*/run.json")):
        if path.is_symlink():
            raise PermissionError("provider evidence cannot be a symbolic link")
        resolved = path.resolve(strict=True)
        if not resolved.is_relative_to(root):
            raise PermissionError("provider evidence escapes the run root")
        try:
            value = json.loads(resolved.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(value, dict):
            records.append(value)
    return records


def _evidence_artifacts(evidence: Path) -> list[dict[str, Any]]:
    root = evidence.resolve()
    artifacts: list[dict[str, Any]] = []
    excluded = {"evidence-index.json", "final-report.json", "final-report.md"}
    for path in sorted(root.rglob("*")):
        if path.name in excluded or not path.is_file():
            continue
        if path.is_symlink():
            raise PermissionError("evidence artifact cannot be a symbolic link")
        resolved = path.resolve(strict=True)
        if not resolved.is_relative_to(root):
            raise PermissionError("evidence artifact escapes the run root")
        content = resolved.read_bytes()
        artifacts.append(
            {
                "path": resolved.relative_to(root).as_posix(),
                "sha256": hashlib.sha256(content).hexdigest(),
                "size": len(content),
            }
        )
    return artifacts


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _active_provider_pid(record: dict[str, Any]) -> int | None:
    root = record.get("evidence_root")
    if not isinstance(root, str):
        return None
    for path in sorted(
        Path(root).glob(".ai-workflow/runs/*/run.json"),
        key=lambda item: item.stat().st_mtime if item.exists() else 0,
        reverse=True,
    ):
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        pid = value.get("process_id")
        if value.get("status") == "running" and isinstance(pid, int):
            return pid
    return None


def _active_provider_record(
    record: dict[str, Any],
) -> dict[str, Any] | None:
    root = record.get("evidence_root")
    if not isinstance(root, str):
        return None
    for path in sorted(
        Path(root).glob(".ai-workflow/runs/*/run.json"),
        key=lambda item: item.stat().st_mtime if item.exists() else 0,
        reverse=True,
    ):
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if value.get("status") == "running" and isinstance(value, dict):
            return value
    return None


def _terminate_attributable_tree(process_id: int) -> bool:
    if os.name == "nt":
        process_ids = _windows_process_tree(process_id)
        result = subprocess.run(
            ["taskkill.exe", "/PID", str(process_id), "/T", "/F"],
            capture_output=True,
            text=True,
            shell=False,
            timeout=15,
            check=False,
        )
        if result.returncode != 0:
            for pid in process_ids:
                _windows_terminate_process(pid)
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline and any(
            process_exists(pid) for pid in process_ids
        ):
            time.sleep(0.05)
        return not any(process_exists(pid) for pid in process_ids)
    try:
        killpg = getattr(os, "killpg")
        killpg(process_id, signal.SIGTERM)
    except ProcessLookupError:
        return True
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        try:
            killpg(process_id, 0)
        except ProcessLookupError:
            return True
        time.sleep(0.05)
    try:
        killpg(process_id, getattr(signal, "SIGKILL"))
    except ProcessLookupError:
        return True
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        try:
            killpg(process_id, 0)
        except ProcessLookupError:
            return True
        time.sleep(0.05)
    return False


def _windows_process_tree(root_process_id: int) -> list[int]:
    class ProcessEntry(ctypes.Structure):
        _fields_ = [
            ("dwSize", ctypes.c_uint32),
            ("cntUsage", ctypes.c_uint32),
            ("th32ProcessID", ctypes.c_uint32),
            ("th32DefaultHeapID", ctypes.c_void_p),
            ("th32ModuleID", ctypes.c_uint32),
            ("cntThreads", ctypes.c_uint32),
            ("th32ParentProcessID", ctypes.c_uint32),
            ("pcPriClassBase", ctypes.c_long),
            ("dwFlags", ctypes.c_uint32),
            ("szExeFile", ctypes.c_wchar * 260),
        ]

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateToolhelp32Snapshot.argtypes = (ctypes.c_uint32, ctypes.c_uint32)
    kernel32.CreateToolhelp32Snapshot.restype = ctypes.c_void_p
    kernel32.Process32FirstW.argtypes = (
        ctypes.c_void_p,
        ctypes.POINTER(ProcessEntry),
    )
    kernel32.Process32FirstW.restype = ctypes.c_int
    kernel32.Process32NextW.argtypes = (
        ctypes.c_void_p,
        ctypes.POINTER(ProcessEntry),
    )
    kernel32.Process32NextW.restype = ctypes.c_int
    kernel32.CloseHandle.argtypes = (ctypes.c_void_p,)
    snapshot = kernel32.CreateToolhelp32Snapshot(0x00000002, 0)
    if snapshot == ctypes.c_void_p(-1).value:
        return [root_process_id]
    children: dict[int, list[int]] = {}
    try:
        entry = ProcessEntry()
        entry.dwSize = ctypes.sizeof(entry)
        available = bool(kernel32.Process32FirstW(snapshot, ctypes.byref(entry)))
        while available:
            children.setdefault(int(entry.th32ParentProcessID), []).append(
                int(entry.th32ProcessID)
            )
            available = bool(kernel32.Process32NextW(snapshot, ctypes.byref(entry)))
    finally:
        kernel32.CloseHandle(snapshot)

    ordered: list[int] = []

    def visit(pid: int) -> None:
        for child in children.get(pid, []):
            visit(child)
        ordered.append(pid)

    visit(root_process_id)
    return ordered


def _windows_terminate_process(process_id: int) -> bool:
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.OpenProcess.argtypes = (ctypes.c_uint32, ctypes.c_int, ctypes.c_uint32)
    kernel32.OpenProcess.restype = ctypes.c_void_p
    kernel32.TerminateProcess.argtypes = (ctypes.c_void_p, ctypes.c_uint32)
    kernel32.TerminateProcess.restype = ctypes.c_int
    kernel32.WaitForSingleObject.argtypes = (ctypes.c_void_p, ctypes.c_uint32)
    kernel32.WaitForSingleObject.restype = ctypes.c_uint32
    kernel32.CloseHandle.argtypes = (ctypes.c_void_p,)
    handle = kernel32.OpenProcess(0x0001 | 0x00100000, False, process_id)
    if not handle:
        return not process_exists(process_id)
    try:
        if not kernel32.TerminateProcess(handle, 1):
            return False
        kernel32.WaitForSingleObject(handle, 5000)
        return not process_exists(process_id)
    finally:
        kernel32.CloseHandle(handle)
