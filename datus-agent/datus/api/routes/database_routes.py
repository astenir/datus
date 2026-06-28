"""
API routes for Database Management endpoints.
"""

import asyncio
from fnmatch import fnmatchcase
from typing import Annotated, Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from datus.api.auth.context import AppContext
from datus.api.deps import ServiceDep
from datus.api.enterprise.deps import project_request_config, require_module
from datus.api.models.base_models import Result
from datus.api.models.database_models import (
    DatabaseInfo,
    DatabasesData,
    ListDatabasesData,
    ListDatabasesInput,
)
from datus.utils.exceptions import DatusException

router = APIRouter(prefix="/api/v1", tags=["databases"])
_require_catalog_module = require_module("module.datasource_catalog")
CatalogModuleCtx = Annotated[AppContext, Depends(_require_catalog_module)]

# Timeout for datasource network I/O (test_connection, get_databases, get_schemas,
# get_tables). Matches the adapter-level timeout_seconds=30 so the connector gets
# a chance to surface its own error before we give up at the route layer.
_DB_IO_TIMEOUT = 30.0

# Pre-configured parameters to avoid definition-time evaluation in defaults
DATASOURCE_QUERY = Query("", description="Datasource to list databases from")
DATABASE_NAME_QUERY = Query("", description="Database name")
SCHEMA_NAME_QUERY = Query("", description="Schema name")
CATALOG_NAME_QUERY = Query("", description="Catalog name")
INCLUDE_SYS_SCHEMAS_QUERY = Query(False, description="Include system schemas")


@router.get(
    "/catalog/list",
    response_model=Result[DatabasesData],
    summary="List Catalogs",
    description="List available catalogs",
    dependencies=[Depends(_require_catalog_module)],
)
async def list_catalogs(
    svc: ServiceDep,
    _ctx: CatalogModuleCtx,
    datasource_id: Optional[str] = DATASOURCE_QUERY,
    catalog_name: Optional[str] = CATALOG_NAME_QUERY,
    database_name: Optional[str] = DATABASE_NAME_QUERY,
    schema_name: Optional[str] = SCHEMA_NAME_QUERY,
    include_sys_schemas: bool = INCLUDE_SYS_SCHEMAS_QUERY,
) -> Result[DatabasesData]:
    """List available databases."""
    try:
        projection = await project_request_config(
            _ctx,
            svc.agent_config,
            operation="catalog.list",
            requested_datasource=datasource_id or None,
            requested_catalog=catalog_name or None,
            requested_database=database_name or None,
            requested_schema=schema_name or None,
        )
    except DatusException as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    request = ListDatabasesInput(
        datasource_id=datasource_id or projection.config.current_datasource or svc.datasource.current_datasource,
        catalog_name=catalog_name,
        database_name=database_name,
        schema_name=schema_name,
        include_sys_schemas=include_sys_schemas,
    )
    try:
        databases: Result[ListDatabasesData] = await asyncio.wait_for(
            asyncio.to_thread(svc.datasource.list_databases, request),
            timeout=_DB_IO_TIMEOUT,
        )
    except TimeoutError:
        return Result(success=False, errorCode="REQUEST_TIMEOUT", errorMessage="Datasource query timed out")
    if not databases.success or databases.data is None:
        return Result(
            success=False,
            errorCode=databases.errorCode,
            errorMessage=databases.errorMessage,
        )
    selected_datasource = (
        request.datasource_id or projection.config.current_datasource or svc.datasource.current_datasource
    )
    visible_databases = _prune_databases_for_datasource_grant(
        databases.data.databases,
        datasource_id=selected_datasource,
        datasource_grants=projection.datasource_grants,
    )
    return Result(success=True, data=DatabasesData(databases=visible_databases))


def _prune_databases_for_datasource_grant(
    databases: list[DatabaseInfo],
    *,
    datasource_id: str,
    datasource_grants: dict[str, Any],
) -> list[DatabaseInfo]:
    if not datasource_grants:
        return databases
    grant = datasource_grants.get(datasource_id)
    if grant is True:
        return databases
    if grant in (False, None) or not isinstance(grant, dict):
        return []
    if str(grant.get("effect", "allow")).strip().lower() != "allow":
        return []
    if grant.get("allow_catalog") is False:
        return []

    visible_databases: list[DatabaseInfo] = []
    for database in databases:
        if not _scope_allows(grant, "catalogs", database.catalog_name):
            continue
        if not _scope_allows(grant, "databases", database.name):
            continue
        if not _scope_allows(grant, "schemas", database.schema_name):
            continue

        table_patterns = _scope_patterns(grant, "tables")
        tables = _filter_tables_for_grant(database, grant)
        if table_patterns is not None and not tables:
            continue
        update = {"tables": tables}
        if table_patterns is not None and tables is not None:
            update["tables_count"] = len(tables)
        visible_databases.append(database.model_copy(update=update))
    return visible_databases


def _filter_tables_for_grant(database: DatabaseInfo, grant: dict[str, Any]) -> list[str] | None:
    table_patterns = _scope_patterns(grant, "tables")
    if table_patterns is None:
        return database.tables
    if not database.tables:
        return []
    return [
        table for table in database.tables if _matches_any(_table_scope_candidates(database, table), table_patterns)
    ]


def _table_scope_candidates(database: DatabaseInfo, table: str) -> list[str]:
    candidates = [table]
    if database.schema_name:
        candidates.append(f"{database.schema_name}.{table}")
    if database.name:
        candidates.append(f"{database.name}.{table}")
    if database.name and database.schema_name:
        candidates.append(f"{database.name}.{database.schema_name}.{table}")
    if database.catalog_name and database.name:
        candidates.append(f"{database.catalog_name}.{database.name}.{table}")
    if database.catalog_name and database.name and database.schema_name:
        candidates.append(f"{database.catalog_name}.{database.name}.{database.schema_name}.{table}")
    return candidates


def _scope_allows(grant: dict[str, Any], scope_key: str, value: str | None) -> bool:
    patterns = _scope_patterns(grant, scope_key)
    if patterns is None:
        return True
    if not patterns or not value:
        return False
    return _matches_any([value], patterns)


def _scope_patterns(grant: dict[str, Any], scope_key: str) -> list[str] | None:
    if scope_key not in grant or grant.get(scope_key) is None:
        return None
    raw_patterns = grant[scope_key]
    if isinstance(raw_patterns, str):
        raw_patterns = [part.strip() for part in raw_patterns.split(",")]
    if not isinstance(raw_patterns, (list, tuple, set)):
        return []
    return [str(pattern).strip() for pattern in raw_patterns if str(pattern).strip()]


def _matches_any(values: list[str], patterns: list[str]) -> bool:
    return any(fnmatchcase(value, pattern) for value in values for pattern in patterns)
