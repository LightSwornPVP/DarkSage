from __future__ import annotations

from dataclasses import replace

from keeper.executive.authority import AuthorityEvaluator
from keeper.executive.enums import ExecutiveState, TaskStatus
from keeper.executive.models import (
    ExecutiveTask,
    MemoryRecord,
    ProjectCharter,
    ProjectRecord,
    SpecialistProfile,
    utc_now,
)
from keeper.executive.planning import TaskReadiness, WorkflowPlanner
from keeper.executive.repository import ExecutiveRepository, new_id
from keeper.executive.specialists import (
    ReviewOrchestrator,
    SpecialistGateway,
    SpecialistOrchestrator,
    SpecialistSelector,
)
from keeper.executive.state import transition_project


class ExecutiveRuntime:
    """One durable bounded progression step per call."""

    def __init__(
        self,
        repository: ExecutiveRepository,
        gateway: SpecialistGateway,
        specialists: tuple[SpecialistProfile, ...],
    ) -> None:
        self.repository = repository
        self.gateway = gateway
        self.specialists = specialists
        self.evaluator = AuthorityEvaluator()
        self.selector = SpecialistSelector()
        self.reviewer = ReviewOrchestrator()

    def progress(self, project_id: str) -> ProjectRecord:
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
                project = transition_project(project, ExecutiveState.PLANNING)
                self.repository.save_project(project)
            WorkflowPlanner(self.repository).generate(project, charter)
            project = transition_project(project, ExecutiveState.EXECUTING)
            self.repository.save_project(project)
            return project
        tasks = tuple(self.repository.tasks(project_id))
        if tasks and all(task.status in {TaskStatus.COMPLETED, TaskStatus.SKIPPED} for task in tasks):
            if project.state == ExecutiveState.EXECUTING:
                project = transition_project(project, ExecutiveState.REVIEWING)
            project = transition_project(project, ExecutiveState.COMPLETED)
            self.repository.save_project(project)
            return project
        candidate = self._next_candidate(tasks)
        if candidate is None:
            return self._pause(project, ExecutiveState.BLOCKED, "No task can progress from durable state.")
        author = self.selector.select(candidate, charter, self.specialists)
        if author is None:
            matching = [
                item for item in self.specialists
                if not set(item.capabilities).isdisjoint(candidate.required_capabilities)
                and item.provider_id in charter.approved_providers
            ]
            state = (
                ExecutiveState.WAITING_FOR_CREDENTIAL
                if matching and any(not item.credential_available for item in matching)
                else ExecutiveState.WAITING_FOR_PROVIDER
            )
            return self._pause(project, state, "No qualified available specialist can accept the task.")
        available_inputs = frozenset(
            output
            for task in tasks
            if task.status == TaskStatus.COMPLETED
            for output in task.expected_outputs
        )
        if candidate.status in {TaskStatus.PROPOSED, TaskStatus.BLOCKED, TaskStatus.WAITING}:
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
            candidate = TaskReadiness.mark_ready(candidate, readiness)
            self.repository.save_task(candidate)
        returned, result = SpecialistOrchestrator(self.gateway).run(
            candidate, charter, author
        )
        self.repository.save_task(returned)
        self.repository.insert_memory(
            MemoryRecord(
                new_id("memory"),
                project.project_id,
                charter.revision,
                returned.task_id,
                returned.stage_id,
                "EVIDENCE",
                "VERIFIED",
                "specialist result",
                f"{result.status}: {', '.join(result.outputs)}",
                True,
                result.evidence,
                None,
                utc_now(),
            )
        )
        requires_independent = any(
            "independent" in item.casefold()
            for item in returned.review_requirements
        )
        reviewer = self.selector.select(
            returned,
            charter,
            self.specialists,
            author=author,
            independent=requires_independent,
        )
        checks = result.verification
        review = self.reviewer.evaluate(
            returned,
            result,
            reviewer=reviewer,
            author=author,
            deterministic_checks=checks,
        )
        disposition = self.reviewer.apply(returned, review)
        self.repository.save_task(disposition)
        self.repository.insert_memory(
            MemoryRecord(
                new_id("memory"),
                project.project_id,
                charter.revision,
                disposition.task_id,
                disposition.stage_id,
                "OUTCOME",
                "VERIFIED",
                "review disposition",
                review.disposition,
                True,
                review.evidence,
                None,
                utc_now(),
            )
        )
        if disposition.status == TaskStatus.BLOCKED:
            return self._pause(
                project,
                ExecutiveState.BLOCKED,
                "Required independent review is unavailable.",
            )
        if disposition.status == TaskStatus.FAILED:
            return self._pause(
                project, ExecutiveState.BLOCKED, "Task retry limit was exceeded."
            )
        return project

    def pause(self, project_id: str, reason: str) -> ProjectRecord:
        project = self.repository.project(project_id)
        paused = transition_project(project, ExecutiveState.PAUSED, reason)
        self.repository.save_project(paused)
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
        approvals = self.repository.approvals(
            project_id, project.active_charter_revision
        )
        if not any(item.revoked_at is None for item in approvals):
            raise PermissionError("delegation was revoked; new Founder approval is required")
        resumed = replace(
            project,
            state=ExecutiveState.EXECUTING.value,
            pause_reason=None,
            updated_at=utc_now(),
        )
        self.repository.save_project(resumed)
        return resumed

    def revoke_delegation(self, project_id: str) -> ProjectRecord:
        project = self.repository.project(project_id)
        for approval in self.repository.approvals(
            project_id, project.active_charter_revision
        ):
            if approval.revoked_at is None:
                self.repository.revoke_approval(approval.approval_id, utc_now())
        return self.pause(project_id, "Founder revoked delegation.")

    def cancel(self, project_id: str) -> ProjectRecord:
        project = self.repository.project(project_id)
        canceled = transition_project(project, ExecutiveState.CANCELED)
        self.repository.save_project(canceled)
        for task in self.repository.tasks(project_id):
            if task.status not in {
                TaskStatus.COMPLETED,
                TaskStatus.FAILED,
                TaskStatus.CANCELED,
                TaskStatus.SKIPPED,
            }:
                self.repository.save_task(
                    replace(task, status=TaskStatus.CANCELED.value, updated_at=utc_now())
                )
        return canceled

    def _active_charter(self, project: ProjectRecord) -> ProjectCharter:
        if project.active_charter_id is None:
            raise PermissionError("project has no active charter")
        charter = self.repository.charter(project.active_charter_id)
        if (
            charter.status != "APPROVED"
            or charter.revision != project.active_charter_revision
        ):
            raise PermissionError("active charter binding is invalid")
        return charter

    @staticmethod
    def _next_candidate(
        tasks: tuple[ExecutiveTask, ...],
    ) -> ExecutiveTask | None:
        completed = {
            item.task_id for item in tasks if item.status == TaskStatus.COMPLETED
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
        try:
            paused = transition_project(project, state, reason)
        except PermissionError:
            paused = replace(project, state=state.value, pause_reason=reason, updated_at=utc_now())
        self.repository.save_project(paused)
        return paused
