"""Current-user private datasource routes."""

from __future__ import annotations

import asyncio
import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from datus.api import deps
from datus.api.auth.context import AppContext
from datus.api.deps import ServiceDep
from datus.api.enterprise.deps import require_module, require_platform_active
from datus.api.models.base_models import Result
from datus.api.models.downstream import ProbeResultData
from datus.utils.exceptions import DatusException
from datus.utils.loggings import get_logger
from datus_enterprise.api.config_routes import _probe_datasource_sync
from datus_enterprise.audit import AuditEvent, audit_decision
from datus_enterprise.personal_datasources import (
    datasource_record_to_db_config,
    normalize_datasource_id,
    normalize_datasource_type,
    normalize_display_name,
    normalize_host,
    normalize_optional_text,
    normalize_password,
    normalize_port,
    normalize_required_text,
    personal_datasource_key,
    personal_datasource_options,
    redact_db_config,
    validate_personal_datasource_policy,
)

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1/me", tags=["user-datasources"])
_require_catalog_module = require_module("module.datasource_catalog")
RequestContextDep = Annotated[AppContext, Depends(deps.get_request_app_context)]


class PersonalDatasourceProviderOptions(BaseModel):
    enabled: bool
    allowed_types: list[str] = Field(default_factory=list)
    allowed_hosts: list[str] = Field(default_factory=list)
    default_ports: dict[str, str] = Field(default_factory=dict)


class PersonalDatasourceSummary(BaseModel):
    id: str
    datasource_key: str
    type: str
    host: str
    port: str
    username: str
    password_hint: str
    database: str
    schema_name: str | None = None
    catalog_name: str | None = None
    display_name: str | None = None
    enabled: bool = True
    last_used_at: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


class UpsertPersonalDatasourceRequest(BaseModel):
    type: str
    host: str
    port: str | int
    username: str
    password: str
    database: str
    schema_name: str | None = None
    catalog_name: str | None = None
    display_name: str | None = None
    enabled: bool = True


@router.get(
    "/datasource-providers",
    response_model=Result[PersonalDatasourceProviderOptions],
    summary="List Personal Datasource Provider Options",
    dependencies=[Depends(_require_catalog_module)],
)
async def list_personal_datasource_options(
    svc: ServiceDep,
    _ctx: RequestContextDep,
) -> Result[PersonalDatasourceProviderOptions]:
    return Result(success=True, data=PersonalDatasourceProviderOptions(**personal_datasource_options(svc.agent_config)))


@router.get(
    "/datasources",
    response_model=Result[list[PersonalDatasourceSummary]],
    summary="List Current User Personal Datasources",
    dependencies=[Depends(_require_catalog_module)],
)
async def list_my_personal_datasources(ctx: RequestContextDep) -> Result[list[PersonalDatasourceSummary]]:
    user_id = _require_user_id(ctx)
    records = await deps.get_enterprise_extensions().user_datasource_store.list_datasources(user_id)
    return Result(success=True, data=[_datasource_summary(record) for record in records])


@router.post(
    "/datasources",
    response_model=Result[PersonalDatasourceSummary],
    summary="Create Current User Personal Datasource",
    dependencies=[
        Depends(_require_catalog_module),
        Depends(require_platform_active(operation="me.datasource.create", resource_type="user_datasource")),
    ],
)
async def create_my_personal_datasource(
    body: UpsertPersonalDatasourceRequest,
    svc: ServiceDep,
    ctx: RequestContextDep,
) -> Result[PersonalDatasourceSummary]:
    user_id = _require_user_id(ctx)
    payload = _validated_datasource_input(body, svc.agent_config)
    record = await deps.get_enterprise_extensions().user_datasource_store.put_datasource(
        user_id=user_id,
        datasource_id=uuid.uuid4().hex,
        **payload,
    )
    summary = _datasource_summary(record)
    await _audit_personal_datasource_best_effort(
        ctx,
        operation="create",
        decision="allow",
        resource_id=summary.id,
        new_summary=_summary_for_audit(summary),
    )
    return Result(success=True, data=summary)


@router.get(
    "/datasources/{datasource_id}",
    response_model=Result[PersonalDatasourceSummary],
    summary="Get Current User Personal Datasource",
    dependencies=[Depends(_require_catalog_module)],
)
async def get_my_personal_datasource(
    datasource_id: str,
    ctx: RequestContextDep,
) -> Result[PersonalDatasourceSummary]:
    user_id = _require_user_id(ctx)
    record = await deps.get_enterprise_extensions().user_datasource_store.get_datasource(
        user_id,
        normalize_datasource_id(datasource_id),
    )
    if record is None:
        raise HTTPException(status_code=404, detail="USER_DATASOURCE_NOT_FOUND")
    return Result(success=True, data=_datasource_summary(record))


@router.put(
    "/datasources/{datasource_id}",
    response_model=Result[PersonalDatasourceSummary],
    summary="Replace Current User Personal Datasource",
    dependencies=[
        Depends(_require_catalog_module),
        Depends(require_platform_active(operation="me.datasource.update", resource_type="user_datasource")),
    ],
)
async def update_my_personal_datasource(
    datasource_id: str,
    body: UpsertPersonalDatasourceRequest,
    svc: ServiceDep,
    ctx: RequestContextDep,
) -> Result[PersonalDatasourceSummary]:
    user_id = _require_user_id(ctx)
    normalized_id = normalize_datasource_id(datasource_id)
    store = deps.get_enterprise_extensions().user_datasource_store
    before = await store.get_datasource(user_id, normalized_id)
    if before is None:
        await _audit_personal_datasource_best_effort(
            ctx,
            operation="update",
            decision="deny",
            resource_id=normalized_id,
            reason="user datasource not found",
        )
        raise HTTPException(status_code=404, detail="USER_DATASOURCE_NOT_FOUND")
    payload = _validated_datasource_input(body, svc.agent_config)
    record = await store.put_datasource(user_id=user_id, datasource_id=normalized_id, **payload)
    summary = _datasource_summary(record)
    await _audit_personal_datasource_best_effort(
        ctx,
        operation="update",
        decision="allow",
        resource_id=normalized_id,
        old_summary=_record_for_audit(before),
        new_summary=_summary_for_audit(summary),
    )
    return Result(success=True, data=summary)


@router.delete(
    "/datasources/{datasource_id}",
    response_model=Result[dict[str, bool]],
    summary="Delete Current User Personal Datasource",
    dependencies=[
        Depends(_require_catalog_module),
        Depends(require_platform_active(operation="me.datasource.delete", resource_type="user_datasource")),
    ],
)
async def delete_my_personal_datasource(
    datasource_id: str,
    ctx: RequestContextDep,
) -> Result[dict[str, bool]]:
    user_id = _require_user_id(ctx)
    normalized_id = normalize_datasource_id(datasource_id)
    store = deps.get_enterprise_extensions().user_datasource_store
    before = await store.get_datasource(user_id, normalized_id)
    deleted = await store.delete_datasource(user_id, normalized_id)
    await _audit_personal_datasource_best_effort(
        ctx,
        operation="delete",
        decision="allow",
        resource_id=normalized_id,
        old_summary=_record_for_audit(before),
        metadata={"deleted": deleted},
    )
    return Result(success=True, data={"deleted": deleted})


@router.post(
    "/datasources/{datasource_id}/test",
    response_model=Result[ProbeResultData],
    response_model_exclude_none=True,
    summary="Test Current User Personal Datasource",
    dependencies=[
        Depends(_require_catalog_module),
        Depends(require_platform_active(operation="me.datasource.probe", resource_type="user_datasource")),
    ],
)
async def test_my_personal_datasource(
    datasource_id: str,
    ctx: RequestContextDep,
) -> Result[ProbeResultData]:
    user_id = _require_user_id(ctx)
    record = await deps.get_enterprise_extensions().user_datasource_store.get_datasource(
        user_id,
        normalize_datasource_id(datasource_id),
    )
    if record is None:
        await _audit_personal_datasource_best_effort(
            ctx,
            operation="probe",
            decision="deny",
            resource_id=normalize_datasource_id(datasource_id),
            reason="user datasource not found",
        )
        raise HTTPException(status_code=404, detail="USER_DATASOURCE_NOT_FOUND")
    payload = redact_db_config(datasource_record_to_db_config(record))
    payload["password"] = str(record["password"])
    try:
        await asyncio.to_thread(_probe_datasource_sync, payload)
        await _audit_personal_datasource_best_effort(
            ctx,
            operation="probe",
            decision="allow",
            resource_id=str(record["id"]),
            new_summary=_record_for_audit(record),
            metadata={"probe_ok": True},
        )
        return Result(success=True, data={"ok": True})
    except Exception as exc:
        logger.info("User datasource probe failed: %s", exc)
        await _audit_personal_datasource_best_effort(
            ctx,
            operation="probe",
            decision="allow",
            resource_id=str(record["id"]),
            new_summary=_record_for_audit(record),
            metadata={"probe_ok": False, "error_type": exc.__class__.__name__},
        )
        return Result(success=True, data={"ok": False, "message": str(exc)})


def _require_user_id(ctx: AppContext) -> str:
    if not ctx.user_id:
        raise HTTPException(status_code=401, detail="AUTH_REQUIRED")
    return ctx.user_id


def _validated_datasource_input(body: UpsertPersonalDatasourceRequest, agent_config: Any) -> dict[str, Any]:
    try:
        datasource_type = normalize_datasource_type(body.type)
        host = normalize_host(body.host)
        validate_personal_datasource_policy(agent_config, datasource_type=datasource_type, host=host)
        return {
            "datasource_type": datasource_type,
            "host": host,
            "port": normalize_port(body.port),
            "username": normalize_required_text(body.username, label="Username"),
            "password": normalize_password(body.password),
            "database": normalize_required_text(body.database, label="Database"),
            "schema": normalize_optional_text(body.schema_name, label="Schema"),
            "catalog": normalize_optional_text(body.catalog_name, label="Catalog"),
            "display_name": normalize_display_name(body.display_name),
            "enabled": body.enabled,
        }
    except DatusException as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def _datasource_summary(record: dict[str, Any]) -> PersonalDatasourceSummary:
    datasource_id = str(record["id"])
    return PersonalDatasourceSummary(
        id=datasource_id,
        datasource_key=personal_datasource_key(datasource_id),
        type=str(record["type"]),
        host=str(record["host"]),
        port=str(record["port"]),
        username=str(record["username"]),
        password_hint=str(record.get("password_hint") or ""),
        database=str(record["database"]),
        schema_name=record.get("schema"),
        catalog_name=record.get("catalog"),
        display_name=record.get("display_name"),
        enabled=bool(record.get("enabled")),
        last_used_at=record.get("last_used_at"),
        created_at=record.get("created_at"),
        updated_at=record.get("updated_at"),
    )


def _summary_for_audit(summary: PersonalDatasourceSummary) -> dict[str, Any]:
    return {
        "id": summary.id,
        "datasource_key": summary.datasource_key,
        "type": summary.type,
        "host": summary.host,
        "port": summary.port,
        "username": summary.username,
        "database": summary.database,
        "schema_name": summary.schema_name,
        "catalog_name": summary.catalog_name,
        "display_name": summary.display_name,
        "enabled": summary.enabled,
    }


def _record_for_audit(record: dict[str, Any] | None) -> dict[str, Any] | None:
    if record is None:
        return None
    return _summary_for_audit(_datasource_summary(record))


async def _audit_personal_datasource(
    ctx: AppContext,
    *,
    operation: str,
    decision: str,
    resource_id: str | None,
    reason: str | None = None,
    old_summary: dict[str, Any] | None = None,
    new_summary: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    audit_metadata: dict[str, Any] = {"operation": operation}
    if old_summary is not None:
        audit_metadata["old"] = old_summary
    if new_summary is not None:
        audit_metadata["new"] = new_summary
    if metadata:
        audit_metadata.update(metadata)
    await audit_decision(
        ctx,
        AuditEvent(
            action="me.datasource",
            resource_type="user_datasource",
            resource_id=resource_id,
            decision=decision,
            reason=reason,
            metadata=audit_metadata,
        ),
    )


async def _audit_personal_datasource_best_effort(
    ctx: AppContext,
    *,
    operation: str,
    decision: str,
    resource_id: str | None,
    reason: str | None = None,
    old_summary: dict[str, Any] | None = None,
    new_summary: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    try:
        await _audit_personal_datasource(
            ctx,
            operation=operation,
            decision=decision,
            resource_id=resource_id,
            reason=reason,
            old_summary=old_summary,
            new_summary=new_summary,
            metadata=metadata,
        )
    except Exception as exc:
        logger.warning(
            "Personal datasource audit write failed for operation '%s' decision '%s': %s",
            operation,
            decision,
            exc,
        )
