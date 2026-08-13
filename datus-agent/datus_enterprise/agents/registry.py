"""Enterprise agent registry helpers."""

from __future__ import annotations

import re
from fnmatch import fnmatchcase
from typing import Any

from datus.agent.node_capabilities import enterprise_agent_node_capabilities, get_agent_node_capability
from datus.agent.tool_policy import include_bound_mcp_servers, normalize_runtime_policy, normalize_tool_policy
from datus.api.auth.context import AppContext
from datus.api.enterprise.prompt_versions import prompt_template_value
from datus.api.services.agent_service import _validate_tools, _validate_tools_for_agent_type
from datus.prompts.prompt_manager import PromptManager
from datus.tools.func_tool.sub_agent_task_tool import BUILTIN_SUBAGENT_DESCRIPTIONS
from datus.utils.constants import HIDDEN_SYS_SUB_AGENTS
from datus_enterprise.services.sub_agent_task_policy import ENTERPRISE_DELEGATABLE_BUILTIN_AGENT_IDS

AGENT_ID_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9_-]{0,79}$")
AGENT_STATUSES = {"draft", "published", "disabled", "archived"}
AGENT_VISIBILITIES = {"private", "role", "enterprise"}
ADMIN_AGENT_PERMISSION = "module.admin.agents"
DEFAULT_CHAT_AGENT_ID = "chat"
ENTERPRISE_AGENT_NODE_CAPABILITIES = enterprise_agent_node_capabilities()
ENTERPRISE_AGENT_NODE_CLASSES = {capability.node_class for capability in ENTERPRISE_AGENT_NODE_CAPABILITIES}
ENTERPRISE_BUILTIN_AGENT_IDS = set(ENTERPRISE_DELEGATABLE_BUILTIN_AGENT_IDS) | {DEFAULT_CHAT_AGENT_ID}
ENTERPRISE_RESERVED_AGENT_IDS = ENTERPRISE_BUILTIN_AGENT_IDS | HIDDEN_SYS_SUB_AGENTS
AGENT_POLICY_CONTEXT_KEY = "_enterprise_agent_policy"
PERSONAL_MCP_MODES = {"disabled", "selectable"}

_RUNTIME_DENY_TOOL_METHODS: dict[str, set[str]] = {
    "bash_tools": {"bash"},
    "bi_tools": {
        "add_chart_to_dashboard",
        "create_chart",
        "create_dashboard",
        "create_dataset",
        "delete_chart",
        "delete_dashboard",
        "delete_dataset",
        "get_bi_serving_target",
        "get_chart",
        "get_chart_data",
        "get_dashboard",
        "get_dataset",
        "list_bi_databases",
        "list_charts",
        "list_dashboards",
        "list_datasets",
        "update_chart",
        "update_dashboard",
    },
    "orchestrator_tools": {
        "create_issue_comment",
        "finish_mission",
        "mark_blocked",
        "request_human_input",
        "update_issue_status",
    },
    "skill_authoring_tools": {"search_skill_usage", "validate_skill"},
    "skills": {"load_skill"},
    "scheduler_tools": {
        "delete_job",
        "get_run_log",
        "get_scheduler_job",
        "list_job_runs",
        "list_scheduler_connections",
        "list_scheduler_jobs",
        "pause_job",
        "resume_job",
        "submit_sparksql_job",
        "submit_sql_job",
        "trigger_scheduler_job",
        "update_job",
    },
    "sub_agent_tools": {"task"},
    "web_tool": {"web_fetch", "web_search"},
}


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


def normalize_personal_mcp_mode(value: Any) -> str:
    mode = str(value or "disabled").strip().lower()
    if mode not in PERSONAL_MCP_MODES:
        raise ValueError(f"Personal MCP mode must be one of: {', '.join(sorted(PERSONAL_MCP_MODES))}.")
    return mode


def normalize_enterprise_agent_tool_policy(
    raw_policy: Any,
    *,
    node_class: str,
    mcp_server_names: list[str] | None,
) -> dict[str, Any]:
    """Validate one newly written enterprise Agent tool policy.

    Allowed native tools must come from the node-specific editor catalog.
    MCP allow rules are server-level and may only target servers bound to the
    Agent. Deny rules intentionally have a wider, independent vocabulary so
    defensive rules for runtime-only surfaces remain representable.
    """

    policy = normalize_tool_policy(raw_policy)
    bound_mcp_patterns = {f"mcp.{name}.*" for name in _normalize_list(mcp_server_names) if name}

    native_allowed = [pattern for pattern in policy["allowed"] if not pattern.startswith("mcp.")]
    invalid_allowed = set(_validate_tools(native_allowed))
    invalid_allowed.update(_validate_tools_for_agent_type(native_allowed, node_class))

    capability = get_agent_node_capability(node_class)
    allowed_categories = set(capability.tool_categories if capability is not None else ())
    invalid_allowed.update(
        pattern for pattern in native_allowed if _tool_pattern_category(pattern) not in allowed_categories
    )
    invalid_allowed.update(
        pattern for pattern in policy["allowed"] if pattern.startswith("mcp.") and pattern not in bound_mcp_patterns
    )
    if invalid_allowed:
        raise ValueError(f"Invalid allowed tools for {node_class}: {', '.join(sorted(invalid_allowed))}.")

    invalid_denied = [pattern for pattern in policy["denied"] if not _is_valid_denied_tool_pattern(pattern)]
    if invalid_denied:
        raise ValueError(f"Invalid denied tools: {', '.join(sorted(invalid_denied))}.")

    return include_bound_mcp_servers(policy, mcp_server_names)


def _tool_pattern_category(pattern: str) -> str:
    return pattern.split(".", 1)[0]


def _is_valid_denied_tool_pattern(pattern: str) -> bool:
    if not _validate_tools([pattern]):
        return True
    if pattern.startswith("mcp.") and pattern.endswith(".*"):
        server_name = pattern[len("mcp.") : -len(".*")]
        return bool(server_name) and not any(token in server_name for token in ("*", "?", "[", "]"))
    category, separator, method = pattern.partition(".")
    methods = _RUNTIME_DENY_TOOL_METHODS.get(category)
    if methods is None:
        return False
    return not separator or method == "*" or method in methods


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
    mcp = _normalize_list(payload.get("mcp"))
    capability = get_agent_node_capability(node_class)
    if mcp and (capability is None or not capability.supports_mcp):
        raise ValueError(f"Agent node_class '{node_class}' does not support MCP servers.")
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
        "tool_policy": normalize_enterprise_agent_tool_policy(
            payload.get("tool_policy", existing_metadata.get("tool_policy")),
            node_class=node_class,
            mcp_server_names=mcp,
        ),
        "runtime_policy": normalize_runtime_policy(
            payload.get("runtime_policy", existing_metadata.get("runtime_policy"))
        ),
        "enterprise_default": bool(existing_metadata.get("enterprise_default", False)),
        "personal_mcp_mode": normalize_personal_mcp_mode(
            payload.get("personal_mcp_mode", existing_metadata.get("personal_mcp_mode"))
        ),
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
        "prompt_template": prompt_template_value(payload.get("prompt_template")),
        "prompt_language": str(payload.get("prompt_language") or "en").strip(),
        "prompt_version": _optional_str(payload.get("prompt_version")) or "1.0",
        "tools": tools,
        "mcp": mcp,
        "skills": _normalize_list(payload.get("skills")),
        "scoped_context": scoped_context,
        "rules": _normalize_list(payload.get("rules")),
        "max_turns": int(payload.get("max_turns") or 30),
        "acl": acl,
    }


def agent_record_to_runtime_entry(record: dict[str, Any]) -> dict[str, Any]:
    """Convert an enterprise agent record to ``AgentConfig.agentic_nodes`` shape."""

    policy = agent_policy_metadata(record)
    policy["tool_policy"] = include_bound_mcp_servers(policy["tool_policy"], record.get("mcp"))
    prompt_template = record.get("prompt_template")
    has_custom_prompt = isinstance(prompt_template, str) and bool(prompt_template.strip())
    node_class = str(record["node_class"])
    capability = get_agent_node_capability(node_class)
    builtin_template = (
        capability.prompt_template if capability and capability.prompt_template else f"{node_class}_system"
    )
    entry: dict[str, Any] = {
        "id": record["agent_id"],
        "type": node_class,
        "node_class": node_class,
        "system_prompt": record["agent_id"] if has_custom_prompt else builtin_template.removesuffix("_system"),
        "agent_description": record.get("description") or "",
        "prompt_template": prompt_template if has_custom_prompt else None,
        "prompt_version": (record.get("prompt_version") or "1.0") if has_custom_prompt else None,
        "prompt_language": record.get("prompt_language") or "en",
        "tools": ", ".join(record.get("tools") or []),
        "mcp": ", ".join(record.get("mcp") or []),
        "skills": ", ".join(record.get("skills") or []),
        "scoped_context": public_scoped_context(record),
        "rules": list(record.get("rules") or []),
        "max_turns": int(record.get("max_turns") or 30),
        "tool_policy": policy["tool_policy"],
        "runtime_policy": policy["runtime_policy"],
        "personal_mcp_mode": policy["personal_mcp_mode"],
    }
    if record.get("datasource_id"):
        entry.setdefault("scoped_context", {})["datasource"] = record["datasource_id"]
    if record.get("artifact_slug"):
        entry["artifact_slug"] = record["artifact_slug"]
    return entry


def materialize_enterprise_agent(agent_config: Any, record: dict[str, Any]) -> None:
    """Install one enterprise agent into a request-scoped AgentConfig clone."""

    agentic_nodes = dict(getattr(agent_config, "agentic_nodes", None) or {})
    agentic_nodes[str(record["agent_id"])] = agent_record_to_runtime_entry(record)
    agent_config.agentic_nodes = agentic_nodes


def materialize_artifact_edit_agent(agent_config: Any, session: Any) -> None:
    """Install one ACL-authorized Artifact edit session as a locked runtime node."""

    agentic_nodes = dict(getattr(agent_config, "agentic_nodes", None) or {})
    if session.artifact_type == "dashboard":
        node_type = "gen_visual_dashboard"
        root_dir = "dashboards"
        bind_call = f"bind_existing_dashboard('{session.artifact_slug}')"
        start_call = "start_new_dashboard"
    else:
        node_type = "gen_visual_report"
        root_dir = "reports"
        bind_call = f"bind_existing_report('{session.artifact_slug}')"
        start_call = "start_new_report"
    agentic_nodes[session.subagent_id] = {
        "id": session.subagent_id,
        "type": node_type,
        "node_class": node_type,
        "system_prompt": node_type,
        "artifact_slug": session.artifact_slug,
        "edit_locked": True,
        # This internal capability marker is added only after the route's
        # authoritative Artifact edit ACL check has succeeded.
        "_acl_authorized_artifact_edit": True,
        "agent_description": (
            f"This is a private edit session locked to {root_dir}/{session.artifact_slug}. "
            f"Call {bind_call} first; do not create a new {session.artifact_type}."
        ),
        "rules": [
            f"You are editing exactly {root_dir}/{session.artifact_slug}/.",
            f"Your first artifact tool call must be {bind_call}.",
            f"Do not call read_file, glob, list_tables, describe_table, execute_sql, or any other tool before {bind_call}.",
            (
                f"If {root_dir}/{session.artifact_slug}/ is empty, missing manifest.json, or missing render/app.jsx, "
                f"still call {bind_call}; the bind tool bootstraps incomplete locked edit artifacts."
            ),
            "After bind returns bootstrap_warning, inspect the restored tree, write or repair render/app.jsx, "
            "save required queries, and call validate_render.",
            "validate_render is a static check only — it cannot reproduce browser runtime errors (e.g. "
            "Minified React errors, ReferenceError from a missing named import). When the user reports a "
            "runtime render error, cross-check the reported Error/stack against the actual render files "
            "(default/named exports, import paths, hook order) before validate_render; a passing "
            "validate_render does not prove the runtime error is fixed.",
            "Do not call web_search, web_fetch, or any other network tool to decode browser error URLs or "
            "look up documentation for them; error data only maps to local render/ code.",
            f"Do not call {start_call} in this edit session.",
            f"Do not inspect, write, edit, or delete any other {session.artifact_type} artifact.",
        ],
    }
    agent_config.agentic_nodes = agentic_nodes


def is_enterprise_builtin_agent_id(agent_id: str) -> bool:
    return agent_id in ENTERPRISE_BUILTIN_AGENT_IDS


def is_enterprise_reserved_agent_id(agent_id: str) -> bool:
    return agent_id in ENTERPRISE_RESERVED_AGENT_IDS


def builtin_agent_default_max_turns(agent_id: str) -> int:
    """Return the built-in Agent's runtime-default ``max_turns``.

    Aligned with the node class constructor defaults (``agent.yml``
    ``agentic_nodes.<name>.max_turns`` fallback): visual-artifact nodes
    default to 80, every other built-in node class to 50. The value is
    deliberately not hardcoded here so enterprise Agent management cannot
    drift from the runtime node defaults again.
    """
    capability = get_agent_node_capability(agent_id)
    if capability is None:
        return 50
    return capability.default_max_turns


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
                "personal_mcp_mode": "disabled",
            }
        },
        "rules": [],
        "max_turns": builtin_agent_default_max_turns(agent_id),
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
    personal_mcp_mode: str = "disabled",
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
                    "personal_mcp_mode": normalize_personal_mcp_mode(personal_mcp_mode),
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
        "personal_mcp_mode": normalize_personal_mcp_mode(metadata.get("personal_mcp_mode")),
    }


def public_scoped_context(record: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value for key, value in dict(record.get("scoped_context") or {}).items() if key != AGENT_POLICY_CONTEXT_KEY
    }


def with_agent_policy_metadata(
    record: dict[str, Any],
    *,
    tool_policy: dict[str, Any] | None = None,
    runtime_policy: dict[str, Any] | None = None,
    enterprise_default: bool | None = None,
    personal_mcp_mode: str | None = None,
) -> dict[str, Any]:
    updated = dict(record)
    scoped_context = dict(record.get("scoped_context") or {})
    current = agent_policy_metadata(record)
    normalized_tool_policy = (
        normalize_enterprise_agent_tool_policy(
            tool_policy,
            node_class=str(record.get("node_class") or record.get("agent_id") or ""),
            mcp_server_names=_normalize_list(record.get("mcp")),
        )
        if tool_policy is not None
        else current["tool_policy"]
    )
    scoped_context[AGENT_POLICY_CONTEXT_KEY] = {
        "tool_policy": normalized_tool_policy,
        "runtime_policy": normalize_runtime_policy(
            runtime_policy if runtime_policy is not None else current["runtime_policy"]
        ),
        "enterprise_default": (
            bool(enterprise_default) if enterprise_default is not None else current["enterprise_default"]
        ),
        "personal_mcp_mode": normalize_personal_mcp_mode(
            personal_mcp_mode if personal_mcp_mode is not None else current["personal_mcp_mode"]
        ),
    }
    updated["scoped_context"] = scoped_context
    return updated


def builtin_agent_prompt_template(
    agent_id: str,
    *,
    agent_config: Any | None = None,
) -> dict[str, str | None]:
    """Return read-only prompt template metadata and source for one built-in agent."""

    capability = get_agent_node_capability(agent_id)
    template_name = capability.prompt_template if capability and capability.prompt_template else f"{agent_id}_system"
    prompt_manager = PromptManager(agent_config=agent_config)
    try:
        version = prompt_manager.get_latest_version(template_name)
        content = prompt_manager.get_raw_template(template_name, version)
        identity = prompt_manager.get_template_identity(template_name, version)
    except FileNotFoundError:
        version = None
        content = None
        identity = None
    template_source = identity.get("source") if identity is not None else "builtin"
    prompt_source = {
        "user": "user_override",
        "runtime": "runtime",
    }.get(template_source, "builtin")
    return {
        "prompt_template_name": template_name,
        "prompt_version": version,
        "prompt_template": content,
        "prompt_template_content": content,
        "prompt_source": prompt_source,
        "configured_prompt_version": version,
        "resolved_prompt_version": version,
        "prompt_revision": identity.get("content_sha256") if identity is not None else None,
    }


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
        record for record in records if not is_enterprise_builtin_agent_id(str(record.get("agent_id") or ""))
    )
    if status is not None:
        normalized_status = status.strip().lower()
        effective = [record for record in effective if record.get("status") == normalized_status]
    return sorted(effective, key=lambda record: str(record.get("agent_id") or ""))


async def list_available_agent_records(ctx: AppContext) -> list[dict[str, Any]]:
    records = await list_effective_agent_records(status="published")
    return [record for record in records if can_use_agent(ctx, record)]


async def resolve_effective_default_agent(ctx: AppContext) -> tuple[dict[str, Any] | None, str]:
    """Resolve user default, enterprise default, built-in chat, then the first ACL-usable Agent."""

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
    for record in available:
        if record.get("agent_id") == DEFAULT_CHAT_AGENT_ID:
            return record, "builtin_chat"
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
