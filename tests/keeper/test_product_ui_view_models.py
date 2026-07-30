from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from keeper.app.service import KeeperApplication
from keeper.pass_b.models import PresentationStateRecord
from keeper.ui.desktop import KeeperProductDesktop, ProductSetupController
from keeper.ui.view_models import SETUP_STEPS, build_product_view


NOW = "2026-07-30T12:00:00+00:00"


def _snapshot() -> dict[str, object]:
    return {
        "conversation": {
            "messages": [
                {"speaker": "FOUNDER", "text": "Build Keeper", "created_at": NOW},
                {"speaker": "KEEPER", "text": "I prepared a charter", "created_at": NOW},
            ],
            "charter_proposal": {
                "project_id": "project-1",
                "charter_revision": 2,
                "state": "APPROVAL_REQUESTED",
                "intake": {
                    "title": "Keeper polish",
                    "goals": ["Readable control room"],
                    "exclusions": ["No deployment"],
                    "objective": "Polish the approved application",
                },
                "updated_at": NOW,
            },
            "approval_required": True,
            "recovery_prompts": [
                {"assignment_id": "assignment-2", "message": "Review uncertain work"}
            ],
        },
        "control_room": {
            "assignment_counts": {"RUNNING": 1, "BLOCKED": 1},
            "active_assignments": [{"assignment_id": "assignment-1"}],
            "waiting_for_usage_reset": [{"assignment_id": "assignment-3"}],
            "recent_evidence": [
                {
                    "summary": "Implementation evidence",
                    "state": "VALIDATED",
                    "updated_at": NOW,
                }
            ],
            "recent_reviews": [
                {"state": "ACCEPTED", "disposition": "ACCEPTED", "updated_at": NOW}
            ],
        },
        "project": {
            "project_id": "project-1",
            "charter_revision": 2,
            "work_items": [
                {
                    "work_item_id": "work-1",
                    "title": "Implement",
                    "required_roles": ["IMPLEMENTER"],
                    "dependencies": [],
                    "state": "ACTIVE",
                }
            ],
            "assignments": [
                {
                    "assignment_id": "assignment-1",
                    "work_item_id": "work-1",
                    "provider_id": "provider-1",
                    "role": "IMPLEMENTER",
                    "state": "RUNNING",
                }
            ],
            "evidence": [
                {
                    "evidence_bundle_id": "evidence-1",
                    "producer_provider_id": "provider-1",
                    "assignment_id": "assignment-1",
                    "attempt_id": "attempt-1",
                    "artifacts": [{"kind": "structured-report"}],
                    "state": "VALIDATED",
                    "content_digest": "a" * 64,
                    "updated_at": NOW,
                }
            ],
            "reviews": [
                {
                    "review_id": "review-1",
                    "assignment_id": "assignment-1",
                    "reviewer_assignment_id": "assignment-review",
                    "state": "ACCEPTED",
                    "disposition": "ACCEPTED",
                    "producer_evidence_bundle_id": "evidence-1",
                    "reviewer_evidence_bundle_id": "evidence-review",
                    "updated_at": NOW,
                }
            ],
        },
        "providers": {
            "providers": [
                {
                    "provider_id": "provider-1",
                    "display_name": "Local provider",
                    "adapter_kind": "local-mock",
                    "classification": "LOCAL",
                    "health": "READY",
                    "capabilities": ["implementer"],
                    "cost_mode": "FREE",
                }
            ],
            "accounts": [
                {
                    "account_id": "account-1",
                    "provider_id": "provider-1",
                    "display_name": "Local account",
                    "privacy_classification": "LOCAL",
                    "cost_mode": "FREE",
                }
            ],
            "sessions": [
                {
                    "session_id": "session-1",
                    "provider_id": "provider-1",
                    "active_assignments": 1,
                    "concurrency_limit": 2,
                    "state": "BUSY",
                }
            ],
            "usage_pools": [
                {
                    "pool_id": "pool-1",
                    "provider_id": "provider-1",
                    "consumed": 8,
                    "reserved": 2,
                    "remaining": 0,
                    "reset_at": NOW,
                    "observation_source": "provider-api",
                    "confidence": "HIGH",
                    "exhausted": True,
                }
            ],
        },
        "safety": {
            "authority": {"state": "TEST_COMPOSITION"},
            "delegated_mode_history": [
                {"state": "ACTIVE"},
                {"state": "EXPIRED"},
                {"state": "REVOKED"},
                {"state": "SUPERSEDED"},
            ],
            "uncertain_assignments": [{"assignment_id": "assignment-2"}],
            "open_pauses": [{"assignment_id": "assignment-3"}],
            "prohibited_actions": ["unapproved-push", "live-trading"],
        },
        "presentation": {
            "avatar_asset_identity": "sage-default",
            "form": "default",
            "expression": "focused",
            "activity_state": "THINKING",
            "mood": "CALM",
            "background": "black-gold",
            "intensity": 0.3,
            "interruption_state": "IDLE",
            "mode": "ANALYST",
            "authority_effect": "NONE",
        },
    }


def test_product_view_maps_conversation_control_room_and_evidence() -> None:
    view = build_product_view(_snapshot())
    assert view.project_title == "Keeper polish"
    assert view.project_status == "APPROVAL_REQUESTED"
    assert [item.kind for item in view.timeline[:3]] == [
        "founder", "keeper", "approval"
    ]
    assert any(item.kind == "warning" for item in view.timeline)
    assert view.workflow_rows[0]["assignment"]["state"] == "RUNNING"
    assert view.provider_cards[0]["composition"] == "MOCK"
    assert view.usage_cards[0]["status"] == "WAITING_FOR_USAGE_RESET"
    assert view.evidence_cards[0]["review"]["disposition"] == "ACCEPTED"
    assert "EXPIRED: 1" in view.safety_rows[1]["value"]
    assert dict(view.right_rail)["KeeperAuthority"] == "TEST_COMPOSITION"
    assert view.developer_details is None


def test_mock_test_production_labels_and_optional_raw_details() -> None:
    snapshot = _snapshot()
    view = build_product_view(snapshot, developer_details=True)
    assert view.composition == "TEST_COMPOSITION"
    assert view.developer_details == snapshot
    snapshot["safety"]["authority"] = {"state": "READY"}  # type: ignore[index]
    assert build_product_view(snapshot).composition == "PRODUCTION"


def test_sage_cannot_gain_authority_effect() -> None:
    snapshot = _snapshot()
    snapshot["presentation"]["authority_effect"] = "APPROVE"  # type: ignore[index]
    with pytest.raises(ValueError, match="authority-neutral"):
        build_product_view(snapshot)
    record = PresentationStateRecord(
        presentation_state_id="sage-test",
        project_id=None,
        form="default",
        mode="COMPACT",
        expression="neutral",
        intensity=0.2,
        background="black-gold",
        ambient_effect="none",
        updated_at=NOW,
        revision=1,
    )
    with pytest.raises(ValueError, match="authority effect"):
        replace(record, authority_effect="LAUNCH")


def test_first_run_has_seven_bounded_steps(tmp_path: Path) -> None:
    application = KeeperApplication(tmp_path / "data")
    controller = ProductSetupController(application)
    assert tuple(item[0] for item in SETUP_STEPS) == (
        "boundaries", "storage", "repository", "providers",
        "provider_validation", "authority", "finish",
    )
    for _ in range(len(SETUP_STEPS) - 1):
        controller.next()
    controller.finish()
    assert application.setup_complete()


def test_product_ui_exposes_no_direct_authority_bypass_commands() -> None:
    prohibited = {
        "approve", "accept_review", "force_push", "deploy",
        "enable_paid_fallback", "change_service", "live_trade",
    }
    assert prohibited.isdisjoint(dir(KeeperProductDesktop))
