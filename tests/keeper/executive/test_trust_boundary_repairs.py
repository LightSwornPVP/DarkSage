from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from keeper.app.storage import KeeperStore
from keeper.executive.charters import CharterService
from keeper.executive.intake import ConversationIntake
from keeper.executive.models import ProjectCharter, ProjectRecord, utc_now
from keeper.executive.repository import ExecutiveRepository


def _proposed(
    tmp_path: Path,
    *,
    interaction_id: str = "founder-approval",
    resolve_questions: bool = True,
) -> tuple[CharterService, ProjectRecord, ProjectCharter]:
    store = KeeperStore(tmp_path / "keeper.db")
    store.migrate()
    service = CharterService(ExecutiveRepository(store))
    replacements: dict[str, object] = {
        "target_audience": "Founder",
        "approved_providers": ("mock",),
        "approved_tools": ("filesystem",),
    }
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
