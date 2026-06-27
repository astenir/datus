"""Enterprise extension interfaces and local-compatible defaults."""

from datus.api.enterprise.defaults import (
    InMemorySessionOwnerStore,
    LocalAuthorizationProvider,
    NoopAuditSink,
    PassthroughConfigProjector,
    SqliteSessionOwnerStore,
)
from datus.api.enterprise.deps import (
    SessionAccess,
    authorize,
    authorize_session_access,
    delete_session_owner,
    require_module,
)
from datus.api.enterprise.loader import EnterpriseExtensions, load_enterprise_extensions
from datus.api.enterprise.models import (
    AccessDecision,
    AuditEvent,
    ProjectionInput,
    ProjectionResult,
    ResourceRef,
)
from datus.api.enterprise.protocols import (
    AuditLogReader,
    AuditSink,
    AuthorizationProvider,
    ConfigProjector,
    SessionOwnerStore,
)

__all__ = [
    "AccessDecision",
    "AuditEvent",
    "AuditLogReader",
    "AuditSink",
    "AuthorizationProvider",
    "ConfigProjector",
    "EnterpriseExtensions",
    "InMemorySessionOwnerStore",
    "LocalAuthorizationProvider",
    "NoopAuditSink",
    "PassthroughConfigProjector",
    "ProjectionInput",
    "ProjectionResult",
    "ResourceRef",
    "SessionOwnerStore",
    "SessionAccess",
    "SqliteSessionOwnerStore",
    "authorize",
    "authorize_session_access",
    "delete_session_owner",
    "load_enterprise_extensions",
    "require_module",
]
