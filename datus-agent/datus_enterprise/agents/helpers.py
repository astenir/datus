"""Shared non-route helpers for enterprise Agent APIs."""

from __future__ import annotations

from typing import Any

from fastapi import HTTPException, Request

from datus.api import deps
from datus.api.auth.context import AppContext
from datus.api.enterprise.prompt_versions import (
    PromptVersionConflictError,
    prompt_content_sha256,
    prompt_template_value,
)
from datus.api.models.base_models import Result
from datus_enterprise.agents.models import (
    AgentAcl,
    AgentAclRoleSummary,
    AgentAclUserSummary,
    AgentPreferenceSummary,
    AgentPromptVersionDetail,
    AgentPromptVersionSummary,
    AgentRuntimePolicy,
    AgentToolPolicy,
    EnterpriseAgentDetail,
    EnterpriseAgentSummary,
)
from datus_enterprise.agents.registry import (
    ADMIN_AGENT_PERMISSION,
    agent_policy_metadata,
    builtin_agent_default_max_turns,
    builtin_agent_prompt_template,
    builtin_overlay_payload,
    can_use_agent,
    get_effective_agent_record,
    is_enterprise_builtin_agent_id,
    list_available_agent_records,
    normalize_acl,
    public_scoped_context,
    validate_agent_id,
)
from datus_enterprise.audit import AuditEvent, audit_decision


async def _node_class_for_available_agent(agent_id: str, ctx: AppContext) -> str | None:
    try:
        record = await get_effective_agent_record(agent_id)
    except Exception:
        return None
    if record is None or record.get("status") != "published" or not can_use_agent(ctx, record):
        return None
    return str(record.get("node_class") or "")


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
        personal_mcp_mode=policy["personal_mcp_mode"],
        enterprise_default=policy["enterprise_default"],
        created_at=record.get("created_at"),
        updated_at=record.get("updated_at"),
    )


def _detail_from_record(
    record: dict[str, Any],
    *,
    active_prompt_version: dict[str, Any] | None = None,
    agent_config: Any | None = None,
) -> EnterpriseAgentDetail:
    summary = _summary_from_record(record).model_dump()
    prompt_template = prompt_template_value(record.get("prompt_template"))
    configured_version = _optional_str(record.get("prompt_version")) or "1.0"
    if prompt_template is not None:
        prompt_template_name = str(record["agent_id"])
        prompt_template_content = prompt_template
        prompt_source = "enterprise"
        resolved_version = configured_version
        prompt_revision = prompt_content_sha256(prompt_template)
    else:
        fallback = builtin_agent_prompt_template(
            str(record.get("node_class") or "gen_sql"),
            agent_config=agent_config,
        )
        prompt_template_name = fallback.get("prompt_template_name")
        prompt_template_content = fallback.get("prompt_template_content")
        prompt_source = {
            "user_override": "user_override_fallback",
            "runtime": "runtime_fallback",
        }.get(fallback.get("prompt_source"), "builtin_fallback")
        resolved_version = fallback.get("resolved_prompt_version")
        prompt_revision = fallback.get("prompt_revision")
    return EnterpriseAgentDetail(
        **summary,
        prompt_template=prompt_template,
        prompt_template_name=prompt_template_name,
        prompt_template_content=prompt_template_content,
        prompt_language=str(record.get("prompt_language") or "en"),
        prompt_version=resolved_version,
        prompt_source=prompt_source,
        configured_prompt_version=configured_version,
        resolved_prompt_version=resolved_version,
        prompt_revision=prompt_revision,
        active_prompt_version_id=(
            str(active_prompt_version["version_id"]) if active_prompt_version is not None else None
        ),
        tools=list(record.get("tools") or []),
        mcp=list(record.get("mcp") or []),
        skills=list(record.get("skills") or []),
        scoped_context=public_scoped_context(record),
        rules=list(record.get("rules") or []),
        max_turns=int(record.get("max_turns") or 30),
    )


def _detail_from_builtin(
    record: dict[str, Any],
    *,
    agent_config: Any | None = None,
) -> EnterpriseAgentDetail:
    summary = _summary_from_record(record).model_dump()
    return EnterpriseAgentDetail(
        **summary,
        max_turns=int(
            record.get("max_turns") or builtin_agent_default_max_turns(str(record.get("agent_id") or ""))
        ),
        **builtin_agent_prompt_template(
            str(record["agent_id"]),
            agent_config=agent_config,
        ),
    )


async def _request_agent_config(request: Request, ctx: AppContext) -> Any:
    if ctx.config is not None:
        return ctx.config
    return (await deps.resolve_datus_service_for_request(request)).agent_config


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


def _prompt_version_summary(record: dict[str, Any]) -> AgentPromptVersionSummary:
    return AgentPromptVersionSummary(
        version_id=str(record["version_id"]),
        version=str(record["version"]),
        content_sha256=str(record["content_sha256"]),
        change_note=_optional_str(record.get("change_note")),
        based_on_version_id=_optional_str(record.get("based_on_version_id")),
        created_by=_optional_str(record.get("created_by")),
        created_at=_optional_str(record.get("created_at")),
        active=bool(record.get("active", False)),
    )


def _prompt_version_detail(record: dict[str, Any]) -> AgentPromptVersionDetail:
    return AgentPromptVersionDetail(
        **_prompt_version_summary(record).model_dump(),
        prompt_template=str(record["prompt_template"]),
        prompt_language=str(record.get("prompt_language") or "en"),
    )


def _legacy_prompt_version_record(record: dict[str, Any]) -> dict[str, Any] | None:
    prompt_template = prompt_template_value(record.get("prompt_template"))
    if prompt_template is None:
        return None
    version = _optional_str(record.get("prompt_version")) or "1.0"
    prompt_language = str(record.get("prompt_language") or "en")
    content_sha256 = prompt_content_sha256(prompt_template)
    identity_sha256 = prompt_content_sha256(f"{record.get('agent_id')}\0{version}\0{prompt_language}\0{content_sha256}")
    return {
        "version_id": f"legacy_{identity_sha256[:24]}",
        "agent_id": str(record["agent_id"]),
        "version": version,
        "prompt_template": prompt_template,
        "prompt_language": prompt_language,
        "content_sha256": content_sha256,
        "change_note": "Legacy Agent definition; persisted on the next prompt version mutation.",
        "based_on_version_id": None,
        "created_by": None,
        "created_at": _optional_str(record.get("updated_at")) or _optional_str(record.get("created_at")),
        "active": True,
    }


def _prompt_payload_matches_version(payload: dict[str, Any], version: dict[str, Any]) -> bool:
    prompt_template = prompt_template_value(payload.get("prompt_template"))
    if prompt_template is None:
        return False
    return (
        (_optional_str(payload.get("prompt_version")) or "1.0") == str(version["version"])
        and str(payload.get("prompt_language") or "en") == str(version.get("prompt_language") or "en")
        and prompt_content_sha256(prompt_template) == str(version["content_sha256"])
    )


async def _ensure_legacy_prompt_version(store, record: dict[str, Any]) -> dict[str, Any] | None:
    active = await store.get_active_prompt_version(str(record["agent_id"]))
    if active is not None:
        return active
    legacy = _legacy_prompt_version_record(record)
    if legacy is None:
        return None
    versions = await store.list_prompt_versions(str(record["agent_id"]))
    matching = next((item for item in versions if item["version"] == legacy["version"]), None)
    if matching is not None and matching["content_sha256"] != legacy["content_sha256"]:
        raise PromptVersionConflictError("The legacy prompt version label already contains different content.")
    if matching is None:
        try:
            matching = await store.create_prompt_version(
                agent_id=str(record["agent_id"]),
                version=str(legacy["version"]),
                prompt_template=str(legacy["prompt_template"]),
                prompt_language=str(legacy["prompt_language"]),
                change_note="Migrated from legacy Agent definition.",
                based_on_version_id=None,
                created_by="system:migration",
            )
        except PromptVersionConflictError:
            versions = await store.list_prompt_versions(str(record["agent_id"]))
            matching = next((item for item in versions if item["version"] == legacy["version"]), None)
            if matching is None or matching["content_sha256"] != legacy["content_sha256"]:
                raise
    try:
        return await store.activate_prompt_version(
            agent_id=str(record["agent_id"]),
            version_id=str(matching["version_id"]),
            expected_active_version_id=None,
            activated_by="system:migration",
        )
    except PromptVersionConflictError:
        active = await store.get_active_prompt_version(str(record["agent_id"]))
        if active is not None:
            return active
        raise


async def _refresh_active_prompt_projection(
    store,
    *,
    agent_id: str,
    active_prompt_version: dict[str, Any],
    actor_user_id: str | None,
) -> dict[str, Any]:
    expected_version_id = str(active_prompt_version["version_id"])
    try:
        return await store.activate_prompt_version(
            agent_id=agent_id,
            version_id=expected_version_id,
            expected_active_version_id=expected_version_id,
            activated_by=actor_user_id,
        )
    except PromptVersionConflictError:
        current = await store.get_active_prompt_version(agent_id)
        if current is None:
            raise
        current_version_id = str(current["version_id"])
        return await store.activate_prompt_version(
            agent_id=agent_id,
            version_id=current_version_id,
            expected_active_version_id=current_version_id,
            activated_by=actor_user_id,
        )


async def _require_custom_agent_record(
    agent_id: str,
    ctx: AppContext,
    *,
    operation: str,
) -> dict[str, Any]:
    if is_enterprise_builtin_agent_id(agent_id):
        await _audit_agent(
            ctx,
            agent_id=agent_id,
            operation=operation,
            decision="deny",
            reason="built-in Agent prompt versions are read-only",
        )
        raise HTTPException(status_code=409, detail="AGENT_BUILTIN_IMMUTABLE")
    invalid = validate_agent_id(agent_id)
    if invalid is not None:
        await _audit_agent(ctx, agent_id=agent_id, operation=operation, decision="deny", reason=invalid)
        raise HTTPException(status_code=404, detail="RESOURCE_NOT_FOUND")
    try:
        record = await deps.get_enterprise_extensions().agent_store.get_agent(agent_id)
    except Exception as exc:
        await _audit_agent(ctx, agent_id=agent_id, operation=operation, decision="deny", reason="read failed")
        raise HTTPException(status_code=503, detail="AGENT_READ_FAILED") from exc
    if record is None:
        await _audit_agent(ctx, agent_id=agent_id, operation=operation, decision="deny", reason="not found")
        raise HTTPException(status_code=404, detail="RESOURCE_NOT_FOUND")
    return record


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
            personal_mcp_mode=policy["personal_mcp_mode"],
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
