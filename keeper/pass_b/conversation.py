from __future__ import annotations

import uuid
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from typing import Any, Protocol

from keeper.executive.enums import CharterStatus
from keeper.executive.intake import ConversationIntake, IntakeResult, IntakeValue
from keeper.executive.models import (
    FounderApprovalChallenge,
    ProjectCharter,
    ProjectRecord,
)
from keeper.pass_b.enums import DelegatedModeState
from keeper.pass_b.models import (
    ConversationMessageRecord,
    DelegatedModeGrantRecord,
    PassBRecord,
)
from keeper.pass_b.repository import PassBRepository


class ConversationExecutive(Protocol):
    def begin(self, message: str) -> tuple[ProjectRecord, IntakeResult]: ...

    def draft(
        self,
        project_id: str,
        intake: IntakeResult,
        *,
        founder_revisions: dict[str, Any] | None = None,
    ) -> ProjectCharter: ...

    def propose_charter(self, charter: ProjectCharter) -> ProjectCharter: ...

    def request_charter_approval(
        self, charter: ProjectCharter
    ) -> FounderApprovalChallenge: ...


@dataclass(frozen=True, slots=True)
class CharterDraftContextRecord(PassBRecord):
    charter_draft_context_id: str
    project_id: str
    intake: dict[str, Any]
    charter_id: str
    charter_revision: int
    state: str
    created_at: str
    updated_at: str
    revision: int

    KIND = "charter_draft_context"
    ID_FIELD = "charter_draft_context_id"

    def __post_init__(self) -> None:
        if self.charter_revision < 1 or self.state not in {
            "DRAFT",
            "PROPOSED",
            "APPROVAL_REQUESTED",
            "APPROVED",
            "SUPERSEDED",
        }:
            raise ValueError("charter draft context is invalid")
        _parse_time(self.created_at)
        _parse_time(self.updated_at)
        if self.revision < 1:
            raise ValueError("charter draft revision must be positive")


@dataclass(frozen=True, slots=True)
class ConversationOutcome:
    project: ProjectRecord
    charter: ProjectCharter
    unresolved_questions: tuple[str, ...]
    proposed_assumptions: tuple[str, ...]
    approval_required: bool


@dataclass(frozen=True, slots=True)
class WorkflowStepBlueprint:
    title: str
    role: str
    objective: str
    dependencies: tuple[str, ...]
    independent_review: bool


@dataclass(frozen=True, slots=True)
class WorkflowBlueprint:
    project_id: str
    charter_id: str
    charter_revision: int
    strategy: str
    explanation: str
    steps: tuple[WorkflowStepBlueprint, ...]


class ConversationService:
    def __init__(
        self,
        repository: PassBRepository,
        executive: ConversationExecutive,
    ) -> None:
        self.repository = repository
        self.executive = executive

    def begin(self, message: str) -> ConversationOutcome:
        self._message(None, "FOUNDER", message, "PROJECT_REQUEST")
        project, intake = self.executive.begin(message)
        draft = self.executive.draft(project.project_id, intake)
        proposed = self.executive.propose_charter(draft)
        now = _now()
        context = CharterDraftContextRecord(
            charter_draft_context_id=uuid.uuid4().hex,
            project_id=project.project_id,
            intake=_intake_to_dict(intake),
            charter_id=proposed.charter_id,
            charter_revision=proposed.revision,
            state="PROPOSED",
            created_at=now,
            updated_at=now,
            revision=1,
        )
        self.repository.insert(context)
        self._message(
            project.project_id,
            "KEEPER",
            self._proposal_summary(proposed, intake),
            "CHARTER_PROPOSAL",
        )
        return ConversationOutcome(
            project,
            proposed,
            intake.unresolved_questions,
            intake.proposed_assumptions,
            True,
        )

    def revise(
        self, project_id: str, replacements: dict[str, Any]
    ) -> ConversationOutcome:
        current = self.current_context(project_id)
        intake = ConversationIntake.revise(
            _intake_from_dict(current.intake), replacements=replacements
        )
        draft = self.executive.draft(project_id, intake)
        proposed = self.executive.propose_charter(draft)
        now = _now()
        self.repository.replace(
            replace(
                current,
                state="SUPERSEDED",
                updated_at=now,
                revision=current.revision + 1,
            ),
            expected_revision=current.revision,
        )
        context = CharterDraftContextRecord(
            charter_draft_context_id=uuid.uuid4().hex,
            project_id=project_id,
            intake=_intake_to_dict(intake),
            charter_id=proposed.charter_id,
            charter_revision=proposed.revision,
            state="PROPOSED",
            created_at=now,
            updated_at=now,
            revision=1,
        )
        self.repository.insert(context)
        self._message(
            project_id,
            "FOUNDER",
            f"Revised charter fields: {', '.join(sorted(replacements))}",
            "CHARTER_REVISION",
        )
        self._message(
            project_id,
            "KEEPER",
            self._proposal_summary(proposed, intake),
            "CHARTER_PROPOSAL",
        )
        return ConversationOutcome(
            ProjectRecord(
                project_id=project_id,
                name=proposed.title,
                project_type=proposed.project_type,
                state="AWAITING_CHARTER_APPROVAL",
                active_charter_id=None,
                active_charter_revision=None,
                pause_reason=None,
                created_at=proposed.created_at,
                updated_at=proposed.updated_at,
            ),
            proposed,
            intake.unresolved_questions,
            intake.proposed_assumptions,
            True,
        )

    def request_approval(self, project_id: str) -> FounderApprovalChallenge:
        current = self.current_context(project_id)
        if current.state != "PROPOSED":
            raise PermissionError("only the current proposed charter can be approved")
        charter = self._charter_from_context(current)
        challenge = self.executive.request_charter_approval(charter)
        now = _now()
        self.repository.replace(
            replace(
                current,
                state="APPROVAL_REQUESTED",
                updated_at=now,
                revision=current.revision + 1,
            ),
            expected_revision=current.revision,
        )
        return challenge

    def current_context(self, project_id: str) -> CharterDraftContextRecord:
        values = [
            item
            for item in self.repository.list(
                CharterDraftContextRecord, project_id=project_id
            )
            if item.state != "SUPERSEDED"
        ]
        if len(values) != 1:
            raise RuntimeError("project does not have one current charter draft")
        return values[0]

    def _charter_from_context(
        self, context: CharterDraftContextRecord
    ) -> ProjectCharter:
        # Draft/proposal truth remains in the Executive repository. Re-drafting
        # the exact durable intake returns the current version-bound proposal.
        draft = self.executive.draft(
            context.project_id, _intake_from_dict(context.intake)
        )
        if (
            draft.charter_id != context.charter_id
            or draft.revision != context.charter_revision
        ):
            raise PermissionError("durable charter context is stale")
        return draft

    def _message(
        self,
        project_id: str | None,
        speaker: str,
        text: str,
        intent: str,
    ) -> ConversationMessageRecord:
        record = ConversationMessageRecord(
            message_id=uuid.uuid4().hex,
            project_id=project_id,
            speaker=speaker,
            text=text,
            intent=intent,
            durable_authority=False,
            created_at=_now(),
            revision=1,
        )
        self.repository.insert(record)
        return record

    @staticmethod
    def _proposal_summary(
        charter: ProjectCharter, intake: IntakeResult
    ) -> str:
        questions = (
            " Material questions: " + "; ".join(intake.unresolved_questions)
            if intake.unresolved_questions
            else ""
        )
        return (
            f"Proposed charter revision {charter.revision}: {charter.title}. "
            f"Goals: {', '.join(charter.deliverables)}. "
            f"Exclusions: {', '.join(charter.non_goals) or 'none recorded'}. "
            "Conversation text is not approval; explicit Founder confirmation "
            f"is required.{questions}"
        )


class DynamicWorkflowDesigner:
    """Charter-derived workflow selection; there is no universal pipeline."""

    def design(self, charter: ProjectCharter) -> WorkflowBlueprint:
        if (
            charter.status != CharterStatus.ACTIVE
            or not charter.founder_approval_record_id
            or not charter.founder_authorization_capability_digest
        ):
            raise PermissionError("workflow design requires active Founder authority")
        templates: dict[str, tuple[tuple[str, str, str, bool], ...]] = {
            "software": (
                ("Plan", "PLANNER", "Translate charter into bounded work", False),
                ("Implement", "IMPLEMENTER", "Create assigned deliverables", False),
                ("Test", "TESTER", "Verify behavior and failure paths", True),
                ("Review", "REVIEWER", "Independently assess evidence", True),
            ),
            "research": (
                ("Research plan", "PLANNER", "Bound questions and sources", False),
                ("Investigate", "RESEARCHER", "Collect structured evidence", False),
                ("Review sources", "REVIEWER", "Assess provenance and gaps", True),
                (
                    "Synthesize",
                    "DOCUMENTATION_SPECIALIST",
                    "Produce the supported report",
                    False,
                ),
            ),
            "video": (
                ("Creative plan", "PLANNER", "Define audience and structure", False),
                (
                    "Produce assets",
                    "IMPLEMENTER",
                    "Create charter-approved media assets",
                    False,
                ),
                ("Quality review", "REVIEWER", "Review delivery evidence", True),
            ),
            "writing": (
                ("Outline", "PLANNER", "Design structure and voice", False),
                (
                    "Draft",
                    "DOCUMENTATION_SPECIALIST",
                    "Create the manuscript",
                    False,
                ),
                ("Editorial review", "REVIEWER", "Independently review", True),
                (
                    "Revise",
                    "DOCUMENTATION_SPECIALIST",
                    "Address accepted findings",
                    False,
                ),
            ),
        }
        selected = templates.get(
            charter.project_type,
            (
                ("Plan", "PLANNER", "Design a charter-specific workflow", False),
                ("Produce", "IMPLEMENTER", "Create the deliverables", False),
                ("Review", "REVIEWER", "Independently review evidence", True),
            ),
        )
        steps: list[WorkflowStepBlueprint] = []
        previous: str | None = None
        for title, role, objective, independent in selected:
            steps.append(
                WorkflowStepBlueprint(
                    title=title,
                    role=role,
                    objective=objective,
                    dependencies=(previous,) if previous else (),
                    independent_review=independent,
                )
            )
            previous = title
        return WorkflowBlueprint(
            project_id=charter.project_id,
            charter_id=charter.charter_id,
            charter_revision=charter.revision,
            strategy=f"{charter.project_type}-adaptive",
            explanation=(
                "Stages were selected from the approved project type, "
                "deliverables, evidence needs, and review requirements."
            ),
            steps=tuple(steps),
        )


FORBIDDEN_DELEGATED_SCOPE = frozenset(
    {
        "HISTORY_REWRITE",
        "DELETE_BACKUP",
        "DELETE_WORKTREE",
        "SPENDING",
        "PAID_FALLBACK",
        "DEPLOY_PRODUCTION",
        "PUBLISH",
        "LIVE_TRADING",
        "CREDENTIAL_CHANGE",
        "SECURITY_BOUNDARY_CHANGE",
        "EXPAND_GOVERNANCE",
        "EXPAND_CHARTER",
    }
)


def activate_delegated_mode(
    repository: PassBRepository,
    *,
    project_id: str,
    charter: ProjectCharter,
    founder_identity: str,
    founder_approval_id: str,
    founder_approval_digest: str,
    scope: tuple[str, ...],
    expires_at: str,
) -> DelegatedModeGrantRecord:
    if (
        charter.project_id != project_id
        or charter.status != CharterStatus.ACTIVE
        or charter.delegation_mode not in {"DELEGATED", "FULL_DELEGATION"}
        or not charter.founder_approval_record_id
        or not charter.founder_approval_identity
        or not charter.founder_authorization_capability_digest
        or founder_approval_id != charter.founder_approval_record_id
        or founder_identity != charter.founder_approval_identity
        or founder_approval_digest
        != charter.founder_authorization_capability_digest
        or not scope
        or FORBIDDEN_DELEGATED_SCOPE.intersection(scope)
    ):
        raise PermissionError("delegated mode is outside Founder charter authority")
    now = _now()
    if _parse_time(expires_at) <= _parse_time(now):
        raise ValueError("delegated mode expiry must be in the future")
    record = DelegatedModeGrantRecord(
        delegated_mode_grant_id=uuid.uuid4().hex,
        project_id=project_id,
        charter_id=charter.charter_id,
        charter_revision=charter.revision,
        founder_identity=founder_identity,
        founder_approval_id=founder_approval_id,
        founder_approval_digest=founder_approval_digest,
        scope=scope,
        starts_at=now,
        expires_at=expires_at,
        state=DelegatedModeState.ACTIVE,
        revoked_at=None,
        created_at=now,
        updated_at=now,
        revision=1,
    )
    repository.insert(record)
    return record


def revoke_delegated_mode(
    repository: PassBRepository, grant_id: str
) -> DelegatedModeGrantRecord:
    record = repository.get(DelegatedModeGrantRecord, grant_id)
    if record.state != DelegatedModeState.ACTIVE:
        raise PermissionError("delegated mode is not active")
    now = _now()
    return repository.replace(
        replace(
            record,
            state=DelegatedModeState.REVOKED,
            revoked_at=now,
            updated_at=now,
            revision=record.revision + 1,
        ),
        expected_revision=record.revision,
    )


def _intake_to_dict(value: IntakeResult) -> dict[str, Any]:
    return value.to_dict()


def _intake_from_dict(value: dict[str, Any]) -> IntakeResult:
    fields = value.get("fields")
    questions = value.get("unresolved_questions")
    assumptions = value.get("proposed_assumptions")
    if (
        not isinstance(fields, dict)
        or not isinstance(questions, list)
        or not isinstance(assumptions, list)
    ):
        raise ValueError("durable intake context is malformed")
    converted: dict[str, IntakeValue] = {}
    for key, item in fields.items():
        if not isinstance(key, str) or not isinstance(item, dict):
            raise ValueError("durable intake field is malformed")
        converted[key] = IntakeValue(
            item["value"],
            str(item["provenance"]),
            float(item["confidence"]),
            str(item["source_excerpt"]),
        )
    return IntakeResult(
        converted,
        tuple(str(item) for item in questions),
        tuple(str(item) for item in assumptions),
    )


def _parse_time(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        raise ValueError("timestamp must be timezone aware")
    return parsed


def _now() -> str:
    return datetime.now(UTC).isoformat()
