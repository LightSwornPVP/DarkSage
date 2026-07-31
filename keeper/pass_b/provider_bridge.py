from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from types import MappingProxyType
from typing import Any

from keeper.authority_service.client import ProductionAuthorityServiceClient
from keeper.executive.authority_gateway import AuthorityProviderBinding
from keeper.pass_b.enums import (
    CostMode,
    HealthState,
    ProviderClassification,
    ProviderSessionState,
    SessionModel,
)
from keeper.pass_b.models import (
    ProviderAccountRecord,
    ProviderRecord,
    ProviderSessionRecord,
    UsagePoolRecord,
)
from keeper.pass_b.orchestration import OrchestrationService
from keeper.pass_b.providers import AdapterAssignment, AdapterDescriptor, AdapterResult


_ROLE_ALIASES = MappingProxyType(
    {
        "planning": "planner",
        "implementation": "implementer",
        "review": "reviewer",
        "research": "researcher",
        "testing": "tester",
        "documentation": "documentation_specialist",
    }
)


@dataclass(frozen=True, slots=True)
class AuthorityManagedAdapter:
    """Descriptor-only adapter; production execution remains Authority-owned."""

    adapter_descriptor: AdapterDescriptor

    def descriptor(self) -> AdapterDescriptor:
        return self.adapter_descriptor

    def launch(self, assignment: AdapterAssignment) -> AdapterResult:
        del assignment
        raise PermissionError(
            "Authority-managed provider cannot execute through a local adapter"
        )

    def cancel(self, external_execution_id: str) -> None:
        del external_execution_id
        raise PermissionError(
            "Authority-managed cancellation requires the Authority service"
        )

    def resume(
        self, assignment: AdapterAssignment, resume_token: str
    ) -> AdapterResult:
        del assignment, resume_token
        raise PermissionError(
            "Authority-managed resume requires the Authority service"
        )

    def health(self) -> dict[str, Any]:
        return {
            "provider_id": self.adapter_descriptor.provider_identity,
            "state": self.adapter_descriptor.health,
            "composition": "PRODUCTION_AUTHORITY",
        }


def bridge_qualified_provider(
    orchestration: OrchestrationService,
    authority: ProductionAuthorityServiceClient,
    binding: AuthorityProviderBinding,
) -> ProviderRecord:
    """Project one exact Authority-qualified provider into Pass B records."""

    registration_container = authority.query_state(
        "registrations", binding.registration_id
    )
    qualification_container = authority.query_state(
        "qualifications", binding.qualification_id
    )
    registration = _record(registration_container, "registration")
    qualified = _record(qualification_container, "qualification")
    evidence = qualified.get("evidence")
    if (
        registration.get("service_state") != "QUALIFIED"
        or qualified.get("service_state") != "QUALIFIED"
        or not isinstance(evidence, dict)
        or evidence.get("registration_id") != binding.registration_id
        or evidence.get("id") != binding.qualification_id
        or evidence.get("qualification_result") != "qualified"
        or not authority.verify("provider-qualification", evidence)
    ):
        raise PermissionError("Authority provider qualification is invalid")
    provider_id = _text(registration, "logical_provider_id")
    model_id = _text(registration, "model_or_service_identity")
    session_id = _text(evidence, "provider_instance_id")
    declared_capabilities = _texts(
        registration, "executive_capability_set"
    )
    capabilities = tuple(
        dict.fromkeys(
            [
                *(item.casefold() for item in declared_capabilities),
                *(
                    alias
                    for source, alias in _ROLE_ALIASES.items()
                    if source in {item.casefold() for item in declared_capabilities}
                ),
            ]
        )
    )
    pricing = registration.get("pricing_authority")
    if not isinstance(pricing, dict) or set(pricing) != {
        "pricing_identity",
        "pricing_version",
        "currency",
        "estimated_cost",
        "maximum_cost",
        "billing_unit",
        "included_plan",
        "marginally_free",
        "quoted_at",
        "expires_at",
        "source",
        "cost_tier",
    }:
        raise PermissionError("Authority provider pricing declaration is invalid")
    if pricing.get("marginally_free") is True:
        cost_mode = CostMode.FREE
    elif pricing.get("included_plan") is True:
        cost_mode = CostMode.INCLUDED
    else:
        cost_mode = CostMode.PAID
    now = datetime.now(UTC).isoformat()
    account_id = f"authority-account:{binding.registration_id}"
    pool_id = f"authority-pool:{binding.registration_id}"
    descriptor = AdapterDescriptor(
        provider_identity=f"authority:{binding.registration_id}",
        model_identity=model_id,
        capabilities=capabilities,
        classification=ProviderClassification.LOCAL,
        session_model=SessionModel.PERSISTENT,
        usage_pool_identity=f"authority-usage:{binding.registration_id}",
        concurrency_limit=1,
        cost_mode=cost_mode,
        authentication_ready=True,
        tool_support=("authority-managed-tools",),
        workspace_support=("isolated-worktree", "read-only"),
        cancellation_support=True,
        resume_support=False,
        evidence_format="keeper-evidence-v1",
        health=HealthState.READY,
    )
    provider = ProviderRecord(
        provider_id=provider_id,
        identity=descriptor.provider_identity,
        display_name=provider_id,
        classification=descriptor.classification,
        adapter_kind="authority-managed",
        capabilities=descriptor.capabilities,
        session_model=descriptor.session_model,
        usage_pool_strategy="authority-declared",
        concurrency_limit=descriptor.concurrency_limit,
        cost_mode=descriptor.cost_mode,
        authentication_ready=True,
        tool_support=descriptor.tool_support,
        workspace_support=descriptor.workspace_support,
        cancellation_support=descriptor.cancellation_support,
        resume_support=descriptor.resume_support,
        evidence_format=descriptor.evidence_format,
        health=descriptor.health,
        created_at=now,
        updated_at=now,
        revision=1,
        authority_registration_id=binding.registration_id,
    )
    account = ProviderAccountRecord(
        account_id=account_id,
        provider_id=provider_id,
        identity=f"authority:{binding.registration_id}:account",
        display_name="Authority-managed account",
        usage_pool_id=pool_id,
        cost_mode=cost_mode,
        privacy_classification="AUTHORITY_DECLARED",
        authentication_ready=True,
        enabled=cost_mode != CostMode.PAID,
        created_at=now,
        updated_at=now,
        revision=1,
    )
    pool = UsagePoolRecord(
        pool_id=pool_id,
        provider_id=provider_id,
        account_id=account_id,
        identity=descriptor.usage_pool_identity,
        limit_type="AUTHORITY_DECLARED_INCLUDED",
        capacity=None,
        consumed=0.0,
        reserved=0.0,
        remaining=None,
        reset_at=None,
        observation_source="KEEPERAUTHORITY_QUALIFICATION",
        confidence="HIGH",
        exhausted=False,
        last_observed_at=now,
        created_at=now,
        updated_at=now,
        revision=1,
    )
    session = ProviderSessionRecord(
        session_id=session_id,
        provider_id=provider_id,
        account_id=account_id,
        model_id=model_id,
        external_session_id=session_id,
        state=ProviderSessionState.READY,
        concurrency_limit=1,
        active_assignments=0,
        supports_resume=False,
        resume_token_digest=None,
        last_seen_at=now,
        created_at=now,
        updated_at=now,
        revision=1,
    )
    adapter = AuthorityManagedAdapter(descriptor)
    existing = orchestration.repository.optional(ProviderRecord, provider_id)
    if existing is None:
        orchestration.register_provider(
            provider, account, pool, (session,), adapter
        )
        return provider
    if existing.authority_registration_id != binding.registration_id:
        raise PermissionError("durable provider registration identity changed")
    orchestration.attach_adapter(provider_id, adapter)
    return existing


def _record(value: object, label: str) -> dict[str, Any]:
    if not isinstance(value, dict) or value.get("found") is not True:
        raise PermissionError(f"Authority {label} is unavailable")
    record = value.get("record")
    if not isinstance(record, dict):
        raise PermissionError(f"Authority {label} is malformed")
    return dict(record)


def _text(value: dict[str, Any], name: str) -> str:
    result = value.get(name)
    if not isinstance(result, str) or not result:
        raise PermissionError(f"Authority provider {name} is invalid")
    return result


def _texts(value: dict[str, Any], name: str) -> tuple[str, ...]:
    result = value.get(name)
    if (
        not isinstance(result, list)
        or not result
        or any(not isinstance(item, str) or not item for item in result)
    ):
        raise PermissionError(f"Authority provider {name} is invalid")
    return tuple(result)
