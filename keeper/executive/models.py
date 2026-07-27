from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any, ClassVar, TypeVar, cast

from keeper.executive.enums import (
    ActionCategory,
    ApprovalKind,
    AuthorityOutcome,
    CharterStatus,
    DelegationMode,
    ExecutiveState,
    MemoryKind,
    ReviewPolicy,
    TaskStatus,
    ValueProvenance,
)


T = TypeVar("T", bound="StrictRecord")


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def validate_timestamp(value: str, field_name: str) -> None:
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as error:
        raise ValueError(f"{field_name} must be an ISO timestamp") from error
    if parsed.tzinfo is None:
        raise ValueError(f"{field_name} must be timezone aware")


@dataclass(frozen=True, slots=True)
class StrictRecord:
    FIELDS: ClassVar[frozenset[str]]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def _validated_data(cls: type[T], value: dict[str, Any]) -> dict[str, Any]:
        unknown = set(value) - cls.FIELDS
        missing = cls.FIELDS - set(value)
        if unknown or missing:
            raise ValueError(
                f"{cls.__name__} fields invalid; unknown={sorted(unknown)}, "
                f"missing={sorted(missing)}"
            )
        return dict(value)


@dataclass(frozen=True, slots=True)
class AuthorityEnvelope(StrictRecord):
    allowed_actions: tuple[str, ...]
    separately_approvable_actions: tuple[str, ...]
    denied_actions: tuple[str, ...]
    allowed_workspaces: tuple[str, ...]
    allowed_tools: tuple[str, ...]
    allowed_providers: tuple[str, ...]
    maximum_cost: float
    risk_limit: str
    data_classifications: tuple[str, ...]
    expires_at: str | None

    FIELDS = frozenset(
        {
            "allowed_actions",
            "separately_approvable_actions",
            "denied_actions",
            "allowed_workspaces",
            "allowed_tools",
            "allowed_providers",
            "maximum_cost",
            "risk_limit",
            "data_classifications",
            "expires_at",
        }
    )

    def __post_init__(self) -> None:
        if self.maximum_cost < 0:
            raise ValueError("maximum_cost cannot be negative")
        if self.expires_at is not None:
            validate_timestamp(self.expires_at, "expires_at")

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> AuthorityEnvelope:
        data = cls._validated_data(value)
        for key in (
            "allowed_actions",
            "separately_approvable_actions",
            "denied_actions",
            "allowed_workspaces",
            "allowed_tools",
            "allowed_providers",
            "data_classifications",
        ):
            data[key] = tuple(data[key])
        return cls(**data)


@dataclass(frozen=True, slots=True)
class ProjectRecord(StrictRecord):
    project_id: str
    name: str
    project_type: str
    state: str
    active_charter_id: str | None
    active_charter_revision: int | None
    pause_reason: str | None
    created_at: str
    updated_at: str

    FIELDS = frozenset(
        {
            "project_id",
            "name",
            "project_type",
            "state",
            "active_charter_id",
            "active_charter_revision",
            "pause_reason",
            "created_at",
            "updated_at",
        }
    )

    def __post_init__(self) -> None:
        ExecutiveState(self.state)
        validate_timestamp(self.created_at, "created_at")
        validate_timestamp(self.updated_at, "updated_at")

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> ProjectRecord:
        return cls(**cls._validated_data(value))


@dataclass(frozen=True, slots=True)
class ProjectCharter(StrictRecord):
    charter_id: str
    project_id: str
    title: str
    project_type: str
    purpose: str
    problem_statement: str
    desired_outcome: str
    deliverables: tuple[str, ...]
    non_goals: tuple[str, ...]
    success_criteria: tuple[str, ...]
    constraints: tuple[str, ...]
    assumptions: tuple[str, ...]
    unresolved_questions: tuple[str, ...]
    timeline: str | None
    budget_policy: str
    budget_limit: float
    approved_tools: tuple[str, ...]
    approved_providers: tuple[str, ...]
    prohibited_tools: tuple[str, ...]
    prohibited_providers: tuple[str, ...]
    workspaces: tuple[str, ...]
    data_privacy_restrictions: tuple[str, ...]
    risk_classification: str
    delegation_mode: str
    authority_envelope: AuthorityEnvelope
    escalation_rules: tuple[str, ...]
    review_requirements: tuple[str, ...]
    evidence_requirements: tuple[str, ...]
    completion_definition: tuple[str, ...]
    revision: int
    status: str
    supersedes_charter_id: str | None
    change_reason: str | None
    differences: tuple[str, ...]
    founder_approval_identity: str | None
    founder_approval_record_id: str | None
    created_at: str
    updated_at: str

    FIELDS = frozenset(
        {
            "charter_id", "project_id", "title", "project_type", "purpose",
            "problem_statement", "desired_outcome", "deliverables", "non_goals",
            "success_criteria", "constraints", "assumptions", "unresolved_questions",
            "timeline", "budget_policy", "budget_limit", "approved_tools",
            "approved_providers", "prohibited_tools", "prohibited_providers",
            "workspaces", "data_privacy_restrictions", "risk_classification",
            "delegation_mode", "authority_envelope", "escalation_rules",
            "review_requirements", "evidence_requirements", "completion_definition",
            "revision", "status", "supersedes_charter_id", "change_reason",
            "differences", "founder_approval_identity", "founder_approval_record_id",
            "created_at", "updated_at",
        }
    )
    TUPLE_FIELDS = (
        "deliverables", "non_goals", "success_criteria", "constraints", "assumptions",
        "unresolved_questions", "approved_tools", "approved_providers",
        "prohibited_tools", "prohibited_providers", "workspaces",
        "data_privacy_restrictions", "escalation_rules", "review_requirements",
        "evidence_requirements", "completion_definition", "differences",
    )

    def __post_init__(self) -> None:
        if self.revision < 1 or self.budget_limit < 0:
            raise ValueError("charter revision and budget must be valid")
        CharterStatus(self.status)
        DelegationMode(self.delegation_mode)
        validate_timestamp(self.created_at, "created_at")
        validate_timestamp(self.updated_at, "updated_at")
        if self.status in {CharterStatus.APPROVED, CharterStatus.ACTIVE} and (
            not self.founder_approval_identity or not self.founder_approval_record_id
        ):
            raise ValueError("approved charters require a Founder approval record")

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> ProjectCharter:
        data = cls._validated_data(value)
        for key in cls.TUPLE_FIELDS:
            data[key] = tuple(data[key])
        envelope = data["authority_envelope"]
        if not isinstance(envelope, dict):
            raise ValueError("authority_envelope must be an object")
        data["authority_envelope"] = AuthorityEnvelope.from_dict(envelope)
        return cls(**data)


@dataclass(frozen=True, slots=True)
class ApprovalRecord(StrictRecord):
    approval_id: str
    project_id: str
    charter_id: str
    charter_revision: int
    kind: str
    action_category: str | None
    approver: str
    scope: tuple[str, ...]
    limits: dict[str, Any]
    approved_at: str
    expires_at: str | None
    revoked_at: str | None
    consumed_at: str | None
    evidence_digest: str
    source_interaction_id: str

    FIELDS = frozenset(
        {
            "approval_id", "project_id", "charter_id", "charter_revision", "kind",
            "action_category", "approver", "scope", "limits", "approved_at",
            "expires_at", "revoked_at", "consumed_at", "evidence_digest",
            "source_interaction_id",
        }
    )

    def __post_init__(self) -> None:
        ApprovalKind(self.kind)
        if self.action_category is not None:
            ActionCategory(self.action_category)
        for name, value in (
            ("approved_at", self.approved_at),
            ("expires_at", self.expires_at),
            ("revoked_at", self.revoked_at),
            ("consumed_at", self.consumed_at),
        ):
            if value is not None:
                validate_timestamp(value, name)

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> ApprovalRecord:
        data = cls._validated_data(value)
        data["scope"] = tuple(data["scope"])
        return cls(**data)


@dataclass(frozen=True, slots=True)
class ProposedAction(StrictRecord):
    action_id: str
    project_id: str
    charter_revision: int
    category: str
    target_resource: str
    provider: str | None
    tool: str | None
    workspace: str | None
    scope: tuple[str, ...]
    cost: float
    reversible: bool
    risk: str
    data_classification: str
    external_side_effect: bool

    FIELDS = frozenset(
        {
            "action_id", "project_id", "charter_revision", "category",
            "target_resource", "provider", "tool", "workspace", "scope", "cost",
            "reversible", "risk", "data_classification", "external_side_effect",
        }
    )

    def __post_init__(self) -> None:
        ActionCategory(self.category)
        if self.cost < 0:
            raise ValueError("action cost cannot be negative")

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> ProposedAction:
        data = cls._validated_data(value)
        data["scope"] = tuple(data["scope"])
        return cls(**data)


@dataclass(frozen=True, slots=True)
class AuthorityDecision(StrictRecord):
    outcome: str
    rule: str
    charter_field: str
    limits: dict[str, Any]
    reason: str
    required_next_step: str
    approval_id: str | None = None

    FIELDS = frozenset(
        {
            "outcome", "rule", "charter_field", "limits", "reason",
            "required_next_step", "approval_id",
        }
    )

    def __post_init__(self) -> None:
        AuthorityOutcome(self.outcome)

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> AuthorityDecision:
        return cls(**cls._validated_data(value))


@dataclass(frozen=True, slots=True)
class WorkflowStage(StrictRecord):
    stage_id: str
    title: str
    purpose: str
    rationale: str
    dependencies: tuple[str, ...]
    milestone: bool

    FIELDS = frozenset(
        {"stage_id", "title", "purpose", "rationale", "dependencies", "milestone"}
    )

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> WorkflowStage:
        data = cls._validated_data(value)
        data["dependencies"] = tuple(data["dependencies"])
        return cls(**data)


@dataclass(frozen=True, slots=True)
class WorkflowRecord(StrictRecord):
    workflow_id: str
    project_id: str
    charter_id: str
    charter_revision: int
    revision: int
    strategy: str
    explanation: str
    stages: tuple[WorkflowStage, ...]
    created_at: str

    FIELDS = frozenset(
        {
            "workflow_id", "project_id", "charter_id", "charter_revision",
            "revision", "strategy", "explanation", "stages", "created_at",
        }
    )

    def __post_init__(self) -> None:
        validate_timestamp(self.created_at, "created_at")

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> WorkflowRecord:
        data = cls._validated_data(value)
        data["stages"] = tuple(
            WorkflowStage.from_dict(item) for item in data["stages"]
        )
        return cls(**data)


@dataclass(frozen=True, slots=True)
class ExecutiveTask(StrictRecord):
    task_id: str
    project_id: str
    charter_id: str
    charter_revision: int
    workflow_id: str
    stage_id: str
    title: str
    objective: str
    role: str
    required_capabilities: tuple[str, ...]
    instructions: tuple[str, ...]
    constraints: tuple[str, ...]
    dependencies: tuple[str, ...]
    provider_id: str | None
    model_id: str | None
    session_id: str | None
    status: str
    authority_category: str
    inputs: tuple[str, ...]
    expected_outputs: tuple[str, ...]
    evidence_requirements: tuple[str, ...]
    review_requirements: tuple[str, ...]
    retry_count: int
    max_retries: int
    attempt_history: tuple[dict[str, Any], ...]
    result_disposition: str | None
    created_at: str
    updated_at: str

    FIELDS = frozenset(
        {
            "task_id", "project_id", "charter_id", "charter_revision",
            "workflow_id", "stage_id", "title", "objective", "role",
            "required_capabilities", "instructions", "constraints", "dependencies",
            "provider_id", "model_id", "session_id", "status",
            "authority_category", "inputs", "expected_outputs",
            "evidence_requirements", "review_requirements", "retry_count",
            "max_retries", "attempt_history", "result_disposition", "created_at",
            "updated_at",
        }
    )
    TUPLE_FIELDS = (
        "required_capabilities", "instructions", "constraints", "dependencies",
        "inputs", "expected_outputs", "evidence_requirements", "review_requirements",
        "attempt_history",
    )

    def __post_init__(self) -> None:
        TaskStatus(self.status)
        ActionCategory(self.authority_category)
        if self.retry_count < 0 or self.max_retries < 0:
            raise ValueError("retry counts cannot be negative")
        validate_timestamp(self.created_at, "created_at")
        validate_timestamp(self.updated_at, "updated_at")

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> ExecutiveTask:
        data = cls._validated_data(value)
        for key in cls.TUPLE_FIELDS:
            data[key] = tuple(data[key])
        return cls(**data)


@dataclass(frozen=True, slots=True)
class DecisionRecord(StrictRecord):
    decision_id: str
    project_id: str
    charter_revision: int
    subject: str
    options_considered: tuple[str, ...]
    selected_option: str
    rationale: str
    decision_maker: str
    authority_basis: str
    evidence: tuple[str, ...]
    consequences: tuple[str, ...]
    reversible: bool
    decided_at: str
    supersedes_decision_id: str | None

    FIELDS = frozenset(
        {
            "decision_id", "project_id", "charter_revision", "subject",
            "options_considered", "selected_option", "rationale", "decision_maker",
            "authority_basis", "evidence", "consequences", "reversible",
            "decided_at", "supersedes_decision_id",
        }
    )

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> DecisionRecord:
        data = cls._validated_data(value)
        for key in ("options_considered", "evidence", "consequences"):
            data[key] = tuple(data[key])
        validate_timestamp(cast(str, data["decided_at"]), "decided_at")
        return cls(**data)


@dataclass(frozen=True, slots=True)
class AssumptionRecord(StrictRecord):
    assumption_id: str
    project_id: str
    charter_revision: int
    assumption: str
    source: str
    confidence: float
    validation_plan: str
    impact_if_false: str
    status: str
    resolution: str | None
    created_at: str

    FIELDS = frozenset(
        {
            "assumption_id", "project_id", "charter_revision", "assumption",
            "source", "confidence", "validation_plan", "impact_if_false", "status",
            "resolution", "created_at",
        }
    )

    def __post_init__(self) -> None:
        if not 0 <= self.confidence <= 1:
            raise ValueError("confidence must be between zero and one")
        validate_timestamp(self.created_at, "created_at")

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> AssumptionRecord:
        return cls(**cls._validated_data(value))


@dataclass(frozen=True, slots=True)
class MemoryRecord(StrictRecord):
    memory_id: str
    project_id: str
    charter_revision: int
    task_id: str | None
    stage_id: str | None
    kind: str
    provenance: str
    category: str
    content: str
    authority_relevant: bool
    evidence: tuple[str, ...]
    superseded_by: str | None
    created_at: str

    FIELDS = frozenset(
        {
            "memory_id", "project_id", "charter_revision", "task_id", "stage_id",
            "kind", "provenance", "category", "content", "authority_relevant",
            "evidence", "superseded_by", "created_at",
        }
    )

    def __post_init__(self) -> None:
        MemoryKind(self.kind)
        ValueProvenance(self.provenance)
        validate_timestamp(self.created_at, "created_at")

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> MemoryRecord:
        data = cls._validated_data(value)
        data["evidence"] = tuple(data["evidence"])
        return cls(**data)


@dataclass(frozen=True, slots=True)
class SpecialistProfile(StrictRecord):
    provider_id: str
    model_id: str
    session_id: str
    capabilities: tuple[str, ...]
    project_types: tuple[str, ...]
    qualified: bool
    available: bool
    independence_identity: str
    cost_tier: int
    effort_levels: tuple[str, ...]
    credential_available: bool
    prior_success_rate: float

    FIELDS = frozenset(
        {
            "provider_id", "model_id", "session_id", "capabilities",
            "project_types", "qualified", "available", "independence_identity",
            "cost_tier", "effort_levels", "credential_available",
            "prior_success_rate",
        }
    )

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> SpecialistProfile:
        data = cls._validated_data(value)
        data["capabilities"] = tuple(data["capabilities"])
        data["project_types"] = tuple(data["project_types"])
        return cls(**data)


@dataclass(frozen=True, slots=True)
class ReviewResult(StrictRecord):
    accepted: bool
    disposition: str
    failed_criteria: tuple[str, ...]
    evidence: tuple[str, ...]
    repair_instructions: tuple[str, ...]
    review_policy: str

    FIELDS = frozenset(
        {
            "accepted", "disposition", "failed_criteria", "evidence",
            "repair_instructions", "review_policy",
        }
    )

    def __post_init__(self) -> None:
        ReviewPolicy(self.review_policy)

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> ReviewResult:
        data = cls._validated_data(value)
        for key in ("failed_criteria", "evidence", "repair_instructions"):
            data[key] = tuple(data[key])
        return cls(**data)
