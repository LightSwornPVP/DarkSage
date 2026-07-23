"""TradeProposal domain model — canonical TradeValidationPipeline stage 2.

See ARCHITECTURE.md Section 14: "The candidate trade, not yet validated.
Carries the signal, strategy, and proposed size/direction."

This model deliberately has no ``execute()`` method, no broker reference,
and no way to reach the Execution Engine or Broker Adapter directly. A
TradeProposal only becomes eligible for execution after passing every
downstream pipeline stage (Signal Validator -> Strategy Validation ->
Risk Engine -> Permissions Engine -> Portfolio/Exposure Checks -> Buying
Power Checks -> Market Condition Checks -> Order Validation), which are
out of scope for this foundational slice. AI (or the Strategy Engine) may
create this object; it may never bypass the pipeline (TRADING_RULES.md).

``TradeProposal`` carries no status/validation-result field at all — it
structurally cannot represent "validated" or "rejected". That result lives
exclusively on :class:`TradeValidationOutcome`, and constructing one — by
any path, including :meth:`TradeValidationOutcome.record` — requires
possessing a `_ValidationPipelineAuthority` capability token that is not
exported from `shared.models` and not referenced anywhere in proposal- or
AI-producing code. See :class:`TradeValidationOutcome` for the full
rationale. This is a deliberate design choice, not a naming convention:
pydantic's ``model_copy(update=...)`` bypasses field validation, so a
status *field* on TradeProposal could always be forged at runtime
regardless of what validators say. Removing the field entirely closes
that hole — there is nothing on TradeProposal for such a call to
meaningfully set. See tests in tests/test_models.py proving this.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Annotated, Any

from pydantic import BaseModel, Field, field_validator

from shared.models.signal import SignalDirection

PositivePrice = Annotated[Decimal, Field(gt=0)]


class TradeProposalSource(str, Enum):
    """Who produced this proposal. Advisory only in both cases."""

    AI = "ai"
    STRATEGY_ENGINE = "strategy_engine"
    MANUAL = "manual"


class TradeProposalStatus(str, Enum):
    PENDING_VALIDATION = "pending_validation"
    REJECTED = "rejected"
    VALIDATED = "validated"


class TradeProposal(BaseModel):
    """The candidate trade, not yet validated. See module docstring."""

    model_config = {"frozen": True, "extra": "forbid"}

    proposal_id: str = Field(min_length=1)
    signal_id: str | None = None
    strategy_id: str = Field(min_length=1)
    strategy_version: str = Field(min_length=1)
    symbol: str = Field(min_length=1, max_length=32)
    direction: SignalDirection
    proposed_quantity: Decimal = Field(gt=0)
    proposed_entry: Decimal = Field(gt=0)
    proposed_stop: Decimal = Field(gt=0)
    proposed_targets: list[PositivePrice] = Field(default_factory=list)
    source: TradeProposalSource
    created_at: datetime

    @field_validator("created_at")
    @classmethod
    def _timezone_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError(
                "created_at must be timezone-aware; naive datetimes are rejected "
                "rather than silently assumed to be UTC"
            )
        return value.astimezone(timezone.utc)

    @field_validator("symbol")
    @classmethod
    def _symbol_uppercase(cls, value: str) -> str:
        return value.strip().upper()


class _ValidationPipelineAuthority:
    """Capability token asserting "I am the deterministic validation pipeline."

    Python has no true private/friend-class access control, so this is the
    strongest structural gate available: constructing a
    :class:`TradeValidationOutcome` — through :meth:`TradeValidationOutcome.record`
    or directly — requires an instance of this class. Neither this class nor
    :data:`_PIPELINE_AUTHORITY` is exported from ``shared.models`` (see
    ``shared/models/__init__.py``), and no proposal-producing code (AI,
    Strategy Engine, or otherwise) imports or references it. Obtaining one
    means reaching past the public package boundary into this module's
    underscore-prefixed internals directly — a deliberate circumvention of
    implementation details, not normal use of the public API. A future
    TradeValidationPipeline module is expected to import
    ``_PIPELINE_AUTHORITY`` from here the same way tests do.
    """

    __slots__ = ()


_PIPELINE_AUTHORITY = _ValidationPipelineAuthority()


class TradeValidationOutcome(BaseModel):
    """The deterministic validation pipeline's verdict on a TradeProposal.

    This is the only object type that can represent a proposal having
    passed or failed validation, and it cannot be produced without an
    ``authority`` token (see :class:`_ValidationPipelineAuthority`) —
    neither via :meth:`record` nor via direct construction, and not via
    ``model_copy`` (overridden below to always refuse). There is
    deliberately no public, unconditional "make this VALIDATED" factory.
    """

    model_config = {"frozen": True, "extra": "forbid", "arbitrary_types_allowed": True}

    proposal: TradeProposal
    status: TradeProposalStatus
    authority: _ValidationPipelineAuthority = Field(repr=False, exclude=True)

    @field_validator("status")
    @classmethod
    def _status_must_be_a_decision(cls, value: TradeProposalStatus) -> TradeProposalStatus:
        if value is TradeProposalStatus.PENDING_VALIDATION:
            raise ValueError(
                "a TradeValidationOutcome must be VALIDATED or REJECTED, never "
                "PENDING_VALIDATION"
            )
        return value

    @classmethod
    def record(
        cls,
        proposal: TradeProposal,
        *,
        approved: bool,
        authority: _ValidationPipelineAuthority,
    ) -> "TradeValidationOutcome":
        """The sole controlled path that can produce a validation result.

        ``authority`` must be a genuine capability token (see
        :class:`_ValidationPipelineAuthority`); ordinary proposal-producing
        code has no way to obtain one, so this is not callable as a normal
        public factory.
        """
        return cls(
            proposal=proposal,
            status=TradeProposalStatus.VALIDATED if approved else TradeProposalStatus.REJECTED,
            authority=authority,
        )

    def model_copy(
        self, *, update: Mapping[str, Any] | None = None, deep: bool = False
    ) -> "TradeValidationOutcome":
        """Refused: a validation outcome is a one-time verdict, not editable.

        Without this override, ``model_copy`` (which bypasses field
        validation by design) could be used to reshape an already-obtained
        outcome — e.g. flipping REJECTED to VALIDATED — despite already
        holding a legitimate ``authority`` token from its original
        construction. Refusing outright removes that path entirely.
        """
        raise TypeError(
            "TradeValidationOutcome cannot be copied or mutated via model_copy; "
            "it is a one-time verdict from the deterministic validation "
            "pipeline. Obtain a fresh outcome from the pipeline instead."
        )

    @classmethod
    def model_construct(
        cls, _fields_set: set[str] | None = None, **values: Any
    ) -> "TradeValidationOutcome":
        """Refused: ``model_construct`` bypasses *all* field validation.

        Unlike the normal constructor, pydantic's inherited
        ``model_construct`` skips validation entirely — including the
        required ``authority`` field check — so without this override,
        ordinary code could do
        ``TradeValidationOutcome.model_construct(proposal=..., status=VALIDATED)``
        and manufacture a verdict with no authority token at all. That is a
        normal public Pydantic API path, not deliberate underscore-internal
        circumvention, so it must be refused outright rather than merely
        discouraged.
        """
        raise TypeError(
            "TradeValidationOutcome.model_construct() is refused; it would "
            "bypass the authority-token requirement enforced by normal "
            "construction. Use TradeValidationOutcome.record(proposal, "
            "approved=..., authority=...) from the deterministic validation "
            "pipeline instead."
        )
