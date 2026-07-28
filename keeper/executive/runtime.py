from __future__ import annotations

from dataclasses import asdict, replace
from pathlib import Path

from keeper.executive.authority import (
    AuthorityEvaluator,
    TrustedActionClassifier,
)
from keeper.executive.authority_gateway import (
    AuthorityBackedSpecialistGateway,
    AuthorityExecutionPlan,
    ProductionAuthorityBackedSpecialistGateway,
    SemanticAuthorityTestGateway,
    artifact_digest_from_files,
)
from keeper.executive.enums import ExecutiveState, TaskStatus
from keeper.executive.models import (
    ApprovalRecord,
    ExecutiveTask,
    MemoryRecord,
    ProjectCharter,
    ProjectRecord,
    SpecialistProfile,
    utc_now,
)
from keeper.executive.planning import TaskReadiness, WorkflowPlanner
from keeper.executive.repository import ExecutiveRepository, new_id
from keeper.executive.specialists import SpecialistSelector
from keeper.executive.state import transition_project


IN_FLIGHT = frozenset(
    {
        TaskStatus.LAUNCH_CLAIMED,
        TaskStatus.EXECUTION_STARTED,
        TaskStatus.RUNNING,
        TaskStatus.COMPLETION_PENDING,
        TaskStatus.UNCERTAIN,
    }
)


class ExecutiveRuntime:
    """Production runtime: every provider boundary is KeeperAuthority-owned."""

    __slots__ = (
        "_repository", "_gateway", "evaluator", "selector",
        "_production_composition",
    )

    def __init__(
        self,
        repository: ExecutiveRepository,
        gateway: SemanticAuthorityTestGateway,
    ) -> None:
        if type(gateway) is not SemanticAuthorityTestGateway:
            raise RuntimeError(
                "test runtime requires the explicit semantic Authority test gateway"
            )
        self._repository = repository
        self._gateway = gateway
        self.evaluator = AuthorityEvaluator()
        self.selector = SpecialistSelector()
        self._production_composition = False

    @classmethod
    def production(
        cls,
        repository: ExecutiveRepository,
        gateway: ProductionAuthorityBackedSpecialistGateway,
    ) -> ExecutiveRuntime:
        if type(gateway) is not ProductionAuthorityBackedSpecialistGateway:
            raise RuntimeError("production runtime requires the sealed production gateway")
        runtime = object.__new__(cls)
        runtime._repository = repository
        runtime._gateway = gateway
        runtime.evaluator = AuthorityEvaluator()
        runtime.selector = SpecialistSelector()
        runtime._production_composition = True
        return runtime

    @property
    def repository(self) -> ExecutiveRepository:
        return self._repository

    @property
    def gateway(self) -> AuthorityBackedSpecialistGateway:
        return self._gateway

    def progress(self, project_id: str) -> ProjectRecord:
        self._validate_composition()
        project = self.repository.project(project_id)
        if project.state in {
            ExecutiveState.PAUSED,
            ExecutiveState.CANCELED,
            ExecutiveState.COMPLETED,
            ExecutiveState.FAILED,
            ExecutiveState.WAITING_FOR_FOUNDER,
            ExecutiveState.WAITING_FOR_PROVIDER,
            ExecutiveState.WAITING_FOR_CREDENTIAL,
            ExecutiveState.WAITING_FOR_EXTERNAL_SYSTEM,
            ExecutiveState.WAITING_FOR_USAGE_RESET,
        }:
            return project
        charter = self._active_charter(project)
        workflows = self.repository.workflows(project_id)
        if not workflows:
            if project.state == ExecutiveState.ACTIVE:
                prior = project
                project = transition_project(project, ExecutiveState.PLANNING)
                self.repository.save_project(project, expected=prior)
            WorkflowPlanner(self.repository).generate(project, charter)
            prior = project
            project = transition_project(project, ExecutiveState.EXECUTING)
            self.repository.save_project(project, expected=prior)
            return project
        tasks = tuple(self.repository.tasks(project_id))
        in_flight = next(
            (task for task in tasks if TaskStatus(task.status) in IN_FLIGHT),
            None,
        )
        if in_flight is not None:
            return self._reconcile_author(project, charter, in_flight)
        review_pending = next(
            (
                task
                for task in tasks
                if task.status == TaskStatus.REVIEW_REQUIRED
                and task.review_attempt_id is not None
            ),
            None,
        )
        if review_pending is not None:
            return self._reconcile_review(project, charter, review_pending)
        unclaimed_review = next(
            (
                task
                for task in tasks
                if task.status == TaskStatus.REVIEW_REQUIRED
                and task.review_attempt_id is None
            ),
            None,
        )
        if unclaimed_review is not None:
            profiles = self.gateway.specialists(charter)
            author = next(
                (
                    item
                    for item in profiles
                    if item.provider_id == unclaimed_review.provider_id
                    and item.model_id == unclaimed_review.model_id
                    and item.session_id == unclaimed_review.session_id
                ),
                None,
            )
            if author is None:
                return self._pause(
                    project,
                    ExecutiveState.BLOCKED,
                    "Author Authority identity is unavailable for review binding.",
                )
            return self._review(
                project, charter, unclaimed_review, author
            )
        if tasks and all(
            task.status in {TaskStatus.COMPLETED, TaskStatus.SKIPPED}
            for task in tasks
        ):
            prior = project
            if project.state == ExecutiveState.EXECUTING:
                project = transition_project(project, ExecutiveState.REVIEWING)
            project = transition_project(project, ExecutiveState.COMPLETED)
            self.repository.save_project(project, expected=prior)
            return project
        candidate = self._next_candidate(tasks)
        if candidate is None:
            return self._pause(
                project,
                ExecutiveState.BLOCKED,
                "No task can progress from durable state.",
            )
        profiles = self.gateway.specialists(charter)
        author = self.selector.select(candidate, charter, profiles)
        if author is None:
            return self._pause(
                project,
                ExecutiveState.WAITING_FOR_PROVIDER,
                "No Authority-qualified provider can accept the task.",
            )
        available_inputs = frozenset(
            output
            for task in tasks
            if task.status == TaskStatus.COMPLETED
            for output in task.expected_outputs
        )
        if candidate.status in {
            TaskStatus.PROPOSED,
            TaskStatus.BLOCKED,
            TaskStatus.WAITING,
        }:
            readiness = TaskReadiness(self.evaluator).evaluate(
                candidate,
                all_tasks=tasks,
                project=project,
                charter=charter,
                specialist=author,
                available_inputs=available_inputs,
            )
            if not readiness.ready:
                return self._pause(
                    project,
                    ExecutiveState.BLOCKED,
                    "; ".join(readiness.reasons),
                )
            ready = TaskReadiness.mark_ready(candidate, readiness)
            try:
                self.repository.save_task(ready, expected=candidate)
            except PermissionError:
                return self.repository.project(project_id)
            candidate = ready
        action = TrustedActionClassifier().classify(
            candidate, charter, author
        )
        decision = self.evaluator.evaluate(
            project,
            charter,
            action,
            tuple(
                self.repository.approvals(
                    project.project_id, charter.revision
                )
            ),
        )
        if decision.outcome not in {"ALLOWED", "ALLOWED_WITHIN_LIMIT"}:
            return self._pause(
                project,
                ExecutiveState.WAITING_FOR_FOUNDER,
                f"Authority denied launch: {decision.outcome}.",
            )
        plan = self.gateway.prepare(candidate, charter, author)
        try:
            claimed = self.repository.claim_execution(
                candidate.task_id,
                expected_revision=candidate.revision,
                plan=asdict(plan),
                action=action,
                approval_id=decision.approval_id,
            )
        except PermissionError:
            return self.repository.project(project_id)
        owned = claimed
        try:
            self.gateway.reserve(plan)
            claimed = self.repository.transition_execution(
                claimed.task_id,
                expected_revision=claimed.revision,
                expected_status=TaskStatus.LAUNCH_CLAIMED,
                target_status=TaskStatus.EXECUTION_STARTED,
                attempt_state="RESERVED",
            )
            owned = claimed
            self._recheck_launch(claimed, charter, author)
            running = self.repository.transition_execution(
                claimed.task_id,
                expected_revision=claimed.revision,
                expected_status=TaskStatus.EXECUTION_STARTED,
                target_status=TaskStatus.RUNNING,
                attempt_state="EXECUTION_STARTED",
            )
            owned = running
            self._cross_budget_boundary(running)
            result = self.gateway.execute(plan)
        except BaseException as error:
            current = self.repository.task(candidate.task_id)
            if (
                current.revision != owned.revision
                or current.status != owned.status
            ):
                return self.repository.project(project_id)
            if current.status != TaskStatus.CANCELED:
                try:
                    self.repository.mark_execution_uncertain(
                        current.task_id,
                        expected_revision=current.revision,
                        reason=f"Authority reconciliation required: {type(error).__name__}",
                    )
                except PermissionError:
                    pass
            return self._pause(
                self.repository.project(project_id),
                ExecutiveState.BLOCKED,
                "Provider execution is uncertain and is not retry-safe.",
            )
        imported = self.repository.accept_author_completion(
            running.task_id,
            expected_revision=running.revision,
            result=asdict(result),
        )
        self._record_author_evidence(imported, result.evidence_digest)
        if imported.status != TaskStatus.REVIEW_REQUIRED:
            return self._pause(
                self.repository.project(project_id),
                ExecutiveState.BLOCKED,
                imported.result_disposition or "Provider execution failed.",
            )
        if imported.status == TaskStatus.CANCELED:
            return self.repository.project(project_id)
        return self._review(project, charter, imported, author)

    def _validate_composition(self) -> None:
        expected = (
            ProductionAuthorityBackedSpecialistGateway
            if self._production_composition
            else SemanticAuthorityTestGateway
        )
        if type(self._gateway) is not expected:
            raise RuntimeError("Executive Authority composition was replaced")

    def pause(self, project_id: str, reason: str) -> ProjectRecord:
        project = self.repository.project(project_id)
        paused = transition_project(project, ExecutiveState.PAUSED, reason)
        self.repository.save_project(paused, expected=project)
        return paused

    def resume(self, project_id: str) -> ProjectRecord:
        project = self.repository.project(project_id)
        if project.state not in {
            ExecutiveState.PAUSED,
            ExecutiveState.BLOCKED,
            ExecutiveState.WAITING_FOR_PROVIDER,
            ExecutiveState.WAITING_FOR_CREDENTIAL,
            ExecutiveState.WAITING_FOR_EXTERNAL_SYSTEM,
            ExecutiveState.WAITING_FOR_USAGE_RESET,
        }:
            raise PermissionError("project is not resumable")
        charter = self._active_charter(project)
        approval = self._active_charter_approval(charter)
        if approval.revoked_at is not None:
            raise PermissionError(
                "delegation was revoked; new Founder approval is required"
            )
        resumed = replace(
            project,
            state=ExecutiveState.EXECUTING.value,
            pause_reason=None,
            updated_at=utc_now(),
        )
        self.repository.save_project(resumed, expected=project)
        return resumed

    def revoke_delegation(self, project_id: str) -> ProjectRecord:
        project = self.repository.project(project_id)
        for approval in self.repository.approvals(
            project_id, project.active_charter_revision
        ):
            if approval.revoked_at is None:
                self.repository.revoke_approval(
                    approval.approval_id, utc_now()
                )
        return self.pause(project_id, "Founder revoked delegation.")

    def cancel(self, project_id: str) -> ProjectRecord:
        canceled, attempt_ids = self.repository.cancel_project_execution(
            project_id
        )
        for attempt_id in attempt_ids:
            try:
                self.gateway.cancel(attempt_id)
            except PermissionError:
                # A terminal Authority attempt is reconciled as late evidence;
                # local cancellation remains authoritative.
                continue
        return canceled

    def _review(
        self,
        project: ProjectRecord,
        charter: ProjectCharter,
        task: ExecutiveTask,
        author: SpecialistProfile,
    ) -> ProjectRecord:
        requires_independent = any(
            "independent" in item.casefold()
            for item in task.review_requirements
        )
        if not requires_independent:
            self.repository.complete_automated_review(
                task.task_id, expected_revision=task.revision
            )
            return project
        profiles = self.gateway.specialists(charter)
        reviewer = self.selector.select(
            task,
            charter,
            profiles,
            author=author,
            independent=True,
        )
        if reviewer is None:
            return self._pause(
                project,
                ExecutiveState.BLOCKED,
                "A distinct Authority-qualified reviewer is unavailable.",
            )
        artifact_digest = task.artifact_digest
        if artifact_digest is None:
            return self._pause(
                project,
                ExecutiveState.BLOCKED,
                "Author artifact evidence is missing.",
            )
        try:
            self._recheck_artifact(task)
        except PermissionError:
            return self._pause(
                project,
                ExecutiveState.BLOCKED,
                "Author artifact changed after authenticated completion.",
            )
        review_task_id = (
            f"{task.task_id}:review:r{task.revision}:"
            f"{artifact_digest[:16]}"
        )
        plan = self.gateway.prepare(
            task,
            charter,
            reviewer,
            task_id=review_task_id,
            role="reviewer",
            artifact_revision_digest=artifact_digest,
            review_instructions=(
                "Review the exact bound artifact and evidence revision.",
                "Return a structured semantic review disposition.",
                "Do not approve your own session or attempt.",
            ),
        )
        claimed = self.repository.claim_review(
            task.task_id,
            expected_revision=task.revision,
            plan=asdict(plan),
        )
        try:
            self.gateway.reserve(plan)
            self.repository.transition_review(
                plan.authority_attempt_id,
                expected_state="LAUNCH_CLAIMED",
                target_state="EXECUTION_STARTED",
            )
            self._recheck_review(claimed, artifact_digest)
            result = self.gateway.execute(plan)
            self._recheck_artifact(claimed)
        except BaseException as error:
            try:
                self.repository.transition_review(
                    plan.authority_attempt_id,
                    expected_state="EXECUTION_STARTED",
                    target_state="UNCERTAIN",
                )
            except PermissionError:
                pass
            return self._pause(
                self.repository.project(project.project_id),
                ExecutiveState.BLOCKED,
                f"Independent review is uncertain: {type(error).__name__}.",
            )
        disposition = self.repository.accept_review_completion(
            task.task_id,
            expected_revision=claimed.revision,
            result=asdict(result),
        )
        if disposition.status == TaskStatus.CANCELED:
            return self.repository.project(project.project_id)
        self.repository.insert_memory(
            MemoryRecord(
                new_id("memory"),
                task.project_id,
                task.charter_revision,
                task.task_id,
                task.stage_id,
                "OUTCOME",
                "VERIFIED",
                "authenticated independent review",
                disposition.result_disposition or "",
                True,
                (
                    result.authority_attempt_id,
                    result.completion_digest,
                    result.structured_review_digest or "",
                ),
                None,
                utc_now(),
            )
        )
        if disposition.status in {
            TaskStatus.REPAIR_REQUIRED,
            TaskStatus.FAILED,
        }:
            return self._pause(
                project,
                ExecutiveState.BLOCKED,
                disposition.result_disposition
                or "Independent review requires repair.",
            )
        return project

    def _reconcile_author(
        self,
        project: ProjectRecord,
        charter: ProjectCharter,
        task: ExecutiveTask,
    ) -> ProjectRecord:
        if task.authority_attempt_id is None:
            return self._pause(
                project,
                ExecutiveState.BLOCKED,
                "In-flight task has no Authority attempt binding.",
            )
        record = self.repository.execution_attempt(
            task.authority_attempt_id
        )
        plan = self.gateway.plan_from_record(record)
        completion = self.gateway.reconcile(plan)
        if completion is None:
            state = self.gateway.attempt_state(plan.authority_attempt_id)
            if (
                state == "RESERVED"
                and task.status
                in {
                    TaskStatus.LAUNCH_CLAIMED,
                    TaskStatus.EXECUTION_STARTED,
                    TaskStatus.UNCERTAIN,
                }
            ):
                current = task
                if current.status in {
                    TaskStatus.LAUNCH_CLAIMED,
                    TaskStatus.UNCERTAIN,
                }:
                    try:
                        current = self.repository.transition_execution(
                            current.task_id,
                            expected_revision=current.revision,
                            expected_status=TaskStatus(current.status),
                            target_status=TaskStatus.EXECUTION_STARTED,
                            attempt_state="RESERVED",
                        )
                    except PermissionError:
                        return self.repository.project(
                            project.project_id
                        )
                profiles = self.gateway.specialists(charter)
                author = next(
                    (
                        item
                        for item in profiles
                        if item.provider_id == current.provider_id
                        and item.model_id == current.model_id
                        and item.session_id == current.session_id
                    ),
                    None,
                )
                if author is None:
                    return self._pause(
                        project,
                        ExecutiveState.BLOCKED,
                        "The claimed Authority provider is no longer qualified.",
                    )
                self._recheck_launch(
                    current,
                    charter,
                    author,
                    allow_blocked_reconciliation=True,
                )
                try:
                    running = self.repository.transition_execution(
                        current.task_id,
                        expected_revision=current.revision,
                        expected_status=TaskStatus.EXECUTION_STARTED,
                        target_status=TaskStatus.RUNNING,
                        attempt_state="EXECUTION_STARTED",
                    )
                except PermissionError:
                    return self.repository.project(project.project_id)
                self._cross_budget_boundary(running)
                try:
                    completion = self.gateway.execute(plan)
                except BaseException:
                    self.repository.mark_execution_uncertain(
                        running.task_id,
                        expected_revision=running.revision,
                        reason="Authority reconciliation required after launch",
                    )
                    return self._pause(
                        project,
                        ExecutiveState.BLOCKED,
                        "Provider execution is uncertain and not retry-safe.",
                    )
                task = running
            else:
                if task.status != TaskStatus.UNCERTAIN:
                    try:
                        self.repository.mark_execution_uncertain(
                            task.task_id,
                            expected_revision=task.revision,
                            reason="Authority completion is not yet authenticated",
                        )
                    except PermissionError:
                        pass
                return self._pause(
                    project,
                    ExecutiveState.BLOCKED,
                    "Claimed execution awaits Authority reconciliation; no retry was created.",
                )
        imported = self.repository.accept_author_completion(
            task.task_id,
            expected_revision=task.revision,
            result=asdict(completion),
        )
        if imported.status == TaskStatus.CANCELED:
            self._record_author_evidence(
                imported, completion.evidence_digest
            )
            return self.repository.project(project.project_id)
        if imported.status != TaskStatus.REVIEW_REQUIRED:
            self._record_author_evidence(
                imported, completion.evidence_digest
            )
            return self._pause(
                project,
                ExecutiveState.BLOCKED,
                imported.result_disposition or "Provider execution failed.",
            )
        profiles = self.gateway.specialists(charter)
        author = next(
            (
                item
                for item in profiles
                if item.provider_id == imported.provider_id
                and item.model_id == imported.model_id
                and item.session_id == imported.session_id
            ),
            None,
        )
        if author is None:
            return self._pause(
                project,
                ExecutiveState.BLOCKED,
                "Completed provider identity is no longer Authority-qualified.",
            )
        self._record_author_evidence(
            imported, completion.evidence_digest
        )
        return self._review(project, charter, imported, author)

    def _reconcile_review(
        self,
        project: ProjectRecord,
        charter: ProjectCharter,
        task: ExecutiveTask,
    ) -> ProjectRecord:
        if task.review_attempt_id is None:
            return project
        review = self.repository.review(task.review_attempt_id)
        plan = self.gateway.plan_from_record(review["plan"])
        completion = self.gateway.reconcile(plan)
        if completion is None:
            return self._pause(
                project,
                ExecutiveState.BLOCKED,
                "Independent review awaits Authority reconciliation.",
            )
        self._recheck_artifact(task)
        disposition = self.repository.accept_review_completion(
            task.task_id,
            expected_revision=task.revision,
            result=asdict(completion),
        )
        if disposition.status != TaskStatus.COMPLETED:
            return self._pause(
                project,
                ExecutiveState.BLOCKED,
                disposition.result_disposition
                or "Independent review requires repair.",
            )
        return project

    def _recheck_artifact(self, task: ExecutiveTask) -> None:
        if task.authority_attempt_id is None or task.artifact_digest is None:
            raise PermissionError("task has no author artifact binding")
        attempt = self.repository.execution_attempt(task.authority_attempt_id)
        identity = attempt.get("artifact_identity")
        files = attempt.get("artifact_files")
        if (
            not isinstance(identity, str)
            or not isinstance(files, list)
            or not all(isinstance(item, str) for item in files)
            or not isinstance(attempt.get("workspace"), str)
        ):
            raise PermissionError("author artifact manifest is unavailable")
        current = artifact_digest_from_files(
            identity,
            Path(str(attempt["workspace"])),
            tuple(files),
        )
        if current != task.artifact_digest:
            raise PermissionError("author artifact digest changed")

    def _recheck_launch(
        self,
        task: ExecutiveTask,
        charter: ProjectCharter,
        specialist: SpecialistProfile,
        *,
        allow_blocked_reconciliation: bool = False,
    ) -> None:
        project = self.repository.project(task.project_id)
        durable_task = self.repository.task(task.task_id)
        durable_charter = self._active_charter(project)
        approval = self._active_charter_approval(durable_charter)
        if (
            durable_task.revision != task.revision
            or durable_task.status != task.status
            or approval.revoked_at is not None
            or durable_charter.charter_id != charter.charter_id
        ):
            raise PermissionError("launch authority changed before execution")
        action = TrustedActionClassifier().classify(
            durable_task, durable_charter, specialist
        )
        authority_project = (
            replace(
                project,
                state=ExecutiveState.EXECUTING.value,
                pause_reason=None,
            )
            if allow_blocked_reconciliation
            and project.state == ExecutiveState.BLOCKED
            else project
        )
        decision = self.evaluator.evaluate(
            authority_project,
            durable_charter,
            action,
            tuple(
                self.repository.approvals(
                    project.project_id, durable_charter.revision
                )
            ),
        )
        if decision.outcome not in {"ALLOWED", "ALLOWED_WITHIN_LIMIT"}:
            raise PermissionError("launch authority was revoked or changed")

    def _recheck_review(
        self,
        task: ExecutiveTask,
        artifact_digest: str,
    ) -> None:
        project = self.repository.project(task.project_id)
        current = self.repository.task(task.task_id)
        charter = self._active_charter(project)
        approval = self._active_charter_approval(charter)
        if (
            project.state == ExecutiveState.CANCELED
            or current.status != TaskStatus.REVIEW_REQUIRED
            or current.artifact_digest != artifact_digest
            or approval.revoked_at is not None
        ):
            raise PermissionError("review authority changed before execution")

    def _active_charter(self, project: ProjectRecord) -> ProjectCharter:
        if project.active_charter_id is None:
            raise PermissionError("project has no active charter")
        charter = self.repository.charter(project.active_charter_id)
        if (
            charter.status != "ACTIVE"
            or charter.revision != project.active_charter_revision
        ):
            raise PermissionError("active charter binding is invalid")
        return charter

    def _active_charter_approval(
        self, charter: ProjectCharter
    ) -> ApprovalRecord:
        approval_id = charter.founder_approval_record_id
        if approval_id is None:
            raise PermissionError("active charter approval is missing")
        approvals = self.repository.approvals(
            charter.project_id, charter.revision
        )
        approval = next(
            (
                item
                for item in approvals
                if item.approval_id == approval_id
            ),
            None,
        )
        if approval is None:
            raise PermissionError("active charter approval is unavailable")
        return approval

    def _record_author_evidence(
        self,
        task: ExecutiveTask,
        completion_digest: str,
    ) -> None:
        self.repository.insert_memory(
            MemoryRecord(
                new_id("memory"),
                task.project_id,
                task.charter_revision,
                task.task_id,
                task.stage_id,
                "EVIDENCE",
                "VERIFIED",
                "authenticated Authority completion",
                "KeeperAuthority completed the bound provider attempt.",
                True,
                (
                    task.authority_attempt_id or "",
                    completion_digest,
                    task.artifact_digest or "",
                ),
                None,
                utc_now(),
            )
        )

    def _cross_budget_boundary(self, task: ExecutiveTask) -> None:
        if task.authority_attempt_id is None:
            raise PermissionError("execution attempt binding is missing")
        attempt = self.repository.execution_attempt(
            task.authority_attempt_id
        )
        reservation_id = attempt.get("budget_reservation_id")
        if isinstance(reservation_id, str):
            self.repository.mark_budget_boundary(reservation_id)

    @staticmethod
    def _next_candidate(
        tasks: tuple[ExecutiveTask, ...],
    ) -> ExecutiveTask | None:
        completed = {
            item.task_id
            for item in tasks
            if item.status == TaskStatus.COMPLETED
        }
        for task in tasks:
            if task.status in {
                TaskStatus.PROPOSED,
                TaskStatus.READY,
                TaskStatus.REPAIR_REQUIRED,
                TaskStatus.BLOCKED,
                TaskStatus.WAITING,
            } and set(task.dependencies).issubset(completed):
                return task
        return None

    def _pause(
        self,
        project: ProjectRecord,
        state: ExecutiveState,
        reason: str,
    ) -> ProjectRecord:
        if project.state == ExecutiveState.CANCELED:
            return project
        try:
            paused = transition_project(project, state, reason)
        except PermissionError:
            paused = replace(
                project,
                state=state.value,
                pause_reason=reason,
                updated_at=utc_now(),
            )
        try:
            self.repository.save_project(paused, expected=project)
        except PermissionError:
            return self.repository.project(project.project_id)
        return paused
