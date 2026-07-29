from __future__ import annotations

import hashlib
import json
import math
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Callable, Protocol

from keeper.pass_b.models import UsagePoolRecord


@dataclass(frozen=True, slots=True)
class UsageResetObservation:
    observation_id: str
    pool_id: str
    provider_id: str
    account_id: str
    reset_at: str
    observed_at: str
    source: str
    remaining: float | None
    proof: str

    def digest(self) -> str:
        value = asdict(self)
        value.pop("proof")
        return hashlib.sha256(
            json.dumps(
                value, sort_keys=True, separators=(",", ":")
            ).encode("utf-8")
        ).hexdigest()


class UsageResetVerifier(Protocol):
    def verify(
        self,
        pool: UsagePoolRecord,
        observation: UsageResetObservation,
        *,
        now: datetime,
    ) -> None: ...


class UnavailableUsageResetVerifier:
    def verify(
        self,
        pool: UsagePoolRecord,
        observation: UsageResetObservation,
        *,
        now: datetime,
    ) -> None:
        del pool, observation, now
        raise PermissionError(
            "authenticated provider usage reset observer is unavailable"
        )


class ProductionUsageResetVerifier:
    """Validates provider-authenticated observations via a sealed integration."""

    def __init__(
        self,
        verify_proof: Callable[[UsageResetObservation], bool],
    ) -> None:
        self._verify_proof = verify_proof

    def verify(
        self,
        pool: UsagePoolRecord,
        observation: UsageResetObservation,
        *,
        now: datetime,
    ) -> None:
        _validate_observation(pool, observation, now)
        if not self._verify_proof(observation):
            raise PermissionError(
                "provider usage reset proof is unauthenticated"
            )


class TestUsageResetVerifier:
    """Explicit deterministic verifier for tests and the isolated pilot."""

    __test__ = False

    def __init__(self) -> None:
        self._issued: dict[str, str] = {}
        self._consumed: set[str] = set()

    def issue(
        self,
        pool: UsagePoolRecord,
        *,
        reset_at: str,
        observed_at: str,
        remaining: float | None = None,
    ) -> UsageResetObservation:
        observation = UsageResetObservation(
            observation_id=f"test-reset:{uuid.uuid4().hex}",
            pool_id=pool.pool_id,
            provider_id=pool.provider_id,
            account_id=pool.account_id,
            reset_at=reset_at,
            observed_at=observed_at,
            source="TEST_AUTHENTICATED_USAGE_OBSERVER",
            remaining=remaining,
            proof="pending",
        )
        digest = observation.digest()
        signed = UsageResetObservation(
            **{
                **asdict(observation),
                "proof": f"test-proof:{digest}",
            }
        )
        self._issued[signed.observation_id] = signed.digest()
        return signed

    def verify(
        self,
        pool: UsagePoolRecord,
        observation: UsageResetObservation,
        *,
        now: datetime,
    ) -> None:
        if observation.observation_id in self._consumed:
            raise PermissionError(
                "test usage reset observation was replayed"
            )
        _validate_observation(pool, observation, now)
        expected = self._issued.get(observation.observation_id)
        if (
            expected != observation.digest()
            or observation.proof
            != f"test-proof:{observation.digest()}"
        ):
            raise PermissionError(
                "test usage reset observation is invalid or replayed"
            )
        self._consumed.add(observation.observation_id)


def _validate_observation(
    pool: UsagePoolRecord,
    observation: UsageResetObservation,
    now: datetime,
) -> None:
    try:
        reset = datetime.fromisoformat(observation.reset_at)
        observed = datetime.fromisoformat(observation.observed_at)
    except ValueError as error:
        raise PermissionError(
            "usage reset observation timestamps are invalid"
        ) from error
    if (
        reset.tzinfo is None
        or observed.tzinfo is None
        or now.tzinfo is None
        or observation.pool_id != pool.pool_id
        or observation.provider_id != pool.provider_id
        or observation.account_id != pool.account_id
        or not observation.observation_id
        or not observation.source
        or reset > observed
        or observed > now
        or pool.reset_at is None
        or reset < datetime.fromisoformat(pool.reset_at)
        or (
            observation.remaining is not None
            and (
                not math.isfinite(observation.remaining)
                or observation.remaining < 0
            )
        )
    ):
        raise PermissionError(
            "usage reset observation is stale or mismatched"
        )
