"""Application context — request authentication and configuration."""

from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Set

from datus.configuration.agent_config import AgentConfig


@dataclass
class AppContext:
    """Request context with optional agent configuration.

    - ``user_id``: identifier from the auth provider; ``None`` means anonymous.
      Used as ``SessionManager.scope`` to isolate sessions per user.
    - ``project_id``: optional project identifier; ``None`` means the single
      (default) project.
    - ``config``: optional preloaded ``AgentConfig``; when ``None``,
      ``get_datus_service`` loads it on demand.
    - ``principal``: request-scoped SQL policy attributes consumed by
      SQL policies. This is separate from ``user_id`` because one
      authenticated identity can carry many business scopes.
    - ``roles`` / ``permissions`` / ``datasource_grants``: enterprise RBAC
      metadata loaded by production auth/RBAC providers. Local no-auth mode
      leaves them empty.
    """

    user_id: Optional[str] = None
    project_id: Optional[str] = None
    config: Optional[AgentConfig] = None
    principal: Dict[str, Any] = field(default_factory=dict)
    roles: list[str] = field(default_factory=list)
    permissions: Set[str] = field(default_factory=set)
    datasource_grants: Dict[str, Any] = field(default_factory=dict)
    is_admin: bool = False
