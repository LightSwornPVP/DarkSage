from __future__ import annotations

from typing import Any, Protocol

from keeper.authority_service.client import AuthorityServiceClient


class AuthorityOperations(Protocol):
    """Narrow executive view of the approved Authority Service contract."""

    def query_state(self, kind: str, identifier: str) -> dict[str, Any]: ...
    def reserve_attempt(self, **identity: Any) -> dict[str, Any]: ...
    def execute_provider(self, attempt_id: str) -> dict[str, Any]: ...
    def finalize_completion(self, attempt_id: str) -> dict[str, Any]: ...
    def cancel_attempt(self, attempt_id: str) -> dict[str, Any]: ...
    def verify(self, purpose: str, record: object) -> bool: ...


def authority_operations(client: AuthorityServiceClient) -> AuthorityOperations:
    """Dependency-inversion seam; no signing or protected state enters the executive."""
    return client
