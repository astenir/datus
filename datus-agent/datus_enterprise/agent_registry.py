"""Enterprise agent registry helpers."""

from __future__ import annotations

import re
from fnmatch import fnmatchcase
from typing import Any

from datus.api.auth.context import AppContext
from datus.api.constants import BUILTIN_SUBAGENTS
from datus.api.enterprise.models import ResourceRef
from datus.api.services.agent_service import (
    SUBAGENT_TOOL_REFERENCE,
    _validate_tools,
    _validate_tools_for_agent_type,
)
from datus.tools.func_tool.sub_agent_task_tool import BUILTIN_SUBAGENT_DESCRIPTIONS

AGENT_ID_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9_-]{0,79}$")
AGENT_STATUSES = {"draft", "published", "disabled", "archived"}
AGENT_VISIBILITIES = {"private", "role", "enterprise"}
ADMIN_AGENT_PERMISSION = "module.admin.agents"
ENTERPRISE_AGENT_NODE_CLASSES = set(SUBAGENT_TOOL_REFERENCE) - {"chat"}

_NODE_CLASS_MODULE_PERMISSIONS = {
    "gen_sql": "module.sql_executor",
    "gen_report": "module.report.query",
    "gen_visual_report": "module.report.query",
    "ask_report": "module.report.query",
    "gen_dashboard": "module.dashboard.query",
    "gen_visual_dashboard": "module.dashboard.query",
    "ask_dashboard": "module.dashboard.query",
}


def validate_agent_id(agent_id: str) -> str | None:
    """Return an error message if ``agent_id`` cannot be used as a custom agent key."""

    normalized = (agent_id or "").strip()
    if not AGENT_ID_PATTERN.fullmatch(normalized):
        return "Agent id must match ^[A-Za-z][A-Za-z0-9_-]{0,79}$."
    if normalized in BUILTIN_SUBAGENTS:
        return f"Agent id '{normalized}' is reserved for a built-in subagent."
    return None


def validate_agent_status(status: str) -> str | None:
    if (status or "").strip().lower() not in AGENT_STATUSES:
        return f"Agent status must be one of: {', '.join(sorted(AGENT_STATUSES))}."
    return None


def normalize_acl(raw_acl: dict[str, Any] | None) -> dict[str, Any]:
    raw = raw_acl if isinstance(raw_acl, dict) else {}
    visibility = str(raw.get("visibility") or "private").strip().lower()
    if visibility not in AGENT_VISIBILITIES:
        raise ValueError(f"Agent visibility must be one of: {', '.join(sorted(AGENT_VISIBILITIES))}.")
    return {
        "visibility": visibility,
        "allowed_roles": sorted({str(role).strip() for role in raw.get("allowed_roles") or [] if str(role).strip()}),
        "allowed_user_ids": sorted(
            {str(user_id).strip() for user_id in raw.get("allowed_user_ids") or [] if str(user_id).strip()}
        ),
    }


def normalize_agent_payload(
    agent_id: str, payload: dict[str, Any], *, actor_user_id: str | None = None
) -> dict[str, Any]:
    """Normalize a route payload into the store/runtime record shape."""

    node_class = str(payload.get("node_class") or payload.get("type") or "gen_sql").strip()
    if node_class not in ENTERPRISE_AGENT_NODE_CLASSES:
        raise ValueError(f"Unsupported agent node_class: {node_class}.")

    tools = _normalize_list(payload.get("tools"))
    invalid_tools = _validate_tools(tools) + _validate_tools_for_agent_type(tools, node_class)
    if invalid_tools:
        raise ValueError(f"Invalid tools for {node_class}: {', '.join(sorted(set(invalid_tools)))}.")

    status = str(payload.get("status") or "draft").strip().lower()
    status_error = validate_agent_status(status)
    if status_error:
        raise ValueError(status_error)

    acl = normalize_acl(payload.get("acl"))
    return {
        "agent_id": agent_id,
        "name": str(payload.get("name") or agent_id).strip(),
        "description": _optional_str(payload.get("description")),
        "node_class": node_class,
        "status": status,
        "owner_user_id": _optional_str(payload.get("owner_user_id")) or actor_user_id,
        "datasource_id": _optional_str(payload.get("datasource_id")),
        "artifact_slug": _optional_str(payload.get("artifact_slug")),
        "prompt_template": _optional_str(payload.get("prompt_template")),
        "prompt_language": str(payload.get("prompt_language") or "en").strip(),
        "prompt_version": _optional_str(payload.get("prompt_version")) or "1.0",
        "tools": tools,
        "mcp": _normalize_list(payload.get("mcp")),
        "skills": _normalize_list(payload.get("skills")),
        "scoped_context": dict(payload.get("scoped_context") or {}),
        "rules": _normalize_list(payload.get("rules")),
        "max_turns": int(payload.get("max_turns") or 30),
        "acl": acl,
    }


def agent_record_to_runtime_entry(record: dict[str, Any]) -> dict[str, Any]:
    """Convert an enterprise agent record to ``AgentConfig.agentic_nodes`` shape."""

    entry: dict[str, Any] = {
        "id": record["agent_id"],
        "type": record["node_class"],
        "node_class": record["node_class"],
        "system_prompt": record["agent_id"],
        "agent_description": record.get("description") or "",
        "prompt_template": record.get("prompt_template"),
        "prompt_version": record.get("prompt_version") or "1.0",
        "prompt_language": record.get("prompt_language") or "en",
        "tools": ", ".join(record.get("tools") or []),
        "mcp": ", ".join(record.get("mcp") or []),
        "skills": ", ".join(record.get("skills") or []),
        "scoped_context": dict(record.get("scoped_context") or {}),
        "rules": list(record.get("rules") or []),
        "max_turns": int(record.get("max_turns") or 30),
    }
    if record.get("datasource_id"):
        entry.setdefault("scoped_context", {})["datasource"] = record["datasource_id"]
    if record.get("artifact_slug"):
        entry["artifact_slug"] = record["artifact_slug"]
    return entry


def builtin_agent_summaries_for_context(ctx: AppContext) -> list[dict[str, Any]]:
    """Return built-in agents the current user is allowed to dispatch."""

    summaries = []
    for agent_id in sorted(BUILTIN_SUBAGENTS):
        if not can_use_node_class(ctx, agent_id):
            continue
        summaries.append(
            {
                "agent_id": agent_id,
                "name": agent_id,
                "description": BUILTIN_SUBAGENT_DESCRIPTIONS.get(agent_id, ""),
                "node_class": agent_id,
                "status": "published",
                "source": "builtin",
            }
        )
    return summaries


def can_view_agent(ctx: AppContext, record: dict[str, Any]) -> bool:
    """Return whether ``ctx`` may see an enterprise agent record."""

    return _can_access_agent(ctx, record, require_use=False)


def can_use_agent(ctx: AppContext, record: dict[str, Any]) -> bool:
    """Return whether ``ctx`` may dispatch an enterprise agent record."""

    return _can_access_agent(ctx, record, require_use=True)


def can_use_node_class(ctx: AppContext, node_class: str) -> bool:
    permission = _NODE_CLASS_MODULE_PERMISSIONS.get(node_class)
    return permission is None or has_permission(ctx, permission)


def dispatch_permission_for_record(record: dict[str, Any]) -> str | None:
    return _NODE_CLASS_MODULE_PERMISSIONS.get(str(record.get("node_class") or ""))


def has_permission(ctx: AppContext, permission: str) -> bool:
    permissions = set(ctx.permissions or set())
    if not permissions:
        raw = ctx.principal.get("permissions") if isinstance(ctx.principal, dict) else None
        if raw is None:
            return True
        if isinstance(raw, str):
            permissions = {raw}
        elif isinstance(raw, list):
            permissions = {str(item) for item in raw if isinstance(item, str)}
    return any(item == "*" or fnmatchcase(permission, item) for item in permissions)


def agent_audit_summary(record: dict[str, Any] | None) -> dict[str, Any] | None:
    if record is None:
        return None
    return {
        "agent_id": record.get("agent_id"),
        "node_class": record.get("node_class"),
        "status": record.get("status"),
        "owner_user_id": record.get("owner_user_id"),
        "datasource_id": record.get("datasource_id"),
        "artifact_slug": record.get("artifact_slug"),
        "tools": sorted(record.get("tools") or []),
        "acl": normalize_acl(record.get("acl")),
    }


async def resolve_enterprise_agent_for_dispatch(ctx: AppContext, agent_id: str) -> dict[str, Any] | None:
    """Return a dispatchable enterprise agent record, or ``None`` if it does not exist."""

    from datus.api import deps
    from datus.api.enterprise.deps import require_authorized_module

    extensions = deps.get_enterprise_extensions()
    if not extensions.enabled:
        return None

    record = await extensions.agent_store.get_agent(agent_id)
    if record is None:
        return None
    if record.get("status") != "published" or not can_use_agent(ctx, record):
        await _audit_dispatch(ctx, record, decision="deny", reason="agent access denied")
        raise PermissionError("AGENT_FORBIDDEN")

    permission = dispatch_permission_for_record(record)
    if permission is not None:
        await require_authorized_module(ctx, permission, resource=ResourceRef(type="subagent", id=agent_id))

    await _audit_dispatch(ctx, record, decision="allow", reason=None)
    return record


async def _audit_dispatch(ctx: AppContext, record: dict[str, Any], *, decision: str, reason: str | None) -> None:
    from datus_enterprise.audit import AuditEvent, audit_decision

    await audit_decision(
        ctx,
        AuditEvent(
            action="agent.dispatch",
            resource_type="agent",
            resource_id=record.get("agent_id"),
            decision=decision,
            reason=reason,
            metadata={"summary": agent_audit_summary(record)},
        ),
    )


def _can_access_agent(ctx: AppContext, record: dict[str, Any], *, require_use: bool) -> bool:
    if has_permission(ctx, ADMIN_AGENT_PERMISSION):
        return True
    user_id = ctx.user_id
    if user_id and user_id == record.get("owner_user_id"):
        return True

    acl = normalize_acl(record.get("acl"))
    if user_id and user_id in set(acl["allowed_user_ids"]):
        return True
    if set(ctx.roles or []) & set(acl["allowed_roles"]):
        return True
    if acl["visibility"] == "enterprise":
        return True
    if acl["visibility"] == "role" and set(ctx.roles or []) & set(acl["allowed_roles"]):
        return True
    return not require_use and bool(user_id and user_id == record.get("owner_user_id"))


def _normalize_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        items = value.split(",")
    elif isinstance(value, (list, tuple, set)):
        items = value
    else:
        return []
    return [str(item).strip() for item in items if str(item).strip()]


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
