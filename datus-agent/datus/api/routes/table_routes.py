"""
API routes for Table and SemanticModel endpoints.
"""

import asyncio
from fnmatch import fnmatchcase
from inspect import isawaitable
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from datus.api import deps
from datus.api.auth.context import AppContext
from datus.api.deps import ServiceDep
from datus.api.enterprise.deps import project_request_config, require_module, require_platform_active
from datus.api.models.base_models import Result
from datus.api.models.table_models import (
    GetSemanticModelData,
    GetTableDetailData,
    SemanticModelInput,
    ValidateSemanticModelData,
)
from datus.api.services.database_service import DatasourceService
from datus.utils.loggings import get_logger
from datus.utils.sql_utils import parse_table_name_parts
from datus_enterprise.audit import AuditEvent, audit_decision

router = APIRouter(prefix="/api/v1", tags=["table"])
logger = get_logger(__name__)
_require_catalog_module = require_module("module.datasource_catalog")
_require_config_edit = require_module("module.config.edit")
CatalogModuleCtx = Annotated[AppContext, Depends(_require_catalog_module)]
ConfigEditCtx = Annotated[AppContext, Depends(_require_config_edit)]


async def _resolve_request_service(request: Request) -> ServiceDep:
    service_provider = request.app.dependency_overrides.get(deps.get_datus_service, deps.get_datus_service)
    result = service_provider(request)
    if isawaitable(result):
        return await result
    return result


# ========== Table Endpoints ==========


@router.get(
    "/table/detail",
    response_model=Result[GetTableDetailData],
    summary="Get Table Detail",
    description="Get detailed information about a table including columns, indexes, and row count",
    dependencies=[Depends(_require_catalog_module)],
)
async def get_table_detail(
    svc: ServiceDep,
    ctx: CatalogModuleCtx,
    datasource_id: str | None = Query(None, description="Datasource selected for this request"),
    table: str = Query(
        ...,
        description="Full table name e.g. 'production_db.public.frpm' or 'db.schema.table'",
    ),
) -> Result[GetTableDetailData]:
    """Get table detail."""
    datasource = await _request_datasource_service(
        ctx,
        svc,
        datasource_id=datasource_id,
        table=table,
        operation="table.detail",
    )
    return await asyncio.to_thread(datasource.get_table_schema, table)


# ========== SemanticModel Endpoints ==========


@router.get(
    "/semantic_model",
    response_model=Result[GetSemanticModelData],
    summary="Get Semantic Model",
    description="Get SemanticModel YAML configuration for a specific table",
    dependencies=[Depends(_require_catalog_module)],
)
async def get_semantic_model(
    svc: ServiceDep,
    ctx: CatalogModuleCtx,
    datasource_id: str | None = Query(None, description="Datasource selected for this request"),
    table: str = Query(
        ...,
        description="Full table name e.g. 'production_db.public.frpm' or 'db.schema.table'",
    ),
    catalog: str | None = Query(None, description="Current catalog context"),
    database: str | None = Query(None, description="Current database context"),
    db_schema: str | None = Query(None, description="Current schema context"),
) -> Result[GetSemanticModelData]:
    """Get SemanticModel YAML."""
    datasource = await _request_datasource_service(
        ctx,
        svc,
        datasource_id=datasource_id,
        table=table,
        operation="semantic_model.read",
    )
    return await asyncio.to_thread(
        datasource.get_semantic_model,
        table,
        catalog=catalog,
        database=database,
        db_schema=db_schema,
    )


@router.post(
    "/semantic_model",
    response_model=Result[dict],
    summary="Save Semantic Model",
    description="Save or update SemanticModel YAML configuration for a table",
    dependencies=[
        Depends(_require_config_edit),
        Depends(require_platform_active(operation="semantic_model.save", resource_type="semantic_model")),
    ],
)
async def save_semantic_model(
    request: SemanticModelInput,
    ctx: ConfigEditCtx,
    http_request: Request,
) -> Result[dict]:
    """Save SemanticModel YAML."""
    svc = await _resolve_request_service(http_request)
    datasource = await _request_datasource_service(
        ctx,
        svc,
        datasource_id=request.datasource_id,
        table=request.table,
        operation="semantic_model.save",
    )
    return await datasource.save_semantic_model(request)


@router.post(
    "/semantic_model/validate",
    response_model=Result[ValidateSemanticModelData],
    summary="Validate Semantic Model",
    description="Validate SemanticModel YAML structure and syntax",
    dependencies=[Depends(_require_config_edit)],
)
async def validate_semantic_model(
    request: SemanticModelInput,
    ctx: ConfigEditCtx,
    http_request: Request,
) -> Result[ValidateSemanticModelData]:
    """Validate SemanticModel YAML."""
    svc = await _resolve_request_service(http_request)
    datasource = await _request_datasource_service(
        ctx,
        svc,
        datasource_id=request.datasource_id,
        table=request.table,
        operation="semantic_model.validate",
    )
    return await datasource.validate_semantic_model(request)


async def _request_datasource_service(
    ctx: AppContext,
    svc: ServiceDep,
    *,
    datasource_id: str | None,
    table: str,
    operation: str,
) -> DatasourceService:
    projection = await project_request_config(
        ctx,
        svc.agent_config,
        operation=f"catalog.{operation}",
        requested_datasource=datasource_id,
    )
    selected_datasource = str(projection.principal.get("datasource") or projection.config.current_datasource or "")
    service_datasource = str(
        getattr(getattr(svc, "datasource", None), "current_datasource", None)
        or getattr(svc.agent_config, "current_datasource", "")
        or ""
    )

    denial = _table_scope_denial(
        table,
        datasource=selected_datasource or service_datasource,
        datasource_grants=projection.datasource_grants,
        dialect=_table_parser_dialect(projection.config, selected_datasource or service_datasource),
    )
    if denial:
        await _audit_table_denial(
            ctx,
            operation=operation,
            table=table,
            datasource=selected_datasource or service_datasource,
            reason=denial,
        )
        raise HTTPException(status_code=403, detail=denial)

    if selected_datasource and selected_datasource == service_datasource:
        return svc.datasource

    base_datasources = getattr(getattr(svc.agent_config, "services", None), "datasources", {}) or {}
    shared_db_manager = (
        getattr(getattr(svc, "datasource", None), "db_manager", None)
        if selected_datasource in base_datasources
        else None
    )
    return DatasourceService(projection.config, db_manager=shared_db_manager)


def _table_scope_denial(
    table: str,
    *,
    datasource: str,
    datasource_grants: dict[str, Any],
    dialect: str | None = None,
) -> str | None:
    if not datasource_grants:
        return None
    grant = datasource_grants.get(datasource)
    if grant is True:
        return None
    if grant in (False, None) or not isinstance(grant, dict):
        return f"Datasource '{datasource}' is not authorized for this request."
    if str(grant.get("effect", "allow")).strip().lower() != "allow":
        return f"Datasource '{datasource}' is not authorized for this request."

    parsed = _parse_table_name(table, dialect=dialect)
    for scope_key, label, values in (
        ("catalogs", "catalog", [parsed["catalog"]]),
        ("databases", "database", [parsed["database"]]),
        ("schemas", "schema", _schema_scope_candidates(parsed)),
    ):
        denial = _scope_denial(grant, scope_key, label, values)
        if denial:
            return denial

    table_patterns = _scope_patterns(grant, "tables")
    if table_patterns is None:
        return None
    if table_patterns and _matches_any(_table_scope_candidates(parsed), table_patterns):
        return None
    return f"Table '{table}' is not authorized for datasource '{datasource}'."


def _scope_denial(grant: dict[str, Any], scope_key: str, label: str, values: list[str | None]) -> str | None:
    patterns = _scope_patterns(grant, scope_key)
    if patterns is None:
        return None
    candidates = [value for value in values if value]
    if not patterns or not candidates:
        return f"Requested table is not sufficiently qualified for scoped {label} authorization."
    if _matches_any(candidates, patterns):
        return None
    return f"Requested {label} '{candidates[0]}' is not authorized."


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


def _table_parser_dialect(agent_config: Any, datasource: str) -> str | None:
    datasources = getattr(getattr(agent_config, "services", None), "datasources", {}) or {}
    datasource_config = datasources.get(datasource)
    config_type = getattr(datasource_config, "type", None)
    if hasattr(config_type, "value"):
        config_type = config_type.value
    if isinstance(config_type, str) and config_type.strip():
        return config_type
    return None


def _parse_table_name(table: str, *, dialect: str | None = None) -> dict[str, str | None]:
    if dialect:
        parts = parse_table_name_parts(table, dialect=dialect)
        return {
            "catalog": parts.get("catalog_name") or None,
            "database": parts.get("database_name") or None,
            "schema": parts.get("schema_name") or None,
            "table": parts.get("table_name") or "",
        }

    parts = [part.strip('"`[] ') for part in table.split(".") if part.strip('"`[] ')]
    parsed = {"catalog": None, "database": None, "schema": None, "table": parts[-1] if parts else ""}
    if len(parts) >= 4:
        parsed["catalog"], parsed["database"], parsed["schema"], parsed["table"] = parts[-4:]
    elif len(parts) == 3:
        parsed["database"], parsed["schema"], parsed["table"] = parts
    elif len(parts) == 2:
        parsed["schema"], parsed["table"] = parts
    return parsed


def _table_scope_candidates(parsed: dict[str, str | None]) -> list[str]:
    table = parsed["table"]
    schema = parsed["schema"]
    database = parsed["database"]
    catalog = parsed["catalog"]
    candidates = [table] if table else []
    if schema and table:
        candidates.append(f"{schema}.{table}")
    if database and table:
        candidates.append(f"{database}.{table}")
    if database and schema and table:
        candidates.append(f"{database}.{schema}.{table}")
    if catalog and database and table:
        candidates.append(f"{catalog}.{database}.{table}")
    if catalog and database and schema and table:
        candidates.append(f"{catalog}.{database}.{schema}.{table}")
    return candidates


def _schema_scope_candidates(parsed: dict[str, str | None]) -> list[str | None]:
    schema = parsed["schema"]
    database = parsed["database"]
    catalog = parsed["catalog"]
    candidates = [schema]
    if database and schema:
        candidates.append(f"{database}.{schema}")
    if catalog and schema:
        candidates.append(f"{catalog}.{schema}")
    if catalog and database and schema:
        candidates.append(f"{catalog}.{database}.{schema}")
    return candidates


def _matches_any(values: list[str], patterns: list[str]) -> bool:
    return any(fnmatchcase(value, pattern) for value in values for pattern in patterns)


async def _audit_table_denial(
    ctx: AppContext,
    *,
    operation: str,
    table: str,
    datasource: str,
    reason: str,
    metadata: dict[str, Any] | None = None,
) -> None:
    audit_metadata = {"datasource": datasource}
    if metadata:
        audit_metadata.update(metadata)
    try:
        await audit_decision(
            ctx,
            AuditEvent(
                action=operation,
                resource_type="table",
                resource_id=table,
                decision="deny",
                reason=reason,
                metadata=audit_metadata,
            ),
        )
    except Exception:
        logger.warning("Table denial audit write failed for operation=%s table=%s", operation, table, exc_info=True)
