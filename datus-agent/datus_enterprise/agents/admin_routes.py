"""Enterprise Agent administration and lifecycle routes."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from datus.api import deps
from datus.api.enterprise.deps import require_platform_active
from datus.api.enterprise.prompt_versions import (
    PromptVersionConflictError,
)
from datus.api.models.base_models import Result
from datus_enterprise.agents.context import AdminAgentsCtx, _require_admin_agents
from datus_enterprise.agents.helpers import (
    _agent_error,
    _audit_agent,
    _audit_agent_best_effort,
    _detail_from_builtin,
    _detail_from_record,
    _ensure_legacy_prompt_version,
    _enterprise_default_agent_id,
    _get_agent_best_effort,
    _optional_str,
    _persist_effective_record,
    _prompt_payload_matches_version,
    _refresh_active_prompt_projection,
    _request_agent_config,
    _summary_from_record,
)
from datus_enterprise.agents.models import (
    AgentPreferenceSummary,
    EnterpriseAgentDetail,
    EnterpriseAgentSummary,
    SetAgentStatusRequest,
    UpdateAgentPreferenceRequest,
    UpsertEnterpriseAgentRequest,
)
from datus_enterprise.agents.registry import (
    agent_audit_summary,
    agent_policy_metadata,
    get_effective_agent_record,
    is_enterprise_builtin_agent_id,
    list_effective_agent_records,
    normalize_agent_payload,
    validate_agent_id,
    validate_agent_status,
    with_agent_policy_metadata,
)

router = APIRouter(prefix="/api/v1", tags=["enterprise-agents"])


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
async def get_admin_agent(agent_id: str, request: Request, ctx: AdminAgentsCtx) -> Result[EnterpriseAgentDetail]:
    """Return one enterprise agent definition for administration."""

    if is_enterprise_builtin_agent_id(agent_id):
        record = await get_effective_agent_record(agent_id)
        agent_config = await _request_agent_config(request, ctx)
        await _audit_agent(ctx, agent_id=agent_id, operation="get_admin_agent", decision="allow")
        return Result(success=True, data=_detail_from_builtin(record or {}, agent_config=agent_config))

    invalid = validate_agent_id(agent_id)
    if invalid is not None:
        await _audit_agent(ctx, agent_id=agent_id, operation="get_admin_agent", decision="deny", reason=invalid)
        return _agent_error("AGENT_ID_INVALID", invalid)
    store = deps.get_enterprise_extensions().agent_store
    try:
        record = await store.get_agent(agent_id)
        active_prompt_version = await store.get_active_prompt_version(agent_id)
    except Exception:
        await _audit_agent(ctx, agent_id=agent_id, operation="get_admin_agent", decision="deny", reason="read failed")
        return _agent_error("AGENT_READ_FAILED", "Agent read failed.")
    if record is None:
        await _audit_agent(ctx, agent_id=agent_id, operation="get_admin_agent", decision="deny", reason="not found")
        return _agent_error("RESOURCE_NOT_FOUND", "Agent not found.")
    agent_config = await _request_agent_config(request, ctx)
    await _audit_agent(
        ctx,
        agent_id=agent_id,
        operation="get_admin_agent",
        decision="allow",
        old_summary=agent_audit_summary(record),
    )
    return Result(
        success=True,
        data=_detail_from_record(
            record,
            active_prompt_version=active_prompt_version,
            agent_config=agent_config,
        ),
    )


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
    request: Request,
    ctx: AdminAgentsCtx,
) -> Result[EnterpriseAgentDetail]:
    """Create or replace one enterprise custom agent definition."""

    invalid = validate_agent_id(agent_id)
    if invalid is not None:
        await _audit_agent(ctx, agent_id=agent_id, operation="upsert_admin_agent", decision="deny", reason=invalid)
        return _agent_error("AGENT_ID_INVALID", invalid)
    agent_config = await _request_agent_config(request, ctx)

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
    active_prompt_version = None
    stored_prompt_versions: list[dict[str, Any]] = []
    if before is not None:
        try:
            active_prompt_version = await _ensure_legacy_prompt_version(store, before)
            if active_prompt_version is None:
                stored_prompt_versions = await store.list_prompt_versions(agent_id)
        except PromptVersionConflictError as exc:
            await _audit_agent(
                ctx,
                agent_id=agent_id,
                operation="upsert_admin_agent",
                decision="deny",
                reason=str(exc),
            )
            raise HTTPException(status_code=409, detail="AGENT_PROMPT_VERSION_CONFLICT") from exc
        except Exception:
            await _audit_agent(
                ctx,
                agent_id=agent_id,
                operation="upsert_admin_agent",
                decision="deny",
                reason="prompt version preflight failed",
            )
            return _agent_error("AGENT_PROMPT_VERSION_READ_FAILED", "Agent prompt version read failed.")
    prompt_change_requires_version = (
        active_prompt_version is not None and not _prompt_payload_matches_version(payload, active_prompt_version)
    ) or (
        active_prompt_version is None
        and bool(stored_prompt_versions)
        and _optional_str(payload.get("prompt_template")) is not None
    )
    if prompt_change_requires_version:
        await _audit_agent(
            ctx,
            agent_id=agent_id,
            operation="upsert_admin_agent",
            decision="deny",
            reason="prompt changes require a new immutable version",
            metadata={
                "active_prompt_version_id": (
                    active_prompt_version["version_id"] if active_prompt_version is not None else None
                ),
                "active_prompt_version": active_prompt_version["version"]
                if active_prompt_version is not None
                else None,
                "active_prompt_sha256": (
                    active_prompt_version["content_sha256"] if active_prompt_version is not None else None
                ),
            },
        )
        raise HTTPException(status_code=409, detail="AGENT_PROMPT_VERSION_REQUIRED")
    try:
        record = await store.put_agent(agent_id=agent_id, payload=payload)
        if active_prompt_version is None:
            active_prompt_version = await _ensure_legacy_prompt_version(store, record)
        else:
            active_prompt_version = await _refresh_active_prompt_projection(
                store,
                agent_id=agent_id,
                active_prompt_version=active_prompt_version,
                actor_user_id=ctx.user_id,
            )
            refreshed = await store.get_agent(agent_id)
            if refreshed is not None:
                record = refreshed
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
    return Result(
        success=True,
        data=_detail_from_record(
            record,
            active_prompt_version=active_prompt_version,
            agent_config=agent_config,
        ),
    )


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
    request: Request,
    ctx: AdminAgentsCtx,
) -> Result[EnterpriseAgentDetail]:
    """Set draft/published/disabled/archived status for one enterprise agent."""

    invalid = (
        None if is_enterprise_builtin_agent_id(agent_id) else validate_agent_id(agent_id)
    ) or validate_agent_status(body.status)
    if invalid is not None:
        await _audit_agent(ctx, agent_id=agent_id, operation="set_admin_agent_status", decision="deny", reason=invalid)
        return _agent_error("AGENT_INVALID", invalid)
    agent_config = await _request_agent_config(request, ctx)
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
    return Result(success=True, data=_detail_from_record(record, agent_config=agent_config))


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
