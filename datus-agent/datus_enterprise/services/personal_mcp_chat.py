"""Request-scoped personal MCP selection and Agent projection."""

from __future__ import annotations

from typing import Any

from fastapi import HTTPException

from datus.agent.tool_policy import include_bound_mcp_servers
from datus.api import deps
from datus.api.auth.context import AppContext
from datus.api.enterprise.deps import require_authorized_module
from datus.api.models.downstream import StreamChatInput
from datus.utils.exceptions import DatusException
from datus_enterprise.agents.registry import agent_policy_metadata
from datus_enterprise.personal_mcp import (
    normalize_personal_mcp_id,
    personal_mcp_alias,
    personal_mcp_display_names,
    personal_mcp_options,
    record_to_mcp_config,
    validate_personal_mcp_destination,
    validate_personal_mcp_policy,
)


async def project_personal_mcp_for_chat(
    ctx: AppContext,
    request: StreamChatInput,
    *,
    agent_config: Any,
    agent_record: dict[str, Any] | None,
    project_id: str,
    new_session: bool,
) -> list[dict[str, Any]]:
    """Validate, lock and project selected personal MCP servers into this request clone."""

    user_id = (ctx.user_id or "").strip()
    if not user_id:
        raise HTTPException(status_code=401, detail="AUTH_REQUIRED")
    store = deps.get_enterprise_extensions().user_mcp_server_store
    requested_ids = _normalized_ids(request.personal_mcp_ids)
    binding = None
    if request.session_id and not new_session:
        binding = await store.get_session_binding(project_id, request.session_id, user_id)
        if binding is not None:
            bound_ids = [str(item["mcp_id"]) for item in binding["servers"]]
            if requested_ids and requested_ids != sorted(bound_ids):
                raise HTTPException(status_code=409, detail="PERSONAL_MCP_SESSION_LOCKED")
            requested_ids = sorted(bound_ids)
        elif requested_ids:
            raise HTTPException(status_code=409, detail="PERSONAL_MCP_SESSION_LOCKED")

    if not requested_ids:
        request.personal_mcp_ids = []
        return []

    await require_authorized_module(ctx, "mcp.personal.use")
    if agent_record is None or agent_policy_metadata(agent_record)["personal_mcp_mode"] != "selectable":
        raise HTTPException(status_code=403, detail="PERSONAL_MCP_AGENT_DISABLED")

    options = personal_mcp_options(agent_config)
    if not options["enabled"]:
        raise HTTPException(status_code=503, detail="PERSONAL_MCP_DISABLED")
    if len(requested_ids) > options["max_selected_per_session"]:
        raise HTTPException(status_code=400, detail="PERSONAL_MCP_SELECTION_LIMIT_EXCEEDED")

    records = []
    for mcp_id in requested_ids:
        record = await store.get_server(user_id, mcp_id)
        if record is None or not record.get("enabled"):
            raise HTTPException(status_code=404, detail="PERSONAL_MCP_NOT_FOUND")
        if binding is not None:
            bound_revision = next(int(item["revision"]) for item in binding["servers"] if str(item["mcp_id"]) == mcp_id)
            if int(record.get("revision") or 0) != bound_revision:
                raise HTTPException(status_code=409, detail="PERSONAL_MCP_REVISION_CHANGED")
        try:
            validate_personal_mcp_policy(agent_config, url=str(record["url"]))
            await validate_personal_mcp_destination(
                str(record["url"]), allow_private_hosts=options["allow_private_hosts"]
            )
        except DatusException as exc:
            raise HTTPException(status_code=400, detail="PERSONAL_MCP_DESTINATION_DENIED") from exc
        records.append(record)

    aliases = [personal_mcp_alias(str(record["id"])) for record in records]
    request_servers = dict(getattr(agent_config, "_request_mcp_servers", {}) or {})
    for alias, record in zip(aliases, records, strict=True):
        request_servers[alias] = record_to_mcp_config(record, timeout_seconds=options["timeout_seconds"])
    agent_config._request_mcp_servers = request_servers

    # Keep the alias -> display_name map next to the projected servers so chat
    # rendering can show the user-facing MCP name instead of the record ID
    # alias (``personal_<id>``) in tool cards and connection-failure events.
    request_display_names = dict(getattr(agent_config, "_request_mcp_display_names", {}) or {})
    request_display_names.update(personal_mcp_display_names(records))
    agent_config._request_mcp_display_names = request_display_names
    _attach_to_target_agent(agent_config, request.subagent_id, aliases)

    request.personal_mcp_ids = requested_ids
    return records


async def commit_personal_mcp_session(
    *,
    project_id: str,
    session_id: str,
    user_id: str,
    records: list[dict[str, Any]],
) -> None:
    """Persist the immutable selection only after chat admission succeeds."""

    if not records:
        return
    store = deps.get_enterprise_extensions().user_mcp_server_store
    await store.set_session_binding(
        project_id=project_id,
        session_id=session_id,
        user_id=user_id,
        servers=[{"mcp_id": record["id"], "revision": record["revision"]} for record in records],
    )
    for record in records:
        await store.touch_server_used(user_id, str(record["id"]))


def _attach_to_target_agent(agent_config: Any, agent_id: str | None, aliases: list[str]) -> None:
    agentic_nodes = dict(getattr(agent_config, "agentic_nodes", {}) or {})
    target_key = agent_id if agent_id in agentic_nodes else None
    if target_key is None:
        target_key = next(
            (
                key
                for key, entry in agentic_nodes.items()
                if isinstance(entry, dict) and str(entry.get("id") or "") == str(agent_id or "")
            ),
            None,
        )
    if target_key is None:
        raise HTTPException(status_code=404, detail="AGENT_NOT_FOUND")
    entry = dict(agentic_nodes[target_key])
    existing = [item.strip() for item in str(entry.get("mcp") or "").split(",") if item.strip()]
    combined = list(dict.fromkeys([*existing, *aliases]))
    entry["mcp"] = ", ".join(combined)
    entry["tool_policy"] = include_bound_mcp_servers(entry.get("tool_policy"), combined)
    agentic_nodes[target_key] = entry
    agent_config.agentic_nodes = agentic_nodes


def _normalized_ids(values: list[str]) -> list[str]:
    try:
        return sorted({normalize_personal_mcp_id(value) for value in values})
    except DatusException as exc:
        raise HTTPException(status_code=400, detail="PERSONAL_MCP_ID_INVALID") from exc
