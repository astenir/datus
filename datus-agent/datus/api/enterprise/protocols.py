"""Protocols implemented by enterprise extension packages."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from datus.api.auth.context import AppContext
from datus.api.enterprise.models import AccessDecision, AuditEvent, ProjectionInput, ProjectionResult, ResourceRef


@runtime_checkable
class AuthorizationProvider(Protocol):
    """Authorize module and resource access."""

    async def check(self, ctx: AppContext, action: str, resource: ResourceRef) -> AccessDecision:
        """Return whether ``ctx`` can perform ``action`` on ``resource``."""
        ...

    async def allowed_datasources(self, ctx: AppContext) -> dict[str, Any]:
        """Return datasource grants visible to ``ctx``."""
        ...


@runtime_checkable
class ConfigProjector(Protocol):
    """Build request-scoped config clones for execution paths."""

    async def project(self, request: ProjectionInput) -> ProjectionResult:
        """Return a projected AgentConfig clone and derived principal."""
        ...


@runtime_checkable
class SessionOwnerStore(Protocol):
    """Persist and query session owner metadata."""

    async def set_owner(self, project_id: str, session_id: str, user_id: str) -> None:
        """Record the owner of a session."""
        ...

    async def get_owner(self, project_id: str, session_id: str) -> str | None:
        """Return the recorded session owner, if any."""
        ...

    async def delete_owner(self, project_id: str, session_id: str) -> None:
        """Remove owner metadata for a deleted session."""
        ...

    async def list_session_ids(self, project_id: str, user_id: str) -> list[str]:
        """Return session ids recorded for ``user_id`` in ``project_id``."""
        ...


@runtime_checkable
class AuditSink(Protocol):
    """Write security audit events."""

    async def write(self, event: AuditEvent) -> None:
        """Persist or forward an audit event."""
        ...


@runtime_checkable
class AuditLogReader(Protocol):
    """Optional audit log query interface for admin APIs."""

    async def query_events(
        self,
        *,
        limit: int,
        user_id: str | None = None,
        action: str | None = None,
        resource_type: str | None = None,
        resource_id: str | None = None,
        decision: str | None = None,
    ) -> list[AuditEvent]:
        """Return matching audit events, newest first."""
        ...
