"""Enterprise system status routes."""

from __future__ import annotations

import os
from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from datus.api.auth.context import AppContext
from datus.api.deps import ServiceDep
from datus.api.models.base_models import Result
from datus_enterprise.authorization import require_module

router = APIRouter(prefix="/api/v1", tags=["enterprise-system"])

SystemStatusCtx = Annotated[AppContext, Depends(require_module("module.system.status"))]

_PLATFORM_STATUSES = {"active", "maintenance", "readonly"}


class SystemStatusSummary(BaseModel):
    """Sanitized platform status summary for operators."""

    platform_status: str
    enterprise_enabled: bool
    project_id: str | None = None
    current_datasource: str | None = None
    active_tasks: int
    known_tasks: int


@router.get("/system/status", response_model=Result[SystemStatusSummary], summary="Get System Status")
async def get_system_status(svc: ServiceDep, ctx: SystemStatusCtx) -> Result[SystemStatusSummary]:
    snapshots = _task_snapshots(svc)
    active_tasks = sum(1 for task in snapshots if bool(task.get("is_running")))
    agent_config = getattr(svc, "agent_config", None)
    return Result(
        success=True,
        data=SystemStatusSummary(
            platform_status=_platform_status(),
            enterprise_enabled=_enterprise_enabled(),
            project_id=ctx.project_id,
            current_datasource=getattr(agent_config, "current_datasource", None),
            active_tasks=active_tasks,
            known_tasks=len(snapshots),
        ),
    )


def _platform_status() -> str:
    raw_status = os.getenv("DATUS_PLATFORM_STATUS", "active").strip().lower()
    if raw_status in _PLATFORM_STATUSES:
        return raw_status
    return "unknown"


def _enterprise_enabled() -> bool:
    from datus.api import deps

    return bool(deps.get_enterprise_extensions().enabled)


def _task_snapshots(svc: ServiceDep) -> list[dict]:
    task_manager = getattr(svc, "task_manager", None)
    list_snapshots = getattr(task_manager, "list_task_snapshots", None)
    if not callable(list_snapshots):
        return []
    return list(list_snapshots())
