"""Shared FastAPI dependencies for enterprise Agent routes."""

from typing import Annotated

from fastapi import Depends

from datus.api import deps
from datus.api.auth.context import AppContext
from datus_enterprise.agents.registry import ADMIN_AGENT_PERMISSION
from datus_enterprise.authorization import require_module

_require_admin_agents = require_module(ADMIN_AGENT_PERMISSION)
AgentListCtx = Annotated[AppContext, Depends(deps.get_request_app_context)]
AdminAgentsCtx = Annotated[AppContext, Depends(_require_admin_agents)]
