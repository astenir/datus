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
class EnterpriseUserStore(Protocol):
    """Persist and query enterprise user metadata."""

    async def list_users(self, *, enabled: bool | None = None) -> list[dict[str, Any]]:
        """Return user records, optionally filtered by enabled status."""
        ...

    async def get_user(self, user_id: str) -> dict[str, Any] | None:
        """Return one user record, if present."""
        ...

    async def upsert_user(
        self,
        *,
        user_id: str,
        display_name: str | None = None,
        email: str | None = None,
        enabled: bool = True,
    ) -> dict[str, Any]:
        """Create or update a user record."""
        ...

    async def set_user_enabled(self, user_id: str, enabled: bool) -> dict[str, Any] | None:
        """Enable or disable a user record."""
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

    async def list_sessions(self, project_id: str, user_id: str | None = None) -> list[dict[str, Any]]:
        """Return session owner records in ``project_id``, optionally filtered by user."""
        ...


@runtime_checkable
class ArtifactAclStore(Protocol):
    """Optional artifact ACL persistence interface for admin APIs."""

    async def get_acl(self, *, artifact_type: str, slug: str) -> dict[str, Any]:
        """Return the ACL metadata for one artifact."""
        ...

    async def put_acl(self, *, artifact_type: str, slug: str, acl: dict[str, Any]) -> dict[str, Any]:
        """Persist and return the ACL metadata for one artifact."""
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
