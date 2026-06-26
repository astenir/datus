"""Enterprise extension interfaces and local-compatible defaults."""

from datus.api.enterprise.defaults import (
    InMemorySessionOwnerStore,
    LocalAuthorizationProvider,
    NoopAuditSink,
    PassthroughConfigProjector,
)
from datus.api.enterprise.deps import authorize, require_module
from datus.api.enterprise.loader import EnterpriseExtensions, load_enterprise_extensions
from datus.api.enterprise.models import (
    AccessDecision,
    AuditEvent,
    ProjectionInput,
    ProjectionResult,
    ResourceRef,
)
from datus.api.enterprise.protocols import (
    AuditSink,
    AuthorizationProvider,
    ConfigProjector,
    SessionOwnerStore,
)

__all__ = [
    "AccessDecision",
    "AuditEvent",
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
    "authorize",
    "load_enterprise_extensions",
    "require_module",
]
