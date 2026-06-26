"""Enterprise datasource administration routes."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from datus.api import deps
from datus.api.auth.context import AppContext
from datus.api.deps import ServiceDep
from datus.api.models.base_models import Result
from datus.configuration.project_config import ProjectOverride, load_project_override, save_project_override
from datus.utils.exceptions import DatusException, ErrorCode
from datus.utils.loggings import get_logger
from datus_enterprise.audit import AuditEvent, audit_decision
from datus_enterprise.authorization import require_module

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1", tags=["enterprise-datasources"])


AdminDatasourcesCtx = Annotated[AppContext, Depends(require_module("module.admin.datasources"))]


class SetDefaultDatasourceRequest(BaseModel):
    """Project-level datasource default mutation."""

    name: str


class AdminDatasourceSummary(BaseModel):
    """Sanitized datasource summary for admin selection UIs."""

    name: str
    type: str | None = None
    is_default: bool = False


@router.get(
    "/admin/datasources",
    response_model=Result[list[AdminDatasourceSummary]],
    summary="List Admin Datasources",
    description="Admin-only datasource key list. Connection details and secrets are never returned.",
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


@router.put(
    "/admin/datasource-default",
    response_model=Result[dict],
    summary="Set Project Default Datasource",
    description="Admin-only project default datasource mutation. This is not a user request-level datasource switch.",
)
async def set_project_default_datasource_endpoint(
    body: SetDefaultDatasourceRequest,
    svc: ServiceDep,
    ctx: AdminDatasourcesCtx,
) -> Result[dict]:
    """Persist ``default_datasource`` to ``./.datus/config.yml``."""

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
        raise DatusException(
            ErrorCode.COMMON_FIELD_INVALID,
            message=f"Datasource '{body.name}' not found in services.datasources.",
        )

    current = load_project_override() or ProjectOverride()
    current.default_datasource = body.name
    save_project_override(current)

    await _evict_current_project(ctx.project_id or "default")
    await audit_decision(
        ctx,
        AuditEvent(
            action="module.admin.datasources",
            resource_type="datasource",
            resource_id=body.name,
            decision="allow",
            metadata={"mutation": "set_project_default_datasource"},
        ),
    )

    return Result(success=True, data={"default_datasource": body.name, "scope": "project"})


async def _evict_current_project(project_id: str) -> None:
    try:
        await deps.evict_datus_service(project_id)
    except Exception:
        logger.exception(f"Failed to evict service cache for project {project_id}")


def _default_datasource_name(svc: ServiceDep) -> str | None:
    current = getattr(svc.agent_config, "current_datasource", None)
    if current:
        return str(current)
    default = getattr(svc.agent_config.services, "default_datasource", None)
    return str(default) if default else None


def _datasource_type(config) -> str | None:
    if isinstance(config, dict):
        value = config.get("type")
    else:
        value = getattr(config, "type", None)
    return str(value) if value is not None else None
