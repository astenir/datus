"""Enterprise Agent immutable Prompt version routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from datus.api import deps
from datus.api.enterprise.deps import require_platform_active
from datus.api.enterprise.prompt_versions import (
    PromptVersionAgentNotFoundError,
    PromptVersionConflictError,
    PromptVersionNotFoundError,
)
from datus.api.models.base_models import Result
from datus_enterprise.agents.context import AdminAgentsCtx, _require_admin_agents
from datus_enterprise.agents.helpers import (
    _agent_error,
    _audit_agent,
    _audit_agent_best_effort,
    _ensure_legacy_prompt_version,
    _legacy_prompt_version_record,
    _prompt_version_detail,
    _prompt_version_summary,
    _require_custom_agent_record,
)
from datus_enterprise.agents.models import (
    ActivateAgentPromptVersionRequest,
    AgentPromptVersionCollection,
    AgentPromptVersionDetail,
    CreateAgentPromptVersionRequest,
)

router = APIRouter(prefix="/api/v1", tags=["enterprise-agents"])


@router.get(
    "/admin/agents/{agent_id}/prompt-versions",
    response_model=Result[AgentPromptVersionCollection],
    summary="List Admin Agent Prompt Versions",
)
async def list_admin_agent_prompt_versions(
    agent_id: str,
    ctx: AdminAgentsCtx,
) -> Result[AgentPromptVersionCollection]:
    """Return immutable prompt history without mutating legacy records."""

    record = await _require_custom_agent_record(agent_id, ctx, operation="list_admin_agent_prompt_versions")
    store = deps.get_enterprise_extensions().agent_store
    try:
        versions = await store.list_prompt_versions(agent_id)
    except Exception:
        await _audit_agent(
            ctx,
            agent_id=agent_id,
            operation="list_admin_agent_prompt_versions",
            decision="deny",
            reason="prompt version list failed",
        )
        return _agent_error("AGENT_PROMPT_VERSION_LIST_FAILED", "Agent prompt version list failed.")
    if not versions:
        legacy = _legacy_prompt_version_record(record)
        versions = [legacy] if legacy is not None else []
    active_version_id = next(
        (str(version["version_id"]) for version in versions if bool(version.get("active"))),
        None,
    )
    await _audit_agent(
        ctx,
        agent_id=agent_id,
        operation="list_admin_agent_prompt_versions",
        decision="allow",
        metadata={"count": len(versions), "active_prompt_version_id": active_version_id},
    )
    return Result(
        success=True,
        data=AgentPromptVersionCollection(
            active_version_id=active_version_id,
            versions=[_prompt_version_summary(version) for version in versions],
        ),
    )


@router.get(
    "/admin/agents/{agent_id}/prompt-versions/{version_id}",
    response_model=Result[AgentPromptVersionDetail],
    summary="Get Admin Agent Prompt Version",
)
async def get_admin_agent_prompt_version(
    agent_id: str,
    version_id: str,
    ctx: AdminAgentsCtx,
) -> Result[AgentPromptVersionDetail]:
    """Return one authorized prompt body scoped to its owning Agent."""

    record = await _require_custom_agent_record(agent_id, ctx, operation="get_admin_agent_prompt_version")
    store = deps.get_enterprise_extensions().agent_store
    try:
        version = await store.get_prompt_version(agent_id, version_id)
    except Exception:
        await _audit_agent(
            ctx,
            agent_id=agent_id,
            operation="get_admin_agent_prompt_version",
            decision="deny",
            reason="prompt version read failed",
        )
        return _agent_error("AGENT_PROMPT_VERSION_READ_FAILED", "Agent prompt version read failed.")
    if version is None:
        legacy = _legacy_prompt_version_record(record)
        version = legacy if legacy is not None and legacy["version_id"] == version_id else None
    if version is None:
        await _audit_agent(
            ctx,
            agent_id=agent_id,
            operation="get_admin_agent_prompt_version",
            decision="deny",
            reason="not found",
        )
        raise HTTPException(status_code=404, detail="RESOURCE_NOT_FOUND")
    await _audit_agent(
        ctx,
        agent_id=agent_id,
        operation="get_admin_agent_prompt_version",
        decision="allow",
        metadata={
            "prompt_version_id": version["version_id"],
            "prompt_version": version["version"],
            "prompt_sha256": version["content_sha256"],
        },
    )
    return Result(success=True, data=_prompt_version_detail(version))


@router.post(
    "/admin/agents/{agent_id}/prompt-versions",
    response_model=Result[AgentPromptVersionDetail],
    summary="Create Admin Agent Prompt Version",
    dependencies=[
        Depends(_require_admin_agents),
        Depends(require_platform_active(operation="admin.agents.prompt_versions.create", resource_type="agent")),
    ],
)
async def create_admin_agent_prompt_version(
    agent_id: str,
    body: CreateAgentPromptVersionRequest,
    ctx: AdminAgentsCtx,
) -> Result[AgentPromptVersionDetail]:
    """Create one immutable custom Prompt version and optionally activate it."""

    record = await _require_custom_agent_record(agent_id, ctx, operation="create_admin_agent_prompt_version")
    store = deps.get_enterprise_extensions().agent_store
    try:
        active = await _ensure_legacy_prompt_version(store, record)
        based_on_version_id = body.based_on_version_id
        legacy = _legacy_prompt_version_record(record)
        if legacy is not None and based_on_version_id == legacy["version_id"]:
            based_on_version_id = str(active["version_id"]) if active is not None else None
        created = await store.create_prompt_version(
            agent_id=agent_id,
            version=body.version,
            prompt_template=body.prompt_template,
            prompt_language=body.prompt_language,
            change_note=body.change_note,
            based_on_version_id=based_on_version_id,
            created_by=ctx.user_id,
        )
        if body.activate:
            created = await store.activate_prompt_version(
                agent_id=agent_id,
                version_id=str(created["version_id"]),
                expected_active_version_id=(str(active["version_id"]) if active is not None else None),
                activated_by=ctx.user_id,
            )
    except PromptVersionConflictError as exc:
        await _audit_agent(
            ctx,
            agent_id=agent_id,
            operation="create_admin_agent_prompt_version",
            decision="deny",
            reason=str(exc),
        )
        raise HTTPException(status_code=409, detail="AGENT_PROMPT_VERSION_CONFLICT") from exc
    except (PromptVersionNotFoundError, PromptVersionAgentNotFoundError) as exc:
        await _audit_agent(
            ctx,
            agent_id=agent_id,
            operation="create_admin_agent_prompt_version",
            decision="deny",
            reason=str(exc),
        )
        raise HTTPException(status_code=404, detail="RESOURCE_NOT_FOUND") from exc
    except ValueError as exc:
        await _audit_agent(
            ctx,
            agent_id=agent_id,
            operation="create_admin_agent_prompt_version",
            decision="deny",
            reason=str(exc),
        )
        raise HTTPException(status_code=422, detail="AGENT_PROMPT_VERSION_INVALID") from exc
    except Exception:
        await _audit_agent(
            ctx,
            agent_id=agent_id,
            operation="create_admin_agent_prompt_version",
            decision="deny",
            reason="prompt version create failed",
        )
        return _agent_error("AGENT_PROMPT_VERSION_CREATE_FAILED", "Agent prompt version create failed.")
    await _audit_agent_best_effort(
        ctx,
        agent_id=agent_id,
        operation="create_admin_agent_prompt_version",
        decision="allow",
        metadata={
            "prompt_version_id": created["version_id"],
            "prompt_version": created["version"],
            "prompt_sha256": created["content_sha256"],
            "activated": bool(created.get("active")),
        },
    )
    return Result(success=True, data=_prompt_version_detail(created))


@router.put(
    "/admin/agents/{agent_id}/prompt-version",
    response_model=Result[AgentPromptVersionDetail],
    summary="Activate Admin Agent Prompt Version",
    dependencies=[
        Depends(_require_admin_agents),
        Depends(require_platform_active(operation="admin.agents.prompt_versions.activate", resource_type="agent")),
    ],
)
async def activate_admin_agent_prompt_version(
    agent_id: str,
    body: ActivateAgentPromptVersionRequest,
    ctx: AdminAgentsCtx,
) -> Result[AgentPromptVersionDetail]:
    """Activate one version after verifying the caller's expected current version."""

    record = await _require_custom_agent_record(agent_id, ctx, operation="activate_admin_agent_prompt_version")
    store = deps.get_enterprise_extensions().agent_store
    try:
        active = await _ensure_legacy_prompt_version(store, record)
        expected_active_version_id = body.expected_active_version_id
        legacy = _legacy_prompt_version_record(record)
        if legacy is not None and expected_active_version_id == legacy["version_id"]:
            expected_active_version_id = str(active["version_id"]) if active is not None else None
        activated = await store.activate_prompt_version(
            agent_id=agent_id,
            version_id=body.version_id,
            expected_active_version_id=expected_active_version_id,
            activated_by=ctx.user_id,
        )
    except PromptVersionConflictError as exc:
        await _audit_agent(
            ctx,
            agent_id=agent_id,
            operation="activate_admin_agent_prompt_version",
            decision="deny",
            reason=str(exc),
        )
        raise HTTPException(status_code=409, detail="AGENT_PROMPT_VERSION_CONFLICT") from exc
    except (PromptVersionNotFoundError, PromptVersionAgentNotFoundError) as exc:
        await _audit_agent(
            ctx,
            agent_id=agent_id,
            operation="activate_admin_agent_prompt_version",
            decision="deny",
            reason=str(exc),
        )
        raise HTTPException(status_code=404, detail="RESOURCE_NOT_FOUND") from exc
    except Exception:
        await _audit_agent(
            ctx,
            agent_id=agent_id,
            operation="activate_admin_agent_prompt_version",
            decision="deny",
            reason="prompt version activation failed",
        )
        return _agent_error("AGENT_PROMPT_VERSION_ACTIVATE_FAILED", "Agent prompt version activation failed.")
    await _audit_agent_best_effort(
        ctx,
        agent_id=agent_id,
        operation="activate_admin_agent_prompt_version",
        decision="allow",
        metadata={
            "old_prompt_version_id": active["version_id"] if active is not None else None,
            "old_prompt_version": active["version"] if active is not None else None,
            "old_prompt_sha256": active["content_sha256"] if active is not None else None,
            "new_prompt_version_id": activated["version_id"],
            "new_prompt_version": activated["version"],
            "new_prompt_sha256": activated["content_sha256"],
        },
    )
    return Result(success=True, data=_prompt_version_detail(activated))
