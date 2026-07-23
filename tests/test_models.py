"""Domain model validation tests."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from pydantic import ValidationError

from shared.models.candle import Candle, Timeframe
from shared.models.quote import Quote
from shared.models.signal import Signal, SignalDirection, SignalGrade
from shared.models.strategy_profile import StrategyProfile, StrategyStatus
from shared.models.trade_proposal import (
    TradeProposal,
    TradeProposalSource,
    TradeProposalStatus,
    TradeValidationOutcome,
)

NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)
NON_UTC_AWARE = datetime(2026, 1, 1, 12, 0, tzinfo=timezone(timedelta(hours=-5)))


def test_candle_accepts_consistent_ohlc() -> None:
    candle = Candle(
        symbol="aapl",
        timeframe=Timeframe.D1,
        timestamp=NOW,
        open=100.0,
        high=105.0,
        low=99.0,
        close=104.0,
        volume=1000,
    )
    assert candle.symbol == "AAPL"  # normalized uppercase
    assert candle.timestamp.tzinfo is not None


def test_candle_rejects_high_below_low() -> None:
    with pytest.raises(ValidationError):
        Candle(
            symbol="AAPL",
            timeframe=Timeframe.D1,
            timestamp=NOW,
            open=100.0,
            high=98.0,
            low=99.0,
            close=100.0,
            volume=1000,
        )


def test_candle_is_frozen() -> None:
    candle = Candle(
        symbol="AAPL",
        timeframe=Timeframe.D1,
        timestamp=NOW,
        open=100.0,
        high=105.0,
        low=99.0,
        close=104.0,
        volume=1000,
    )
    with pytest.raises(ValidationError):
        candle.close = 999.0  # type: ignore[misc]


def test_quote_rejects_ask_below_bid() -> None:
    with pytest.raises(ValidationError):
        Quote(symbol="AAPL", timestamp=NOW, bid=101.0, ask=100.0, last=100.5)


def test_quote_spread() -> None:
    quote = Quote(symbol="AAPL", timestamp=NOW, bid=100.0, ask=100.5, last=100.2)
    assert quote.spread == Decimal("0.5")


def test_signal_grade_and_confidence_bounds() -> None:
    signal = Signal(
        symbol="AAPL",
        direction=SignalDirection.LONG,
        strategy_id="momentum-v1",
        strategy_version="1.0.0",
        entry=100.0,
        stop=95.0,
        confidence=0.8,
        grade=SignalGrade.A,
        timestamp=NOW,
    )
    assert signal.grade == SignalGrade.A

    with pytest.raises(ValidationError):
        Signal(
            symbol="AAPL",
            direction=SignalDirection.LONG,
            strategy_id="momentum-v1",
            strategy_version="1.0.0",
            entry=100.0,
            stop=95.0,
            confidence=1.5,  # out of bounds
            grade=SignalGrade.A,
            timestamp=NOW,
        )


def test_strategy_profile_defaults_to_experimental() -> None:
    profile = StrategyProfile(strategy_id="momentum-v1", name="Momentum", version="1.0.0")
    assert profile.status == StrategyStatus.EXPERIMENTAL


def test_trade_proposal_has_no_execution_capability() -> None:
    """Architectural guarantee: a TradeProposal cannot reach the broker directly
    (ARCHITECTURE.md Section 14 / TRADING_RULES.md)."""
    proposal = TradeProposal(
        proposal_id="tp-1",
        strategy_id="momentum-v1",
        strategy_version="1.0.0",
        symbol="AAPL",
        direction=SignalDirection.LONG,
        proposed_quantity=10,
        proposed_entry=100.0,
        proposed_stop=95.0,
        source=TradeProposalSource.AI,
        created_at=NOW,
    )
    assert not hasattr(proposal, "execute")
    assert not hasattr(proposal, "broker")
    assert not hasattr(proposal, "submit_order")


# --- Timestamp integrity (naive rejected, aware normalized to UTC) ---


def test_candle_rejects_naive_timestamp() -> None:
    with pytest.raises(ValidationError):
        Candle(
            symbol="AAPL",
            timeframe=Timeframe.D1,
            timestamp=datetime(2026, 1, 1),  # naive
            open=100.0,
            high=105.0,
            low=99.0,
            close=104.0,
            volume=1000,
        )


def test_candle_normalizes_aware_non_utc_timestamp() -> None:
    candle = Candle(
        symbol="AAPL",
        timeframe=Timeframe.D1,
        timestamp=NON_UTC_AWARE,
        open=100.0,
        high=105.0,
        low=99.0,
        close=104.0,
        volume=1000,
    )
    assert candle.timestamp.tzinfo == timezone.utc
    assert candle.timestamp == NON_UTC_AWARE.astimezone(timezone.utc)


def test_quote_rejects_naive_timestamp() -> None:
    with pytest.raises(ValidationError):
        Quote(symbol="AAPL", timestamp=datetime(2026, 1, 1), bid=100.0, ask=100.5, last=100.2)


def test_quote_normalizes_aware_non_utc_timestamp() -> None:
    quote = Quote(symbol="AAPL", timestamp=NON_UTC_AWARE, bid=100.0, ask=100.5, last=100.2)
    assert quote.timestamp.tzinfo == timezone.utc
    assert quote.timestamp == NON_UTC_AWARE.astimezone(timezone.utc)


def test_signal_rejects_naive_timestamp() -> None:
    with pytest.raises(ValidationError):
        Signal(
            symbol="AAPL",
            direction=SignalDirection.LONG,
            strategy_id="momentum-v1",
            strategy_version="1.0.0",
            entry=100.0,
            stop=95.0,
            confidence=0.8,
            grade=SignalGrade.A,
            timestamp=datetime(2026, 1, 1),
        )


def test_signal_rejects_naive_expiration() -> None:
    with pytest.raises(ValidationError):
        Signal(
            symbol="AAPL",
            direction=SignalDirection.LONG,
            strategy_id="momentum-v1",
            strategy_version="1.0.0",
            entry=100.0,
            stop=95.0,
            confidence=0.8,
            grade=SignalGrade.A,
            timestamp=NOW,
            expiration=datetime(2026, 1, 2),
        )


def test_signal_normalizes_aware_non_utc_timestamp() -> None:
    signal = Signal(
        symbol="AAPL",
        direction=SignalDirection.LONG,
        strategy_id="momentum-v1",
        strategy_version="1.0.0",
        entry=100.0,
        stop=95.0,
        confidence=0.8,
        grade=SignalGrade.A,
        timestamp=NON_UTC_AWARE,
        expiration=NON_UTC_AWARE,
    )
    assert signal.timestamp.tzinfo == timezone.utc
    assert signal.timestamp == NON_UTC_AWARE.astimezone(timezone.utc)
    assert signal.expiration is not None
    assert signal.expiration.tzinfo == timezone.utc


def test_trade_proposal_rejects_naive_created_at() -> None:
    with pytest.raises(ValidationError):
        TradeProposal(
            proposal_id="tp-naive",
            strategy_id="momentum-v1",
            strategy_version="1.0.0",
            symbol="AAPL",
            direction=SignalDirection.LONG,
            proposed_quantity=10,
            proposed_entry=100.0,
            proposed_stop=95.0,
            source=TradeProposalSource.AI,
            created_at=datetime(2026, 1, 1),
        )


def test_trade_proposal_normalizes_aware_non_utc_created_at() -> None:
    proposal = TradeProposal(
        proposal_id="tp-aware",
        strategy_id="momentum-v1",
        strategy_version="1.0.0",
        symbol="AAPL",
        direction=SignalDirection.LONG,
        proposed_quantity=10,
        proposed_entry=100.0,
        proposed_stop=95.0,
        source=TradeProposalSource.AI,
        created_at=NON_UTC_AWARE,
    )
    assert proposal.created_at.tzinfo == timezone.utc
    assert proposal.created_at == NON_UTC_AWARE.astimezone(timezone.utc)


# --- Financial precision: Decimal fields must be finite and constrained ---


@pytest.mark.parametrize("bad_value", [Decimal("nan"), Decimal("inf"), Decimal("-inf")])
def test_candle_rejects_non_finite_price(bad_value: Decimal) -> None:
    with pytest.raises(ValidationError):
        Candle(
            symbol="AAPL",
            timeframe=Timeframe.D1,
            timestamp=NOW,
            open=bad_value,
            high=105.0,
            low=99.0,
            close=104.0,
            volume=1000,
        )


def test_candle_rejects_zero_or_negative_price() -> None:
    with pytest.raises(ValidationError):
        Candle(
            symbol="AAPL",
            timeframe=Timeframe.D1,
            timestamp=NOW,
            open=0,
            high=105.0,
            low=99.0,
            close=104.0,
            volume=1000,
        )


def test_candle_decimal_round_trips_through_json() -> None:
    candle = Candle(
        symbol="AAPL",
        timeframe=Timeframe.D1,
        timestamp=NOW,
        open=100.10,
        high=105.25,
        low=99.05,
        close=104.75,
        volume=1000,
    )
    restored = Candle.model_validate_json(candle.model_dump_json())
    assert restored == candle
    assert isinstance(restored.close, Decimal)
    assert restored.close == Decimal("104.75")


@pytest.mark.parametrize("bad_value", [Decimal("nan"), Decimal("inf"), Decimal("-inf")])
def test_quote_rejects_non_finite_price(bad_value: Decimal) -> None:
    with pytest.raises(ValidationError):
        Quote(symbol="AAPL", timestamp=NOW, bid=bad_value, ask=100.5, last=100.2)


@pytest.mark.parametrize("bad_value", [Decimal("nan"), Decimal("inf"), Decimal("-inf")])
def test_signal_rejects_non_finite_entry(bad_value: Decimal) -> None:
    with pytest.raises(ValidationError):
        Signal(
            symbol="AAPL",
            direction=SignalDirection.LONG,
            strategy_id="momentum-v1",
            strategy_version="1.0.0",
            entry=bad_value,
            stop=95.0,
            confidence=0.8,
            grade=SignalGrade.A,
            timestamp=NOW,
        )


@pytest.mark.parametrize("bad_value", [Decimal("nan"), Decimal("inf"), Decimal("-inf")])
def test_trade_proposal_rejects_non_finite_quantity(bad_value: Decimal) -> None:
    with pytest.raises(ValidationError):
        TradeProposal(
            proposal_id="tp-bad",
            strategy_id="momentum-v1",
            strategy_version="1.0.0",
            symbol="AAPL",
            direction=SignalDirection.LONG,
            proposed_quantity=bad_value,
            proposed_entry=100.0,
            proposed_stop=95.0,
            source=TradeProposalSource.AI,
            created_at=NOW,
        )


def test_trade_proposal_rejects_zero_or_negative_quantity() -> None:
    with pytest.raises(ValidationError):
        TradeProposal(
            proposal_id="tp-zero",
            strategy_id="momentum-v1",
            strategy_version="1.0.0",
            symbol="AAPL",
            direction=SignalDirection.LONG,
            proposed_quantity=0,
            proposed_entry=100.0,
            proposed_stop=95.0,
            source=TradeProposalSource.AI,
            created_at=NOW,
        )


def test_trade_proposal_decimal_round_trips_through_json() -> None:
    proposal = TradeProposal(
        proposal_id="tp-json",
        strategy_id="momentum-v1",
        strategy_version="1.0.0",
        symbol="AAPL",
        direction=SignalDirection.LONG,
        proposed_quantity=10.5,
        proposed_entry=100.10,
        proposed_stop=95.05,
        proposed_targets=[105.0, 110.0],
        source=TradeProposalSource.AI,
        created_at=NOW,
    )
    restored = TradeProposal.model_validate_json(proposal.model_dump_json())
    assert restored == proposal
    assert isinstance(restored.proposed_entry, Decimal)
    assert restored.proposed_entry == Decimal("100.10")


# --- TradeProposal validation-state safety: creation != validation ---


def _make_proposal(**overrides: object) -> TradeProposal:
    fields: dict[str, object] = dict(
        proposal_id="tp-1",
        strategy_id="momentum-v1",
        strategy_version="1.0.0",
        symbol="AAPL",
        direction=SignalDirection.LONG,
        proposed_quantity=10,
        proposed_entry=100.0,
        proposed_stop=95.0,
        source=TradeProposalSource.AI,
        created_at=NOW,
    )
    fields.update(overrides)
    return TradeProposal(**fields)  # type: ignore[arg-type]


def test_trade_proposal_has_no_status_field() -> None:
    """TradeProposal cannot represent a validation result at all (see module docstring)."""
    proposal = _make_proposal()
    assert "status" not in TradeProposal.model_fields
    assert "status" not in proposal.model_dump()


def test_trade_proposal_rejects_direct_construction_with_status_kwarg() -> None:
    """extra='forbid' means an unrecognized status= kwarg raises loudly, never ignored."""
    with pytest.raises(ValidationError):
        _make_proposal(status=TradeProposalStatus.VALIDATED)
    with pytest.raises(ValidationError):
        _make_proposal(status=TradeProposalStatus.REJECTED)


def test_trade_proposal_is_frozen() -> None:
    proposal = _make_proposal()
    with pytest.raises(ValidationError):
        proposal.proposal_id = "tp-mutated"  # type: ignore[misc]


def test_trade_proposal_model_copy_cannot_fabricate_a_validated_result() -> None:
    """model_copy(update=...) bypasses field validation, but since TradeProposal has
    no status field, the update can only ever inject a harmless phantom attribute
    that no code path reads and that never appears in serialized output."""
    proposal = _make_proposal()
    forged = proposal.model_copy(update={"status": TradeProposalStatus.VALIDATED})

    assert isinstance(forged, TradeProposal)
    assert "status" not in forged.model_dump()
    assert "status" not in forged.model_dump_json()
    # TradeValidationOutcome is the only type that can represent a decision;
    # nothing about `forged` lets it be mistaken for, or used as, one.
    assert not isinstance(forged, TradeValidationOutcome)


def test_trade_validation_outcome_rejects_normal_public_construction() -> None:
    """No authority token -> ValidationError, regardless of the status requested."""
    proposal = _make_proposal()
    with pytest.raises(ValidationError):
        TradeValidationOutcome(proposal=proposal, status=TradeProposalStatus.VALIDATED)  # type: ignore[call-arg]
    with pytest.raises(ValidationError):
        TradeValidationOutcome(proposal=proposal, status=TradeProposalStatus.REJECTED)  # type: ignore[call-arg]


def test_trade_validation_outcome_record_has_no_public_unconditional_factory() -> None:
    """.record() called the way ordinary/proposal-producing code would call it —
    with no authority token — must fail; there is no bare approved=True factory."""
    proposal = _make_proposal()
    with pytest.raises(TypeError):
        TradeValidationOutcome.record(proposal, approved=True)  # type: ignore[call-arg]
    with pytest.raises(TypeError):
        TradeValidationOutcome.record(proposal, approved=False)  # type: ignore[call-arg]


def test_only_the_pipeline_authority_can_produce_a_validation_outcome() -> None:
    """The one intended path: import the private capability token (as only a real
    validation pipeline module would) and pass it explicitly to .record()."""
    from shared.models.trade_proposal import _PIPELINE_AUTHORITY

    proposal = _make_proposal()

    validated = TradeValidationOutcome.record(
        proposal, approved=True, authority=_PIPELINE_AUTHORITY
    )
    assert validated.status == TradeProposalStatus.VALIDATED
    assert validated.proposal == proposal

    rejected = TradeValidationOutcome.record(
        proposal, approved=False, authority=_PIPELINE_AUTHORITY
    )
    assert rejected.status == TradeProposalStatus.REJECTED


def test_trade_validation_outcome_rejects_pending_as_a_decision() -> None:
    from shared.models.trade_proposal import _PIPELINE_AUTHORITY

    proposal = _make_proposal()
    with pytest.raises(ValidationError):
        TradeValidationOutcome(
            proposal=proposal,
            status=TradeProposalStatus.PENDING_VALIDATION,
            authority=_PIPELINE_AUTHORITY,
        )


def test_trade_validation_outcome_is_frozen() -> None:
    from shared.models.trade_proposal import _PIPELINE_AUTHORITY

    proposal = _make_proposal()
    outcome = TradeValidationOutcome.record(proposal, approved=True, authority=_PIPELINE_AUTHORITY)
    with pytest.raises(ValidationError):
        outcome.status = TradeProposalStatus.REJECTED  # type: ignore[misc]


def test_trade_validation_outcome_model_copy_is_refused() -> None:
    """Even a legitimately-obtained outcome cannot be reshaped via model_copy —
    e.g. flipping a REJECTED verdict into VALIDATED after the fact."""
    from shared.models.trade_proposal import _PIPELINE_AUTHORITY

    proposal = _make_proposal()
    rejected = TradeValidationOutcome.record(
        proposal, approved=False, authority=_PIPELINE_AUTHORITY
    )
    with pytest.raises(TypeError):
        rejected.model_copy(update={"status": TradeProposalStatus.VALIDATED})


def test_trade_validation_outcome_model_construct_cannot_manufacture_validated() -> None:
    """model_construct bypasses all field validation, including the authority
    check — it must be refused outright, not merely undocumented."""
    proposal = _make_proposal()
    with pytest.raises(TypeError):
        TradeValidationOutcome.model_construct(
            proposal=proposal, status=TradeProposalStatus.VALIDATED
        )


def test_trade_validation_outcome_model_construct_cannot_manufacture_rejected() -> None:
    proposal = _make_proposal()
    with pytest.raises(TypeError):
        TradeValidationOutcome.model_construct(
            proposal=proposal, status=TradeProposalStatus.REJECTED
        )


def test_trade_validation_outcome_is_distinct_from_eligibility_and_execution() -> None:
    """A validation outcome is a verdict, not a trade-eligibility or
    execution-permission decision — it has no such fields or capability."""
    from shared.models.trade_proposal import _PIPELINE_AUTHORITY

    proposal = _make_proposal()
    outcome = TradeValidationOutcome.record(proposal, approved=True, authority=_PIPELINE_AUTHORITY)
    assert not hasattr(outcome, "eligible")
    assert not hasattr(outcome, "execute")
    assert not hasattr(outcome, "broker")
    assert not hasattr(outcome, "submit_order")


# --- Target price collections: every element finite and positive ---


@pytest.mark.parametrize("bad_target", [Decimal("0"), Decimal("-1"), Decimal("nan"), Decimal("inf"), Decimal("-inf")])
def test_signal_rejects_invalid_target_elements(bad_target: Decimal) -> None:
    with pytest.raises(ValidationError):
        Signal(
            symbol="AAPL",
            direction=SignalDirection.LONG,
            strategy_id="momentum-v1",
            strategy_version="1.0.0",
            entry=100.0,
            stop=95.0,
            targets=[Decimal("105"), bad_target],
            confidence=0.8,
            grade=SignalGrade.A,
            timestamp=NOW,
        )


def test_signal_accepts_valid_positive_targets() -> None:
    signal = Signal(
        symbol="AAPL",
        direction=SignalDirection.LONG,
        strategy_id="momentum-v1",
        strategy_version="1.0.0",
        entry=100.0,
        stop=95.0,
        targets=[105.0, 110.5],
        confidence=0.8,
        grade=SignalGrade.A,
        timestamp=NOW,
    )
    assert signal.targets == [Decimal("105.0"), Decimal("110.5")]


@pytest.mark.parametrize("bad_target", [Decimal("0"), Decimal("-1"), Decimal("nan"), Decimal("inf"), Decimal("-inf")])
def test_trade_proposal_rejects_invalid_target_elements(bad_target: Decimal) -> None:
    with pytest.raises(ValidationError):
        _make_proposal(proposed_targets=[Decimal("105"), bad_target])


def test_trade_proposal_accepts_valid_positive_targets() -> None:
    proposal = _make_proposal(proposed_targets=[105.0, 110.5])
    assert proposal.proposed_targets == [Decimal("105.0"), Decimal("110.5")]
