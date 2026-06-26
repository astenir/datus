"""
API routes for CLI Command Type endpoints.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Path

from datus.api.auth.context import AppContext
from datus.api.deps import AppContextDep, ServiceDep
from datus.api.enterprise.deps import project_request_config, require_authorized_module, require_module
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

router = APIRouter(prefix="/api/v1", tags=["cli"])
SqlExecutorModuleCtx = Annotated[AppContext, Depends(require_module("module.sql_executor"))]

_DATASOURCE_CATALOG_CONTEXT_TYPES = {"tables", "catalogs"}
_DATASOURCE_CATALOG_INTERNAL_COMMANDS = {"database", "databases", "schemas", "tables"}


@router.post(
    "/sql/execute",
    response_model=Result[ExecuteSQLData],
    summary="Execute SQL Query",
    description="Execute SQL query directly against the database. Returns an execute_task_id that can be used to stop the execution.",
)
async def execute_sql(
    request: ExecuteSQLInput,
    svc: ServiceDep,
    ctx: SqlExecutorModuleCtx,
) -> Result[ExecuteSQLData]:
    """Execute SQL query directly."""
    projection = await project_request_config(
        ctx,
        svc.agent_config,
        operation="sql.execute",
        requested_database=request.database_name,
    )
    return await svc.cli.execute_sql(request, user_id=ctx.user_id, agent_config=projection.config)


@router.post(
    "/sql/stop_execute",
    response_model=Result[StopExecuteSQLData],
    summary="Stop SQL Execution",
    description="Stop a running SQL execution by its execute_task_id",
)
async def stop_execute_sql(
    request: StopExecuteSQLInput,
    svc: ServiceDep,
    ctx: SqlExecutorModuleCtx,
) -> Result[StopExecuteSQLData]:
    """Stop a running SQL execution."""
    return await svc.cli.stop_execute_sql(request.execute_task_id, user_id=ctx.user_id)


@router.post(
    "/context/{context_type}",
    response_model=Result[ExecuteContextData],
    summary="Execute Context Command",
    description="Execute context-related commands (@ prefix commands)",
)
async def execute_context(
    context_type: Annotated[str, Path(description="Type of context command")],
    svc: ServiceDep,
    ctx: AppContextDep,
    request: ExecuteContextInput = None,
) -> Result[ExecuteContextData]:
    """Execute context command."""
    await _require_datasource_catalog_for_context(ctx, context_type)
    if request is None:
        request = ExecuteContextInput(context_type="")
    # Update the context_type from path parameter
    request.context_type = context_type
    return svc.cli.execute_context(context_type, request)


@router.post(
    "/internal/{command}",
    response_model=Result[InternalCommandData],
    summary="Execute Internal Command",
    description="Execute internal management commands (. prefix commands)",
)
async def execute_internal_command(
    command: Annotated[str, Path(description="Internal command name")],
    svc: ServiceDep,
    ctx: AppContextDep,
    request: InternalCommandInput = None,
) -> Result[InternalCommandData]:
    """Execute internal command."""
    await _require_datasource_catalog_for_internal_command(ctx, command)
    if request is None:
        request = InternalCommandInput(command="", args="")
    # Update the command from path parameter
    request.command = command
    return svc.cli.execute_internal_command(command, request)


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
