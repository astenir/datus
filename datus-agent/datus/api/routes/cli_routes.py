"""
API routes for CLI Command Type endpoints.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Path, Request

from datus.api import deps as api_deps
from datus.api.auth.context import AppContext
from datus.api.deps import get_request_app_context
from datus.api.enterprise.deps import (
    project_request_config,
    require_authorized_module,
    require_module,
    require_platform_active,
)
from datus.api.enterprise.models import ResourceRef
from datus.api.models.base_models import Result
from datus.api.models.cli_models import (
    ExecuteContextData,
    ExecuteContextInput,
    ExecuteSQLData,
    ExecuteSQLInput,
    InternalCommandData,
    InternalCommandInput,
    StopExecuteSQLData,
    StopExecuteSQLInput,
)
from datus.utils.loggings import get_logger
from datus_enterprise.audit import AuditEvent, audit_decision
from datus_enterprise.quota import consume_enterprise_quota

router = APIRouter(prefix="/api/v1", tags=["cli"])
logger = get_logger(__name__)
_require_sql_executor = require_module("module.sql_executor")
SqlExecutorModuleCtx = Annotated[AppContext, Depends(_require_sql_executor)]
RequestContextDep = Annotated[AppContext, Depends(get_request_app_context)]

_DATASOURCE_CATALOG_CONTEXT_TYPES = {"tables", "catalogs", "catalog", "context", "subject", "sql"}
_DATASOURCE_CATALOG_INTERNAL_COMMANDS = {"database", "databases", "schemas", "tables"}
_CHAT_INTERNAL_COMMANDS = {"chat_info", "clear", "sessions"}


async def _context_metadata_auth_context(context_type: str, ctx: RequestContextDep) -> AppContext:
    await _require_datasource_catalog_for_context(ctx, context_type)
    return ctx


async def _internal_metadata_auth_context(command: str, ctx: RequestContextDep) -> AppContext:
    await _require_datasource_catalog_for_internal_command(ctx, command)
    await _require_chat_for_internal_command(ctx, command)
    return ctx


ContextMetadataCtx = Annotated[AppContext, Depends(_context_metadata_auth_context)]
InternalMetadataCtx = Annotated[AppContext, Depends(_internal_metadata_auth_context)]


@router.post(
    "/sql/execute",
    response_model=Result[ExecuteSQLData],
    summary="Execute SQL Query",
    description="Execute SQL query directly against the database. Returns an execute_task_id that can be used to stop the execution.",
    dependencies=[
        Depends(_require_sql_executor),
        Depends(require_platform_active(operation="sql.execute", resource_type="datasource")),
    ],
)
async def execute_sql(
    request: ExecuteSQLInput,
    ctx: SqlExecutorModuleCtx,
    http_request: Request,
) -> Result[ExecuteSQLData]:
    """Execute SQL query directly."""
    svc = await api_deps.resolve_datus_service_for_request(http_request)
    projection = await project_request_config(
        ctx,
        svc.agent_config,
        operation="sql.execute",
        requested_database=request.database_name,
    )
    datasource = projection.principal.get("datasource") or getattr(projection.config, "current_datasource", None)
    quota_error = await consume_enterprise_quota(
        ctx,
        resource="sql.execute",
        amount=1,
        resource_type="datasource",
        resource_id=str(datasource) if datasource else None,
        metadata={"operation": "sql.execute", "result_format": request.result_format},
    )
    if quota_error is not None:
        return quota_error
    result = await svc.cli.execute_sql(request, user_id=ctx.user_id, agent_config=projection.config)
    await _audit_sql_execute(ctx, request, projection, result)
    return result


@router.post(
    "/sql/stop_execute",
    response_model=Result[StopExecuteSQLData],
    summary="Stop SQL Execution",
    description="Stop a running SQL execution by its execute_task_id",
)
async def stop_execute_sql(
    request: StopExecuteSQLInput,
    ctx: SqlExecutorModuleCtx,
    http_request: Request,
) -> Result[StopExecuteSQLData]:
    """Stop a running SQL execution."""
    svc = await api_deps.resolve_datus_service_for_request(http_request)
    return await svc.cli.stop_execute_sql(request.execute_task_id, user_id=ctx.user_id)


@router.post(
    "/context/{context_type}",
    response_model=Result[ExecuteContextData],
    summary="Execute Context Command",
    description="Execute context-related commands (@ prefix commands)",
)
async def execute_context(
    context_type: Annotated[str, Path(description="Type of context command")],
    ctx: ContextMetadataCtx,
    http_request: Request,
    request: ExecuteContextInput = None,
) -> Result[ExecuteContextData]:
    """Execute context command."""
    svc = await api_deps.resolve_datus_service_for_request(http_request)
    if request is None:
        request = ExecuteContextInput(context_type="")
    # Update the context_type from path parameter
    request.context_type = context_type
    projection = None
    if context_type.strip().lower() in _DATASOURCE_CATALOG_CONTEXT_TYPES:
        projection = await project_request_config(
            ctx,
            svc.agent_config,
            operation="catalog.context",
            requested_database=request.database_name,
        )
    return svc.cli.execute_context(
        context_type,
        request,
        agent_config=projection.config if projection else None,
    )


@router.post(
    "/internal/{command}",
    response_model=Result[InternalCommandData],
    summary="Execute Internal Command",
    description="Execute internal management commands (. prefix commands)",
)
async def execute_internal_command(
    command: Annotated[str, Path(description="Internal command name")],
    ctx: InternalMetadataCtx,
    http_request: Request,
    request: InternalCommandInput = None,
) -> Result[InternalCommandData]:
    """Execute internal command."""
    svc = await api_deps.resolve_datus_service_for_request(http_request)
    if request is None:
        request = InternalCommandInput(command="", args="")
    # Update the command from path parameter
    request.command = command
    projection = None
    if command.strip().lower() in _DATASOURCE_CATALOG_INTERNAL_COMMANDS:
        projection = await project_request_config(
            ctx,
            svc.agent_config,
            operation="catalog.internal",
        )
    return svc.cli.execute_internal_command(
        command,
        request,
        user_id=ctx.user_id,
        agent_config=projection.config if projection else None,
    )


async def _require_datasource_catalog_for_context(ctx: AppContext, context_type: str) -> None:
    normalized = context_type.strip().lower()
    if normalized not in _DATASOURCE_CATALOG_CONTEXT_TYPES:
        return
    await require_authorized_module(
        ctx,
        "module.datasource_catalog",
        resource=ResourceRef(type="cli_context", id=normalized),
    )


async def _require_datasource_catalog_for_internal_command(ctx: AppContext, command: str) -> None:
    normalized = command.strip().lower()
    if normalized not in _DATASOURCE_CATALOG_INTERNAL_COMMANDS:
        return
    await require_authorized_module(
        ctx,
        "module.datasource_catalog",
        resource=ResourceRef(type="cli_internal_command", id=normalized),
    )


async def _require_chat_for_internal_command(ctx: AppContext, command: str) -> None:
    normalized = command.strip().lower()
    if normalized not in _CHAT_INTERNAL_COMMANDS:
        return
    await require_authorized_module(
        ctx,
        "module.chat",
        resource=ResourceRef(type="cli_internal_command", id=normalized),
    )


async def _audit_sql_execute(
    ctx: AppContext, request: ExecuteSQLInput, projection, result: Result[ExecuteSQLData]
) -> None:
    datasource = projection.principal.get("datasource") or getattr(projection.config, "current_datasource", None)
    data = result.data if result.success else None
    error_code = str(result.errorCode) if not result.success and result.errorCode is not None else None
    metadata = {
        "database": request.database_name,
        "result_format": request.result_format,
        "execute_task_id": getattr(data, "execute_task_id", None),
        "row_count": getattr(data, "row_count", None),
        "error_code": error_code,
    }
    decision = "allow" if result.success else "deny"
    try:
        await audit_decision(
            ctx,
            AuditEvent(
                action="sql.execute",
                resource_type="datasource",
                resource_id=str(datasource) if datasource else None,
                decision=decision,
                reason=None if result.success else (error_code or "SQL execution failed"),
                metadata={key: value for key, value in metadata.items() if value is not None},
            ),
        )
    except Exception as exc:
        logger.warning(
            "SQL execute audit write failed for decision '%s': %s",
            decision,
            exc,
        )
