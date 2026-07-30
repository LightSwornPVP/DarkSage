from __future__ import annotations

import math
from dataclasses import asdict, dataclass, fields
from datetime import datetime
from typing import Any, ClassVar, TypeVar

from keeper.pass_b.enums import (
    AssignmentRole,
    AssignmentState,
    AttemptState,
    CostMode,
    DelegatedModeState,
    EvidenceReferenceKind,
    EvidenceReferenceState,
    EvidenceState,
    HealthState,
    PauseCode,
    PresentationMode,
    ProviderClassification,
    ProviderSessionState,
    ReservationMode,
    ReservationState,
    ReviewState,
    SessionModel,
    WorkItemState,
    WorkflowState,
)


R = TypeVar("R", bound="PassBRecord")


def _timestamp(value: str, name: str) -> None:
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as error:
        raise ValueError(f"{name} must be an ISO timestamp") from error
    if parsed.tzinfo is None:
        raise ValueError(f"{name} must be timezone aware")


def _optional_timestamp(value: str | None, name: str) -> None:
    if value is not None:
        _timestamp(value, name)


def _positive_revision(value: int) -> None:
    if value < 1:
        raise ValueError("record revision must be positive")


@dataclass(frozen=True, slots=True)
class PassBRecord:
    KIND: ClassVar[str]
    ID_FIELD: ClassVar[str]
    TUPLE_FIELDS: ClassVar[tuple[str, ...]] = ()
    DEFAULTS: ClassVar[dict[str, Any]] = {}

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls: type[R], value: dict[str, Any]) -> R:
        expected = {item.name for item in fields(cls) if item.init}
        normalized = {**cls.DEFAULTS, **value}
        if set(normalized) != expected:
            raise ValueError(
                f"{cls.__name__} fields invalid; "
                f"unknown={sorted(set(normalized) - expected)}, "
                f"missing={sorted(expected - set(normalized))}"
            )
        for name in cls.TUPLE_FIELDS:
            normalized[name] = tuple(normalized[name])
        return cls(**normalized)

    @property
    def record_id(self) -> str:
        value = getattr(self, self.ID_FIELD)
        if not isinstance(value, str) or not value:
            raise ValueError(f"{self.ID_FIELD} must be a durable identity")
        return value


@dataclass(frozen=True, slots=True)
class ProviderRecord(PassBRecord):
    provider_id: str
    identity: str
    display_name: str
    classification: str
    adapter_kind: str
    capabilities: tuple[str, ...]
    session_model: str
    usage_pool_strategy: str
    concurrency_limit: int
    cost_mode: str
    authentication_ready: bool
    tool_support: tuple[str, ...]
    workspace_support: tuple[str, ...]
    cancellation_support: bool
    resume_support: bool
    evidence_format: str
    health: str
    created_at: str
    updated_at: str
    revision: int
    authority_registration_id: str | None = None

    KIND = "provider"
    ID_FIELD = "provider_id"
    TUPLE_FIELDS = ("capabilities", "tool_support", "workspace_support")
    DEFAULTS = {"authority_registration_id": None}

    def __post_init__(self) -> None:
        ProviderClassification(self.classification)
        SessionModel(self.session_model)
        CostMode(self.cost_mode)
        HealthState(self.health)
        if self.concurrency_limit < 1:
            raise ValueError("provider concurrency limit must be positive")
        _timestamp(self.created_at, "created_at")
        _timestamp(self.updated_at, "updated_at")
        _positive_revision(self.revision)


@dataclass(frozen=True, slots=True)
class ProviderAccountRecord(PassBRecord):
    account_id: str
    provider_id: str
    identity: str
    display_name: str
    usage_pool_id: str
    cost_mode: str
    privacy_classification: str
    authentication_ready: bool
    enabled: bool
    created_at: str
    updated_at: str
    revision: int

    KIND = "provider_account"
    ID_FIELD = "account_id"

    def __post_init__(self) -> None:
        CostMode(self.cost_mode)
        _timestamp(self.created_at, "created_at")
        _timestamp(self.updated_at, "updated_at")
        _positive_revision(self.revision)


@dataclass(frozen=True, slots=True)
class ProviderSessionRecord(PassBRecord):
    session_id: str
    provider_id: str
    account_id: str
    model_id: str
    external_session_id: str | None
    state: str
    concurrency_limit: int
    active_assignments: int
    supports_resume: bool
    resume_token_digest: str | None
    last_seen_at: str
    created_at: str
    updated_at: str
    revision: int

    KIND = "provider_session"
    ID_FIELD = "session_id"

    def __post_init__(self) -> None:
        ProviderSessionState(self.state)
        if (
            self.concurrency_limit < 1
            or self.active_assignments < 0
            or self.active_assignments > self.concurrency_limit
        ):
            raise ValueError("provider session concurrency is invalid")
        _timestamp(self.last_seen_at, "last_seen_at")
        _timestamp(self.created_at, "created_at")
        _timestamp(self.updated_at, "updated_at")
        _positive_revision(self.revision)


@dataclass(frozen=True, slots=True)
class UsagePoolRecord(PassBRecord):
    pool_id: str
    provider_id: str
    account_id: str
    identity: str
    limit_type: str
    capacity: float | None
    consumed: float
    reserved: float
    remaining: float | None
    reset_at: str | None
    observation_source: str
    confidence: str
    exhausted: bool
    last_observed_at: str
    created_at: str
    updated_at: str
    revision: int
    observation_generation: int = 1

    KIND = "usage_pool"
    ID_FIELD = "pool_id"
    DEFAULTS = {"observation_generation": 1}

    def __post_init__(self) -> None:
        values = [self.consumed, self.reserved]
        if self.capacity is not None:
            values.append(self.capacity)
        if self.remaining is not None:
            values.append(self.remaining)
        if any(not math.isfinite(value) or value < 0 for value in values):
            raise ValueError(
                "usage values must be finite and cannot be negative"
            )
        if self.observation_generation < 1:
            raise ValueError("usage observation generation must be positive")
        _optional_timestamp(self.reset_at, "reset_at")
        _timestamp(self.last_observed_at, "last_observed_at")
        _timestamp(self.created_at, "created_at")
        _timestamp(self.updated_at, "updated_at")
        _positive_revision(self.revision)


@dataclass(frozen=True, slots=True)
class WorkflowRecord(PassBRecord):
    workflow_id: str
    project_id: str
    charter_id: str
    charter_revision: int
    strategy: str
    authority_envelope_digest: str
    state: str
    created_at: str
    updated_at: str
    revision: int

    KIND = "workflow"
    ID_FIELD = "workflow_id"

    def __post_init__(self) -> None:
        WorkflowState(self.state)
        if (
            self.charter_revision < 1
            or not self.strategy
            or len(self.authority_envelope_digest) != 64
        ):
            raise ValueError("workflow charter binding is invalid")
        _timestamp(self.created_at, "created_at")
        _timestamp(self.updated_at, "updated_at")
        _positive_revision(self.revision)


@dataclass(frozen=True, slots=True)
class WorkItemRecord(PassBRecord):
    work_item_id: str
    project_id: str
    charter_id: str
    charter_revision: int
    workflow_id: str
    title: str
    objective: str
    dependencies: tuple[str, ...]
    required_roles: tuple[str, ...]
    state: str
    created_at: str
    updated_at: str
    revision: int

    KIND = "work_item"
    ID_FIELD = "work_item_id"
    TUPLE_FIELDS = ("dependencies", "required_roles")

    def __post_init__(self) -> None:
        WorkItemState(self.state)
        if self.charter_revision < 1:
            raise ValueError("work item charter revision must be positive")
        for role in self.required_roles:
            AssignmentRole(role)
        _timestamp(self.created_at, "created_at")
        _timestamp(self.updated_at, "updated_at")
        _positive_revision(self.revision)


@dataclass(frozen=True, slots=True)
class AssignmentRecord(PassBRecord):
    assignment_id: str
    project_id: str
    charter_id: str
    charter_revision: int
    workflow_id: str
    work_item_id: str
    provider_id: str
    account_id: str
    session_id: str
    role: str
    model_id: str
    workspace_id: str
    authority_envelope_digest: str
    expected_evidence: tuple[str, ...]
    usage_policy: dict[str, Any]
    state: str
    read_only: bool
    independence_key: str
    created_at: str
    updated_at: str
    revision: int

    KIND = "assignment"
    ID_FIELD = "assignment_id"
    TUPLE_FIELDS = ("expected_evidence",)

    def __post_init__(self) -> None:
        AssignmentRole(self.role)
        AssignmentState(self.state)
        if self.charter_revision < 1 or not self.authority_envelope_digest:
            raise ValueError("assignment charter and authority binding are required")
        if self.role == AssignmentRole.REVIEWER and not self.read_only:
            raise ValueError("review assignments must be read-only")
        _timestamp(self.created_at, "created_at")
        _timestamp(self.updated_at, "updated_at")
        _positive_revision(self.revision)


@dataclass(frozen=True, slots=True)
class AttemptRecord(PassBRecord):
    attempt_id: str
    assignment_id: str
    authority_attempt_id: str
    launch_token: str
    state: str
    external_execution_id: str | None
    side_effect_class: str
    started_at: str | None
    finished_at: str | None
    last_error: str | None
    created_at: str
    updated_at: str
    revision: int
    workspace_reservation_id: str = ""
    usage_reservation_id: str | None = None
    launch_plan_digest: str = ""
    session_slot_claimed: bool = False

    KIND = "attempt"
    ID_FIELD = "attempt_id"
    DEFAULTS = {
        "workspace_reservation_id": "legacy-unbound",
        "usage_reservation_id": None,
        "launch_plan_digest": "legacy-unbound",
        "session_slot_claimed": False,
    }

    def __post_init__(self) -> None:
        AttemptState(self.state)
        if (
            not self.authority_attempt_id
            or not self.launch_token
            or not self.workspace_reservation_id
            or not self.launch_plan_digest
        ):
            raise ValueError("attempt authority and launch identities are required")
        _optional_timestamp(self.started_at, "started_at")
        _optional_timestamp(self.finished_at, "finished_at")
        _timestamp(self.created_at, "created_at")
        _timestamp(self.updated_at, "updated_at")
        _positive_revision(self.revision)


@dataclass(frozen=True, slots=True)
class ReviewRecord(PassBRecord):
    review_id: str
    project_id: str
    assignment_id: str
    attempt_id: str
    reviewer_assignment_id: str
    independence_key: str
    state: str
    findings: tuple[dict[str, Any], ...]
    disposition: str | None
    created_at: str
    updated_at: str
    revision: int
    producer_evidence_bundle_id: str = ""
    reviewer_attempt_id: str = ""
    reviewer_evidence_bundle_id: str = ""

    KIND = "review"
    ID_FIELD = "review_id"
    TUPLE_FIELDS = ("findings",)
    DEFAULTS = {
        "producer_evidence_bundle_id": "legacy-unbound",
        "reviewer_attempt_id": "legacy-unbound",
        "reviewer_evidence_bundle_id": "legacy-unbound",
    }

    def __post_init__(self) -> None:
        ReviewState(self.state)
        if (
            not self.producer_evidence_bundle_id
            or not self.reviewer_attempt_id
            or not self.reviewer_evidence_bundle_id
        ):
            raise ValueError(
                "review requires producer and reviewer execution evidence"
            )
        _timestamp(self.created_at, "created_at")
        _timestamp(self.updated_at, "updated_at")
        _positive_revision(self.revision)


@dataclass(frozen=True, slots=True)
class EvidenceBundleRecord(PassBRecord):
    evidence_bundle_id: str
    project_id: str
    assignment_id: str
    attempt_id: str
    producer_provider_id: str
    producer_session_id: str
    schema_version: int
    artifacts: tuple[dict[str, Any], ...]
    summary: str
    content_digest: str
    state: str
    validation_errors: tuple[str, ...]
    created_at: str
    updated_at: str
    revision: int

    KIND = "evidence_bundle"
    ID_FIELD = "evidence_bundle_id"
    TUPLE_FIELDS = ("artifacts", "validation_errors")

    def __post_init__(self) -> None:
        EvidenceState(self.state)
        if self.schema_version != 1 or len(self.content_digest) != 64:
            raise ValueError("evidence schema or digest is invalid")
        _timestamp(self.created_at, "created_at")
        _timestamp(self.updated_at, "updated_at")
        _positive_revision(self.revision)


@dataclass(frozen=True, slots=True)
class EvidenceReferenceRecord(PassBRecord):
    evidence_reference_id: str
    project_id: str
    charter_id: str
    charter_revision: int
    workflow_id: str
    work_item_id: str
    assignment_id: str
    source_kind: str
    source_identity: str
    canonical_source_path: str | None
    source_evidence_bundle_id: str | None
    sha256: str
    size_bytes: int
    state: str
    validation_error: str | None
    created_at: str
    validated_at: str | None
    updated_at: str
    revision: int

    KIND = "evidence_reference"
    ID_FIELD = "evidence_reference_id"

    def __post_init__(self) -> None:
        kind = EvidenceReferenceKind(self.source_kind)
        EvidenceReferenceState(self.state)
        if len(self.sha256) != 64 or any(
            item not in "0123456789abcdef" for item in self.sha256
        ):
            raise ValueError("evidence reference digest is invalid")
        if self.size_bytes < 0:
            raise ValueError("evidence reference size is invalid")
        if (
            kind == EvidenceReferenceKind.LOCAL_PROTECTED_ARTIFACT
            and not self.canonical_source_path
        ):
            raise ValueError("local evidence reference requires a source path")
        if (
            kind == EvidenceReferenceKind.REMOTE_STRUCTURED_EVIDENCE
            and self.canonical_source_path is not None
        ):
            raise ValueError("remote evidence reference cannot expose a local path")
        if self.charter_revision < 1 or not self.source_identity:
            raise ValueError("evidence reference binding is invalid")
        _timestamp(self.created_at, "created_at")
        _optional_timestamp(self.validated_at, "validated_at")
        _timestamp(self.updated_at, "updated_at")
        _positive_revision(self.revision)


@dataclass(frozen=True, slots=True)
class WorkspaceReservationRecord(PassBRecord):
    workspace_reservation_id: str
    project_id: str
    assignment_id: str
    workspace_id: str
    canonical_path: str
    mode: str
    owner_token: str
    lease_expires_at: str
    state: str
    worktree_branch: str | None
    base_commit: str | None
    created_at: str
    updated_at: str
    revision: int

    KIND = "workspace_reservation"
    ID_FIELD = "workspace_reservation_id"

    def __post_init__(self) -> None:
        ReservationMode(self.mode)
        ReservationState(self.state)
        _timestamp(self.lease_expires_at, "lease_expires_at")
        _timestamp(self.created_at, "created_at")
        _timestamp(self.updated_at, "updated_at")
        _positive_revision(self.revision)


@dataclass(frozen=True, slots=True)
class WriteReservationRecord(PassBRecord):
    write_reservation_id: str
    workspace_reservation_id: str
    assignment_id: str
    scope: tuple[str, ...]
    scope_keys: tuple[str, ...]
    owner_token: str
    lease_expires_at: str
    state: str
    created_at: str
    updated_at: str
    revision: int

    KIND = "write_reservation"
    ID_FIELD = "write_reservation_id"
    TUPLE_FIELDS = ("scope", "scope_keys")

    def __post_init__(self) -> None:
        ReservationState(self.state)
        if not self.scope or len(self.scope) != len(self.scope_keys):
            raise ValueError("write reservation scope is invalid")
        _timestamp(self.lease_expires_at, "lease_expires_at")
        _timestamp(self.created_at, "created_at")
        _timestamp(self.updated_at, "updated_at")
        _positive_revision(self.revision)


@dataclass(frozen=True, slots=True)
class PauseReasonRecord(PassBRecord):
    pause_reason_id: str
    assignment_id: str
    code: str
    detail: str
    reset_at: str | None
    safe_to_release_workspace: bool
    created_at: str
    resolved_at: str | None
    revision: int

    KIND = "pause_reason"
    ID_FIELD = "pause_reason_id"

    def __post_init__(self) -> None:
        PauseCode(self.code)
        _optional_timestamp(self.reset_at, "reset_at")
        _timestamp(self.created_at, "created_at")
        _optional_timestamp(self.resolved_at, "resolved_at")
        _positive_revision(self.revision)


@dataclass(frozen=True, slots=True)
class ResumeCheckpointRecord(PassBRecord):
    resume_checkpoint_id: str
    assignment_id: str
    attempt_id: str | None
    project_id: str
    charter_id: str
    charter_revision: int
    workspace_reservation_id: str
    usage_pool_id: str
    authority_envelope_digest: str
    checkpoint_state: dict[str, Any]
    created_at: str
    resumed_at: str | None
    revision: int

    KIND = "resume_checkpoint"
    ID_FIELD = "resume_checkpoint_id"

    def __post_init__(self) -> None:
        if self.charter_revision < 1 or not self.authority_envelope_digest:
            raise ValueError("resume checkpoint binding is invalid")
        _timestamp(self.created_at, "created_at")
        _optional_timestamp(self.resumed_at, "resumed_at")
        _positive_revision(self.revision)


@dataclass(frozen=True, slots=True)
class DelegatedModeGrantRecord(PassBRecord):
    delegated_mode_grant_id: str
    project_id: str
    charter_id: str
    charter_revision: int
    founder_identity: str
    founder_approval_id: str
    founder_approval_digest: str
    scope: tuple[str, ...]
    starts_at: str
    expires_at: str
    state: str
    revoked_at: str | None
    created_at: str
    updated_at: str
    revision: int
    project_generation: str = ""
    max_actions: int = 0
    actions_used: int = 0
    last_action_at: str | None = None

    KIND = "delegated_mode_grant"
    ID_FIELD = "delegated_mode_grant_id"
    TUPLE_FIELDS = ("scope",)
    DEFAULTS = {
        "project_generation": "",
        "max_actions": 0,
        "actions_used": 0,
        "last_action_at": None,
    }

    def __post_init__(self) -> None:
        DelegatedModeState(self.state)
        if self.charter_revision < 1 or not self.founder_approval_digest:
            raise ValueError("delegated mode requires Founder-bound authority")
        _timestamp(self.starts_at, "starts_at")
        _timestamp(self.expires_at, "expires_at")
        _optional_timestamp(self.revoked_at, "revoked_at")
        _optional_timestamp(self.last_action_at, "last_action_at")
        if (
            self.max_actions < 0
            or self.actions_used < 0
            or self.actions_used > self.max_actions
        ):
            raise ValueError("delegated action count is invalid")
        _timestamp(self.created_at, "created_at")
        _timestamp(self.updated_at, "updated_at")
        _positive_revision(self.revision)


@dataclass(frozen=True, slots=True)
class ConversationMessageRecord(PassBRecord):
    message_id: str
    project_id: str | None
    speaker: str
    text: str
    intent: str
    durable_authority: bool
    created_at: str
    revision: int

    KIND = "conversation_message"
    ID_FIELD = "message_id"

    def __post_init__(self) -> None:
        if self.speaker not in {"FOUNDER", "KEEPER"}:
            raise ValueError("conversation speaker is invalid")
        if self.durable_authority:
            raise ValueError("conversation text cannot be durable authority")
        _timestamp(self.created_at, "created_at")
        _positive_revision(self.revision)


@dataclass(frozen=True, slots=True)
class PresentationStateRecord(PassBRecord):
    presentation_state_id: str
    project_id: str | None
    form: str
    mode: str
    expression: str
    intensity: float
    background: str
    ambient_effect: str
    updated_at: str
    revision: int
    avatar_asset_identity: str = "sage-default"
    activity_state: str = "LISTENING"
    mood: str = "CALM"
    interruption_state: str = "IDLE"
    authority_effect: str = "NONE"

    KIND = "presentation_state"
    ID_FIELD = "presentation_state_id"
    DEFAULTS = {
        "avatar_asset_identity": "sage-default",
        "activity_state": "LISTENING",
        "mood": "CALM",
        "interruption_state": "IDLE",
        "authority_effect": "NONE",
    }

    def __post_init__(self) -> None:
        PresentationMode(self.mode)
        if self.activity_state not in {"SPEAKING", "LISTENING", "THINKING"}:
            raise ValueError("Sage activity state is invalid")
        if self.interruption_state not in {"IDLE", "INTERRUPTED"}:
            raise ValueError("Sage interruption state is invalid")
        if self.authority_effect != "NONE":
            raise ValueError("Sage presentation cannot have authority effect")
        if not self.avatar_asset_identity or not self.mood:
            raise ValueError("Sage presentation identity is incomplete")
        if not math.isfinite(self.intensity) or not (
            0 <= self.intensity <= 1
        ):
            raise ValueError("presentation intensity must be between zero and one")
        _timestamp(self.updated_at, "updated_at")
        _positive_revision(self.revision)


PASS_B_RECORD_TYPES: tuple[type[PassBRecord], ...] = (
    ProviderRecord,
    ProviderAccountRecord,
    ProviderSessionRecord,
    UsagePoolRecord,
    WorkflowRecord,
    WorkItemRecord,
    AssignmentRecord,
    AttemptRecord,
    ReviewRecord,
    EvidenceBundleRecord,
    EvidenceReferenceRecord,
    WorkspaceReservationRecord,
    WriteReservationRecord,
    PauseReasonRecord,
    ResumeCheckpointRecord,
    DelegatedModeGrantRecord,
    ConversationMessageRecord,
    PresentationStateRecord,
)

PASS_B_RECORD_BY_KIND = {
    record_type.KIND: record_type for record_type in PASS_B_RECORD_TYPES
}
