"""Enterprise agent registry helpers."""

from __future__ import annotations

import re
from fnmatch import fnmatchcase
from typing import Any

from datus.agent.node_capabilities import enterprise_agent_node_capabilities, get_agent_node_capability
from datus.agent.tool_policy import normalize_runtime_policy, normalize_tool_policy
from datus.api.auth.context import AppContext
from datus.api.constants import BUILTIN_SUBAGENTS
from datus.api.services.agent_service import _validate_tools, _validate_tools_for_agent_type
from datus.prompts.prompt_manager import PromptManager
from datus.tools.func_tool.sub_agent_task_tool import BUILTIN_SUBAGENT_DESCRIPTIONS
from datus.utils.constants import SYS_SUB_AGENTS

AGENT_ID_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9_-]{0,79}$")
AGENT_STATUSES = {"draft", "published", "disabled", "archived"}
AGENT_VISIBILITIES = {"private", "role", "enterprise"}
ADMIN_AGENT_PERMISSION = "module.admin.agents"
DEFAULT_CHAT_AGENT_ID = "chat"
ENTERPRISE_AGENT_NODE_CAPABILITIES = enterprise_agent_node_capabilities()
ENTERPRISE_AGENT_NODE_CLASSES = {capability.node_class for capability in ENTERPRISE_AGENT_NODE_CAPABILITIES}
ENTERPRISE_BUILTIN_AGENT_IDS = set(BUILTIN_SUBAGENTS) | {DEFAULT_CHAT_AGENT_ID}
ENTERPRISE_RESERVED_AGENT_IDS = set(SYS_SUB_AGENTS) | {DEFAULT_CHAT_AGENT_ID}
AGENT_POLICY_CONTEXT_KEY = "_enterprise_agent_policy"


def validate_agent_id(agent_id: str) -> str | None:
    """Return an error message if ``agent_id`` cannot be used as a custom agent key."""

    normalized = (agent_id or "").strip()
    if not AGENT_ID_PATTERN.fullmatch(normalized):
        return "Agent id must match ^[A-Za-z][A-Za-z0-9_-]{0,79}$."
    if is_enterprise_reserved_agent_id(normalized):
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
    agent_id: str,
    payload: dict[str, Any],
    *,
    actor_user_id: str | None = None,
    existing_record: dict[str, Any] | None = None,
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
    scoped_context = dict(payload.get("scoped_context") or {})
    existing_metadata = agent_policy_metadata(existing_record)
    scoped_context[AGENT_POLICY_CONTEXT_KEY] = {
        "tool_policy": normalize_tool_policy(payload.get("tool_policy", existing_metadata.get("tool_policy"))),
        "runtime_policy": normalize_runtime_policy(
            payload.get("runtime_policy", existing_metadata.get("runtime_policy"))
        ),
        "enterprise_default": bool(existing_metadata.get("enterprise_default", False)),
    }
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
        "scoped_context": scoped_context,
        "rules": _normalize_list(payload.get("rules")),
        "max_turns": int(payload.get("max_turns") or 30),
        "acl": acl,
    }


def agent_record_to_runtime_entry(record: dict[str, Any]) -> dict[str, Any]:
    """Convert an enterprise agent record to ``AgentConfig.agentic_nodes`` shape."""

    policy = agent_policy_metadata(record)
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
        "scoped_context": public_scoped_context(record),
        "rules": list(record.get("rules") or []),
        "max_turns": int(record.get("max_turns") or 30),
        "tool_policy": policy["tool_policy"],
        "runtime_policy": policy["runtime_policy"],
    }
    if record.get("datasource_id"):
        entry.setdefault("scoped_context", {})["datasource"] = record["datasource_id"]
    if record.get("artifact_slug"):
        entry["artifact_slug"] = record["artifact_slug"]
    return entry


def is_enterprise_builtin_agent_id(agent_id: str) -> bool:
    return agent_id in ENTERPRISE_BUILTIN_AGENT_IDS


def is_enterprise_reserved_agent_id(agent_id: str) -> bool:
    return agent_id in ENTERPRISE_RESERVED_AGENT_IDS


def builtin_agent_summary(agent_id: str) -> dict[str, Any]:
    """Return the stable summary shape for one built-in agent."""

    public_by_default = agent_id == DEFAULT_CHAT_AGENT_ID
    return {
        "agent_id": agent_id,
        "name": agent_id,
        "description": BUILTIN_SUBAGENT_DESCRIPTIONS.get(agent_id, ""),
        "node_class": agent_id,
        "status": "published" if public_by_default else "disabled",
        "source": "builtin",
        "owner_user_id": None,
        "acl": normalize_acl({"visibility": "enterprise" if public_by_default else "private"}),
        "tools": [],
        "mcp": [],
        "skills": [],
        "scoped_context": {
            AGENT_POLICY_CONTEXT_KEY: {
                "tool_policy": normalize_tool_policy(None),
                "runtime_policy": normalize_runtime_policy(None),
                "enterprise_default": False,
            }
        },
        "rules": [],
        "max_turns": 30,
    }


def merge_builtin_agent_overlay(agent_id: str, overlay: dict[str, Any] | None) -> dict[str, Any]:
    """Merge mutable enterprise policy fields over an immutable built-in definition."""

    record = builtin_agent_summary(agent_id)
    if overlay is None:
        return record
    record.update(
        {
            "status": str(overlay.get("status") or record["status"]),
            "acl": normalize_acl(overlay.get("acl")),
            "scoped_context": dict(overlay.get("scoped_context") or record["scoped_context"]),
            "created_at": overlay.get("created_at"),
            "updated_at": overlay.get("updated_at"),
        }
    )
    return record


def builtin_overlay_payload(
    agent_id: str,
    *,
    status: str,
    acl: dict[str, Any],
    tool_policy: dict[str, Any],
    runtime_policy: dict[str, Any],
    enterprise_default: bool = False,
    actor_user_id: str | None = None,
) -> dict[str, Any]:
    base = builtin_agent_summary(agent_id)
    base.update(
        {
            "status": status,
            "acl": normalize_acl(acl),
            "owner_user_id": None,
            "scoped_context": {
                AGENT_POLICY_CONTEXT_KEY: {
                    "tool_policy": normalize_tool_policy(tool_policy),
                    "runtime_policy": normalize_runtime_policy(runtime_policy),
                    "enterprise_default": bool(enterprise_default),
                }
            },
        }
    )
    base.pop("source", None)
    return base


def agent_policy_metadata(record: dict[str, Any] | None) -> dict[str, Any]:
    scoped_context = record.get("scoped_context") if isinstance(record, dict) else None
    raw = scoped_context.get(AGENT_POLICY_CONTEXT_KEY) if isinstance(scoped_context, dict) else None
    metadata = raw if isinstance(raw, dict) else {}
    agent_id = str(record.get("agent_id") or "") if isinstance(record, dict) else ""
    default_tool_policy: dict[str, Any] | None = None
    if record is not None and not is_enterprise_builtin_agent_id(agent_id) and not isinstance(raw, dict):
        default_tool_policy = {
            "mode": "allowlist",
            "allowed": list(record.get("tools") or []),
            "denied": [],
        }
    return {
        "tool_policy": normalize_tool_policy(metadata.get("tool_policy", default_tool_policy)),
        "runtime_policy": normalize_runtime_policy(metadata.get("runtime_policy")),
        "enterprise_default": bool(metadata.get("enterprise_default", False)),
    }


def public_scoped_context(record: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in dict(record.get("scoped_context") or {}).items()
        if key != AGENT_POLICY_CONTEXT_KEY
    }


def with_agent_policy_metadata(
    record: dict[str, Any],
    *,
    tool_policy: dict[str, Any] | None = None,
    runtime_policy: dict[str, Any] | None = None,
    enterprise_default: bool | None = None,
) -> dict[str, Any]:
    updated = dict(record)
    scoped_context = dict(record.get("scoped_context") or {})
    current = agent_policy_metadata(record)
    scoped_context[AGENT_POLICY_CONTEXT_KEY] = {
        "tool_policy": normalize_tool_policy(tool_policy if tool_policy is not None else current["tool_policy"]),
        "runtime_policy": normalize_runtime_policy(
            runtime_policy if runtime_policy is not None else current["runtime_policy"]
        ),
        "enterprise_default": (
            bool(enterprise_default) if enterprise_default is not None else current["enterprise_default"]
        ),
    }
    updated["scoped_context"] = scoped_context
    return updated


def builtin_agent_prompt_template(agent_id: str) -> dict[str, str | None]:
    """Return read-only prompt template metadata and source for one built-in agent."""

    capability = get_agent_node_capability(agent_id)
    template_name = capability.prompt_template if capability and capability.prompt_template else f"{agent_id}_system"
    prompt_manager = PromptManager()
    try:
        version = prompt_manager.get_latest_version(template_name)
        content = prompt_manager.get_raw_template(template_name, version)
    except FileNotFoundError:
        version = None
        content = None
    return {
        "prompt_template_name": template_name,
        "prompt_version": version,
        "prompt_template": content,
        "prompt_template_content": content,
    }


def can_view_agent(ctx: AppContext, record: dict[str, Any]) -> bool:
    """Return whether ``ctx`` may see an enterprise agent record."""

    return _can_access_agent(ctx, record, require_use=False)


def can_use_agent(ctx: AppContext, record: dict[str, Any]) -> bool:
    """Return whether ``ctx`` may dispatch an enterprise agent record."""

    return _can_access_agent(ctx, record, require_use=True)


def has_permission(ctx: AppContext, permission: str) -> bool:
    permissions = set(ctx.permissions or set())
    if not permissions:
        raw = ctx.principal.get("permissions") if isinstance(ctx.principal, dict) else None
        if raw is None:
            return False
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
        "policy": agent_policy_metadata(record),
    }


async def get_effective_agent_record(agent_id: str) -> dict[str, Any] | None:
    """Return a custom Agent or built-in definition merged with its policy overlay."""

    from datus.api import deps

    store = deps.get_enterprise_extensions().agent_store
    record = await store.get_agent(agent_id)
    if is_enterprise_builtin_agent_id(agent_id):
        return merge_builtin_agent_overlay(agent_id, record)
    return record


async def list_effective_agent_records(*, status: str | None = None) -> list[dict[str, Any]]:
    """Return one effective record per built-in or custom Agent without duplicates."""

    from datus.api import deps

    records = await deps.get_enterprise_extensions().agent_store.list_agents(status=None)
    overlays = {
        str(record.get("agent_id")): record
        for record in records
        if is_enterprise_builtin_agent_id(str(record.get("agent_id") or ""))
    }
    effective = [
        merge_builtin_agent_overlay(agent_id, overlays.get(agent_id))
        for agent_id in sorted(ENTERPRISE_BUILTIN_AGENT_IDS)
    ]
    effective.extend(
        record
        for record in records
        if not is_enterprise_builtin_agent_id(str(record.get("agent_id") or ""))
    )
    if status is not None:
        normalized_status = status.strip().lower()
        effective = [record for record in effective if record.get("status") == normalized_status]
    return sorted(effective, key=lambda record: str(record.get("agent_id") or ""))


async def list_available_agent_records(ctx: AppContext) -> list[dict[str, Any]]:
    records = await list_effective_agent_records(status="published")
    return [record for record in records if can_use_agent(ctx, record)]


async def resolve_effective_default_agent(ctx: AppContext) -> tuple[dict[str, Any] | None, str]:
    """Resolve user default, enterprise default, then the first ACL-usable Agent."""

    from datus.api import deps

    extensions = deps.get_enterprise_extensions()
    user_id = _optional_str(ctx.user_id)
    if user_id:
        preference = await extensions.user_store.get_chat_preference(user_id)
        user_default_id = _optional_str(preference.get("default_agent_id"))
        if user_default_id:
            record = await get_effective_agent_record(user_default_id)
            if record is not None and record.get("status") == "published" and can_use_agent(ctx, record):
                return record, "user"

    available = await list_available_agent_records(ctx)
    for record in available:
        if agent_policy_metadata(record)["enterprise_default"]:
            return record, "enterprise"
    if available:
        return available[0], "first_available"
    return None, "none"


async def resolve_enterprise_agent_for_dispatch(ctx: AppContext, agent_id: str) -> dict[str, Any] | None:
    """Return a dispatchable enterprise agent record, or ``None`` if it does not exist."""

    from datus.api import deps
    extensions = deps.get_enterprise_extensions()
    if not extensions.enabled:
        return None

    record = await get_effective_agent_record(agent_id)
    if record is None:
        return None
    if record.get("status") != "published" or not can_use_agent(ctx, record):
        await _audit_dispatch(ctx, record, decision="deny", reason="agent access denied")
        raise PermissionError("AGENT_FORBIDDEN")

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
    if ctx.is_admin or has_permission(ctx, ADMIN_AGENT_PERMISSION):
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
