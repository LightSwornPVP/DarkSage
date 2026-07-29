from __future__ import annotations

import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from keeper.app.storage import KeeperStore, default_data_directory
from keeper.authority_service.client import ProductionAuthorityServiceClient
from keeper.executive.service import KeeperExecutive
from keeper.pass_b.control_room import ControlRoomService
from keeper.pass_b.conversation import ConversationExecutive
from keeper.pass_b.conversation_runtime import DurableConversationService
from keeper.pass_b.enums import (
    AssignmentRole,
    CostMode,
    HealthState,
    PresentationMode,
    ProviderClassification,
    ProviderSessionState,
    SessionModel,
)
from keeper.pass_b.models import (
    PresentationStateRecord,
    ProviderAccountRecord,
    ProviderRecord,
    ProviderSessionRecord,
    UsagePoolRecord,
)
from keeper.pass_b.launch_authority import (
    ExecutiveAuthorityLaunchGate,
    LaunchAuthority,
)
from keeper.pass_b.orchestration import OrchestrationService
from keeper.pass_b.providers import LocalMockAdapter, ProviderAdapter
from keeper.pass_b.repository import PassBRepository
from keeper.pass_b.usage_authority import UsageResetVerifier


class PassBApplication:
    """Conversation-first Pass B application composition."""

    def __init__(
        self,
        data_directory: Path | None = None,
        *,
        executive: ConversationExecutive | None = None,
        authority_client: ProductionAuthorityServiceClient | None = None,
        usage_reset_verifier: UsageResetVerifier | None = None,
        _test_launch_authority: LaunchAuthority | None = None,
    ) -> None:
        self.data_directory = (
            data_directory or default_data_directory()
        ).resolve()
        self.store = KeeperStore(self.data_directory / "keeper.db")
        self.store.migrate()
        self.repository = PassBRepository(self.store)
        self.startup_recovery = (
            self.repository.recover_interrupted_attempts(_now())
        )
        self.executive = executive or KeeperExecutive(self.store.path)
        self.authority_client = authority_client
        self._test_authority_configured = _test_launch_authority is not None
        if _test_launch_authority is not None:
            launch_authority = _test_launch_authority
        elif authority_client is not None:
            if not isinstance(self.executive, KeeperExecutive):
                raise TypeError(
                    "production Authority requires the production Executive"
                )
            launch_authority = ExecutiveAuthorityLaunchGate.production(
                self.executive, authority_client
            )
        else:
            launch_authority = None
        self.orchestration = OrchestrationService(
            self.repository,
            launch_authority=launch_authority,
            usage_reset_verifier=usage_reset_verifier,
        )
        self.conversation = DurableConversationService(
            self.repository, self.executive
        )
        self.control_room = ControlRoomService(
            self.repository, authority_health=self._authority_health
        )
        self._ensure_presentation_state()

    @classmethod
    def test_composition(
        cls,
        data_directory: Path,
        *,
        executive: ConversationExecutive,
        launch_authority: LaunchAuthority,
        usage_reset_verifier: UsageResetVerifier,
    ) -> PassBApplication:
        """Build an explicitly non-production deterministic composition."""

        return cls(
            data_directory,
            executive=executive,
            usage_reset_verifier=usage_reset_verifier,
            _test_launch_authority=launch_authority,
        )

    def begin_conversation(self, message: str) -> Any:
        return self.conversation.begin(message)

    def register_local_mock(
        self,
        *,
        provider_id: str = "local-mock",
        account_id: str = "local-default",
        session_count: int = 2,
    ) -> tuple[ProviderRecord, tuple[ProviderSessionRecord, ...]]:
        if session_count < 1:
            raise ValueError("at least one provider session is required")
        adapter = LocalMockAdapter(provider_id)
        descriptor = adapter.descriptor()
        now = _now()
        existing = self.repository.optional(ProviderRecord, provider_id)
        if existing is not None:
            account = self.repository.get(
                ProviderAccountRecord, account_id
            )
            sessions = tuple(
                item
                for item in self.repository.list(ProviderSessionRecord)
                if item.provider_id == provider_id
                and item.account_id == account_id
            )
            if (
                account.provider_id != provider_id
                or len(sessions) != session_count
            ):
                raise PermissionError(
                    "local provider restart configuration changed"
                )
            self.orchestration.attach_adapter(provider_id, adapter)
            return existing, sessions
        pool_id = f"usage-{provider_id}-{account_id}"
        provider = ProviderRecord(
            provider_id=provider_id,
            identity=descriptor.provider_identity,
            display_name="Local deterministic provider",
            classification=ProviderClassification.LOCAL,
            adapter_kind="local-mock",
            capabilities=tuple(
                role.value.casefold() for role in AssignmentRole
            )
            + descriptor.capabilities,
            session_model=SessionModel.RESUMABLE,
            usage_pool_strategy="shared-account-window",
            concurrency_limit=descriptor.concurrency_limit,
            cost_mode=CostMode.FREE,
            authentication_ready=True,
            tool_support=descriptor.tool_support,
            workspace_support=descriptor.workspace_support,
            cancellation_support=True,
            resume_support=True,
            evidence_format=descriptor.evidence_format,
            health=HealthState.READY,
            created_at=now,
            updated_at=now,
            revision=1,
        )
        account = ProviderAccountRecord(
            account_id=account_id,
            provider_id=provider_id,
            identity=f"{provider_id}:{account_id}",
            display_name="Local included account",
            usage_pool_id=pool_id,
            cost_mode=CostMode.FREE,
            privacy_classification="LOCAL",
            authentication_ready=True,
            enabled=True,
            created_at=now,
            updated_at=now,
            revision=1,
        )
        pool = UsagePoolRecord(
            pool_id=pool_id,
            provider_id=provider_id,
            account_id=account_id,
            identity=descriptor.usage_pool_identity,
            limit_type="UNLIMITED_LOCAL",
            capacity=None,
            consumed=0,
            reserved=0,
            remaining=None,
            reset_at=None,
            observation_source="deterministic-local",
            confidence="HIGH",
            exhausted=False,
            last_observed_at=now,
            created_at=now,
            updated_at=now,
            revision=1,
        )
        sessions = tuple(
            ProviderSessionRecord(
                session_id=f"{provider_id}-session-{index}",
                provider_id=provider_id,
                account_id=account_id,
                model_id="deterministic-v1",
                external_session_id=None,
                state=ProviderSessionState.READY,
                concurrency_limit=1,
                active_assignments=0,
                supports_resume=True,
                resume_token_digest=None,
                last_seen_at=now,
                created_at=now,
                updated_at=now,
                revision=1,
            )
            for index in range(1, session_count + 1)
        )
        self.orchestration.register_provider(
            provider, account, pool, sessions, adapter
        )
        return provider, sessions

    def attach_adapter(
        self, provider_id: str, adapter: ProviderAdapter
    ) -> None:
        self.orchestration.attach_adapter(provider_id, adapter)

    def register_adapter(
        self,
        provider: ProviderRecord,
        account: ProviderAccountRecord,
        pool: UsagePoolRecord,
        sessions: tuple[ProviderSessionRecord, ...],
        adapter: ProviderAdapter,
    ) -> None:
        self.orchestration.register_provider(
            provider, account, pool, sessions, adapter
        )

    def diagnostics(self) -> dict[str, Any]:
        return {
            "data_directory": str(self.data_directory),
            "pass_b_schema_version": 3,
            "authority": self._authority_health(),
            "launch_authority_configured": (
                self.authority_client is not None
                or self._test_authority_configured
            ),
            "providers": len(self.repository.list(ProviderRecord)),
            "sessions": len(self.repository.list(ProviderSessionRecord)),
            "startup_recovery": dict(self.startup_recovery),
            "presentation_authority_effect": "NONE",
            "automatic_paid_fallback": False,
            "provider_code_loading": False,
        }

    def _authority_health(self) -> dict[str, Any]:
        client = self.authority_client
        if client is None:
            if self._test_authority_configured:
                return {
                    "state": "TEST_COMPOSITION",
                    "production_validation": False,
                }
            return {"state": "NOT_CONFIGURED"}
        try:
            value = client.require_live_identity()
        except (OSError, PermissionError, RuntimeError, TimeoutError) as error:
            return {"state": "UNAVAILABLE", "error": str(error)}
        return {
            "state": "READY",
            "service_version": value.get("service_version"),
            "protocol_version": value.get("protocol_version"),
            "service_key_id": value.get("service_key_id"),
        }

    def _ensure_presentation_state(self) -> None:
        if self.repository.optional(
            PresentationStateRecord, "sage-default"
        ) is not None:
            return
        self.repository.insert(
            PresentationStateRecord(
                presentation_state_id="sage-default",
                project_id=None,
                form="default",
                mode=PresentationMode.CONVERSATION,
                expression="neutral",
                intensity=0.25,
                background="black-gold",
                ambient_effect="none",
                updated_at=_now(),
                revision=1,
            )
        )


def _now() -> str:
    return datetime.now(UTC).isoformat()
