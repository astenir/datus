"""Current-user enterprise Agent catalog and preference routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from datus.api import deps
from datus.api.enterprise.deps import require_platform_active
from datus.api.models.base_models import Result
from datus.api.models.downstream import AgentUseToolsData
from datus.api.services.agent_service import AgentService
from datus_enterprise.agents.context import AgentListCtx
from datus_enterprise.agents.helpers import (
    _agent_error,
    _detail_from_builtin,
    _detail_from_record,
    _enterprise_default_agent_id,
    _node_class_for_available_agent,
    _optional_str,
    _preference_summary,
    _request_agent_config,
    _require_user_id,
    _summary_from_record,
)
from datus_enterprise.agents.models import (
    AgentPreferenceSummary,
    EnterpriseAgentDetail,
    EnterpriseAgentSummary,
    UpdateAgentPreferenceRequest,
)
from datus_enterprise.agents.registry import (
    can_use_agent,
    get_effective_agent_record,
    is_enterprise_builtin_agent_id,
    list_available_agent_records,
    resolve_effective_default_agent,
)

router = APIRouter(prefix="/api/v1", tags=["enterprise-agents"])


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
async def get_available_agent(
    agent_id: str,
    request: Request,
    ctx: AgentListCtx,
) -> Result[EnterpriseAgentDetail]:
    """Return a published enterprise agent visible to the current user."""

    try:
        record = await get_effective_agent_record(agent_id)
    except Exception:
        return _agent_error("AGENT_READ_FAILED", "Agent read failed.")
    if record is None or record.get("status") != "published" or not can_use_agent(ctx, record):
        return _agent_error("RESOURCE_NOT_FOUND", "Agent not found.")
    agent_config = await _request_agent_config(request, ctx)
    return Result(
        success=True,
        data=(
            _detail_from_builtin(record, agent_config=agent_config)
            if is_enterprise_builtin_agent_id(agent_id)
            else _detail_from_record(record, agent_config=agent_config)
        ),
    )
