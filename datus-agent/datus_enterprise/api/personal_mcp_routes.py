"""Current-user personal MCP management routes."""

from __future__ import annotations

import uuid
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from datus.api import deps
from datus.api.auth.context import AppContext
from datus.api.deps import ServiceDep
from datus.api.enterprise.deps import (
    authorize_session_access,
    require_authorized_module,
    require_module,
    require_platform_active,
)
from datus.api.models.base_models import Result
from datus.tools.mcp_tools.mcp_manager import MCPManager
from datus.utils.exceptions import DatusException
from datus.utils.loggings import get_logger
from datus_enterprise.audit import AuditEvent, audit_decision
from datus_enterprise.personal_mcp import (
    normalize_display_name,
    normalize_personal_mcp_id,
    normalize_token,
    normalize_tool_names,
    normalize_transport,
    personal_mcp_alias,
    personal_mcp_options,
    personal_mcp_policy_mode,
    record_to_mcp_config,
    validate_personal_mcp_destination,
    validate_personal_mcp_policy,
)

logger = get_logger(__name__)
router = APIRouter(prefix="/api/v1/me/mcp-servers", tags=["user-mcp"])
_require_personal_mcp_module = require_module("module.mcp.personal")
RequestContextDep = Annotated[AppContext, Depends(deps.get_request_app_context)]


class PersonalMcpOptions(BaseModel):
    enabled: bool
    allowed_hosts: list[str] = Field(default_factory=list)
    allow_insecure_http: bool
    allow_private_hosts: bool
    max_servers_per_user: int
    max_selected_per_session: int


class PersonalMcpSummary(BaseModel):
    id: str
    display_name: str
    transport: Literal["http", "sse"]
    url: str
    auth_mode: Literal["none", "static_bearer"]
    credential_configured: bool
    token_hint: str | None = None
    allowed_tools: list[str] = Field(default_factory=list)
    blocked_tools: list[str] = Field(default_factory=list)
    enabled: bool
    revision: int
    last_used_at: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


class UpsertPersonalMcpRequest(BaseModel):
    display_name: str = Field(min_length=1, max_length=120)
    transport: Literal["http", "sse"]
    url: str = Field(min_length=1, max_length=2048)
    token: str | None = Field(default=None, max_length=4096)
    allowed_tools: list[str] = Field(default_factory=list, max_length=300)
    blocked_tools: list[str] = Field(default_factory=list, max_length=300)
    enabled: bool = True


class PersonalMcpSessionBindingItem(BaseModel):
    mcp_id: str
    revision: int
    display_name: str = ""


class PersonalMcpSessionBinding(BaseModel):
    session_id: str
    servers: list[PersonalMcpSessionBindingItem] = Field(default_factory=list)


async def _require_permission(ctx: RequestContextDep, action: str) -> None:
    await require_authorized_module(ctx, action)


async def _require_list(ctx: RequestContextDep) -> None:
    await _require_permission(ctx, "mcp.personal.list")


async def _require_create(ctx: RequestContextDep) -> None:
    await _require_permission(ctx, "mcp.personal.create")


async def _require_edit(ctx: RequestContextDep) -> None:
    await _require_permission(ctx, "mcp.personal.edit")


async def _require_remove(ctx: RequestContextDep) -> None:
    await _require_permission(ctx, "mcp.personal.remove")


async def _require_connectivity(ctx: RequestContextDep) -> None:
    await _require_permission(ctx, "mcp.personal.connectivity")


async def _require_tools(ctx: RequestContextDep) -> None:
    await _require_permission(ctx, "mcp.personal.tools")


@router.get(
    "/options",
    response_model=Result[PersonalMcpOptions],
    dependencies=[Depends(_require_personal_mcp_module), Depends(_require_list)],
)
async def get_personal_mcp_options(svc: ServiceDep, _ctx: RequestContextDep) -> Result[PersonalMcpOptions]:
    options = personal_mcp_options(svc.agent_config)
    return Result(success=True, data=PersonalMcpOptions(**{k: v for k, v in options.items() if k != "timeout_seconds"}))


@router.get(
    "/session-binding/{session_id}",
    response_model=Result[PersonalMcpSessionBinding],
    dependencies=[Depends(_require_personal_mcp_module), Depends(_require_list)],
)
async def get_personal_mcp_session_binding(
    session_id: str,
    svc: ServiceDep,
    ctx: RequestContextDep,
) -> Result[PersonalMcpSessionBinding]:
    access = await authorize_session_access(
        svc,
        ctx,
        session_id,
        action="personal_mcp_binding",
        require_existing_session=True,
        allow_admin=False,
    )
    if access.error:
        raise HTTPException(status_code=404, detail="RESOURCE_NOT_FOUND")
    binding = await _store().get_session_binding(svc.project_id, session_id, _require_user_id(ctx))
    servers = list(binding.get("servers") or []) if binding else []
    user_id = _require_user_id(ctx)
    items = []
    for item in servers:
        # Join the user-facing display name so chat rendering can resolve the
        # runtime alias (``personal_<id>``) back to the MCP name.
        record = await _store().get_server(user_id, str(item["mcp_id"]))
        items.append(
            PersonalMcpSessionBindingItem(
                mcp_id=str(item["mcp_id"]),
                revision=int(item["revision"]),
                display_name=str(record.get("display_name") or "") if record else "",
            )
        )
    return Result(
        success=True,
        data=PersonalMcpSessionBinding(session_id=session_id, servers=items),
    )


@router.get(
    "",
    response_model=Result[list[PersonalMcpSummary]],
    dependencies=[Depends(_require_personal_mcp_module), Depends(_require_list)],
)
async def list_personal_mcp_servers(ctx: RequestContextDep) -> Result[list[PersonalMcpSummary]]:
    records = await _store().list_servers(_require_user_id(ctx))
    return Result(success=True, data=[_summary(record) for record in records])


@router.post(
    "",
    response_model=Result[PersonalMcpSummary],
    dependencies=[
        Depends(_require_personal_mcp_module),
        Depends(_require_create),
        Depends(require_platform_active(operation="me.mcp.create", resource_type="user_mcp_server")),
    ],
)
async def create_personal_mcp_server(
    body: UpsertPersonalMcpRequest,
    svc: ServiceDep,
    ctx: RequestContextDep,
) -> Result[PersonalMcpSummary]:
    user_id = _require_user_id(ctx)
    options = personal_mcp_options(svc.agent_config)
    if len(await _store().list_servers(user_id)) >= options["max_servers_per_user"]:
        raise HTTPException(status_code=409, detail="PERSONAL_MCP_LIMIT_EXCEEDED")
    payload = _validated_payload(body, svc.agent_config)
    mcp_id = uuid.uuid4().hex
    record = await _store().put_server(user_id=user_id, mcp_id=mcp_id, **payload)
    await _audit_best_effort(ctx, "create", mcp_id, agent_config=svc.agent_config, new_record=record)
    return Result(success=True, data=_summary(record))


@router.get(
    "/{mcp_id}",
    response_model=Result[PersonalMcpSummary],
    dependencies=[Depends(_require_personal_mcp_module), Depends(_require_list)],
)
async def get_personal_mcp_server(mcp_id: str, ctx: RequestContextDep) -> Result[PersonalMcpSummary]:
    record = await _owned_record(ctx, mcp_id)
    return Result(success=True, data=_summary(record))


@router.put(
    "/{mcp_id}",
    response_model=Result[PersonalMcpSummary],
    dependencies=[
        Depends(_require_personal_mcp_module),
        Depends(_require_edit),
        Depends(require_platform_active(operation="me.mcp.edit", resource_type="user_mcp_server")),
    ],
)
async def update_personal_mcp_server(
    mcp_id: str,
    body: UpsertPersonalMcpRequest,
    svc: ServiceDep,
    ctx: RequestContextDep,
) -> Result[PersonalMcpSummary]:
    existing = await _owned_record(ctx, mcp_id)
    payload = _validated_payload(body, svc.agent_config)
    if "token" not in body.model_fields_set:
        payload["token"] = existing.get("token")
    record = await _store().put_server(
        user_id=_require_user_id(ctx), mcp_id=normalize_personal_mcp_id(mcp_id), **payload
    )
    await _audit_best_effort(
        ctx, "edit", str(record["id"]), agent_config=svc.agent_config, old_record=existing, new_record=record
    )
    return Result(success=True, data=_summary(record))


@router.delete(
    "/{mcp_id}",
    response_model=Result[dict[str, bool]],
    dependencies=[
        Depends(_require_personal_mcp_module),
        Depends(_require_remove),
        Depends(require_platform_active(operation="me.mcp.remove", resource_type="user_mcp_server")),
    ],
)
async def delete_personal_mcp_server(
    mcp_id: str,
    svc: ServiceDep,
    ctx: RequestContextDep,
) -> Result[dict[str, bool]]:
    existing = await _owned_record(ctx, mcp_id)
    user_id = _require_user_id(ctx)
    normalized_id = normalize_personal_mcp_id(mcp_id)
    try:
        session_count = await _store().count_session_bindings(user_id, normalized_id)
    except Exception as exc:
        logger.error("Personal MCP reference check failed", exc_info=True)
        raise HTTPException(status_code=503, detail="PERSONAL_MCP_REFERENCE_CHECK_FAILED") from exc
    if session_count:
        await _audit_best_effort(
            ctx,
            "remove",
            str(existing["id"]),
            agent_config=svc.agent_config,
            old_record=existing,
            metadata={"blocked": True, "session_count": session_count},
        )
        raise HTTPException(
            status_code=409,
            detail={"code": "PERSONAL_MCP_SERVER_IN_USE", "session_count": session_count},
        )
    deleted = await _store().delete_server(user_id, normalized_id)
    await _audit_best_effort(
        ctx,
        "remove",
        str(existing["id"]),
        agent_config=svc.agent_config,
        old_record=existing,
        metadata={"deleted": deleted},
    )
    return Result(success=True, data={"deleted": deleted})


@router.post(
    "/{mcp_id}/test",
    response_model=Result[dict[str, Any]],
    dependencies=[
        Depends(_require_personal_mcp_module),
        Depends(_require_connectivity),
        Depends(require_platform_active(operation="me.mcp.connectivity", resource_type="user_mcp_server")),
    ],
)
async def test_personal_mcp_server(mcp_id: str, svc: ServiceDep, ctx: RequestContextDep) -> Result[dict[str, Any]]:
    record = await _owned_record(ctx, mcp_id)
    success, message, details = await _operate(record, svc.agent_config, operation="connectivity")
    await _audit_best_effort(
        ctx,
        "connectivity",
        str(record["id"]),
        agent_config=svc.agent_config,
        new_record=record,
        metadata={"connected": success},
    )
    return Result(
        success=True, data={"connected": success, "message": message, "tools_count": details.get("tool_count")}
    )


@router.get(
    "/{mcp_id}/tools",
    response_model=Result[list[dict[str, Any]]],
    dependencies=[Depends(_require_personal_mcp_module), Depends(_require_tools)],
)
async def list_personal_mcp_tools(mcp_id: str, svc: ServiceDep, ctx: RequestContextDep) -> Result[list[dict[str, Any]]]:
    record = await _owned_record(ctx, mcp_id)
    success, _message, details = await _operate(record, svc.agent_config, operation="tools")
    if not success:
        raise HTTPException(status_code=502, detail="PERSONAL_MCP_CONNECTION_FAILED")
    return Result(success=True, data=list(details.get("tools") or []))


def _store():
    return deps.get_enterprise_extensions().user_mcp_server_store


def _require_user_id(ctx: AppContext) -> str:
    if not ctx.user_id:
        raise HTTPException(status_code=401, detail="AUTH_REQUIRED")
    return ctx.user_id


async def _owned_record(ctx: AppContext, mcp_id: str) -> dict[str, Any]:
    normalized = normalize_personal_mcp_id(mcp_id)
    record = await _store().get_server(_require_user_id(ctx), normalized)
    if record is None:
        raise HTTPException(status_code=404, detail="PERSONAL_MCP_NOT_FOUND")
    return record


def _validated_payload(body: UpsertPersonalMcpRequest, agent_config: Any) -> dict[str, Any]:
    try:
        return {
            "display_name": normalize_display_name(body.display_name),
            "transport": normalize_transport(body.transport),
            "url": validate_personal_mcp_policy(agent_config, url=body.url),
            "token": normalize_token(body.token),
            "allowed_tools": normalize_tool_names(body.allowed_tools),
            "blocked_tools": normalize_tool_names(body.blocked_tools),
            "enabled": bool(body.enabled),
        }
    except DatusException as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def _summary(record: dict[str, Any]) -> PersonalMcpSummary:
    configured = bool(record.get("token"))
    return PersonalMcpSummary(
        id=str(record["id"]),
        display_name=str(record["display_name"]),
        transport=str(record["transport"]),
        url=str(record["url"]),
        auth_mode="static_bearer" if configured else "none",
        credential_configured=configured,
        token_hint=record.get("token_hint"),
        allowed_tools=list(record.get("allowed_tools") or []),
        blocked_tools=list(record.get("blocked_tools") or []),
        enabled=bool(record.get("enabled")),
        revision=int(record.get("revision") or 1),
        last_used_at=record.get("last_used_at"),
        created_at=record.get("created_at"),
        updated_at=record.get("updated_at"),
    )


async def _operate(record: dict[str, Any], agent_config: Any, *, operation: str):
    try:
        options = personal_mcp_options(agent_config)
        validate_personal_mcp_policy(agent_config, url=str(record["url"]))
        await validate_personal_mcp_destination(str(record["url"]), allow_private_hosts=options["allow_private_hosts"])
        manager = MCPManager(agent_config=agent_config)
        alias = personal_mcp_alias(str(record["id"]))
        manager.config.servers[alias] = record_to_mcp_config(record, timeout_seconds=options["timeout_seconds"])
        if operation == "connectivity":
            success, message, details = await manager.check_connectivity(alias)
            return success, "Connected" if success else "Connection failed", details
        success, _message, tools = await manager.list_tools(alias)
        return success, "Tools loaded" if success else "Connection failed", {"tools": tools}
    except Exception:
        logger.info("Personal MCP operation failed", exc_info=True)
        return False, "Connection failed", {}


async def _audit_best_effort(
    ctx: AppContext,
    operation: str,
    resource_id: str,
    *,
    agent_config: Any | None = None,
    old_record: dict[str, Any] | None = None,
    new_record: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    try:
        await audit_decision(
            ctx,
            AuditEvent(
                action=f"mcp.personal.{operation}",
                resource_type="user_mcp_server",
                resource_id=resource_id,
                decision="allow",
                metadata={
                    "policy_mode": personal_mcp_policy_mode(agent_config) if agent_config is not None else None,
                    "old": _audit_summary(old_record),
                    "new": _audit_summary(new_record),
                    **(metadata or {}),
                },
            ),
        )
    except Exception:
        logger.warning("Personal MCP audit failed for operation=%s", operation, exc_info=True)


def _audit_summary(record: dict[str, Any] | None) -> dict[str, Any] | None:
    if record is None:
        return None
    return {
        "id": str(record["id"]),
        "display_name": str(record["display_name"]),
        "transport": str(record["transport"]),
        "host": str(record["url"]).split("/", 3)[2],
        "auth_mode": "static_bearer" if record.get("token") else "none",
        "enabled": bool(record.get("enabled")),
        "revision": int(record.get("revision") or 1),
    }
