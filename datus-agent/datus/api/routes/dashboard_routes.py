"""API routes for the visual-dashboard artifact.

* ``GET /api/v1/dashboard/detail`` — returns render/* + template metadata
  for a dashboard slug.
* ``POST /api/v1/dashboard/query`` — renders a saved Jinja2 SQL template
  against the supplied filter values and executes it live through the
  project's connector.

Published-version snapshotting and the companion ``ask_dashboard``
subagent are not part of the agent contract — they live in a separate
SaaS host that wraps this service when present.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from datus.api.auth.context import AppContext
from datus.api.deps import ServiceDep
from datus.api.enterprise.deps import project_request_config, require_module
from datus.api.models.base_models import Result
from datus.api.models.dashboard_models import (
    DashboardDetail,
    DashboardQueryRequest,
    SqlQueryResultEnvelope,
)
from datus.configuration.agent_config import AgentConfig
from datus_enterprise.artifact_acl import require_artifact_access
from datus_enterprise.audit import AuditEvent, audit_decision

router = APIRouter(prefix="/api/v1", tags=["dashboard"])
DashboardViewModuleCtx = Annotated[AppContext, Depends(require_module("module.dashboard.view"))]
DashboardQueryModuleCtx = Annotated[AppContext, Depends(require_module("module.dashboard.query"))]


def _project_files_root(svc: ServiceDep) -> Path:
    """Anchor for ``dashboards/<slug>/``; matches where
    ``gen_visual_dashboard`` wrote the artifact (CWD in CLI; the
    workspace's project files dir when a SaaS host overrides it)."""
    return Path(svc.agent_config.project_root)


@router.get(
    "/dashboard/detail",
    response_model=Result[DashboardDetail],
    summary="Get Dashboard Artifact Detail",
    description=(
        "Return the render/ tree (app.jsx + sibling modules) plus the parameter "
        "metadata for every saved query template under a dashboard produced by the "
        "gen_visual_dashboard subagent."
    ),
)
async def get_dashboard_detail(
    svc: ServiceDep,
    ctx: DashboardViewModuleCtx,
    slug: str = Query(..., description="Dashboard slug, e.g. 'revenue_overview'"),
) -> Result[DashboardDetail]:
    await require_artifact_access(ctx, artifact_type="dashboard", slug=slug, action="view")
    return await svc.dashboard.get_detail(
        project_files_root=_project_files_root(svc),
        dashboard_slug=slug,
    )


@router.post(
    "/dashboard/query",
    response_model=Result[SqlQueryResultEnvelope],
    summary="Run Dashboard Query",
    description=(
        "Render a saved Jinja2 SQL template with the supplied filter values and "
        "execute it live against the project's bound datasource. Returns the result "
        "envelope expected by RemoteQueryArtifactProvider in @datus/web-artifact."
    ),
)
async def run_dashboard_query(
    body: DashboardQueryRequest,
    svc: ServiceDep,
    ctx: DashboardQueryModuleCtx,
) -> Result[SqlQueryResultEnvelope]:
    await require_artifact_access(ctx, artifact_type="dashboard", slug=body.dashboard_slug, action="query")
    projection = await project_request_config(
        ctx,
        svc.agent_config,
        operation="dashboard.query",
    )
    selected_datasource = projection.principal.get("datasource") or getattr(projection.config, "current_datasource", None)

    async def _project_query_config(datasource: str | None) -> AgentConfig:
        nonlocal selected_datasource
        if not datasource:
            return projection.config
        selected_datasource = datasource
        datasource_projection = await project_request_config(
            ctx,
            svc.agent_config,
            operation="dashboard.query",
            requested_datasource=datasource,
        )
        return datasource_projection.config

    result = await svc.dashboard.run_query(
        project_files_root=_project_files_root(svc),
        dashboard_slug=body.dashboard_slug,
        query_slug=body.query_slug,
        params=body.params,
        published_version=body.published_version,
        # Agent-only deployment: no Postgres-backed version snapshots, so no loader.
        published_template_loader=None,
        agent_config=projection.config,
        agent_config_projector=_project_query_config,
    )
    await _audit_dashboard_query(ctx, body, result, selected_datasource=str(selected_datasource) if selected_datasource else None)
    return result


async def _audit_dashboard_query(
    ctx: AppContext,
    body: DashboardQueryRequest,
    result: Result[SqlQueryResultEnvelope],
    *,
    selected_datasource: str | None,
) -> None:
    data = result.data if result.success else None
    error_code = str(result.errorCode) if not result.success and result.errorCode is not None else None
    metadata = {
        "query_slug": body.query_slug,
        "published_version": body.published_version,
        "datasource": getattr(data, "datasource", None) or selected_datasource,
        "row_count": getattr(data, "row_count", None),
        "error_code": error_code,
    }
    await audit_decision(
        ctx,
        AuditEvent(
            action="dashboard.query",
            resource_type="dashboard",
            resource_id=body.dashboard_slug,
            decision="allow" if result.success else "deny",
            reason=None if result.success else (error_code or "Dashboard query failed"),
            metadata={key: value for key, value in metadata.items() if value is not None},
        ),
    )
