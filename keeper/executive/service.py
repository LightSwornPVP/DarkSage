from __future__ import annotations

from pathlib import Path
from typing import Any

from keeper.app.storage import KeeperStore
from keeper.authority_service.client import ProductionAuthorityServiceClient
from keeper.executive.authority_gateway import (
    AuthorityProviderBinding,
    ProductionAuthorityBackedSpecialistGateway,
)
from keeper.executive.charters import CharterService
from keeper.executive.intake import ConversationIntake, IntakeResult
from keeper.executive.models import MemoryRecord, ProjectCharter, ProjectRecord, utc_now
from keeper.executive.repository import ExecutiveRepository, new_id
from keeper.executive.runtime import ExecutiveRuntime
from keeper.executive.surfaces import ProjectStatusView, StatusSurface


class KeeperExecutive:
    """Conversation-first application facade for future desktop clients."""

    def __init__(self, database: Path) -> None:
        store = KeeperStore(database)
        store.migrate()
        self.repository = ExecutiveRepository(store)
        self.charters = CharterService(self.repository)
        self.intake = ConversationIntake()

    def begin(self, message: str) -> tuple[ProjectRecord, IntakeResult]:
        result = self.intake.extract(message)
        project = self.charters.create_project(result)
        interaction_id = new_id("interaction")
        self.repository.save_conversation(
            interaction_id,
            {
                "interaction_id": interaction_id,
                "project_id": project.project_id,
                "speaker": "Founder",
                "message": message,
                "created_at": utc_now(),
            },
        )
        for field_name, item in result.fields.items():
            self.repository.insert_memory(
                MemoryRecord(
                    new_id("memory"),
                    project.project_id,
                    0,
                    None,
                    None,
                    "FACT" if item.provenance == "EXPLICIT" else "ASSUMPTION",
                    item.provenance,
                    f"intake:{field_name}",
                    str(item.value),
                    field_name in {
                        "budget_policy",
                        "budget_limit",
                        "delegation_mode",
                        "workspaces",
                        "approved_providers",
                        "approved_tools",
                    },
                    (interaction_id,),
                    None,
                    utc_now(),
                )
            )
        return project, result

    def draft(
        self,
        project_id: str,
        intake: IntakeResult,
        *,
        founder_revisions: dict[str, Any] | None = None,
    ) -> ProjectCharter:
        revised = (
            ConversationIntake.revise(intake, replacements=founder_revisions)
            if founder_revisions
            else intake
        )
        return self.charters.draft(self.repository.project(project_id), revised)

    def status(self, project_id: str) -> ProjectStatusView:
        return StatusSurface(self.repository).project(project_id)

    def production_runtime(
        self,
        authority_client: ProductionAuthorityServiceClient,
        *,
        provider_bindings: tuple[AuthorityProviderBinding, ...],
        exchange_root: Path,
    ) -> ExecutiveRuntime:
        """Fail-closed production composition root; no mock gateway seam."""
        if type(authority_client) is not ProductionAuthorityServiceClient:
            raise RuntimeError(
                "production runtime requires the production Authority client"
            )
        authority_client.require_live_identity()
        gateway = ProductionAuthorityBackedSpecialistGateway(
            authority_client,
            provider_bindings,
            exchange_root,
        )
        return ExecutiveRuntime.production(self.repository, gateway)
