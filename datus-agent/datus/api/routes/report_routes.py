"""API routes for the visual-report artifact.

* ``GET /api/v1/report/list`` — enumerates all reports under the project's
  ``reports/`` directory and returns manifest summaries.
* ``GET /api/v1/report/detail`` — returns the render/ tree (app.jsx + sibling
  modules) plus the full set of queries/*.sql and queries/*.json files for
  a report produced by the ``gen_visual_report`` subagent.
* ``GET /api/v1/report/html`` — compiles and returns the report as a
  self-contained HTML page for iframe rendering.

Publish and the companion ``ask_report`` subagent are not part of the
agent contract — they live in a separate SaaS host that wraps this
service when present.
"""

from __future__ import annotations

from pathlib import Path
from typing import List

from fastapi import APIRouter, Query, Request, Response
from fastapi.responses import HTMLResponse

from datus.api.deps import ServiceDep
from datus.api.models.base_models import Result
from datus.api.models.report_models import ReportDetail
from datus.schemas.artifact_manifest import ArtifactManifest

router = APIRouter(prefix="/api/v1", tags=["report"])


def _project_files_root(svc: ServiceDep) -> Path:
    """Anchor for ``reports/<slug>/``; matches where
    ``gen_visual_report`` wrote the artifact (CWD in CLI; the
    workspace's project files dir when a SaaS host overrides it)."""
    return Path(svc.agent_config.project_root)


@router.get(
    "/report/list",
    response_model=Result[List[ArtifactManifest]],
    summary="List Report Artifacts",
    description=(
        "Enumerate all reports under the project's reports/ directory. "
        "Returns a list of manifest summaries sorted by recency."
    ),
)
async def list_reports(
    svc: ServiceDep,
) -> Result[List[ArtifactManifest]]:
    return await svc.report.list_reports(
        project_files_root=_project_files_root(svc),
    )


@router.get(
    "/report/html",
    response_class=HTMLResponse,
    summary="Get Report HTML",
    description=(
        "Compile and return the report as a self-contained HTML page that "
        "loads @datus/web-artifact-render from CDN and bootstraps the "
        "React-based report viewer. Suitable for embedding in an iframe."
    ),
)
async def get_report_html(
    svc: ServiceDep,
    slug: str = Query(..., description="Report slug"),
) -> Response:
    result = await svc.report.render_html(
        project_files_root=_project_files_root(svc),
        report_slug=slug,
    )
    if not result.success or result.data is None:
        error_html = (
            "<!doctype html><html><body style='font-family:sans-serif;padding:40px;text-align:center'>"
            f"<h2>Report not found</h2><p>{result.errorMessage or 'Unknown error'}</p>"
            "</body></html>"
        )
        return HTMLResponse(content=error_html, status_code=404)
    return HTMLResponse(content=result.data)


@router.get(
    "/report/detail",
    response_model=Result[ReportDetail],
    summary="Get Report Artifact Detail",
    description=(
        "Return the render/ tree (app.jsx + sibling modules) plus the full set of "
        "queries/*.sql and queries/*.json files for a report produced by the "
        "gen_visual_report subagent."
    ),
)
async def get_report_detail(
    svc: ServiceDep,
    slug: str = Query(..., description="Report slug, e.g. 'account_activity_q1'"),
) -> Result[ReportDetail]:
    return await svc.report.get_detail(
        project_files_root=_project_files_root(svc),
        report_slug=slug,
    )
