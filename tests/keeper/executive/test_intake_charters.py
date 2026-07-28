from __future__ import annotations

from pathlib import Path

import pytest

from keeper.app.storage import KeeperStore
from keeper.executive.charters import CharterService
from keeper.executive.intake import ConversationIntake
from keeper.executive.models import ProjectCharter, ProjectRecord
from keeper.executive.models import utc_now
from keeper.executive.repository import ExecutiveRepository


def service(tmp_path: Path) -> CharterService:
    store = KeeperStore(tmp_path / "keeper.db")
    store.migrate()
    return CharterService(ExecutiveRepository(store))


def approved_project(
    tmp_path: Path,
) -> tuple[CharterService, ProjectRecord, ProjectCharter]:
    charter_service = service(tmp_path)
    intake = ConversationIntake().extract(
        f"I want a small application called Pocket List in {tmp_path}. "
        "Use full delegation, no spending, and do not push."
    )
    intake = ConversationIntake.revise(
        intake,
        replacements={
            "success_criteria": ("users can add and complete items",),
            "target_audience": "personal users",
            "approved_providers": ("codex", "reviewer-provider"),
            "approved_tools": ("filesystem",),
        },
    )
    project = charter_service.create_project(intake)
    charter_service.repository.save_conversation(
        "message-1",
        {
            "interaction_id": "message-1",
            "project_id": project.project_id,
            "speaker": "Founder",
            "message": "Approve the exact proposed Pocket List charter.",
            "created_at": utc_now(),
        },
    )
    draft = charter_service.draft(project, intake)
    proposed = charter_service.propose(draft)
    approved, _ = charter_service.approve(
        proposed, approver="Founder", source_interaction_id="message-1"
    )
    active = charter_service.activate(approved)
    return (
        charter_service,
        active,
        charter_service.repository.charter(approved.charter_id),
    )


def test_natural_language_intake_tracks_provenance_and_assumptions(tmp_path: Path) -> None:
    result = ConversationIntake().extract(
        f"I want a small application called Pocket List in {tmp_path}. "
        "Use full delegation and no spending."
    )
    assert result.explicit("project_type") == "software"
    assert result.fields["project_name"].provenance == "EXPLICIT"
    assert result.explicit("budget_limit") == 0
    assert result.explicit("delegation_mode") == "FULL_DELEGATION"
    assert "success" in result.unresolved_questions[0].lower()


def test_revision_replaces_assumption_and_removes_deliverable(tmp_path: Path) -> None:
    intake = ConversationIntake().extract("I want a research report about urban gardens.")
    revised = ConversationIntake.revise(
        intake,
        replacements={"target_audience": "city planners"},
        remove_deliverables=("contradiction analysis",),
    )
    assert revised.fields["target_audience"].provenance == "EXPLICIT"
    assert "contradiction analysis" not in revised.explicit("deliverables")


def test_charter_approval_and_activation_are_bound(tmp_path: Path) -> None:
    charter_service, project, charter = approved_project(tmp_path)
    assert project.state == "ACTIVE"
    assert project.active_charter_id == charter.charter_id
    assert charter.founder_approval_record_id
    stored = charter_service.repository.charter(charter.charter_id)
    assert stored.status == "ACTIVE"


def test_non_founder_or_blank_identity_cannot_approve(tmp_path: Path) -> None:
    charter_service = service(tmp_path)
    intake = ConversationIntake.revise(
        ConversationIntake().extract("Create a research report."),
        replacements={"success_criteria": ("report accepted",), "target_audience": "Founder"},
    )
    draft = charter_service.draft(charter_service.create_project(intake), intake)
    proposed = charter_service.propose(draft)
    with pytest.raises(PermissionError):
        charter_service.approve(proposed, approver="", source_interaction_id="x")


def test_material_change_creates_revision_and_old_approval_does_not_apply(tmp_path: Path) -> None:
    charter_service, _, charter = approved_project(tmp_path)
    revised = charter_service.revise(
        charter,
        {"deliverables": ("application", "public hosted service")},
        reason="Founder requested hosting",
        authority_basis="Founder conversation",
    )
    assert revised.revision == 2
    assert revised.charter_id != charter.charter_id
    assert revised.status == "DRAFT"
    assert revised.founder_approval_record_id is None
    assert charter_service.repository.approvals(charter.project_id, revised.revision) == []


def test_approved_charter_cannot_be_self_expanded(tmp_path: Path) -> None:
    charter_service, _, charter = approved_project(tmp_path)
    with pytest.raises(ValueError):
        charter_service.revise(
            charter,
            {"status": "APPROVED"},
            reason="specialist request",
            authority_basis="specialist",
        )
