from __future__ import annotations

import hashlib
import json
import math
import os
import uuid
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Callable, NoReturn, TypedDict, cast

from keeper.pass_b.enums import (
    AssignmentRole,
    AssignmentState,
    AttemptState,
    EvidenceReferenceKind,
    EvidenceReferenceState,
    EvidenceState,
    PauseCode,
    ReservationMode,
    ReservationState,
    ReviewState,
    WorkItemState,
    WorkflowState,
)
from keeper.pass_b.models import (
    AssignmentRecord,
    AttemptRecord,
    EvidenceBundleRecord,
    EvidenceReferenceRecord,
    PauseReasonRecord,
    ProviderAccountRecord,
    ProviderRecord,
    ProviderSessionRecord,
    ResumeCheckpointRecord,
    ReviewRecord,
    UsagePoolRecord,
    WorkflowRecord,
    WorkItemRecord,
    WorkspaceReservationRecord,
    WriteReservationRecord,
)
from keeper.pass_b.launch_authority import (
    LaunchAuthority,
    ProjectStatusReader,
    UnavailableLaunchAuthority,
)
from keeper.pass_b.providers import (
    AdapterResult,
    ProviderAdapter,
    assignment_to_adapter,
)
from keeper.pass_b.repository import (
    PassBRepository,
    canonical_evidence_reference_path,
    canonical_scope,
    canonical_workspace_path,
)
from keeper.pass_b.usage_authority import (
    UnavailableUsageResetVerifier,
    UsageResetObservation,
    UsageResetVerifier,
)


class _EvidenceLineageFields(TypedDict):
    source_project_id: str
    source_charter_id: str
    source_charter_revision: int
    source_workflow_id: str
    source_work_item_id: str
    producer_assignment_id: str
    producer_attempt_id: str
    review_target_assignment_id: str


Clock = Callable[[], datetime]


class OrchestrationService:
    def __init__(
        self,
        repository: PassBRepository,
        *,
        clock: Clock | None = None,
        launch_authority: LaunchAuthority | None = None,
        usage_reset_verifier: UsageResetVerifier | None = None,
        project_status: ProjectStatusReader | None = None,
    ) -> None:
        self.repository = repository
        self.clock = clock or (lambda: datetime.now(UTC))
        self.launch_authority = (
            launch_authority or UnavailableLaunchAuthority()
        )
        self.usage_reset_verifier = (
            usage_reset_verifier or UnavailableUsageResetVerifier()
        )
        self.project_status = project_status
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
        sessions = tuple(
            item
            for item in self.repository.list(ProviderSessionRecord)
            if item.provider_id == provider_id
        )
        accounts = tuple(
            item
            for item in self.repository.list(ProviderAccountRecord)
            if item.provider_id == provider_id
        )
        pools = tuple(
            self.repository.get(UsagePoolRecord, item.usage_pool_id)
            for item in accounts
        )
        if (
            descriptor.provider_identity != provider.identity
            or descriptor.classification != provider.classification
            or descriptor.session_model != provider.session_model
            or descriptor.cost_mode != provider.cost_mode
            or provider.concurrency_limit != descriptor.concurrency_limit
            or descriptor.authentication_ready
            != provider.authentication_ready
            or descriptor.cancellation_support
            != provider.cancellation_support
            or descriptor.resume_support != provider.resume_support
            or descriptor.evidence_format != provider.evidence_format
            or descriptor.health != provider.health
            or set(provider.capabilities) != set(descriptor.capabilities)
            or set(provider.tool_support) != set(descriptor.tool_support)
            or set(provider.workspace_support)
            != set(descriptor.workspace_support)
            or any(
                item.model_id != descriptor.model_identity
                for item in sessions
            )
            or any(
                item.identity != descriptor.usage_pool_identity
                for item in pools
            )
        ):
            raise PermissionError("adapter does not match durable provider")
        self.adapters[provider.provider_id] = adapter

    def create_workflow(
        self,
        *,
        project_id: str,
        charter_id: str,
        charter_revision: int,
        strategy: str,
        authority_envelope_digest: str,
        workflow_id: str | None = None,
    ) -> WorkflowRecord:
        self._require_current_charter(
            project_id, charter_id, charter_revision, authority_envelope_digest
        )
        now = self._now()
        record = WorkflowRecord(
            workflow_id=workflow_id or uuid.uuid4().hex,
            project_id=project_id,
            charter_id=charter_id,
            charter_revision=charter_revision,
            strategy=strategy,
            authority_envelope_digest=authority_envelope_digest,
            state=WorkflowState.ACTIVE,
            created_at=now,
            updated_at=now,
            revision=1,
        )
        self.repository.insert_workflow(record)
        return record
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
        workflow = self.repository.get(WorkflowRecord, workflow_id)
        self._require_current_charter(
            workflow.project_id,
            workflow.charter_id,
            workflow.charter_revision,
            workflow.authority_envelope_digest,
        )
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
        self.repository.insert_work_item_bound(record)
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
        workflow = self.repository.get(
            WorkflowRecord, work_item.workflow_id
        )
        self._require_current_charter(
            workflow.project_id,
            workflow.charter_id,
            workflow.charter_revision,
            workflow.authority_envelope_digest,
        )
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
        self.repository.insert_assignment_bound(record, work_item)
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
            canonical_path=canonical_workspace_path(
                path
            ),
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
                canonical_scope(workspace.canonical_path, item)
                for item in scopes
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
                "usage_observation_generation": pool.observation_generation,
                "workspace_id": workspace.workspace_id,
                "workspace_canonical_path": workspace.canonical_path,
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

    def observe_usage_reset(
        self,
        observation: UsageResetObservation,
    ) -> UsagePoolRecord:
        pool = self.repository.get(
            UsagePoolRecord, observation.pool_id
        )
        sessions = tuple(
            item
            for item in self.repository.list(ProviderSessionRecord)
            if item.provider_id == pool.provider_id
            and item.account_id == pool.account_id
        )
        expected_models = tuple(sorted({item.model_id for item in sessions}))
        expected_sessions = tuple(sorted(item.session_id for item in sessions))
        if (
            tuple(sorted(observation.model_ids)) != expected_models
            or tuple(sorted(observation.session_ids)) != expected_sessions
        ):
            raise PermissionError(
                "usage reset observation provider-session scope changed"
            )
        self.usage_reset_verifier.verify(
            pool, observation, now=self.clock()
        )
        return self.repository.observe_usage_reset(
            pool_id=observation.pool_id,
            observation_id=observation.observation_id,
            observation_digest=observation.digest(),
            observed_reset_at=observation.reset_at,
            observation_source=observation.source,
            observation_generation=observation.generation,
            observed_capacity=observation.capacity,
            observed_consumed=observation.consumed,
            observed_remaining=observation.remaining,
            confidence=observation.confidence,
            observed_at=observation.observed_at,
        )

    def create_local_evidence_reference(
        self,
        assignment_id: str,
        source_path: Path,
        *,
        source_evidence_bundle_id: str | None = None,
    ) -> EvidenceReferenceRecord:
        workflow, work_item, assignment = (
            self.repository.assignment_launch_binding(assignment_id)
        )
        resolved = source_path.resolve(strict=True)
        canonical_path = canonical_evidence_reference_path(resolved)
        if not resolved.is_file():
            raise PermissionError("evidence reference must be a regular file")
        content = resolved.read_bytes()
        lineage = self._validate_reference_source_bundle(
            assignment,
            source_evidence_bundle_id,
        )
        now = self._now()
        record = EvidenceReferenceRecord(
            evidence_reference_id=uuid.uuid4().hex,
            project_id=assignment.project_id,
            charter_id=assignment.charter_id,
            charter_revision=assignment.charter_revision,
            workflow_id=workflow.workflow_id,
            work_item_id=work_item.work_item_id,
            assignment_id=assignment.assignment_id,
            source_kind=EvidenceReferenceKind.LOCAL_PROTECTED_ARTIFACT,
            source_identity=canonical_path,
            canonical_source_path=canonical_path,
            source_evidence_bundle_id=source_evidence_bundle_id,
            sha256=hashlib.sha256(content).hexdigest(),
            size_bytes=len(content),
            state=EvidenceReferenceState.VALIDATED,
            validation_error=None,
            created_at=now,
            validated_at=now,
            updated_at=now,
            revision=1,
            **self._reference_lineage_fields(assignment, lineage),
        )
        self.repository.insert(record)
        return record

    def create_remote_evidence_reference(
        self,
        assignment_id: str,
        *,
        source_identity: str,
        sha256: str,
        size_bytes: int,
        source_evidence_bundle_id: str | None = None,
    ) -> EvidenceReferenceRecord:
        workflow, work_item, assignment = (
            self.repository.assignment_launch_binding(assignment_id)
        )
        lineage = self._validate_reference_source_bundle(
            assignment,
            source_evidence_bundle_id,
        )
        now = self._now()
        record = EvidenceReferenceRecord(
            evidence_reference_id=uuid.uuid4().hex,
            project_id=assignment.project_id,
            charter_id=assignment.charter_id,
            charter_revision=assignment.charter_revision,
            workflow_id=workflow.workflow_id,
            work_item_id=work_item.work_item_id,
            assignment_id=assignment.assignment_id,
            source_kind=EvidenceReferenceKind.REMOTE_STRUCTURED_EVIDENCE,
            source_identity=source_identity,
            canonical_source_path=None,
            source_evidence_bundle_id=source_evidence_bundle_id,
            sha256=sha256.casefold(),
            size_bytes=size_bytes,
            state=EvidenceReferenceState.VALIDATED,
            validation_error=None,
            created_at=now,
            validated_at=now,
            updated_at=now,
            revision=1,
            **self._reference_lineage_fields(assignment, lineage),
        )
        self.repository.insert(record)
        return record

    def validate_evidence_reference(
        self,
        evidence_reference_id: str,
        assignment_id: str,
        *,
        expected_source_evidence_bundle_id: str | None = None,
        review_id: str | None = None,
    ) -> EvidenceReferenceRecord:
        record = self.repository.get(
            EvidenceReferenceRecord, evidence_reference_id
        )
        workflow, work_item, assignment = (
            self.repository.assignment_launch_binding(assignment_id)
        )
        expected_binding = (
            assignment.project_id,
            assignment.charter_id,
            assignment.charter_revision,
            workflow.workflow_id,
            work_item.work_item_id,
            assignment.assignment_id,
        )
        actual_binding = (
            record.project_id,
            record.charter_id,
            record.charter_revision,
            record.workflow_id,
            record.work_item_id,
            record.assignment_id,
        )
        if actual_binding != expected_binding:
            raise PermissionError(
                "evidence reference does not match assignment context"
            )
        if record.state != EvidenceReferenceState.VALIDATED:
            raise PermissionError("evidence reference is not validated")
        if (
            record.consumed_by_review_id is not None
            and record.consumed_by_review_id != review_id
        ):
            raise PermissionError("evidence reference was already consumed")
        if (
            expected_source_evidence_bundle_id is not None
            and record.source_evidence_bundle_id
            != expected_source_evidence_bundle_id
        ):
            raise PermissionError(
                "evidence reference does not match reviewed evidence"
            )
        lineage = self._validate_reference_source_bundle(
            assignment,
            record.source_evidence_bundle_id,
        )
        if self._reference_lineage_fields(assignment, lineage) != {
            "source_project_id": record.source_project_id,
            "source_charter_id": record.source_charter_id,
            "source_charter_revision": record.source_charter_revision,
            "source_workflow_id": record.source_workflow_id,
            "source_work_item_id": record.source_work_item_id,
            "producer_assignment_id": record.producer_assignment_id,
            "producer_attempt_id": record.producer_attempt_id,
            "review_target_assignment_id": record.review_target_assignment_id,
        }:
            raise PermissionError("evidence reference source lineage changed")
        if (
            record.source_kind
            == EvidenceReferenceKind.LOCAL_PROTECTED_ARTIFACT
        ):
            try:
                source_path = Path(cast(str, record.canonical_source_path))
                canonical_path = canonical_evidence_reference_path(source_path)
                content = source_path.read_bytes()
            except (OSError, PermissionError, RuntimeError) as error:
                self._reject_evidence_reference(record, str(error))
            if (
                canonical_path != record.canonical_source_path
                or len(content) != record.size_bytes
                or hashlib.sha256(content).hexdigest() != record.sha256
            ):
                self._reject_evidence_reference(
                    record, "evidence reference content changed"
                )
        return record

    def _validate_reference_source_bundle(
        self,
        assignment: AssignmentRecord,
        evidence_bundle_id: str | None,
    ) -> tuple[
        EvidenceBundleRecord,
        AssignmentRecord,
        AttemptRecord,
        WorkItemRecord,
        WorkflowRecord,
    ] | None:
        if evidence_bundle_id is None:
            if (
                assignment.role == AssignmentRole.REVIEWER
                or assignment.usage_policy.get("review_of_assignment_id")
                is not None
            ):
                raise PermissionError(
                    "review evidence reference requires an exact source bundle"
                )
            return None
        evidence = self.repository.get(
            EvidenceBundleRecord, evidence_bundle_id
        )
        producer = self.repository.get(
            AssignmentRecord, evidence.assignment_id
        )
        producer_attempt = self.repository.get(
            AttemptRecord, evidence.attempt_id
        )
        producer_work_item = self.repository.get(
            WorkItemRecord, producer.work_item_id
        )
        producer_workflow = self.repository.get(
            WorkflowRecord, producer.workflow_id
        )
        review_target = assignment.usage_policy.get(
            "review_of_assignment_id"
        )
        if (
            evidence.project_id != assignment.project_id
            or evidence.state != EvidenceState.VALIDATED
            or evidence.assignment_id != producer.assignment_id
            or evidence.attempt_id != producer_attempt.attempt_id
            or producer_attempt.assignment_id != producer.assignment_id
            or producer_attempt.state != AttemptState.COMPLETED
            or review_target != producer.assignment_id
            or producer.project_id != assignment.project_id
            or producer.charter_id != assignment.charter_id
            or producer.charter_revision != assignment.charter_revision
            or producer.workflow_id != assignment.workflow_id
            or producer_work_item.project_id != producer.project_id
            or producer_work_item.charter_id != producer.charter_id
            or producer_work_item.charter_revision
            != producer.charter_revision
            or producer_work_item.workflow_id != producer.workflow_id
            or producer_workflow.project_id != producer.project_id
            or producer_workflow.charter_id != producer.charter_id
            or producer_workflow.charter_revision
            != producer.charter_revision
        ):
            raise PermissionError(
                "evidence reference source lineage is invalid"
            )
        return (
            evidence,
            producer,
            producer_attempt,
            producer_work_item,
            producer_workflow,
        )

    @staticmethod
    def _reference_lineage_fields(
        assignment: AssignmentRecord,
        lineage: tuple[
            EvidenceBundleRecord,
            AssignmentRecord,
            AttemptRecord,
            WorkItemRecord,
            WorkflowRecord,
        ] | None,
    ) -> _EvidenceLineageFields:
        if lineage is None:
            return {
                "source_project_id": "",
                "source_charter_id": "",
                "source_charter_revision": 0,
                "source_workflow_id": "",
                "source_work_item_id": "",
                "producer_assignment_id": "",
                "producer_attempt_id": "",
                "review_target_assignment_id": "",
            }
        evidence, producer, producer_attempt, work_item, workflow = lineage
        return {
            "source_project_id": evidence.project_id,
            "source_charter_id": producer.charter_id,
            "source_charter_revision": producer.charter_revision,
            "source_workflow_id": workflow.workflow_id,
            "source_work_item_id": work_item.work_item_id,
            "producer_assignment_id": producer.assignment_id,
            "producer_attempt_id": producer_attempt.attempt_id,
            "review_target_assignment_id": str(
                assignment.usage_policy["review_of_assignment_id"]
            ),
        }

    def _reject_evidence_reference(
        self,
        record: EvidenceReferenceRecord,
        detail: str,
    ) -> NoReturn:
        rejected = replace(
            record,
            state=EvidenceReferenceState.REJECTED,
            validation_error=detail,
            updated_at=self._now(),
            revision=record.revision + 1,
        )
        self.repository.replace(rejected, expected_revision=record.revision)
        raise PermissionError(detail)

    def run_assignment(
        self,
        assignment_id: str,
        workspace_path: Path,
        *,
        authority_attempt_id: str,
        global_context: dict[str, object],
        task_context: dict[str, object],
        evidence_reference_ids: tuple[str, ...] = (),
        side_effect_class: str = "REVERSIBLE_WORKSPACE_WRITE",
        after_launch_claim: Callable[[], None] | None = None,
    ) -> EvidenceBundleRecord:
        workflow, work_item, assignment = (
            self.repository.assignment_launch_binding(assignment_id)
        )
        if any(
            "evidence_reference" in key.casefold()
            for key in task_context
        ):
            raise PermissionError(
                "raw evidence references are prohibited; use durable IDs"
            )
        references = tuple(
            self.validate_evidence_reference(item, assignment_id)
            for item in evidence_reference_ids
        )
        adapter = self.adapters.get(assignment.provider_id)
        if adapter is None:
            raise RuntimeError("assignment provider adapter is unavailable")
        workspaces = [
            item
            for item in self.repository.list(
                WorkspaceReservationRecord,
                project_id=assignment.project_id,
            )
            if item.assignment_id == assignment.assignment_id
            and item.state == ReservationState.ACTIVE
        ]
        if len(workspaces) != 1:
            raise PermissionError(
                "assignment needs exactly one active workspace"
            )
        workspace = workspaces[0]
        if (
            workspace.workspace_id != assignment.workspace_id
            or canonical_workspace_path(
                workspace_path
            )
            != workspace.canonical_path
        ):
            raise PermissionError(
                "launch workspace does not match the durable reservation"
            )
        (
            delivery_context,
            delivery_files,
            delivery_manifest_digest,
        ) = self._prepare_evidence_delivery(references, workspace_path)
        provider = self.repository.get(
            ProviderRecord, assignment.provider_id
        )
        authorization = self.launch_authority.authorize(
            workflow,
            work_item,
            assignment,
            provider,
            workspace,
            authority_attempt_id,
        )
        usage_rows = [
            item
            for item in self.repository.usage_reservations(
                assignment.assignment_id
            )
            if item["state"] == "ACTIVE"
        ]
        reservation_required = bool(
            assignment.usage_policy.get("reservation_required", True)
        )
        if reservation_required and len(usage_rows) != 1:
            raise PermissionError(
                "launch requires exactly one active usage reservation"
            )
        usage_reservation_id = (
            str(usage_rows[0]["reservation_id"])
            if usage_rows
            else None
        )
        now = self._now()
        attempt = AttemptRecord(
            attempt_id=uuid.uuid4().hex,
            assignment_id=assignment_id,
            authority_attempt_id=authority_attempt_id,
            launch_token=authorization.launch_token,
            state=AttemptState.RESERVED,
            external_execution_id=None,
            side_effect_class=side_effect_class,
            started_at=None,
            finished_at=None,
            last_error=None,
            created_at=now,
            updated_at=now,
            revision=1,
            workspace_reservation_id=workspace.workspace_reservation_id,
            usage_reservation_id=usage_reservation_id,
            launch_plan_digest=authorization.launch_plan_digest,
            session_slot_claimed=True,
        )
        self.repository.reserve_attempt(
            attempt,
            expected_workflow=workflow,
            expected_work_item=work_item,
            expected_assignment=assignment,
        )
        claimed = self.repository.claim_launch(attempt.attempt_id, self._now())
        if after_launch_claim is not None:
            after_launch_claim()
        if canonical_workspace_path(workspace_path) != workspace.canonical_path:
            raise PermissionError(
                "launch workspace became unsafe before adapter invocation"
            )
        references = tuple(
            self.validate_evidence_reference(item, assignment_id)
            for item in evidence_reference_ids
        )
        self._verify_evidence_delivery(
            delivery_files,
            workspace_path,
            delivery_manifest_digest,
        )
        adapter_task_context = dict(task_context)
        if references:
            adapter_task_context["keeper_evidence_references"] = list(
                delivery_context
            )
            adapter_task_context["keeper_evidence_manifest"] = (
                ".keeper-input/evidence-references.json"
            )
        request = assignment_to_adapter(
            assignment,
            claimed.attempt_id,
            authority_attempt_id,
            workspace_path,
            global_context=dict(global_context),
            task_context=adapter_task_context,
        )
        try:
            result = self.launch_authority.launch(
                authorization, request, adapter
            )
        except BaseException:
            # The durable claim deliberately remains ambiguous for restart recovery.
            raise
        self._verify_evidence_delivery(
            delivery_files,
            workspace_path,
            delivery_manifest_digest,
        )
        for item in evidence_reference_ids:
            self.validate_evidence_reference(item, assignment_id)
        if (
            result.usage is not None
            and (
                not math.isfinite(result.usage)
                or result.usage < 0
                or not usage_rows
                or result.usage > float(usage_rows[0]["amount"])
            )
        ):
            raise PermissionError(
                "provider usage exceeds the durable launch reservation"
            )
        running = self.repository.mark_running(
            claimed.attempt_id, result.external_execution_id, self._now()
        )
        evidence = self._evidence(assignment, running, result)
        self.repository.complete_attempt(
            running.attempt_id, evidence, self._now()
        )
        return evidence

    def _prepare_evidence_delivery(
        self,
        references: tuple[EvidenceReferenceRecord, ...],
        workspace_path: Path,
    ) -> tuple[
        tuple[dict[str, object], ...],
        dict[str, tuple[Path, str, int]],
        str | None,
    ]:
        if not references:
            return (), {}, None
        canonical_workspace_path(workspace_path)
        workspace = workspace_path.resolve(strict=True)
        delivery_root = workspace / ".keeper-input"
        try:
            delivery_root.mkdir(mode=0o700, exist_ok=False)
        except OSError as error:
            raise PermissionError(
                "trusted evidence-delivery directory is unavailable"
            ) from error
        context: list[dict[str, object]] = []
        copied: dict[str, tuple[Path, str, int]] = {}
        for reference in references:
            item: dict[str, object] = {
                "reference_id": reference.evidence_reference_id,
                "reference_revision": reference.revision,
                "classification": reference.source_kind,
                "source_identity": (
                    reference.source_identity
                    if reference.source_kind
                    == EvidenceReferenceKind.REMOTE_STRUCTURED_EVIDENCE
                    else f"protected:{reference.evidence_reference_id}"
                ),
                "project_id": reference.project_id,
                "charter_id": reference.charter_id,
                "charter_revision": reference.charter_revision,
                "workflow_id": reference.workflow_id,
                "work_item_id": reference.work_item_id,
                "producer_assignment_id": reference.producer_assignment_id,
                "producer_attempt_id": reference.producer_attempt_id,
                "reviewed_assignment_id": (
                    reference.review_target_assignment_id
                ),
                "sha256": reference.sha256,
                "size_bytes": reference.size_bytes,
                "validated_at": reference.validated_at,
                "local_or_remote": (
                    "LOCAL"
                    if reference.source_kind
                    == EvidenceReferenceKind.LOCAL_PROTECTED_ARTIFACT
                    else "REMOTE"
                ),
            }
            if (
                reference.source_kind
                == EvidenceReferenceKind.LOCAL_PROTECTED_ARTIFACT
            ):
                source = Path(cast(str, reference.canonical_source_path))
                content = source.read_bytes()
                if (
                    len(content) != reference.size_bytes
                    or hashlib.sha256(content).hexdigest()
                    != reference.sha256
                ):
                    raise PermissionError(
                        "local evidence changed before trusted delivery"
                    )
                destination = (
                    delivery_root
                    / f"{reference.evidence_reference_id}.evidence"
                )
                try:
                    descriptor = os.open(
                        destination,
                        os.O_CREAT | os.O_EXCL | os.O_WRONLY,
                        0o400,
                    )
                    with os.fdopen(descriptor, "wb") as stream:
                        stream.write(content)
                        stream.flush()
                        os.fsync(stream.fileno())
                except OSError as error:
                    raise PermissionError(
                        "immutable evidence review copy could not be created"
                    ) from error
                relative = destination.relative_to(workspace).as_posix()
                item["review_copy"] = relative
                copied[reference.evidence_reference_id] = (
                    destination,
                    reference.sha256,
                    reference.size_bytes,
                )
            context.append(item)
        manifest = delivery_root / "evidence-references.json"
        manifest_bytes = json.dumps(
            context,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        try:
            descriptor = os.open(
                manifest,
                os.O_CREAT | os.O_EXCL | os.O_WRONLY,
                0o400,
            )
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(manifest_bytes)
                stream.flush()
                os.fsync(stream.fileno())
        except OSError as error:
            raise PermissionError(
                "structured evidence-delivery manifest could not be created"
            ) from error
        return (
            tuple(context),
            copied,
            hashlib.sha256(manifest_bytes).hexdigest(),
        )

    @staticmethod
    def _verify_evidence_delivery(
        copied: dict[str, tuple[Path, str, int]],
        workspace_path: Path,
        manifest_digest: str | None,
    ) -> None:
        if manifest_digest is None:
            return
        canonical_workspace_path(workspace_path)
        workspace = workspace_path.resolve(strict=True)
        manifest = workspace / ".keeper-input" / "evidence-references.json"
        try:
            manifest_content = manifest.read_bytes()
        except OSError as error:
            raise PermissionError(
                "trusted evidence-delivery manifest is unavailable"
            ) from error
        if hashlib.sha256(manifest_content).hexdigest() != manifest_digest:
            raise PermissionError(
                "trusted evidence-delivery manifest was modified"
            )
        for destination, digest, size in copied.values():
            try:
                content = destination.read_bytes()
            except OSError as error:
                raise PermissionError(
                    "immutable evidence review copy is unavailable"
                ) from error
            if (
                len(content) != size
                or hashlib.sha256(content).hexdigest() != digest
            ):
                raise PermissionError(
                    "immutable evidence review copy was modified"
                )

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
        root = workspace_path.resolve(strict=True)
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
                    resolved = candidate.resolve(strict=True)
                    resolved.relative_to(root)
                except (FileNotFoundError, ValueError):
                    errors.append("artifact path escapes assigned workspace")
                    continue
                if not resolved.is_file():
                    errors.append("artifact path is not a regular file")
                    continue
                if hashlib.sha256(resolved.read_bytes()).hexdigest() != digest:
                    errors.append("artifact digest does not match file content")
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
        reviewer_evidence_id: str,
        *,
        evidence_reference_id: str | None = None,
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
            or (
                reviewer.provider_id == producer.provider_id
                and reviewer.session_id == producer.session_id
            )
        ):
            raise PermissionError("review independence or evidence is invalid")
        reviewer_evidence = self.repository.get(
            EvidenceBundleRecord, reviewer_evidence_id
        )
        reviewer_attempt = self.repository.get(
            AttemptRecord, reviewer_evidence.attempt_id
        )
        disposition, findings = _review_outcome(reviewer_evidence)
        if (
            reviewer_evidence.state != EvidenceState.VALIDATED
            or reviewer_evidence.assignment_id != reviewer.assignment_id
            or reviewer_attempt.assignment_id != reviewer.assignment_id
            or reviewer_attempt.state != AttemptState.COMPLETED
            or reviewer.project_id != producer.project_id
            or reviewer.charter_id != producer.charter_id
            or reviewer.charter_revision != producer.charter_revision
            or reviewer.usage_policy.get("review_of_assignment_id")
            != producer.assignment_id
        ):
            raise PermissionError("review independence or evidence is invalid")
        now = self._now()
        reference = (
            self.validate_evidence_reference(
                evidence_reference_id,
                reviewer_assignment_id,
                expected_source_evidence_bundle_id=evidence_id,
            )
            if evidence_reference_id is not None
            else None
        )
        review = ReviewRecord(
            review_id=uuid.uuid4().hex,
            project_id=producer.project_id,
            assignment_id=producer.assignment_id,
            attempt_id=evidence.attempt_id,
            reviewer_assignment_id=reviewer_assignment_id,
            independence_key=reviewer.independence_key,
            state=ReviewState.PENDING,
            findings=findings,
            disposition=disposition,
            created_at=now,
            updated_at=now,
            revision=1,
            producer_evidence_bundle_id=evidence.evidence_bundle_id,
            reviewer_attempt_id=reviewer_attempt.attempt_id,
            reviewer_evidence_bundle_id=reviewer_evidence.evidence_bundle_id,
            consumed_evidence_reference_id=(
                reference.evidence_reference_id
                if reference is not None
                else None
            ),
            consumed_evidence_reference_revision=(
                reference.revision + 1 if reference is not None else None
            ),
        )
        if reference is None:
            self.repository.insert(review)
        else:
            self.repository.insert_review_with_reference(
                review,
                reference,
                consumed_at=now,
            )
        return review

    def decide_review(
        self,
        review_id: str,
    ) -> tuple[ReviewRecord, AssignmentRecord, WorkItemRecord]:
        review = self.repository.get(ReviewRecord, review_id)
        if review.consumed_evidence_reference_id is not None:
            self.validate_evidence_reference(
                review.consumed_evidence_reference_id,
                review.reviewer_assignment_id,
                expected_source_evidence_bundle_id=(
                    review.producer_evidence_bundle_id
                ),
                review_id=review.review_id,
            )
        return self.repository.decide_review(
            review_id,
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

    def _require_current_charter(
        self,
        project_id: str,
        charter_id: str,
        charter_revision: int,
        authority_envelope_digest: str,
    ) -> None:
        if self.project_status is None:
            return
        status = self.project_status(project_id)
        project = status.get("project_summary")
        charter = status.get("active_charter")
        if (
            not isinstance(project, dict)
            or not isinstance(charter, dict)
            or project.get("project_id") != project_id
            or project.get("state") != "ACTIVE"
            or project.get("active_charter_id") != charter_id
            or project.get("active_charter_revision") != charter_revision
            or charter.get("project_id") != project_id
            or charter.get("charter_id") != charter_id
            or charter.get("revision") != charter_revision
            or charter.get("status") != "ACTIVE"
            or not charter.get("founder_approval_record_id")
            or not charter.get("founder_approval_identity")
            or not charter.get("founder_authorization_capability_digest")
            or not isinstance(charter.get("authority_envelope"), dict)
            or authority_envelope_digest
            != authority_envelope_digest_for_status(charter)
        ):
            raise PermissionError(
                "workflow is not bound to the current Founder-approved charter"
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


def authority_envelope_digest_for_status(charter: dict[str, Any]) -> str:
    envelope = charter.get("authority_envelope")
    if not isinstance(envelope, dict):
        raise PermissionError("current charter authority envelope is malformed")
    return authority_envelope_digest(cast(dict[str, object], envelope))

def authority_envelope_digest(value: dict[str, object]) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode(
            "utf-8"
        )
    ).hexdigest()


def _review_outcome(
    evidence: EvidenceBundleRecord,
) -> tuple[str, tuple[dict[str, object], ...]]:
    reports = [
        artifact
        for artifact in evidence.artifacts
        if artifact.get("kind") == "structured-report"
    ]
    if len(reports) != 1:
        raise PermissionError(
            "reviewer evidence needs one structured review report"
        )
    report = reports[0]
    disposition = report.get("review_disposition")
    findings = report.get("findings")
    if disposition not in {"ACCEPTED", "REPAIR_REQUIRED"}:
        raise PermissionError("review disposition is missing or invalid")
    if not isinstance(findings, list) or any(
        not isinstance(item, dict) for item in findings
    ):
        raise PermissionError("review findings are malformed")
    return str(disposition), tuple(dict(item) for item in findings)
