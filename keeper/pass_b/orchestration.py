from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Callable

from keeper.pass_b.enums import (
    AssignmentRole,
    AssignmentState,
    AttemptState,
    EvidenceState,
    PauseCode,
    ReservationMode,
    ReservationState,
    ReviewState,
    WorkItemState,
)
from keeper.pass_b.models import (
    AssignmentRecord,
    AttemptRecord,
    EvidenceBundleRecord,
    PauseReasonRecord,
    ProviderAccountRecord,
    ProviderRecord,
    ProviderSessionRecord,
    ResumeCheckpointRecord,
    ReviewRecord,
    UsagePoolRecord,
    WorkItemRecord,
    WorkspaceReservationRecord,
    WriteReservationRecord,
)
from keeper.pass_b.providers import (
    AdapterResult,
    ProviderAdapter,
    assignment_to_adapter,
)
from keeper.pass_b.repository import (
    PassBRepository,
    canonical_scope,
    canonical_workspace_path,
)


Clock = Callable[[], datetime]


class OrchestrationService:
    def __init__(
        self,
        repository: PassBRepository,
        *,
        clock: Clock | None = None,
    ) -> None:
        self.repository = repository
        self.clock = clock or (lambda: datetime.now(UTC))
        self.adapters: dict[str, ProviderAdapter] = {}

    def register_provider(
        self,
        provider: ProviderRecord,
        account: ProviderAccountRecord,
        usage_pool: UsagePoolRecord,
        sessions: tuple[ProviderSessionRecord, ...],
        adapter: ProviderAdapter,
    ) -> None:
        if (
            provider.provider_id != account.provider_id
            or account.usage_pool_id != usage_pool.pool_id
            or usage_pool.provider_id != provider.provider_id
            or usage_pool.account_id != account.account_id
            or any(
                session.provider_id != provider.provider_id
                or session.account_id != account.account_id
                for session in sessions
            )
        ):
            raise PermissionError("provider registration identities are inconsistent")
        self.repository.insert(provider)
        self.repository.insert(account)
        self.repository.insert(usage_pool)
        for session in sessions:
            self.repository.insert(session)
        self.attach_adapter(provider.provider_id, adapter)

    def attach_adapter(
        self, provider_id: str, adapter: ProviderAdapter
    ) -> None:
        provider = self.repository.get(ProviderRecord, provider_id)
        descriptor = adapter.descriptor()
        if (
            descriptor.provider_identity != provider.identity
            or descriptor.classification != provider.classification
            or descriptor.session_model != provider.session_model
            or descriptor.cost_mode != provider.cost_mode
            or provider.concurrency_limit > descriptor.concurrency_limit
            or descriptor.authentication_ready
            != provider.authentication_ready
            or descriptor.cancellation_support
            != provider.cancellation_support
            or descriptor.resume_support != provider.resume_support
            or descriptor.evidence_format != provider.evidence_format
            or not set(provider.capabilities).issubset(
                descriptor.capabilities
            )
            or not set(provider.tool_support).issubset(
                descriptor.tool_support
            )
            or not set(provider.workspace_support).issubset(
                descriptor.workspace_support
            )
        ):
            raise PermissionError("adapter does not match durable provider")
        self.adapters[provider.provider_id] = adapter

    def create_work_item(
        self,
        *,
        project_id: str,
        charter_id: str,
        charter_revision: int,
        workflow_id: str,
        title: str,
        objective: str,
        dependencies: tuple[str, ...] = (),
        required_roles: tuple[str, ...] = (),
    ) -> WorkItemRecord:
        now = self._now()
        record = WorkItemRecord(
            work_item_id=uuid.uuid4().hex,
            project_id=project_id,
            charter_id=charter_id,
            charter_revision=charter_revision,
            workflow_id=workflow_id,
            title=title,
            objective=objective,
            dependencies=dependencies,
            required_roles=required_roles,
            state=WorkItemState.READY,
            created_at=now,
            updated_at=now,
            revision=1,
        )
        self.repository.insert(record)
        return record

    def create_assignment(
        self,
        *,
        work_item: WorkItemRecord,
        provider_id: str,
        account_id: str,
        session_id: str,
        role: str,
        model_id: str,
        workspace_id: str,
        authority_envelope_digest: str,
        expected_evidence: tuple[str, ...],
        usage_policy: dict[str, object],
        independence_key: str,
    ) -> AssignmentRecord:
        selected_role = AssignmentRole(role)
        provider = self.repository.get(ProviderRecord, provider_id)
        account = self.repository.get(ProviderAccountRecord, account_id)
        session = self.repository.get(ProviderSessionRecord, session_id)
        if (
            account.provider_id != provider_id
            or session.provider_id != provider_id
            or session.account_id != account_id
            or model_id != session.model_id
            or selected_role.value.casefold() not in {
                item.casefold() for item in provider.capabilities
            }
            and "all-roles" not in provider.capabilities
        ):
            raise PermissionError("provider session cannot satisfy assignment")
        now = self._now()
        record = AssignmentRecord(
            assignment_id=uuid.uuid4().hex,
            project_id=work_item.project_id,
            charter_id=work_item.charter_id,
            charter_revision=work_item.charter_revision,
            workflow_id=work_item.workflow_id,
            work_item_id=work_item.work_item_id,
            provider_id=provider_id,
            account_id=account_id,
            session_id=session_id,
            role=selected_role,
            model_id=model_id,
            workspace_id=workspace_id,
            authority_envelope_digest=authority_envelope_digest,
            expected_evidence=expected_evidence,
            usage_policy=dict(usage_policy),
            state=AssignmentState.READY,
            read_only=selected_role == AssignmentRole.REVIEWER,
            independence_key=independence_key,
            created_at=now,
            updated_at=now,
            revision=1,
        )
        self.repository.insert(record)
        return record

    def reserve_workspace(
        self,
        assignment: AssignmentRecord,
        path: Path,
        *,
        lease_seconds: int,
        branch: str | None,
        base_commit: str | None,
    ) -> WorkspaceReservationRecord:
        if lease_seconds < 1:
            raise ValueError("workspace lease must be positive")
        now = self.clock()
        record = WorkspaceReservationRecord(
            workspace_reservation_id=uuid.uuid4().hex,
            project_id=assignment.project_id,
            assignment_id=assignment.assignment_id,
            workspace_id=assignment.workspace_id,
            canonical_path=canonical_workspace_path(path),
            mode=(
                ReservationMode.READ_ONLY
                if assignment.read_only
                else ReservationMode.WRITE
            ),
            owner_token=uuid.uuid4().hex,
            lease_expires_at=(now + timedelta(seconds=lease_seconds)).isoformat(),
            state=ReservationState.ACTIVE,
            worktree_branch=branch,
            base_commit=base_commit,
            created_at=now.isoformat(),
            updated_at=now.isoformat(),
            revision=1,
        )
        self.repository.reserve_workspace(record)
        return record

    def reserve_writes(
        self,
        assignment: AssignmentRecord,
        workspace: WorkspaceReservationRecord,
        scopes: tuple[str, ...],
        *,
        lease_seconds: int,
    ) -> WriteReservationRecord:
        if assignment.read_only:
            raise PermissionError("review assignment cannot reserve writes")
        now = self.clock()
        record = WriteReservationRecord(
            write_reservation_id=uuid.uuid4().hex,
            workspace_reservation_id=workspace.workspace_reservation_id,
            assignment_id=assignment.assignment_id,
            scope=scopes,
            scope_keys=tuple(
                canonical_scope(workspace.workspace_id, item) for item in scopes
            ),
            owner_token=workspace.owner_token,
            lease_expires_at=(now + timedelta(seconds=lease_seconds)).isoformat(),
            state=ReservationState.ACTIVE,
            created_at=now.isoformat(),
            updated_at=now.isoformat(),
            revision=1,
        )
        self.repository.reserve_write(record)
        return record

    def reserve_usage(
        self,
        assignment: AssignmentRecord,
        workspace: WorkspaceReservationRecord,
        amount: float,
    ) -> bool:
        account = self.repository.get(
            ProviderAccountRecord, assignment.account_id
        )
        pool = self.repository.get(UsagePoolRecord, account.usage_pool_id)
        now = self._now()
        pause = PauseReasonRecord(
            pause_reason_id=uuid.uuid4().hex,
            assignment_id=assignment.assignment_id,
            code=PauseCode.USAGE_EXHAUSTED,
            detail="Provider usage pool is exhausted; waiting for its reset.",
            reset_at=pool.reset_at,
            safe_to_release_workspace=False,
            created_at=now,
            resolved_at=None,
            revision=1,
        )
        checkpoint = ResumeCheckpointRecord(
            resume_checkpoint_id=uuid.uuid4().hex,
            assignment_id=assignment.assignment_id,
            attempt_id=None,
            project_id=assignment.project_id,
            charter_id=assignment.charter_id,
            charter_revision=assignment.charter_revision,
            workspace_reservation_id=workspace.workspace_reservation_id,
            usage_pool_id=pool.pool_id,
            authority_envelope_digest=assignment.authority_envelope_digest,
            checkpoint_state={
                "assignment_revision": assignment.revision,
                "workspace_revision": workspace.revision,
                "provider_id": assignment.provider_id,
                "account_id": assignment.account_id,
                "session_id": assignment.session_id,
                "model_id": assignment.model_id,
            },
            created_at=now,
            resumed_at=None,
            revision=1,
        )
        return self.repository.reserve_usage_or_pause(
            reservation_id=uuid.uuid4().hex,
            pool_id=pool.pool_id,
            assignment_id=assignment.assignment_id,
            amount=amount,
            pause=pause,
            checkpoint=checkpoint,
            observed_at=now,
        )

    def resume_after_reset(
        self, assignment_id: str, checkpoint_id: str
    ) -> AssignmentRecord:
        assignment = self.repository.get(AssignmentRecord, assignment_id)
        account = self.repository.get(
            ProviderAccountRecord, assignment.account_id
        )
        return self.repository.resume_after_usage_reset(
            pool_id=account.usage_pool_id,
            assignment_id=assignment_id,
            checkpoint_id=checkpoint_id,
            resumed_at=self._now(),
        )

    def run_assignment(
        self,
        assignment_id: str,
        workspace_path: Path,
        *,
        authority_attempt_id: str,
        global_context: dict[str, object],
        task_context: dict[str, object],
        side_effect_class: str = "REVERSIBLE_WORKSPACE_WRITE",
        after_launch_claim: Callable[[], None] | None = None,
    ) -> EvidenceBundleRecord:
        assignment = self.repository.get(AssignmentRecord, assignment_id)
        adapter = self.adapters.get(assignment.provider_id)
        if adapter is None:
            raise RuntimeError("assignment provider adapter is unavailable")
        now = self._now()
        attempt = AttemptRecord(
            attempt_id=uuid.uuid4().hex,
            assignment_id=assignment_id,
            authority_attempt_id=authority_attempt_id,
            launch_token=uuid.uuid4().hex,
            state=AttemptState.RESERVED,
            external_execution_id=None,
            side_effect_class=side_effect_class,
            started_at=None,
            finished_at=None,
            last_error=None,
            created_at=now,
            updated_at=now,
            revision=1,
        )
        self.repository.reserve_attempt(attempt)
        claimed = self.repository.claim_launch(attempt.attempt_id, self._now())
        if after_launch_claim is not None:
            after_launch_claim()
        request = assignment_to_adapter(
            assignment,
            claimed.attempt_id,
            authority_attempt_id,
            workspace_path,
            global_context=dict(global_context),
            task_context=dict(task_context),
        )
        try:
            result = adapter.launch(request)
        except BaseException:
            # The durable claim deliberately remains ambiguous for restart recovery.
            raise
        running = self.repository.mark_running(
            claimed.attempt_id, result.external_execution_id, self._now()
        )
        evidence = self._evidence(assignment, running, result)
        self.repository.complete_attempt(
            running.attempt_id, evidence, self._now()
        )
        return evidence

    def cancel_assignment(self, assignment_id: str) -> AttemptRecord:
        assignment = self.repository.get(AssignmentRecord, assignment_id)
        provider = self.repository.get(
            ProviderRecord, assignment.provider_id
        )
        adapter = self.adapters.get(assignment.provider_id)
        if (
            adapter is None
            or not provider.cancellation_support
            or not adapter.descriptor().cancellation_support
        ):
            raise PermissionError("assignment provider does not support cancellation")
        claimed = self.repository.claim_cancellation(
            assignment.assignment_id, self._now()
        )
        external_execution_id = claimed.external_execution_id
        if external_execution_id is None:
            raise RuntimeError("claimed cancellation lacks external identity")
        adapter.cancel(external_execution_id)
        return self.repository.complete_cancellation(
            claimed.attempt_id, self._now()
        )

    def validate_evidence(
        self, evidence_id: str, workspace_path: Path
    ) -> EvidenceBundleRecord:
        evidence = self.repository.get(EvidenceBundleRecord, evidence_id)
        assignment = self.repository.get(
            AssignmentRecord, evidence.assignment_id
        )
        attempt = self.repository.get(AttemptRecord, evidence.attempt_id)
        errors: list[str] = []
        expected_digest = evidence_content_digest(
            project_id=evidence.project_id,
            assignment_id=evidence.assignment_id,
            attempt_id=evidence.attempt_id,
            producer_provider_id=evidence.producer_provider_id,
            producer_session_id=evidence.producer_session_id,
            schema_version=evidence.schema_version,
            artifacts=evidence.artifacts,
            summary=evidence.summary,
        )
        if evidence.content_digest != expected_digest:
            errors.append("evidence content digest does not match payload")
        if (
            evidence.producer_provider_id != assignment.provider_id
            or evidence.producer_session_id != assignment.session_id
            or attempt.assignment_id != assignment.assignment_id
        ):
            errors.append("producer identity does not match assignment")
        kinds: set[str] = set()
        root = workspace_path.resolve()
        forbidden_keys = {
            "evaluate",
            "exec",
            "import_module",
            "load_library",
            "trusted_plugin",
        }
        for artifact in evidence.artifacts:
            if not isinstance(artifact.get("kind"), str):
                errors.append("artifact kind is missing")
                continue
            kinds.add(str(artifact["kind"]))
            if any(key in artifact for key in forbidden_keys):
                errors.append("artifact requests trusted-process code loading")
            if artifact.get("execution_requested") is not False:
                errors.append("artifact execution request is prohibited")
            digest = artifact.get("digest")
            if not isinstance(digest, str) or len(digest) != 64:
                errors.append("artifact digest is invalid")
            path_value = artifact.get("path")
            if path_value is not None:
                candidate = Path(str(path_value))
                if not candidate.is_absolute():
                    candidate = root / candidate
                try:
                    candidate.resolve().relative_to(root)
                except ValueError:
                    errors.append("artifact path escapes assigned workspace")
        if not set(assignment.expected_evidence).issubset(kinds):
            errors.append("required evidence kind is missing")
        updated = replace(
            evidence,
            state=EvidenceState.REJECTED if errors else EvidenceState.VALIDATED,
            validation_errors=tuple(errors),
            updated_at=self._now(),
            revision=evidence.revision + 1,
        )
        return self.repository.replace(
            updated, expected_revision=evidence.revision
        )

    def create_review(
        self,
        evidence_id: str,
        reviewer_assignment_id: str,
    ) -> ReviewRecord:
        evidence = self.repository.get(EvidenceBundleRecord, evidence_id)
        producer = self.repository.get(
            AssignmentRecord, evidence.assignment_id
        )
        reviewer = self.repository.get(
            AssignmentRecord, reviewer_assignment_id
        )
        if (
            evidence.state != EvidenceState.VALIDATED
            or reviewer.role != AssignmentRole.REVIEWER
            or not reviewer.read_only
            or reviewer.independence_key == producer.independence_key
            or reviewer.provider_id == producer.provider_id
            and reviewer.session_id == producer.session_id
        ):
            raise PermissionError("review independence or evidence is invalid")
        now = self._now()
        review = ReviewRecord(
            review_id=uuid.uuid4().hex,
            project_id=producer.project_id,
            assignment_id=producer.assignment_id,
            attempt_id=evidence.attempt_id,
            reviewer_assignment_id=reviewer_assignment_id,
            independence_key=reviewer.independence_key,
            state=ReviewState.PENDING,
            findings=(),
            disposition=None,
            created_at=now,
            updated_at=now,
            revision=1,
        )
        self.repository.insert(review)
        return review

    def decide_review(
        self,
        review_id: str,
        *,
        accepted: bool,
        findings: tuple[dict[str, object], ...] = (),
    ) -> tuple[ReviewRecord, AssignmentRecord, WorkItemRecord]:
        normalized_findings = tuple(dict(item) for item in findings)
        return self.repository.decide_review(
            review_id,
            accepted=accepted,
            findings=normalized_findings,
            decided_at=self._now(),
        )

    def create_repair_assignment(
        self, review_id: str
    ) -> AssignmentRecord:
        review = self.repository.get(ReviewRecord, review_id)
        original = self.repository.get(
            AssignmentRecord, review.assignment_id
        )
        work_item = self.repository.get(
            WorkItemRecord, original.work_item_id
        )
        if (
            review.state != ReviewState.REPAIR_REQUIRED
            or original.state != AssignmentState.REPAIR_REQUIRED
            or work_item.state != WorkItemState.REPAIR_REQUIRED
        ):
            raise PermissionError(
                "repair assignment requires a repair-required decision"
            )
        prior_repairs = sum(
            1
            for item in self.repository.list(
                AssignmentRecord, project_id=original.project_id
            )
            if item.usage_policy.get("repair_of_assignment_id")
            == original.assignment_id
        )
        usage_policy = dict(original.usage_policy)
        usage_policy.update(
            {
                "repair_of_assignment_id": original.assignment_id,
                "repair_review_id": review.review_id,
                "repair_ordinal": prior_repairs + 1,
            }
        )
        return self.create_assignment(
            work_item=work_item,
            provider_id=original.provider_id,
            account_id=original.account_id,
            session_id=original.session_id,
            role=original.role,
            model_id=original.model_id,
            workspace_id=original.workspace_id,
            authority_envelope_digest=original.authority_envelope_digest,
            expected_evidence=original.expected_evidence,
            usage_policy=usage_policy,
            independence_key=original.independence_key,
        )

    def _evidence(
        self,
        assignment: AssignmentRecord,
        attempt: AttemptRecord,
        result: AdapterResult,
    ) -> EvidenceBundleRecord:
        now = self._now()
        return EvidenceBundleRecord(
            evidence_bundle_id=uuid.uuid4().hex,
            project_id=assignment.project_id,
            assignment_id=assignment.assignment_id,
            attempt_id=attempt.attempt_id,
            producer_provider_id=assignment.provider_id,
            producer_session_id=assignment.session_id,
            schema_version=1,
            artifacts=result.artifacts,
            summary=result.summary,
            content_digest=evidence_content_digest(
                project_id=assignment.project_id,
                assignment_id=assignment.assignment_id,
                attempt_id=attempt.attempt_id,
                producer_provider_id=assignment.provider_id,
                producer_session_id=assignment.session_id,
                schema_version=1,
                artifacts=result.artifacts,
                summary=result.summary,
            ),
            state=EvidenceState.UNTRUSTED,
            validation_errors=(),
            created_at=now,
            updated_at=now,
            revision=1,
        )

    def _now(self) -> str:
        value = self.clock()
        if value.tzinfo is None:
            raise ValueError("orchestration clock must be timezone aware")
        return value.isoformat()


def evidence_content_digest(
    *,
    project_id: str,
    assignment_id: str,
    attempt_id: str,
    producer_provider_id: str,
    producer_session_id: str,
    schema_version: int,
    artifacts: tuple[dict[str, object], ...],
    summary: str,
) -> str:
    return hashlib.sha256(
        json.dumps(
            {
                "project_id": project_id,
                "assignment_id": assignment_id,
                "attempt_id": attempt_id,
                "producer_provider_id": producer_provider_id,
                "producer_session_id": producer_session_id,
                "schema_version": schema_version,
                "artifacts": artifacts,
                "summary": summary,
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


def authority_envelope_digest(value: dict[str, object]) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode(
            "utf-8"
        )
    ).hexdigest()
