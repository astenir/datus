"""API routes for the visual-dashboard artifact.

* ``GET /api/v1/dashboard/list`` — enumerates all dashboards under the
  project's ``dashboards/`` directory and returns manifest summaries.
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
from typing import List

from fastapi import APIRouter, Query, Request, Response
from fastapi.responses import HTMLResponse

from datus.api.deps import ServiceDep
from datus.api.models.base_models import Result
from datus.api.models.dashboard_models import (
    DashboardDetail,
    DashboardQueryRequest,
    SqlQueryResultEnvelope,
)
from datus.schemas.artifact_manifest import ArtifactManifest

router = APIRouter(prefix="/api/v1", tags=["dashboard"])


def _project_files_root(svc: ServiceDep) -> Path:
    """Anchor for ``dashboards/<slug>/``; matches where
    ``gen_visual_dashboard`` wrote the artifact (CWD in CLI; the
    workspace's project files dir when a SaaS host overrides it)."""
    return Path(svc.agent_config.project_root)


@router.get(
    "/dashboard/list",
    response_model=Result[List[ArtifactManifest]],
    summary="List Dashboard Artifacts",
    description=(
        "Enumerate all dashboards under the project's dashboards/ directory. "
        "Returns a list of manifest summaries sorted by recency."
    ),
)
async def list_dashboards(
    svc: ServiceDep,
) -> Result[List[ArtifactManifest]]:
    return await svc.dashboard.list_dashboards(
        project_files_root=_project_files_root(svc),
    )


@router.get(
    "/dashboard/html",
    response_class=HTMLResponse,
    summary="Get Dashboard HTML",
    description=(
        "Compile and return the dashboard as a self-contained HTML page that "
        "loads @datus/web-artifact-render from CDN and bootstraps the interactive "
        "React-based dashboard viewer. Suitable for embedding in an iframe."
    ),
)
async def get_dashboard_html(
    svc: ServiceDep,
    request: Request,
    slug: str = Query(..., description="Dashboard slug"),
    query_endpoint: str = Query(default="", description="Override query endpoint URL (empty = auto-detect)"),
) -> Response:
    # Derive the query endpoint from the request URL if not explicitly provided
    if not query_endpoint:
        base = str(request.base_url).rstrip("/")
        query_endpoint = f"{base}/api/v1/dashboard/query"

    result = await svc.dashboard.render_html(
        project_files_root=_project_files_root(svc),
        dashboard_slug=slug,
        query_endpoint=query_endpoint,
    )
    if not result.success or result.data is None:
        error_html = (
            "<!doctype html><html><body style='font-family:sans-serif;padding:40px;text-align:center'>"
            f"<h2>Dashboard not found</h2><p>{result.errorMessage or 'Unknown error'}</p>"
            "</body></html>"
        )
        return HTMLResponse(content=error_html, status_code=404)
    return HTMLResponse(content=result.data)


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
    slug: str = Query(..., description="Dashboard slug, e.g. 'revenue_overview'"),
) -> Result[DashboardDetail]:
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
) -> Result[SqlQueryResultEnvelope]:
    return await svc.dashboard.run_query(
        project_files_root=_project_files_root(svc),
        dashboard_slug=body.dashboard_slug,
        query_slug=body.query_slug,
        params=body.params,
        published_version=body.published_version,
        # Agent-only deployment: no Postgres-backed version snapshots, so no loader.
        published_template_loader=None,
    )
