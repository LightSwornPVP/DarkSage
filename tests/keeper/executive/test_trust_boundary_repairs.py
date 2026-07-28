from __future__ import annotations

from dataclasses import replace
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from keeper.app.storage import KeeperStore
from keeper.executive.authority import AuthorityEvaluator, TrustedActionClassifier
from keeper.executive.charters import CharterService
from keeper.executive.enums import ActionCategory, ApprovalKind
from keeper.executive.intake import ConversationIntake
from keeper.executive.models import (
    ProjectCharter,
    ProjectRecord,
    ProposedAction,
    SpecialistProfile,
    utc_now,
)
from keeper.executive.planning import WorkflowPlanner
from keeper.executive.repository import ExecutiveRepository


def _proposed(
    tmp_path: Path,
    *,
    interaction_id: str = "founder-approval",
    resolve_questions: bool = True,
    budget_limit: float = 0,
) -> tuple[CharterService, ProjectRecord, ProjectCharter]:
    store = KeeperStore(tmp_path / "keeper.db")
    store.migrate()
    service = CharterService(ExecutiveRepository(store))
    replacements: dict[str, object] = {
        "target_audience": "Founder",
        "approved_providers": ("mock",),
        "approved_tools": ("filesystem",),
    }
    if budget_limit:
        replacements.update(
            {
                "budget_limit": budget_limit,
                "budget_policy": f"up to {budget_limit:.2f} USD",
                "budget_currency": "USD",
            }
        )
    if resolve_questions:
        replacements["success_criteria"] = ("tests pass",)
    intake = ConversationIntake.revise(
        ConversationIntake().extract(
            f"Create a small application in {tmp_path} with full delegation and no spending."
        ),
        replacements=replacements,
    )
    project = service.create_project(intake)
    service.repository.save_conversation(
        interaction_id,
        {
            "interaction_id": interaction_id,
            "project_id": project.project_id,
            "speaker": "Founder",
            "message": "Approve this exact proposed charter.",
            "created_at": utc_now(),
        },
    )
    return service, project, service.propose(service.draft(project, intake))


def test_direct_or_caller_constructed_approved_charter_is_rejected(
    tmp_path: Path,
) -> None:
    service, _, proposed = _proposed(tmp_path)
    forged = replace(
        proposed,
        status="APPROVED",
        founder_approval_identity="specialist-impersonating-Founder",
        founder_approval_record_id="nonexistent-approval",
    )
    with pytest.raises(PermissionError, match="transition"):
        service.repository.save_charter(forged, expected=proposed)
    with pytest.raises(PermissionError, match="CAS"):
        service.repository.save_charter(forged)


@pytest.mark.parametrize("identity", ["", "founder", "specialist-impersonating-Founder"])
def test_only_exact_authenticated_founder_identity_can_approve(
    tmp_path: Path,
    identity: str,
) -> None:
    service, _, proposed = _proposed(tmp_path)
    with pytest.raises(PermissionError, match="Founder"):
        service.approve(
            proposed,
            approver=identity,
            source_interaction_id="founder-approval",
        )


def test_missing_or_cross_project_approval_source_is_rejected(
    tmp_path: Path,
) -> None:
    service, _, proposed = _proposed(tmp_path)
    with pytest.raises(KeyError, match="project_conversations"):
        service.approve(
            proposed,
            approver="Founder",
            source_interaction_id="nonexistent",
        )

    other_intake = ConversationIntake.revise(
        ConversationIntake().extract("Create a separate research report."),
        replacements={
            "success_criteria": ("report exists",),
            "target_audience": "Founder",
        },
    )
    other_project = service.create_project(other_intake)
    service.repository.save_conversation(
        "other-founder-approval",
        {
            "interaction_id": "other-founder-approval",
            "project_id": other_project.project_id,
            "speaker": "Founder",
            "message": "Approve only the other project.",
            "created_at": utc_now(),
        },
    )
    with pytest.raises(PermissionError, match="source"):
        service.approve(
            proposed,
            approver="Founder",
            source_interaction_id="other-founder-approval",
        )


def test_activation_reloads_durable_charter_and_approval(
    tmp_path: Path,
) -> None:
    service, project, proposed = _proposed(tmp_path)
    approved, approval = service.approve(
        proposed,
        approver="Founder",
        source_interaction_id="founder-approval",
    )
    caller_substitution = replace(
        approved,
        title="same ID but caller-mutated content",
        founder_approval_record_id="nonexistent-approval",
    )
    active = service.activate(caller_substitution)
    stored = service.repository.charter(approved.charter_id)
    assert active.project_id == project.project_id
    assert stored.title == approved.title
    assert stored.status == "ACTIVE"
    assert stored.founder_approval_record_id == approval.approval_id


def test_unresolved_material_question_blocks_activation(tmp_path: Path) -> None:
    service, _, proposed = _proposed(tmp_path, resolve_questions=False)
    approved, _ = service.approve(
        proposed,
        approver="Founder",
        source_interaction_id="founder-approval",
    )
    with pytest.raises(PermissionError, match="unresolved"):
        service.activate(approved)


def test_exact_non_goal_and_disguised_deployment_are_denied(
    tmp_path: Path,
) -> None:
    service, project, proposed = _proposed(tmp_path)
    approved, _ = service.approve(
        proposed,
        approver="Founder",
        source_interaction_id="founder-approval",
    )
    active_project = service.activate(approved)
    active = service.repository.charter(approved.charter_id)
    denied_charter = replace(active, non_goals=("production deployment",))
    action = ProposedAction(
        "deploy",
        project.project_id,
        active.revision,
        ActionCategory.WRITE.value,
        "production deployment",
        "mock",
        "filesystem",
        str(tmp_path),
        active.deliverables,
        0,
        False,
        "LOW",
        "INTERNAL",
        True,
        objective="Deploy the application to production",
        deployment=True,
        trusted_source="DURABLE_WORKFLOW_TASK",
    )
    decision = AuthorityEvaluator().evaluate(
        active_project, denied_charter, action
    )
    assert decision.outcome == "DENIED"
    assert decision.rule == "explicit-non-goal"


@pytest.mark.parametrize(
    ("objective", "flag"),
    [
        ("Publish externally as a public release", "publication"),
        ("Select and buy access to a paid provider", "spending"),
    ],
)
def test_publication_or_spending_disguised_as_write_is_denied(
    tmp_path: Path,
    objective: str,
    flag: str,
) -> None:
    service, _, proposed = _proposed(tmp_path)
    approved, _ = service.approve(
        proposed,
        approver="Founder",
        source_interaction_id="founder-approval",
    )
    project = service.activate(approved)
    charter = service.repository.charter(approved.charter_id)
    action = ProposedAction(
        "hidden-side-effect",
        project.project_id,
        charter.revision,
        ActionCategory.WRITE.value,
        objective,
        "mock",
        "filesystem",
        str(tmp_path),
        charter.deliverables,
        None if flag == "spending" else 0,
        False,
        "LOW",
        "INTERNAL",
        True,
        objective=objective,
        publication=flag == "publication",
        spending=flag == "spending",
        trusted_source="DURABLE_WORKFLOW_TASK",
    )
    decision = AuthorityEvaluator().evaluate(project, charter, action)
    assert decision.outcome == "DENIED"
    assert decision.rule == "classification-mismatch"


def test_readiness_classification_uses_actual_task_objective(
    tmp_path: Path,
) -> None:
    service, _, proposed = _proposed(tmp_path)
    approved, _ = service.approve(
        proposed,
        approver="Founder",
        source_interaction_id="founder-approval",
    )
    project = service.activate(approved)
    charter = service.repository.charter(approved.charter_id)
    _, tasks = WorkflowPlanner(service.repository).generate(project, charter)
    task = tasks[0]
    specialist = SpecialistProfile(
        "mock",
        "model",
        "session",
        task.required_capabilities,
        ("software",),
        True,
        True,
        "independent-1",
        0,
        ("medium",),
        True,
        1.0,
    )
    action = TrustedActionClassifier().classify(task, charter, specialist)
    assert action.objective == task.objective
    assert action.target_resource == task.objective
    assert action.scope == charter.deliverables


def _activate(
    service: CharterService,
    proposed: ProjectCharter,
) -> tuple[ProjectRecord, ProjectCharter]:
    approved, _ = service.approve(
        proposed,
        approver="Founder",
        source_interaction_id="founder-approval",
    )
    project = service.activate(approved)
    return project, service.repository.charter(approved.charter_id)


def _record_action_approval_interaction(
    service: CharterService,
    project_id: str,
) -> None:
    service.repository.save_conversation(
        "action-approval",
        {
            "interaction_id": "action-approval",
            "project_id": project_id,
            "speaker": "Founder",
            "message": "Approve the exact bounded action.",
            "created_at": utc_now(),
        },
    )


def test_one_time_approval_is_consumed_atomically_once(tmp_path: Path) -> None:
    service, project, proposed = _proposed(tmp_path)
    _, charter = _activate(service, proposed)
    _record_action_approval_interaction(service, project.project_id)
    approval = service.repository.grant_action_approval(
        project_id=project.project_id,
        charter_id=charter.charter_id,
        charter_revision=charter.revision,
        kind=ApprovalKind.ONE_TIME,
        action_category=ActionCategory.COMMIT,
        scope=charter.deliverables,
        limits={"action_id": "commit-once"},
        approver="Founder",
        source_interaction_id="action-approval",
    )
    action = ProposedAction(
        "commit-once",
        project.project_id,
        charter.revision,
        ActionCategory.COMMIT.value,
        "repository commit",
        "mock",
        "filesystem",
        str(tmp_path),
        charter.deliverables,
        0,
        False,
        "LOW",
        "INTERNAL",
        True,
        objective="Commit the reviewed changes",
        git_mutation="MUTATE",
        trusted_source="DURABLE_WORKFLOW_TASK",
    )

    def consume() -> str:
        repository = ExecutiveRepository(KeeperStore(tmp_path / "keeper.db"))
        try:
            repository.reserve_action_authority(
                action,
                approval_id=approval.approval_id,
                task_id="task-commit",
            )
        except PermissionError:
            return "rejected"
        return "consumed"

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = sorted(pool.map(lambda _: consume(), range(2)))
    assert outcomes == ["consumed", "rejected"]
    with pytest.raises(PermissionError, match="binding"):
        service.repository.reserve_action_authority(
            action,
            approval_id=approval.approval_id,
            task_id="task-commit",
        )


def test_cumulative_spending_prevents_split_action_bypass(
    tmp_path: Path,
) -> None:
    service, project, proposed = _proposed(tmp_path, budget_limit=50)
    _, charter = _activate(service, proposed)
    _record_action_approval_interaction(service, project.project_id)
    approval = service.repository.grant_action_approval(
        project_id=project.project_id,
        charter_id=charter.charter_id,
        charter_revision=charter.revision,
        kind=ApprovalKind.AMOUNT_LIMITED,
        action_category=ActionCategory.SPEND,
        scope=charter.deliverables,
        limits={
            "maximum_cost": 50,
            "currency": "USD",
            "provider": "mock",
            "workspace": str(tmp_path),
        },
        approver="Founder",
        source_interaction_id="action-approval",
    )
    outcomes: list[str] = []
    for index in range(10):
        action = ProposedAction(
            f"paid-action-{index}",
            project.project_id,
            charter.revision,
            ActionCategory.SPEND.value,
            f"paid provider action {index}",
            "mock",
            "filesystem",
            str(tmp_path),
            charter.deliverables,
            10,
            False,
            "LOW",
            "INTERNAL",
            True,
            objective="Use the explicitly approved paid provider",
            currency="USD",
            spending=True,
            trusted_source="DURABLE_WORKFLOW_TASK",
        )
        try:
            service.repository.reserve_action_authority(
                action,
                approval_id=approval.approval_id,
                task_id=f"paid-task-{index}",
            )
        except PermissionError:
            outcomes.append("rejected")
        else:
            outcomes.append("reserved")
    assert outcomes == ["reserved"] * 5 + ["rejected"] * 5


def test_unknown_cost_and_absent_budget_fail_closed(tmp_path: Path) -> None:
    service, _, proposed = _proposed(tmp_path)
    project, charter = _activate(service, proposed)
    action = ProposedAction(
        "unknown-cost",
        project.project_id,
        charter.revision,
        ActionCategory.SPEND.value,
        "paid provider",
        "mock",
        "filesystem",
        str(tmp_path),
        charter.deliverables,
        None,
        False,
        "LOW",
        "INTERNAL",
        True,
        objective="Use a paid provider",
        currency="USD",
        spending=True,
        trusted_source="DURABLE_WORKFLOW_TASK",
    )
    decision = AuthorityEvaluator().evaluate(project, charter, action)
    assert decision.outcome == "DENIED"
    assert decision.rule == "unknown-cost"
