"""Request-level AgentConfig projection for datasource-scoped execution."""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from datus.api.auth.context import AppContext
from datus.configuration.agent_config import AgentConfig
from datus.utils.exceptions import DatusException, ErrorCode


@dataclass(frozen=True)
class ConfigProjection:
    """Projected request config and derived principal."""

    agent_config: AgentConfig
    principal: Dict[str, Any] = field(default_factory=dict)


async def project_request_config(
    ctx: AppContext,
    agent_config: AgentConfig,
    *,
    requested_datasource: Optional[str] = None,
) -> ConfigProjection:
    """Clone ``agent_config`` and apply request-scoped datasource selection.

    This helper does not write ``.datus/config.yml`` and does not mutate the
    cached ``DatusService.agent_config``. The default implementation performs
    only shape-safe local projection; production enterprise deployments should
    layer datasource grants into this function.
    """

    projected = copy.deepcopy(agent_config)
    principal = dict(ctx.principal or {})
    if requested_datasource:
        if requested_datasource not in projected.services.datasources:
            raise DatusException(
                ErrorCode.COMMON_FIELD_INVALID,
                message=f"Datasource '{requested_datasource}' not found in services.datasources.",
            )
        projected.current_datasource = requested_datasource
        principal.setdefault("datasource", requested_datasource)
    projected.principal = principal
    return ConfigProjection(agent_config=projected, principal=principal)
