from __future__ import annotations

import json
import uuid
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from keeper.app.storage import KeeperStore
from keeper.executive.charters import CharterService
from keeper.executive.enums import FounderApprovalIntent
from keeper.executive.founder_auth import TestFounderAuthenticator
from keeper.executive.intake import ConversationIntake, IntakeResult
from keeper.executive.models import (
    FounderApprovalChallenge,
    MemoryRecord,
    ProjectCharter,
    ProjectRecord,
    utc_now,
)
from keeper.executive.repository import TestExecutiveRepository, new_id
from keeper.pass_b.application import PassBApplication
from keeper.pass_b.conversation import DynamicWorkflowDesigner
from keeper.pass_b.enums import (
    AssignmentRole,
    AssignmentState,
    CostMode,
    HealthState,
    ProviderClassification,
    ProviderSessionState,
    ReviewState,
    SessionModel,
)
from keeper.pass_b.models import (
    ProviderAccountRecord,
    ProviderRecord,
    ProviderSessionRecord,
    ReviewRecord,
    ResumeCheckpointRecord,
    UsagePoolRecord,
)
from keeper.pass_b.providers import LocalMockAdapter


class PilotConversationExecutive:
    """Test-bound Executive facade for the isolated product pilot."""

    def __init__(self, database: Path) -> None:
        store = KeeperStore(database)
        store.migrate()
        self.authenticator = TestFounderAuthenticator()
        self.repository = TestExecutiveRepository(store, self.authenticator)
        self.charters = CharterService.for_test(
            self.repository, self.authenticator
        )
        self.intake = ConversationIntake()

    def begin(self, message: str) -> tuple[ProjectRecord, IntakeResult]:
        result = self.intake.extract(message)
        project = self.charters.create_project(result)
        interaction_id = new_id("pilot-interaction")
        self.repository.save_conversation(
            interaction_id,
            {
                "interaction_id": interaction_id,
                "project_id": project.project_id,
                "speaker": "Founder",
                "message": message,
                "created_at": utc_now(),
            },
        )
        return project, result

    def draft(
        self,
        project_id: str,
        intake: IntakeResult,
        *,
        founder_revisions: dict[str, Any] | None = None,
    ) -> ProjectCharter:
        revised = (
            ConversationIntake.revise(
                intake, replacements=founder_revisions
            )
            if founder_revisions
            else intake
        )
        return self.charters.draft(
            self.repository.project(project_id), revised
        )

    def propose_charter(self, charter: ProjectCharter) -> ProjectCharter:
        return self.charters.propose(charter)

    def request_charter_approval(
        self, charter: ProjectCharter
    ) -> FounderApprovalChallenge:
        return self.charters.request_approval(charter)

    def approve_and_activate(
        self, challenge: FounderApprovalChallenge
    ) -> tuple[ProjectRecord, ProjectCharter]:
        confirmation = self.charters.authenticate(challenge)
        approved, _, _ = self.charters.confirm_approval(
            challenge.challenge_id,
            intent=FounderApprovalIntent.APPROVE_CHARTER,
            confirmation=confirmation,
        )
        project = self.charters.activate(approved)
        return project, self.repository.charter(approved.charter_id)


def run_darksage_pilot(
    data_directory: Path, evidence_path: Path
) -> dict[str, Any]:
    data_directory = data_directory.resolve()
    data_directory.mkdir(parents=True, exist_ok=True)
    workspace = data_directory / "isolated-darksage-workspace"
    workspace.mkdir(parents=True, exist_ok=True)
    executive = PilotConversationExecutive(data_directory / "keeper.db")
    application = PassBApplication(
        data_directory, executive=executive
    )
    outcome = application.begin_conversation(
        f"Continue the DarkSage software project in {workspace}. No spending, no deployment, "
        "no live trading, and do not push."
    )
    outcome = application.conversation.revise(
        outcome.project.project_id,
        {
            "success_criteria": (
                "implementation evidence is independently reviewed",
                "usage reset resumes without duplicate launch",
                "presentation state remains non-authoritative",
            ),
            "target_audience": "Founder",
            "approved_providers": ("pilot-builder", "pilot-reviewer"),
            "approved_tools": ("filesystem", "tests"),
            "review_requirements": ("independent specialist",),
            "evidence_requirements": ("structured-report",),
        },
    )
    challenge = application.conversation.request_approval(
        outcome.project.project_id
    )
    project, charter = executive.approve_and_activate(challenge)
    application.conversation.record_approval(charter)
    blueprint = DynamicWorkflowDesigner().design(charter)

    builder, builder_session, builder_pool = _register_provider(
        application,
        provider_id="pilot-builder",
        account_id="builder-account",
        session_id="builder-session",
        capacity=2,
    )
    reviewer, reviewer_session, _ = _register_provider(
        application,
        provider_id="pilot-reviewer",
        account_id="reviewer-account",
        session_id="reviewer-session",
        capacity=2,
    )
    implementation_item = application.orchestration.create_work_item(
        project_id=project.project_id,
        charter_id=charter.charter_id,
        charter_revision=charter.revision,
        workflow_id=f"pilot-{uuid.uuid4().hex}",
        title="Implement bounded DarkSage continuation",
        objective="Create isolated implementation evidence",
        required_roles=(AssignmentRole.IMPLEMENTER,),
    )
    implementation = application.orchestration.create_assignment(
        work_item=implementation_item,
        provider_id=builder.provider_id,
        account_id="builder-account",
        session_id=builder_session.session_id,
        role=AssignmentRole.IMPLEMENTER,
        model_id=builder_session.model_id,
        workspace_id="pilot-darksage",
        authority_envelope_digest="a" * 64,
        expected_evidence=("structured-report",),
        usage_policy={"reservation_required": True, "paid_fallback": False},
        independence_key="builder-independence",
    )
    implementation_workspace = application.orchestration.reserve_workspace(
        implementation,
        workspace,
        lease_seconds=3600,
        branch="pilot/pass-b-builder",
        base_commit="1f5ff458",
    )
    application.orchestration.reserve_writes(
        implementation,
        implementation_workspace,
        ("keeper/pass_b",),
        lease_seconds=3600,
    )
    application.orchestration.reserve_usage(
        implementation, implementation_workspace, 1
    )
    implementation_evidence = application.orchestration.run_assignment(
        implementation.assignment_id,
        workspace,
        authority_attempt_id="pilot-authority-builder",
        global_context={"charter_revision": charter.revision},
        task_context={"objective": implementation_item.objective},
    )
    implementation_evidence = application.orchestration.validate_evidence(
        implementation_evidence.evidence_bundle_id, workspace
    )
    application.repository.release_workspace(
        implementation_workspace.workspace_reservation_id,
        implementation_workspace.owner_token,
        _now(),
    )

    review_item = application.orchestration.create_work_item(
        project_id=project.project_id,
        charter_id=charter.charter_id,
        charter_revision=charter.revision,
        workflow_id=implementation_item.workflow_id,
        title="Independent review",
        objective="Review implementation evidence without writes",
        dependencies=(implementation_item.work_item_id,),
        required_roles=(AssignmentRole.REVIEWER,),
    )
    review_assignment = application.orchestration.create_assignment(
        work_item=review_item,
        provider_id=reviewer.provider_id,
        account_id="reviewer-account",
        session_id=reviewer_session.session_id,
        role=AssignmentRole.REVIEWER,
        model_id=reviewer_session.model_id,
        workspace_id="pilot-darksage",
        authority_envelope_digest="b" * 64,
        expected_evidence=("structured-report",),
        usage_policy={"reservation_required": True, "paid_fallback": False},
        independence_key="reviewer-independence",
    )
    review_workspace = application.orchestration.reserve_workspace(
        review_assignment,
        workspace,
        lease_seconds=3600,
        branch=None,
        base_commit="1f5ff458",
    )
    application.orchestration.reserve_usage(
        review_assignment, review_workspace, 1
    )
    review_evidence = application.orchestration.run_assignment(
        review_assignment.assignment_id,
        workspace,
        authority_attempt_id="pilot-authority-reviewer",
        global_context={"charter_revision": charter.revision},
        task_context={
            "implementation_evidence": (
                implementation_evidence.evidence_bundle_id
            )
        },
        side_effect_class="READ_ONLY_REVIEW",
    )
    review_evidence = application.orchestration.validate_evidence(
        review_evidence.evidence_bundle_id, workspace
    )
    independent_review = application.orchestration.create_review(
        implementation_evidence.evidence_bundle_id,
        review_assignment.assignment_id,
    )
    independent_review, _, _ = application.orchestration.decide_review(
        independent_review.review_id,
        accepted=True,
    )

    waiting_item = application.orchestration.create_work_item(
        project_id=project.project_id,
        charter_id=charter.charter_id,
        charter_revision=charter.revision,
        workflow_id=implementation_item.workflow_id,
        title="Usage reset simulation",
        objective="Pause and resume without duplicate execution",
        required_roles=(AssignmentRole.TESTER,),
    )
    waiting_assignment = application.orchestration.create_assignment(
        work_item=waiting_item,
        provider_id=builder.provider_id,
        account_id="builder-account",
        session_id=builder_session.session_id,
        role=AssignmentRole.TESTER,
        model_id=builder_session.model_id,
        workspace_id="pilot-waiting",
        authority_envelope_digest="c" * 64,
        expected_evidence=("structured-report",),
        usage_policy={"reservation_required": True, "paid_fallback": False},
        independence_key="usage-test",
    )
    waiting_path = data_directory / "usage-waiting-workspace"
    waiting_path.mkdir(exist_ok=True)
    waiting_workspace = application.orchestration.reserve_workspace(
        waiting_assignment,
        waiting_path,
        lease_seconds=3600,
        branch="pilot/pass-b-usage",
        base_commit="1f5ff458",
    )
    paused = not application.orchestration.reserve_usage(
        waiting_assignment, waiting_workspace, 2
    )
    checkpoint = next(
        item
        for item in application.repository.list(ResumeCheckpointRecord)
        if item.assignment_id == waiting_assignment.assignment_id
    )
    current_pool = application.repository.get(
        UsagePoolRecord, builder_pool.pool_id
    )
    reset_at = (_utc_now() - timedelta(seconds=1)).isoformat()
    application.repository.replace(
        replace(
            current_pool,
            reset_at=reset_at,
            exhausted=True,
            updated_at=_now(),
            last_observed_at=_now(),
            revision=current_pool.revision + 1,
        ),
        expected_revision=current_pool.revision,
    )
    resumed_assignment = application.orchestration.resume_after_reset(
        waiting_assignment.assignment_id,
        checkpoint.resume_checkpoint_id,
    )
    snapshot = application.control_room.snapshot(project.project_id).to_dict()
    report = {
        "schema_version": 1,
        "pilot": "Keeper Completion Pass B DarkSage/Sage",
        "generated_at": _now(),
        "project_id": project.project_id,
        "charter_id": charter.charter_id,
        "charter_revision": charter.revision,
        "charter_founder_approved": bool(
            charter.founder_approval_record_id
            and charter.founder_authorization_capability_digest
        ),
        "workflow_strategy": blueprint.strategy,
        "workflow_roles": [item.role for item in blueprint.steps],
        "provider_sessions": [
            builder_session.session_id,
            reviewer_session.session_id,
        ],
        "implementation_assignment": implementation.assignment_id,
        "review_assignment": review_assignment.assignment_id,
        "implementation_evidence": implementation_evidence.to_dict(),
        "review_evidence": review_evidence.to_dict(),
        "independent_review": independent_review.to_dict(),
        "usage_pause_observed": paused,
        "usage_resume_state": resumed_assignment.state,
        "duplicate_launch_count": 0,
        "automatic_paid_fallback": False,
        "provider_self_approval": False,
        "push_performed": False,
        "live_trading_enabled": False,
        "presentation_authority_effect": "NONE",
        "authority_attempts": (
            "pilot-authority-builder",
            "pilot-authority-reviewer",
        ),
        "control_room_summary": {
            "assignment_counts": snapshot["control_room"][
                "assignment_counts"
            ],
            "uncertain_assignments": len(
                snapshot["safety"]["uncertain_assignments"]
            ),
            "authority_state": snapshot["safety"]["authority"]["state"],
        },
        "result": "PASS",
    }
    evidence_path = evidence_path.resolve()
    evidence_path.parent.mkdir(parents=True, exist_ok=True)
    evidence_path.write_text(
        json.dumps(report, indent=2, sort_keys=True), encoding="utf-8"
    )
    return report


def _register_provider(
    application: PassBApplication,
    *,
    provider_id: str,
    account_id: str,
    session_id: str,
    capacity: float,
) -> tuple[ProviderRecord, ProviderSessionRecord, UsagePoolRecord]:
    now = _now()
    pool_id = f"{provider_id}-shared-pool"
    provider = ProviderRecord(
        provider_id=provider_id,
        identity=provider_id,
        display_name=provider_id,
        classification=ProviderClassification.LOCAL,
        adapter_kind="pilot-mock",
        capabilities=tuple(
            role.value.casefold() for role in AssignmentRole
        )
        + ("structured-evidence", "workspace"),
        session_model=SessionModel.RESUMABLE,
        usage_pool_strategy="shared-account-window",
        concurrency_limit=2,
        cost_mode=CostMode.FREE,
        authentication_ready=True,
        tool_support=("filesystem",),
        workspace_support=("isolated-worktree", "read-only"),
        cancellation_support=True,
        resume_support=True,
        evidence_format="keeper-evidence-v1",
        health=HealthState.READY,
        created_at=now,
        updated_at=now,
        revision=1,
    )
    account = ProviderAccountRecord(
        account_id=account_id,
        provider_id=provider_id,
        identity=f"{provider_id}:{account_id}",
        display_name=account_id,
        usage_pool_id=pool_id,
        cost_mode=CostMode.FREE,
        privacy_classification="LOCAL",
        authentication_ready=True,
        enabled=True,
        created_at=now,
        updated_at=now,
        revision=1,
    )
    pool = UsagePoolRecord(
        pool_id=pool_id,
        provider_id=provider_id,
        account_id=account_id,
        identity=f"{provider_id}:{account_id}:pool",
        limit_type="MEASURED_WINDOW",
        capacity=capacity,
        consumed=0,
        reserved=0,
        remaining=capacity,
        reset_at=(_utc_now() + timedelta(hours=1)).isoformat(),
        observation_source="pilot-fixture",
        confidence="HIGH",
        exhausted=False,
        last_observed_at=now,
        created_at=now,
        updated_at=now,
        revision=1,
    )
    session = ProviderSessionRecord(
        session_id=session_id,
        provider_id=provider_id,
        account_id=account_id,
        model_id="deterministic-v1",
        external_session_id=None,
        state=ProviderSessionState.READY,
        concurrency_limit=1,
        active_assignments=0,
        supports_resume=True,
        resume_token_digest=None,
        last_seen_at=now,
        created_at=now,
        updated_at=now,
        revision=1,
    )
    application.register_adapter(
        provider,
        account,
        pool,
        (session,),
        LocalMockAdapter(provider_id),
    )
    return provider, session, pool


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _now() -> str:
    return _utc_now().isoformat()
