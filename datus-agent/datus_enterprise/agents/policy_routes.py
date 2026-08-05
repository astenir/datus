"""Enterprise Agent ACL, policy, and default-user routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from datus.api import deps
from datus.api.enterprise.deps import require_platform_active
from datus.api.models.base_models import Result
from datus_enterprise.agents.context import AdminAgentsCtx, _require_admin_agents
from datus_enterprise.agents.helpers import (
    _agent_error,
    _audit_agent,
    _audit_agent_best_effort,
    _get_agent_best_effort,
    _persist_effective_record,
    _target_user_context,
)
from datus_enterprise.agents.models import (
    AgentAcl,
    AgentPolicy,
    UpdateDefaultUsersRequest,
)
from datus_enterprise.agents.registry import (
    agent_audit_summary,
    agent_policy_metadata,
    can_use_agent,
    get_effective_agent_record,
    is_enterprise_builtin_agent_id,
    normalize_acl,
    with_agent_policy_metadata,
)

router = APIRouter(prefix="/api/v1", tags=["enterprise-agents"])


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
