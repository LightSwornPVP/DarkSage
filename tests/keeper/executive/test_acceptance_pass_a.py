from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from keeper.executive.authority import AuthorityEvaluator
from keeper.executive.charters import CharterService
from keeper.executive.enums import ActionCategory, TaskStatus
from keeper.executive.intake import ConversationIntake
from keeper.executive.models import ProposedAction, SpecialistProfile
from keeper.executive.planning import WorkflowPlanner
from keeper.executive.runtime import ExecutiveRuntime
from keeper.executive.service import KeeperExecutive
from keeper.executive.specialists import (
    SpecialistOrchestrator,
    SpecialistResult,
)
from tests.keeper.executive.test_intake_charters import approved_project
from tests.keeper.executive.test_runtime import RuntimeGateway, profiles
from tests.keeper.executive.test_specialists import FakeGateway, profile, result_for


def test_scenario_a_software_full_delegation_repair_and_completion(tmp_path: Path) -> None:
    executive = KeeperExecutive(tmp_path / "keeper.db")
    project, intake = executive.begin(
        f"I want a small application called Pocket List in {tmp_path}. "
        "Use full delegation, no spending, and do not push."
    )
    draft = executive.draft(
        project.project_id,
        intake,
        founder_revisions={
            "success_criteria": ("all acceptance checks pass",),
            "target_audience": "personal users",
            "approved_providers": ("mock",),
            "approved_tools": ("filesystem",),
        },
    )
    service = executive.charters
    approved, _ = service.approve(
        service.propose(draft), approver="Founder", source_interaction_id="accept-a"
    )
    active = service.activate(approved)
    gateway = RuntimeGateway()
    runtime = ExecutiveRuntime(executive.repository, gateway, profiles())
    for _ in range(20):
        active = runtime.progress(active.project_id)
        if active.state == "COMPLETED":
            break
    assert active.state == "COMPLETED"
    assert any(task.retry_count == 1 for task in executive.repository.tasks(active.project_id))
    assert executive.repository.decisions(active.project_id)
    assert executive.repository.memories(active.project_id)


def test_scenario_b_non_software_workflow(tmp_path: Path) -> None:
    executive = KeeperExecutive(tmp_path / "keeper.db")
    project, intake = executive.begin("Research urban gardens and create a sourced final report.")
    draft = executive.draft(
        project.project_id,
        intake,
        founder_revisions={
            "success_criteria": ("all material claims are sourced",),
            "target_audience": "city planners",
            "approved_providers": ("mock",),
            "approved_tools": ("filesystem",),
            "workspaces": (str(tmp_path),),
            "delegation_mode": "FULL_DELEGATION",
        },
    )
    approved, _ = executive.charters.approve(
        executive.charters.propose(draft), approver="Founder", source_interaction_id="b"
    )
    active = executive.charters.activate(approved)
    workflow, _ = WorkflowPlanner(executive.repository).generate(active, approved)
    titles = {stage.title for stage in workflow.stages}
    assert "Source quality review" in titles
    assert "Implementation" not in titles


@pytest.mark.parametrize(
    "category",
    [
        ActionCategory.SPEND,
        ActionCategory.PUBLISH_EXTERNAL,
        ActionCategory.DEPLOY_PRODUCTION,
        ActionCategory.REWRITE_HISTORY,
    ],
)
def test_scenario_c_authority_exceeded_pauses_or_denies(
    tmp_path: Path, category: ActionCategory
) -> None:
    _, project, charter = approved_project(tmp_path)
    action = ProposedAction(
        "outside", project.project_id, charter.revision, category.value, "external",
        "mock", "filesystem", str(tmp_path), (charter.deliverables[0],), 10, False,
        "HIGH", "INTERNAL", True,
    )
    decision = AuthorityEvaluator().evaluate(project, charter, action)
    assert decision.outcome in {"DENIED", "REQUIRES_FOUNDER_APPROVAL"}


def test_scenario_d_revocation_stops_new_launches(tmp_path: Path) -> None:
    service, project, _ = approved_project(tmp_path)
    gateway = RuntimeGateway()
    runtime = ExecutiveRuntime(service.repository, gateway, profiles())
    runtime.progress(project.project_id)
    runtime.revoke_delegation(project.project_id)
    count = len(gateway.calls)
    runtime.progress(project.project_id)
    assert len(gateway.calls) == count


def test_scenario_e_charter_expansion_requires_new_approval(tmp_path: Path) -> None:
    service, project, charter = approved_project(tmp_path)
    revised = service.revise(
        charter,
        {"deliverables": charter.deliverables + ("external launch",)},
        reason="Expanded delivery",
        authority_basis="Founder request",
    )
    assert project.active_charter_revision is not None
    assert revised.revision == project.active_charter_revision + 1
    assert not service.repository.approvals(project.project_id, revised.revision)


def test_scenario_f_specialist_overreach_is_rejected(tmp_path: Path) -> None:
    service, project, charter = approved_project(tmp_path)
    _, tasks = WorkflowPlanner(service.repository).generate(project, charter)
    task = replace(tasks[0], status=TaskStatus.READY.value)
    specialist = profile(task.required_capabilities[0])
    result = result_for(task, specialist, claims={"self_approved": True})
    with pytest.raises(PermissionError):
        SpecialistOrchestrator(FakeGateway(result)).run(task, charter, specialist)


def test_scenario_g_restart_does_not_duplicate_completed_work(tmp_path: Path) -> None:
    service, project, _ = approved_project(tmp_path)
    gateway = RuntimeGateway()
    runtime = ExecutiveRuntime(service.repository, gateway, profiles())
    runtime.progress(project.project_id)
    runtime.progress(project.project_id)
    completed_before = {
        task.task_id for task in service.repository.tasks(project.project_id)
        if task.status == "COMPLETED"
    }
    reopened = KeeperExecutive(service.repository.store.path)
    ExecutiveRuntime(reopened.repository, gateway, profiles()).progress(project.project_id)
    completed_after = [
        task.task_id for task in reopened.repository.tasks(project.project_id)
        if task.status == "COMPLETED"
    ]
    assert completed_before.issubset(completed_after)
    assert len(completed_after) == len(set(completed_after))


def test_scenario_h_missing_provider_or_credential_waits(tmp_path: Path) -> None:
    service, project, _ = approved_project(tmp_path)
    runtime = ExecutiveRuntime(service.repository, RuntimeGateway(), ())
    runtime.progress(project.project_id)
    assert runtime.progress(project.project_id).state == "WAITING_FOR_PROVIDER"

    service2, project2, _ = approved_project(tmp_path / "credential")
    unavailable: SpecialistProfile = replace(
        profiles()[0], credential_available=False
    )
    runtime2 = ExecutiveRuntime(service2.repository, RuntimeGateway(), (unavailable,))
    runtime2.progress(project2.project_id)
    assert runtime2.progress(project2.project_id).state == "WAITING_FOR_CREDENTIAL"
