"""Enterprise agent registry and administration routes."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from datus.api import deps
from datus.api.auth.context import AppContext
from datus.api.enterprise.deps import require_platform_active
from datus.api.models.base_models import Result
from datus.api.models.downstream import AgentToolsData, AgentUseToolsData
from datus.api.services.agent_service import VALID_TOOL_METHODS, AgentService
from datus_enterprise.agent_registry import (
    ADMIN_AGENT_PERMISSION,
    ENTERPRISE_AGENT_NODE_CAPABILITIES,
    ENTERPRISE_AGENT_NODE_CLASSES,
    agent_audit_summary,
    agent_policy_metadata,
    builtin_agent_prompt_template,
    builtin_overlay_payload,
    can_use_agent,
    get_effective_agent_record,
    is_enterprise_builtin_agent_id,
    list_available_agent_records,
    list_effective_agent_records,
    normalize_acl,
    normalize_agent_payload,
    public_scoped_context,
    resolve_effective_default_agent,
    validate_agent_id,
    validate_agent_status,
    with_agent_policy_metadata,
)
from datus_enterprise.audit import AuditEvent, audit_decision
from datus_enterprise.authorization import require_module

router = APIRouter(prefix="/api/v1", tags=["enterprise-agents"])

_require_admin_agents = require_module(ADMIN_AGENT_PERMISSION)
AgentListCtx = Annotated[AppContext, Depends(deps.get_request_app_context)]
AdminAgentsCtx = Annotated[AppContext, Depends(_require_admin_agents)]


class AgentAcl(BaseModel):
    """Enterprise agent ACL."""

    visibility: str = Field(default="private", description="private / role / enterprise")
    allowed_roles: list[str] = Field(default_factory=list)
    allowed_user_ids: list[str] = Field(default_factory=list)


class AgentToolPolicy(BaseModel):
    """Server-enforced LLM tool exposure and invocation policy."""

    mode: str = Field(default="inherit", description="inherit / allowlist")
    allowed: list[str] = Field(default_factory=list, max_length=300)
    denied: list[str] = Field(default_factory=list, max_length=300)


class AgentRuntimePolicy(BaseModel):
    """Server-enforced Agent delegation policy."""

    allow_subagent_delegation: bool = False
    allowed_subagents: list[str] = Field(default_factory=list, max_length=100)


class AgentPolicy(BaseModel):
    tool_policy: AgentToolPolicy = Field(default_factory=AgentToolPolicy)
    runtime_policy: AgentRuntimePolicy = Field(default_factory=AgentRuntimePolicy)


class UpsertEnterpriseAgentRequest(BaseModel):
    """Enterprise custom agent definition mutation."""

    name: str | None = Field(default=None, max_length=100)
    description: str | None = Field(default=None, max_length=500)
    node_class: str = Field(default="gen_sql")
    status: str = Field(default="draft")
    datasource_id: str | None = Field(default=None, max_length=128)
    artifact_slug: str | None = Field(default=None, max_length=80)
    prompt_template: str | None = None
    prompt_language: str = Field(default="en", max_length=20)
    prompt_version: str | None = Field(default="1.0", max_length=40)
    tools: list[str] = Field(default_factory=list, max_length=200)
    mcp: list[str] = Field(default_factory=list, max_length=200)
    skills: list[str] = Field(default_factory=list, max_length=200)
    scoped_context: dict[str, Any] = Field(default_factory=dict)
    rules: list[str] = Field(default_factory=list, max_length=100)
    max_turns: int = Field(default=30, ge=1, le=200)
    acl: AgentAcl = Field(default_factory=AgentAcl)
    tool_policy: AgentToolPolicy = Field(default_factory=AgentToolPolicy)
    runtime_policy: AgentRuntimePolicy = Field(default_factory=AgentRuntimePolicy)


class SetAgentStatusRequest(BaseModel):
    """Enterprise agent status mutation."""

    status: str


class EnterpriseAgentSummary(BaseModel):
    """Sanitized enterprise agent summary."""

    agent_id: str
    name: str
    description: str | None = None
    node_class: str
    status: str
    source: str = "enterprise"
    owner_user_id: str | None = None
    datasource_id: str | None = None
    artifact_slug: str | None = None
    acl: AgentAcl | None = None
    tool_policy: AgentToolPolicy = Field(default_factory=AgentToolPolicy)
    runtime_policy: AgentRuntimePolicy = Field(default_factory=AgentRuntimePolicy)
    enterprise_default: bool = False
    created_at: str | None = None
    updated_at: str | None = None


class EnterpriseAgentDetail(EnterpriseAgentSummary):
    """Sanitized enterprise agent detail."""

    prompt_template: str | None = None
    prompt_template_name: str | None = None
    prompt_template_content: str | None = None
    prompt_language: str = "en"
    prompt_version: str | None = "1.0"
    tools: list[str] = Field(default_factory=list)
    mcp: list[str] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    scoped_context: dict[str, Any] = Field(default_factory=dict)
    rules: list[str] = Field(default_factory=list)
    max_turns: int = 30


class EnterpriseAgentNodeType(BaseModel):
    """Supported enterprise Agent node type metadata."""

    node_class: str
    label: str
    description: str
    supports_mcp: bool = False


class AgentPreferenceSummary(BaseModel):
    """Current user's default Agent preference."""

    default_agent_id: str | None = None
    source: str = "none"
    user_default_agent_id: str | None = None
    enterprise_default_agent_id: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


class AgentAclUserSummary(BaseModel):
    """Sanitized enterprise user summary for Agent ACL selectors."""

    user_id: str
    display_name: str | None = None
    email: str | None = None
    department: str | None = None
    title: str | None = None


class AgentAclRoleSummary(BaseModel):
    """Sanitized enterprise role summary for Agent ACL selectors."""

    role_id: str
    name: str
    description: str | None = None


class UpdateAgentPreferenceRequest(BaseModel):
    """Current user's default Agent preference mutation."""

    default_agent_id: str | None = Field(default=None, max_length=80)


class UpdateDefaultUsersRequest(BaseModel):
    user_ids: list[str] = Field(default_factory=list, max_length=500)


@router.get("/agents", response_model=Result[list[EnterpriseAgentSummary]], summary="List Available Agents")
async def list_available_agents(ctx: AgentListCtx) -> Result[list[EnterpriseAgentSummary]]:
    """Return built-in and published enterprise agents available to the current user."""

    try:
        records = await list_available_agent_records(ctx)
    except Exception:
        return _agent_error("AGENT_LIST_FAILED", "Agent list failed.")
    summaries = [_summary_from_record(record) for record in records]
    return Result(success=True, data=sorted(summaries, key=lambda item: (item.source, item.agent_id)))


@router.get(
    "/me/agent-preferences",
    response_model=Result[AgentPreferenceSummary],
    summary="Get Current User Agent Preference",
)
async def get_my_agent_preference(ctx: AgentListCtx) -> Result[AgentPreferenceSummary]:
    """Return the effective default Agent and its policy source."""

    user_id = _require_user_id(ctx)
    try:
        record = await deps.get_enterprise_extensions().user_store.get_chat_preference(user_id)
        effective, source = await resolve_effective_default_agent(ctx)
        enterprise_default = await _enterprise_default_agent_id(ctx)
    except Exception:
        return _agent_error("AGENT_PREFERENCE_READ_FAILED", "Agent preference read failed.")
    return Result(
        success=True,
        data=_preference_summary(
            record,
            default_agent_id=_optional_str(effective.get("agent_id")) if effective else None,
            source=source,
            enterprise_default_agent_id=enterprise_default,
        ),
    )


@router.put(
    "/me/agent-preferences",
    response_model=Result[AgentPreferenceSummary],
    summary="Update Current User Agent Preference",
    dependencies=[
        Depends(require_platform_active(operation="me.agent_preferences.update", resource_type="agent_preference")),
    ],
)
async def update_my_agent_preference(
    body: UpdateAgentPreferenceRequest,
    ctx: AgentListCtx,
) -> Result[AgentPreferenceSummary]:
    """Persist one visible, published Agent as the current user's default."""

    user_id = _require_user_id(ctx)
    default_agent_id = _optional_str(body.default_agent_id)
    if default_agent_id and await _node_class_for_available_agent(default_agent_id, ctx) is None:
        return _agent_error("RESOURCE_NOT_FOUND", "Agent not found.")

    try:
        record = await deps.get_enterprise_extensions().user_store.put_chat_preference(
            user_id=user_id,
            default_agent_id=default_agent_id,
        )
    except Exception:
        return _agent_error("AGENT_PREFERENCE_UPDATE_FAILED", "Agent preference update failed.")
    effective, source = await resolve_effective_default_agent(ctx)
    return Result(
        success=True,
        data=_preference_summary(
            record,
            default_agent_id=_optional_str(effective.get("agent_id")) if effective else None,
            source=source,
            enterprise_default_agent_id=await _enterprise_default_agent_id(ctx),
        ),
    )


@router.get(
    "/agents/{agent_id}/tools",
    response_model=Result[AgentUseToolsData],
    summary="Get Available Agent Tools",
)
async def get_available_agent_tools(agent_id: str, ctx: AgentListCtx) -> Result[AgentUseToolsData]:
    """Return the selectable tool reference for an available built-in or enterprise agent."""

    node_class = await _node_class_for_available_agent(agent_id, ctx)
    if node_class is None:
        return _agent_error("RESOURCE_NOT_FOUND", "Agent not found.")
    return AgentService.get_use_tools(node_class)


@router.get("/agents/{agent_id}", response_model=Result[EnterpriseAgentDetail], summary="Get Available Agent")
async def get_available_agent(agent_id: str, ctx: AgentListCtx) -> Result[EnterpriseAgentDetail]:
    """Return a published enterprise agent visible to the current user."""

    try:
        record = await get_effective_agent_record(agent_id)
    except Exception:
        return _agent_error("AGENT_READ_FAILED", "Agent read failed.")
    if record is None or record.get("status") != "published" or not can_use_agent(ctx, record):
        return _agent_error("RESOURCE_NOT_FOUND", "Agent not found.")
    return Result(
        success=True,
        data=_detail_from_builtin(record) if is_enterprise_builtin_agent_id(agent_id) else _detail_from_record(record),
    )


async def _node_class_for_available_agent(agent_id: str, ctx: AppContext) -> str | None:
    try:
        record = await get_effective_agent_record(agent_id)
    except Exception:
        return None
    if record is None or record.get("status") != "published" or not can_use_agent(ctx, record):
        return None
    return str(record.get("node_class") or "")


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


@router.get("/admin/agents", response_model=Result[list[EnterpriseAgentSummary]], summary="List Admin Agents")
async def list_admin_agents(
    ctx: AdminAgentsCtx,
    status: Annotated[str | None, Query(description="Optional agent status filter.")] = None,
) -> Result[list[EnterpriseAgentSummary]]:
    """Return enterprise agent metadata for administration."""

    status_error = validate_agent_status(status) if status is not None else None
    if status_error is not None:
        await _audit_agent(ctx, operation="list_admin_agents", decision="deny", reason=status_error)
        return _agent_error("AGENT_STATUS_INVALID", status_error)
    try:
        records = await list_effective_agent_records(status=status)
    except Exception:
        await _audit_agent(ctx, operation="list_admin_agents", decision="deny", reason="agent list failed")
        return _agent_error("AGENT_LIST_FAILED", "Agent list failed.")
    summaries = [_summary_from_record(record) for record in records]
    await _audit_agent(ctx, operation="list_admin_agents", decision="allow", metadata={"count": len(summaries)})
    return Result(success=True, data=summaries)


@router.get(
    "/admin/agents/default",
    response_model=Result[AgentPreferenceSummary],
    summary="Get Enterprise Default Agent",
)
async def get_admin_enterprise_default(ctx: AdminAgentsCtx) -> Result[AgentPreferenceSummary]:
    agent_id = await _enterprise_default_agent_id(ctx)
    return Result(
        success=True,
        data=AgentPreferenceSummary(
            default_agent_id=agent_id,
            source="enterprise" if agent_id else "none",
            enterprise_default_agent_id=agent_id,
        ),
    )


@router.put(
    "/admin/agents/default",
    response_model=Result[AgentPreferenceSummary],
    summary="Set Enterprise Default Agent",
    dependencies=[
        Depends(_require_admin_agents),
        Depends(require_platform_active(operation="admin.agents.default.update", resource_type="agent")),
    ],
)
async def set_admin_enterprise_default(
    body: UpdateAgentPreferenceRequest,
    ctx: AdminAgentsCtx,
) -> Result[AgentPreferenceSummary]:
    default_agent_id = _optional_str(body.default_agent_id)
    records = await list_effective_agent_records()
    target = next((record for record in records if record.get("agent_id") == default_agent_id), None)
    if default_agent_id and (target is None or target.get("status") != "published"):
        return _agent_error("RESOURCE_NOT_FOUND", "Published Agent not found.")

    store = deps.get_enterprise_extensions().agent_store
    try:
        for record in records:
            should_default = record.get("agent_id") == default_agent_id
            if agent_policy_metadata(record)["enterprise_default"] == should_default:
                continue
            updated = with_agent_policy_metadata(record, enterprise_default=should_default)
            await _persist_effective_record(store, updated, actor_user_id=ctx.user_id)
    except Exception:
        return _agent_error("AGENT_DEFAULT_UPDATE_FAILED", "Enterprise default Agent update failed.")

    await _audit_agent_best_effort(
        ctx,
        agent_id=default_agent_id,
        operation="set_admin_enterprise_default",
        decision="allow",
    )
    return Result(
        success=True,
        data=AgentPreferenceSummary(
            default_agent_id=default_agent_id,
            source="enterprise" if default_agent_id else "none",
            enterprise_default_agent_id=default_agent_id,
        ),
    )


@router.get("/admin/agents/{agent_id}", response_model=Result[EnterpriseAgentDetail], summary="Get Admin Agent")
async def get_admin_agent(agent_id: str, ctx: AdminAgentsCtx) -> Result[EnterpriseAgentDetail]:
    """Return one enterprise agent definition for administration."""

    if is_enterprise_builtin_agent_id(agent_id):
        record = await get_effective_agent_record(agent_id)
        await _audit_agent(ctx, agent_id=agent_id, operation="get_admin_agent", decision="allow")
        return Result(success=True, data=_detail_from_builtin(record or {}))

    invalid = validate_agent_id(agent_id)
    if invalid is not None:
        await _audit_agent(ctx, agent_id=agent_id, operation="get_admin_agent", decision="deny", reason=invalid)
        return _agent_error("AGENT_ID_INVALID", invalid)
    try:
        record = await deps.get_enterprise_extensions().agent_store.get_agent(agent_id)
    except Exception:
        await _audit_agent(ctx, agent_id=agent_id, operation="get_admin_agent", decision="deny", reason="read failed")
        return _agent_error("AGENT_READ_FAILED", "Agent read failed.")
    if record is None:
        await _audit_agent(ctx, agent_id=agent_id, operation="get_admin_agent", decision="deny", reason="not found")
        return _agent_error("RESOURCE_NOT_FOUND", "Agent not found.")
    await _audit_agent(
        ctx,
        agent_id=agent_id,
        operation="get_admin_agent",
        decision="allow",
        old_summary=agent_audit_summary(record),
    )
    return Result(success=True, data=_detail_from_record(record))


@router.put(
    "/admin/agents/{agent_id}",
    response_model=Result[EnterpriseAgentDetail],
    summary="Upsert Admin Agent",
    dependencies=[
        Depends(_require_admin_agents),
        Depends(require_platform_active(operation="admin.agents.upsert", resource_type="agent")),
    ],
)
async def upsert_admin_agent(
    agent_id: str,
    body: UpsertEnterpriseAgentRequest,
    ctx: AdminAgentsCtx,
) -> Result[EnterpriseAgentDetail]:
    """Create or replace one enterprise custom agent definition."""

    invalid = validate_agent_id(agent_id)
    if invalid is not None:
        await _audit_agent(ctx, agent_id=agent_id, operation="upsert_admin_agent", decision="deny", reason=invalid)
        return _agent_error("AGENT_ID_INVALID", invalid)

    store = deps.get_enterprise_extensions().agent_store
    before = await _get_agent_best_effort(store, agent_id)
    try:
        payload = normalize_agent_payload(
            agent_id,
            body.model_dump(),
            actor_user_id=ctx.user_id,
            existing_record=before,
        )
    except (TypeError, ValueError) as exc:
        await _audit_agent(ctx, agent_id=agent_id, operation="upsert_admin_agent", decision="deny", reason=str(exc))
        return _agent_error("AGENT_INVALID", str(exc))
    try:
        record = await store.put_agent(agent_id=agent_id, payload=payload)
    except Exception:
        await _audit_agent(
            ctx,
            agent_id=agent_id,
            operation="upsert_admin_agent",
            decision="deny",
            reason="agent upsert failed",
            old_summary=agent_audit_summary(before),
        )
        return _agent_error("AGENT_UPSERT_FAILED", "Agent upsert failed.")
    await _audit_agent_best_effort(
        ctx,
        agent_id=agent_id,
        operation="upsert_admin_agent",
        decision="allow",
        old_summary=agent_audit_summary(before),
        new_summary=agent_audit_summary(record),
    )
    return Result(success=True, data=_detail_from_record(record))


@router.put(
    "/admin/agents/{agent_id}/status",
    response_model=Result[EnterpriseAgentDetail],
    summary="Set Admin Agent Status",
    dependencies=[
        Depends(_require_admin_agents),
        Depends(require_platform_active(operation="admin.agents.status.update", resource_type="agent")),
    ],
)
async def set_admin_agent_status(
    agent_id: str,
    body: SetAgentStatusRequest,
    ctx: AdminAgentsCtx,
) -> Result[EnterpriseAgentDetail]:
    """Set draft/published/disabled/archived status for one enterprise agent."""

    invalid = (
        None if is_enterprise_builtin_agent_id(agent_id) else validate_agent_id(agent_id)
    ) or validate_agent_status(body.status)
    if invalid is not None:
        await _audit_agent(ctx, agent_id=agent_id, operation="set_admin_agent_status", decision="deny", reason=invalid)
        return _agent_error("AGENT_INVALID", invalid)
    store = deps.get_enterprise_extensions().agent_store
    before = await _get_agent_best_effort(store, agent_id)
    try:
        if is_enterprise_builtin_agent_id(agent_id):
            effective = await get_effective_agent_record(agent_id)
            record = await _persist_effective_record(
                store,
                {**(effective or {}), "status": body.status},
                actor_user_id=ctx.user_id,
            )
        else:
            record = await store.set_agent_status(agent_id, body.status)
    except Exception:
        await _audit_agent(ctx, agent_id=agent_id, operation="set_admin_agent_status", decision="deny", reason="failed")
        return _agent_error("AGENT_UPDATE_FAILED", "Agent status update failed.")
    if record is None:
        await _audit_agent(
            ctx, agent_id=agent_id, operation="set_admin_agent_status", decision="deny", reason="not found"
        )
        return _agent_error("RESOURCE_NOT_FOUND", "Agent not found.")
    await _audit_agent_best_effort(
        ctx,
        agent_id=agent_id,
        operation="set_admin_agent_status",
        decision="allow",
        old_summary=agent_audit_summary(before),
        new_summary=agent_audit_summary(record),
    )
    return Result(success=True, data=_detail_from_record(record))


@router.get("/admin/agents/{agent_id}/acl", response_model=Result[AgentAcl], summary="Get Admin Agent ACL")
async def get_admin_agent_acl(agent_id: str, ctx: AdminAgentsCtx) -> Result[AgentAcl]:
    """Return ACL metadata for one enterprise agent."""

    record = await get_effective_agent_record(agent_id)
    if record is None:
        await _audit_agent(ctx, agent_id=agent_id, operation="get_admin_agent_acl", decision="deny", reason="not found")
        return _agent_error("RESOURCE_NOT_FOUND", "Agent not found.")
    await _audit_agent(ctx, agent_id=agent_id, operation="get_admin_agent_acl", decision="allow")
    return Result(success=True, data=AgentAcl(**normalize_acl(record.get("acl"))))


@router.put(
    "/admin/agents/{agent_id}/acl",
    response_model=Result[AgentAcl],
    summary="Set Admin Agent ACL",
    dependencies=[
        Depends(_require_admin_agents),
        Depends(require_platform_active(operation="admin.agents.acl.update", resource_type="agent")),
    ],
)
async def set_admin_agent_acl(agent_id: str, body: AgentAcl, ctx: AdminAgentsCtx) -> Result[AgentAcl]:
    """Replace one enterprise agent ACL."""

    try:
        acl = normalize_acl(body.model_dump())
    except ValueError as exc:
        await _audit_agent(ctx, agent_id=agent_id, operation="set_admin_agent_acl", decision="deny", reason=str(exc))
        return _agent_error("AGENT_ACL_INVALID", str(exc))
    store = deps.get_enterprise_extensions().agent_store
    before = await _get_agent_best_effort(store, agent_id)
    try:
        if is_enterprise_builtin_agent_id(agent_id):
            effective = await get_effective_agent_record(agent_id)
            record = await _persist_effective_record(
                store,
                {**(effective or {}), "acl": acl},
                actor_user_id=ctx.user_id,
            )
        else:
            record = await store.put_agent_acl(agent_id, acl)
    except Exception:
        await _audit_agent(ctx, agent_id=agent_id, operation="set_admin_agent_acl", decision="deny", reason="failed")
        return _agent_error("AGENT_ACL_UPDATE_FAILED", "Agent ACL update failed.")
    if record is None:
        await _audit_agent(ctx, agent_id=agent_id, operation="set_admin_agent_acl", decision="deny", reason="not found")
        return _agent_error("RESOURCE_NOT_FOUND", "Agent not found.")
    await _audit_agent_best_effort(
        ctx,
        agent_id=agent_id,
        operation="set_admin_agent_acl",
        decision="allow",
        old_summary=agent_audit_summary(before),
        new_summary=agent_audit_summary(record),
    )
    return Result(success=True, data=AgentAcl(**normalize_acl(record.get("acl"))))


@router.get(
    "/admin/agents/{agent_id}/policy",
    response_model=Result[AgentPolicy],
    summary="Get Admin Agent Policy",
)
async def get_admin_agent_policy(agent_id: str, ctx: AdminAgentsCtx) -> Result[AgentPolicy]:
    record = await get_effective_agent_record(agent_id)
    if record is None:
        return _agent_error("RESOURCE_NOT_FOUND", "Agent not found.")
    metadata = agent_policy_metadata(record)
    return Result(success=True, data=AgentPolicy(**metadata))


@router.put(
    "/admin/agents/{agent_id}/policy",
    response_model=Result[AgentPolicy],
    summary="Set Admin Agent Policy",
    dependencies=[
        Depends(_require_admin_agents),
        Depends(require_platform_active(operation="admin.agents.policy.update", resource_type="agent")),
    ],
)
async def set_admin_agent_policy(agent_id: str, body: AgentPolicy, ctx: AdminAgentsCtx) -> Result[AgentPolicy]:
    record = await get_effective_agent_record(agent_id)
    if record is None:
        return _agent_error("RESOURCE_NOT_FOUND", "Agent not found.")
    try:
        updated = with_agent_policy_metadata(
            record,
            tool_policy=body.tool_policy.model_dump(),
            runtime_policy=body.runtime_policy.model_dump(),
        )
        persisted = await _persist_effective_record(
            deps.get_enterprise_extensions().agent_store,
            updated,
            actor_user_id=ctx.user_id,
        )
    except (TypeError, ValueError):
        return _agent_error("AGENT_POLICY_INVALID", "Agent policy is invalid.")
    except Exception:
        return _agent_error("AGENT_POLICY_UPDATE_FAILED", "Agent policy update failed.")
    await _audit_agent_best_effort(
        ctx,
        agent_id=agent_id,
        operation="set_admin_agent_policy",
        decision="allow",
        new_summary=agent_audit_summary(persisted),
    )
    return Result(success=True, data=AgentPolicy(**agent_policy_metadata(persisted)))


@router.get(
    "/admin/agents/{agent_id}/default-users",
    response_model=Result[list[str]],
    summary="List Agent Default Users",
)
async def list_admin_agent_default_users(agent_id: str, ctx: AdminAgentsCtx) -> Result[list[str]]:
    record = await get_effective_agent_record(agent_id)
    if record is None:
        return _agent_error("RESOURCE_NOT_FOUND", "Agent not found.")
    users = await deps.get_enterprise_extensions().user_store.list_users(enabled=True)
    selected = []
    for user in users:
        user_id = str(user.get("user_id") or "")
        preference = await deps.get_enterprise_extensions().user_store.get_chat_preference(user_id)
        if preference.get("default_agent_id") == agent_id:
            selected.append(user_id)
    return Result(success=True, data=sorted(selected))


@router.put(
    "/admin/agents/{agent_id}/default-users",
    response_model=Result[list[str]],
    summary="Set Agent Default Users",
    dependencies=[
        Depends(_require_admin_agents),
        Depends(require_platform_active(operation="admin.agents.default_users.update", resource_type="agent")),
    ],
)
async def set_admin_agent_default_users(
    agent_id: str,
    body: UpdateDefaultUsersRequest,
    ctx: AdminAgentsCtx,
) -> Result[list[str]]:
    record = await get_effective_agent_record(agent_id)
    if record is None:
        return _agent_error("RESOURCE_NOT_FOUND", "Agent not found.")
    extensions = deps.get_enterprise_extensions()
    users = await extensions.user_store.list_users(enabled=True)
    users_by_id = {str(user.get("user_id")): user for user in users}
    selected = sorted({user_id.strip() for user_id in body.user_ids if user_id.strip()})
    if record.get("status") != "published" and selected:
        return _agent_error(
            "AGENT_DEFAULT_REQUIRES_PUBLISHED",
            "Default users require a published Agent.",
        )
    if any(user_id not in users_by_id for user_id in selected):
        return _agent_error("AGENT_DEFAULT_USER_INVALID", "One or more users are unavailable.")
    for user_id in selected:
        target_ctx = await _target_user_context(user_id)
        if not can_use_agent(target_ctx, record):
            return _agent_error("AGENT_FORBIDDEN", f"User '{user_id}' cannot access this Agent.")
    try:
        for user_id in users_by_id:
            preference = await extensions.user_store.get_chat_preference(user_id)
            is_selected = user_id in selected
            if is_selected:
                await extensions.user_store.put_chat_preference(user_id=user_id, default_agent_id=agent_id)
            elif preference.get("default_agent_id") == agent_id:
                await extensions.user_store.put_chat_preference(user_id=user_id, default_agent_id=None)
    except Exception:
        return _agent_error("AGENT_DEFAULT_USERS_UPDATE_FAILED", "Default user assignment failed.")
    await _audit_agent_best_effort(
        ctx,
        agent_id=agent_id,
        operation="set_admin_agent_default_users",
        decision="allow",
        metadata={"user_count": len(selected)},
    )
    return Result(success=True, data=selected)


@router.delete(
    "/admin/agents/{agent_id}",
    response_model=Result[dict[str, bool]],
    summary="Delete Admin Agent",
    dependencies=[
        Depends(_require_admin_agents),
        Depends(require_platform_active(operation="admin.agents.delete", resource_type="agent")),
    ],
)
async def delete_admin_agent(agent_id: str, ctx: AdminAgentsCtx) -> Result[dict[str, bool]]:
    """Delete one enterprise custom agent definition."""

    if is_enterprise_builtin_agent_id(agent_id):
        return _agent_error("AGENT_BUILTIN_IMMUTABLE", "Built-in Agent definitions cannot be deleted.")
    store = deps.get_enterprise_extensions().agent_store
    before = await _get_agent_best_effort(store, agent_id)
    try:
        deleted = await store.delete_agent(agent_id)
    except Exception:
        await _audit_agent(ctx, agent_id=agent_id, operation="delete_admin_agent", decision="deny", reason="failed")
        return _agent_error("AGENT_DELETE_FAILED", "Agent delete failed.")
    if not deleted:
        await _audit_agent(ctx, agent_id=agent_id, operation="delete_admin_agent", decision="deny", reason="not found")
        return _agent_error("RESOURCE_NOT_FOUND", "Agent not found.")
    await _audit_agent_best_effort(
        ctx,
        agent_id=agent_id,
        operation="delete_admin_agent",
        decision="allow",
        old_summary=agent_audit_summary(before),
    )
    return Result(success=True, data={"deleted": True})


def _summary_from_record(record: dict[str, Any]) -> EnterpriseAgentSummary:
    policy = agent_policy_metadata(record)
    return EnterpriseAgentSummary(
        agent_id=str(record["agent_id"]),
        name=str(record.get("name") or record["agent_id"]),
        description=record.get("description"),
        node_class=str(record.get("node_class") or "gen_sql"),
        status=str(record.get("status") or "draft"),
        source="builtin" if is_enterprise_builtin_agent_id(str(record["agent_id"])) else "enterprise",
        owner_user_id=record.get("owner_user_id"),
        datasource_id=record.get("datasource_id"),
        artifact_slug=record.get("artifact_slug"),
        acl=AgentAcl(**normalize_acl(record.get("acl"))),
        tool_policy=AgentToolPolicy(**policy["tool_policy"]),
        runtime_policy=AgentRuntimePolicy(**policy["runtime_policy"]),
        enterprise_default=policy["enterprise_default"],
        created_at=record.get("created_at"),
        updated_at=record.get("updated_at"),
    )


def _detail_from_record(record: dict[str, Any]) -> EnterpriseAgentDetail:
    summary = _summary_from_record(record).model_dump()
    return EnterpriseAgentDetail(
        **summary,
        prompt_template=record.get("prompt_template"),
        prompt_language=str(record.get("prompt_language") or "en"),
        prompt_version=record.get("prompt_version") or "1.0",
        tools=list(record.get("tools") or []),
        mcp=list(record.get("mcp") or []),
        skills=list(record.get("skills") or []),
        scoped_context=public_scoped_context(record),
        rules=list(record.get("rules") or []),
        max_turns=int(record.get("max_turns") or 30),
    )


def _detail_from_builtin(record: dict[str, Any]) -> EnterpriseAgentDetail:
    summary = _summary_from_record(record).model_dump()
    return EnterpriseAgentDetail(
        **summary,
        **builtin_agent_prompt_template(str(record["agent_id"])),
    )


def _agent_acl_user_summary(record: dict[str, Any]) -> AgentAclUserSummary:
    return AgentAclUserSummary(
        user_id=str(record["user_id"]),
        display_name=_optional_str(record.get("display_name")),
        email=_optional_str(record.get("email")),
        department=_optional_str(record.get("department")),
        title=_optional_str(record.get("title")),
    )


def _agent_acl_role_summary(record: dict[str, Any]) -> AgentAclRoleSummary:
    return AgentAclRoleSummary(
        role_id=str(record["role_id"]),
        name=str(record.get("name") or record["role_id"]),
        description=_optional_str(record.get("description")),
    )


def _matches_acl_directory_query(query: str, *values: Any) -> bool:
    normalized_query = query.strip().casefold()
    if not normalized_query:
        return True
    return any(normalized_query in str(value).casefold() for value in values if value is not None)


def _preference_summary(
    record: dict[str, Any],
    *,
    default_agent_id: str | None,
    source: str,
    enterprise_default_agent_id: str | None,
) -> AgentPreferenceSummary:
    return AgentPreferenceSummary(
        default_agent_id=default_agent_id,
        source=source,
        user_default_agent_id=_optional_str(record.get("default_agent_id")),
        enterprise_default_agent_id=enterprise_default_agent_id,
        created_at=_optional_str(record.get("created_at")),
        updated_at=_optional_str(record.get("updated_at")),
    )


def _require_user_id(ctx: AppContext) -> str:
    user_id = _optional_str(ctx.user_id)
    if user_id is None:
        raise HTTPException(status_code=401, detail="AUTH_REQUIRED")
    return user_id


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _agent_error(code: str, message: str):
    return Result(success=False, errorCode=code, errorMessage=message)


async def _get_agent_best_effort(store, agent_id: str) -> dict[str, Any] | None:
    try:
        return await store.get_agent(agent_id)
    except Exception:
        return None


async def _enterprise_default_agent_id(ctx: AppContext) -> str | None:
    records = await list_available_agent_records(ctx)
    defaults = [str(record["agent_id"]) for record in records if agent_policy_metadata(record)["enterprise_default"]]
    return sorted(defaults)[0] if defaults else None


async def _persist_effective_record(store, record: dict[str, Any], *, actor_user_id: str | None) -> dict[str, Any]:
    agent_id = str(record["agent_id"])
    if is_enterprise_builtin_agent_id(agent_id):
        policy = agent_policy_metadata(record)
        payload = builtin_overlay_payload(
            agent_id,
            status=str(record.get("status") or "disabled"),
            acl=normalize_acl(record.get("acl")),
            tool_policy=policy["tool_policy"],
            runtime_policy=policy["runtime_policy"],
            enterprise_default=policy["enterprise_default"],
            actor_user_id=actor_user_id,
        )
    else:
        payload = dict(record)
    return await store.put_agent(agent_id=agent_id, payload=payload)


async def _target_user_context(user_id: str) -> AppContext:
    extensions = deps.get_enterprise_extensions()
    role_ids = await extensions.role_store.list_user_roles(user_id)
    return AppContext(
        user_id=user_id,
        roles=role_ids,
        permissions={"__agent_acl_only__"},
        principal={"permissions": ["__agent_acl_only__"]},
    )


async def _audit_agent(
    ctx: AppContext,
    *,
    operation: str,
    decision: str,
    agent_id: str | None = None,
    reason: str | None = None,
    old_summary: dict[str, Any] | None = None,
    new_summary: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    event_metadata = {"operation": operation}
    if old_summary is not None:
        event_metadata["old"] = old_summary
    if new_summary is not None:
        event_metadata["new"] = new_summary
    if metadata:
        event_metadata.update(metadata)
    await audit_decision(
        ctx,
        AuditEvent(
            action=ADMIN_AGENT_PERMISSION,
            resource_type="agent",
            resource_id=agent_id,
            decision=decision,
            reason=reason,
            metadata=event_metadata,
        ),
    )


async def _audit_agent_best_effort(ctx: AppContext, **kwargs: Any) -> None:
    try:
        await _audit_agent(ctx, **kwargs)
    except Exception:
        return None
