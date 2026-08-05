"""Enterprise datasource administration routes."""

from __future__ import annotations

import asyncio
from inspect import isawaitable
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from datus.api import deps
from datus.api.auth.context import AppContext
from datus.api.deps import ServiceDep
from datus.api.enterprise.deps import require_platform_active
from datus.api.models.base_models import Result
from datus.api.models.database_models import DatabasesData, ListDatabasesData, ListDatabasesInput
from datus.configuration.project_config import ProjectOverride, load_project_override, save_project_override
from datus.utils.loggings import get_logger
from datus_enterprise.admin_datasources.helpers import (
    _audit_datasource_grant,
    _audit_datasource_grant_best_effort,
    _audit_decision_best_effort,
    _datasource_display_name,
    _datasource_error,
    _datasource_type,
    _default_datasource_name,
    _grant_matches_search,
    _grant_record_for_audit,
    _grant_resource_id,
    _grant_summary_for_audit,
    _grant_summary_from_record,
    _grant_validation_error_code,
    _normalized_effect,
    _normalized_scope,
    _validate_existing_grant_subject,
    _validate_grant_effect,
    _validate_grant_identity,
    _validate_grant_scope,
    _validate_optional_grant_filters,
)
from datus_enterprise.admin_datasources.models import (
    AdminDatasourceGrantSummary,
    AdminDatasourceSummary,
    SetDefaultDatasourceRequest,
    UpsertDatasourceGrantRequest,
)
from datus_enterprise.api.admin_pagination import (
    ADMIN_LIST_DEFAULT_LIMIT,
    ADMIN_LIST_MAX_LIMIT,
    AdminListResult,
    paginate_admin_records,
)
from datus_enterprise.audit import AuditEvent, audit_decision
from datus_enterprise.authorization import require_module

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1", tags=["enterprise-datasources"])


_require_admin_datasources = require_module("module.admin.datasources")
AdminDatasourcesCtx = Annotated[AppContext, Depends(_require_admin_datasources)]
# Grant editing loads the complete datasource hierarchy and can require several
# sequential metadata queries. Keep this above the adapter's usual 30-second
# connection timeout so the route does not cut off a recoverable catalog load.
_DB_IO_TIMEOUT = 60.0


@router.get(
    "/admin/datasources",
    response_model=Result[list[AdminDatasourceSummary]],
    summary="List Admin Datasources",
    description="Admin-only datasource key list. Connection details and secrets are never returned.",
    dependencies=[Depends(_require_admin_datasources)],
)
async def list_admin_datasources_endpoint(
    svc: ServiceDep,
    ctx: AdminDatasourcesCtx,
) -> Result[list[AdminDatasourceSummary]]:
    """Return sanitized configured datasource identifiers for admin workflows."""

    datasources = getattr(svc.agent_config.services, "datasources", {}) or {}
    default_datasource = _default_datasource_name(svc)
    items = [
        AdminDatasourceSummary(
            name=name,
            display_name=_datasource_display_name(config),
            type=_datasource_type(config),
            is_default=name == default_datasource,
        )
        for name, config in sorted(datasources.items())
    ]
    await audit_decision(
        ctx,
        AuditEvent(
            action="module.admin.datasources",
            resource_type="datasource",
            resource_id=None,
            decision="allow",
            metadata={"operation": "list_admin_datasources", "count": len(items)},
        ),
    )
    return Result(success=True, data=items)


@router.get(
    "/admin/datasources/{datasource_key}/catalog",
    response_model=Result[DatabasesData],
    summary="List Admin Datasource Catalog",
    description="Admin-only raw datasource catalog for grant editing; not pruned by the caller's datasource grants.",
    dependencies=[Depends(_require_admin_datasources)],
)
async def list_admin_datasource_catalog(
    datasource_key: str,
    svc: ServiceDep,
    ctx: AdminDatasourcesCtx,
    catalog_name: Annotated[str | None, Query(description="Catalog name")] = None,
    database_name: Annotated[str | None, Query(description="Database name")] = None,
    schema_name: Annotated[str | None, Query(description="Schema name")] = None,
    include_sys_schemas: Annotated[bool, Query(description="Include system schemas")] = False,
) -> Result[DatabasesData]:
    """Return an unpruned datasource catalog for admin grant editing."""

    normalized_datasource = datasource_key.strip()
    datasources = getattr(svc.agent_config.services, "datasources", {}) or {}
    if not normalized_datasource or normalized_datasource not in datasources:
        await audit_decision(
            ctx,
            AuditEvent(
                action="module.admin.datasources",
                resource_type="datasource",
                resource_id=normalized_datasource or None,
                decision="deny",
                reason="datasource not found",
                metadata={"operation": "list_admin_datasource_catalog"},
            ),
        )
        return _datasource_error("DATASOURCE_NOT_FOUND", "Datasource not found.")

    request = ListDatabasesInput(
        datasource_id=normalized_datasource,
        catalog_name=catalog_name or "",
        database_name=database_name or "",
        schema_name=schema_name or "",
        include_sys_schemas=include_sys_schemas,
    )
    try:
        result: Result[ListDatabasesData] = await asyncio.wait_for(
            asyncio.to_thread(svc.datasource.list_databases, request),
            timeout=_DB_IO_TIMEOUT,
        )
    except TimeoutError:
        record_timeout = getattr(svc.datasource, "record_datasource_timeout", None)
        if callable(record_timeout):
            record_timeout(normalized_datasource)
        await audit_decision(
            ctx,
            AuditEvent(
                action="module.admin.datasources",
                resource_type="datasource",
                resource_id=normalized_datasource,
                decision="deny",
                reason="datasource catalog timed out",
                metadata={"operation": "list_admin_datasource_catalog"},
            ),
        )
        return _datasource_error("REQUEST_TIMEOUT", "Datasource query timed out.")

    if not result.success or result.data is None:
        await audit_decision(
            ctx,
            AuditEvent(
                action="module.admin.datasources",
                resource_type="datasource",
                resource_id=normalized_datasource,
                decision="deny",
                reason="datasource catalog failed",
                metadata={"operation": "list_admin_datasource_catalog", "errorCode": result.errorCode},
            ),
        )
        return Result(success=False, errorCode=result.errorCode, errorMessage=result.errorMessage)

    databases = result.data.databases
    await audit_decision(
        ctx,
        AuditEvent(
            action="module.admin.datasources",
            resource_type="datasource",
            resource_id=normalized_datasource,
            decision="allow",
            metadata={"operation": "list_admin_datasource_catalog", "count": len(databases)},
        ),
    )
    return Result(success=True, data=DatabasesData(databases=databases))


@router.get(
    "/admin/datasource-grants",
    response_model=AdminListResult[AdminDatasourceGrantSummary],
    summary="List Datasource Grants",
)
async def list_admin_datasource_grants(
    ctx: AdminDatasourcesCtx,
    subject_type: Annotated[str | None, Query(description="Filter by subject type: user or role.")] = None,
    subject_id: Annotated[str | None, Query(description="Filter by subject id.")] = None,
    datasource_key: Annotated[str | None, Query(description="Filter by datasource key.")] = None,
    effect: Annotated[str | None, Query(pattern="^(allow|deny)$")] = None,
    search: Annotated[str | None, Query(max_length=200, description="Search grant fields and scope.")] = None,
    limit: Annotated[int, Query(ge=1, le=ADMIN_LIST_MAX_LIMIT)] = ADMIN_LIST_DEFAULT_LIMIT,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> AdminListResult[AdminDatasourceGrantSummary] | Result[Any]:
    """Return role/user datasource grants for admin workflows."""

    invalid = _validate_optional_grant_filters(
        subject_type=subject_type,
        subject_id=subject_id,
        datasource_key=datasource_key,
    )
    if invalid is not None:
        await _audit_datasource_grant(
            ctx,
            operation="list_admin_datasource_grants",
            decision="deny",
            reason=invalid,
            metadata={"subject_type": subject_type, "subject_id": subject_id, "datasource_key": datasource_key},
        )
        return _datasource_error("DATASOURCE_GRANT_FILTER_INVALID", invalid)

    try:
        store = deps.get_enterprise_extensions().datasource_grant_store
        list_page = getattr(store, "list_grants_page", None)
        records_are_offset = callable(list_page)
        if records_are_offset:
            records = await list_page(
                subject_type=subject_type,
                subject_id=subject_id,
                datasource_key=datasource_key,
                effect=effect,
                search=search,
                limit=limit + 1,
                offset=offset,
            )
        else:
            records = await store.list_grants(
                subject_type=subject_type,
                subject_id=subject_id,
                datasource_key=datasource_key,
            )
    except Exception:
        await _audit_datasource_grant(
            ctx,
            operation="list_admin_datasource_grants",
            decision="deny",
            reason="datasource grant list failed",
        )
        return _datasource_error("DATASOURCE_GRANT_LIST_FAILED", "Datasource grant list failed.")

    grants = [
        _grant_summary_from_record(record)
        for record in records
        if records_are_offset
        or (
            (effect is None or str(record.get("effect") or "allow") == effect) and _grant_matches_search(record, search)
        )
    ]
    page = paginate_admin_records(
        grants,
        limit=limit,
        offset=offset,
        records_are_offset=records_are_offset,
    )
    await _audit_datasource_grant(
        ctx,
        operation="list_admin_datasource_grants",
        decision="allow",
        metadata={
            "count": len(page.data or []),
            "subject_type": subject_type,
            "subject_id": subject_id,
            "datasource_key": datasource_key,
            "effect": effect,
            "offset": offset,
            "has_more": page.pagination.has_more,
        },
    )
    return page


@router.get(
    "/admin/datasource-grants/{subject_type}/{subject_id}/{datasource_key}",
    response_model=Result[AdminDatasourceGrantSummary],
    summary="Get Datasource Grant",
)
async def get_admin_datasource_grant(
    subject_type: str,
    subject_id: str,
    datasource_key: str,
    ctx: AdminDatasourcesCtx,
) -> Result[AdminDatasourceGrantSummary]:
    """Return one datasource grant record."""

    invalid = _validate_grant_identity(
        subject_type=subject_type,
        subject_id=subject_id,
        datasource_key=datasource_key,
    )
    resource_id = _grant_resource_id(subject_type, subject_id, datasource_key)
    if invalid is not None:
        await _audit_datasource_grant(
            ctx,
            operation="get_admin_datasource_grant",
            decision="deny",
            reason=invalid,
            resource_id=resource_id,
        )
        return _datasource_error("DATASOURCE_GRANT_ID_INVALID", invalid)

    try:
        record = await deps.get_enterprise_extensions().datasource_grant_store.get_grant(
            subject_type=subject_type,
            subject_id=subject_id,
            datasource_key=datasource_key,
        )
    except Exception:
        await _audit_datasource_grant(
            ctx,
            operation="get_admin_datasource_grant",
            decision="deny",
            reason="datasource grant read failed",
            resource_id=resource_id,
        )
        return _datasource_error("DATASOURCE_GRANT_READ_FAILED", "Datasource grant read failed.")
    if record is None:
        await _audit_datasource_grant(
            ctx,
            operation="get_admin_datasource_grant",
            decision="deny",
            reason="datasource grant not found",
            resource_id=resource_id,
        )
        return _datasource_error("RESOURCE_NOT_FOUND", "Datasource grant not found.")

    summary = _grant_summary_from_record(record)
    await _audit_datasource_grant(
        ctx,
        operation="get_admin_datasource_grant",
        decision="allow",
        resource_id=resource_id,
        old_summary=_grant_summary_for_audit(summary),
    )
    return Result(success=True, data=summary)


@router.put(
    "/admin/datasource-grants/{subject_type}/{subject_id}/{datasource_key}",
    response_model=Result[AdminDatasourceGrantSummary],
    summary="Upsert Datasource Grant",
    dependencies=[
        Depends(_require_admin_datasources),
        Depends(require_platform_active(operation="admin.datasource_grants.upsert", resource_type="datasource_grant")),
    ],
)
async def upsert_admin_datasource_grant(
    subject_type: str,
    subject_id: str,
    datasource_key: str,
    body: UpsertDatasourceGrantRequest,
    ctx: AdminDatasourcesCtx,
    request: Request,
) -> Result[AdminDatasourceGrantSummary]:
    """Create or replace one role/user datasource grant."""

    invalid = (
        _validate_grant_identity(subject_type=subject_type, subject_id=subject_id, datasource_key=datasource_key)
        or _validate_grant_effect(body.effect)
        or _validate_grant_scope(body.scope)
    )
    resource_id = _grant_resource_id(subject_type, subject_id, datasource_key)
    if invalid is not None:
        await _audit_datasource_grant(
            ctx,
            operation="upsert_admin_datasource_grant",
            decision="deny",
            reason=invalid,
            resource_id=resource_id,
        )
        return _datasource_error(_grant_validation_error_code(invalid), invalid)

    svc = await _resolve_request_service(request)
    if datasource_key not in (getattr(svc.agent_config.services, "datasources", {}) or {}):
        await _audit_datasource_grant(
            ctx,
            operation="upsert_admin_datasource_grant",
            decision="deny",
            reason="datasource not found",
            resource_id=resource_id,
        )
        return _datasource_error("DATASOURCE_NOT_FOUND", "Datasource not found.")

    subject_error = await _validate_existing_grant_subject(
        ctx,
        subject_type=subject_type,
        subject_id=subject_id,
        datasource_key=datasource_key,
    )
    if subject_error is not None:
        return subject_error

    store = deps.get_enterprise_extensions().datasource_grant_store
    try:
        before = await store.get_grant(
            subject_type=subject_type,
            subject_id=subject_id,
            datasource_key=datasource_key,
        )
    except Exception:
        await _audit_datasource_grant(
            ctx,
            operation="upsert_admin_datasource_grant",
            decision="deny",
            reason="datasource grant read failed",
            resource_id=resource_id,
        )
        return _datasource_error("DATASOURCE_GRANT_READ_FAILED", "Datasource grant read failed.")

    try:
        record = await store.put_grant(
            subject_type=subject_type,
            subject_id=subject_id,
            datasource_key=datasource_key,
            effect=_normalized_effect(body.effect),
            scope=_normalized_scope(body.scope),
        )
    except Exception:
        await _audit_datasource_grant(
            ctx,
            operation="upsert_admin_datasource_grant",
            decision="deny",
            reason="datasource grant upsert failed",
            resource_id=resource_id,
            old_summary=_grant_record_for_audit(before),
        )
        return _datasource_error("DATASOURCE_GRANT_UPSERT_FAILED", "Datasource grant upsert failed.")

    summary = _grant_summary_from_record(record)
    await _audit_datasource_grant_best_effort(
        ctx,
        operation="upsert_admin_datasource_grant",
        decision="allow",
        resource_id=resource_id,
        old_summary=_grant_record_for_audit(before),
        new_summary=_grant_summary_for_audit(summary),
    )
    return Result(success=True, data=summary)


@router.delete(
    "/admin/datasource-grants/{subject_type}/{subject_id}/{datasource_key}",
    response_model=Result[dict],
    summary="Delete Datasource Grant",
    dependencies=[
        Depends(_require_admin_datasources),
        Depends(require_platform_active(operation="admin.datasource_grants.delete", resource_type="datasource_grant")),
    ],
)
async def delete_admin_datasource_grant(
    subject_type: str,
    subject_id: str,
    datasource_key: str,
    ctx: AdminDatasourcesCtx,
) -> Result[dict]:
    """Delete one datasource grant record."""

    invalid = _validate_grant_identity(
        subject_type=subject_type,
        subject_id=subject_id,
        datasource_key=datasource_key,
    )
    resource_id = _grant_resource_id(subject_type, subject_id, datasource_key)
    if invalid is not None:
        await _audit_datasource_grant(
            ctx,
            operation="delete_admin_datasource_grant",
            decision="deny",
            reason=invalid,
            resource_id=resource_id,
        )
        return _datasource_error("DATASOURCE_GRANT_ID_INVALID", invalid)

    store = deps.get_enterprise_extensions().datasource_grant_store
    try:
        before = await store.get_grant(
            subject_type=subject_type,
            subject_id=subject_id,
            datasource_key=datasource_key,
        )
    except Exception:
        await _audit_datasource_grant(
            ctx,
            operation="delete_admin_datasource_grant",
            decision="deny",
            reason="datasource grant read failed",
            resource_id=resource_id,
        )
        return _datasource_error("DATASOURCE_GRANT_READ_FAILED", "Datasource grant read failed.")
    if before is None:
        await _audit_datasource_grant(
            ctx,
            operation="delete_admin_datasource_grant",
            decision="deny",
            reason="datasource grant not found",
            resource_id=resource_id,
        )
        return _datasource_error("RESOURCE_NOT_FOUND", "Datasource grant not found.")

    try:
        deleted = await store.delete_grant(
            subject_type=subject_type,
            subject_id=subject_id,
            datasource_key=datasource_key,
        )
    except Exception:
        await _audit_datasource_grant(
            ctx,
            operation="delete_admin_datasource_grant",
            decision="deny",
            reason="datasource grant delete failed",
            resource_id=resource_id,
            old_summary=_grant_record_for_audit(before),
        )
        return _datasource_error("DATASOURCE_GRANT_DELETE_FAILED", "Datasource grant delete failed.")
    if not deleted:
        await _audit_datasource_grant(
            ctx,
            operation="delete_admin_datasource_grant",
            decision="deny",
            reason="datasource grant not found",
            resource_id=resource_id,
        )
        return _datasource_error("RESOURCE_NOT_FOUND", "Datasource grant not found.")

    await _audit_datasource_grant_best_effort(
        ctx,
        operation="delete_admin_datasource_grant",
        decision="allow",
        resource_id=resource_id,
        old_summary=_grant_record_for_audit(before),
    )
    return Result(success=True, data={"deleted": True})


@router.put(
    "/admin/datasource-default",
    response_model=Result[dict],
    summary="Set Project Default Datasource",
    description="Admin-only project default datasource mutation. This is not a user request-level datasource switch.",
    dependencies=[
        Depends(_require_admin_datasources),
        Depends(require_platform_active(operation="admin.datasource_default.update", resource_type="config")),
    ],
)
async def set_project_default_datasource_endpoint(
    body: SetDefaultDatasourceRequest,
    ctx: AdminDatasourcesCtx,
    request: Request,
) -> Result[dict]:
    """Persist ``default_datasource`` to ``./.datus/config.yml``."""

    svc = await _resolve_request_service(request)
    return await _set_project_default_datasource(body, svc, ctx)


async def _resolve_request_service(request: Request) -> ServiceDep:
    service_provider = request.app.dependency_overrides.get(deps.get_datus_service, deps.get_datus_service)
    result = service_provider(request)
    if isawaitable(result):
        return await result
    return result


async def _set_project_default_datasource(
    body: SetDefaultDatasourceRequest,
    svc: ServiceDep,
    ctx: AppContext,
) -> Result[dict]:
    if body.name not in svc.agent_config.services.datasources:
        await audit_decision(
            ctx,
            AuditEvent(
                action="module.admin.datasources",
                resource_type="datasource",
                resource_id=body.name,
                decision="deny",
                reason="datasource not found",
            ),
        )
        raise HTTPException(
            status_code=400,
            detail=f"Datasource '{body.name}' not found in services.datasources.",
        )

    try:
        current = load_project_override() or ProjectOverride()
        current.default_datasource = body.name
        save_project_override(current)
    except Exception:
        logger.exception("Failed to persist project default datasource")
        await audit_decision(
            ctx,
            AuditEvent(
                action="module.admin.datasources",
                resource_type="datasource",
                resource_id=body.name,
                decision="deny",
                reason="project default datasource update failed",
                metadata={"mutation": "set_project_default_datasource"},
            ),
        )
        return _datasource_error("DATASOURCE_DEFAULT_UPDATE_FAILED", "Project default datasource update failed.")

    await _evict_current_project(ctx.project_id or "default")
    await _audit_decision_best_effort(
        ctx,
        AuditEvent(
            action="module.admin.datasources",
            resource_type="datasource",
            resource_id=body.name,
            decision="allow",
            metadata={"mutation": "set_project_default_datasource"},
        ),
        operation="set_project_default_datasource",
        decision="allow",
    )

    return Result(success=True, data={"default_datasource": body.name, "scope": "project"})


async def _evict_current_project(project_id: str) -> None:
    try:
        await deps.evict_datus_service(project_id)
    except Exception:
        logger.exception(f"Failed to evict service cache for project {project_id}")
