"""Current-user enterprise summary routes."""

from __future__ import annotations

import copy
from fnmatch import fnmatchcase
from typing import Annotated, Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from datus.api import deps
from datus.api.auth.context import AppContext
from datus.api.deps import AppContextDep, ServiceDep
from datus.api.models.base_models import Result
from datus.api.models.cli_models import ChatSessionData

router = APIRouter(prefix="/api/v1", tags=["enterprise-me"])
RequestContextDep = Annotated[AppContext, Depends(deps.get_request_app_context)]

_FEATURE_PERMISSIONS = {
    "chat": "module.chat",
    "sql_executor": "module.sql_executor",
    "datasource_catalog": "module.datasource_catalog",
    "report_view": "module.report.view",
    "report_query": "module.report.query",
    "dashboard_view": "module.dashboard.view",
    "dashboard_query": "module.dashboard.query",
    "kb": "module.kb",
    "mcp": "module.mcp",
    "config_view": "module.config.view",
    "config_edit": "module.config.edit",
}


class MeSummary(BaseModel):
    user_id: str | None = None
    project_id: str | None = None
    roles: list[str] = Field(default_factory=list)
    permissions: list[str] = Field(default_factory=list)
    datasource_grants: dict[str, Any] = Field(default_factory=dict)
    features: dict[str, bool] = Field(default_factory=dict)
    is_admin: bool = False


@router.get("/me", response_model=Result[MeSummary], summary="Get Current User Summary")
async def get_me(ctx: RequestContextDep) -> Result[MeSummary]:
    return Result(success=True, data=_me_summary(ctx))


@router.get("/me/permissions", response_model=Result[list[str]], summary="Get Current User Permissions")
async def get_my_permissions(ctx: RequestContextDep) -> Result[list[str]]:
    return Result(success=True, data=_permissions(ctx))


@router.get(
    "/me/datasource-grants",
    response_model=Result[dict[str, Any]],
    summary="Get Current User Datasource Grants",
)
async def get_my_datasource_grants(ctx: RequestContextDep) -> Result[dict[str, Any]]:
    return Result(success=True, data=_datasource_grants(ctx))


@router.get("/me/features", response_model=Result[dict[str, bool]], summary="Get Current User Features")
async def get_my_features(ctx: RequestContextDep) -> Result[dict[str, bool]]:
    return Result(success=True, data=_features(ctx))


@router.get("/me/sessions", response_model=Result[ChatSessionData], summary="Get Current User Sessions")
async def get_my_sessions(svc: ServiceDep, ctx: AppContextDep) -> Result[ChatSessionData]:
    return await svc.chat.list_sessions_async(user_id=ctx.user_id, subagent_id=None)


@router.get("/me/usage", response_model=Result[list[dict[str, Any]]], summary="Get Current User Usage")
async def get_my_usage(ctx: RequestContextDep) -> Result[list[dict[str, Any]]]:
    store = deps.get_enterprise_extensions().quota_store
    if store is None or not ctx.user_id:
        return Result(success=True, data=[])
    try:
        usage = await store.list_usage(subject_type="user", subject_id=ctx.user_id)
    except Exception:
        return Result(success=False, errorCode="USAGE_LIST_FAILED", errorMessage="Usage list failed.")
    return Result(success=True, data=usage)


def _me_summary(ctx: AppContext) -> MeSummary:
    permissions = _permissions(ctx)
    return MeSummary(
        user_id=ctx.user_id,
        project_id=ctx.project_id,
        roles=_roles(ctx),
        permissions=permissions,
        datasource_grants=_datasource_grants(ctx),
        features=_features_for_permissions(permissions),
        is_admin=bool(ctx.is_admin),
    )


def _roles(ctx: AppContext) -> list[str]:
    roles = {str(role).strip() for role in getattr(ctx, "roles", []) if str(role).strip()}
    principal = getattr(ctx, "principal", {}) or {}
    principal_roles = principal.get("roles")
    if isinstance(principal_roles, str):
        roles.add(principal_roles.strip())
    elif isinstance(principal_roles, (list, tuple, set)):
        roles.update(str(role).strip() for role in principal_roles if str(role).strip())
    return sorted(roles)


def _permissions(ctx: AppContext) -> list[str]:
    permissions = {
        str(permission).strip() for permission in getattr(ctx, "permissions", set()) if str(permission).strip()
    }
    principal = getattr(ctx, "principal", {}) or {}
    principal_permissions = principal.get("permissions")
    if isinstance(principal_permissions, str):
        permissions.add(principal_permissions.strip())
    elif isinstance(principal_permissions, (list, tuple, set)):
        permissions.update(str(permission).strip() for permission in principal_permissions if str(permission).strip())
    return sorted(permissions)


def _datasource_grants(ctx: AppContext) -> dict[str, Any]:
    grants = copy.deepcopy(getattr(ctx, "datasource_grants", {}) or {})
    return grants if isinstance(grants, dict) else {}


def _features(ctx: AppContext) -> dict[str, bool]:
    return _features_for_permissions(_permissions(ctx))


def _features_for_permissions(permissions: list[str]) -> dict[str, bool]:
    return {
        feature: any(permission == "*" or fnmatchcase(required, permission) for permission in permissions)
        for feature, required in _FEATURE_PERMISSIONS.items()
    }
