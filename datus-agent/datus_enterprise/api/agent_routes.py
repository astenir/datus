"""Compatibility router for the split enterprise Agent API domain."""

from fastapi import APIRouter

from datus.api import deps
from datus_enterprise.agents.admin_routes import (
    delete_admin_agent,
    get_admin_agent,
    get_admin_enterprise_default,
    list_admin_agents,
    set_admin_agent_status,
    set_admin_enterprise_default,
    upsert_admin_agent,
)
from datus_enterprise.agents.admin_routes import (
    router as admin_router,
)
from datus_enterprise.agents.admin_support_routes import (
    get_admin_agent_tool_reference,
    list_admin_agent_acl_roles,
    list_admin_agent_acl_users,
    list_admin_agent_node_types,
    list_admin_agent_tools,
)
from datus_enterprise.agents.admin_support_routes import (
    router as admin_support_router,
)
from datus_enterprise.agents.models import (
    ActivateAgentPromptVersionRequest,
    AgentAcl,
    AgentAclRoleSummary,
    AgentAclUserSummary,
    AgentPolicy,
    AgentPreferenceSummary,
    AgentPromptVersionCollection,
    AgentPromptVersionDetail,
    AgentPromptVersionSummary,
    AgentRuntimePolicy,
    AgentToolPolicy,
    CreateAgentPromptVersionRequest,
    EnterpriseAgentDetail,
    EnterpriseAgentNodeType,
    EnterpriseAgentSummary,
    SetAgentStatusRequest,
    UpdateAgentPreferenceRequest,
    UpdateDefaultUsersRequest,
    UpsertEnterpriseAgentRequest,
)
from datus_enterprise.agents.policy_routes import (
    get_admin_agent_acl,
    get_admin_agent_policy,
    list_admin_agent_default_users,
    set_admin_agent_acl,
    set_admin_agent_default_users,
    set_admin_agent_policy,
)
from datus_enterprise.agents.policy_routes import (
    router as policy_router,
)
from datus_enterprise.agents.prompt_routes import (
    activate_admin_agent_prompt_version,
    create_admin_agent_prompt_version,
    get_admin_agent_prompt_version,
    list_admin_agent_prompt_versions,
)
from datus_enterprise.agents.prompt_routes import (
    router as prompt_router,
)
from datus_enterprise.agents.public_routes import (
    get_available_agent,
    get_available_agent_tools,
    get_my_agent_preference,
    list_available_agents,
    update_my_agent_preference,
)
from datus_enterprise.agents.public_routes import (
    router as public_router,
)

router = APIRouter()
router.include_router(public_router)
router.include_router(admin_support_router)
router.include_router(admin_router)
router.include_router(prompt_router)
router.include_router(policy_router)

__all__ = [
    "ActivateAgentPromptVersionRequest",
    "AgentAcl",
    "AgentAclRoleSummary",
    "AgentAclUserSummary",
    "AgentPolicy",
    "AgentPreferenceSummary",
    "AgentPromptVersionCollection",
    "AgentPromptVersionDetail",
    "AgentPromptVersionSummary",
    "AgentRuntimePolicy",
    "AgentToolPolicy",
    "CreateAgentPromptVersionRequest",
    "EnterpriseAgentDetail",
    "EnterpriseAgentNodeType",
    "EnterpriseAgentSummary",
    "SetAgentStatusRequest",
    "UpdateAgentPreferenceRequest",
    "UpdateDefaultUsersRequest",
    "UpsertEnterpriseAgentRequest",
    "activate_admin_agent_prompt_version",
    "create_admin_agent_prompt_version",
    "delete_admin_agent",
    "deps",
    "get_admin_agent",
    "get_admin_agent_acl",
    "get_admin_agent_policy",
    "get_admin_agent_prompt_version",
    "get_admin_agent_tool_reference",
    "get_admin_enterprise_default",
    "get_available_agent",
    "get_available_agent_tools",
    "get_my_agent_preference",
    "list_admin_agent_acl_roles",
    "list_admin_agent_acl_users",
    "list_admin_agent_default_users",
    "list_admin_agent_node_types",
    "list_admin_agent_prompt_versions",
    "list_admin_agent_tools",
    "list_admin_agents",
    "list_available_agents",
    "router",
    "set_admin_agent_acl",
    "set_admin_agent_default_users",
    "set_admin_agent_policy",
    "set_admin_agent_status",
    "set_admin_enterprise_default",
    "update_my_agent_preference",
    "upsert_admin_agent",
]
