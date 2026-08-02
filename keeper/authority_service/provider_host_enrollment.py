from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, datetime
from typing import Any, Callable, Mapping, Protocol, cast

from keeper.authority_service.store import AuthorityStore
from keeper.executive.founder_capability import (
    FounderAuthorizationCapability,
    ProductionFounderCapabilityVerifier,
    TestFounderCapabilityVerifier,
    capability_digest,
    capability_signature_digest,
)
from keeper.provider_host.enrollment import (
    ENROLLMENT_GRANT_PURPOSE,
    ENROLLMENT_RECEIPT_PURPOSE,
    ENROLLMENT_REVOCATION_PURPOSE,
    MAXIMUM_ENROLLMENT_TTL,
    redacted_enrollment_status,
    validate_enrollment_proof,
    validate_enrollment_proposal,
)
from keeper.provider_host.protocol import (
    HOST_PROTOCOL,
    EnvelopeSigner,
    EnvelopeVerifier,
    require_production_identity,
    structured_digest,
)
from keeper.provider_host.signing import RsaPublicIdentity


ENROLLMENT_SYSTEM_PROJECT = "keeper-system:provider-host"
ENROLLMENT_SYSTEM_CHARTER = "keeper-system:provider-host-enrollment"


class ProposalObserver(Protocol):
    def validate_provider_host_enrollment_proposal(
        self, proposal: Mapping[str, Any], client_sid: str
    ) -> dict[str, Any]: ...

    def provider_host_runtime_configuration(
        self,
        proposal: Mapping[str, Any],
        *,
        enrollment_id: str,
        authority_id: str,
        authority_public_identity: Mapping[str, object],
    ) -> dict[str, Any]: ...


class ProviderHostEnrollmentCoordinator:
    """Authority-owned one-use Host enrollment and reconciliation lifecycle."""

    def __init__(
        self,
        *,
        store: AuthorityStore,
        service_key_id: str,
        authority_protocol_version: int,
        authority_schema_version: int,
        founder_verifier: (
            ProductionFounderCapabilityVerifier | TestFounderCapabilityVerifier
        ),
        authority_signer: EnvelopeSigner,
        authority_public_identity: Mapping[str, object],
        proposal_observer: ProposalObserver,
        activate: Callable[[Mapping[str, Any]], None],
        deactivate: Callable[[Mapping[str, Any]], None],
        host_verifier_factory: (
            Callable[[Mapping[str, object]], EnvelopeVerifier] | None
        ) = None,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        if type(founder_verifier) is ProductionFounderCapabilityVerifier:
            require_production_identity(authority_signer)
        elif type(founder_verifier) is not TestFounderCapabilityVerifier:
            raise TypeError("Provider Host Founder verifier is not trusted")
        if authority_signer.identity != authority_public_identity.get("identity"):
            raise PermissionError("Provider Host Authority enrollment identity differs")
        self.store = store
        self.service_key_id = service_key_id
        self.authority_protocol_version = authority_protocol_version
        self.authority_schema_version = authority_schema_version
        self.founder_verifier = founder_verifier
        self.authority_signer = authority_signer
        self.authority_public_identity = dict(authority_public_identity)
        self.proposal_observer = proposal_observer
        self.activate = activate
        self.deactivate = deactivate
        self.host_verifier_factory = host_verifier_factory or (
            lambda value: RsaPublicIdentity.from_configuration(value).verifier()
        )
        self.now = now or (lambda: datetime.now(UTC))

    def status(self) -> dict[str, Any]:
        return redacted_enrollment_status(
            self.store.current_provider_host_enrollment()
        )

    def begin(
        self, payload: Mapping[str, Any], client_sid: str
    ) -> dict[str, Any]:
        if set(payload) != {"founder_capability", "proposal"}:
            raise PermissionError("Provider Host enrollment request fields are invalid")
        proposal_record = _object(payload["proposal"], "enrollment proposal")
        unsigned = _object(
            proposal_record.get("payload"), "enrollment proposal payload"
        )
        public = _object(
            unsigned.get("host_public_identity"), "Host public identity"
        )
        host_verifier = self.host_verifier_factory(public)
        if (
            host_verifier.identity != public.get("identity")
            or host_verifier.key_id != public.get("key_id")
        ):
            raise PermissionError("Provider Host proposal signing identity differs")
        proposal = validate_enrollment_proposal(
            proposal_record,
            expected_authority_protocol=self.authority_protocol_version,
            expected_authority_schema=self.authority_schema_version,
            expected_service_key_id=self.service_key_id,
            verifier=host_verifier,
            now=self.now(),
        )
        proposal = self.proposal_observer.validate_provider_host_enrollment_proposal(
            proposal, client_sid
        )
        proposal_digest = structured_digest(proposal_record)
        capability = self._founder_capability(
            payload["founder_capability"],
            client_sid,
            action="ENROLL_PROVIDER_HOST",
            action_digest=proposal_digest,
            generation=int(proposal["enrollment_generation"]),
        )
        enrollment_id = "provider-host-enrollment:" + hashlib.sha256(
            (
                str(proposal["host_id"])
                + ":"
                + proposal_digest
            ).encode("utf-8")
        ).hexdigest()
        capability_value_digest = capability_digest(capability)
        existing = self.store.get("provider_host_enrollments", enrollment_id)
        if existing is not None:
            state = existing.get("service_state")
            if (
                state == "PENDING"
                and existing.get("proposal_digest") == proposal_digest
                and existing.get("founder_capability_digest")
                == capability_value_digest
                and str(existing.get("founder_principal_sid", "")).casefold()
                == client_sid.casefold()
            ):
                return {
                    "enrollment_id": enrollment_id,
                    "state": "PENDING",
                    "grant": existing["grant"],
                    "grant_digest": existing["grant_digest"],
                    "expires_at": _object(
                        _object(existing["grant"], "stored grant")["payload"],
                        "stored grant payload",
                    )["expires_at"],
                }
            raise PermissionError("A Provider Host enrollment is already unresolved")
        now = self.now().astimezone(UTC)
        grant_payload = {
            "authority_id": self.authority_signer.identity,
            "authority_protocol_version": self.authority_protocol_version,
            "authority_public_identity": dict(self.authority_public_identity),
            "authority_schema_version": self.authority_schema_version,
            "challenge": secrets.token_hex(32),
            "enrollment_generation": int(proposal["enrollment_generation"]),
            "enrollment_id": enrollment_id,
            "expires_at": (now + MAXIMUM_ENROLLMENT_TTL).isoformat(),
            "host_id": str(proposal["host_id"]),
            "host_protocol": HOST_PROTOCOL,
            "issued_at": now.isoformat(),
            "proposal_digest": proposal_digest,
            "sequence": int(proposal["enrollment_generation"]),
            "service_key_id": self.service_key_id,
            "state": "PENDING",
        }
        grant = self.authority_signer.sign(
            ENROLLMENT_GRANT_PURPOSE, grant_payload
        )
        record = {
            "enrollment_id": enrollment_id,
            "enrollment_generation": int(proposal["enrollment_generation"]),
            "proposal": proposal_record,
            "proposal_digest": proposal_digest,
            "grant": grant,
            "grant_digest": structured_digest(grant),
            "founder_capability_digest": capability_value_digest,
            "founder_capability_signature_digest": capability_signature_digest(
                capability
            ),
            "founder_principal_sid": capability.founder_principal_sid,
            "proof_digest": None,
            "receipt": None,
            "created_at": now.isoformat(),
            "updated_at": now.isoformat(),
        }
        stored = self.store.begin_provider_host_enrollment(enrollment_id, record)
        return {
            "enrollment_id": enrollment_id,
            "state": str(stored["service_state"]),
            "grant": stored["grant"],
            "grant_digest": stored["grant_digest"],
            "expires_at": grant_payload["expires_at"],
        }

    def complete(
        self, payload: Mapping[str, Any], client_sid: str
    ) -> dict[str, Any]:
        if set(payload) != {"enrollment_id", "proof"}:
            raise PermissionError("Provider Host enrollment completion fields are invalid")
        enrollment_id = _text(payload["enrollment_id"], "enrollment ID")
        record = self.store.get("provider_host_enrollments", enrollment_id)
        if record is None:
            raise PermissionError("Provider Host enrollment is absent")
        if str(record.get("founder_principal_sid", "")).casefold() != client_sid.casefold():
            raise PermissionError("Provider Host enrollment client identity differs")
        proposal_record = _object(record["proposal"], "stored proposal")
        proposal = _object(proposal_record["payload"], "stored proposal payload")
        public = _object(proposal["host_public_identity"], "Host public identity")
        host_verifier = self.host_verifier_factory(public)
        grant_record = _object(record["grant"], "stored grant")
        grant = _object(grant_record["payload"], "stored grant payload")
        proof_record = _object(payload["proof"], "enrollment proof")
        proof = validate_enrollment_proof(
            proof_record,
            host_verifier,
            grant,
            expected_grant_digest=str(record["grant_digest"]),
            now=self.now(),
        )
        if proof.get("host_public_key_id") != public.get("key_id"):
            raise PermissionError("Provider Host enrollment proof key differs")
        proof_digest = structured_digest(proof_record)
        if record.get("service_state") == "ACTIVE":
            if record.get("proof_digest") != proof_digest:
                raise PermissionError("Provider Host enrollment proof conflicts")
            self.activate(record)
            return self._completion_result(record)
        if record.get("service_state") != "PENDING":
            raise PermissionError("Provider Host enrollment is not completable")
        runtime = self.proposal_observer.provider_host_runtime_configuration(
            proposal,
            enrollment_id=enrollment_id,
            authority_id=self.authority_signer.identity,
            authority_public_identity=self.authority_public_identity,
        )
        activated_at = self.now().astimezone(UTC).isoformat()
        receipt_payload = {
            "activated_at": activated_at,
            "authority_id": self.authority_signer.identity,
            "authority_key_id": self.authority_signer.key_id,
            "authority_protocol_version": self.authority_protocol_version,
            "authority_schema_version": self.authority_schema_version,
            "enrollment_generation": int(record["enrollment_generation"]),
            "enrollment_id": enrollment_id,
            "grant_digest": str(record["grant_digest"]),
            "host_id": str(proposal["host_id"]),
            "host_protocol": HOST_PROTOCOL,
            "host_public_key_id": str(public["key_id"]),
            "proof_digest": proof_digest,
            "proposal_digest": str(record["proposal_digest"]),
            "runtime_configuration": runtime,
            "service_key_id": self.service_key_id,
            "state": "ACTIVE",
        }
        receipt = self.authority_signer.sign(
            ENROLLMENT_RECEIPT_PURPOSE, receipt_payload
        )
        completed = {
            **{name: value for name, value in record.items() if name != "service_state"},
            "proof_digest": proof_digest,
            "receipt": receipt,
            "updated_at": activated_at,
        }
        stored = self.store.complete_provider_host_enrollment(
            enrollment_id,
            proof_digest=proof_digest,
            payload=completed,
        )
        try:
            self.activate(stored)
        except (OSError, PermissionError, RuntimeError, TypeError, ValueError):
            uncertain = {
                **{name: value for name, value in stored.items() if name != "service_state"},
                "uncertainty_kind": "ACTIVATION",
                "updated_at": self.now().astimezone(UTC).isoformat(),
            }
            self.store.transition_provider_host_enrollment(
                enrollment_id,
                expected=("ACTIVE",),
                state="UNCERTAIN",
                payload=uncertain,
            )
            raise RuntimeError(
                "Provider Host enrollment activation is uncertain; reconcile explicitly"
            )
        return self._completion_result(stored)

    def reconcile(
        self, payload: Mapping[str, Any], client_sid: str
    ) -> dict[str, Any]:
        if set(payload) != {"enrollment_id", "proof"}:
            raise PermissionError("Provider Host reconciliation fields are invalid")
        enrollment_id = _text(payload["enrollment_id"], "enrollment ID")
        record = self.store.get("provider_host_enrollments", enrollment_id)
        if record is None:
            raise PermissionError("Provider Host enrollment is absent")
        if str(record.get("founder_principal_sid", "")).casefold() != client_sid.casefold():
            raise PermissionError("Provider Host enrollment client identity differs")
        state = str(record["service_state"])
        if state == "PENDING":
            grant = _object(_object(record["grant"], "stored grant")["payload"], "stored grant payload")
            if datetime.fromisoformat(str(grant["expires_at"])) <= self.now().astimezone(UTC):
                expired = {
                    **{name: value for name, value in record.items() if name != "service_state"},
                    "updated_at": self.now().astimezone(UTC).isoformat(),
                }
                self.store.transition_provider_host_enrollment(
                    enrollment_id,
                    expected=("PENDING",),
                    state="EXPIRED",
                    payload=expired,
                )
                return {"enrollment_id": enrollment_id, "state": "EXPIRED"}
            return self.complete(payload, client_sid)
        proof_digest = structured_digest(_object(payload["proof"], "enrollment proof"))
        if record.get("proof_digest") != proof_digest:
            raise PermissionError("Provider Host reconciliation proof differs")
        if state == "ACTIVE":
            self.activate(record)
            return self._completion_result(record)
        if state != "UNCERTAIN" or record.get("uncertainty_kind") != "ACTIVATION":
            raise PermissionError("Provider Host enrollment cannot be reconciled")
        self.activate(record)
        reconciled = {
            **{name: value for name, value in record.items() if name != "service_state"},
            "updated_at": self.now().astimezone(UTC).isoformat(),
        }
        self.store.transition(
            "provider_host_enrollments",
            enrollment_id,
            "UNCERTAIN",
            "ACTIVE",
            reconciled,
        )
        return self._completion_result({**reconciled, "service_state": "ACTIVE"})

    def revoke(
        self, payload: Mapping[str, Any], client_sid: str
    ) -> dict[str, Any]:
        if set(payload) != {"enrollment_id", "founder_capability"}:
            raise PermissionError("Provider Host revocation fields are invalid")
        enrollment_id = _text(payload["enrollment_id"], "enrollment ID")
        record = self.store.get("provider_host_enrollments", enrollment_id)
        if record is None or record.get("service_state") not in {
            "ACTIVE",
            "UNCERTAIN",
            "REVOKED",
        }:
            raise PermissionError("Provider Host active enrollment is absent")
        receipt = _object(record.get("receipt"), "enrollment receipt")
        revocation_binding = {
            "action": "REVOKE_PROVIDER_HOST",
            "enrollment_id": enrollment_id,
            "receipt_digest": structured_digest(receipt),
        }
        capability = self._founder_capability(
            payload["founder_capability"],
            client_sid,
            action="REVOKE_PROVIDER_HOST",
            action_digest=structured_digest(revocation_binding),
            generation=int(record["enrollment_generation"]) + 1,
        )
        capability_value_digest = capability_digest(capability)
        if record.get("service_state") == "REVOKED":
            return self._revocation_result(record)
        for prior in self.store.list_records("provider_host_enrollments"):
            if prior.get("revocation_capability_digest") == capability_value_digest:
                raise PermissionError("Founder Host-revocation capability is replayed")
        revoked_at = self.now().astimezone(UTC).isoformat()
        revocation = self.authority_signer.sign(
            ENROLLMENT_REVOCATION_PURPOSE,
            {
                "authority_id": self.authority_signer.identity,
                "authority_key_id": self.authority_signer.key_id,
                "enrollment_generation": int(record["enrollment_generation"]),
                "enrollment_id": enrollment_id,
                "host_id": str(
                    _object(_object(record["proposal"], "stored proposal")["payload"], "stored proposal payload")["host_id"]
                ),
                "receipt_digest": structured_digest(receipt),
                "revoked_at": revoked_at,
                "service_key_id": self.service_key_id,
                "state": "REVOKED",
            },
        )
        revoked = {
            **{name: value for name, value in record.items() if name != "service_state"},
            "revocation_capability_digest": capability_value_digest,
            "revocation": revocation,
            "revoked_at": revoked_at,
            "updated_at": revoked_at,
        }
        revocation_pending = {
            **revoked,
            "uncertainty_kind": "REVOCATION",
        }
        # Fence restart and every new gateway RPC durably before removing the
        # live gateway. Any interruption remains non-executable and can only be
        # completed by the exact Founder-authorized revocation operation.
        pending = self.store.transition_provider_host_enrollment(
            enrollment_id,
            expected=("ACTIVE", "UNCERTAIN"),
            state="UNCERTAIN",
            payload=revocation_pending,
        )
        self.deactivate(pending)
        stored = self.store.transition_provider_host_enrollment(
            enrollment_id,
            expected=("UNCERTAIN",),
            state="REVOKED",
            payload=revoked,
        )
        return self._revocation_result(stored)

    def activate_current(self) -> None:
        record = self.store.current_provider_host_enrollment()
        if record is not None and record.get("service_state") == "ACTIVE":
            self.activate(record)

    def _founder_capability(
        self,
        value: object,
        client_sid: str,
        *,
        action: str,
        action_digest: str,
        generation: int,
    ) -> FounderAuthorizationCapability:
        if not isinstance(value, dict):
            raise PermissionError("Founder Host-enrollment capability is absent")
        try:
            capability = self.founder_verifier.verify(value)
        except (KeyError, TypeError, ValueError) as error:
            raise PermissionError(
                "Founder Host-enrollment capability is invalid"
            ) from error
        now = self.now().astimezone(UTC)
        if (
            capability.authorization_kind != "PROVIDER_HOST_ENROLLMENT"
            or capability.protected_action != action
            or capability.action_digest != action_digest
            or capability.project_id != ENROLLMENT_SYSTEM_PROJECT
            or capability.charter_id != ENROLLMENT_SYSTEM_CHARTER
            or capability.charter_revision != 1
            or capability.authorization_generation != generation
            or capability.revocation_epoch != generation - 1
            or capability.usage != "ONE_TIME_GENERATION"
            or capability.founder_principal_sid.casefold() != client_sid.casefold()
            or datetime.fromisoformat(capability.issued_at) > now
            or datetime.fromisoformat(capability.expires_at) <= now
        ):
            raise PermissionError("Founder Host-enrollment capability binding differs")
        return capability

    @staticmethod
    def _completion_result(record: Mapping[str, Any]) -> dict[str, Any]:
        receipt = record.get("receipt")
        if not isinstance(receipt, dict):
            raise RuntimeError("Provider Host enrollment receipt is unavailable")
        return {
            "enrollment_id": str(record["enrollment_id"]),
            "state": "ACTIVE",
            "receipt": dict(receipt),
            "receipt_digest": structured_digest(receipt),
        }

    @staticmethod
    def _revocation_result(record: Mapping[str, Any]) -> dict[str, Any]:
        revocation = record.get("revocation")
        if not isinstance(revocation, dict):
            raise RuntimeError("Provider Host revocation receipt is unavailable")
        return {
            "enrollment_id": str(record["enrollment_id"]),
            "state": "REVOKED",
            "revocation": dict(revocation),
            "revocation_digest": structured_digest(revocation),
            "revoked_at": str(record["revoked_at"]),
        }


def _object(value: object, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise PermissionError(f"Provider Host {label} is invalid")
    return dict(cast(dict[str, Any], value))


def _text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value or "\x00" in value:
        raise PermissionError(f"Provider Host {label} is invalid")
    return value
