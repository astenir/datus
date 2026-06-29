"""Enterprise agent registry and administration routes."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from datus.api import deps
from datus.api.auth.context import AppContext
from datus.api.constants import BUILTIN_SUBAGENTS
from datus.api.enterprise.deps import require_platform_active
from datus.api.models.agent_models import AgentToolsData, AgentUseToolsData
from datus.api.models.base_models import Result
from datus.api.services.agent_service import VALID_TOOL_METHODS, AgentService
from datus_enterprise.agent_registry import (
    ADMIN_AGENT_PERMISSION,
    ENTERPRISE_AGENT_NODE_CLASSES,
    agent_audit_summary,
    builtin_agent_summaries_for_context,
    can_use_agent,
    can_use_node_class,
    normalize_acl,
    normalize_agent_payload,
    validate_agent_id,
    validate_agent_status,
)
from datus_enterprise.audit import AuditEvent, audit_decision
from datus_enterprise.authorization import require_module

router = APIRouter(prefix="/api/v1", tags=["enterprise-agents"])

_require_chat = require_module("module.chat")
_require_admin_agents = require_module(ADMIN_AGENT_PERMISSION)
AgentListCtx = Annotated[AppContext, Depends(_require_chat)]
AdminAgentsCtx = Annotated[AppContext, Depends(_require_admin_agents)]


class AgentAcl(BaseModel):
    """Enterprise agent ACL."""

    visibility: str = Field(default="private", description="private / role / enterprise")
    allowed_roles: list[str] = Field(default_factory=list)
    allowed_user_ids: list[str] = Field(default_factory=list)


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
    created_at: str | None = None
    updated_at: str | None = None


class EnterpriseAgentDetail(EnterpriseAgentSummary):
    """Sanitized enterprise agent detail."""

    prompt_template: str | None = None
    prompt_language: str = "en"
    prompt_version: str | None = "1.0"
    tools: list[str] = Field(default_factory=list)
    mcp: list[str] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    scoped_context: dict[str, Any] = Field(default_factory=dict)
    rules: list[str] = Field(default_factory=list)
    max_turns: int = 30


@router.get("/agents", response_model=Result[list[EnterpriseAgentSummary]], summary="List Available Agents")
async def list_available_agents(ctx: AgentListCtx) -> Result[list[EnterpriseAgentSummary]]:
    """Return built-in and published enterprise agents available to the current user."""

    summaries = [EnterpriseAgentSummary(**item) for item in builtin_agent_summaries_for_context(ctx)]
    try:
        records = await deps.get_enterprise_extensions().agent_store.list_agents(status="published")
    except Exception:
        return _agent_error("AGENT_LIST_FAILED", "Agent list failed.")
    summaries.extend(
        _summary_from_record(record)
        for record in records
        if can_use_agent(ctx, record) and can_use_node_class(ctx, str(record.get("node_class") or ""))
    )
    return Result(success=True, data=sorted(summaries, key=lambda item: (item.source, item.agent_id)))


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
        record = await deps.get_enterprise_extensions().agent_store.get_agent(agent_id)
    except Exception:
        return _agent_error("AGENT_READ_FAILED", "Agent read failed.")
    if (
        record is None
        or record.get("status") != "published"
        or not can_use_agent(ctx, record)
        or not can_use_node_class(ctx, str(record.get("node_class") or ""))
    ):
        return _agent_error("RESOURCE_NOT_FOUND", "Agent not found.")
    return Result(success=True, data=_detail_from_record(record))


async def _node_class_for_available_agent(agent_id: str, ctx: AppContext) -> str | None:
    if agent_id in BUILTIN_SUBAGENTS:
        return agent_id if can_use_node_class(ctx, agent_id) else None
    try:
        record = await deps.get_enterprise_extensions().agent_store.get_agent(agent_id)
    except Exception:
        return None
    if (
        record is None
        or record.get("status") != "published"
        or not can_use_agent(ctx, record)
        or not can_use_node_class(ctx, str(record.get("node_class") or ""))
    ):
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
        records = await deps.get_enterprise_extensions().agent_store.list_agents(status=status)
    except Exception:
        await _audit_agent(ctx, operation="list_admin_agents", decision="deny", reason="agent list failed")
        return _agent_error("AGENT_LIST_FAILED", "Agent list failed.")
    await _audit_agent(ctx, operation="list_admin_agents", decision="allow", metadata={"count": len(records)})
    return Result(success=True, data=[_summary_from_record(record) for record in records])


@router.get("/admin/agents/{agent_id}", response_model=Result[EnterpriseAgentDetail], summary="Get Admin Agent")
async def get_admin_agent(agent_id: str, ctx: AdminAgentsCtx) -> Result[EnterpriseAgentDetail]:
    """Return one enterprise agent definition for administration."""

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
        payload = normalize_agent_payload(agent_id, body.model_dump(), actor_user_id=ctx.user_id)
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

    invalid = validate_agent_id(agent_id) or validate_agent_status(body.status)
    if invalid is not None:
        await _audit_agent(ctx, agent_id=agent_id, operation="set_admin_agent_status", decision="deny", reason=invalid)
        return _agent_error("AGENT_INVALID", invalid)
    store = deps.get_enterprise_extensions().agent_store
    before = await _get_agent_best_effort(store, agent_id)
    try:
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

    record = await deps.get_enterprise_extensions().agent_store.get_agent(agent_id)
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
    return EnterpriseAgentSummary(
        agent_id=str(record["agent_id"]),
        name=str(record.get("name") or record["agent_id"]),
        description=record.get("description"),
        node_class=str(record.get("node_class") or "gen_sql"),
        status=str(record.get("status") or "draft"),
        owner_user_id=record.get("owner_user_id"),
        datasource_id=record.get("datasource_id"),
        artifact_slug=record.get("artifact_slug"),
        acl=AgentAcl(**normalize_acl(record.get("acl"))),
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
        scoped_context=dict(record.get("scoped_context") or {}),
        rules=list(record.get("rules") or []),
        max_turns=int(record.get("max_turns") or 30),
    )


def _agent_error(code: str, message: str):
    return Result(success=False, errorCode=code, errorMessage=message)


async def _get_agent_best_effort(store, agent_id: str) -> dict[str, Any] | None:
    try:
        return await store.get_agent(agent_id)
    except Exception:
        return None


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
