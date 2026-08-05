"""Enterprise Agent administration support-data routes."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query

from datus.api import deps
from datus.api.models.base_models import Result
from datus.api.models.downstream import AgentToolsData, AgentUseToolsData
from datus.api.services.agent_service import VALID_TOOL_METHODS, AgentService
from datus_enterprise.agents.context import AdminAgentsCtx
from datus_enterprise.agents.helpers import (
    _agent_acl_role_summary,
    _agent_acl_user_summary,
    _agent_error,
    _audit_agent_best_effort,
    _matches_acl_directory_query,
)
from datus_enterprise.agents.models import (
    AgentAclRoleSummary,
    AgentAclUserSummary,
    EnterpriseAgentNodeType,
)
from datus_enterprise.agents.registry import (
    ENTERPRISE_AGENT_NODE_CAPABILITIES,
    ENTERPRISE_AGENT_NODE_CLASSES,
)

router = APIRouter(prefix="/api/v1", tags=["enterprise-agents"])


@router.get(
    "/admin/agents/tools",
    response_model=Result[AgentToolsData],
    summary="List Admin Agent Tool Catalog",
)
async def list_admin_agent_tools(ctx: AdminAgentsCtx) -> Result[AgentToolsData]:
    """Return all valid tool categories and methods for enterprise agent administration."""

    return Result(
        success=True,
        data=AgentToolsData(tools={category: sorted(methods) for category, methods in VALID_TOOL_METHODS.items()}),
    )


@router.get(
    "/admin/agents/tool-reference",
    response_model=Result[AgentUseToolsData],
    summary="Get Admin Agent Tool Reference",
)
async def get_admin_agent_tool_reference(
    ctx: AdminAgentsCtx,
    node_class: Annotated[str, Query(description="Agent node_class, e.g. gen_sql or ask_report.")] = "gen_sql",
) -> Result[AgentUseToolsData]:
    """Return default tools and selectable categories for one enterprise agent node class."""

    if node_class not in ENTERPRISE_AGENT_NODE_CLASSES:
        return _agent_error(
            "INVALID_AGENT_TYPE",
            f"Unknown node_class '{node_class}'. Must be one of: {', '.join(sorted(ENTERPRISE_AGENT_NODE_CLASSES))}",
        )
    return AgentService.get_use_tools(node_class)


@router.get(
    "/admin/agents/node-types",
    response_model=Result[list[EnterpriseAgentNodeType]],
    summary="List Supported Custom Agent Node Types",
)
async def list_admin_agent_node_types(ctx: AdminAgentsCtx) -> Result[list[EnterpriseAgentNodeType]]:
    """Return node classes that enterprise administrators may use for custom Agents."""

    return Result(
        success=True,
        data=[
            EnterpriseAgentNodeType(
                node_class=capability.node_class,
                label=capability.label,
                description=capability.description,
                supports_mcp=capability.supports_mcp,
            )
            for capability in ENTERPRISE_AGENT_NODE_CAPABILITIES
        ],
    )


@router.get(
    "/admin/agents/acl-users",
    response_model=Result[list[AgentAclUserSummary]],
    summary="List Agent ACL Users",
)
async def list_admin_agent_acl_users(
    ctx: AdminAgentsCtx,
    query: Annotated[str, Query(max_length=200, description="Case-insensitive user search text.")] = "",
    limit: Annotated[int, Query(ge=1, le=100)] = 100,
) -> Result[list[AgentAclUserSummary]]:
    """Return a sanitized enabled-user directory for Agent ACL selectors."""

    try:
        records = await deps.get_enterprise_extensions().user_store.list_users(enabled=True)
    except Exception:
        await _audit_agent_best_effort(
            ctx,
            operation="list_admin_agent_acl_users",
            decision="deny",
            reason="user directory query failed",
            metadata={"query_present": bool(query.strip())},
        )
        return _agent_error("AGENT_ACL_USER_DIRECTORY_FAILED", "Agent ACL user directory query failed.")

    users = [
        _agent_acl_user_summary(record)
        for record in records
        if _matches_acl_directory_query(
            query,
            record.get("user_id"),
            record.get("display_name"),
            record.get("email"),
            record.get("department"),
            record.get("title"),
        )
    ][:limit]
    await _audit_agent_best_effort(
        ctx,
        operation="list_admin_agent_acl_users",
        decision="allow",
        metadata={"query_present": bool(query.strip()), "count": len(users)},
    )
    return Result(success=True, data=users)


@router.get(
    "/admin/agents/acl-roles",
    response_model=Result[list[AgentAclRoleSummary]],
    summary="List Agent ACL Roles",
)
async def list_admin_agent_acl_roles(
    ctx: AdminAgentsCtx,
    query: Annotated[str, Query(max_length=200, description="Case-insensitive role search text.")] = "",
    limit: Annotated[int, Query(ge=1, le=100)] = 100,
) -> Result[list[AgentAclRoleSummary]]:
    """Return a sanitized role directory for Agent ACL selectors."""

    try:
        records = await deps.get_enterprise_extensions().role_store.list_roles()
    except Exception:
        await _audit_agent_best_effort(
            ctx,
            operation="list_admin_agent_acl_roles",
            decision="deny",
            reason="role directory query failed",
            metadata={"query_present": bool(query.strip())},
        )
        return _agent_error("AGENT_ACL_ROLE_DIRECTORY_FAILED", "Agent ACL role directory query failed.")

    roles = [
        _agent_acl_role_summary(record)
        for record in records
        if _matches_acl_directory_query(
            query,
            record.get("role_id"),
            record.get("name"),
            record.get("description"),
        )
    ][:limit]
    await _audit_agent_best_effort(
        ctx,
        operation="list_admin_agent_acl_roles",
        decision="allow",
        metadata={"query_present": bool(query.strip()), "count": len(roles)},
    )
    return Result(success=True, data=roles)
