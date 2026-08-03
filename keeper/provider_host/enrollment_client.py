from __future__ import annotations

import hashlib
import secrets
import uuid
from dataclasses import asdict
from datetime import UTC, datetime, timedelta
from typing import Any, Callable, Protocol

from keeper.authority_service.client import AuthorityServiceClient
from keeper.executive.founder_auth import FounderAuthenticator
from keeper.executive.founder_capability import (
    APPLICATION_IDENTITY,
    FounderAuthorizationCapability,
    FounderCapabilityClaims,
)
from keeper.executive.models import FounderApprovalChallenge
from keeper.provider_host.bootstrap import ProviderHostBootstrap
from keeper.provider_host.protocol import structured_digest


_SYSTEM_PROJECT = "keeper-system:provider-host"
_SYSTEM_CHARTER = "keeper-system:provider-host-enrollment"


class EnrollmentAuthorityClient(Protocol):
    def provider_host_enrollment_status(self) -> dict[str, Any]: ...

    def begin_provider_host_enrollment(
        self,
        *,
        founder_capability: dict[str, object],
        proposal: dict[str, object],
    ) -> dict[str, Any]: ...

    def complete_provider_host_enrollment(
        self, enrollment_id: str, proof: dict[str, object]
    ) -> dict[str, Any]: ...

    def reconcile_provider_host_enrollment(
        self, enrollment_id: str, proof: dict[str, object] | None
    ) -> dict[str, Any]: ...

    def revoke_provider_host_enrollment(
        self, enrollment_id: str, founder_capability: dict[str, object]
    ) -> dict[str, Any]: ...


class ProviderHostEnrollmentClient:
    """Founder-confirmed client flow; no protected config edits are required."""

    def __init__(
        self,
        *,
        authority: AuthorityServiceClient | EnrollmentAuthorityClient,
        authenticator: FounderAuthenticator,
        bootstrap: ProviderHostBootstrap,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self.authority = authority
        self.authenticator = authenticator
        self.bootstrap = bootstrap
        self.now = now or (lambda: datetime.now(UTC))

    def enroll(self, *, generation: int) -> dict[str, Any]:
        with self.bootstrap.checkpoint_transaction():
            self.bootstrap.prepare_new_enrollment(
                self.authority.provider_host_enrollment_status()
            )
            proposal = self.bootstrap.create_proposal(generation=generation)
            proposal_digest = structured_digest(proposal)
            try:
                capability = self._founder_capability(
                    action="ENROLL_PROVIDER_HOST",
                    action_digest=proposal_digest,
                    generation=generation,
                )
            except (OSError, PermissionError, RuntimeError, TypeError, ValueError):
                self.bootstrap.abandon_unauthorized_proposal(proposal_digest)
                raise
            capability_record = asdict(capability)
            self.bootstrap.store_founder_capability(capability_record)
            return self._begin_and_complete(proposal, capability_record)

    def resume_authorization(self) -> dict[str, Any]:
        with self.bootstrap.checkpoint_transaction():
            proposal, capability = self.bootstrap.authorization_material()
            return self._begin_and_complete(proposal, capability)

    def _begin_and_complete(
        self,
        proposal: dict[str, object],
        capability: dict[str, object],
    ) -> dict[str, Any]:
        begun = self.authority.begin_provider_host_enrollment(
            founder_capability=capability,
            proposal=proposal,
        )
        proof = self.bootstrap.prove_grant(_dict(begun.get("grant"), "grant"))
        completed = self.authority.complete_provider_host_enrollment(
            str(begun["enrollment_id"]), proof
        )
        return self.bootstrap.commit_receipt(
            _dict(completed.get("receipt"), "receipt")
        )

    def reconcile(self) -> dict[str, Any]:
        with self.bootstrap.checkpoint_transaction():
            enrollment_id, proof = self.bootstrap.reconciliation_material()
            completed = self.authority.reconcile_provider_host_enrollment(
                enrollment_id, proof
            )
            return self.bootstrap.commit_receipt(
                _dict(completed.get("receipt"), "receipt")
            )

    def reconcile_expired(self, enrollment_id: str) -> dict[str, Any]:
        with self.bootstrap.checkpoint_transaction():
            return self.authority.reconcile_provider_host_enrollment(
                enrollment_id, None
            )

    def revoke(
        self,
        *,
        enrollment_id: str,
        receipt_digest: str,
        generation: int,
    ) -> dict[str, Any]:
        with self.bootstrap.checkpoint_transaction():
            binding = {
                "action": "REVOKE_PROVIDER_HOST",
                "enrollment_id": enrollment_id,
                "receipt_digest": receipt_digest,
            }
            capability = self._founder_capability(
                action="REVOKE_PROVIDER_HOST",
                action_digest=structured_digest(binding),
                generation=generation,
            )
            result = self.authority.revoke_provider_host_enrollment(
                enrollment_id, asdict(capability)
            )
            return self.bootstrap.commit_revocation(
                _dict(result.get("revocation"), "revocation")
            )

    def _founder_capability(
        self, *, action: str, action_digest: str, generation: int
    ) -> FounderAuthorizationCapability:
        now = self.now().astimezone(UTC)
        challenge = FounderApprovalChallenge(
            challenge_id="provider-host-challenge:" + uuid.uuid4().hex,
            schema_version=2,
            project_id=_SYSTEM_PROJECT,
            charter_id=_SYSTEM_CHARTER,
            charter_revision=1,
            charter_digest=action_digest,
            approval_action="APPROVE_ACTION",
            approval_binding={
                "action": action,
                "action_digest": action_digest,
                "authorization_generation": generation,
            },
            nonce=secrets.token_hex(32),
            requested_at=now.isoformat(),
            expires_at=(now + timedelta(minutes=2)).isoformat(),
            state="PENDING",
            consumed_event_id=None,
        )
        confirmation = self.authenticator.authenticate(challenge)
        session = self.authenticator.verify(challenge, confirmation)
        issued = self.now().astimezone(UTC)
        claims = FounderCapabilityClaims(
            capability_id="provider-host-capability:" + uuid.uuid4().hex,
            project_id=_SYSTEM_PROJECT,
            charter_id=_SYSTEM_CHARTER,
            charter_revision=1,
            authorization_kind="PROVIDER_HOST_ENROLLMENT",
            protected_action=action,
            action_digest=action_digest,
            approval_digest=structured_digest(challenge.to_dict()),
            approval_event_digest=hashlib.sha256(
                confirmation.proof.encode("ascii")
            ).hexdigest(),
            founder_principal_sid=session.principal_sid,
            founder_authenticated_session_id=session.session_id,
            approval_event_id="provider-host-approval:" + challenge.challenge_id,
            approval_record_id="provider-host-record:" + challenge.challenge_id,
            challenge_id=challenge.challenge_id,
            challenge_proof_digest=session.proof_digest,
            authorization_generation=generation,
            revocation_epoch=generation - 1,
            issued_at=issued.isoformat(),
            expires_at=min(
                issued + timedelta(minutes=2),
                datetime.fromisoformat(session.expires_at),
            ).isoformat(),
            usage="ONE_TIME_GENERATION",
            machine_identity=session.machine_identity,
            application_identity=APPLICATION_IDENTITY,
        )
        return self.authenticator.issue_authorization_capability(
            claims, confirmation
        )


def _dict(value: object, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise PermissionError(f"Provider Host {label} is invalid")
    return dict(value)
