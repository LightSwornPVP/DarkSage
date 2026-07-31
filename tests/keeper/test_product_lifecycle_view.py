from __future__ import annotations

from keeper.ui.view_models import build_product_view


def test_authoritative_charter_fields_reach_founder_product_view() -> None:
    snapshot = {
        "conversation": {
            "messages": [],
            "charter_proposal": {
                "project_id": "project-1",
                "state": "APPROVAL_REQUESTED",
                "intake": {},
            },
            "approval_required": True,
        },
        "control_room": {},
        "project": {
            "project_id": "project-1",
            "work_items": [],
            "assignments": [],
            "evidence": [],
            "reviews": [],
            "evidence_references": [],
        },
        "projects": [
            {
                "project_id": "project-1",
                "title": "Keeper",
                "state": "AWAITING_CHARTER_APPROVAL",
            }
        ],
        "executive": {
            "project_summary": {
                "project_id": "project-1",
                "name": "Keeper",
                "state": "AWAITING_CHARTER_APPROVAL",
            },
            "active_charter": {
                "charter_id": "charter-1",
                "revision": 3,
                "title": "Keeper",
                "deliverables": ["Desktop"],
                "constraints": ["No deployment"],
                "non_goals": ["Live trading"],
                "budget_limit": 0,
                "budget_currency": "USD",
                "approved_providers": ["codex"],
                "approved_tools": ["tests"],
                "workspaces": ["C:/tmp/keeper"],
                "delegation_mode": "FULL_DELEGATION",
                "unresolved_questions": [],
                "authority_envelope": {
                    "data_classifications": ["INTERNAL"]
                },
            },
            "controls": ["cancel"],
        },
        "providers": {},
        "safety": {"authority": {"state": "NOT_CONFIGURED"}},
        "presentation": {
            "mode": "HIDDEN",
            "authority_effect": "NONE",
        },
    }

    view = build_product_view(snapshot)
    card = view.project_cards[0]

    assert view.project_id == "project-1"
    assert view.project_status == "AWAITING_CHARTER_APPROVAL"
    assert view.charter_revision == 3
    assert view.controls == ("cancel",)
    assert view.project_catalog[0]["project_id"] == "project-1"
    assert card["constraints"] == ("No deployment",)
    assert card["approved_providers"] == ("codex",)
    assert card["approved_tools"] == ("tests",)
    assert card["workspaces"] == ("C:/tmp/keeper",)
    assert card["data_classifications"] == ("INTERNAL",)
    assert card["delegation_mode"] == "FULL_DELEGATION"
    assert view.sage["visible"] is False
