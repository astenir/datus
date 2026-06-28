"""
API routes for Table and SemanticModel endpoints.
"""

import asyncio
from fnmatch import fnmatchcase
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query

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

router = APIRouter(prefix="/api/v1", tags=["table"])
CatalogModuleCtx = Annotated[AppContext, Depends(require_module("module.datasource_catalog"))]
ConfigEditCtx = Annotated[AppContext, Depends(require_module("module.config.edit"))]


# ========== Table Endpoints ==========


@router.get(
    "/table/detail",
    response_model=Result[GetTableDetailData],
    summary="Get Table Detail",
    description="Get detailed information about a table including columns, indexes, and row count",
)
async def get_table_detail(
    svc: ServiceDep,
    ctx: CatalogModuleCtx,
    table: str = Query(
        ...,
        description="Full table name e.g. 'production_db.public.frpm' or 'db.schema.table'",
    ),
) -> Result[GetTableDetailData]:
    """Get table detail."""
    await _authorize_table_read(ctx, svc, table=table, operation="table.detail")
    return await asyncio.to_thread(svc.datasource.get_table_schema, table)


# ========== SemanticModel Endpoints ==========


@router.get(
    "/semantic_model",
    response_model=Result[GetSemanticModelData],
    summary="Get Semantic Model",
    description="Get SemanticModel YAML configuration for a specific table",
)
async def get_semantic_model(
    svc: ServiceDep,
    ctx: CatalogModuleCtx,
    table: str = Query(
        ...,
        description="Full table name e.g. 'production_db.public.frpm' or 'db.schema.table'",
    ),
) -> Result[GetSemanticModelData]:
    """Get SemanticModel YAML."""
    await _authorize_table_read(ctx, svc, table=table, operation="semantic_model.read")
    return await asyncio.to_thread(svc.datasource.get_semantic_model, table)


@router.post(
    "/semantic_model",
    response_model=Result[dict],
    summary="Save Semantic Model",
    description="Save or update SemanticModel YAML configuration for a table",
)
async def save_semantic_model(
    request: SemanticModelInput,
    svc: ServiceDep,
    ctx: ConfigEditCtx,
    _platform: None = Depends(
        require_platform_active(operation="semantic_model.save", resource_type="semantic_model")
    ),
) -> Result[dict]:
    """Save SemanticModel YAML."""
    await _authorize_table_read(ctx, svc, table=request.table, operation="semantic_model.save")
    return await svc.datasource.save_semantic_model(request)


@router.post(
    "/semantic_model/validate",
    response_model=Result[ValidateSemanticModelData],
    summary="Validate Semantic Model",
    description="Validate SemanticModel YAML structure and syntax",
)
async def validate_semantic_model(
    request: SemanticModelInput,
    svc: ServiceDep,
    ctx: ConfigEditCtx,
) -> Result[ValidateSemanticModelData]:
    """Validate SemanticModel YAML."""
    await _authorize_table_read(ctx, svc, table=request.table, operation="semantic_model.validate")
    return await svc.datasource.validate_semantic_model(request)


async def _authorize_table_read(ctx: AppContext, svc: ServiceDep, *, table: str, operation: str) -> None:
    projection = await project_request_config(ctx, svc.agent_config, operation=operation)
    selected_datasource = str(projection.principal.get("datasource") or projection.config.current_datasource or "")
    service_datasource = str(
        getattr(getattr(svc, "datasource", None), "current_datasource", None)
        or getattr(svc.agent_config, "current_datasource", "")
        or ""
    )
    if selected_datasource and service_datasource and selected_datasource != service_datasource:
        raise HTTPException(status_code=403, detail="DATASOURCE_FORBIDDEN")

    denial = _table_scope_denial(
        table,
        datasource=selected_datasource or service_datasource,
        datasource_grants=projection.datasource_grants,
    )
    if denial:
        raise HTTPException(status_code=403, detail=denial)


def _table_scope_denial(table: str, *, datasource: str, datasource_grants: dict[str, Any]) -> str | None:
    if not datasource_grants:
        return None
    grant = datasource_grants.get(datasource)
    if grant is True:
        return None
    if grant in (False, None) or not isinstance(grant, dict):
        return f"Datasource '{datasource}' is not authorized for this request."
    if str(grant.get("effect", "allow")).strip().lower() != "allow":
        return f"Datasource '{datasource}' is not authorized for this request."

    parsed = _parse_table_name(table)
    for scope_key, label, value in (
        ("catalogs", "catalog", parsed["catalog"]),
        ("databases", "database", parsed["database"]),
        ("schemas", "schema", parsed["schema"]),
    ):
        denial = _scope_denial(grant, scope_key, label, value)
        if denial:
            return denial

    table_patterns = _scope_patterns(grant, "tables")
    if table_patterns is None:
        return None
    if table_patterns and _matches_any(_table_scope_candidates(parsed), table_patterns):
        return None
    return f"Table '{table}' is not authorized for datasource '{datasource}'."


def _scope_denial(grant: dict[str, Any], scope_key: str, label: str, value: str | None) -> str | None:
    patterns = _scope_patterns(grant, scope_key)
    if patterns is None:
        return None
    if not patterns or not value:
        return f"Requested table is not sufficiently qualified for scoped {label} authorization."
    if any(fnmatchcase(value, pattern) for pattern in patterns):
        return None
    return f"Requested {label} '{value}' is not authorized."


def _scope_patterns(grant: dict[str, Any], scope_key: str) -> list[str] | None:
    if scope_key not in grant or grant.get(scope_key) is None:
        return None
    raw_patterns = grant[scope_key]
    if isinstance(raw_patterns, str):
        raw_patterns = [part.strip() for part in raw_patterns.split(",")]
    if not isinstance(raw_patterns, (list, tuple, set)):
        return []
    return [str(pattern).strip() for pattern in raw_patterns if str(pattern).strip()]


def _parse_table_name(table: str) -> dict[str, str | None]:
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
    if database and schema and table:
        candidates.append(f"{database}.{schema}.{table}")
    if catalog and database and schema and table:
        candidates.append(f"{catalog}.{database}.{schema}.{table}")
    return candidates


def _matches_any(values: list[str], patterns: list[str]) -> bool:
    return any(fnmatchcase(value, pattern) for value in values for pattern in patterns)
