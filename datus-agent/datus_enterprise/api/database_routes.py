"""Enterprise datasource catalog routes built on the upstream catalog handler."""

import asyncio
from fnmatch import fnmatchcase
from typing import Annotated, Any, Optional

from fastapi import APIRouter, Depends, HTTPException

from datus.api.auth.context import AppContext
from datus.api.deps import ServiceDep
from datus.api.enterprise.deps import project_request_config, require_any_module, require_platform_active
from datus.api.models.base_models import Result
from datus.api.models.database_models import DatabaseInfo, DatabasesData
from datus.api.models.downstream import DatasourcePrewarmData, DatasourceStatusData
from datus.api.routes import database_routes as upstream_database_routes
from datus.api.services.background_drain import track_background_task
from datus.utils.datasource_scope import datasource_field_order, datasource_scope_matches, grant_uses_tree_scope
from datus.utils.exceptions import DatusException

router = APIRouter(prefix="/api/v1", tags=["databases"])
_require_catalog_read = require_any_module("module.datasource_catalog", "module.chat")
CatalogReadCtx = Annotated[AppContext, Depends(_require_catalog_read)]


@router.get(
    "/catalog/list",
    response_model=Result[DatabasesData],
    summary="List Catalogs",
    description="List available catalogs",
    dependencies=[Depends(_require_catalog_read)],
)
async def list_catalogs(
    svc: ServiceDep,
    _ctx: CatalogReadCtx,
    datasource_id: Optional[str] = upstream_database_routes.DATASOURCE_QUERY,
    catalog_name: Optional[str] = upstream_database_routes.CATALOG_NAME_QUERY,
    database_name: Optional[str] = upstream_database_routes.DATABASE_NAME_QUERY,
    schema_name: Optional[str] = upstream_database_routes.SCHEMA_NAME_QUERY,
    include_sys_schemas: bool = upstream_database_routes.INCLUDE_SYS_SCHEMAS_QUERY,
) -> Result[DatabasesData]:
    """Project datasource scope, delegate catalog loading, and prune the result."""
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

    selected_datasource = datasource_id or projection.config.current_datasource or svc.datasource.current_datasource
    result = await upstream_database_routes.list_catalogs(
        svc,
        datasource_id=selected_datasource,
        catalog_name=catalog_name,
        database_name=database_name,
        schema_name=schema_name,
        include_sys_schemas=include_sys_schemas,
    )
    if not result.success or result.data is None:
        if result.errorCode == "REQUEST_TIMEOUT":
            svc.datasource.record_datasource_timeout(selected_datasource)
        return result

    visible_databases = _prune_databases_for_datasource_grant(
        result.data.databases,
        datasource_id=selected_datasource,
        datasource_grants=projection.datasource_grants,
    )
    return Result(success=True, data=DatabasesData(databases=visible_databases))


@router.get(
    "/catalog/status",
    response_model=Result[DatasourceStatusData],
    summary="Get Datasource Connection Status",
    description="Return cached datasource connection status without opening new database connections.",
    dependencies=[Depends(_require_catalog_read)],
)
async def datasource_status(
    svc: ServiceDep,
    _ctx: CatalogReadCtx,
    datasource_id: Optional[str] = upstream_database_routes.DATASOURCE_QUERY,
) -> Result[DatasourceStatusData]:
    """Return cached connection status for authorized datasources."""
    try:
        projection = await project_request_config(
            _ctx,
            svc.agent_config,
            operation="catalog.status",
            requested_datasource=datasource_id or None,
        )
    except DatusException as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    datasource_ids = [datasource_id] if datasource_id else list(projection.config.services.datasources)
    statuses = svc.datasource.datasource_statuses(datasource_ids)
    return Result(success=True, data=DatasourceStatusData(statuses=statuses))


@router.post(
    "/catalog/prewarm",
    response_model=Result[DatasourcePrewarmData],
    summary="Prewarm Datasource Connection",
    description="Queue a background connection prewarm for the selected datasource.",
    dependencies=[
        Depends(_require_catalog_read),
        Depends(require_platform_active(operation="catalog.prewarm", resource_type="datasource")),
    ],
)
async def prewarm_datasource(
    svc: ServiceDep,
    _ctx: CatalogReadCtx,
    datasource_id: Optional[str] = upstream_database_routes.DATASOURCE_QUERY,
) -> Result[DatasourcePrewarmData]:
    """Queue a background prewarm for one authorized datasource."""
    try:
        projection = await project_request_config(
            _ctx,
            svc.agent_config,
            operation="catalog.prewarm",
            requested_datasource=datasource_id or None,
        )
    except DatusException as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    selected_datasource = datasource_id or projection.config.current_datasource
    if not selected_datasource:
        return Result(
            success=False,
            errorCode="DATASOURCE_REQUIRED",
            errorMessage="Datasource is required for prewarm.",
        )

    scheduled = svc.datasource.start_prewarm(selected_datasource)
    if scheduled:
        task = asyncio.create_task(asyncio.to_thread(svc.datasource.prewarm_datasource, selected_datasource))
        track_background_task(task)
    return Result(
        success=True,
        data=DatasourcePrewarmData(
            datasource_id=selected_datasource,
            status="queued" if scheduled else "already_running",
        ),
    )


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
        field_order = datasource_field_order(database.type or "")
        tree_scope = grant_uses_tree_scope(grant, field_order)
        namespace_selected = False
        if tree_scope:
            namespace_field = "schema" if "schema" in field_order and database.schema_name else "database"
            coordinate = _database_coordinate(database)
            if not datasource_scope_matches(
                grant,
                coordinate=coordinate,
                target_field=namespace_field,
                field_order=field_order,
            ):
                continue
            namespace_selected = datasource_scope_matches(
                grant,
                coordinate=coordinate,
                target_field=namespace_field,
                field_order=field_order,
                include_descendants=False,
            )
        else:
            if not _scope_matches(grant, "catalogs", [database.catalog_name]):
                continue
            if not _scope_matches(grant, "databases", [database.name]):
                continue
            if not _scope_matches(grant, "schemas", _schema_scope_candidates(database)):
                continue

        table_patterns = _scope_patterns(grant, "tables")
        tables = _filter_tables_for_grant(database, grant, field_order=field_order, tree_scope=tree_scope)
        if table_patterns is not None and not tables and not namespace_selected:
            continue
        update = {"tables": tables}
        if table_patterns is not None and tables is not None:
            update["tables_count"] = len(tables)
        visible_databases.append(database.model_copy(update=update))
    return visible_databases


def _filter_tables_for_grant(
    database: DatabaseInfo,
    grant: dict[str, Any],
    *,
    field_order: list[str],
    tree_scope: bool,
) -> list[str] | None:
    table_patterns = _scope_patterns(grant, "tables")
    if table_patterns is None:
        return database.tables
    if not database.tables:
        return []
    if tree_scope:
        coordinate = _database_coordinate(database)
        return [
            table
            for table in database.tables
            if datasource_scope_matches(
                grant,
                coordinate={**coordinate, "table": table},
                target_field="table",
                field_order=field_order,
            )
        ]
    return [
        table for table in database.tables if _matches_any(_table_scope_candidates(database, table), table_patterns)
    ]


def _database_coordinate(database: DatabaseInfo) -> dict[str, str]:
    return {
        "catalog": database.catalog_name or "",
        "database": database.name or "",
        "schema": database.schema_name or "",
        "table": "",
    }


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


def _scope_matches(grant: dict[str, Any], scope_key: str, values: list[str | None]) -> bool:
    patterns = _scope_patterns(grant, scope_key)
    if patterns is None:
        return True
    candidates = [value for value in values if value]
    if not patterns or not candidates:
        return False
    return _matches_any(candidates, patterns)


def _scope_patterns(grant: dict[str, Any], scope_key: str) -> list[str] | None:
    if scope_key not in grant or grant.get(scope_key) is None:
        return None
    raw_patterns = grant[scope_key]
    if isinstance(raw_patterns, str):
        raw_patterns = [part.strip() for part in raw_patterns.split(",")]
    if not isinstance(raw_patterns, (list, tuple, set)):
        return []
    patterns = [str(pattern).strip() for pattern in raw_patterns if str(pattern).strip()]
    return patterns or None


def _schema_scope_candidates(database: DatabaseInfo) -> list[str | None]:
    schema_name = database.schema_name
    candidates = [schema_name]
    if database.name and schema_name:
        candidates.append(f"{database.name}.{schema_name}")
    if database.catalog_name and schema_name:
        candidates.append(f"{database.catalog_name}.{schema_name}")
    if database.catalog_name and database.name and schema_name:
        candidates.append(f"{database.catalog_name}.{database.name}.{schema_name}")
    return candidates


def _matches_any(values: list[str], patterns: list[str]) -> bool:
    return any(fnmatchcase(value, pattern) for value in values for pattern in patterns)
