from __future__ import annotations

from dataclasses import replace
from typing import Any

from keeper.executive.enums import (
    ActionCategory,
    ApprovalKind,
    CharterStatus,
    ExecutiveState,
)
from keeper.executive.intake import IntakeResult
from keeper.executive.models import (
    ApprovalRecord,
    AssumptionRecord,
    AuthorityEnvelope,
    DecisionRecord,
    ProjectCharter,
    ProjectRecord,
    utc_now,
)
from keeper.executive.repository import (
    ExecutiveRepository,
    canonical_digest,
    new_id,
)
from keeper.executive.state import transition_project


class CharterService:
    def __init__(self, repository: ExecutiveRepository) -> None:
        self.repository = repository

    def create_project(self, intake: IntakeResult) -> ProjectRecord:
        now = utc_now()
        project = ProjectRecord(
            new_id("project"),
            str(intake.explicit("project_name", "Untitled Project")),
            str(intake.explicit("project_type", "general")),
            ExecutiveState.CLARIFICATION_REQUIRED.value if intake.unresolved_questions else ExecutiveState.INTAKE.value,
            None,
            None,
            None,
            now,
            now,
        )
        self.repository.save_project(project)
        return project

    def draft(self, project: ProjectRecord, intake: IntakeResult) -> ProjectCharter:
        prior = self.repository.charters(project.project_id)
        revision = max((item.revision for item in prior), default=0) + 1
        now = utc_now()
        workspace_values = tuple(str(item) for item in intake.explicit("workspaces", ()))
        provider_values = tuple(str(item) for item in intake.explicit("approved_providers", ("mock",)))
        tool_values = tuple(str(item) for item in intake.explicit("approved_tools", ("filesystem",)))
        deliverables = tuple(str(item) for item in intake.explicit("deliverables", ("project deliverable",)))
        mode = str(intake.explicit("delegation_mode", "ADVISORY"))
        allowed_actions = (
            ActionCategory.ANALYZE.value,
            ActionCategory.PLAN.value,
            ActionCategory.DRAFT.value,
            ActionCategory.READ.value,
            ActionCategory.WRITE.value,
            ActionCategory.TEST.value,
            ActionCategory.REVIEW.value,
            ActionCategory.REPAIR.value,
        )
        envelope = AuthorityEnvelope(
            allowed_actions,
            tuple(item.value for item in (ActionCategory.COMMIT, ActionCategory.PUSH, ActionCategory.DEPLOY_PRODUCTION, ActionCategory.PUBLISH_EXTERNAL, ActionCategory.PURCHASE, ActionCategory.SPEND)),
            tuple(item.value for item in (ActionCategory.DELETE_PROTECTED, ActionCategory.REWRITE_HISTORY, ActionCategory.ACCESS_CREDENTIAL, ActionCategory.CHANGE_SECURITY_BOUNDARY, ActionCategory.ENABLE_LIVE_TRADING, ActionCategory.CHANGE_FINANCIAL_AUTHORITY, ActionCategory.CHANGE_GOVERNANCE, ActionCategory.EXPAND_SCOPE, ActionCategory.IRREVERSIBLE_DESTRUCTIVE)),
            workspace_values,
            tool_values,
            provider_values,
            float(intake.explicit("budget_limit", 0.0)),
            str(intake.explicit("risk_classification", "LOW")),
            tuple(str(item) for item in intake.explicit("data_classifications", ("INTERNAL",))),
            None,
        )
        charter = ProjectCharter(
            new_id("charter"),
            project.project_id,
            project.name,
            project.project_type,
            str(intake.explicit("purpose", intake.explicit("desired_outcome", ""))),
            str(intake.explicit("problem_or_opportunity", "")),
            str(intake.explicit("desired_outcome", "")),
            deliverables,
            tuple(str(item) for item in intake.explicit("non_goals", ())),
            tuple(str(item) for item in intake.explicit("success_criteria", ())),
            tuple(str(item) for item in intake.explicit("constraints", ())),
            intake.proposed_assumptions,
            intake.unresolved_questions,
            _optional_string(intake.explicit("timeline")),
            str(intake.explicit("budget_policy", "spending prohibited")),
            float(intake.explicit("budget_limit", 0.0)),
            tool_values,
            provider_values,
            tuple(str(item) for item in intake.explicit("prohibited_tools", ())),
            tuple(str(item) for item in intake.explicit("prohibited_providers", ())),
            workspace_values,
            tuple(str(item) for item in intake.explicit("data_privacy_restrictions", ("Do not store secrets in project records.",))),
            str(intake.explicit("risk_classification", "LOW")),
            mode,
            envelope,
            tuple(str(item) for item in intake.explicit("escalation_rules", ("Pause when authority is ambiguous or exceeded.",))),
            tuple(str(item) for item in intake.explicit("review_requirements", ("Verify each deliverable against its criteria.",))),
            tuple(str(item) for item in intake.explicit("evidence_requirements", ("Preserve outputs and verification results.",))),
            tuple(str(item) for item in intake.explicit("completion_definition", ("All success criteria and deliverables are satisfied.",))),
            revision,
            CharterStatus.DRAFT.value,
            prior[-1].charter_id if prior else None,
            None,
            (),
            None,
            None,
            now,
            now,
        )
        self.repository.save_charter(charter)
        for assumption in charter.assumptions:
            self.repository.insert_assumption(
                AssumptionRecord(
                    new_id("assumption"),
                    project.project_id,
                    revision,
                    assumption,
                    "conversation intake",
                    0.6,
                    "Confirm during charter review.",
                    "May change scope, schedule, or completion criteria.",
                    "PROPOSED",
                    None,
                    now,
                )
            )
        self.repository.save_project(
            transition_project(
                project if project.state in {ExecutiveState.INTAKE, ExecutiveState.CLARIFICATION_REQUIRED} else replace(project, state=ExecutiveState.INTAKE.value),
                ExecutiveState.CHARTER_DRAFT,
            )
        )
        return charter

    def propose(self, charter: ProjectCharter) -> ProjectCharter:
        if charter.status != CharterStatus.DRAFT:
            raise PermissionError("only draft charters may be proposed")
        proposed = replace(charter, status=CharterStatus.PROPOSED.value, updated_at=utc_now())
        self.repository.save_charter(proposed)
        project = self.repository.project(charter.project_id)
        self.repository.save_project(transition_project(project, ExecutiveState.AWAITING_CHARTER_APPROVAL))
        return proposed

    def approve(
        self,
        charter: ProjectCharter,
        *,
        approver: str,
        source_interaction_id: str,
    ) -> tuple[ProjectCharter, ApprovalRecord]:
        if charter.status != CharterStatus.PROPOSED or not approver.strip():
            raise PermissionError("Founder identity must approve a proposed charter")
        now = utc_now()
        approval = ApprovalRecord(
            new_id("approval"),
            charter.project_id,
            charter.charter_id,
            charter.revision,
            ApprovalKind.CHARTER_DURATION.value,
            None,
            approver,
            charter.deliverables,
            {"delegation_mode": charter.delegation_mode, "maximum_cost": charter.budget_limit},
            now,
            charter.authority_envelope.expires_at,
            None,
            None,
            canonical_digest(charter.to_dict()),
            source_interaction_id,
        )
        self.repository.insert_approval(approval)
        approved = replace(
            charter,
            status=CharterStatus.APPROVED.value,
            founder_approval_identity=approver,
            founder_approval_record_id=approval.approval_id,
            updated_at=now,
        )
        self.repository.save_charter(approved)
        return approved, approval

    def activate(self, charter: ProjectCharter) -> ProjectRecord:
        if charter.status != CharterStatus.APPROVED:
            raise PermissionError("only approved charters may be activated")
        project = self.repository.project(charter.project_id)
        active = transition_project(project, ExecutiveState.ACTIVE)
        active = replace(
            active,
            active_charter_id=charter.charter_id,
            active_charter_revision=charter.revision,
        )
        self.repository.save_project(active)
        self.repository.insert_decision(
            DecisionRecord(
                new_id("decision"),
                charter.project_id,
                charter.revision,
                "Activate Project Charter",
                ("keep draft", "activate approved charter"),
                "activate approved charter",
                "Founder approval authorizes project execution within the charter.",
                charter.founder_approval_identity or "Founder",
                charter.founder_approval_record_id or "",
                (charter.founder_approval_record_id or "",),
                ("Keeper may plan and act only within the active authority envelope.",),
                True,
                utc_now(),
                None,
            )
        )
        return active

    def revise(
        self,
        active: ProjectCharter,
        changes: dict[str, Any],
        *,
        reason: str,
        authority_basis: str,
    ) -> ProjectCharter:
        if active.status != CharterStatus.APPROVED or not reason.strip():
            raise PermissionError("only an approved charter may be amended")
        forbidden = {
            "charter_id", "project_id", "revision", "status", "created_at",
            "founder_approval_identity", "founder_approval_record_id",
        }
        if set(changes) & forbidden or not set(changes).issubset(ProjectCharter.FIELDS):
            raise ValueError("charter revision contains forbidden or unknown fields")
        data = active.to_dict()
        differences: list[str] = []
        for key, value in changes.items():
            if data[key] != value:
                differences.append(f"{key}: {data[key]!r} -> {value!r}")
                data[key] = value
        data.update(
            {
                "charter_id": new_id("charter"),
                "revision": active.revision + 1,
                "status": CharterStatus.DRAFT.value,
                "supersedes_charter_id": active.charter_id,
                "change_reason": reason,
                "differences": differences + [f"authority_basis: {authority_basis}"],
                "founder_approval_identity": None,
                "founder_approval_record_id": None,
                "created_at": utc_now(),
                "updated_at": utc_now(),
            }
        )
        revised = ProjectCharter.from_dict(data)
        self.repository.save_charter(revised)
        project = self.repository.project(active.project_id)
        paused = replace(project, state=ExecutiveState.PAUSED.value, pause_reason="Charter revision awaiting approval", updated_at=utc_now())
        self.repository.save_project(paused)
        return revised


def _optional_string(value: Any) -> str | None:
    return str(value) if value is not None else None
