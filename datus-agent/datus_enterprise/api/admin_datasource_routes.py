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


ConfigEditCtx = Annotated[AppContext, Depends(require_module("module.config.edit"))]


class SetDefaultDatasourceRequest(BaseModel):
    """Project-level datasource default mutation."""

    name: str


@router.put(
    "/admin/datasource-default",
    response_model=Result[dict],
    summary="Set Project Default Datasource",
    description="Admin-only project default datasource mutation. This is not a user request-level datasource switch.",
)
async def set_project_default_datasource_endpoint(
    body: SetDefaultDatasourceRequest,
    svc: ServiceDep,
    ctx: ConfigEditCtx,
) -> Result[dict]:
    """Persist ``default_datasource`` to ``./.datus/config.yml``."""

    if body.name not in svc.agent_config.services.datasources:
        await audit_decision(
            ctx,
            AuditEvent(
                action="module.config.edit",
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
            action="module.config.edit",
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
